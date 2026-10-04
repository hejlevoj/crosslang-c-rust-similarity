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
  rm -f $MAIN.aux $MAIN.bbl $MAIN.blg $MAIN.log $MAIN.out p?.log bib*.log paper-build.*
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

# A PDF viewer holding main.pdf open makes pdflatex die with "I can't write on
# file" - and because it dies before writing the .aux, bibtex then reports "I
# found no \bibdata command", which looks like a bibliography problem and is
# not. Build under a scratch jobname when the target is locked, and copy over
# it afterwards if the lock has since cleared.
JOB=$MAIN
if [[ -e $MAIN.pdf ]] && ! (mv "$MAIN.pdf" "$MAIN.pdf.locktest" 2>/dev/null \
     && mv "$MAIN.pdf.locktest" "$MAIN.pdf"); then
  JOB=paper-build
  echo "note: $MAIN.pdf is open in another program; building as $JOB.pdf"
  echo
fi

# Three passes plus bibtex: the first resolves nothing, bibtex builds the
# bibliography, and the last two settle cross-references and the page numbers
# those shift. Everything stays in this directory - with -output-directory,
# MiKTeX does not read the .aux and .bbl back, so every citation and reference
# silently comes out undefined.
pdflatex -interaction=nonstopmode -jobname=$JOB $MAIN.tex >/dev/null 2>&1
bibtex $JOB > bib.log 2>&1
bib_status=$?
pdflatex -interaction=nonstopmode -jobname=$JOB $MAIN.tex >/dev/null 2>&1
pdflatex -interaction=nonstopmode -jobname=$JOB $MAIN.tex > p3.log 2>&1

if [[ "$JOB" != "$MAIN" ]] && cp "$JOB.pdf" "$MAIN.pdf" 2>/dev/null; then
  echo "note: lock cleared, $MAIN.pdf updated"
  echo
fi
MAIN_LOG=$JOB.log

echo "=== errors ==="
grep -E "^! " $MAIN_LOG || echo "none"

echo
echo "=== bibtex ==="
if (( bib_status != 0 )) || grep -qiE "error|skipping" bib.log; then
  grep -iE "error|skipping|warning" bib.log | head -8
  echo "NOTE: BibTeX rejects % comments inside an entry - it reads the line as"
  echo "      a field name and drops the entry silently. Keep notes between"
  echo "      entries."
else
  echo "ok, $(grep -c bibitem ${JOB}.bbl 2>/dev/null || echo 0) entries"
fi

echo
echo "=== unresolved ==="
echo "citations:  $(tr -d '\n' < $MAIN_LOG | grep -oE 'Citation [^ ]+ on page[^.]*undefined' | wc -l)"
echo "references: $(tr -d '\n' < $MAIN_LOG | grep -oE 'Reference [^ ]+ on page[^.]*undefined' | wc -l)"

echo
echo "=== overfull boxes over 10pt ==="
grep -oE "Overfull .hbox \([0-9.]+pt" $MAIN_LOG 2>/dev/null \
  | awk -F'[(]' '$2+0>10' | head -8 || true
grep -qoE "Overfull .hbox \([0-9.]+pt" $MAIN_LOG 2>/dev/null || echo "none"

echo
echo "=== still to fill in ==="
grep -nE "TODO|\\\\pending\{" $MAIN.tex | sed 's/^/  /' | head -12
echo "  ($(grep -cE 'TODO|\\\\pending\{' $MAIN.tex) lines)"

echo
echo "=== result ==="
tr -d '\n' < $MAIN_LOG | grep -oE "\([0-9]+ pages, [0-9]+ bytes" \
  || echo "no PDF produced"
echo
echo "MSR limit is 4 pages plus 1 of references."
