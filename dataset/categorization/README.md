# Dataset Difficulty Categorization with SFR-Embedding-Code

Categorizes C↔Rust problem pairs into difficulty tiers (easy / medium / hard) based on how similar the zero-shot `SFR-Embedding-Code-400M_R` embeddings of the C and Rust implementations already are — without any finetuning.

## Idea

Pairs where the model already assigns high cosine similarity are **easy** — the implementations are structurally close enough for a generic code model to find them similar (near-literal translations). Pairs with low similarity are **hard** — the implementations diverge structurally and require the model to learn a more significant cross-language remapping.

SFR is used rather than UniXcoder on purpose. Using the same model family to both define the difficulty tiers and measure finetuning improvement would make "hard" pairs hard *by construction* for UniXcoder. SFR is independently trained on a different corpus, so the tiers stay meaningful as an evaluation axis.

Thresholds are quantile-based (25/50/25 split) so bins are always balanced regardless of the distribution shape.

| Category | Threshold | Share |
|----------|-----------|-------|
| Easy | sim ≥ p75 | 25% |
| Medium | p25 ≤ sim < p75 | 50% |
| Hard | sim < p25 | 25% |

This categorization is origin-agnostic — it avoids comparing difficulty ratings across sources (AtCoder vs Codeforces ratings are incompatible scales).

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python categorize.py
```

Reads `dataset/dataset.jsonl` through `dataset/common/load.py` — no separate input file to place.

To confirm the script regenerates the `difficulty` labels shipped in the dataset:

```bash
python categorize.py --verify
```

This fails loudly on any disagreement. **Run it before submitting anywhere** — the labels in the release have not yet been verified against this script (see `PUBLICATION_PLAN.md`, B2).

Output:
- `outputs/similarity_scores.json` — per-problem cosine similarity and assigned category
- `outputs/categories.json` — `{problem_id: "easy"|"medium"|"hard"}` mapping

## Results (on the 1886-problem dataset)

| Category | SFR sim range | Count |
|----------|---------------|-------|
| Easy | ≥ 0.868 | 472 (25%) |
| Medium | 0.781 – 0.868 | 943 (50%) |
| Hard | < 0.781 | 471 (25%) |

Distribution: mean=0.823, std=0.062.

> **Note.** An earlier version of this script used `microsoft/unixcoder-base` and reported a different distribution (mean=0.730, std=0.092; bins 472/942/472). Those labels were replaced by the SFR ones in commit `60c0ab1`, but this script was not updated at the same time — so the published `difficulty` field was, until now, not reproducible from the published code. The `--verify` flag exists to close that gap.
