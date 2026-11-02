# Paper — MSR 2027 Data and Tool Showcase

Target: **4 pages + 1 page of references**, IEEEtran `[10pt,conference]`, no
`compsoc`. Single-anonymous, so author names stay on the manuscript.

| Milestone | Date (AoE) |
|---|---|
| Abstract | 2026-11-05 |
| Paper | 2026-11-10 |
| Notification | 2027-01-05 |
| Camera-ready | 2027-01-24 |

Submission: https://msr2027-data-tool.hotcrp.com/

## Build

```bash
./paper/build.sh            # main.pdf, the 4-page MSR submission
./paper/build.sh extended   # extended.pdf, the arXiv preprint
./paper/build.sh --clean
```

Two outputs, one source. `main.tex` and `extended.tex` are thin drivers that
set `\ifextended` and then `\input body.tex`; everything they share is defined
once, so the versions cannot drift apart. Extended-only material sits in
`\ifextended ... \fi` blocks inside `body.tex`.

The two versions did diverge once — `main.tex` was edited standalone while the
paper was being resubmitted to the right track — and were reconciled on
2026-11-02. The rebuilt four-page PDF is textually identical to the submitted
one apart from one semicolon (noted below), and the editorial changes made in
that window now reach both versions.

Where the versions differ *within a sentence*, two macros defined in `body.tex`
carry it, so the difference is visible where it happens instead of hiding in a
second copy of the paragraph:

| Macro | Extended | Four-page |
|---|---|---|
| `\runin{...}` | bold run-in heading | the same text, unbolded |
| `\variant{a}{b}` | `a` | `b` |

Everything they guard is a concession to the page limit. **If a claim differs
between the versions, that is a bug** — the numbers, the author list and the
availability statement are defined once and shared.

One deliberate difference from the submitted PDF: it read "over four seeds
(σ = 0.011 on MRR), the others are single runs", a comma splice; the shared
body keeps the semicolon it originally had. Change it in `body.tex` if you
would rather match the submitted file byte for byte.

The extended version carries what does not fit in four pages: the positioning
table, the size and composition statistics, training hyper-parameters, the
full per-tier metrics and the per-source breakdown, two further use cases, and
the reproducibility analysis of the earlier tier labels in detail.

## Before submitting

- [x] No `\pending{}` left — `grep -n 'pending{' body.tex`
- [x] Every `TODO` resolved — `grep -n TODO body.tex refs.bib`
- [x] Every entry checked against dblp (2026-10-21); no `% VERIFY` left
- [ ] Re-check whether Syzygy LLM4Code 2025 proceedings have appeared
- [ ] Dataset name settled and consistent with the repository and Zenodo
- [ ] Author list, order and affiliations confirmed
- [x] Zenodo DOI cited in the availability section: `10.5281/zenodo.23888785`
- [x] **Publish the Zenodo record** — published 2026-11-02; the DOI resolves,
      concept DOI `10.5281/zenodo.23888784`
- [x] Licence on the Zenodo record is `CC-BY-NC-4.0`, matching the paper and
      `DATA_LICENSES.md` (it went up as `CC-BY-4.0`; corrected 2026-11-02 by a
      metadata edit, so the DOI and the archive's md5 are unchanged)
- [x] Body within 4 pages, bibliography starting on page 4 or earlier
      (`build.sh` reports this; a 5-page PDF is fine, body text on page 5 is not)
- [ ] Numbers match the regenerated `outputs/*.json`, not the stale READMEs


## Posting to arXiv

MSR's Data and Tool Showcase is single-anonymous, so a preprint before
submission is allowed and does not break anonymity. Post it on or after the
MSR submission date rather than before — there is no benefit to posting early
and it exposes a version that may still change.

```bash
./paper/arxiv-package.sh      # builds arxiv-submission.tar.gz (extended)
```

The tarball carries `extended.tex`, `body.tex`, `refs.bib` and
`extended.bbl`. `extended.tex` is the top-level file; `body.tex` has to travel
with it because arXiv compiles from the submission root.

Upload that at https://arxiv.org/submit, choosing **tex** as the format.
Primary category `cs.SE`, cross-list `cs.LG`.

**See [`ARXIV_GUIDE.md`](ARXIV_GUIDE.md)** for the field-by-field walkthrough,
with the abstract already converted to plain text. Two decisions in it are
yours and are worth making before you open the form:

**Who submits.** Since 21 January 2026 an institutional email alone no longer
earns endorsement. Alneu de Andrade Lopes already has papers in the `cs`
endorsement domain, so he can either submit or endorse — which avoids waiting
on a stranger. The prerequisite is claiming ownership of
[arXiv:2508.14330](https://arxiv.org/abs/2508.14330); see the guide.

**The licence, which is irrevocable per version.** The guide recommends the
`arXiv.org perpetual, non-exclusive license 1.0` rather than CC BY 4.0,
because MSR proceedings carry an IEEE copyright notice and a CC BY grant on v1
cannot be withdrawn. Either way it covers the paper text only — the dataset
keeps its own per-record terms (`DATA_LICENSES.md`).

**Style files.** `IEEEtran.cls` and `IEEEtran.bst` are in TeX Live, so arXiv
provides them and they stay out of the tarball.

## Open dependencies on Phase 1

Two tables cannot be finalised yet, both marked `\pending`:

- **Table III (composition).** Tier counts are being regenerated by
  `dataset/categorization/categorize.py --write-labels` over the 1857-pair
  population; the current values are quantiles of the older 1886-pair one.
- **Table IV (baselines).** All retrieval numbers need re-running against the
  current stratified split. The figures in `dataset/finetune/README.md` were
  computed on a different input and are not usable — see `PUBLICATION_PLAN.md`
  (B6).

## Figures still to draw

1. Construction pipeline with counts at each stage (2013 → 1886 → 1857).
2. Histogram of SFR similarity with the tier cut lines.
3. A side-by-side C/Rust "hard" pair showing structural divergence. This is the
   figure that sells the dataset — pick the example deliberately.
