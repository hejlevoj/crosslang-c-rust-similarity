#!/usr/bin/env bash
# Build the paper and report everything worth knowing about the result.
#
#   ./paper/build.sh          build and check
#   ./paper/build.sh --clean  remove build artefacts, keep the pdf
#
# Works wherever bash does; the Makefile beside it is the same thing for
# make-based environments. On Windows, MiKTeX installs outside PATH for a
# user-scope install, so this looks for it.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MAIN=main

if [[ "${1:-}" == "--clean" ]]; then
  rm -f $MAIN.aux $MAIN.bbl $MAIN.blg $MAIN.log $MAIN.out p?.log bib.log
  echo "cleaned"
  exit 0
fi

for d in \
  "$HOME/AppData/Local/Programs/MiKTeX/miktex/bin/x64" \
  "/c/Users/${USER:-${USERNAME:-}}/AppData/Local/Programs/MiKTeX/miktex/bin/x64" \
  "/c/Program Files/MiKTeX/miktex/bin/x64"
do
  [[ -x "$d/pdflatex.exe" || -x "$d/pdflatex" ]] && PATH="$d:$PATH"
done

command -v pdflatex >/dev/null || {
  echo "pdflatex not found. Install a TeX distribution, or build on a machine" >&2
  echo "that has one - the cluster hosts generally do (try: module avail tex)." >&2
  exit 1
}

# Three passes plus bibtex: the first resolves nothing, bibtex builds the
# bibliography, and the last two settle cross-references and the page numbers
# those shift.
pdflatex -interaction=nonstopmode $MAIN >/dev/null 2>&1
bibtex $MAIN > bib.log 2>&1
bib_status=$?
pdflatex -interaction=nonstopmode $MAIN >/dev/null 2>&1
pdflatex -interaction=nonstopmode $MAIN > p3.log 2>&1

echo "=== errors ==="
grep -E "^! " $MAIN.log || echo "none"

echo
echo "=== bibtex ==="
if (( bib_status != 0 )) || grep -qiE "error|skipping" bib.log; then
  grep -iE "error|skipping|warning" bib.log | head -8
  echo "NOTE: BibTeX rejects % comments inside an entry - it reads the line as"
  echo "      a field name and drops the entry silently. Keep notes between"
  echo "      entries."
else
  echo "ok, $(grep -c bibitem $MAIN.bbl 2>/dev/null || echo 0) entries"
fi

echo
echo "=== unresolved ==="
echo "citations:  $(grep -c 'Citation.*undefined' $MAIN.log 2>/dev/null || echo 0)"
echo "references: $(grep -c 'Reference.*undefined' $MAIN.log 2>/dev/null || echo 0)"

echo
echo "=== overfull boxes over 10pt ==="
grep -oE "Overfull .hbox \([0-9.]+pt" $MAIN.log 2>/dev/null \
  | awk -F'[(]' '$2+0>10' | head -8 || true
grep -qoE "Overfull .hbox \([0-9.]+pt" $MAIN.log 2>/dev/null || echo "none"

echo
echo "=== still to fill in ==="
grep -nE "TODO|\\\\pending\{" $MAIN.tex | sed 's/^/  /' | head -12
echo "  ($(grep -cE 'TODO|\\\\pending\{' $MAIN.tex) lines)"

echo
echo "=== result ==="
grep -oE "Output written on $MAIN.pdf \([0-9]+ pages?, [0-9]+ bytes" $MAIN.log \
  || echo "no PDF produced"
echo
echo "MSR limit is 4 pages plus 1 of references."
