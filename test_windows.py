#!/usr/bin/env python3
"""The regions that exist only in this edition.

Every other suite here is the Linux one, run against this browser.py:
they cover the shared code, which is nearly all of it. What they cannot
cover is the handful of Windows-only regions listed in
tools/win_port.json, because those are the parts that do not run on the
machine this is built on — and those are exactly the parts a bad port
breaks, because they are the parts nobody upstream is testing.

So this goes at them the only ways Linux allows:

  * take the statements that build DATA_DIR and the five data files
    straight out of browser.py and run those, with a sys.platform and an
    environment of our choosing. Faking sys.platform and importing does
    not work — the standard library reads it too, and shutil goes
    looking for _winapi — but the region is self-contained, so it can be
    run on its own. It is the real code from the real file;
  * call the win32 helpers directly, with the things they shell out to
    replaced or absent;
  * drive the zip updater with urlopen replaced, so its decisions and
    its unpacking are exercised with no network and nothing downloaded.

Never against real data: APP_DIR, the config and every data file are
redirected into a throwaway directory, and the updater is never allowed
to write into the repository.

KNOWN GAP, deliberately not covered here: the unpacking loop in
Bridge._zip_update joins an entry name from the downloaded zip onto
APP_DIR without checking the result stays inside APP_DIR, so an archive
containing "repo-main/../../x" would be written outside the folder.
Reaching it means controlling the GitHub repository or breaking TLS to
codeload.github.com, so it is not a hole anyone can walk through from
outside — but it is not checked, and a test that asserted it was safe
would be asserting something untrue. Flagged rather than papered over.
"""

import io
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
HERE = Path(__file__).resolve().parent
SCRATCH = Path(tempfile.mkdtemp(prefix="winregions-"))
os.environ["XDG_DATA_HOME"] = str(SCRATCH / "share")
os.environ["XDG_CONFIG_HOME"] = str(SCRATCH / "config")
os.environ["XDG_CACHE_HOME"] = str(SCRATCH / "cache")
sys.path.insert(0, str(HERE))

fails = []


def src_of_browser():
    return SRC


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name
          + (("  " + str(detail)) if detail and not cond else ""))
    if not cond:
        fails.append(name)


# --- the constants, as Windows would build them ----------------------
# browser.py decides DATA_DIR at import time from sys.platform. Faking
# sys.platform and importing the module does not work — the standard
# library reads it too, and shutil goes looking for _winapi — so take
# the statements that build these six names straight out of the source
# and run those, with a sys and an os of our choosing. It is the real
# code from the real file, and it is the whole of that region.
import ast  # noqa: E402

WANTED = {"DATA_DIR", "CONFIG_FILE", "HOSTS_FILE", "HISTORY_FILE",
          "DOWNLOADS_FILE", "BOOKMARKS_FILE"}
SRC = (HERE / "browser.py").read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def assigns(node):
    """The names a top-level statement binds, looking inside an if."""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


REGION = [n for n in TREE.body if assigns(n) & WANTED]


class FakeSys:
    pass


def build(platform, environ):
    fake_sys = FakeSys()
    fake_sys.platform = platform
    fake_os = FakeSys()
    fake_os.environ = environ
    ns = {"sys": fake_sys, "os": fake_os, "Path": Path}
    exec(compile(ast.Module(body=REGION, type_ignores=[]),
                 "<data-dir region>", "exec"), ns)
    return {k: str(ns[k]) for k in WANTED}


print("\nwhere this edition keeps its data")
check("the region that builds them was found in browser.py, all of it",
      len(REGION) >= 2 and WANTED <= set().union(*(assigns(n) for n in REGION)),
      [ast.dump(n)[:60] for n in REGION])

appdata = str(SCRATCH / "AppData" / "Local")
got = build("win32", {"LOCALAPPDATA": appdata})
want = str(Path(appdata) / "browser")
check("DATA_DIR is %LOCALAPPDATA%\\browser", got["DATA_DIR"] == want,
      got["DATA_DIR"])
for key in ("CONFIG", "HISTORY", "DOWNLOADS", "HOSTS", "BOOKMARKS"):
    name = key + "_FILE"
    check("%s.json sits under it" % key.lower(),
          got[name] == str(Path(want) / (key.lower() + ".json")), got[name])
check("nothing landed in a POSIX share directory",
      not any(".local/share" in v for v in got.values()), got)

no_appdata = build("win32", {})
check("with no %LOCALAPPDATA% it falls back to the home directory, "
      "not to a POSIX path",
      no_appdata["DATA_DIR"] == str(Path.home() / "browser"),
      no_appdata["DATA_DIR"])

posix = build("linux", {})
check("and on Linux the very same code gives the POSIX path",
      posix["DATA_DIR"] == str(Path.home() / ".local/share/browser"),
      posix["DATA_DIR"])

# and the Linux reading of the same file is still the Linux one, so a
# developer running this on Linux is unaffected by the branch
import browser as B  # noqa: E402

# whatever the developer's own config is, it must be exactly as it was
# when this suite finishes
REAL_CONFIG = B.CONFIG_FILE
REAL_CONFIG_MTIME = (REAL_CONFIG.stat().st_mtime
                     if REAL_CONFIG.exists() else None)

check("imported normally, DATA_DIR is the POSIX one",
      str(B.DATA_DIR) == str(Path.home() / ".local/share/browser"),
      str(B.DATA_DIR))

# --- the ACL helper --------------------------------------------------
print("\nmaking a file owner-only where there is no chmod to do it")
target = SCRATCH / "vault" / "passwords.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(b"secret")

calls = []
real_run = subprocess.run


def spy(cmd, **kw):
    calls.append((cmd, kw))
    raise FileNotFoundError("icacls")     # what Linux does, and FAT32 too


B.subprocess.run = spy
try:
    os.environ["USERNAME"] = "user"
    B._restrict_to_owner(target)
    check("a missing icacls is survived rather than raised", True)
    check("it asked icacls to drop inheritance and grant this user only",
          calls and calls[0][0][:2] == ["icacls", str(target)]
          and "/inheritance:r" in calls[0][0]
          and "user:F" in calls[0][0], calls)
    check("and never lets a non-zero exit throw either",
          calls and calls[0][1].get("check") is False, calls)
    check("with a timeout, so a hung icacls cannot wedge a save",
          calls and calls[0][1].get("timeout"), calls)

    calls.clear()
    os.environ["USERNAME"] = "   "
    B._restrict_to_owner(target)
    check("with no USERNAME it does nothing at all rather than guessing",
          calls == [], calls)
except Exception as exc:                                  # noqa: BLE001
    check("the ACL helper never raises", False, repr(exc))
finally:
    B.subprocess.run = real_run

check("the file is still there and still readable by us",
      target.read_bytes() == b"secret")

# --- which branch _write_private takes -------------------------------
print("\nthe write that is supposed to be private")
p = SCRATCH / "private" / "k.bin"
B._write_private(p, b"key material")
check("on this platform it is written 0600",
      stat.S_IMODE(p.stat().st_mode) == 0o600,
      oct(stat.S_IMODE(p.stat().st_mode)))
check("and the content is what was asked for", p.read_bytes() == b"key material")

seen = []
real_restrict, real_platform = B._restrict_to_owner, B.sys.platform
B._restrict_to_owner = lambda path: seen.append(path)
B.sys.platform = "win32"
try:
    q = SCRATCH / "private" / "w.bin"
    B._write_private(q, b"key material")
    check("told it is Windows, it asks for an ACL instead of a chmod",
          seen == [q], seen)
    check("and the file was still written", q.read_bytes() == b"key material")
finally:
    B._restrict_to_owner, B.sys.platform = real_restrict, real_platform

# --- the zip updater -------------------------------------------------
print("\nthe updater for a copy that was unzipped, not cloned")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeBrowser:
    def __init__(self, cfg):
        self.config = cfg
        self.saved = 0

    def save_config(self):
        self.saved += 1


class FakeSignal:
    def __init__(self):
        self.sent = []

    def emit(self, msg):
        self.sent.append(msg)


class FakeBridge:
    def __init__(self, cfg):
        self.browser = FakeBrowser(cfg)
        self._updating = True
        self.updateFinished = FakeSignal()


def run_update(cfg, responses, app_dir):
    """Drive Bridge._zip_update with the network replaced. Nothing is
    downloaded and APP_DIR points into scratch, so the only thing that
    can be written over is a directory this test made."""
    bridge = FakeBridge(cfg)
    queue = list(responses)

    def fake_urlopen(url, timeout=None):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    real_open, real_app = B.urllib.request.urlopen, B.APP_DIR
    B.urllib.request.urlopen = fake_urlopen
    B.APP_DIR = app_dir
    try:
        B.Bridge._zip_update(bridge)
    finally:
        B.urllib.request.urlopen, B.APP_DIR = real_open, real_app
    return bridge


def make_zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in entries:
            z.writestr(name, body)
    return buf.getvalue()


# already current
dest = SCRATCH / "app-current"
dest.mkdir()
(dest / "browser.py").write_bytes(b"old")
b1 = run_update({"updateSha": "abc123"}, [b'{"sha": "abc123"}'], dest)
check("a sha it already has means nothing is downloaded",
      b1.updateFinished.sent == ["You have the newest version ✓"],
      b1.updateFinished.sent)
check("and nothing on disk was touched",
      (dest / "browser.py").read_bytes() == b"old")
check("and the config was not rewritten", b1.browser.saved == 0)
check("the updater lets go afterwards", b1._updating is None)

# a genuinely newer one
dest = SCRATCH / "app-new"
dest.mkdir()
(dest / "browser.py").write_bytes(b"old")
zipped = make_zip([
    ("browser-windows-main/", b""),
    ("browser-windows-main/browser.py", b"new code"),
    ("browser-windows-main/tools/win_port.py", b"tool"),
    ("browser-windows-main", b""),          # the root entry itself
])
cfg = {"updateSha": "old-sha"}
b2 = run_update(cfg, [b'{"sha": "new-sha"}', zipped], dest)
check("a new sha unpacks the tree it downloaded",
      b2.updateFinished.sent == ["Updated! Restart the browser to finish."],
      b2.updateFinished.sent)
check("the file was replaced", (dest / "browser.py").read_bytes() == b"new code")
check("a nested file arrived, directory and all",
      (dest / "tools" / "win_port.py").read_bytes() == b"tool")
check("GitHub's top-level directory is stripped rather than nested",
      not (dest / "browser-windows-main").exists())
check("the new sha is recorded, which is the only record of the version",
      cfg["updateSha"] == "new-sha", cfg)
check("and written out", b2.browser.saved == 1)

# the network being the network
dest = SCRATCH / "app-fail"
dest.mkdir()
(dest / "browser.py").write_bytes(b"old")
b3 = run_update({"updateSha": "x"}, [OSError("no route to host")], dest)
check("a failed update says so rather than throwing on a worker thread",
      len(b3.updateFinished.sent) == 1
      and b3.updateFinished.sent[0].startswith("Update failed:"),
      b3.updateFinished.sent)
check("it leaves the folder alone when it fails",
      (dest / "browser.py").read_bytes() == b"old")
check("and lets go, so a second attempt is possible", b3._updating is None)

# --- the update check that runs at startup ---------------------------
print("\nthe quiet check at startup")
emitted = []


class FakeWin:
    config = {"updateSha": "have-this"}

    class updateAvailable:
        @staticmethod
        def emit():
            emitted.append(True)


def run_check(payload, cfg):
    FakeWin.config = cfg
    del emitted[:]

    def fake_urlopen(url, timeout=None):
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(payload)

    real = B.urllib.request.urlopen
    B.urllib.request.urlopen = fake_urlopen
    try:
        B.Browser._check_zip_update(FakeWin)
    finally:
        B.urllib.request.urlopen = real
    return list(emitted)


check("a newer sha raises the flag for the window to see",
      run_check(b'{"sha": "newer"}', {"updateSha": "have-this"}) == [True])
check("the one we already have says nothing",
      run_check(b'{"sha": "have-this"}', {"updateSha": "have-this"}) == [])
check("and a network error says nothing rather than taking the thread down",
      run_check(OSError("offline"), {"updateSha": "have-this"}) == [])
check("it goes through a signal, because a worker thread cannot touch "
      "a widget",
      "updateAvailable = pyqtSignal()" in src_of_browser(),
      "not declared as a signal on Browser")
check("and the window connects that signal to the toast",
      "self.updateAvailable.connect(self._show_toast)" in src_of_browser())

# --- the taskbar identity and the icon -------------------------------
print("\nthe things that only main() does on Windows")
src = SRC
check("the taskbar is told which application this is, "
      "or it groups the window under python.exe",
      "SetCurrentProcessExplicitAppUserModelID" in src)
check("and that call is guarded by a platform check, "
      "so importing on Linux cannot reach it",
      'if sys.platform == "win32":\n        # without this the taskbar'
      in src)
check("the window icon is the .ico on Windows and the .svg elsewhere",
      'icon = "icon.ico" if sys.platform == "win32" else "icon.svg"' in src)
check("and the .ico is actually shipped", (HERE / "icon.ico").is_file())

print("\nnothing anywhere near real data")
check("every file this suite wrote is inside its own scratch directory",
      all(Path(p).is_relative_to(SCRATCH)
          for p in (target, p, q, dest / "browser.py")),
      [str(target), str(p), str(q)])
check("the real config is exactly as this suite found it",
      (REAL_CONFIG.stat().st_mtime if REAL_CONFIG.exists() else None)
      == REAL_CONFIG_MTIME, str(REAL_CONFIG))
check("APP_DIR was put back after the updater borrowed it",
      B.APP_DIR == HERE, B.APP_DIR)
check("and the repository's own browser.py is untouched",
      (HERE / "browser.py").read_text(encoding="utf-8") == SRC)

print("\n%d checks failed" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
