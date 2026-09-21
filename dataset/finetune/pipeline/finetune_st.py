"""
Method 1: Full finetune of UniXcoder with InfoNCE loss (no LoRA, no ST wrapper).

Trains all parameters. Compared to LoRA this updates the full 126M params,
which on CPU with gradient checkpointing uses ~3-4 GB RAM.
In-batch negatives: every other Rust in the same batch is a negative.

Expected CPU time: ~2-3h for 5 epochs over 1500 pairs at batch_size=8.
"""

import json
import os
import sys
import time
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup
from evaluate import evaluate_embeddings, print_results


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

MODEL_NAME   = "microsoft/unixcoder-base"
OUTPUT_DIR   = os.path.join(ROOT, "model_st")
MAX_LEN      = 512
BATCH_SIZE   = 8
EPOCHS       = 5
LR           = 1e-5       # lower LR than LoRA since we update all params
WARMUP_RATIO = 0.1
TEMPERATURE  = 0.07


class CodePairDataset(Dataset):
    def __init__(self, data):
        self.data = data
    def __len__(self):
        return len(self.data)
    def __getitem__(self, idx):
        return self.data[idx]["c"], self.data[idx]["rust"]


def collate_fn(tokenizer):
    def _collate(batch):
        c_enc = tokenizer([b[0] for b in batch], max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt")
        r_enc = tokenizer([b[1] for b in batch], max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt")
        return c_enc, r_enc
    return _collate


def mean_pool(token_emb, attn_mask):
    mask = attn_mask.unsqueeze(-1).expand(token_emb.size()).float()
    return (token_emb * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def infonce_loss(c_emb, r_emb, temp=TEMPERATURE):
    c_emb = F.normalize(c_emb, dim=-1)
    r_emb = F.normalize(r_emb, dim=-1)
    logits = (c_emb @ r_emb.T) / temp
    labels = torch.arange(len(c_emb))
    return (F.cross_entropy(logits, labels) + F.cross_entropy(logits.T, labels)) / 2


def encode_split(data, tokenizer, model, device, batch_size=16):
    model.eval()
    c_embs, r_embs = [], []
    with torch.no_grad():
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            c_enc = tokenizer([d["c"]    for d in batch], max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt").to(device)
            r_enc = tokenizer([d["rust"] for d in batch], max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt").to(device)
            c_embs.append(mean_pool(model(**c_enc).last_hidden_state, c_enc["attention_mask"]).cpu().numpy())
            r_embs.append(mean_pool(model(**r_enc).last_hidden_state, r_enc["attention_mask"]).cpu().numpy())
    return np.vstack(c_embs), np.vstack(r_embs)


sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402


def load_split(split):
    """Rows for one frozen split, keyed the way this pipeline expects."""
    return [{"problem_id": r["problem_id"], "c": r["c_code"], "rust": r["rust_code"]}
            for r in load(split=split)]


def main():
    device = torch.device("cpu")

    train_data = load_split("train")
    val_data   = load_split("val")
    test_data  = load_split("test")

    print(f"Loading model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model     = AutoModel.from_pretrained(MODEL_NAME)
    # gradient checkpointing halves activation memory at ~20% speed cost
    model.gradient_checkpointing_enable()
    model = model.to(device)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Trainable params: {n_params:,}")

    loader = DataLoader(CodePairDataset(train_data), batch_size=BATCH_SIZE,
                        shuffle=True, collate_fn=collate_fn(tokenizer))

    total_steps  = len(loader) * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)
    optimizer    = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    scheduler    = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    best_val_mrr = 0.0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        t0 = time.time()
        for step, (c_enc, r_enc) in enumerate(loader, 1):
            c_enc = {k: v.to(device) for k, v in c_enc.items()}
            r_enc = {k: v.to(device) for k, v in r_enc.items()}

            c_emb = mean_pool(model(**c_enc).last_hidden_state, c_enc["attention_mask"])
            r_emb = mean_pool(model(**r_enc).last_hidden_state, r_enc["attention_mask"])

            loss = infonce_loss(c_emb, r_emb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step(); scheduler.step(); optimizer.zero_grad()
            total_loss += loss.item()

            if step % 50 == 0:
                print(f"  Epoch {epoch} step {step}/{len(loader)}  loss={total_loss/step:.4f}  {time.time()-t0:.0f}s")

        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch} done. avg_loss={avg_loss:.4f}  time={time.time()-t0:.0f}s")

        c_embs, r_embs = encode_split(val_data, tokenizer, model, device)
        val_res = evaluate_embeddings(c_embs, r_embs, split_name=f"st_val_epoch{epoch}")
        print_results(val_res)

        if val_res["MRR@10"] > best_val_mrr:
            best_val_mrr = val_res["MRR@10"]
            model.save_pretrained(OUTPUT_DIR)
            tokenizer.save_pretrained(OUTPUT_DIR)
            print(f"  -> Best model saved (MRR@10={best_val_mrr:.4f})")

    print("\n--- Final test evaluation (best checkpoint) ---")
    model_best = AutoModel.from_pretrained(OUTPUT_DIR).to(device)
    results_all = {}
    for split, data in [("val", val_data), ("test", test_data)]:
        c_embs, r_embs = encode_split(data, tokenizer, model_best, device)
        res = evaluate_embeddings(c_embs, r_embs, split_name=f"st_{split}")
        print_results(res)
        results_all[split] = res

    with open(os.path.join(ROOT, "outputs", "results_st.json"), "w") as f:
        json.dump(results_all, f, indent=2)
    print("Saved results_st.json")


if __name__ == "__main__":
    main()
