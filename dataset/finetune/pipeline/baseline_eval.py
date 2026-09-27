"""
Baseline evaluation: zero-shot UniXcoder embeddings, no finetuning.
Encodes all C and Rust functions and runs the evaluation metrics.
"""

import json, os, sys
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from evaluate import evaluate_embeddings, print_results

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402
from common.runtime import get_device, env_int  # noqa: E402

RESULTS_DIR  = os.path.join(ROOT, "outputs")
MODEL_NAME = "microsoft/unixcoder-base"
MAX_LEN = 512
BATCH_SIZE = env_int("EVAL_BATCH_SIZE", 16)


def mean_pool(token_embeddings, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def encode(texts, tokenizer, model, device, batch_size=BATCH_SIZE):
    all_embs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        enc = tokenizer(
            batch,
            max_length=MAX_LEN,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            out = model(**enc)
        emb = mean_pool(out.last_hidden_state, enc["attention_mask"])
        all_embs.append(emb.cpu().numpy())
    return np.vstack(all_embs)



def load_split(split):
    rows = load(split=split)
    return ([r["c_code"] for r in rows],
            [r["rust_code"] for r in rows],
            [r["difficulty"] for r in rows],
            [r["origin"] for r in rows])


def main():
    # Create the results directory up front, not at the end. A LoRA run once
    # trained, evaluated, and then died on the final write because this did not
    # exist - hours of GPU time with nothing saved. Anything that can fail
    # about the output path should fail in the first second.
    os.makedirs(RESULTS_DIR, exist_ok=True)

    device = get_device()
    print(f"Loading model {MODEL_NAME} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    results_all = {}
    for split in ["val", "test"]:
        c_texts, rust_texts, diffs, origins = load_split(split)
        print(f"\nEncoding {split} C ({len(c_texts)} samples)...")
        c_embs = encode(c_texts, tokenizer, model, device)
        print(f"Encoding {split} Rust ({len(rust_texts)} samples)...")
        rust_embs = encode(rust_texts, tokenizer, model, device)

        res = evaluate_embeddings(c_embs, rust_embs,
                                  split_name=f"baseline_{split}",
                                  difficulties=diffs, origins=origins)
        print_results(res)
        results_all[split] = res

    with open(os.path.join(RESULTS_DIR, "results_baseline.json"), "w") as f:
        json.dump(results_all, f, indent=2)
    print("Saved results_baseline.json")


if __name__ == "__main__":
    main()
