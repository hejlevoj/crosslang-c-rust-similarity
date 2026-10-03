# UniXcoder Finetuning — C↔Rust Cross-Language Code Similarity

Finetunes [`microsoft/unixcoder-base`](https://github.com/microsoft/CodeBERT/tree/master/UniXcoder) to embed C and Rust implementations of the same algorithm close together in vector space. Two methods compared: full-parameter finetuning and LoRA adapters.

## Results

Measured on the 187-pair test split of the 1857-pair dataset, on GPU at Labic.
Each C implementation queries the pool of all 187 Rust implementations. LoRA is
mean ± sd over four seeds.

| Model | MRR | MRR@10 | R@1 | R@5 | R@10 |
|-------|-----|--------|-----|-----|------|
| Chance | 0.031 | 0.016 | 0.005 | 0.027 | 0.053 |
| Lexical TF-IDF | 0.206 | 0.191 | 0.128 | 0.273 | 0.353 |
| UniXcoder, zero-shot | 0.189 | 0.170 | 0.134 | 0.203 | 0.283 |
| UniXcoder + LoRA | 0.724±0.011 | 0.720±0.011 | 0.624±0.015 | 0.836±0.011 | 0.913±0.012 |
| UniXcoder, full finetune | **0.792** | **0.791** | **0.706** | **0.909** | **0.952** |

**The lexical baseline beats zero-shot UniXcoder** (0.206 vs 0.189). So the
claim is not "a generic code model finds this hard" but the stronger "neither
generic code embeddings nor lexical matching solve this, and finetuning does"
— 3.8× for LoRA, 4.2× for full finetuning.

### By tier, with and without user identifiers

| Model | Ident. | Easy (47) | Medium (93) | Hard (47) | Retained |
|---|---|---|---|---|---|
| Lexical TF-IDF | kept | 0.446 | 0.144 | 0.089 | |
| | anon | 0.355 | 0.094 | 0.080 | 76% |
| UniXcoder, zero-shot | kept | 0.328 | 0.186 | 0.053 | |
| | anon | 0.276 | 0.084 | 0.048 | 66% |
| UniXcoder + LoRA | kept | 0.957 | 0.776 | 0.388 | |
| | anon | 0.941 | 0.688 | **0.429** | 96% |
| UniXcoder, full | kept | 0.979 | 0.821 | 0.550 | |
| | anon | 0.951 | 0.756 | **0.611** | 97% |

Three findings:

**Retrieval is monotone in tier everywhere.** The tiers were cut with SFR and
these models are UniXcoder-based, so the ordering is a property of the pairs,
not of the encoder that defined it. Zero-shot on the hard tier is 1.7× chance,
with exactly one of 47 pairs at rank 1.

**Finetuning learns structure, not names.** The finetuned models keep 96–97%
of their MRR without identifiers; zero-shot UniXcoder keeps 66%, *less* than
the lexical baseline's 76%. A pretrained code model is more name-dependent
than TF-IDF — it is doing a worse version of the same thing.

**On hard pairs identifiers hurt.** Both finetuned models improve without them
(+11% relative), while lexical and zero-shot get worse. Where implementations
diverge structurally, a shared name is more often coincidence than signal.

### Other observations

Querying with Rust is easier than with C (zero-shot 0.233 vs 0.189; full 0.836
vs 0.792). Under the ablation the asymmetry nearly vanishes for the finetuned
models (0.773 vs 0.768), so it comes from identifiers rather than structure.

LoRA reaches 91% of full finetuning overall with 0.23% of the parameters — but
98% on easy pairs, 95% on medium and only **71% on hard**. The parameter budget
binds where the remapping is hard.

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

Full results, including validation splits and the by-origin breakdown, are in
`outputs/results_baseline.json`, `outputs/results_lora.json` and
`outputs/results_st.json`.

On overfitting to the validation split: checkpoints are selected on val MRR, so
the val/test difference is worth a look. Zero-shot, which involves no selection
at all, differs by −0.030 (test is the easier split), which sets a noise floor.
LoRA drops 0.047 and full finetuning 0.015 — both close enough to that floor
that checkpoint selection is not meaningfully inflating the reported numbers.

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
