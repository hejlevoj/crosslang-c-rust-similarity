# UniXcoder Finetuning — C↔Rust Cross-Language Code Similarity

Finetunes [`microsoft/unixcoder-base`](https://github.com/microsoft/CodeBERT/tree/master/UniXcoder) to embed C and Rust implementations of the same algorithm close together in vector space. Two methods compared: full-parameter finetuning and LoRA adapters.

## Results

| Model | MRR@10 | R@1 | R@5 |
|-------|--------|-----|-----|
| UniXcoder baseline (zero-shot) | 0.136 | 0.100 | 0.180 |
| UniXcoder + LoRA | 0.725 | 0.643 | 0.827 |
| UniXcoder + Full finetune | **0.770** | **0.693** | **0.880** |

5× improvement over zero-shot. LoRA achieves 94% of full finetune performance with 0.23% of parameters updated.

> **These numbers are stale and need to be regenerated before publication.** They were reported against a 300-pair test set. The old seed-42 split applied to the 1886-pair dataset yields only 185 test pairs, so they were produced from a different input — most likely the 2013-pair pre-cleaning dataset, which is large enough for the 1500/200/300 split. The dataset now ships a stratified 1508/187/**191** split instead. Since MRR@10 and R@k depend on the size of the candidate pool, none of the numbers above is comparable to a result computed on this release. See `PUBLICATION_PLAN.md` (B6).
>
> When re-running, report the metrics **broken down by difficulty tier** as well as overall — the split is stratified precisely so that breakdown is valid.

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
