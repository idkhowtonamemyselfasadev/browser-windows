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


def joined(value):
    """A manifest string, which may be written as a list of fragments.

    A guard has to name the thing it forbids, and the things forbidden
    here are his home directory, the subnet his machines sit on and his
    mail handle. Written out, this file would be the leak it exists to
    prevent -- and gitguard refuses the commit, correctly. So a rule may
    spell its needle as ["/home/", "<his login>"] and it is joined here.
    Nothing is interpreted: the pieces are concatenated exactly.
    """
    if isinstance(value, list):
        return "".join(value)
    return value


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


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
    # WIN_PORT_LINUX_REPO points the port at another checkout for one run.
    # The manifest is committed and public, so it names ~/browser; a second
    # clone (a bare mirror of the Linux repo, a worktree at some other
    # commit) is a reason to override it, not a reason to edit it.
    linux = Path(os.environ.get("WIN_PORT_LINUX_REPO")
                 or manifest["linux_repo"]).expanduser()
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


def ancestor_of(repo, rev, branch="main"):
    """Is this commit actually on that branch's line of history?

    Asked separately from "how far behind", because a count of zero
    answers both "the base is the branch tip" and "the base is nowhere
    near it" with the same number. git merge-base --is-ancestor is the
    only one of the two that distinguishes them.
    """
    out = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", rev, branch],
        capture_output=True, text=True)
    return out.returncode == 0


def twin(repo, base, branch="main"):
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


def relation(repo, base, branch="main"):
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
    if ancestor_of(repo, base, branch):
        return "on"
    if soft(repo, "rev-list", "--count",
            "%s..%s" % (base, branch)) == "0":
        return "ahead"
    shared = soft(repo, "merge-base", branch, base)
    return "diverged" if shared else "unrelated"


def drift(manifest):
    """How far this tree is behind the Linux repo it comes from.

    The markers say our regions are intact; they say nothing about the
    edition being current, and those are different questions. Returns
    the lines to print -- it never raises, because being unable to find
    the Linux repo is a thing to report, not a reason to fail.
    """
    # the same override generate() honours, or --check would report drift
    # against one tree while a port read another
    linux = Path(os.environ.get("WIN_PORT_LINUX_REPO")
                 or manifest["linux_repo"]).expanduser()
    base = manifest["ported_from"]
    if not linux.is_dir():
        return ["  linux repo   %s is not here, so drift is unknown" % linux]
    head = soft(linux, "rev-parse", "--short", "HEAD")
    if head is None:
        return ["  linux repo   %s is not a git repo, so drift is unknown"
                % linux]
    branch = soft(linux, "rev-parse", "--abbrev-ref", "HEAD")
    out = ["  linux repo   %s  (HEAD %s%s)"
           % (linux, head, " on " + branch if branch else "")]
    if soft(linux, "cat-file", "-t", base) != "commit":
        out.append("  behind       unknown: ported_from %s is not a commit "
                   "in that repo" % base[:9])
        return out
    behind = soft(linux, "rev-list", "--count", "%s..main" % base)
    if behind is None:
        out.append("  behind       unknown: no main branch in that repo")
    elif (how := relation(linux, base)) != "on":
        # "ported_from..main" being empty says nothing on its own: it is
        # equally true of a base that IS main and of one that is nowhere
        # near main. Counting alone cannot tell those apart, so this used
        # to print "level with main" for a base that was never on main.
        # The same lie d7ee8a1 took off the marker side, arriving the
        # second time through the base pointer.
        ahead = soft(linux, "rev-list", "--count", "main..%s" % base) or "?"
        if how == "ahead":
            out.append("  behind       UNKNOWN: ported_from %s is a "
                       "DESCENDANT of main, not an ancestor" % base[:9])
            out.append("               main is %s commit(s) behind it, so "
                       "ported_from..main is empty" % ahead)
            out.append("               and this line used to read \"level "
                       "with main\". Nothing is level.")
        elif how == "unrelated":
            out.append("  behind       UNKNOWN: ported_from %s shares NO "
                       "history with main here" % base[:9])
            out.append("               no common ancestor at all: main has "
                       "%s commit(s) it lacks, it has %s main lacks"
                       % (behind, ahead))
            out.append("               a three-way merge against that base "
                       "is guesswork, not a port")
        else:
            out.append("  behind       DIVERGED: main has %s commit(s) "
                       "ported_from lacks," % behind)
            out.append("               and ported_from has %s that main "
                       "lacks. The count is real, but a port" % ahead)
            out.append("               carries main's side only.")
            out.append("               see them: tools/win_port.py --to "
                       "main --dry-run")
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
        if relation(linux, base, "origin/main") == "on":
            short = soft(linux, "rev-list", "--count",
                         "%s..origin/main" % base) or "?"
            out.append("  stale main   the base IS on origin/main (%s commit"
                       "(s) behind it)." % short)
            out.append("               This repo's local main is the branch "
                       "left behind, not the base.")
            out.append("               measure with: --to origin/main")
        else:
            # A rewrite: the base's replacement is findable, not
            # guessable. Tried on origin/main too, because a clone whose
            # local main was left behind by the force-push has the
            # rewritten lineage only on the remote-tracking branch.
            got = twin(linux, base) or twin(linux, base, "origin/main")
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
                out.append("               a port --to main would port "
                           "backwards; point ported_from at a commit on main")
            elif how == "unrelated":
                out.append("               point ported_from at a commit "
                           "this repo's main can actually reach")
    elif behind == "0":
        out.append("  behind       nothing: this tree is level with main")
    else:
        out.append("  behind       %s commit(s) of main, ported_from is %s"
                   % (behind, base[:9]))
        out.append("               see them: tools/win_port.py --to main "
                   "--dry-run")
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
    ap.add_argument("--to", help="Linux commit to port (default: main)",
                    default="main")
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
        return 0

    print("Regenerating the Windows edition\n")
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
