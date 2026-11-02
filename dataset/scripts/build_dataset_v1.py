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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(ROOT, "dataset.jsonl")

# Counts of the original v0 release. The recovery below is validated against
# them: if it stops matching, the recovery heuristic is wrong. Only the origins
# actually present in the input are checked, so this script stays idempotent
# after the drop below has been applied once.
RELEASE_ORIGINS = {"codenet": 839, "xcodeeval": 1018, "common-algorithms": 29}

# Origins excluded from the dataset.
#
# common-algorithms: 29 pairs (1.5%) taken from TheAlgorithms, dropped for two
# reasons that point the same way. Licensing - they are the only copyleft
# content (TheAlgorithms/C is GPL-3.0) and the only records whose two halves
# carry different licences (the Rust side is MIT), which is most of the legal
# complexity of the dataset for 1.5% of its size. And fit - they have no
# problem statement (the description is a bare title such as "Bead sort") and
# their functions take arguments rather than reading stdin, so they are
# structurally unlike the 1857 competitive-programming pairs.
DROPPED_ORIGINS = {"common-algorithms"}

# What the dataset should contain once the drop is applied.
EXPECTED_ORIGINS = {k: v for k, v in RELEASE_ORIGINS.items()
                    if k not in DROPPED_ORIGINS}

# SPDX expression governing each record, by source. See DATA_LICENSES.md for
# where each of these comes from and what it obliges a redistributor to do.
# common-algorithms carries two: the C side is taken from TheAlgorithms/C
# (GPL-3.0) and the Rust side from TheAlgorithms/Rust (MIT).
ORIGIN_LICENSES = {
    "codenet": "CDLA-Permissive-2.0",
    "xcodeeval": "CC-BY-NC-4.0",
    "common-algorithms": "GPL-3.0-only AND MIT",
}

# Split parameters. The split is stratified by (origin, difficulty) so that
# every tier and every source keeps its share in train, val and test - a
# retrieval score on the test set is otherwise not comparable across tiers.
#
# This replaces the earlier scheme, which drew a flat random split at run time
# after dropping pairs over a length threshold. That threshold excluded exactly
# one pair (problem 0257, 16460 chars of C; the next longest is 4649) while the
# Rust threshold excluded none, and the models truncate at 512 tokens anyway -
# so it bought nothing and made the split sizes depend on the input file.
SEED = 42
TRAIN_FRAC, VAL_FRAC = 0.80, 0.10

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


def assign_splits(rows, origins):
    """Stratified train/val/test assignment over every pair.

    Each (origin, difficulty) stratum is shuffled with a fixed seed and cut at
    the same 80/10/10 proportions, so the tier and source mix of the test set
    matches the dataset as a whole. No pair is dropped.

    Returns (mapping problem_id -> split, stats dict).
    """
    strata = {}
    for r in rows:
        key = (origins[r["problem_id"]], r["difficulty"])
        strata.setdefault(key, []).append(r["problem_id"])

    rng = random.Random(SEED)
    splits = {}
    for key in sorted(strata):
        # sort first so the shuffle does not inherit file order
        pids = sorted(strata[key])
        rng.shuffle(pids)
        n = len(pids)
        n_train = round(n * TRAIN_FRAC)
        n_val = round(n * VAL_FRAC)
        # guarantee a non-empty test slice for strata big enough to have one
        if n - n_train - n_val < 1 and n >= 3:
            n_train = n - n_val - 1
        for pid in pids[:n_train]:
            splits[pid] = "train"
        for pid in pids[n_train:n_train + n_val]:
            splits[pid] = "val"
        for pid in pids[n_train + n_val:]:
            splits[pid] = "test"

    counts = Counter(splits.values())
    stats = {
        "total": len(rows),
        "train": counts["train"],
        "val": counts["val"],
        "test": counts["test"],
    }
    return splits, stats


def build(rows):
    origins = {r["problem_id"]: classify_origin(r["problem_description"]) for r in rows}
    rows = [r for r in rows if origins[r["problem_id"]] not in DROPPED_ORIGINS]
    splits, split_stats = assign_splits(rows, origins)
    out = []
    for r in rows:
        # difficulty_score is written by categorization/categorize.py
        # --write-labels; carry it through when it is already there.
        score = {"difficulty_score": r["difficulty_score"]} \
            if "difficulty_score" in r else {}
        out.append({
            "problem_id": r["problem_id"],
            "origin": origins[r["problem_id"]],
            "license": ORIGIN_LICENSES[origins[r["problem_id"]]],
            "problem_description": r["problem_description"],
            "problem_description_format": describe_format(r["problem_description"]),
            "c_code": r["c_code"],
            "rust_code": r["rust_code"],
            "difficulty": r["difficulty"],
            **score,
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

    print(f"Loaded {len(rows)} pairs from {DATASET}")

    # validate the recovery on the input, before anything is dropped
    recovered = Counter(classify_origin(r["problem_description"]) for r in rows)
    print("\nRecovered origin (input):")
    mismatch = False
    for name, count in sorted(recovered.items()):
        expected = RELEASE_ORIGINS.get(name)
        ok = expected == count
        mismatch |= not ok
        note = "OK" if ok else f"MISMATCH (release had {expected})"
        dropped = "  [dropped]" if name in DROPPED_ORIGINS else ""
        print(f"  {name:20s} {count:5d}   {note}{dropped}")

    out, split_stats = build(rows)

    origins = Counter(r["origin"] for r in out)
    formats = Counter(r["problem_description_format"] for r in out)

    if len(out) != len(rows):
        print(f"\nDropped {len(rows) - len(out)} pairs "
              f"({', '.join(sorted(DROPPED_ORIGINS))}) -> {len(out)} remain")

    print("\nDescription format:")
    for name, count in sorted(formats.items()):
        print(f"  {name:20s} {count:5d}")

    print("\nFrozen split:")
    for name, count in split_stats.items():
        print(f"  {name:20s} {count:5d}")

    if mismatch:
        print("\nERROR: origin recovery does not match the documented breakdown.",
              file=sys.stderr)
        return 1
    if dict(origins) != EXPECTED_ORIGINS:
        print(f"\nERROR: after the drop the dataset should hold "
              f"{EXPECTED_ORIGINS}, got {dict(origins)}.", file=sys.stderr)
        return 1

    print("\nTest-set composition (should mirror the dataset):")
    test_rows = [r for r in out if r["split"] == "test"]
    for field in ("origin", "difficulty"):
        overall = Counter(r[field] for r in out)
        in_test = Counter(r[field] for r in test_rows)
        parts = [f"{k}={100 * in_test[k] / len(test_rows):.1f}%"
                 f"/{100 * overall[k] / len(out):.1f}%" for k in sorted(overall)]
        print(f"  {field:12s} " + "  ".join(parts))

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
