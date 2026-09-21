"""
Artifact smoke test: checks that a clean clone holds a well-formed dataset.

Runs in seconds and downloads nothing - no model weights, no API keys. This is
the check an artifact reviewer can run first; the model-dependent pipelines
(categorization/, finetune/) are validated separately.

Usage:
    python dataset/scripts/smoke_test.py
"""

import os
import re
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from common.load import load, load_pairs, REQUIRED_FIELDS  # noqa: E402
from scripts.build_dataset_v1 import classify_origin, EXPECTED_ORIGINS  # noqa: E402

failures = []


def check(name, condition, detail=""):
    status = "ok  " if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def main():
    print("Loading dataset ...")
    rows = load()
    print(f"  {len(rows)} pairs\n")

    print("Schema")
    check("every row has all v1.0 fields",
          all(all(k in r for k in REQUIRED_FIELDS) for r in rows))
    check("problem_id is unique",
          len({r["problem_id"] for r in rows}) == len(rows))
    check("no empty code or description",
          all(r["c_code"].strip() and r["rust_code"].strip()
              and r["problem_description"].strip() for r in rows))

    print("\nNormalisation")
    c_ok = sum(1 for r in rows if "solution(" in r["c_code"])
    rust_ok = sum(1 for r in rows if re.search(r"fn\s+solution", r["rust_code"]))
    check("C entry point normalised to solution()", c_ok == len(rows),
          f"{c_ok}/{len(rows)}")
    check("Rust entry point normalised to fn solution", rust_ok == len(rows),
          f"{rust_ok}/{len(rows)}")

    print("\nProvenance")
    origins = Counter(r["origin"] for r in rows)
    check("origin breakdown matches the documented one",
          dict(origins) == EXPECTED_ORIGINS, str(dict(origins)))
    check("stored origin agrees with the recovery heuristic",
          all(r["origin"] == classify_origin(r["problem_description"]) for r in rows))

    print("\nDescription format")
    formats = Counter(r["problem_description_format"] for r in rows)
    check("format is only html or text", set(formats) <= {"html", "text"},
          str(dict(formats)))

    print("\nSplits")
    splits = Counter(r["split"] for r in rows)
    check("split values are known",
          set(splits) <= {"train", "val", "test", "unused", "excluded"},
          str(dict(splits)))
    check("train/val/test are disjoint and non-empty",
          all(splits.get(s) for s in ("train", "val", "test")))
    c, r_, p = load_pairs(split="test")
    check("load_pairs returns aligned columns",
          len(c) == len(r_) == len(p) == splits["test"])

    print("\nDifficulty")
    tiers = Counter(r["difficulty"] for r in rows)
    check("tiers are easy/medium/hard", set(tiers) == {"easy", "medium", "hard"},
          str(dict(tiers)))
    check("tiers are roughly 25/50/25",
          abs(tiers["easy"] - tiers["hard"]) <= 5
          and abs(tiers["medium"] - 2 * tiers["easy"]) <= 10,
          str(dict(tiers)))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
