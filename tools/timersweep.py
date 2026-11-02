"""The fleet defect shape, hunted in an edition's NATIVE timers.

Usage:  python3 tools/timersweep.py [path/to/browser.py]
        python3 tools/timersweep.py --selftest

SHAPE: an expensive construction fired unconditionally from a REPEATING
timer, whether or not its inputs changed. start.html:2792 builds two
Intl.DateTimeFormat a second for a string that changes once a minute.
Every edition hand-ports browser.py, so a timer bug in one is a timer
bug in three: point this at any edition's copy.

REPEATING means a timeout.connect target, or a singleShot target whose
own body re-arms. A plain QTimer.singleShot(ms, self.foo) fires ONCE and
is not the shape -- those are counted and printed separately.

THE UNIT, because browser-mac and this tool count different things and
both are defensible. This counts distinct callback NAMES reached by
timeout.connect, and does NOT exclude a timer someone marked
setSingleShot(True) -- it cannot, because the mark is on the timer
object and resolving which object needs per-function scope resolution.
mac's sweep counts CALL SITES with scope resolution and excludes the
explicit single-shots: on mac that is 18 of 55 sites. So a count here is
"callback names on a timeout signal" and a count there is "repeating
call sites". Neither is wrong and they are not comparable. If a
repeating-count is ever put in a report next to another edition's, the
DEFINITION has to travel with the number.

This edition has 17 setSingleShot(True) sites, so its 40 is an
over-count of genuinely repeating callbacks by up to that many. It does
not touch the four hits: all four were checked by hand and none of
their timers is marked single-shot -- _show_time is setInterval(20000)
with no mark, _caption_tick and _lapse_tick both .start(ms) with no
mark, _drop_private_profile re-arms explicitly.

REACH, so a clean result is not over-read. This finds callbacks named
directly: `timeout.connect(self.foo)` or `QTimer.singleShot(ms,
self.foo)`. It is BLIND to a timer armed through a lambda, a
functools.partial, a relayed signal, or a local closure -- browser-mac
caught `forget` by reading, and this tool cannot see it at all. Any
count printed here is a LOWER BOUND on the population, not a census.

WHY --selftest EXISTS. The first version of this file computed the
re-arms flag and then only PRINTED it, never filtering on it, so every
one-shot singleShot was counted as a repeating timer -- the tool built
to hunt "stated criterion disagrees with actual behaviour" had exactly
that defect inside it, and it shipped to two other editions. It had been
checked only by removing a known bug and watching it go silent.
browser-mac validated its own sweep in BOTH directions: remove the bug
AND plant the shape in a handler just called clean. --selftest does
that, including a planted one-shot that must NOT be reported, which is
the regression test for the bug above. Run it before trusting a count.
"""
import ast, re, sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

# Costly constructs. THIS DICT IS THE TOOL; the parsing is boilerplate.
# Extend it for your platform. Entries tagged (mac) came from browser-mac,
# which found ZERO repeating timers reaching a macOS native call but named
# these as the ones that bite on editions that do tick them.
COSTLY = {
    "QLocale(": "locale construction", "QRegularExpression(": "regex compile",
    "re.compile(": "regex compile", "setStyleSheet(": "QSS re-parse",
    "QFontMetrics(": "font metrics", "QFont(": "font construction",
    "strftime(": "date formatting", "toString(": "date/number formatting",
    "json.loads(": "json parse", "json.dumps(": "json serialise",
    ".clear()": "full teardown", "tint(": "theme re-tint",
    "read_text(": "file read", "QPixmap(": "pixmap decode",
    "smaps": "proc read", "subprocess.": "subprocess", "QProcess(": "subprocess",
    # (mac) -- the last of these is the only entry whose defect is a LEAK
    # rather than a cost: a HELD process per tick, not wasted work per tick.
    "system_profiler": "system_profiler (seconds, not ms)",
    "/usr/bin/security": "Keychain -- can raise a GUI prompt from a timer",
    "refreshRate(": "display query, crosses to the window server",
    "primaryScreen(": "display query, crosses to the window server",
    "caffeinate": "spawns a HELD process (a leak, not a cost)",
}


def sweep(src):
    """(repeating, oneshot, n_repeating, n_oneshot) for one source text.

    repeating/oneshot are [(name, line, span, [why], rearms, [(line, text)])],
    only for callbacks that contain at least one costly construct.
    """
    lines = src.splitlines()
    funcs = {}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.setdefault(n.name, []).append((n.lineno, n.end_lineno or n.lineno))

    ticking, shot = {}, {}
    for i, line in enumerate(lines, 1):
        m = re.search(r"timeout\.connect\(\s*(?:self\.)?([A-Za-z_][\w]*)", line)
        if m:
            ticking.setdefault(m.group(1), []).append((i, line.strip()))
        m = re.search(r"QTimer\.singleShot\(([^,]+),\s*(?:self\.)?([A-Za-z_][\w]*)\s*\)",
                      line)
        if m:
            shot.setdefault(m.group(2), []).append((i, line.strip()))

    def scan(name):
        for lo, hi in funcs.get(name, []):
            body = "\n".join(lines[lo - 1:hi])
            return (lo, hi - lo,
                    sorted({why for tok, why in COSTLY.items() if tok in body}),
                    "singleShot" in body)
        return None

    # A name that does not resolve to a def in this file is NOT a callback:
    # `timeout.connect(lambda: self.foo())` matches the regex and yields the
    # literal "lambda". Counting those inflated the headline -- browser.py
    # reported 42 repeating callbacks, one of which was "lambda" standing in
    # for six lambda-armed sites. They are now counted as UNRESOLVED arming
    # sites, which is the tool's reach expressed as a number instead of a
    # paragraph: a count that moves when someone widens the regex.
    unresolved = 0
    repeating, oneshot, named = [], [], 0
    for name, sites in sorted(ticking.items()):
        got = scan(name)
        if got is None:
            unresolved += len(sites)
            continue
        named += 1
        if got[2]:
            repeating.append((name,) + got + (sites,))
    for name, sites in sorted(shot.items()):
        got = scan(name)
        if got is None:
            unresolved += len(sites)
            continue
        if not got[2]:
            continue
        # re-arms -> genuinely repeating; otherwise once per launch
        (repeating if got[3] else oneshot).append((name,) + got + (sites,))
    n_shot = sum(1 for n in shot if scan(n) is not None)
    return repeating, oneshot, named, n_shot, unresolved


def report(src, label):
    repeating, oneshot, n_tick, n_shot, unresolved = sweep(src)
    print("%d REPEATING callbacks (timeout.connect, or a singleShot that re-arms)"
          % n_tick)
    print("%d one-shot singleShot targets, NOT the shape -- listed separately"
          % n_shot)
    print("%d arming sites UNRESOLVED -- lambda / closure / attribute targets "
          "this tool cannot name\n" % unresolved)
    print("REPEATING, with a costly construct -- these are the candidates:")
    for name, lo, span, found, rearms, sites in sorted(repeating,
                                                       key=lambda h: -len(h[3])):
        print("  %-26s %s:%-6d %3d lines  %s%s"
              % (name, label, lo, span, ", ".join(found),
                 "   [re-arms]" if rearms else ""))
        for at, text in sites[:3]:
            print("      armed at %s:%-6d %s" % (label, at, text[:78]))
    print("\nONE-SHOT, with a costly construct -- once per launch, not the shape:")
    for name, lo, span, found, rearms, sites in sorted(oneshot, key=lambda h: h[1]):
        print("  %-26s %s:%-6d %s" % (name, label, lo, ", ".join(found)))
        for at, text in sites[:2]:
            print("      armed at %s:%-6d %s" % (label, at, text[:78]))
    print("\n%d of %d REPEATING callbacks contain a costly construct"
          % (len(repeating), n_tick))
    print("REACH: lambda / functools.partial / relayed signals / local closures "
          "are invisible here.\n       Any count above is a LOWER BOUND.")


CASE = '''
class T:
    def __init__(self):
        t = QTimer(self)
        t.timeout.connect(self.tick)
        QTimer.singleShot(3000, self.once)
    def tick(self):
        %s
    def once(self):
        self.x = QLocale().toString(QTime.currentTime())
'''


def selftest():
    """Both directions, plus the regression test for the shipped bug."""
    ok = True

    def check(what, cond):
        nonlocal ok
        print("  %-58s %s" % (what, "ok" if cond else "FAIL"))
        ok = ok and bool(cond)

    # 1. planted positive: the shape, in a repeating callback
    rep, shot, _, _, _ = sweep(CASE % "self.x = QLocale().toString(QTime.currentTime())")
    check("planted shape in a repeating callback is FOUND",
          any(n == "tick" for n, *_ in rep))
    # 2. removed negative: same handler, nothing costly in it
    rep2, _, _, _, _ = sweep(CASE % "self.x = 1")
    check("same handler with the construct removed goes SILENT",
          not any(n == "tick" for n, *_ in rep2))
    # 3. THE REGRESSION TEST: a one-shot with a costly construct must not
    #    be reported as repeating. This is the bug that shipped.
    check("one-shot singleShot is NOT in the repeating list",
          not any(n == "once" for n, *_ in rep))
    check("one-shot singleShot IS in the one-shot list",
          any(n == "once" for n, *_ in shot))
    # 4. THE BLIND SPOTS, asserted rather than only described. A lambda and
    #    a local closure are invisible here, and that is a known limit, not a
    #    pass -- so it is pinned. If someone widens the regex, these FAIL and
    #    tell them the reach changed, instead of the reach changing quietly.
    #    browser-mac's lesson, generalised: a mutation has to aim at the part
    #    that decides WHETHER TO LOOK, not only the part that looks.
    blind = '''
class T:
    def __init__(self):
        t = QTimer(self)
        t.timeout.connect(lambda: self.hidden())
        def later():
            self.x = QLocale().toString(QTime.currentTime())
        QTimer.singleShot(500, later)
    def hidden(self):
        self.x = QLocale().toString(QTime.currentTime())
'''
    brep, bshot, n_tick, n_shot, unres = sweep(blind)
    check("KNOWN BLIND: a lambda-armed callback is not named as one",
          not any(n == "hidden" for n, *_ in brep) and n_tick == 0)
    check("KNOWN BLIND: the lambda site is COUNTED as unresolved",
          unres >= 1)
    check('no callback is ever named "lambda"',
          not any(n == "lambda" for n, *_ in brep + bshot))

    # 5. a one-shot target that re-arms itself IS repeating
    rearm = CASE.replace("    def once(self):\n"
                         "        self.x = QLocale().toString(QTime.currentTime())",
                         "    def once(self):\n"
                         "        self.x = QLocale().toString(QTime.currentTime())\n"
                         "        QTimer.singleShot(1000, self.once)")
    rep3, shot3, _, _, _ = sweep(rearm % "self.x = 1")
    check("a singleShot callback that re-arms counts as repeating",
          any(n == "once" for n, *_ in rep3) and not any(n == "once" for n, *_ in shot3))
    print("\n%s" % ("selftest passed" if ok else "SELFTEST FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "browser.py")
    report(target.read_text(), target.name)
