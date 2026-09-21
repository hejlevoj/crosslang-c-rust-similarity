"""
Method 2: LoRA finetuning on UniXcoder encoder with contrastive loss.

Uses PEFT LoRA applied to query/value projections of every attention layer.
Trains a Siamese encoder: encode C and Rust separately, pull positives
together with InfoNCE (in-batch negatives).

LoRA rank=8, alpha=16, dropout=0.1 → ~400k trainable params (vs 125M total).
Expected CPU time: ~2–4 hours for 5 epochs on 1500 pairs.
"""

import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup
from peft import get_peft_model, LoraConfig, TaskType
from evaluate import evaluate_embeddings, print_results


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402
from common.runtime import get_device, env_int  # noqa: E402

MODEL_NAME   = "microsoft/unixcoder-base"
OUTPUT_DIR   = os.path.join(ROOT, "model_lora")
MAX_LEN      = 512
BATCH_SIZE   = env_int("BATCH_SIZE", 8)
EPOCHS       = env_int("EPOCHS", 5)
LR           = 2e-4
WARMUP_RATIO = 0.1
TEMPERATURE  = 0.07

LORA_R       = 8
LORA_ALPHA   = 16
LORA_DROPOUT = 0.1
# target the Q and V projections inside every attention layer
LORA_TARGETS = ["query", "value"]


class CodePairDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]["c"], self.data[idx]["rust"]


def collate_fn(tokenizer, max_len):
    def _collate(batch):
        c_texts    = [b[0] for b in batch]
        rust_texts = [b[1] for b in batch]
        c_enc = tokenizer(c_texts,    max_length=max_len, padding=True, truncation=True, return_tensors="pt")
        r_enc = tokenizer(rust_texts, max_length=max_len, padding=True, truncation=True, return_tensors="pt")
        return c_enc, r_enc
    return _collate


def mean_pool(token_emb, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(token_emb.size()).float()
    return (token_emb * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def infonce_loss(c_emb, r_emb, temperature=TEMPERATURE):
    """Symmetric InfoNCE loss with in-batch negatives."""
    c_emb = F.normalize(c_emb, dim=-1)
    r_emb = F.normalize(r_emb, dim=-1)
    logits = torch.matmul(c_emb, r_emb.T) / temperature   # (B, B)
    labels = torch.arange(len(c_emb), device=c_emb.device)
    loss_c = F.cross_entropy(logits, labels)
    loss_r = F.cross_entropy(logits.T, labels)
    return (loss_c + loss_r) / 2


def encode_dataset(data, tokenizer, model, device, batch_size=16):
    model.eval()
    c_embs, r_embs = [], []
    with torch.no_grad():
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            c_texts    = [d["c"] for d in batch]
            rust_texts = [d["rust"] for d in batch]
            c_enc = tokenizer(c_texts,    max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt").to(device)
            r_enc = tokenizer(rust_texts, max_length=MAX_LEN, padding=True, truncation=True, return_tensors="pt").to(device)
            c_out = model(**c_enc).last_hidden_state
            r_out = model(**r_enc).last_hidden_state
            c_embs.append(mean_pool(c_out, c_enc["attention_mask"]).cpu().numpy())
            r_embs.append(mean_pool(r_out, r_enc["attention_mask"]).cpu().numpy())
    return np.vstack(c_embs), np.vstack(r_embs)



def load_split(split):
    """Rows for one frozen split, keyed the way this pipeline expects."""
    return [{"problem_id": r["problem_id"], "c": r["c_code"], "rust": r["rust_code"]}
            for r in load(split=split)]


def main():
    device = get_device()

    train_data = load_split("train")
    val_data   = load_split("val")
    test_data  = load_split("test")

    print(f"Loading tokenizer and base model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    base_model = AutoModel.from_pretrained(MODEL_NAME)

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGETS,
        bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
    )
    model = get_peft_model(base_model, lora_config)
    model.print_trainable_parameters()
    model = model.to(device)

    dataset    = CodePairDataset(train_data)
    loader     = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True,
                            collate_fn=collate_fn(tokenizer, MAX_LEN))

    optimizer  = torch.optim.AdamW(model.parameters(), lr=LR)
    total_steps = len(loader) * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)
    scheduler  = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    best_val_mrr = 0.0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        t0 = time.time()
        for step, (c_enc, r_enc) in enumerate(loader, 1):
            c_enc = {k: v.to(device) for k, v in c_enc.items()}
            r_enc = {k: v.to(device) for k, v in r_enc.items()}

            c_out = model(**c_enc).last_hidden_state
            r_out = model(**r_enc).last_hidden_state
            c_emb = mean_pool(c_out, c_enc["attention_mask"])
            r_emb = mean_pool(r_out, r_enc["attention_mask"])

            loss = infonce_loss(c_emb, r_emb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            total_loss += loss.item()

            if step % 50 == 0:
                elapsed = time.time() - t0
                print(f"  Epoch {epoch} step {step}/{len(loader)}  loss={total_loss/step:.4f}  time={elapsed:.0f}s")

        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch} done. avg_loss={avg_loss:.4f}  time={time.time()-t0:.0f}s")

        # validation
        c_embs, r_embs = encode_dataset(val_data, tokenizer, model, device)
        val_res = evaluate_embeddings(c_embs, r_embs, split_name=f"lora_val_epoch{epoch}")
        print_results(val_res)

        if val_res["MRR@10"] > best_val_mrr:
            best_val_mrr = val_res["MRR@10"]
            model.save_pretrained(OUTPUT_DIR)
            tokenizer.save_pretrained(OUTPUT_DIR)
            print(f"  -> Best model saved (MRR@10={best_val_mrr:.4f})")

    print("\n--- Final evaluation on test set (best LoRA checkpoint) ---")
    # reload best
    from peft import PeftModel
    base_model2 = AutoModel.from_pretrained(MODEL_NAME)
    model_best = PeftModel.from_pretrained(base_model2, OUTPUT_DIR).to(device)

    results_all = {}
    for split, data in [("val", val_data), ("test", test_data)]:
        c_embs, r_embs = encode_dataset(data, tokenizer, model_best, device)
        res = evaluate_embeddings(c_embs, r_embs, split_name=f"lora_{split}")
        print_results(res)
        results_all[split] = res

    with open(os.path.join(ROOT, "outputs", "results_lora.json"), "w") as f:
        json.dump(results_all, f, indent=2)
    print("Saved results_lora.json")


if __name__ == "__main__":
    main()
