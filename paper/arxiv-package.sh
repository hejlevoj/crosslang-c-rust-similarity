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
#     the main .tex. Note that paper/.gitignore excludes *.bbl, so it does not
#     exist in a fresh clone - this script builds it first.
#   - Auxiliary files must NOT be included: .aux, .log, .out, and the .pdf
#     built from the source. arXiv rejects or mis-handles them. The .bbl is
#     the documented exception.
#   - IEEEtran.cls and IEEEtran.bst are in TeX Live, so arXiv supplies them;
#     they do not go in the tarball. If arXiv ever reports them missing, add
#     them rather than switching document class.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

OUT=arxiv-submission.tar.gz

echo "Building so the .bbl is current ..."
bash build.sh >/dev/null 2>&1 || true

[[ -s main.bbl ]] || {
  echo "main.bbl was not produced - fix the build before packaging." >&2
  exit 1
}

# Figures would need to be listed here too; the paper currently has none.
if grep -q "includegraphics" main.tex; then
  echo "WARNING: main.tex references figures. Add them to the tarball." >&2
fi

rm -f "$OUT"
tar -czf "$OUT" main.tex refs.bib main.bbl

echo
echo "Wrote $OUT:"
tar -tzf "$OUT" | sed 's/^/  /'
echo
echo "Upload this at https://arxiv.org/submit - choose 'tex' as the format."
echo "Primary category cs.SE, cross-list cs.LG."
