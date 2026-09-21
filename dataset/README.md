# C↔Rust Dataset

1886 competitive programming problems each implemented in C and Rust, cleaned and categorized for cross-language code similarity research.

---

## Schema (v1.0)

Each entry in `dataset.jsonl` is a JSON object with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `problem_id` | string | Zero-padded sequential ID (`0001`–`1886`) |
| `origin` | string | `"codenet"` / `"xcodeeval"` / `"common-algorithms"` |
| `problem_description` | string | Full problem statement, verbatim from the source |
| `problem_description_format` | string | `"html"` (AtCoder markup) / `"text"` |
| `c_code` | string | C implementation, entry point normalized to `solution()` |
| `rust_code` | string | Rust implementation, entry point normalized to `fn solution()` |
| `difficulty` | string | `"easy"` / `"medium"` / `"hard"` |
| `split` | string | `"train"` / `"val"` / `"test"` / `"excluded"` |

Read it through the shared loader rather than parsing it directly:

```python
from common.load import load, load_pairs

rows = load(split="test")                       # 185 pairs
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

The train/val/test assignment is frozen in the `split` field. It reproduces the seed-42 split the finetuning pipeline used to generate at run time, including its length filter (`len(c_code) ≤ 10000 and len(rust_code) ≤ 5000`), which excludes 1 pair.

| Split | Pairs |
|-------|-------|
| train | 1500 |
| val | 200 |
| test | 185 |
| excluded (length filter) | 1 |

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
