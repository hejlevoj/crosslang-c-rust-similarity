"""
Evaluation utilities for cross-language code similarity.

Task: given a C implementation as the query, rank every Rust implementation in
the split and find the one solving the same problem.

Reported:
  mean_pos_sim / mean_neg_sim / sim_gap
  MRR        mean reciprocal rank, no cutoff
  MRR@10     mean reciprocal rank truncated at 10 - zero when the true pair
             ranks below 10
  R@1, R@5, R@10

MRR and MRR@10 are both reported on purpose. An earlier version of this file
computed the untruncated mean and labelled it "MRR@10"; the two coincide only
when almost every positive lands in the top 10, which holds for the finetuned
models but not for the zero-shot baseline. Since the headline claim of this
work is the ratio between those two settings, conflating them overstated it.

Per-tier numbers rank against the FULL candidate pool and group the queries by
tier. Restricting the pool to one tier instead would give each tier a different
pool size (roughly 47/93/47 on the test split), and retrieval scores are not
comparable across pool sizes - the tiers would look different for a reason that
has nothing to do with difficulty.
"""

import numpy as np


def cosine_sim_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity between rows of a and b."""
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a @ b.T  # (N, N)


def _ranks(sim: np.ndarray) -> np.ndarray:
    """1-indexed rank of each true positive, using midranks for ties.

    Counting only strictly-better candidates would hand every tie the best
    possible rank, which flatters a model whose embeddings collapse. The
    midrank convention splits a tie group evenly instead.
    """
    n = len(sim)
    diag = sim[np.arange(n), np.arange(n)]
    greater = (sim > diag[:, None]).sum(axis=1)
    # equal count includes the positive itself, hence the -1
    equal = (sim == diag[:, None]).sum(axis=1) - 1
    return 1 + greater + equal / 2.0


def _metrics(ranks: np.ndarray) -> dict:
    return {
        "MRR": round(float(np.mean(1.0 / ranks)), 4),
        "MRR@10": round(float(np.mean(np.where(ranks <= 10, 1.0 / ranks, 0.0))), 4),
        "R@1": round(float(np.mean(ranks <= 1)), 4),
        "R@5": round(float(np.mean(ranks <= 5)), 4),
        "R@10": round(float(np.mean(ranks <= 10)), 4),
    }


def evaluate_embeddings(c_embs, rust_embs, split_name="test",
                        difficulties=None, origins=None) -> dict:
    """
    c_embs[i] and rust_embs[i] are a positive pair (same problem); every other
    (i, j) is a negative.

    `difficulties` and `origins`, when given, are per-pair labels aligned with
    the embedding rows. They add a breakdown keyed by label, computed over the
    same full candidate pool.
    """
    n = len(c_embs)
    sim = cosine_sim_matrix(c_embs, rust_embs)

    pos = sim[np.arange(n), np.arange(n)]
    neg = sim[~np.eye(n, dtype=bool)]

    ranks = _ranks(sim)

    results = {
        "split": split_name,
        "n": n,
        "mean_pos_sim": round(float(pos.mean()), 4),
        "mean_neg_sim": round(float(neg.mean()), 4),
        "sim_gap": round(float(pos.mean() - neg.mean()), 4),
        **_metrics(ranks),
    }

    for field, labels, order in (
        ("by_difficulty", difficulties, ("easy", "medium", "hard")),
        ("by_origin", origins, None),
    ):
        if labels is None:
            continue
        if len(labels) != n:
            raise ValueError(
                f"{field}: got {len(labels)} labels for {n} pairs")
        keys = order if order else sorted(set(labels))
        labels = np.asarray(labels)
        breakdown = {}
        for key in keys:
            sel = labels == key
            if not sel.any():
                continue
            breakdown[key] = {"n": int(sel.sum()), **_metrics(ranks[sel])}
        results[field] = breakdown

    return results


def print_results(results: dict):
    print(f"\n{'=' * 62}")
    print(f"Evaluation on {results['split']} ({results['n']} pairs, "
          f"pool of {results['n']} candidates)")
    print(f"{'=' * 62}")
    print(f"  mean pos similarity : {results['mean_pos_sim']:.4f}")
    print(f"  mean neg similarity : {results['mean_neg_sim']:.4f}")
    print(f"  similarity gap      : {results['sim_gap']:.4f}")
    print(f"  MRR                 : {results['MRR']:.4f}")
    print(f"  MRR@10              : {results['MRR@10']:.4f}")
    print(f"  R@1 / R@5 / R@10    : {results['R@1']:.4f} / "
          f"{results['R@5']:.4f} / {results['R@10']:.4f}")

    for field, title in (("by_difficulty", "difficulty"), ("by_origin", "origin")):
        if field not in results:
            continue
        print(f"\n  by {title} (same {results['n']}-candidate pool):")
        print(f"    {'':<10} {'n':>5} {'MRR':>8} {'MRR@10':>8} "
              f"{'R@1':>8} {'R@5':>8}")
        for key, m in results[field].items():
            print(f"    {key:<10} {m['n']:>5} {m['MRR']:>8.4f} "
                  f"{m['MRR@10']:>8.4f} {m['R@1']:>8.4f} {m['R@5']:>8.4f}")
    print(f"{'=' * 62}\n")
