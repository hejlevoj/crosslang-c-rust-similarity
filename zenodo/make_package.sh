#!/usr/bin/env bash
# Assemble the archive to upload to Zenodo.
#
#   ./zenodo/make_package.sh
#
# Produces zenodo/crustpairs-v1.0.zip from the files tracked in git, so
# nothing untracked or ignored can leak in - the model_lora directory in a
# working tree also holds 5 MB of tokenizer copies that are deliberately not
# versioned, and a naive copy would ship them.
#
# This builds the package. It does not upload: the deposit is created under
# the authors' Zenodo account. See DEPOSIT_GUIDE.md for the steps, including
# reserving the DOI before publishing so it can go in the camera-ready.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERSION=1.0.0
NAME="crustpairs-v${VERSION%.*}"
OUT="zenodo/$NAME.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/$NAME"

say() { printf '  %s\n' "$*"; }

mkdir -p "$ROOT"

# ---------------------------------------------------------------- the data
say "dataset"
mkdir -p "$ROOT"
git show HEAD:dataset/dataset.jsonl > "$ROOT/dataset.jsonl"

# ------------------------------------------------------------- the licences
say "licences"
mkdir -p "$ROOT/LICENSES"
for f in LICENSE DATA_LICENSES.md CITATION.cff .zenodo.json; do
  git show "HEAD:$f" > "$ROOT/$(basename "$f")"
done
git show HEAD:LICENSES/CDLA-Permissive-2.0.txt \
  > "$ROOT/LICENSES/CDLA-Permissive-2.0.txt"

# ---------------------------------------------------------------- the code
# Everything needed to rebuild the dataset from its inputs and to reproduce
# the reported numbers. Paths are kept as they are in the repository so the
# scripts' relative imports still resolve.
say "scripts"
while read -r f; do
  mkdir -p "$ROOT/$(dirname "$f")"
  git show "HEAD:$f" > "$ROOT/$f"
done < <(git ls-files 'dataset/**/*.py' 'dataset/**/requirements.txt' \
                     'dataset/**/*.md' 'dataset/README.md' \
         | grep -v '^dataset/finetune/model_lora/')

# ------------------------------------------------------------- the results
say "results"
mkdir -p "$ROOT/results"
while read -r f; do
  git show "HEAD:$f" > "$ROOT/results/$(basename "$f")"
done < <(git ls-files 'dataset/finetune/outputs/results_*.json')

# ------------------------------------------------------- the trained adapter
# The adapter is 1.2 MB and is the artifact people will actually reuse. The
# full finetune checkpoint is 126M parameters and is deliberately left out.
say "LoRA adapter"
mkdir -p "$ROOT/model_lora"
while read -r f; do
  git show "HEAD:$f" > "$ROOT/model_lora/$(basename "$f")"
done < <(git ls-files 'dataset/finetune/model_lora/*')

# ------------------------------------------------------------------ package
cp zenodo/DEPOSIT_README.md "$ROOT/README.md"

# zip adds to an existing archive rather than replacing it, so a re-run would
# otherwise accumulate files that are no longer meant to be in the package.
rm -f "$OUT"
( cd "$STAGE" && zip -qr "$OLDPWD/$OUT" "$NAME" )

echo
echo "Wrote $OUT"
du -h "$OUT" | sed 's/^/  /'
echo
echo "Contents:"
unzip -l "$OUT" | tail -n +4 | head -40 | sed 's/^/  /'
echo
cat <<'NEXT'
Next, by hand:

  1. zenodo.org -> New upload, drop the zip in.
  2. Fill the form from .zenodo.json inside the archive. Zenodo does not read
     that file for a manual upload; it only does so for its GitHub release
     integration.
  3. Licence: Creative Commons Attribution-NonCommercial 4.0. This is NOT a
     free choice - 1018 of the 1857 pairs derive from xCodeEval under CC
     BY-NC 4.0, so the aggregate cannot be released under anything more
     permissive.
  4. Add ORCIDs for each author, and related identifiers for the two source
     corpora.
  5. Reserve the DOI before publishing. Zenodo will show it while the deposit
     is still a draft, which is what lets you cite it in the camera-ready.

After publishing, metadata stays editable but files are yours to change for
only 45 days; after that, corrections go through a new version with its own
DOI. Deleting a published record needs Zenodo support and leaves a tombstone.
Check the licence and the author list before you press it.
NEXT
