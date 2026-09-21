"""
Dataset difficulty categorization using SFR-Embedding-Code zero-shot embeddings.

For each C<->Rust pair, computes the cosine similarity between the C and the
Rust embedding produced by SFR-Embedding-Code-400M_R with no finetuning, and
bins the pairs by quantile:

  easy   - top 25%    (sim >= p75, implementations already close)
  medium - middle 50% (p25 <= sim < p75)
  hard   - bottom 25% (sim < p25, implementations structurally divergent)

SFR is used rather than UniXcoder on purpose: defining the difficulty tiers
with the same model family that is later finetuned would make "hard" pairs
hard by construction. SFR is trained on a different corpus.

This script previously used `microsoft/unixcoder-base`, which did not match the
`difficulty` labels shipped in dataset.jsonl. It now regenerates those labels
and verifies against them - see --verify.

Output:
  outputs/similarity_scores.json  - per-pair cosine similarity and category
  outputs/categories.json         - problem_id -> "easy" | "medium" | "hard"
"""

import argparse
import json
import os
import sys
from collections import Counter

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402

MODEL_ID = "Salesforce/SFR-Embedding-Code-400M_R"
MAX_LEN = 512
BATCH = 32
OUTPUT_SCORES = os.path.join(ROOT, "outputs", "similarity_scores.json")
OUTPUT_CATS = os.path.join(ROOT, "outputs", "categories.json")


def encode(texts, tokenizer, model, device):
    all_embs = []
    for i in range(0, len(texts), BATCH):
        enc = tokenizer(
            texts[i:i + BATCH],
            padding=True,
            truncation=True,
            max_length=MAX_LEN,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            out = model(**enc)
        # mean pool over non-padding tokens, then L2-normalise
        mask = enc["attention_mask"].unsqueeze(-1).float()
        emb = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
        emb = torch.nn.functional.normalize(emb, dim=-1)
        all_embs.append(emb.cpu().numpy())
        print(f"  encoded {min(i + BATCH, len(texts))}/{len(texts)}")
    return np.vstack(all_embs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="compare the regenerated labels against the ones in "
                         "dataset.jsonl and fail on any disagreement")
    ap.add_argument("--write-labels", action="store_true",
                    help="write the regenerated difficulty and the raw "
                         "similarity back into dataset.jsonl")
    args = ap.parse_args()

    rows = load()
    pids = [r["problem_id"] for r in rows]
    print(f"Loaded {len(rows)} pairs")

    print(f"Loading {MODEL_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"Device: {device}")

    print("\nEncoding C snippets ...")
    c_embs = encode([r["c_code"] for r in rows], tokenizer, model, device)
    print("\nEncoding Rust snippets ...")
    rust_embs = encode([r["rust_code"] for r in rows], tokenizer, model, device)

    sims = (c_embs * rust_embs).sum(axis=1)

    print("\nSimilarity distribution:")
    print(f"  mean={sims.mean():.4f}  std={sims.std():.4f}")
    print(f"  min={sims.min():.4f}  p25={np.percentile(sims, 25):.4f}  "
          f"p50={np.percentile(sims, 50):.4f}  p75={np.percentile(sims, 75):.4f}  "
          f"max={sims.max():.4f}")

    p25 = float(np.percentile(sims, 25))
    p75 = float(np.percentile(sims, 75))

    def assign(sim):
        if sim >= p75:
            return "easy"
        if sim >= p25:
            return "medium"
        return "hard"

    categories = {pid: assign(float(s)) for pid, s in zip(pids, sims)}

    dist = Counter(categories.values())
    print("\nCategory distribution:")
    for cat in ("easy", "medium", "hard"):
        print(f"  {cat}: {dist[cat]} ({100 * dist[cat] / len(rows):.1f}%)")
    print(f"\nThresholds: easy >= {p75:.4f}, hard < {p25:.4f}")

    os.makedirs(os.path.join(ROOT, "outputs"), exist_ok=True)
    with open(OUTPUT_SCORES, "w") as f:
        json.dump([
            {"problem_id": pid, "similarity": float(s), "category": categories[pid]}
            for pid, s in zip(pids, sims)
        ], f, indent=2)
    with open(OUTPUT_CATS, "w") as f:
        json.dump(categories, f, indent=2)
    print(f"\nSaved {OUTPUT_SCORES}\nSaved {OUTPUT_CATS}")

    # Always report how far the regenerated labels are from the shipped ones.
    published = {r["problem_id"]: r["difficulty"] for r in rows}
    disagreements = [pid for pid in pids if published[pid] != categories[pid]]
    print(f"\nAgreement with the labels currently in dataset.jsonl: "
          f"{len(pids) - len(disagreements)}/{len(pids)} "
          f"({100 * (len(pids) - len(disagreements)) / len(pids):.1f}%)")
    if disagreements:
        moved = Counter((published[pid], categories[pid]) for pid in disagreements)
        for (was, now), n in moved.most_common():
            print(f"  {was} -> {now}: {n}")

    if args.write_labels:
        scores = {pid: float(s) for pid, s in zip(pids, sims)}
        dataset_path = os.path.join(ROOT, "..", "dataset.jsonl")
        with open(dataset_path, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        for rec in records:
            rec["difficulty"] = categories[rec["problem_id"]]
            rec["difficulty_score"] = round(scores[rec["problem_id"]], 6)
        with open(dataset_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\nWrote difficulty and difficulty_score for {len(records)} pairs "
              f"to {dataset_path}")
        print("Now re-run scripts/build_dataset_v1.py --write to re-stratify "
              "the split against the new tiers.")

    if args.verify:
        if disagreements:
            print(f"\nFAIL: {len(disagreements)} of {len(pids)} labels differ from "
                  f"the ones shipped in dataset.jsonl.", file=sys.stderr)
            print(f"  first few: {disagreements[:10]}", file=sys.stderr)
            print("  The shipped `difficulty` field is not reproducible by this "
                  "script. Either the pooling/threshold used to produce the "
                  "release differed, or the release was labelled from a "
                  "different input. Resolve before submitting.", file=sys.stderr)
            return 1
        print(f"\nOK: all {len(pids)} labels match dataset.jsonl.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
