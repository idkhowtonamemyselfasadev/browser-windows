#!/bin/sh
# The whole offscreen suite, in one go, with a tail of each run.
#
# This edition cannot be run on the machine it is built on, so the suite
# is the only evidence the port is right. The tests are the Linux ones,
# run against this browser.py: they exercise the shared code, which is
# all of it bar the one region in tools/win_port.json (the zip updater).
# That region is checked by test_windows.py, and that every other one is
# still in place by `tools/win_port.py --check`.
#
# Everything here redirects its own data into scratch; nothing touches
# the vault or the config of the browser you actually use.
R=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$R" || exit 1
# The interpreter, resolved ONCE and then PROVED.
#
# This script said bare `python` until 2026-11-02, and this box has no
# `python` -- only /usr/bin/python3 and .venv/bin/python. So a full run
# exited 127 on all 101 suites plus both tail steps, and the output had
# no assertion, no traceback and no check name anywhere in it. That
# reads like catastrophic breakage rather than a missing binary, and it
# is how test_offpalette and a stale guard in test_bar sat red across
# commits: nobody could complete a full suite to see them.
#
# THE TELL: when the error names `timeout` or the shell rather than a
# Python file, the interpreter was never reached. Look there first, not
# at the hundred suites.
#
# Resolving is not enough on its own. /usr/bin/python3 is present here
# and has no PyQt6, which is the same failure wearing a different exit
# code -- so each candidate has to import the engine before it is
# accepted. The venv comes first because it is the one that can.
PY=""
for cand in "$R/.venv/bin/python" python3 python; do
  command -v "$cand" > /dev/null 2>&1 || continue
  "$cand" -c "import PyQt6.QtWebEngineWidgets" > /dev/null 2>&1 || continue
  PY="$cand"
  break
done
if [ -z "$PY" ]; then
  echo "no interpreter here can import PyQt6.QtWebEngineWidgets." >&2
  echo "tried: $R/.venv/bin/python, python3, python" >&2
  echo "nothing was run -- this is the runner, not the suites." >&2
  exit 127
fi
echo "interpreter: $PY ($("$PY" -c 'import sys;print(sys.version.split()[0])'))"
echo ""

export QT_QPA_PLATFORM=offscreen
# no browser started in here goes looking for library updates: a real
# check per test would be slow, would depend on what the distribution is
# shipping this morning, and could raise a toast over a window another
# test is inspecting. test_libs drives that check by hand instead.
export BROWSER_NO_LIB_CHECK=1

# test_upgrade.py checks an old browser.py out of THIS repository to
# prove a real upgrade path. The revision it names by default is a
# commit in the Linux repository and does not exist here, so this
# edition names its own: the oldest commit whose browser.py has the
# vault but none of the work since.
OLD_REV=${OLD_REV:-21ccc4c}
export OLD_REV

OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
bad=""

run() {
  echo "=== $1 ==="
  # the exit status has to come from python, not from tail: piping
  # straight into tail reports tail's status, which is always 0 -- so
  # every failure, every crash and every timeout would read as a pass.
  timeout 900 "$PY" "$1" > "$OUT/log" 2>&1
  rc=$?
  tail -n 3 "$OUT/log"
  echo "exit=$rc"
  [ "$rc" -eq 0 ] || bad="$bad $2"
}

# Every suite in the folder, rather than a list to keep in step with
# one: what is here is exactly what the port brought over, and a suite
# that arrives with a port has to run without anyone remembering to add
# it. (The old list had stopped at twenty while the Linux one grew to
# eighty-seven.) test_windows.py is ours and is in here too.
for t in test_*.py; do
  [ -f "$t" ] || continue
  run "$t" "$t"
done

cd "$R/tests" || exit 1
for t in test_*.py; do
  [ -f "$t" ] || continue
  run "$t" "tests/$t"
done

cd "$R" || exit 1
echo "=== invariants ==="
timeout 900 "$PY" .github/scripts/invariant_checks.py > "$OUT/log" 2>&1
rc=$?
tail -n 4 "$OUT/log"
echo "exit=$rc"
[ "$rc" -eq 0 ] || bad="$bad invariants"

echo "=== the Windows regions are all still in place ==="
timeout 300 "$PY" tools/win_port.py --check > "$OUT/log" 2>&1
rc=$?
tail -n 3 "$OUT/log"
echo "exit=$rc"
[ "$rc" -eq 0 ] || bad="$bad win_port --check"

if [ -n "$bad" ]; then
  echo "FAILED:$bad"
  exit 1
fi
echo "all green"
