#!/usr/bin/env python3
"""Nothing of his is in this tree, and a port cannot put it back.

Three different things, and the third is the one worth having.

(1) The direct assertion: no file a port writes contains his home
    directory, the subnet his own machines sit on, or his mail handle.
    That is the same question browser-pages/pages.py asks of the nine
    shared pages, asked here of all 118 files tools/win_port.json names
    -- because the leak that blocked every commit in this repo on
    2026-10-28 was in a page, but its two runtime translations were in
    browser.py, where the pages check does not look. Fixing the markup
    and leaving the translation puts the leak back on screen.

(2) The substitutions in win_port.json really do rewrite each spelling
    the two upstreams use, and running them twice changes nothing.
    ~/browser still carries the notes placeholder with his home
    directory in it, and the host-override hint with his subnet, at the
    ported base -- and the HTML pages are *copied* across rather than
    merged, so without these rules a port reintroduces both and the
    pre-commit check blocks the repo again.

    Every needle below is built from fragments rather than written out,
    for the same reason win_port.json's are: a guard that spells out the
    string it forbids puts that string in a public repo, and gitguard's
    pre-commit refuses it, correctly.

(3) The markers actually bite. A marker that passes proves nothing on
    its own -- it has to fail when the thing it guards is gone, and a
    marker list nobody has ever seen fail is a list of untested
    assertions. So each regression a port could plausibly produce is
    simulated here, in memory, and the marker that must catch it is
    required to catch it. This is where the history page's icon bridge
    is defended: tools/port_map.py reported it as a conflict region no
    marker covered, and an undefended region is one a hand-resolved
    conflict can drop in silence.

Static, in-process, no Qt, no network, writes nothing. Runs from
anywhere.
"""
import importlib.util
import os
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOLS = REPO / "tools"

fails = []


def check(what, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what
          + (("  <" + str(detail) + ">") if detail != "" else ""))
    if not ok:
        fails.append(what)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wp = load("win_port_mod", TOOLS / "win_port.py")
MAN = json.loads((TOOLS / "win_port.json").read_text(encoding="utf-8"))

# The file set a port writes: merge_files + copy_files, minus the prose
# entries, which start with '#' (same convention as win_port.py's own
# names()).
WANT = [n for n in MAN["merge_files"] + MAN["copy_files"]
        if not n.startswith("#")]
FILES = {}
absent = []
for name in WANT:
    path = REPO / name
    if path.is_file():
        FILES[name] = path.read_text(encoding="utf-8", errors="replace")
    else:
        absent.append(name)

print("(1) nothing of his is in any file a port writes")
check("the manifest's files are all here", not absent, absent or len(FILES))

# Exactly browser-pages/pages.json's "leaks" list, deliberately: one of
# the two tools noticing is not enough, and this one sees browser.py.
# Built, never written out -- see the docstring.
#
# His login comes from the account this runs under rather than being
# typed: splitting the needle into "/home/" + "<name>" defeats a
# pattern looking for the PATH, but the second half is still the name
# in clear text, and on 2026-10-29 this file was one of thirteen in
# this edition carrying it -- the suite whose whole job is to say
# nothing of his is here, carrying it twice. Read off the account, it
# costs nothing, spells nothing, and makes the suite describe whoever
# runs it instead of one person.
#
# NOT Path.home().name, which was the first attempt and failed in a way
# worth keeping: every suite here is required to run with HOME pointed
# at a throwaway directory, so Path.home().name is the name of that
# directory. Mine was called "wf2", "wf2" appears in a fixture string
# in this very file, and the new check reported a leak that was its own
# test data. The account id does not move when HOME does.
try:
    import pwd
    WHO = pwd.getpwuid(os.getuid()).pw_name
except Exception:                                   # noqa: BLE001
    import getpass
    WHO = getpass.getuser()
HOME = "/home/" + WHO
LAN = "192.168." + "2."
MAIL = "magic" + "wing"
HIS = [("his home directory", HOME),
       ("the subnet his machines sit on", LAN),
       ("his mail handle", MAIL)]
for what, needle in HIS:
    hits = sorted(n for n, text in FILES.items() if needle in text)
    check("no file writes %s" % what, not hits, hits or "%d files" % len(FILES))

# His NAME is asked separately and with a word boundary, because it is
# three letters and the prefix of ordinary English: a substring test
# reports time, timer, timeout, timestamp, estimate and optimal in 86
# of these files, which is what the first version of this check did.
#
# It also does NOT get a catch-all substitution the way the three above
# do, and that asymmetry is the point rather than an omission. A rule
# replacing a bare "<name>" would rewrite every one of those words in
# every ported file. So the rules in win_port.json name the shapes the
# name actually appears in -- quoted as a fixture value, in an example
# mail address, in prose -- and this check is what says the list is
# complete. If a port brings in a fourteenth shape, this fails and the
# rule gets written; nothing silently passes.
BARE = re.compile(r"\b" + re.escape(WHO) + r"\b")
named = sorted(n for n, text in FILES.items() if BARE.search(text))
check("no file writes his name on its own", not named,
      named or "%d files" % len(FILES))


print()
print("(2) a port rewrites every spelling the upstreams use, idempotently")
# The two routes into this tree spell the same string differently:
# win_port copies the page out of ~/browser, browser-pages/pages.py
# ports it out of ~/claude/browser-linux. A rule for one guards one.
SPELLINGS = [
    ('placeholder="%s/Notes"' % HOME, 'placeholder="C:\\Users\\You\\Notes"',
     "the notes placeholder, as ~/browser writes it"),
    ('placeholder="/home/you/Notes"', 'placeholder="C:\\Users\\You\\Notes"',
     "the notes placeholder, as browser-linux writes it"),
    ("example.com %s10." % LAN, "example.com 192.0.2.10.",
     "the host-override hint, as ~/browser writes it"),
    ("example.com 192.168.1.10.", "example.com 192.0.2.10.",
     "the host-override hint, as browser-linux writes it"),
    ("ip %s0/24" % LAN, "ip 192.168.1.0/24",
     "the base-converter docstring's example network"),
]
for before, after, what in SPELLINGS:
    once, _ = wp.apply_substitutions({"settings.html": before},
                                     MAN["substitutions"])
    got = once["settings.html"]
    check("a port rewrites %s" % what, got == after, got)
    twice, _ = wp.apply_substitutions({"settings.html": got},
                                      MAN["substitutions"])
    check("...and rewriting it again changes nothing",
          twice["settings.html"] == after, twice["settings.html"])

# A line of his that arrives in some shape nobody listed must not come
# through just because no specific rule names it.
for what, needle in HIS[:2]:
    sample = "a line with %s in it\n" % needle
    out, _ = wp.apply_substitutions({"browser.py": sample},
                                    MAN["substitutions"])
    check("the catch-all takes %s wherever it appears" % what,
          needle not in out["browser.py"], out["browser.py"].strip())


print()
print("(3) every marker that guards those bites when the thing is gone")
baseline = wp.check_markers(dict(FILES), MAN["markers"])
check("the tree as it stands passes every marker", not baseline,
      baseline[:2] or "%d markers" % len(MAN["markers"]))

# (file, find, replace) -- the regression, written as the smallest edit
# that produces it. A hand-resolved merge conflict is exactly this: one
# region ending up with the other side's text, or with nothing.
REGRESSIONS = [
    ("his subnet back in browser.py",
     "browser.py", "ip 192.168.1.0/24", "ip %s0/24" % LAN),
    ("the host-override hint back to his LAN, both languages",
     "browser.py", "example.com 192.0.2.10.", "example.com %s10." % LAN),
    ("his home directory back in the settings page",
     "settings.html", 'placeholder="C:\\Users\\You\\Notes"',
     'placeholder="%s/Notes"' % HOME),
    ("his subnet back in a suite",
     "test_dev.py", "192.168.1.10", "%s10" % LAN),
    ("his home directory back in a suite",
     "test_bar.py", "/home/you/x", "%s/x" % HOME),
    # The history page's icon bridge. ~/browser has these in its working
    # tree only, so to every commit a port can see they look like ours.
    # Drop either and bridge.siteIcons is undefined, the callback throws
    # inside load(), and the page renders nothing again -- the exact
    # failure a6cb6e3 fixed, by a different route.
    ("the siteIcons slot dropped by a resolution",
     "browser.py", "def siteIcons(self, hosts_json):",
     "def siteIcons_gone(self, hosts_json):"),
    ("the method it reads the icons through dropped",
     "browser.py", 'def site_icon_data(self, host_or_url=""):',
     'def site_icon_data_gone(self, host_or_url=""):'),
    ("the history page no longer asking the bridge for them",
     "history.html", "bridge.siteIcons(", "bridge.siteIcons_gone("),
    ("a page fetching icons from Google again",
     "history.html", "img.src = kept;",
     'img.src = "https://www.google.com/s2/favicons?sz=32&domain=" + host;'),
    # The Windows title bar. Upstream has none of this -- the desktop
    # draws the frame there and is right to -- so to a port these lines
    # look like an edition-only region, which is exactly the kind a
    # hand-resolved conflict drops. Drop any of them and a dark theme
    # gets a white title bar again, which is the one thing that makes a
    # Qt program read as broken rather than minimal on Windows.
    ("the title-bar helper dropped by a resolution",
     "browser.py", "def _windows_dark_titlebar(widget, dark):",
     "def _windows_dark_titlebar_gone(widget, dark):"),
    ("the helper kept but no longer called",
     "browser.py", "                _windows_dark_titlebar(widget, dark)",
     "                pass  # no longer calls it"),
    ("the method the theme and the windows share dropped",
     "browser.py", "def restyle_window_frames(self):",
     "def restyle_window_frames_gone(self):"),
    ("the first window no longer getting its frame themed",
     "browser.py", "    if not headless:\n        win.restyle_window_frames()",
     "    if not headless:\n        pass"),
    # Windows 10 before build 19041 numbers the attribute 19, not 20.
    # Asking with only 20 there is refused and the title bar stays
    # white, silently, on exactly the older machines least likely to be
    # tested on.
    ("only the newer DWM attribute number tried",
     "browser.py", "for attribute in (20, 19):",
     "for attribute in (20,):"),
    # setColorScheme is the half that reaches Windows' own dialogs. Lose
    # it and the frame is still right while the file picker comes up
    # white, which is harder to notice and just as wrong.
    ("Qt no longer told the scheme, so its dialogs stop following",
     "browser.py", "hints.setColorScheme(Qt.ColorScheme.Dark if dark",
     "hints.setColorSchemeGone(Qt.ColorScheme.Dark if dark"),
]
for what, name, old, new in REGRESSIONS:
    if name not in FILES:
        check("a marker catches: " + what, False, "%s is not here" % name)
        continue
    if old not in FILES[name]:
        # the anchor moved; the simulation is no longer the regression it
        # claims to be, and saying so is the only honest outcome
        check("a marker catches: " + what, False,
              "anchor %r is no longer in %s" % (old[:40], name))
        continue
    broken = dict(FILES)
    broken[name] = broken[name].replace(old, new)
    caught = wp.check_markers(broken, MAN["markers"])
    check("a marker catches: " + what, bool(caught),
          caught[0][:70] if caught else "nothing failed")

# An absence marker is only as good as its pattern. check_markers
# compares the hit count against "count", so "never" is expressible as
# count 0 -- and a pattern that does not compile would raise there
# rather than fail, which reads as a broken run instead of a broken
# guard.
never = [m for m in MAN["markers"] if m.get("count") == 0]
check("the leak markers are absence assertions (count 0)",
      len(never) >= 6, len(never))
broken_rx = []
for m in MAN["markers"]:
    try:
        re.compile(wp.joined(m["pattern"]))
    except re.error as err:
        broken_rx.append("%s: %s" % (m["name"], err))
check("every marker pattern compiles", not broken_rx, broken_rx[:2])

# A needle split into fragments must still join back to the string it is
# meant to match -- the whole point is that the file does not contain it,
# so nothing else would notice if a fragment were wrong.
split = [r for r in MAN["substitutions"] if isinstance(r["find"], list)]
check("some rules spell their needle as fragments", len(split) >= 5, len(split))
for needle, what in ((HOME, "his home directory"), (LAN, "his subnet")):
    covered = [r for r in split if needle in wp.joined(r["find"])]
    check("a fragment rule still joins back to %s" % what,
          bool(covered), len(covered))

print()
if fails:
    print("FAILED (%d): %s" % (len(fails), "; ".join(fails[:6])))
else:
    print("all good")
sys.exit(1 if fails else 0)
