#!/usr/bin/env python3
"""Regenerate the Windows edition from the Linux one.

The Windows browser is not a fork. Every feature is written in ~/browser
and arrives here; the only things that are ours are the handful of
regions listed in win_port.json. Doing that by hand from memory is how a
region goes missing, so this does it instead:

  * browser.py is a three-way merge — base is the Linux commit this tree
    was last generated from (win_port.json: "ported_from"), ours is the
    checked-in Windows file, theirs is the Linux commit being ported.
    Our regions are on our side of the merge, so they survive without
    anyone having to remember them.
  * the HTML pages are copied straight across, because nothing in them is
    ours except the font stack.
  * the substitutions in win_port.json are then applied to everything,
    which is what catches a *new* Linux theme arriving with a font stack
    Windows cannot serve.
  * finally every marker in win_port.json must still be true, or this
    refuses to finish and leaves nothing half-written.

Usage:
    tools/win_port.py --to <linux-commit>      # generate
    tools/win_port.py --to <commit> --dry-run  # report, write nothing
    tools/win_port.py --check                  # verify the tree as it is

--check looks at this tree only: the markers hold and every .py parses.
That is not a parity check, and it used to read like one -- a tree forty
commits behind Linux passes it cleanly, because nothing in it compares
anything against the Linux repo. It now also reports how far behind the
tree is, which is the question somebody running --check actually has.

Nothing is written until every file has been generated and every marker
has passed, so a failed port leaves the working tree untouched.
"""

import argparse
import ast
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = HERE / "win_port.json"

#: The branch a port and a drift report measure against.
#:
#: This was `main`, and `main` is the wrong answer: it is a local branch
#: nobody fetches, so in a checkout left behind by a force-push it can
#: be a hundred commits stale while origin/main is current. Not
#: hypothetical -- the five suites this edition had to adopt by hand
#: (win_port.json: adopted_pending) were in the port base the whole
#: time, and `--to main` could not see them, because the linux_repo's
#: local main is 88 commits behind its own origin/main. The report
#: below has described that state as "stale main" for a while and told
#: whoever read it to pass `--to origin/main` by hand. A warning that
#: is right and that nobody has to act on is not the same as being
#: right by default.
UPSTREAM = "origin/main"


class PortError(Exception):
    pass


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise PortError("git %s failed in %s:\n%s"
                        % (" ".join(args), repo, out.stderr.strip()))
    return out.stdout


def show(repo, rev, path):
    """A file as of a commit. Returns None if it did not exist then."""
    out = subprocess.run(["git", "-C", str(repo), "show", "%s:%s" % (rev, path)],
                         capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout


#: His login name, taken from the account this runs under rather than
#: written down. {USER} and {User} in a manifest rule expand to it.
#:
#: The fragment trick below was not enough. A rule could say
#: ["/home/", "<login>"] and defeat a pattern looking for the PATH --
#: but the second fragment is still the name in clear text, and on
#: 2026-10-29 gitguard grew a rule for the bare name, which is the
#: right rule. Thirteen files in this edition carried it, five of them
#: this manifest. A placeholder carries no name at all, and it is also
#: simply more correct: the suites then describe whoever runs them.
#: Read off the account, NOT Path.home().name: everything here runs
#: with HOME pointed at a throwaway directory, so that would be the
#: scratch folder's name. See tests/test_leakguard.py, where exactly
#: that reported a leak that was its own test data.
try:
    import pwd
    USER_NAME = pwd.getpwuid(os.getuid()).pw_name
except Exception:                                   # noqa: BLE001
    import getpass
    USER_NAME = getpass.getuser()


def expand(text):
    """{USER} and {User} filled in, so no rule has to spell the name."""
    return (text.replace("{USER}", USER_NAME)
                .replace("{User}", USER_NAME.capitalize()))


def joined(value):
    """A manifest string, which may be written as a list of fragments.

    A guard has to name the thing it forbids, and the things forbidden
    here are his home directory, the subnet his machines sit on, his
    mail handle and his own name. Written out, this file would be the
    leak it exists to prevent -- and gitguard refuses the commit,
    correctly. So a rule may spell its needle as ["/home/", "{USER}"]:
    the pieces are concatenated exactly, and only {USER} / {User} are
    interpreted, by expand() above.
    """
    if isinstance(value, list):
        value = "".join(value)
    return expand(value)


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def linux_repo(manifest):
    """The Linux checkout a port reads, as a path.

    WIN_PORT_LINUX_REPO points the port at another checkout for one
    run. The manifest is committed and public, so it names ~/browser; a
    second clone is a reason to override it, not a reason to edit it.

    `~` is resolved against the ACCOUNT, not $HOME. Every suite in this
    edition runs with HOME set to a throwaway directory -- that is the
    house rule, because DATA_DIR follows HOME on this platform -- and
    Path.expanduser() reads $HOME, so under the suite `~/browser`
    resolved inside the scratch dir. --check then reported "is not
    here, so drift is unknown" and exited 0: the drift half of the
    check never ran in the one environment where it always runs, and
    said so in a line nobody reads twice.
    """
    override = os.environ.get("WIN_PORT_LINUX_REPO")
    if override:
        return Path(override)
    raw = str(manifest["linux_repo"])
    if raw.startswith("~"):
        try:
            import pwd
            home = pwd.getpwuid(os.getuid()).pw_dir
        except Exception:                               # noqa: BLE001
            home = os.path.expanduser("~")
        return Path(home + raw[1:])
    return Path(raw)


def names(seq):
    """The file lists carry inline commentary — entries starting with a
    '#' are prose, not paths. JSON has no comments, and a list of a
    hundred file names with no explanation is how the next person
    guesses wrong.

    It was an underscore until a port went looking for why the Windows
    _boot.py was two months behind the Linux one: it is listed, and the
    rule that made the prose work quietly made that one entry prose
    too. A '#' cannot be the first character of a file in this tree."""
    return [n for n in seq if not n.startswith("#")]


def apply_substitutions(files, rules):
    """Returns (files, per-rule hit counts). Idempotent by construction:
    each replacement no longer matches its own pattern."""
    counts = []
    for rule in rules:
        hits = 0
        for name, text in files.items():
            if not matches(name, rule["files"]):
                continue
            find, repl = joined(rule["find"]), joined(rule["replace"])
            n = text.count(find)
            if n:
                files[name] = text.replace(find, repl)
                hits += n
        counts.append(hits)
    return files, counts


def check_markers(files, markers):
    """Every marker must hold. Returns a list of failure strings."""
    bad = []
    for m in markers:
        targets = [n for n in files if matches(n, [m["file"]])]
        if not targets:
            bad.append("%s: no file matches %r" % (m["name"], m["file"]))
            continue
        rx = re.compile(joined(m["pattern"]), re.MULTILINE)
        total = sum(len(rx.findall(files[n])) for n in targets)
        want = m.get("count")
        if want is not None and total != want:
            bad.append("%s (%s): found %d, expected %d"
                       % (m["name"], m["file"], total, want))
        elif want is None and total < m.get("min", 1):
            bad.append("%s (%s): found %d, expected at least %d"
                       % (m["name"], m["file"], total, m.get("min", 1)))
    return bad


def three_way(base, ours, theirs, label):
    """git merge-file on three blobs. Raises if it conflicts — a conflict
    means Linux edited a line one of our regions sits on, and that is a
    decision for a person, not for this script."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ours").write_bytes(ours)
        (tmp / "base").write_bytes(base)
        (tmp / "theirs").write_bytes(theirs)
        out = subprocess.run(
            ["git", "merge-file", "--diff3",
             "-L", "windows", "-L", "base (linux)", "-L", "linux",
             str(tmp / "ours"), str(tmp / "base"), str(tmp / "theirs")],
            capture_output=True, text=True)
        merged = (tmp / "ours").read_bytes()
    if out.returncode < 0:
        raise PortError("merge-file died on %s: %s" % (label, out.stderr))
    if out.returncode > 0:
        raise PortError(
            "%s: %d conflict(s). Linux changed a line a Windows region sits "
            "on. Resolve it by hand in ~/browser-windows, commit, and re-run."
            % (label, out.returncode))
    return merged


def generate(manifest, to_rev, verbose=True):
    """Build the whole tree in memory. Returns {name: text}."""
    linux = linux_repo(manifest)
    base_rev = manifest["ported_from"]
    if not linux.is_dir():
        raise PortError("linux_repo %s is not there" % linux)

    base_sha = git(linux, "rev-parse", base_rev).strip()
    to_sha = git(linux, "rev-parse", to_rev).strip()
    if verbose:
        print("  linux repo   %s" % linux)
        print("  base         %s  (%s)" % (base_sha[:9], base_rev))
        print("  porting to   %s  (%s)" % (to_sha[:9], to_rev))
        n = git(linux, "rev-list", "--count",
                "%s..%s" % (base_sha, to_sha)).strip()
        print("  commits      %s" % n)
        print()

    files = {}

    for name in names(manifest["merge_files"]):
        base = show(linux, base_sha, name)
        theirs = show(linux, to_sha, name)
        if theirs is None:
            raise PortError("%s missing from the linux repo" % name)
        here = REPO / name
        if not here.exists():
            # newly listed as a merge file, or arriving for the first
            # time: there is nothing of ours to preserve yet
            files[name] = theirs.decode("utf-8")
            if verbose:
                print("  new     %-16s (nothing here to merge with)" % name)
            continue
        ours = here.read_bytes()
        if base is None:
            # it did not exist at the base commit, so there is no common
            # ancestor to merge against; ours is whatever we already have
            base = ours
        merged = three_way(base, ours, theirs, name)
        files[name] = merged.decode("utf-8")
        if verbose:
            print("  merged  %-16s %d -> %d lines"
                  % (name, ours.decode().count("\n"), files[name].count("\n")))

    copied = 0
    for name in names(manifest["copy_files"]):
        theirs = show(linux, to_sha, name)
        if theirs is None:
            raise PortError("%s missing from the linux repo" % name)
        files[name] = theirs.decode("utf-8")
        copied += 1
    if verbose:
        print("  copied  %d files" % copied)

    # A copied file is only safe to copy if the checked-in one really was
    # the Linux one plus substitutions. If somebody hand-edited it here,
    # copying would throw that away silently, so say so instead.
    drift = []
    for name in names(manifest["copy_files"]):
        was = show(linux, base_sha, name)
        if was is None:
            continue
        expect, _ = apply_substitutions(
            {name: was.decode("utf-8")}, manifest["substitutions"])
        have = (REPO / name).read_text(encoding="utf-8") if (REPO / name).exists() else None
        if have is not None and have != expect[name]:
            drift.append(name)
    if drift:
        raise PortError(
            "these were edited by hand here and copying would lose it: %s\n"
            "Move the change into ~/browser, or add it to win_port.json."
            % ", ".join(drift))

    files, counts = apply_substitutions(files, manifest["substitutions"])
    lost = exclusive_kept(files)
    if lost:
        raise PortError(
            "the port would delete content only this edition has:\n  - "
            + "\n  - ".join(lost)
            + "\nA substitution can put a line back; it cannot put a block "
              "back.\nMove the feature upstream, or list the page out of "
              "copy_files.")
    if verbose:
        print()
        for rule, hit in zip(manifest["substitutions"], counts):
            print("  subst   %-4d %s" % (hit, joined(rule["find"])[:58]))
    for rule, hit in zip(manifest["substitutions"], counts):
        if hit < rule.get("min", 1):
            raise PortError(
                "substitution %r matched %d time(s), expected at least %d.\n"
                "Linux probably renamed it — update win_port.json."
                % (joined(rule["find"]), hit, rule.get("min", 1)))

    return files, to_sha


def soft(repo, *args):
    """git that answers None instead of raising. The drift report has to
    be able to say "the Linux repo is not here" without failing a check
    that is otherwise about this tree alone."""
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else None


def upstream_of(repo, want=UPSTREAM):
    """The ref to measure against in this repo, or the local branch when
    there is no remote one.

    A checkout with no origin has no origin/main, and answering
    "unknown" there would throw away an answer `main` can give
    perfectly well.
    """
    if soft(repo, "rev-parse", "--verify", "--quiet", want) is not None:
        return want
    return "main"


def ancestor_of(repo, rev, branch=None):
    """Is this commit actually on that branch's line of history?

    Asked separately from "how far behind", because a count of zero
    answers both "the base is the branch tip" and "the base is nowhere
    near it" with the same number. git merge-base --is-ancestor is the
    only one of the two that distinguishes them.

    branch defaults to whatever upstream_of makes of THIS repo, not to
    the UPSTREAM literal: a repo with no remote would otherwise be
    measured against a ref it does not have, and every answer would
    come back "unrelated" -- which is what the first cut of this did to
    test_portbase's synthetic repos.
    """
    branch = branch or upstream_of(repo)
    out = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", rev, branch],
        capture_output=True, text=True)
    return out.returncode == 0


def twin(repo, base, branch=None):
    """The post-rewrite twin of a base, if that is what happened to it.

    A history rewrite -- `git filter-branch` over the whole repo, then
    `refs/original/*` dropped and the result force-pushed, which is what
    ~/claude/leak-scrub/scrub.sh does -- gives every commit a new sha
    while keeping its author date, its subject and its position. So the
    base recorded before the rewrite is not gone and is not a judgement
    call: its replacement is the commit on <branch> with the SAME author
    date and the SAME subject and a DIFFERENT tree.

    That is the one shape which looks exactly like "unrelated" (no
    common ancestor, two lineages) while being completely benign, and
    the one a future force-push will produce again. Returns
    (sha, files_changed, branch) or None, and never guesses: an author
    date is
    recorded to the second and a subject is free text, so the pair is
    specific enough to name a candidate and this reports it as a
    candidate rather than acting on it.
    """
    want = soft(repo, "log", "-1", "--format=%aI%x00%s%x00%T", base)
    if not want or "\0" not in want:
        return None
    adate, subject, tree = want.split("\0", 2)
    branch = branch or upstream_of(repo)
    rows = soft(repo, "log", branch, "--format=%H%x00%aI%x00%s%x00%T")
    if not rows:
        return None
    for row in rows.splitlines():
        parts = row.split("\0", 3)
        if len(parts) != 4:
            continue
        sha, their_adate, their_subject, their_tree = parts
        if their_adate == adate and their_subject == subject \
                and their_tree != tree:
            stat = soft(repo, "diff", "--numstat", base, sha)
            files = len([l for l in stat.splitlines() if l.strip()]) \
                if stat else 0
            return sha, files, branch
    return None


def relation(repo, base, branch=None):
    """How the recorded base sits against a branch, as one of four words.

    "on"        an ancestor of main, which is what a base is supposed to
                be: ported_from..main is then the work to port.
    "ahead"     a descendant of main. ported_from..main is empty, and
                reading that as "level with main" is the bug this
                replaced -- the tree was generated from something main
                was never fast-forwarded to.
    "diverged"  a common ancestor exists but neither contains the other.
                The counts still mean something, so this is reportable
                rather than fatal.
    "unrelated" no common ancestor at all. Nothing here is a base of
                anything, and a three-way merge against it is guesswork.
    """
    branch = branch or upstream_of(repo)
    if ancestor_of(repo, base, branch):
        return "on"
    if soft(repo, "rev-list", "--count",
            "%s..%s" % (base, branch)) == "0":
        return "ahead"
    shared = soft(repo, "merge-base", branch, base)
    return "diverged" if shared else "unrelated"


#: browser-pages' shared config, which is the only record of what a
#: page holds that upstream does not. Overridable for a test; `~` is
#: resolved off the account for the same reason linux_repo() does it.
PAGES_JSON = "~/claude/browser-pages/pages.json"


def _pages_config():
    """browser-pages' pages.json, or None if it is not beside us."""
    raw = os.environ.get("WIN_PORT_PAGES_JSON") or PAGES_JSON
    if raw.startswith("~"):
        try:
            import pwd
            raw = pwd.getpwuid(os.getuid()).pw_dir + raw[1:]
        except Exception:                               # noqa: BLE001
            raw = os.path.expanduser(raw)
    path = Path(raw)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def exclusive_kept(files, edition="windows"):
    """Whether the generated pages still hold what only this edition has.

    THE HAZARD: all nine shared pages are in copy_files, so a port
    replaces each one wholesale with upstream's. The substitutions put
    the font stacks and the Windows paths back -- a find-and-replace
    can restore a LINE. It cannot restore a BLOCK that upstream never
    had, so anything this edition owns outright would go silently, and
    the next commit would carry the deletion.

    pages.py already refuses to `port` a page with exclusive content,
    and `pages.py check <edition>` already reports EXCLUSIVE GONE. So
    the detection exists; what was missing is this tool consulting it.
    browser-mac's porter forked the same operation without the guard
    and nearly took mictest.html's call panel out today -- and
    mictest.html is in this manifest's copy_files too.

    Checked BEFORE anything is written, against the text in memory,
    because a check that runs afterwards reports a loss it has already
    caused. Returns a list of problems, empty if clean.

    No pages.json beside us (a clone without browser-pages) is reported
    as a check that could not run, never as a pass.
    """
    cfg = _pages_config()
    if cfg is None:
        return ["pages.json is not beside this checkout, so nothing "
                "verified that the pages still hold what only this "
                "edition has. NOT a pass."]
    mine = (cfg.get("exclusive") or {}).get(edition) or {}
    bad = []
    for page, items in mine.items():
        if page not in files:
            continue            # not ported here, so not at risk here
        for item in items:
            if item["marker"] not in files[page]:
                bad.append("%s would lose %s (marker %r)"
                           % (page, item.get("what", "exclusive content"),
                              item["marker"][:60]))
    return bad


def unlisted_upstream(manifest, rev):
    """Upstream suites this manifest has never classified.

    tests/test_workflow.py checks that every suite ON DISK is in one of
    the lists. That is the easy direction, and it is not the one that
    rots: a suite upstream ADDS is in no list at all, and a file in no
    list reads exactly like a file that is handled. Twelve had
    collected by 2026-11-02 -- test_tmpscratch.py and test_barsuggest.py
    among them, both written for fixes this edition was checking by
    hand at the time, because it did not know the suites existed.

    The same shape as the suite list that stopped at twenty while the
    Linux one grew to eighty-seven. That was fixed by having runall.sh
    read the folder instead of a list, which made every suite PRESENT
    run -- and said nothing about the ones that never arrived.

    Returns the names, sorted, or []. Never raises: --check reports
    what a port refuses.
    """
    linux = linux_repo(manifest)
    if not linux.is_dir():
        return []
    listed = soft(linux, "ls-tree", "-r", "--name-only", rev)
    if listed is None:
        return []
    known = set(names(manifest["merge_files"] + manifest["copy_files"]))
    known |= set(names(manifest.get("win_only_files") or []))
    known |= set(manifest.get("adopted_pending") or {})
    skip = tuple(names(manifest.get("linux_only_files") or []))
    out = []
    for name in listed.splitlines():
        base = name.rsplit("/", 1)[-1]
        if not (base.startswith("test_") and base.endswith(".py")):
            continue
        if name in known or (skip and name.startswith(skip)):
            continue
        out.append(name)
    return sorted(out)


def drift(manifest):
    """How far this tree is behind the Linux repo it comes from.

    The markers say our regions are intact; they say nothing about the
    edition being current, and those are different questions. Returns
    the lines to print -- it never raises, because being unable to find
    the Linux repo is a thing to report, not a reason to fail.
    """
    linux = linux_repo(manifest)        # the same one generate() reads
    base = manifest["ported_from"]
    if not linux.is_dir():
        return ["  linux repo   %s is not here, so drift is unknown" % linux]
    head = soft(linux, "rev-parse", "--short", "HEAD")
    if head is None:
        return ["  linux repo   %s is not a git repo, so drift is unknown"
                % linux]
    branch = soft(linux, "rev-parse", "--abbrev-ref", "HEAD")
    ref = upstream_of(linux)
    out = ["  linux repo   %s  (HEAD %s%s)"
           % (linux, head, " on " + branch if branch else ""),
           "  measured vs  %s" % ref]
    # The branch that used to be the default, when it is not the ref we
    # measured against: the state that produced adopted_pending, said
    # out loud rather than left to be discovered.
    # BOTH directions, and in the right one: `A..B` counts what B has
    # and A lacks, so main's own commits are `ref..main`. The first cut
    # of this printed that count under the word "behind", which is the
    # same kind of mislabelled diagnostic this whole change is about.
    lagging = soft(linux, "rev-list", "--count",
                   "main..%s" % ref) if ref != "main" else None
    leading = soft(linux, "rev-list", "--count",
                   "%s..main" % ref) if ref != "main" else None
    if (lagging and lagging != "0") or (leading and leading != "0"):
        out.append("  note         this repo's local main is %s behind and "
                   "%s ahead of %s" % (lagging or "?", leading or "?", ref))
        out.append("               a port reads %s, so that does not "
                   "affect it" % ref)
    if soft(linux, "cat-file", "-t", base) != "commit":
        out.append("  behind       unknown: ported_from %s is not a commit "
                   "in that repo" % base[:9])
        return out
    behind = soft(linux, "rev-list", "--count", "%s..%s" % (base, ref))
    if behind is None:
        out.append("  behind       unknown: no %s in that repo" % ref)
    elif (how := relation(linux, base)) != "on":
        # "ported_from..main" being empty says nothing on its own: it is
        # equally true of a base that IS main and of one that is nowhere
        # near main. Counting alone cannot tell those apart, so this used
        # to print "level with main" for a base that was never on main.
        # The same lie d7ee8a1 took off the marker side, arriving the
        # second time through the base pointer.
        ahead = soft(linux, "rev-list", "--count",
                     "%s..%s" % (ref, base)) or "?"
        if how == "ahead":
            out.append("  behind       UNKNOWN: ported_from %s is a "
                       "DESCENDANT of %s, not an ancestor" % (base[:9], ref))
            out.append("               %s is %s commit(s) behind it, so "
                       "ported_from..%s is empty" % (ref, ahead, ref))
            out.append("               and this line used to read \"level "
                       "with main\". Nothing is level.")
        elif how == "unrelated":
            out.append("  behind       UNKNOWN: ported_from %s shares NO "
                       "history with %s here" % (base[:9], ref))
            out.append("               no common ancestor at all: %s has "
                       "%s commit(s) it lacks, it has %s that %s lacks"
                       % (ref, behind, ahead, ref))
            out.append("               a three-way merge against that base "
                       "is guesswork, not a port")
        else:
            out.append("  behind       DIVERGED: %s has %s commit(s) "
                       "ported_from lacks," % (ref, behind))
            out.append("               and ported_from has %s that %s "
                       "lacks. The count is real, but a port"
                       % (ahead, ref))
            out.append("               carries %s's side only." % ref)
            out.append("               see them: tools/win_port.py --to "
                       "%s --dry-run" % ref)
        where = soft(linux, "branch", "-a", "--contains", base)
        if where:
            first = where.splitlines()[0].strip().lstrip("* ").strip()
            out.append("               %s lives on %s" % (base[:9], first))
        # Two things worth saying before "re-point it", because both make
        # the base recoverable rather than a judgement call.
        #
        # A local main left behind by a force-push: the base is fine and
        # the branch being measured against is the stale one. That is the
        # state of ~/browser, whose main shares no history with its own
        # origin/main.
        if ref != "main" and relation(linux, base, "main") == "on":
            short = soft(linux, "rev-list", "--count",
                         "%s..main" % base) or "?"
            out.append("  stale ref    the base IS on this repo's local main "
                       "(%s commit(s) behind it)," % short)
            out.append("               but not on %s. One of the two "
                       "branches is the one left behind;" % ref)
            out.append("               check which before pointing "
                       "ported_from anywhere.")
        else:
            # A rewrite: the base's replacement is findable, not
            # guessable. Tried on origin/main too, because a clone whose
            # local main was left behind by the force-push has the
            # rewritten lineage only on the remote-tracking branch.
            got = twin(linux, base) or twin(linux, base, "main")
            if got:
                sha, nfiles, found_on = got
                out.append("  rewritten    %s looks like the PRE-REWRITE "
                           "twin of %s" % (base[:9], sha[:9]))
                out.append("               on %s: same author date, same "
                           "subject, different tree," % found_on)
                out.append("               %d file(s) between them. A "
                           "filter-branch does exactly that." % nfiles)
                out.append("               check it, then point ported_from "
                           "at %s" % sha[:9])
            elif how == "ahead":
                out.append("               a port --to %s would port "
                           "backwards; point ported_from at a commit "
                           "on %s" % (ref, ref))
            elif how == "unrelated":
                out.append("               point ported_from at a commit "
                           "%s can actually reach" % ref)
    elif behind == "0":
        out.append("  behind       nothing: this tree is level with %s" % ref)
    else:
        out.append("  behind       %s commit(s) of %s, ported_from is %s"
                   % (behind, ref, base[:9]))
        out.append("               see them: tools/win_port.py --to %s "
                   "--dry-run" % ref)
    # Uncommitted work in the source is invisible to a port: generate()
    # reads blobs out of commits (git show <rev>:<path>), never the
    # working tree. A feature sitting there unstaged cannot be ported at
    # all, which is worth saying out loud rather than discovering after.
    dirty = soft(linux, "status", "--porcelain")
    if dirty:
        out.append("  uncommitted  %d file(s) there, none of which a port "
                   "can see" % len(dirty.splitlines()))
    return out


def verify(files, manifest, verbose=True):
    bad = check_markers(files, manifest["markers"])
    for name, text in files.items():
        if name.endswith(".py"):
            try:
                ast.parse(text)
            except SyntaxError as exc:
                bad.append("%s does not parse: %s" % (name, exc))
    if bad:
        raise PortError("the port dropped something:\n  - "
                        + "\n  - ".join(bad))
    if verbose:
        print("\n  %d markers pass, every .py parses" % len(manifest["markers"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--to", default=UPSTREAM,
                    help="Linux commit to port (default: %s)" % UPSTREAM)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen, write nothing")
    ap.add_argument("--check", action="store_true",
                    help="verify this tree's markers, and report how far "
                         "behind Linux it is")
    args = ap.parse_args()

    manifest = load_manifest()

    if args.check:
        files = {}
        for name in names(manifest["merge_files"] + manifest["copy_files"]):
            p = REPO / name
            if not p.exists():
                print("MISSING %s" % name, file=sys.stderr)
                return 1
            files[name] = p.read_text(encoding="utf-8")
        try:
            verify(files, manifest)
        except PortError as exc:
            print("\n%s" % exc, file=sys.stderr)
            return 1
        print("  checked: this tree's own regions, not parity with Linux")
        for line in drift(manifest):
            print(line)
        stray = unlisted_upstream(manifest, manifest["ported_from"])
        if stray:
            print("  unlisted     %d upstream suite(s) in no list: %s"
                  % (len(stray), ", ".join(stray)))
            print("               a port refuses while that is true")
        return 0

    print("Regenerating the Windows edition\n")
    # Before anything is read: a suite upstream has that no list here
    # mentions is a decision somebody has to make, and the port is when
    # they are holding the tool. Classifying it is one line in the
    # manifest -- copy_files to take it, linux_only_files to decline it.
    # Reporting this and carrying on is what the "stale main" paragraph
    # did for weeks while being perfectly correct.
    stray = unlisted_upstream(manifest, args.to)
    if stray:
        print("STOPPED. Nothing was written.\n", file=sys.stderr)
        print("%d upstream suite(s) are in no list in win_port.json:"
              % len(stray), file=sys.stderr)
        for one in stray:
            print("  - %s" % one, file=sys.stderr)
        print("\nPut each in copy_files (take it) or linux_only_files "
              "(decline it), then re-run.", file=sys.stderr)
        return 1
    try:
        files, to_sha = generate(manifest, args.to)
        verify(files, manifest)
    except PortError as exc:
        print("\nSTOPPED. Nothing was written.\n\n%s" % exc, file=sys.stderr)
        return 1

    if args.dry_run:
        changed = []
        for name, text in files.items():
            p = REPO / name
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                changed.append(name)
        print("\n  would change: %s" % (", ".join(changed) or "nothing"))
        print("  dry run, nothing written")
        return 0

    for name, text in files.items():
        p = REPO / name
        # a new suite arriving brings its directory with it
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = p.stat().st_mode if p.exists() else None
        p.write_text(text, encoding="utf-8")
        if mode is not None:
            os.chmod(p, mode)
        elif text.startswith("#!"):
            # tools/mock-op is run as a program, not imported
            os.chmod(p, 0o755)

    manifest["ported_from"] = to_sha
    raw = MANIFEST.read_text(encoding="utf-8")
    raw = re.sub(r'("ported_from":\s*)"[^"]*"',
                 lambda m: '%s"%s"' % (m.group(1), to_sha), raw, count=1)
    MANIFEST.write_text(raw, encoding="utf-8")

    print("\n  written. ported_from is now %s" % to_sha[:9])
    print("  review with: git -C %s diff" % REPO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
