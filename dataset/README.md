# C↔Rust Dataset

1886 competitive programming problems each implemented in C and Rust, cleaned and categorized for cross-language code similarity research.

---

## Schema (v1.0)

Each entry in `dataset.jsonl` is a JSON object with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `problem_id` | string | Zero-padded sequential ID (`0001`–`1886`) |
| `origin` | string | `"codenet"` / `"xcodeeval"` / `"common-algorithms"` |
| `license` | string | SPDX expression governing this record — see [`DATA_LICENSES.md`](../DATA_LICENSES.md) |
| `problem_description` | string | Full problem statement, verbatim from the source |
| `problem_description_format` | string | `"html"` (AtCoder markup) / `"text"` |
| `c_code` | string | C implementation, entry point normalized to `solution()` |
| `rust_code` | string | Rust implementation, entry point normalized to `fn solution()` |
| `difficulty` | string | `"easy"` / `"medium"` / `"hard"` |
| `split` | string | `"train"` / `"val"` / `"test"` |

Read it through the shared loader rather than parsing it directly:

```python
from common.load import load, load_pairs

rows = load(split="test")                       # 191 pairs
rows = load(origin="codenet", difficulty="hard")
c, rust, pids = load_pairs(split="train")
```

Validate a clone with `python scripts/smoke_test.py` (seconds, no downloads).

---

## Difficulty Categorization

Difficulty is assigned based on the cosine similarity between the zero-shot `SFR-Embedding-Code-400M_R` embeddings of the C and Rust implementations — without any finetuning. SFR is used rather than UniXcoder to avoid a methodological dependency: using the same model family to both define difficulty tiers and measure finetuning improvement would make "hard" pairs hard by definition for UniXcoder. SFR is independently trained on a different corpus.

Thresholds are quantile-based over the full 1886-pair distribution (SFR sim: mean=0.823, std=0.062):

| Category | SFR similarity range | Count |
|----------|---------------------|-------|
| Easy | ≥ 0.868 | 472 (25%) |
| Medium | 0.781 – 0.868 | 943 (50%) |
| Hard | < 0.781 | 471 (25%) |

This categorization is origin-agnostic — it avoids comparing difficulty ratings across sources since AtCoder and Codeforces use incompatible rating scales.

---

## Sources

| Source | Problems | Style |
|--------|----------|-------|
| XcodeEval (Codeforces) | 1018 | Competitive, systems-heavy |
| CodeNet (AtCoder) | 839 | Competitive, algorithmic |
| common-algorithms | 29 | Textbook reference implementations |

The `origin` field was recovered from the released data by `scripts/build_dataset_v1.py` and reproduces this breakdown exactly. The upstream problem IDs and URLs were not preserved when the release was produced and are **not** currently recoverable — see `PUBLICATION_PLAN.md` (B5).

---

## Splits

The train/val/test assignment is frozen in the `split` field. It is **stratified by (origin × difficulty)** at 80/10/10, so the test set mirrors the dataset on both axes — a retrieval score broken down by tier is otherwise not comparable. Every pair is assigned; none is dropped.

| Split | Pairs |
|-------|-------|
| train | 1508 |
| val | 187 |
| test | 191 |

Max drift between the test set and the full dataset: 0.6pp by origin, 0.7pp by difficulty.

This replaces an earlier scheme that drew a flat random split at run time after dropping pairs over a length threshold. That threshold excluded exactly one pair (problem `0257`, 16460 chars of C; the next longest is 4649) while the Rust threshold excluded none — and since the models truncate at 512 tokens, it bought nothing while making the split sizes depend on the input file.

`python finetune/pipeline/prepare_data.py` reports the split, including its breakdown by difficulty tier and by origin.

---

## Cleaning Applied

127 entries were removed from the original 2013-entry dataset:

| Reason | Removed |
|--------|---------|
| Confirmed mis-pairs | 2 |
| AtCoder easy/hard near-duplicates (description sim > 0.90) | 69 |
| Suspicious similar pairs (0.80–0.90) | 54 |
| Length ratio outlier (190× C/Rust ratio) | 1 |
| Implementation divergence (structurally different algorithms) | 1 |

All entry-point function names are normalized to `solution` in both C and Rust. One consequence: the distributed code is **not** a standalone compilable program, since `main` was renamed.

---

## Licensing

The dataset aggregates three corpora under three different licences, so it has no single one. Each record carries a `license` field.

| `origin` | Pairs | Licence |
|---|---|---|
| `xcodeeval` | 1018 | CC BY-NC 4.0 |
| `codenet` | 839 | CDLA-Permissive-2.0 |
| `common-algorithms` | 29 | GPL-3.0 (C side) and MIT (Rust side) |

**The aggregate is non-commercial**, because 54% of it is CC BY-NC 4.0. A commercially usable subset exists: `load(origin="codenet")` gives 839 pairs under CDLA-Permissive-2.0. Read [`DATA_LICENSES.md`](../DATA_LICENSES.md) before redistributing.

---

## Known limitations

- **Functional equivalence is not verified by execution.** No test cases or expected I/O are distributed. Equivalence is inherited from provenance (both submissions were accepted upstream), not checked.
- **Upstream identifiers are missing.** A pair cannot be traced back to the originating problem.
- **Baseline numbers predate this release.** See the note in `finetune/README.md`.

---

## Related Directories

| Directory | Description |
|-----------|-------------|
| `finetune/` | Finetunes `unixcoder-base` on this dataset, full-parameter and via LoRA. |
| `categorization/` | Computes per-pair SFR zero-shot similarity and assigns the difficulty tiers. `--verify` checks it against the shipped labels. |
| `description-similarity/` | Embeds problem descriptions with OpenAI `text-embedding-3-large` and detects near-duplicate and suspicious problem pairs. |
| `scripts/` | Dataset construction (`build_dataset_v1.py`) and artifact validation (`smoke_test.py`). |
