#!/usr/bin/env bash
# Check the cluster scripts before taking them to a cluster.
#
#   ./cluster/selftest.sh
#
# `bash -n` validates the shell but says nothing about the Python embedded in
# heredocs, which is where the verification and preflight logic lives. A
# SyntaxError in one of those blocks only surfaces on the machine it was
# supposed to protect, after a login and a module load - which has already
# happened once. This extracts every `python - <<'TAG' ... TAG` block and
# compiles it.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Any interpreter will do - this only compiles, never runs. On Windows `python`
# is the Store stub that prints an advert and exits, so try it last.
PYBIN=""
for c in python3 "py -3" python; do
  if $c -c "import sys" >/dev/null 2>&1; then PYBIN="$c"; break; fi
done
[[ -n "$PYBIN" ]] || { echo "no python found to check heredocs with" >&2; exit 1; }

fail=0

echo "Shell syntax"
for f in *.sh; do
  if bash -n "$f" 2>/dev/null; then
    echo "  ok    $f"
  else
    echo "  FAIL  $f"; bash -n "$f" || true; fail=1
  fi
done

echo
echo "Embedded Python"
for f in *.sh; do
  # Pull out each heredoc fed to python, compile it, report where it started.
  $PYBIN - "$f" <<'PY' || fail=1
import re, sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read().splitlines(keepends=True)

# The python invocation is not always at the start of the line - worker.sh
# uses `if ! python - <<'PY'` - so match anywhere, requiring only that the
# heredoc is fed to a python on that line.
start = re.compile(r"""\bpython\d*\s+-\s+<<\s*['"]?(\w+)['"]?\s*$""")
i, found, bad = 0, 0, 0
while i < len(src):
    m = start.search(src[i])
    if not m:
        i += 1
        continue
    tag, first = m.group(1), i + 1
    j = first
    while j < len(src) and src[j].rstrip("\n").strip() != tag:
        j += 1
    block = "".join(src[first:j])
    found += 1
    try:
        compile(block, f"{path}:{first + 1}", "exec")
        print(f"  ok    {path}  block at line {first + 1} ({j - first} lines)")
    except SyntaxError as e:
        bad += 1
        print(f"  FAIL  {path}  block at line {first + 1}: "
              f"line {e.lineno} of the block: {e.msg}")
        if e.text:
            print(f"        {e.text.rstrip()}")
    i = j + 1

if not found:
    sys.exit(0)
sys.exit(1 if bad else 0)
PY
done

echo
echo "Config files"
for f in config/*.env; do
  if bash -n "$f" 2>/dev/null; then
    todo=$(grep -c 'TODO' "$f" || true)
    if [[ "$todo" -gt 0 ]]; then
      echo "  ok    $f  ($todo TODO left)"
    else
      echo "  ok    $f"
    fi
  else
    echo "  FAIL  $f"; fail=1
  fi
done

echo
if (( fail )); then
  echo "FAILED"
  exit 1
fi
echo "All checks passed."
