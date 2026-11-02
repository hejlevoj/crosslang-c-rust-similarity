# CRUSTPairs v1.0

1857 pairs of C and Rust implementations of the same competitive programming
problem, for cross-language code similarity research.

Both sides of a pair are submissions that were accepted by the originating
judge, so functional equivalence is **inherited from provenance, not verified
by execution** — no test cases are distributed, and the entry-point
normalisation means the code does not compile as a standalone program. Read
the limitations below before using this as ground truth.

---

## Contents

| Path | What it is |
|---|---|
| `dataset.jsonl` | The dataset. One JSON object per line, 5.9 MB. |
| `dataset/` | Construction and evaluation scripts, with their READMEs. |
| `results/` | The retrieval results reported in the paper. |
| `model_lora/` | The LoRA adapter trained on this dataset. |
| `DATA_LICENSES.md` | Per-source licensing, and what it permits. |
| `LICENSE`, `LICENSES/` | MIT for the code; the CDLA text the data requires. |
| `CITATION.cff`, `.zenodo.json` | Citation and deposit metadata. |

## Schema

One JSON object per line. All fields are strings except `difficulty_score`.

| Field | Values |
|---|---|
| `problem_id` | `0001`–`1886`, inherited from an earlier release, so not contiguous over 1857 records |
| `origin` | `codenet` (839), `xcodeeval` (1018) |
| `license` | SPDX expression; follows `origin` |
| `problem_description` | Upstream statement, verbatim |
| `problem_description_format` | `html` (839, AtCoder markup) or `text` (1018) |
| `c_code`, `rust_code` | Entry points renamed to `solution` |
| `difficulty` | `easy` (465), `medium` (928), `hard` (464) |
| `difficulty_score` | The raw cross-language similarity the tier was cut from |
| `split` | `train` (1485), `val` (185), `test` (187) |

Difficulty is the cosine similarity between zero-shot
`SFR-Embedding-Code-400M_R` embeddings of the two sides, binned at the 25th
and 75th percentiles. The raw score ships alongside the tier so the cuts can
be redrawn without re-running the model. The split is stratified by source ×
tier and frozen in the data rather than regenerated from a seed, so a
published number can be checked.

## Licensing — read this before redistributing

The dataset aggregates two corpora under different terms, so it has no single
licence and **every record carries its own**.

| `origin` | Pairs | Licence |
|---|---|---|
| `xcodeeval` | 1018 (54.8%) | CC BY-NC 4.0 |
| `codenet` | 839 (45.2%) | CDLA-Permissive-2.0 |

**The aggregate is non-commercial**, because the larger half is CC BY-NC 4.0,
and attribution to both upstream projects is required. A commercially usable
subset exists: filtering to `origin == "codenet"` gives 839 pairs under
CDLA-Permissive-2.0, whose only obligation is to pass on the licence text
included here. The accompanying code is MIT.

## Known limitations

- **Equivalence is not verified by execution.** No tests or expected I/O.
- **Upstream identifiers are absent.** A pair cannot be traced back to the
  originating problem or submission, which limits attribution to the corpus
  level.
- **This is competitive programming code** — short, single-file, I/O-driven,
  without the allocation patterns, aliasing and concurrency that make real C
  hard to port. Do not assume results transfer to systems code.
- **Difficulty is a proxy** for embedding similarity, not for algorithmic
  difficulty or translation effort.
- **Pre-training contamination is possible.** Both source archives are public.

## Reproducing

```bash
python dataset/scripts/smoke_test.py          # validates the artifact, seconds
python dataset/finetune/pipeline/lexical_baseline.py
python dataset/finetune/pipeline/baseline_eval.py
python dataset/finetune/pipeline/finetune_lora.py
```

`dataset/common/load.py` is the single entry point for reading the data; the
pipelines all go through it. `dataset/scripts/build_dataset_v1.py` rebuilds
the derived fields and the split from the dataset itself.

## Citing

See `CITATION.cff`. Please cite both this deposit and the paper describing it.
