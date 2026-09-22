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

## Results (on the 1857-problem dataset)

| Category | SFR sim range | Count | Mean score |
|----------|---------------|-------|------------|
| Easy | ≥ 0.8687 | 465 (25.0%) | 0.8967 |
| Medium | 0.7856 – 0.8687 | 928 (50.0%) | 0.8292 |
| Hard | < 0.7856 | 464 (25.0%) | 0.7486 |

Distribution: mean=0.8260, std=0.0580, min=0.6214, max=0.9635.

---

## On reproducing the original labels

This script previously used `microsoft/unixcoder-base` while the shipped labels were SFR-based, so the published `difficulty` field could not be regenerated from the published code at all. That is fixed; the labels in `dataset.jsonl` are now the output of this script, and `difficulty_score` is stored alongside them so future verification is exact.

The original labels could **not** be reproduced exactly, and it is worth being precise about what that does and does not mean.

The aggregate statistics match closely. This run gives mean=0.8260, std=0.0580 and thresholds 0.8687 / 0.7856, against the 0.823 / 0.062 and 0.868 / 0.781 reported for the 1886-pair release. That level of agreement confirms the model and the general method were as documented.

Per-pair, 1653 of 1857 labels (89.0%) agree. The 204 that differ move as follows:

| Migration | Count |
|---|---|
| medium → easy | 57 |
| hard → medium | 51 |
| easy → medium | 49 |
| medium → hard | 46 |
| easy → hard | 1 |

Only one pair moves two tiers, so nothing moved far. But the migration is **bidirectional**, and that rules out the easy explanation. Dropping 29 pairs shifted the quantile cuts slightly; had the per-pair scores been identical, every reassignment would have been in a single direction, and only 62 pairs lie between the old and new thresholds at all. Observing 204 reassignments in both directions means the per-pair similarity scores themselves differ between the original run and this one.

The cause cannot be recovered, because the original run saved only the bins and not the scores — plausible candidates are a different pooling variant, truncation length, numeric precision, or `transformers` version. Practically, this means the tier labels are a *reproducible function of this script from now on*, but the 1886-pair release's labels are not exactly recoverable. This is recorded as a threat to validity in the paper.
