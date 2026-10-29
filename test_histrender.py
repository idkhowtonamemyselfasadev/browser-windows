#!/usr/bin/env python3
"""The history page has to actually draw.

test_histicon.py reads the source: the slot is there, the JS asks for a
map of icons, no page fetches one from a third party. All of that was
true and green on 2026-10-27 while the page itself rendered **nothing**.

    history.html:523
      document.getElementById("v_searches").onclick = () => setView(...)

a96d8e8 (2026-10-22) removed the Searches view -- the <button> went and
one textContent line with it. That handler stayed. getElementById
returned null, setting .onclick on null threw, and the throw took out
the whole rest of the inline script: every handler below it and the
initial load(). Four static greps and a green suite walked past it for
five days, because nobody loaded the page.

So there are two kinds of check in here:

  (1) a static one, over every .html the browser ships: an element the
      script reaches for and then dereferences has to exist in the same
      file. This is the one that generalises -- the same orphan in
      settings.html or downloads.html would break those pages the same
      way, silently.
  (2) a live one: open the pane for real and count the rows and the
      icons on screen.

Offscreen, scratch data; the real history and config are never opened.
"""
import os
import re
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["BROWSER_NO_LIB_CHECK"] = "1"

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _boot import B                      # noqa: E402
from tests.harness import app, spin      # noqa: E402
from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402

fails = []


def js(page, code):
    """Run something in the pane's page and wait for the answer.

    The IIFE and MAIN_WORLD_ID are both load-bearing: runJavaScript
    evaluates an expression, so a bare `return` is a syntax error and
    comes back as None -- which reads exactly like a page that drew
    nothing. The browser's own pages run in that world.
    """
    box = {}
    loop = QEventLoop()
    page.runJavaScript("(function(){" + code + "})()", B.MAIN_WORLD_ID,
                       lambda r: (box.update({"v": r}), loop.quit()))
    QTimer.singleShot(8000, loop.quit)
    loop.exec()
    return box.get("v")


def check(what, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what
          + (("  <" + str(detail) + ">") if detail != "" else ""))
    if not ok:
        fails.append(what)


# =====================================================================
print("(1) every element the script reaches for exists in the page")
# =====================================================================
#
# Only the dereferenced ones. `const x = getElementById("y")` followed by
# `if (x)` is a page being careful and is none of our business; it is
# `getElementById("y").foo = ...` and `.appendChild(...)` that throws.
# Both quote styles, on the call and on the id attribute. No page uses
# the single-quoted call form today, so this finds nothing new -- it is
# two characters that close the hole before somebody writes one.
DEREF = re.compile(
    r"""getElementById\(\s*['"]([A-Za-z0-9_\-]+)['"]\s*\)\s*\.\s*[A-Za-z_]""")

PAGES = sorted(p for p in HERE.glob("*.html"))
check("there are pages to check", len(PAGES) > 5, len(PAGES))

for page in PAGES:
    text = page.read_text(encoding="utf-8")
    have = set(re.findall(r"""\bid=\\?['"]([A-Za-z0-9_\-]+)\\?['"]""", text))
    # ids the page builds at runtime count as present
    have |= set(re.findall(r'\.id\s*=\s*"([A-Za-z0-9_\-]+)"', text))
    have |= set(re.findall(r'id="\$\{', text))
    want = set(DEREF.findall(text))
    orphans = sorted(want - have)
    check("%s: %d reached for, none missing" % (page.name, len(want)),
          not orphans, ", ".join(orphans) if orphans else "")


# =====================================================================
print("\n(2) the page draws rows, and their icons come from the store")
# =====================================================================
# held in a name on purpose: nothing else references the QApplication,
# and a bare app() call lets it be collected the instant it returns --
# the next widget then dies with "Must construct a QApplication first".
qapp = app()
win = B.Browser()
win.show()
spin(800)

# "t", not "time". browser.py:45536 writes {"url", "title", "t"} and
# history.html:321 reads e.t. A row with the wrong key still DRAWS --
# new Date(undefined * 1000) is an Invalid Date, the .time span simply
# says so, and every other check in this section passes anyway. Found
# by claude-e8 reading the fixture rather than its output: a check that
# passes for a reason other than the one it claims, which is the same
# shape as the bug this file exists for, one level down.
now = int(time.time())
win.history.append({"url": "https://example.com/a", "title": "An example",
                    "t": now})

# a real 1x1 PNG in the icon store, so site_icon_data has bytes to serve
icons = Path(win.icons_dir())
icons.mkdir(parents=True, exist_ok=True)
(icons / "example.com.png").write_bytes(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"))

check("the store answers for that host",
      (win.site_icon_data("example.com") or "").startswith("data:image/png"))

win.open_history()
spin(4000)
page = win._panes["history"].view.page()

check("the page finished loading",
      js(page, "return document.readyState;") == "complete")
rows = js(page, "return document.querySelectorAll('#list > *').length;")
check("it drew something", (rows or 0) > 0, rows)
check("and the entry is on screen",
      js(page, "return (document.body.innerText || '')"
               ".toLowerCase().includes('example');") is True)

# the timestamp path, which the wrong key left completely unexercised
stamp = js(page, "var e = document.querySelector('#list .time');"
                 "return e ? e.textContent : '(no .time span)';")
check("the row's timestamp rendered from the entry",
      bool(re.match(r"^\s*\d{1,2}[:.]\d{2}", str(stamp or ""))), stamp)

imgs = js(page, "return document.querySelectorAll('#list img').length;")
check("the row has an icon", (imgs or 0) > 0, imgs)
check("...and it is a data: URL out of the local store",
      js(page, "return Array.from(document.querySelectorAll('#list img'))"
               ".every(i => (i.src || '').startsWith('data:'));") is True)
check("...and not one of them was fetched over the network",
      js(page, "return Array.from(document.querySelectorAll('#list img'))"
               ".filter(i => /^https?:/.test(i.src || '')).length;") == 0)

# the handlers that sat below the throw: if the script died, these are
# all undefined and the page looks fine until something is clicked
# v_stats first: it is the line immediately below where the throw was,
# so it is the first casualty and the first thing to break again if a
# view button is ever added or removed. Then the row controls, then the
# five context-menu handlers at the very bottom of the script -- the
# further down the file, the better the canary.
for name in ("v_stats", "bygroup", "shownoise", "export", "delrange",
             "popen", "pgroup", "pbookmark", "pcopy", "pdelete", "pnone"):
    check("the %s control got wired" % name,
          js(page, "return typeof (document.getElementById('%s')"
                   " || {}).onclick;" % name) == "function")

print("\n%d checks failed" % len(fails))
for f in fails:
    print("  - " + f)
# os._exit, like every other suite in here that builds a real Browser.
# sys.exit runs interpreter teardown, which collects the window, its
# WebEngine pages and the profile in whatever order it likes, and about
# one run in five that order is wrong: SIGSEGV after "0 checks failed",
# which is a red for any runner and a lie about the test. Nothing here
# needs to outlive this line.
sys.stdout.flush()
os._exit(1 if fails else 0)
