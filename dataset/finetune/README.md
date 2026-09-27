# UniXcoder Finetuning — C↔Rust Cross-Language Code Similarity

Finetunes [`microsoft/unixcoder-base`](https://github.com/microsoft/CodeBERT/tree/master/UniXcoder) to embed C and Rust implementations of the same algorithm close together in vector space. Two methods compared: full-parameter finetuning and LoRA adapters.

## Results

Measured on the 187-pair test split of the 1857-pair dataset, on GPU at Labic.
Each C implementation queries the pool of all 187 Rust implementations.

| Model | MRR | MRR@10 | R@1 | R@5 | R@10 |
|-------|-----|--------|-----|-----|------|
| Chance | 0.031 | 0.016 | 0.005 | 0.027 | 0.053 |
| UniXcoder, zero-shot | 0.189 | 0.170 | 0.134 | 0.203 | 0.283 |
| UniXcoder + LoRA | **0.713** | **0.708** | **0.610** | **0.824** | **0.909** |
| UniXcoder, full finetune | *not run yet* | | | | |

**3.8× over zero-shot on MRR, 4.2× on MRR@10.**

MRR by difficulty tier — same 187-candidate pool, only the queries partitioned:

| Model | Easy (47) | Medium (93) | Hard (47) |
|---|---|---|---|
| UniXcoder, zero-shot | 0.328 | 0.186 | 0.053 |
| UniXcoder + LoRA | 0.947 | 0.760 | 0.386 |
| LoRA gain | 2.9× | 4.1× | 7.3× |

Retrieval is monotone in tier for both models. Since the tiers were cut with
SFR and these models are UniXcoder-based, that ordering is a property of the
pairs rather than of the encoder that defined it. Zero-shot on the hard tier is
0.053 — 1.7× chance, with exactly one of 47 pairs at rank 1.

By origin (LoRA, test): CodeNet 0.775, xCodeEval 0.663. Reweighting for the
tier mix of each accounts for only 26% of that gap, so Codeforces problems are
genuinely harder to match than AtCoder ones beyond what the tier captures.

<details>
<summary>Superseded numbers from the pre-cleaning dataset</summary>

| Model | "MRR@10" | R@1 | R@5 |
|-------|--------|-----|-----|
| UniXcoder baseline (zero-shot) | 0.136 | 0.100 | 0.180 |
| UniXcoder + LoRA | 0.725 | 0.643 | 0.827 |
| UniXcoder + Full finetune | **0.770** | **0.693** | **0.880** |

Kept for anyone who cited them. They are not comparable to the table above:
different dataset, different test pool size, and the column labelled "MRR@10"
was the untruncated mean.
</details>

LoRA updates 0.23% of the parameters (295K of 126M).

Full results, including validation splits and the by-origin breakdown, are in
`outputs/results_baseline.json` and `outputs/results_lora.json`.

## Setup

```bash
pip install -r requirements.txt
```

No data placement needed — the pipeline reads `dataset/dataset.jsonl` through `dataset/common/load.py` and uses the `split` field frozen in it.

## Usage

```bash
# 1. Report the frozen train/val/test split (by tier and by origin)
python pipeline/prepare_data.py

# 2. Evaluate zero-shot baseline
python pipeline/baseline_eval.py

# 3. Finetune — choose one or both
python pipeline/finetune_st.py       # full-parameter finetune (~18h on CPU)
python pipeline/finetune_lora.py     # LoRA adapters (~3h on CPU)
```

Results are written to `outputs/results_*.json`. Trained models saved to `model_st/` and `model_lora/`.

## Method

**Loss:** Symmetric InfoNCE with temperature τ=0.07. For a batch of N pairs, the N×N cosine similarity matrix is computed and each pair is ranked against all in-batch negatives — in both C→Rust and Rust→C directions.

**Embedding:** Mean pooling over non-padding token hidden states, L2-normalized to unit vectors.

| | Full finetune | LoRA |
|--|---|---|
| Parameters updated | 126M (all) | 295K (0.23%) |
| Learning rate | 1e-5 | 2e-4 |
| LoRA rank | — | 8 |
| LoRA targets | — | query, value |
| Batch size | 8 | 8 |
| Epochs | 5 | 5 |
| Peak RAM | ~3.6 GB | ~3 GB |
