"""The fleet defect shape, hunted in an edition's NATIVE timers.

Usage:  python3 tools/timersweep.py [path/to/browser.py]

Every edition hand-ports browser.py, so a timer bug in one is a timer
bug in three. This runs anywhere: point it at any edition's browser.py.

SHAPE: an expensive construction fired unconditionally from a REPEATING
timer, whether or not its inputs changed. start.html:2792 builds two
Intl.DateTimeFormat a second for a string that changes once a minute;
browser-linux found downloads.html doing it per-entry at 100 renders a
minute. Those are shared HTML and get fixed once. browser.py's own
QTimers are per-edition and nobody has looked.

Repeating means: a QTimer with .start() and no setSingleShot(True), or a
singleShot whose callback re-arms itself.
"""
import ast, re, sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "browser.py")
src = TARGET.read_text()
lines = src.splitlines()
tree = ast.parse(src)

# Costly constructs. THIS DICT IS THE TOOL; the parsing is boilerplate.
# Extend it for your platform -- the entries below marked (mac) came from
# browser-mac, which found ZERO repeating timers reaching a macOS native
# call but flagged these as the ones that would bite elsewhere.
COSTLY = {
    "system_profiler": "system_profiler (seconds, not ms)",          # mac
    "/usr/bin/security": "Keychain -- can raise a GUI prompt",       # mac
    "caffeinate": "spawns a HELD process (a leak, not a cost)",      # mac
    "refreshRate(": "display query, crosses to the window server",   # mac
    "primaryScreen(": "display query, crosses to the window server", # mac
    "QLocale(": "locale construction", "QRegularExpression(": "regex compile",
    "re.compile(": "regex compile", "setStyleSheet(": "QSS re-parse",
    "QFontMetrics(": "font metrics", "QFont(": "font construction",
    "strftime(": "date formatting", "toString(": "date/number formatting",
    "json.loads(": "json parse", "json.dumps(": "json serialise",
    ".clear()": "full teardown", "tint(": "theme re-tint",
    "read_text(": "file read", "QPixmap(": "pixmap decode",
    "smaps": "proc read", "subprocess.": "subprocess",
    "QProcess(": "subprocess",
}

# every function def, by name, with its line span
funcs = {}
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        funcs.setdefault(n.name, []).append((n.lineno, n.end_lineno or n.lineno))

# A callback is REPEATING if it is a timeout.connect target, or a singleShot
# target whose own body re-arms. A plain singleShot fires ONCE and is not the
# shape at all.
#
# This filter was missing until browser-mac pointed it out: the docstring said
# "a singleShot whose callback re-arms itself" and the code added EVERY
# singleShot target, computing a `rearms` flag it then only printed. Four of
# this edition's eight reported hits turned out to be once-per-launch
# singleShots. Right verdict, wrong reason -- and in the sweep written to hunt
# exactly that defect.
cbs, oneshot = {}, {}
for i, line in enumerate(lines, 1):
    m = re.search(r"timeout\.connect\(\s*(?:self\.)?([A-Za-z_][\w]*)", line)
    if m:
        cbs.setdefault(m.group(1), []).append((i, line.strip()))
    m = re.search(r"QTimer\.singleShot\(([^,]+),\s*(?:self\.)?([A-Za-z_][\w]*)\s*\)", line)
    if m:
        oneshot.setdefault(m.group(2), []).append((i, line.strip()))

def scan(name, sites):
    """(span, costly, rearms) for a callback, or None if it has no body here."""
    for lo, hi in funcs.get(name, []):
        body = "\n".join(lines[lo - 1:hi])
        found = sorted({why for tok, why in COSTLY.items() if tok in body})
        return lo, hi - lo, found, "singleShot" in body
    return None


repeating, once = [], []
for name, sites in sorted(cbs.items()):
    got = scan(name, sites)
    if got:
        repeating.append((name,) + got + (sites,))
for name, sites in sorted(oneshot.items()):
    got = scan(name, sites)
    if not got:
        continue
    (repeating if got[2] and got[3] else once).append((name,) + got + (sites,))

print("%d REPEATING callbacks (timeout.connect, or a singleShot that re-arms)"
      % len(cbs))
print("%d one-shot singleShot targets, NOT the shape -- listed separately\n"
      % len(oneshot))

print("REPEATING, with a costly construct -- these are the candidates:")
hits = [r for r in repeating if r[3]]
for name, lo, span, found, rearms, sites in sorted(hits, key=lambda h: -len(h[3])):
    print("  %-26s %s:%-6d %3d lines  %s%s"
          % (name, TARGET.name, lo, span, ", ".join(found),
             "   [re-arms]" if rearms else ""))
    for at, text in sites[:3]:
        print("      armed at %s:%-6d %s" % (TARGET.name, at, text[:78]))

print("\nONE-SHOT, with a costly construct -- fires once per launch, not the shape:")
for name, lo, span, found, rearms, sites in sorted(once, key=lambda h: h[0]):
    if not found:
        continue
    print("  %-26s %s:%-6d %s" % (name, TARGET.name, lo, ", ".join(found)))
    for at, text in sites[:2]:
        print("      armed at %s:%-6d %s" % (TARGET.name, at, text[:78]))

print("\n%d of %d REPEATING callbacks contain a costly construct"
      % (len(hits), len(cbs)))

# REACH, stated so a clean result is not over-read: this finds callbacks
# reached by `timeout.connect(...)` or a direct `QTimer.singleShot(ms,
# self.foo)`. A timer armed through a lambda, a functools.partial, or a
# signal relayed via another object is NOT in the count. So the total is
# a lower bound on the population, not a census.
