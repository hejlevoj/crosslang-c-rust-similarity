"""
Report the frozen train/val/test split.

This script used to generate the split at run time from `random.seed(42)` plus
a length filter, writing data_{train,val,test}.json. Two problems with that:
the split was never distributed, so nobody could reproduce a published number,
and the length filter silently changed the split sizes depending on the input
file. The split now lives in the `split` field of dataset.jsonl and is read
through dataset/common/load.py; this script only reports it.

To regenerate the split, see dataset/scripts/build_dataset_v1.py.
"""

import os
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402

rows = load()
counts = Counter(r["split"] for r in rows)

print(f"Frozen split over {len(rows)} pairs:")
for name in ("train", "val", "test", "unused", "excluded"):
    if counts.get(name):
        print(f"  {name:10s} {counts[name]:5d}")

print("\nBy difficulty within each split:")
for name in ("train", "val", "test"):
    tiers = Counter(r["difficulty"] for r in rows if r["split"] == name)
    print(f"  {name:10s} " + "  ".join(f"{k}={tiers[k]}" for k in ("easy", "medium", "hard")))

print("\nBy origin within each split:")
for name in ("train", "val", "test"):
    origins = Counter(r["origin"] for r in rows if r["split"] == name)
    print(f"  {name:10s} " + "  ".join(f"{k}={v}" for k, v in sorted(origins.items())))

if counts.get("test") != 300:
    print(f"\nNote: the test split holds {counts.get('test')} pairs. Results in this "
          f"repository that were reported against a 300-pair test set were not "
          f"produced from this dataset - see PUBLICATION_PLAN.md (B6).")
