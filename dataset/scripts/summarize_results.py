"""
Collect every results_*.json into the tables the paper needs.

Prints the overall comparison, the per-tier breakdown, both retrieval
directions, and - where several seeds of the same configuration exist - the
mean and standard deviation across them.

Usage:
    python dataset/scripts/summarize_results.py
    python dataset/scripts/summarize_results.py --split val
    python dataset/scripts/summarize_results.py --latex
"""

import argparse
import glob
import json
import os
import re
import statistics
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "finetune", "outputs")

# Display order; anything unrecognised is appended alphabetically.
ORDER = ["lexical", "baseline", "lora", "st",
         "lexical-anon", "baseline-anon", "lora-anon", "st-anon"]

LABELS = {
    "lexical": "Lexical TF-IDF",
    "baseline": "UniXcoder, zero-shot",
    "lora": "UniXcoder + LoRA",
    "st": "UniXcoder, full",
    "lexical-anon": "Lexical TF-IDF, anon",
    "baseline-anon": "UniXcoder zero-shot, anon",
    "lora-anon": "UniXcoder + LoRA, anon",
    "st-anon": "UniXcoder full, anon",
}

_SEED = re.compile(r"-seed\d+$")


def load_all(split):
    """Group results by configuration, folding seed variants together."""
    groups = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(RESULTS, "results_*.json"))):
        name = os.path.basename(path)[len("results_"):-len(".json")]
        config = _SEED.sub("", name)
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  skipping {name}: {e}", file=sys.stderr)
            continue
        if split not in data:
            continue
        groups[config].append((name, data[split]))
    return groups


def agg(values):
    """mean +- sd as a string, or the bare value when there is only one run."""
    if len(values) == 1:
        return f"{values[0]:.3f}", ""
    m = statistics.mean(values)
    s = statistics.stdev(values)
    return f"{m:.3f}", f"±{s:.3f}"


def ordered(groups):
    known = [c for c in ORDER if c in groups]
    rest = sorted(c for c in groups if c not in ORDER)
    return known + rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=("val", "test"))
    ap.add_argument("--latex", action="store_true", help="emit LaTeX rows")
    args = ap.parse_args()

    groups = load_all(args.split)
    if not groups:
        print(f"No results_*.json with a '{args.split}' split in {RESULTS}")
        return 1

    n = next(iter(groups.values()))[0][1]["n"]
    print(f"\n{args.split} split, {n} candidates\n")

    cols = ("MRR", "MRR@10", "R@1", "R@5", "R@10")
    print(f"{'configuration':<28} {'runs':>4} " + " ".join(f"{c:>14}" for c in cols))
    print("-" * (34 + 15 * len(cols)))
    for config in ordered(groups):
        runs = groups[config]
        cells = []
        for c in cols:
            v, sd = agg([r[c] for _, r in runs])
            cells.append(f"{v}{sd}")
        label = LABELS.get(config, config)
        print(f"{label:<28} {len(runs):>4} " + " ".join(f"{x:>14}" for x in cells))

    print(f"\nMRR by difficulty tier ({args.split})\n")
    tiers = ("easy", "medium", "hard")
    print(f"{'configuration':<28} " + " ".join(f"{t:>14}" for t in tiers))
    print("-" * (29 + 15 * len(tiers)))
    for config in ordered(groups):
        runs = [r for _, r in groups[config] if "by_difficulty" in r]
        if not runs:
            continue
        cells = []
        for t in tiers:
            v, sd = agg([r["by_difficulty"][t]["MRR"] for r in runs])
            cells.append(f"{v}{sd}")
        print(f"{LABELS.get(config, config):<28} " + " ".join(f"{x:>14}" for x in cells))

    print(f"\nRetrieval direction ({args.split}, MRR)\n")
    print(f"{'configuration':<28} {'C->Rust':>14} {'Rust->C':>14}")
    print("-" * 58)
    for config in ordered(groups):
        runs = [r for _, r in groups[config] if "reverse" in r]
        if not runs:
            continue
        f_v, f_sd = agg([r["MRR"] for r in runs])
        r_v, r_sd = agg([r["reverse"]["MRR"] for r in runs])
        print(f"{LABELS.get(config, config):<28} {f_v + f_sd:>14} {r_v + r_sd:>14}")

    # The ablation is the point of the anon runs: show the drop directly.
    pairs = [(c, c + "-anon") for c in ("lexical", "baseline", "lora", "st")]
    shown = [(a, b) for a, b in pairs if a in groups and b in groups]
    if shown:
        print(f"\nIdentifier ablation ({args.split}, MRR)\n")
        print(f"{'configuration':<28} {'normal':>10} {'anon':>10} {'retained':>10}")
        print("-" * 60)
        for a, b in shown:
            va = statistics.mean([r["MRR"] for _, r in groups[a]])
            vb = statistics.mean([r["MRR"] for _, r in groups[b]])
            print(f"{LABELS.get(a, a):<28} {va:>10.3f} {vb:>10.3f} "
                  f"{100 * vb / va:>9.1f}%")

    if args.latex:
        print("\n% LaTeX rows for tab:baselines\n")
        for config in ordered(groups):
            runs = groups[config]
            cells = " & ".join(agg([r[c] for _, r in runs])[0] for c in cols)
            print(f"{LABELS.get(config, config):<28} & {cells} \\\\")

    return 0


if __name__ == "__main__":
    sys.exit(main())
