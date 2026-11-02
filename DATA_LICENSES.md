# Licensing of the C↔Rust dataset

The dataset is an **aggregate of two upstream corpora that are not under the
same licence**, so it is not distributed under a single one. Every record in
`dataset/dataset.jsonl` carries a `license` field with the SPDX expression that
governs it.

This file records where each of those terms comes from. It is documentation,
not legal advice — if you intend to use this data commercially, read the
upstream licences yourself.

---

## Per-source terms

| `origin` | Pairs | Upstream | Data licence |
|---|---|---|---|
| `xcodeeval` | 1018 (54.8%) | [xCodeEval](https://github.com/ntunlp/xCodeEval) (Codeforces) | **CC BY-NC 4.0** |
| `codenet` | 839 (45.2%) | [IBM Project CodeNet](https://github.com/IBM/Project_CodeNet) (AtCoder) | **CDLA-Permissive-2.0** |

Notes on each:

**xCodeEval.** The project's README separates the two: the repository code is
MIT, but the data is distributed under CC BY-NC 4.0. The Hugging Face mirror is
tagged `cc-by-4.0`, which contradicts the README; this file follows the
authors' own statement in the repository, which is the more restrictive and the
more authoritative of the two. If you need the permissive reading, get it in
writing from the xCodeEval authors — do not rely on the HF tag.

**CodeNet.** CDLA-Permissive-2.0 imposes essentially one obligation on a
redistributor: §2.1 requires that you make the text of the agreement available
with the shared data. It places no restriction on commercial use and none on
the licence of derived results (§3.1). `LICENSES/CDLA-Permissive-2.0.txt` is
included for that reason.

**common-algorithms (removed).** The 1886-pair release also held 29 pairs
taken from the TheAlgorithms project, whose per-language repositories do not
share a licence: [TheAlgorithms/C](https://github.com/TheAlgorithms/C) is
GPL-3.0 and [TheAlgorithms/Rust](https://github.com/TheAlgorithms/Rust) is MIT,
so the two halves of each of those records were under different terms. They
have been dropped - see the end of this file.

---

## What this means for the dataset as a whole

**The aggregate is non-commercial.** 54.8% of the records are CC BY-NC 4.0, so
the dataset as distributed cannot be used commercially, and cannot be
relicensed under CC BY 4.0, MIT, Apache-2.0 or CDLA. Attribution to both
upstream projects is required.

**There is no copyleft content.** Dropping `common-algorithms` removed the only
GPL-3.0 files. That matters because GPL-3.0 and CC BY-NC 4.0 cannot be merged
into a single work — the GPL requires that recipients be free to redistribute,
including commercially, and CC BY-NC forbids exactly that. While those files
were present, they and the CC BY-NC ones could only travel together as a
*collection*, what the GPL calls mere aggregation. That constraint is gone.

**A commercially usable subset exists.** Filtering to `origin == "codenet"`
gives 839 pairs under CDLA-Permissive-2.0 with no commercial restriction:

```python
from common.load import load
rows = load(origin="codenet")   # 839 pairs, CDLA-Permissive-2.0
```

---

## Why `common-algorithms` was dropped

The 1886-pair release held 29 pairs from the TheAlgorithms project. They were
worth 1.5% of the dataset and carried most of its licensing complexity: the
only GPL-3.0 content, and the only records whose two halves were under
different licences.

They were also the odd ones out on the merits. They had no problem statement
(the `problem_description` was a bare title such as `"Bead sort"`), and their
functions take arguments (`fn solution(a: &mut [usize])`) rather than reading
stdin like every competitive-programming pair, so they were structurally
unlike the other 1857.

Dropping them leaves a clean two-licence aggregate — CC BY-NC 4.0 plus
CDLA-Permissive-2.0 — with no copyleft and no split-licence records, at
negligible cost to size or diversity. The exclusion is implemented as
`DROPPED_ORIGINS` in `dataset/scripts/build_dataset_v1.py`, so it is documented
and reversible rather than a one-off deletion.

---

## Missing attribution detail

CC BY-NC 4.0 requires attribution to the creator. Because the upstream problem
identifiers and URLs were not preserved when this dataset was built (see
`PUBLICATION_PLAN.md`, B5), attribution can currently be given only at the
level of the source corpus, not the individual problem or submission. Recovering
per-problem provenance would let the dataset attribute properly, and is the
strongest practical argument for doing that work.
