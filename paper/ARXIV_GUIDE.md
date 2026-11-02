# Posting CRUSTPairs on arXiv

Step by step, with the exact values for this paper. Checked against arXiv's
own help pages on 2026-11-02.

> **Status.** The package is built and current — `arxiv-submission.tar.gz`,
> regenerated after the two paper versions were reconciled. Two things are
> decided by you before you upload: **who submits** (an endorsement question,
> §1) and **which licence** (irrevocable, §2). Everything after that is form
> filling.

**Does this affect the MSR submission?** No. The Data and Tool Showcase track
is single-anonymous, so a preprint carrying your names breaks nothing, and
ACM's policy is explicit that "posting the paper on a web site [...] does not
disqualify it from appearing in an ACM publication." The arXiv cautions in
MSR's own call — don't name the venue, use a different preprint title — are on
the **Technical Papers** page and exist to protect *double*-anonymous review.
They do not apply to this track.

---

## 1. Who submits — settle this first

arXiv requires an endorsement before your first submission *in a category*,
and as of **21 January 2026** an institutional email is no longer enough on
its own. There are two paths:

| Path | Requires |
|---|---|
| Automatic | an institutional email **and** previous authorship on a paper already accepted in the same *endorsement domain* |
| Personal | an established arXiv author in that domain endorses you |

The endorsement domain here is **`cs`** — it covers `cs.SE` and `cs.LG`
together, so a paper in any `cs.*` category counts.

**This is already solved for your author list.** Alneu de Andrade Lopes has
two papers on arXiv, both in `cs`:

| | |
|---|---|
| [arXiv:2508.14330](https://arxiv.org/abs/2508.14330) | *Multi-view Graph Condensation via Tensor Decomposition*, `cs.LG`, submitted 2025-08-20 |
| [arXiv:1606.07950](https://arxiv.org/abs/1606.07950) | *Word sense disambiguation: a complex network approach*, `cs.CL`, 2016 |

So two routes are open, and both avoid asking a stranger:

**Lopes submits.** Fastest. He needs a USP email on the account and ownership
claimed on at least one of those papers.

**Lopes endorses Leonardo.** Also fine, and better if Leonardo should be the
submitting author. Note the window: to *endorse*, arXiv counts only papers
"submitted between three months and five years ago" — so the 2025 paper
qualifies and the **2016 one does not**. One qualifying paper is enough.

Either way the prerequisite is the same and takes minutes: **claim ownership**
of arXiv:2508.14330. Being listed as a co-author is not the same as being
registered as its author in arXiv's records, and endorsement keys off the
latter. Do that before starting the submission.

> If you start a submission without endorsement, arXiv emails you a link to
> hand to a prospective endorser. That path works, but it puts the timeline
> outside your control — which is the usual reason a planned preprint slips.

## 2. The licence — the one irrevocable choice

arXiv offers six: `CC BY 4.0`, `CC BY-SA 4.0`, `CC BY-NC-SA 4.0`,
`CC BY-NC-ND 4.0`, `arXiv.org perpetual, non-exclusive license 1.0`, and
`CC Zero`. The choice **cannot be changed** once made. A later *version* may
carry a different licence, but v1 keeps whatever you picked, forever.

**Recommendation: `arXiv.org perpetual, non-exclusive license 1.0`.**

This is a change from what `arxiv-package.sh` and `README.md` currently print,
and the reason is the publisher. MSR is an IEEE/ACM conference — MSR 2027
requires the IEEE template, and the MSR 2025 volume carried an IEEE copyright
notice. At camera-ready you will likely sign an IEEE copyright transfer, after
which IEEE's policy lets you keep an accepted version posted *with its
copyright notice and the DOI*. An irrevocable CC BY 4.0 on v1 grants the world
commercial reuse of that text, which you cannot walk back if the transfer
turns out to conflict.

To be fair to the alternative: IEEE does not state anywhere that CC licences
are prohibited, and plenty of CC BY preprints coexist with IEEE papers. The
asymmetry is what decides it — the arXiv licence still permits everything a
preprint needs (anyone may read, download and cite it), the downside if CC BY
conflicts is unfixable, and the downside of choosing the arXiv licence is
close to nothing.

**Do not confuse this with the dataset licence.** Three separate things:

| | Licence | Why |
|---|---|---|
| The paper text | your choice here | your own writing |
| The dataset | `CC BY-NC-4.0` | 1018 pairs derive from xCodeEval; see `DATA_LICENSES.md` |
| The code | MIT | |

The paper reproduces no dataset content — no listings, no figures — so no
CC BY-NC material travels inside the preprint.

## 3. Build the package

```bash
./paper/arxiv-package.sh
```

That writes `paper/arxiv-submission.tar.gz` containing exactly four files:

| File | Why it is there |
|---|---|
| `extended.tex` | the top-level file |
| `body.tex` | `\input` from it; arXiv compiles from the submission root |
| `refs.bib` | the bibliography source |
| `extended.bbl` | pre-generated, and its name must match the main `.tex` |

Three things the script already handles, worth knowing in case you ever build
by hand:

- **No auxiliary files.** `.aux`, `.log`, `.out` and the built `.pdf` must not
  be in the tarball. arXiv compiles your source; it does not take your PDF.
- **No `IEEEtran.cls` / `.bst`.** They are in TeX Live, which arXiv supplies.
- **No `\pdfoutput`.** arXiv says plainly: "You should not use `\pdfoutput` to
  change the output format." Neither driver file sets it.

## 4. Fill in the submission

Start at <https://arxiv.org/submit> and choose **tex** as the format.

| Field | Value |
|---|---|
| Primary category | `cs.SE` |
| Cross-list | `cs.LG` |
| Title | `CRUSTPairs: A Cross-Language Dataset of Paired C and Rust Solutions` |
| Authors | `Vojtěch Hejlek, Leonardo Jesus Almeida, Alneu de Andrade Lopes` |

**Authors** go in paper order, comma-separated, in arXiv's own field — it does
not read them from the LaTeX.

**Abstract**: paste the plain text below. The field takes no LaTeX, so the
`$...$` and `\%` of the source have to come out; this is the converted version.

```
C-to-Rust migration is an active agenda, but no dataset pairs the two
languages at the level of whole solutions to a shared problem. We present
CRUSTPairs, 1857 C/Rust implementation pairs drawn from competitive
programming archives, normalised, deduplicated, and stratified into difficulty
tiers by zero-shot cross-language embedding similarity, with per-record
provenance and licensing. Cross-language retrieval is hard on this data, and
harder than a single baseline would suggest: TF-IDF over shared identifiers
reaches MRR 0.21 and so beats a pretrained code model at 0.19, which on the
hardest quarter of the data scores 1.7x chance. Finetuning reaches 0.79, and
lifts that hardest quarter 10x. Renaming every user identifier settles what is
being learned: the finetuned models keep 96-97% of their accuracy without them,
while the pretrained model keeps 66% -- less than the lexical baseline does --
and on structurally divergent pairs the finetuned models are better without
identifiers than with them.
```

**Comments**: this is where the extended-version note and the dataset DOI go.

```
5 pages. Extended version with full per-tier and per-origin results,
training setup, and additional use cases. Dataset:
https://doi.org/10.5281/zenodo.23888785
```

Say nothing about MSR here. Not because this track forbids it — it does not —
but because a submission under review is not yet a venue, and "submitted to"
is exactly what arXiv asks you to keep out of the metadata fields. Add the
real citation after notification (§6).

## 5. Preview, then submit

Compile in the interface and **read the generated PDF**, not your local one.
arXiv's TeX Live is not yours, and the preview is the authoritative render.

Timing, if you care which day it appears (all times **Eastern US**):

| Submitted | Announced |
|---|---|
| Mon 14:00 – Tue 14:00 | Tue 20:00 |
| Tue 14:00 – Wed 14:00 | Wed 20:00 |
| Wed 14:00 – Thu 14:00 | Thu 20:00 |
| Thu 14:00 – Fri 14:00 | **Sun 20:00** |
| Fri 14:00 – Mon 14:00 | Mon 20:00 |

No announcements Friday or Saturday. Budget slack: arXiv's quality-assurance
checks "can take between one to four days to resolve, sometimes longer," and
the identifier is assigned at announcement, not at submission.

**When to post.** On or after the MSR submission date (10 Nov 2026), not
before. Nothing forbids earlier; there is simply no gain in exposing a version
that may still change.

## 6. After it is announced

arXiv mints its own DOI, of the form `10.48550/arXiv.NNNN.NNNNN`. You will then
have three, which are not interchangeable:

| DOI | What it identifies |
|---|---|
| `10.48550/arXiv.…` | the preprint text |
| `10.5281/zenodo.23888785` | the dataset, version 1.0.0 exactly |
| (after acceptance) | the MSR paper of record |

**At acceptance**, add the journal reference and the publisher DOI through the
journal-reference facility on your arXiv user page. This does **not** create a
new version: "no new article version will be generated when journal reference,
DOI or report number information is added." Give the journal reference as
venue, year and pages — not "accepted for…", which that field rejects by
convention; put that kind of note in Comments instead.

Then, if the IEEE transfer is signed, post the accepted version as **v2** with
the IEEE copyright notice and the DOI, per IEEE's posting policy. A new version
may carry a different licence from v1, which is the escape hatch if §2 ever
needs revisiting.

**On Zenodo**, add an `is supplemented by` related identifier pointing at the
arXiv DOI. Zenodo metadata stays editable forever, so this costs nothing —
see `zenodo/DEPOSIT_GUIDE.md` §8.

## What cannot be undone

| | |
|---|---|
| The licence on a version | permanent; only a *new version* can differ |
| Withdrawal | a paper can be marked withdrawn, but earlier versions stay visible |
| The identifier | reflects the month of first announcement |

Everything else — metadata, authors, abstract, categories — is editable.

## Checklist

- [ ] Ownership claimed on arXiv:2508.14330, so endorsement resolves (§1)
- [ ] Submitting author agreed between the three of you
- [ ] Licence decided — `arXiv.org perpetual, non-exclusive license 1.0` (§2)
- [ ] `./paper/arxiv-package.sh` rerun, so the tarball matches current source
- [ ] Abstract pasted as plain text, no `$`, `\%` or `\times` left
- [ ] Comments field carries the Zenodo DOI and the extended-version note
- [ ] arXiv's own compiled PDF read through, not the local one
- [ ] Posted on or after 2026-11-10
- [ ] After notification: journal reference, publisher DOI, Zenodo cross-link
