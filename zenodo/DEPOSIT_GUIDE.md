# Depositing CRUSTPairs on Zenodo

> **Status.** The record is **published** (2026-11-02). The version DOI
> `10.5281/zenodo.23888785` resolves, and the concept DOI
> `10.5281/zenodo.23888784` always points at the newest version. All six steps
> below are done — but see the correction note immediately after.

> **One correction still needed.** The record was published under
> **CC BY 4.0**. It should be **CC BY-NC 4.0**: 1018 of the 1857 pairs derive
> from xCodeEval, whose own README licenses it CC BY-NC 4.0, so the aggregate
> cannot grant commercial use. As published, the record promises a permission
> the upstream data does not give, and it contradicts the paper,
> `DATA_LICENSES.md`, `CITATION.cff`, the per-record `license` field and the
> README inside the archive — all of which say non-commercial.
>
> Zenodo metadata is editable at any time and a licence change needs no new
> version: open the record, **Edit**, change the licence to *Creative Commons
> Attribution-NonCommercial 4.0 International*, **Publish** again. The DOI and
> the files are untouched. Section 4 below explains why this licence is not a
> free choice.
>
> The likely cause is worth knowing: the xCodeEval **Hugging Face mirror** is
> tagged `cc-by-4.0`, contradicting the project's own README. The README is the
> authors' declaration and the more restrictive reading, so it governs.

Step by step, with the exact values for this deposit. Checked against
Zenodo's documentation on 2026-11-02.

The point of depositing now rather than later: MSR's Data and Tool Showcase
requires the artifact to be archived with a DOI, and **the DOI must appear in
the camera-ready**. Zenodo lets you *reserve* a DOI while the upload is still
a draft, so you can cite it in the paper before the record goes public.

---

## Before you start

**Build the package.**

```bash
./zenodo/make_package.sh
```

That writes `zenodo/crustpairs-v1.0.zip` — 2.5 MB, 55 files. Well inside
Zenodo's limit of 100 files and 50 GB.

**Decide who owns the record.** The Zenodo account that publishes becomes the
owner. For a three-author paper spanning two institutions, that is worth
agreeing on first — ownership can be transferred later, but it is friction.

**Optional dry run.** `sandbox.zenodo.org` is a complete copy of Zenodo with
throwaway DOIs. If you have never published a record, do it there once. It
costs ten minutes and removes the fear of clicking the wrong thing on the real
one.

---

## 1. Create the upload

Log in at [zenodo.org](https://zenodo.org), click the **+** in the header,
choose **New upload**.

Drag `crustpairs-v1.0.zip` into the drop zone. Leave file visibility
**public**; there is no reason to embargo this.

## 2. Reserve the DOI

In the **Digital Object Identifier (DOI)** section, answer **No** to "Do you
already have a DOI?", then click **Get a DOI now!**

The reserved DOI appears immediately and is what you put in the paper. It is
only *registered* when you publish — until then it resolves to nothing, which
is fine for a camera-ready deadline that falls after publication.

> **Do not delete the draft.** Deleting it releases the reserved DOI. If you
> remove the reservation but keep the draft, clicking the button again returns
> the same DOI.

## 3. Fill in the metadata

Everything below is also in `.zenodo.json` inside the archive. Zenodo reads
that file automatically **only** for its GitHub-release integration — for a
manual upload you type the fields yourself.

| Field | Value |
|---|---|
| Resource type | **Dataset** |
| Title | `CRUSTPairs: A Cross-Language Dataset of Paired C and Rust Solutions` |
| Publication date | the day you publish |
| Version | `1.0.0` |
| Language | English |

**Creators**, in this order — it is the order on the paper:

| Name | Affiliation |
|---|---|
| Hejlek, Vojtěch | Faculty of Information Technology in Prague |
| Almeida, Leonardo Jesus | University of São Paulo |
| Lopes, Alneu de Andrade | University of São Paulo |

Add each author's **ORCID**. Zenodo links the record to their profile, and it
is the cheapest way to make the deposit findable under their names.

**Description**: paste the `description` field from `.zenodo.json`. It is
already written as HTML, which is what the field expects.

**Keywords**: cross-language code similarity, code retrieval, C, Rust,
program translation, memory safety, competitive programming, dataset.

## 4. Licence — this one is not a free choice

Select **Creative Commons Attribution-NonCommercial 4.0 International**
(`CC-BY-NC-4.0`).

Zenodo takes one licence for the whole deposit, and this is the only one the
data permits: 1018 of the 1857 pairs derive from xCodeEval under CC BY-NC 4.0,
so the aggregate cannot be released under anything more permissive. Choosing
CC BY, or MIT because the code is MIT, would misrepresent what a user is
allowed to do with it.

The per-record terms, and the 839-pair CodeNet subset that *is* commercially
usable, are documented in `DATA_LICENSES.md` inside the archive and summarised
in its `README.md`.

## 5. Related identifiers

Add these under **Related works**:

These are on the record, and all three were checked on 2026-11-02:

| Relation | Identifier | Resolves to |
|---|---|---|
| is supplement to | `https://github.com/hejlevoj/crosslang-c-rust-similarity` | the repository |
| is derived from | `10.5281/zenodo.4814770` | *IBM/Project_CodeNet: Initial release 1.0*, Zenodo, 2021 |
| is derived from | `10.18653/v1/2024.acl-long.367` | *XCodeEval: …*, ACL 2024, pp. 6766–6805 |

They are deliberately absent from `.zenodo.json`, which was written before
either was verified; the live record is the authoritative copy.

Once the paper has a DOI, come back and add **is supplemented by** pointing at
it. Metadata stays editable forever, so this costs nothing later.

## 6. Publish

Save the draft, use **Preview** to read the landing page as a stranger would,
then **Publish**.

### What you can still change afterwards

| | |
|---|---|
| Metadata | editable **at any time** |
| Files | editable by you for **45 days** after publishing |
| After 45 days | files are fixed; corrections go through a **New version** |

A new version gets its own DOI and joins the same *concept DOI*, which always
resolves to the newest version. So cite the **version DOI** in the paper when
you want the exact files you measured, and the concept DOI when you want
whatever is current.

Deletion after publishing is possible but goes through Zenodo support with a
justification, and leaves a tombstone page so citations do not break. Treat
publishing as close to final: check the licence and the author list before
clicking.

---

## 7. Put the DOI in the paper

Section VII of `paper/main.tex` currently reads:

> The dataset will additionally be deposited in a persistent archive with a
> DOI, cited here, for the camera-ready version.

That has been done — it now cites `10.5281/zenodo.23888785` alongside the
repository. `CITATION.cff` and `.zenodo.json` carry the DOI too, and
`date-released` is the publication date.

The paper cites the **version** DOI, which is the right choice: it resolves to
the exact files the reported numbers were measured on. Use the concept DOI
`10.5281/zenodo.23888784` only where you mean "whatever is current".

---

## 8. Once the paper has a DOI

Come back and add a **is supplemented by** related identifier pointing at it.
Metadata stays editable, so this costs nothing later — and it makes the deposit
and the paper discoverable from each other.
