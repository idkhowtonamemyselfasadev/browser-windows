#!/bin/sh
# The whole offscreen suite, in one go, with a tail of each run.
#
# This edition cannot be run on the machine it is built on, so the suite
# is the only evidence the port is right. The tests are the Linux ones,
# run against this browser.py: they exercise the shared code, which is
# all of it bar the handful of Windows regions in tools/win_port.json.
# Those regions are checked separately by `tools/win_port.py --check`.
#
# Everything here redirects its own data into scratch; nothing touches
# the vault or the config of the browser you actually use.
R=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$R" || exit 1
export QT_QPA_PLATFORM=offscreen

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
  # straight into tail reports tail's status and every failure reads
  # as a pass.
  timeout 900 python "$1" > "$OUT/log" 2>&1
  rc=$?
  tail -3 "$OUT/log"
  echo "exit=$rc"
  [ $rc -eq 0 ] || bad="$bad $2$1"
}

for t in test_page.py test_newtab.py test_panes.py test_paneload.py test_vaultoff.py \
         test_theme.py test_trust.py test_vault.py test_providers.py \
         test_async.py test_upgrade.py test_op_page.py test_toolbar.py \
         test_wizard.py test_contrast.py test_themefix.py; do
  run "$t" ""
done

# ours, not Linux's: the Windows-only regions, exercised as far as a
# Linux machine allows
run "test_windows.py" ""

cd "$R/tests" || exit 1
for t in test_twostep.py test_round3.py test_msaccounts.py test_identbox.py \
         test_subdomain.py; do
  [ -f "$t" ] || continue
  run "$t" "tests/"
done
cd "$R" || exit 1

echo "=== invariants ==="
python .github/scripts/invariant_checks.py > "$OUT/log" 2>&1
rc=$?; tail -4 "$OUT/log"; echo "exit=$rc"
[ $rc -eq 0 ] || bad="$bad invariant_checks"

echo "=== windows regions ==="
python tools/win_port.py --check > "$OUT/log" 2>&1
rc=$?; tail -3 "$OUT/log"; echo "exit=$rc"
[ $rc -eq 0 ] || bad="$bad win_port --check"

echo
if [ -n "$bad" ]; then
  echo "FAILED:$bad"
  exit 1
fi
echo "all green"
