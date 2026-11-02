#!/usr/bin/env bash
# Build the tarball to upload to arXiv.
#
#   ./paper/arxiv-package.sh
#
# arXiv compiles your source rather than taking the PDF, so the upload is
# .tex + .bib + .bbl. Three things about that are easy to get wrong:
#
#   - The .bbl must be included even though it is a build product. arXiv will
#     run BibTeX if the .bib is present, but shipping the .bbl removes the
#     dependency on arXiv's TeX Live matching ours, and its name has to match
#     the top-level .tex. Note that paper/.gitignore excludes *.bbl, so it does
#     not exist in a fresh clone - this script builds it first.
#   - Auxiliary files must NOT be included: .aux, .log, .out, and the .pdf
#     built from the source. arXiv rejects or mis-handles them. The .bbl is
#     the documented exception.
#   - IEEEtran.cls and IEEEtran.bst are in TeX Live, so arXiv supplies them;
#     they do not go in the tarball. If arXiv ever reports them missing, add
#     them rather than switching document class.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# The arXiv preprint is the EXTENDED version: it carries the material the
# 4-page MSR submission cannot, and arXiv imposes no page limit. Both versions
# \input body.tex, so that file has to travel with it.
TARGET=extended
OUT=arxiv-submission.tar.gz

echo "Building $TARGET so the .bbl is current ..."
bash build.sh "$TARGET" >/dev/null 2>&1 || true

[[ -s $TARGET.bbl ]] || {
  echo "$TARGET.bbl was not produced - fix the build before packaging." >&2
  exit 1
}

# Figures would need to be listed here too; the paper currently has none.
if grep -q "includegraphics" body.tex; then
  echo "WARNING: body.tex references figures. Add them to the tarball." >&2
fi

rm -f "$OUT"
tar -czf "$OUT" $TARGET.tex body.tex refs.bib $TARGET.bbl

echo
echo "Wrote $OUT:"
tar -tzf "$OUT" | sed 's/^/  /'
echo
echo "Upload this at https://arxiv.org/submit - choose 'tex' as the format."
echo "Primary category cs.SE, cross-list cs.LG, licence CC BY 4.0."
echo
echo "Note: $TARGET.tex is the top-level file. arXiv compiles from the"
echo "submission root, and body.tex is \input from there, so both are included."
