# Licensing of the C↔Rust dataset

The dataset is an **aggregate of three upstream corpora that are not under the
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
| `xcodeeval` | 1018 (54.0%) | [xCodeEval](https://github.com/ntunlp/xCodeEval) (Codeforces) | **CC BY-NC 4.0** |
| `codenet` | 839 (44.5%) | [IBM Project CodeNet](https://github.com/IBM/Project_CodeNet) (AtCoder) | **CDLA-Permissive-2.0** |
| `common-algorithms` | 29 (1.5%) | [TheAlgorithms/C](https://github.com/TheAlgorithms/C) and [TheAlgorithms/Rust](https://github.com/TheAlgorithms/Rust) | **GPL-3.0** (C side) and **MIT** (Rust side) |

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

**common-algorithms.** These 29 pairs were taken from the TheAlgorithms
project, whose per-language repositories do not share a licence: the C
repository is GPL-3.0, the Rust repository is MIT. So the C and the Rust half of
each of these 29 records are under different terms.

---

## What this means for the dataset as a whole

**The aggregate is non-commercial.** 54% of the records are CC BY-NC 4.0, so
the dataset as distributed cannot be used commercially, and cannot be
relicensed under CC BY 4.0, MIT, Apache-2.0 or CDLA. Attribution to the three
upstream projects is required.

**GPL-3.0 and CC BY-NC 4.0 cannot be merged into one work.** GPL-3.0 requires
that recipients be free to redistribute, including commercially; CC BY-NC
forbids exactly that. The two sets of files therefore travel together as a
*collection* — what the GPL calls mere aggregation — and not as a combined
work. Each record keeps its own terms; none is imposed on the others.

**A commercially usable subset exists.** Filtering to `origin == "codenet"`
gives 839 pairs under CDLA-Permissive-2.0 with no commercial restriction:

```python
from common.load import load
rows = load(origin="codenet")   # 839 pairs, CDLA-Permissive-2.0
```

---

## Recommendation: consider dropping `common-algorithms`

The 29 `common-algorithms` pairs are worth 1.5% of the dataset and carry most
of its licensing complexity — they are the only GPL-3.0 content, and the only
records whose two halves are under different licences.

They are also the odd ones out on the merits. They have no problem statement
(the `problem_description` is a bare title such as `"Bead sort"`), and their
functions take arguments (`fn solution(a: &mut [usize])`) rather than reading
stdin like every competitive-programming pair, so they are structurally
unlike the other 1857.

Dropping them would leave a clean two-licence aggregate — CC BY-NC 4.0 plus
CDLA-Permissive-2.0 — with no copyleft and no split-licence records, at
negligible cost to size or diversity. This has not been done: it is a call for
the dataset's authors to make.

---

## Missing attribution detail

CC BY-NC 4.0 requires attribution to the creator. Because the upstream problem
identifiers and URLs were not preserved when this dataset was built (see
`PUBLICATION_PLAN.md`, B5), attribution can currently be given only at the
level of the source corpus, not the individual problem or submission. Recovering
per-problem provenance would let the dataset attribute properly, and is the
strongest practical argument for doing that work.
