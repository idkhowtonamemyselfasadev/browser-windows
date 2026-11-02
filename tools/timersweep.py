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

COSTLY = {
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

# repeating-timer callbacks: X.timeout.connect(self.foo) with a .start() in the file
cbs = {}
for i, line in enumerate(lines, 1):
    m = re.search(r"timeout\.connect\(\s*(?:self\.)?([A-Za-z_][\w]*)", line)
    if m:
        cbs.setdefault(m.group(1), []).append(i)
# and singleShot targets that re-arm (the callback mentions singleShot itself)
for i, line in enumerate(lines, 1):
    m = re.search(r"QTimer\.singleShot\([^,]+,\s*(?:self\.)?([A-Za-z_][\w]*)\s*\)", line)
    if m:
        cbs.setdefault(m.group(1), []).append(i)

print("%d distinct repeating-timer / singleShot callbacks\n" % len(cbs))
hits = []
for name, sites in sorted(cbs.items()):
    for lo, hi in funcs.get(name, []):
        body = "\n".join(lines[lo - 1:hi])
        found = sorted({why for tok, why in COSTLY.items() if tok in body})
        rearms = "singleShot" in body
        if found:
            hits.append((name, lo, hi - lo, found, rearms, sites))
for name, lo, span, found, rearms, sites in sorted(hits, key=lambda h: -len(h[3])):
    print("  %-26s %s:%-6d %3d lines  %s%s"
          % (name, TARGET.name, lo, span, ", ".join(found), "   [re-arms]" if rearms else ""))
    print("      armed at: %s"
          % ", ".join("%s:%d" % (TARGET.name, s) for s in sites[:4]))
print("\n%d of %d callbacks contain at least one costly construct" % (len(hits), len(cbs)))

# REACH, stated so a clean result is not over-read: this finds callbacks
# reached by `timeout.connect(...)` or a direct `QTimer.singleShot(ms,
# self.foo)`. A timer armed through a lambda, a functools.partial, or a
# signal relayed via another object is NOT in the count. So the total is
# a lower bound on the population, not a census.
