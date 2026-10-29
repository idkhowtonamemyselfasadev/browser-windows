#!/usr/bin/env python3
"""How the recorded port base sits against main, and why a count cannot say.

Five shapes, and the fifth is the one that was actually wrong here.

`tools/win_port.py --check` reported

    behind       nothing: this tree is level with main

for days, and it was false. It computed `rev-list --count ported_from..main`
and read 0 as health. That range is empty in two situations which have
nothing in common:

    the base IS main                     -> level, correctly
    the base is a DESCENDANT of main     -> nowhere near level

and it is empty in neither of these, which still are not a port base:

    the base and main have diverged      -> the count is real
    they share no history at all         -> the merge has no base

This tree is the second case against `~/browser` (the base is 39 commits
ahead of that repo's `main`, alive only on a dependabot branch) and the
fourth against `~/claude/browser-linux` (no common ancestor -- the
upstream history was rewritten and the base belongs to the old lineage).
Both reported as "level".

And one of those is not a problem at all, only a sha that moved:

    the base is a PRE-REWRITE TWIN   -> recoverable, not a judgement call

`git filter-branch` over a whole repository -- which is what
`~/claude/leak-scrub/scrub.sh` ran on 2026-10-27, dropping
`refs/original/*` and force-pushing -- gives every commit a new sha while
keeping its author date, its subject and its position. So a base recorded
before that rewrite reads as "no common ancestor" while its replacement
is sitting on `main`, identifiable by exactly those three things. That is
what had happened here, and `twin()` recovers it rather than asking
anybody to choose a commit.

So the classification is the thing under test here, against real git
repositories built in a scratch directory -- one per branch of
`relation()`, plus the rewrite shape, including the ones the live repos
cannot produce. A bug this quiet does not get to depend on which clone
happens to be on the machine.

Writes only inside its own temp directory, reads no repository of
anyone's, no Qt, no network.
"""
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

fails = []


def check(what, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what
          + (("  <" + str(detail) + ">") if detail != "" else ""))
    if not ok:
        fails.append(what)


spec = importlib.util.spec_from_file_location("win_port_mod",
                                              TOOLS / "win_port.py")
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("git %s failed: %s" % (" ".join(args), out.stderr))
    return out.stdout.strip()


def soft_git(repo, *args):
    """git that tolerates a non-zero exit. `merge-base --all` exits 1 when
    there is no merge base, which here is the answer, not a failure."""
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    return out.stdout.strip()


def repo(where):
    where.mkdir(parents=True, exist_ok=True)
    git(where, "init", "-q", "-b", "main", ".")
    git(where, "config", "user.email", "test@example.invalid")
    git(where, "config", "user.name", "test")
    return where


def commit(where, text):
    (where / "f").write_text(text, encoding="utf-8")
    git(where, "add", "f")
    git(where, "commit", "-qm", text)
    return git(where, "rev-parse", "HEAD")


tmp = Path(tempfile.mkdtemp(prefix="portbase-"))
try:
    print("(1) the four shapes a recorded base can have")

    # --- on: an ancestor of main, which is what a base is for ---
    r = repo(tmp / "on")
    first = commit(r, "a")
    commit(r, "b")
    check("an ancestor of main is 'on'", wp.relation(r, first) == "on",
          wp.relation(r, first))
    check("...and main itself is 'on' too",
          wp.relation(r, git(r, "rev-parse", "main")) == "on",
          wp.relation(r, git(r, "rev-parse", "main")))

    # --- ahead: a descendant. base..main is EMPTY, which is the whole bug ---
    r = repo(tmp / "ahead")
    commit(r, "a")
    git(r, "checkout", "-q", "-b", "later")
    base = commit(r, "b")
    git(r, "checkout", "-q", "main")
    check("a descendant of main is 'ahead', not 'on'",
          wp.relation(r, base) == "ahead", wp.relation(r, base))
    check("...and it is exactly the case a count calls level",
          git(r, "rev-list", "--count", "%s..main" % base) == "0",
          git(r, "rev-list", "--count", "%s..main" % base))

    # --- diverged: a common ancestor, neither contains the other ---
    r = repo(tmp / "diverged")
    commit(r, "a")
    commit(r, "b")
    git(r, "checkout", "-q", "-b", "side", "HEAD~1")
    base = commit(r, "c")
    git(r, "checkout", "-q", "main")
    check("a diverged base is 'diverged'", wp.relation(r, base) == "diverged",
          wp.relation(r, base))
    check("...and its range is NOT empty, so the counts mean something",
          git(r, "rev-list", "--count", "%s..main" % base) != "0",
          git(r, "rev-list", "--count", "%s..main" % base))

    # --- unrelated: no common ancestor at all (a rewritten history) ---
    r = repo(tmp / "unrelated")
    commit(r, "a")
    commit(r, "b")
    git(r, "checkout", "-q", "--orphan", "rewritten")
    base = commit(r, "z")
    git(r, "checkout", "-q", "main")
    check("a base on an unrelated lineage is 'unrelated'",
          wp.relation(r, base) == "unrelated", wp.relation(r, base))
    check("...and git finds no merge base for it",
          soft_git(r, "merge-base", "--all", "main", base) == "",
          soft_git(r, "merge-base", "--all", "main", base) or "(none)")

    # --- the fifth shape: a pre-rewrite twin. Looks exactly like
    # 'unrelated' and is completely benign, because the base is not lost
    # -- a filter-branch keeps every commit's author date, subject and
    # position and only changes its sha. This is the shape a force-push
    # produces, and the one this tree was actually in.
    r = repo(tmp / "rewritten")
    (r / "f").write_text("secret 203.0.113.9\n", encoding="utf-8")
    git(r, "add", "f")
    git(r, "commit", "-qm", "the commit that gets rewritten")
    pre = git(r, "rev-parse", "HEAD")
    # the rewrite: same author date, same subject, scrubbed content, new
    # sha, and the old lineage left on another ref the way scrub.sh does
    adate = git(r, "log", "-1", "--format=%aI", pre)
    git(r, "checkout", "-q", "--orphan", "scrubbed")
    (r / "f").write_text("secret 198.51.100.9\n", encoding="utf-8")
    git(r, "add", "f")
    git(r, "-c", "user.name=test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "the commit that gets rewritten",
        "--date", adate)
    post = git(r, "rev-parse", "HEAD")
    git(r, "branch", "-f", "main", post)
    git(r, "checkout", "-q", "main")
    git(r, "branch", "-f", "abandoned", pre)

    check("the twin really is a different commit", pre != post,
          "%s vs %s" % (pre[:9], post[:9]))
    check("...with the same author date",
          git(r, "log", "-1", "--format=%aI", pre)
          == git(r, "log", "-1", "--format=%aI", post), adate)
    check("...and a different tree",
          git(r, "log", "-1", "--format=%T", pre)
          != git(r, "log", "-1", "--format=%T", post))
    check("the pre-rewrite base classifies as 'unrelated'",
          wp.relation(r, pre) == "unrelated", wp.relation(r, pre))
    got = wp.twin(r, pre)
    check("...but twin() recovers its replacement", bool(got), got)
    if got:
        check("...and names the right commit", got[0] == post,
              "%s, wanted %s" % (got[0][:9], post[:9]))
        check("...with the file count between them", got[1] == 1, got[1])
        check("...and the branch it found it on", got[2] == "main", got[2])
    # the shape must not fire on a base that is merely old: same lineage,
    # so there is no twin to find and suggesting one would be noise
    r2 = tmp / "on"
    check("twin() finds nothing for a healthy base",
          wp.twin(r2, git(r2, "rev-parse", "main~1")) is None,
          wp.twin(r2, git(r2, "rev-parse", "main~1")))

    print()
    print("(2) the report says which one it is, and never 'level' wrongly")
    # drift() reads the manifest for the repo and the base, so each shape
    # is handed to it through the same override a real run would use.
    shapes = [
        ("ahead", "DESCENDANT", tmp / "ahead", "later"),
        ("diverged", "DIVERGED", tmp / "diverged", "side"),
        ("unrelated", "shares NO history", tmp / "unrelated", "rewritten"),
        ("rewritten", "PRE-REWRITE twin", tmp / "rewritten", "abandoned"),
    ]
    for shape, word, where, branch in shapes:
        lines = wp.drift({"linux_repo": str(where),
                          "ported_from": git(where, "rev-parse", branch)})
        text = "\n".join(lines)
        check("the %s case is named as such" % shape, word in text,
              lines[1:2])
        # the one place the phrase may appear is the sentence explaining
        # that it used to appear; anywhere else is the old bug back
        stray = [l for l in lines
                 if "level with main" in l and "used to read" not in l]
        check("...and the %s case never claims 'level with main'" % shape,
              not stray, stray)

    # the healthy shape still reports plainly
    r = tmp / "on"
    lines = wp.drift({"linux_repo": str(r),
                      "ported_from": git(r, "rev-parse", "main")})
    check("a base that IS main still reads as level",
          any("level with main" in l for l in lines), lines[1:2])
    lines = wp.drift({"linux_repo": str(r),
                      "ported_from": git(r, "rev-parse", "main~1")})
    check("a base one commit behind main reads as 1 commit behind",
          any("1 commit(s) of main" in l for l in lines), lines[1:2])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

check("the scratch repositories are gone again", not tmp.exists(), tmp)

print()
if fails:
    print("FAILED (%d): %s" % (len(fails), "; ".join(fails[:6])))
else:
    print("all good")
sys.exit(1 if fails else 0)
