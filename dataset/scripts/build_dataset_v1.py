"""
Build the v1.0 dataset from the v0 release by recovering fields that were
dropped when the release was produced.

Recovered here:

  origin                      - which upstream corpus a pair came from
  problem_description_format  - "html" (AtCoder markup) or "text"
  split                       - frozen train/val/test assignment

Not recoverable from the released file (see PUBLICATION_PLAN.md, B5):

  origin_problem_id / origin_url
      The release keeps no link back to the upstream problem. Recovering
      these needs a match against the public CodeNet / xCodeEval corpora.

  difficulty_score
      The published `difficulty` bins come from SFR-Embedding-Code-400M_R
      cosine similarity, but only the bin was kept. Regenerating the score
      means re-running the model (see categorization/).

Usage:
    python dataset/scripts/build_dataset_v1.py            # check only
    python dataset/scripts/build_dataset_v1.py --write    # rewrite dataset.jsonl
"""

import argparse
import json
import os
import random
import re
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATASET = os.path.join(ROOT, "dataset.jsonl")

# Counts reported in dataset/README.md. The recovery below is validated
# against them: if it stops matching, the recovery heuristic is wrong.
EXPECTED_ORIGINS = {"codenet": 839, "xcodeeval": 1018, "common-algorithms": 29}

# Split parameters, kept identical to finetune/pipeline/prepare_data.py so the
# frozen split reproduces what that script generates from the same input.
SEED = 42
MAX_C_CHARS = 10000
MAX_RUST_CHARS = 5000
N_TRAIN, N_VAL, N_TEST = 1500, 200, 300

_HTML_TAG = re.compile(r"</(p|div|section|span|var|h3|li|ul|pre|blockquote)>", re.I)


def classify_origin(description):
    """Recover the upstream corpus from the shape of the problem description.

    The three sources left distinct traces in the release:

    common-algorithms  bare algorithm names ("Heap sort", "Rot13") - the
                       textbook reference implementations carry no statement.
    codenet            AtCoder statements kept as raw HTML.
    xcodeeval          Codeforces statements as plain text, usually with
                       $$$...$$$ math delimiters.
    """
    text = description.strip()
    if len(text) < 30 and "\n" not in text and not text.endswith("."):
        return "common-algorithms"
    if _HTML_TAG.search(text):
        return "codenet"
    return "xcodeeval"


def describe_format(description):
    return "html" if _HTML_TAG.search(description.strip()) else "text"


def assign_splits(rows):
    """Reproduce prepare_data.py's split and freeze it into the dataset.

    Returns (mapping problem_id -> split, stats dict). Pairs dropped by the
    length filter are marked "excluded" rather than silently disappearing.
    """
    kept = [
        r["problem_id"]
        for r in rows
        if len(r["c_code"]) <= MAX_C_CHARS and len(r["rust_code"]) <= MAX_RUST_CHARS
    ]
    excluded = [r["problem_id"] for r in rows if r["problem_id"] not in set(kept)]

    random.seed(SEED)
    random.shuffle(kept)

    n_test = min(N_TEST, len(kept) - N_TRAIN - N_VAL)
    splits = {}
    for pid in kept[:N_TRAIN]:
        splits[pid] = "train"
    for pid in kept[N_TRAIN:N_TRAIN + N_VAL]:
        splits[pid] = "val"
    for pid in kept[N_TRAIN + N_VAL:N_TRAIN + N_VAL + n_test]:
        splits[pid] = "test"
    for pid in kept[N_TRAIN + N_VAL + n_test:]:
        splits[pid] = "unused"
    for pid in excluded:
        splits[pid] = "excluded"

    stats = {
        "total": len(rows),
        "after_length_filter": len(kept),
        "excluded": len(excluded),
        "train": N_TRAIN,
        "val": N_VAL,
        "test": n_test,
    }
    return splits, stats


def build(rows):
    splits, split_stats = assign_splits(rows)
    out = []
    for r in rows:
        out.append({
            "problem_id": r["problem_id"],
            "origin": classify_origin(r["problem_description"]),
            "problem_description": r["problem_description"],
            "problem_description_format": describe_format(r["problem_description"]),
            "c_code": r["c_code"],
            "rust_code": r["rust_code"],
            "difficulty": r["difficulty"],
            "split": splits[r["problem_id"]],
        })
    return out, split_stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite dataset.jsonl in place (default: report only)")
    args = ap.parse_args()

    with open(DATASET, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    out, split_stats = build(rows)

    origins = Counter(r["origin"] for r in out)
    formats = Counter(r["problem_description_format"] for r in out)

    print(f"Loaded {len(rows)} pairs from {DATASET}")
    print("\nRecovered origin:")
    for name, count in sorted(origins.items()):
        expected = EXPECTED_ORIGINS.get(name)
        flag = "OK" if expected == count else f"MISMATCH (README says {expected})"
        print(f"  {name:20s} {count:5d}   {flag}")

    print("\nDescription format:")
    for name, count in sorted(formats.items()):
        print(f"  {name:20s} {count:5d}")

    print("\nFrozen split:")
    for name, count in split_stats.items():
        print(f"  {name:20s} {count:5d}")

    if dict(origins) != EXPECTED_ORIGINS:
        print("\nERROR: origin recovery does not match the documented breakdown.",
              file=sys.stderr)
        return 1

    if split_stats["test"] != N_TEST:
        print(f"\nWARNING: the length filter leaves only "
              f"{split_stats['after_length_filter']} pairs, so the test split is "
              f"{split_stats['test']}, not {N_TEST}. Any result reported against a "
              f"{N_TEST}-pair test set was not produced from this file.",
              file=sys.stderr)

    if args.write:
        with open(DATASET, "w", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(out)} pairs to {DATASET}")
    else:
        print("\n(dry run - pass --write to rewrite dataset.jsonl)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
