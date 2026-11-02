"""
Problem description uniqueness analysis using OpenAI text-embedding-3-large.

Same analysis as description_similarity.py but with a higher-capacity embedding
model (3072 dims, instruction-tuned for semantic similarity) to check whether
near-duplicate detection results change with a stronger model.

Outputs:
  outputs/description_similarity_openai.json  — same schema as description_similarity.json
"""

import json, os, sys, time
import numpy as np
from collections import defaultdict
from openai import OpenAI

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

API_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'open-api-test', 'api-key.txt')
with open(API_KEY_FILE) as f:
    api_key = f.read().strip()

client = OpenAI(api_key=api_key)
MODEL  = "text-embedding-3-large"
BATCH  = 100   # OpenAI allows up to 2048 inputs per request

# ── load dataset ──────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common.load import load  # noqa: E402

entries = load()

print(f"Loaded {len(entries)} entries")

descs = [str(e['problem_description']) if e['problem_description'] else '' for e in entries]
pids  = [e['problem_id'] for e in entries]
origs = [e['origin'] for e in entries]

short = [(i, len(d)) for i, d in enumerate(descs) if len(d) < 30]
print(f"Very short descriptions (<30 chars): {len(short)}")

# ── embed with OpenAI ─────────────────────────────────────────────────────────

print(f"\nEmbedding {len(descs)} descriptions with {MODEL} ...")
all_embs = []
total_tokens = 0

for i in range(0, len(descs), BATCH):
    batch = descs[i:i + BATCH]
    resp = client.embeddings.create(input=batch, model=MODEL)
    # API returns embeddings in order
    vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
    all_embs.extend(vecs)
    total_tokens += resp.usage.total_tokens
    print(f"  {min(i + BATCH, len(descs))}/{len(descs)}  tokens so far: {total_tokens:,}")
    # gentle rate-limit padding
    if i + BATCH < len(descs):
        time.sleep(0.2)

embs = np.array(all_embs, dtype=np.float32)
# L2-normalise for cosine via dot product
norms = np.linalg.norm(embs, axis=1, keepdims=True)
embs  = embs / np.clip(norms, 1e-9, None)
print(f"Embeddings shape: {embs.shape}  (dim={embs.shape[1]})")
print(f"Total tokens used: {total_tokens:,}")

# ── pairwise cosine similarity ────────────────────────────────────────────────

print("\nComputing pairwise similarity matrix ...")
sim = embs @ embs.T
N   = len(entries)
np.fill_diagonal(sim, 0.0)

upper = sim[np.triu_indices(N, k=1)]

SEP = "=" * 65
print(f"\n{SEP}")
print("GLOBAL SIMILARITY DISTRIBUTION (all pairs)")
print(f"{SEP}")
print(f"  Total pairs: {len(upper):,}")
print(f"  mean={upper.mean():.4f}  std={upper.std():.4f}")
print(f"  min={upper.min():.4f}  p25={np.percentile(upper,25):.4f}  "
      f"p50={np.percentile(upper,50):.4f}  p75={np.percentile(upper,75):.4f}  "
      f"p90={np.percentile(upper,90):.4f}  p95={np.percentile(upper,95):.4f}  "
      f"max={upper.max():.4f}")

thresholds = [0.95, 0.90, 0.85, 0.80, 0.70, 0.60]
print()
for t in thresholds:
    n = (upper > t).sum()
    print(f"  pairs with sim > {t:.2f}: {n:>6,}  ({n/len(upper):.2%})")

# ── per-origin mean similarity ────────────────────────────────────────────────

print(f"\n{SEP}")
print("PER-ORIGIN MEAN PAIRWISE SIMILARITY")
print(f"{SEP}")
origin_idx = defaultdict(list)
for i, o in enumerate(origs):
    origin_idx[o].append(i)

per_origin = {}
for orig, idxs in sorted(origin_idx.items()):
    if len(idxs) < 2:
        continue
    sub  = sim[np.ix_(idxs, idxs)]
    vals = sub[np.triu_indices(len(idxs), k=1)]
    other_idxs = [i for i in range(N) if i not in set(idxs)]
    cross_vals = sim[np.ix_(idxs, other_idxs)].flatten()
    within = float(vals.mean())
    cross  = float(cross_vals.mean())
    per_origin[orig] = {'n': len(idxs), 'within_mean': within, 'cross_mean': cross}
    print(f"  {orig:<22} n={len(idxs):>4}  within mean={within:.4f}  cross mean={cross:.4f}")

# ── near-duplicate detection ──────────────────────────────────────────────────

DUP_THRESH  = 0.90
SUSP_THRESH = 0.80

print(f"\n{SEP}")
print(f"NEAR-DUPLICATES  (sim > {DUP_THRESH})")
print(f"{SEP}")

dup_pairs = []
for i in range(N):
    for j in range(i + 1, N):
        s = float(sim[i, j])
        if s > DUP_THRESH:
            dup_pairs.append((s, i, j))
dup_pairs.sort(reverse=True)
print(f"  Found {len(dup_pairs)} pairs\n")


def show_pairs(pairs, limit=30):
    fmt = f"  {'Sim':>6}  {'PID-A':<36} {'Orig-A':<18} {'PID-B':<36} {'Orig-B'}"
    print(fmt)
    print("  " + "-" * 115)
    for s, i, j in pairs[:limit]:
        print(f"  {s:>6.4f}  {pids[i]:<36} {origs[i]:<18} {pids[j]:<36} {origs[j]}")


show_pairs(dup_pairs)

print(f"\n{SEP}")
print(f"SUSPICIOUS PAIRS  ({SUSP_THRESH} < sim ≤ {DUP_THRESH})")
print(f"{SEP}")

susp_pairs = []
for i in range(N):
    for j in range(i + 1, N):
        s = float(sim[i, j])
        if SUSP_THRESH < s <= DUP_THRESH:
            susp_pairs.append((s, i, j))
susp_pairs.sort(reverse=True)
print(f"  Found {len(susp_pairs)} pairs\n")
show_pairs(susp_pairs, limit=40)

print(f"\n{SEP}")
print("MOST SIMILAR PROBLEMS (each problem's closest neighbour)")
print(f"{SEP}")
max_sim = sim.max(axis=1)
order   = np.argsort(-max_sim)
print(f"  {'PID':<36} {'Origin':<18} {'MaxSim':>7}  {'Closest match'}")
print("  " + "-" * 100)
for idx in order[:30]:
    j = int(np.argmax(sim[idx]))
    print(f"  {pids[idx]:<36} {origs[idx]:<18} {max_sim[idx]:>7.4f}  {pids[j]} ({origs[j]})")

print(f"\n{SEP}")
print("UNIQUENESS SUMMARY")
print(f"{SEP}")
dup_count  = len(set(i for _, i, j in dup_pairs) | set(j for _, i, j in dup_pairs))
susp_count = len(set(i for _, i, j in susp_pairs) | set(j for _, i, j in susp_pairs))
clean      = N - dup_count
print(f"  Total problems          : {N}")
print(f"  Near-duplicates (>{DUP_THRESH:.0%}): {dup_count}  ({dup_count/N:.1%})")
print(f"  Suspicious      (>{SUSP_THRESH:.0%}): {susp_count}  ({susp_count/N:.1%})")
print(f"  Clearly unique  (<{SUSP_THRESH:.0%}): {clean}   ({clean/N:.1%})")
print(f"  Mean max-similarity     : {max_sim.mean():.4f}")
print(f"  Median max-similarity   : {np.median(max_sim):.4f}")

# ── save ──────────────────────────────────────────────────────────────────────

results = {
    'model': MODEL,
    'n': N,
    'total_tokens': total_tokens,
    'global': {
        'mean': float(upper.mean()),
        'std':  float(upper.std()),
        'p50':  float(np.percentile(upper, 50)),
        'p90':  float(np.percentile(upper, 90)),
        'p95':  float(np.percentile(upper, 95)),
        'max':  float(upper.max()),
    },
    'per_origin': per_origin,
    'near_duplicates': [
        {'sim': s, 'pid_a': pids[i], 'origin_a': origs[i],
                   'pid_b': pids[j], 'origin_b': origs[j]}
        for s, i, j in dup_pairs
    ],
    'suspicious': [
        {'sim': s, 'pid_a': pids[i], 'origin_a': origs[i],
                   'pid_b': pids[j], 'origin_b': origs[j]}
        for s, i, j in susp_pairs
    ],
}
with open('outputs/description_similarity_openai.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to outputs/description_similarity_openai.json")
print(f"{SEP}")
