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
  timeout 900 python "$1" > "$OUT/log" 2>&1
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
timeout 900 python .github/scripts/invariant_checks.py > "$OUT/log" 2>&1
rc=$?
tail -n 4 "$OUT/log"
echo "exit=$rc"
[ "$rc" -eq 0 ] || bad="$bad invariants"

echo "=== the Windows regions are all still in place ==="
timeout 300 python tools/win_port.py --check > "$OUT/log" 2>&1
rc=$?
tail -n 3 "$OUT/log"
echo "exit=$rc"
[ "$rc" -eq 0 ] || bad="$bad win_port --check"

if [ -n "$bad" ]; then
  echo "FAILED:$bad"
  exit 1
fi
echo "all green"
