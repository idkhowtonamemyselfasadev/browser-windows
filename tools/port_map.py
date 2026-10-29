#!/usr/bin/env python3
"""Where a port's merge conflicts come from, before anyone resolves one.

win_port.py answers "can this port run?" and stops at the first file that
conflicts. That is the right answer for a port and the wrong one for
planning: "browser.py: 77 conflict(s)" says nothing about whether that is
42 commits each costing two, or one commit costing sixty-seven. Those are
different weeks of work. This answers that instead, and writes nothing.

Three questions, all read-only:

  --commits   which commits cause the conflicts. The merge is replayed
              cumulatively, base..c for every commit c in order, and the
              jump in the count when c arrives is what c is responsible
              for. Cumulative because that is how the port actually runs.
  --areas     which parts of the file they land in, by enclosing class or
              function, so "fix the two hot definitions" can be seen.
  --markers   how many of them sit in a region win_port.json actually
              declares. This is the uncomfortable one: a conflict inside a
              declared region is defended by a marker, and a conflict
              outside one can be resolved away wrongly with every marker
              still passing afterwards.

Usage:
    tools/port_map.py                 # all three
    tools/port_map.py --commits       # just the attribution
    tools/port_map.py --to <rev>      # against something other than main

Everything is resolved relative to this file, so it works in a fresh
clone with no editing.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = HERE / "win_port.json"

CONFLICT = "<<<<<<< windows"


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def joined(value):
    """A manifest string, or a list of fragments to concatenate. See the
    same helper in win_port.py: a marker that names his home directory
    or his subnet cannot spell it out in a repo that forbids it."""
    if isinstance(value, list):
        return "".join(value)
    return value


def names(seq):
    """The manifest's file lists carry prose entries starting with a '#'.
    Same convention as win_port.py, and it is '#' rather than '_' for a
    reason worth not repeating: under the old underscore rule _boot.py
    was read as commentary and went two months unported."""
    return [n for n in seq if not n.startswith("#")]


def git(repo, *args, text=False):
    """None rather than an exception: a missing blob is an answer here
    (the file did not exist at that commit), not a failure."""
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace") if text else out.stdout


def ancestor(repo, rev, of):
    """Is rev on of's line of history? The one question a conflict count
    cannot answer for itself -- see the refusal in main()."""
    out = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", rev, of],
        capture_output=True)
    return out.returncode == 0


def merge(base, ours, theirs):
    """(conflict count, merged text) for one three-way merge.

    Counted from the markers rather than from git merge-file's exit code,
    which saturates: it returns the number of conflicts but caps well
    below what this file produces.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "ours").write_bytes(ours)
        (tmp / "base").write_bytes(base)
        (tmp / "theirs").write_bytes(theirs)
        subprocess.run(
            ["git", "merge-file", "--diff3",
             "-L", "windows", "-L", "base", "-L", "linux",
             str(tmp / "ours"), str(tmp / "base"), str(tmp / "theirs")],
            capture_output=True)
        merged = (tmp / "ours").read_text("utf-8", "replace")
    return merged.count(CONFLICT), merged


def final_merge(linux, base_rev, to_rev, name):
    """The merge the port would do for one file, or None if it cannot."""
    base = git(linux, "show", "%s:%s" % (base_rev, name))
    theirs = git(linux, "show", "%s:%s" % (to_rev, name))
    here = REPO / name
    if base is None or theirs is None or not here.exists():
        return None
    return merge(base, here.read_bytes(), theirs)


def commit_list(linux, base_rev, to_rev):
    """(sha, subject) oldest first, which is the order a port replays."""
    out = git(linux, "rev-list", "--reverse", "--pretty=%h %s",
              "--no-commit-header", "%s..%s" % (base_rev, to_rev), text=True)
    if out is None:
        return []
    rows = []
    for line in out.splitlines():
        if line.strip():
            sha, _, subject = line.partition(" ")
            rows.append((sha, subject.strip()))
    return rows


def per_commit(linux, base_rev, to_rev, files):
    print("Which commits cause the conflicts\n")
    commits = commit_list(linux, base_rev, to_rev)
    print("  %d commit(s) from %s to %s\n" % (len(commits), base_rev[:9], to_rev))
    for name in files:
        base = git(linux, "show", "%s:%s" % (base_rev, name))
        here = REPO / name
        if base is None or not here.exists():
            print("  %s: not in both trees, skipped\n" % name)
            continue
        ours = here.read_bytes()
        previous, moved = 0, []
        for sha, subject in commits:
            theirs = git(linux, "show", "%s:%s" % (sha, name))
            if theirs is None:
                continue
            count, _ = merge(base, ours, theirs)
            if count != previous:
                moved.append((sha, subject, count - previous, count))
            previous = count
        print("  %s -> %d conflict(s)" % (name, previous))
        for sha, subject, delta, running in moved:
            print("    %+4d  (running %3d)  %s  %s"
                  % (delta, running, sha, subject[:58]))
        if not moved:
            print("    no commit conflicts with this file")
        quiet = len(commits) - len(moved)
        if moved:
            print("    %d of %d commit(s) conflict with nothing here"
                  % (quiet, len(commits)))
        print()


def hunks(merged):
    """Just the "ours" side of each conflict, with its line number.

    The windows side is the interesting one: it is what the port would
    be deciding whether to keep.
    """
    out, body, side, start = [], None, None, 0
    for number, line in enumerate(merged.splitlines(), 1):
        if line.startswith(CONFLICT):
            body, side, start = [], "ours", number
            continue
        if line.startswith("||||||| base"):
            side = "base"
            continue
        if line.startswith("=======") and body is not None:
            side = "linux"
            continue
        if line.startswith(">>>>>>> linux") and body is not None:
            out.append((start, "\n".join(body)))
            body, side = None, None
            continue
        if body is not None and side == "ours":
            body.append(line)
    return out


def per_area(merged, name):
    print("Where the conflicts land in %s\n" % name)
    lines = merged.splitlines()
    top = re.compile(r"^(class|def)\s+(\w+)")
    owner, current = [], "(module level)"
    for line in lines:
        found = top.match(line)
        if found:
            current = "%s %s" % (found.group(1), found.group(2))
        owner.append(current)

    areas = Counter()
    for index, line in enumerate(lines):
        if line.startswith(CONFLICT):
            areas[owner[index]] += 1
    total = sum(areas.values()) or 1
    running = 0
    for area, count in areas.most_common():
        running += count
        print("    %3d  (%3d%% cumulative)  %s"
              % (count, 100 * running // total, area))
    print("\n  %d area(s) in all\n" % len(areas))


def per_marker(merged, name, declared):
    print("How many conflicts a marker defends\n")
    rules = [(m["name"], re.compile(joined(m["pattern"]), re.MULTILINE))
             for m in declared if m["file"] == name]
    defended, undefended = Counter(), []
    for _start, body in hunks(merged):
        hit = [label for label, rx in rules if rx.search(body)]
        if hit:
            for label in hit:
                defended[label] += 1
        else:
            undefended.append(body)
    total = len(hunks(merged)) or 1
    covered = total - len(undefended)
    print("    %d of %d conflict(s) sit in a declared region" % (covered, total))
    print("    %d do not, and the markers would not notice those being "
          "resolved away\n" % len(undefended))
    if defended:
        print("  defended regions that a conflict touches:")
        for label, count in defended.most_common():
            print("    %3d  %s" % (count, label))
        print()
    if undefended:
        print("  undefended, by the first line of each:")
        seen = Counter()
        for body in undefended:
            first = next((l.strip() for l in body.splitlines() if l.strip()),
                         "(nothing but blank lines)")
            seen[first[:68]] += 1
        for first, count in seen.most_common(20):
            print("    %3d  %s" % (count, first))
        if len(seen) > 20:
            print("    ... and %d more" % (len(seen) - 20))
        print()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--to", default="main",
                    help="the Linux commit to measure against (default: main)")
    ap.add_argument("--commits", action="store_true",
                    help="only which commits cause the conflicts")
    ap.add_argument("--areas", action="store_true",
                    help="only where in the file they land")
    ap.add_argument("--markers", action="store_true",
                    help="only how many of them a marker defends")
    args = ap.parse_args()
    everything = not (args.commits or args.areas or args.markers)

    data = manifest()
    # the override win_port.py's generate() honours, so this measures the
    # tree a port would actually read
    linux = Path(os.environ.get("WIN_PORT_LINUX_REPO")
                 or data["linux_repo"]).expanduser()
    base_rev = data["ported_from"]
    files = names(data["merge_files"])

    if not linux.is_dir():
        print("the linux repo %s is not here" % linux, file=sys.stderr)
        return 1
    if git(linux, "cat-file", "-t", base_rev, text=True) != "commit\n":
        print("ported_from %s is not a commit in %s"
              % (base_rev[:9], linux), file=sys.stderr)
        return 1
    if git(linux, "rev-parse", args.to, text=True) is None:
        print("%s is not a revision in %s" % (args.to, linux), file=sys.stderr)
        return 1
    # Everything below replays base..to, so the shape of that range
    # decides whether any of it means anything.
    #
    #   base is an ancestor of to   the range is the work to port; normal.
    #   the range is EMPTY          every count below is a zero that means
    #                               "nothing is in the range", not
    #                               "nothing is left to port" -- and it
    #                               reads as the second. This is what
    #                               printed "0 commit(s)" and "no commit
    #                               conflicts with this file" for a tree
    #                               whose base was 39 commits ahead of
    #                               main, on a dependabot branch.
    #   no common ancestor          the three-way merge has no base at
    #                               all; its conflict counts are noise.
    #   diverged, range non-empty   the counts are real. Worth saying so
    #                               out loud, not worth refusing over.
    #
    # Refusing in the first two: a planning tool that reports a clean tree
    # because it measured the range backwards is worse than one that will
    # not run.
    if not ancestor(linux, base_rev, args.to):
        span = (git(linux, "rev-list", "--count",
                    "%s..%s" % (base_rev, args.to), text=True) or "0").strip()
        ahead = (git(linux, "rev-list", "--count",
                     "%s..%s" % (args.to, base_rev), text=True) or "?").strip()
        shared = git(linux, "merge-base", args.to, base_rev, text=True)
        where = git(linux, "branch", "-a", "--contains", base_rev, text=True)
        where = (where.splitlines()[0].strip().lstrip("* ").strip()
                 if where else None)
        if span == "0" or not shared:
            if span == "0":
                print("ported_from %s is a DESCENDANT of %s in %s."
                      % (base_rev[:9], args.to, linux), file=sys.stderr)
                print("%s is %s commit(s) behind it, so %s..%s is empty and "
                      "every count below would be a meaningless 0."
                      % (args.to, ahead, base_rev[:9], args.to),
                      file=sys.stderr)
            else:
                print("ported_from %s shares no history with %s in %s."
                      % (base_rev[:9], args.to, linux), file=sys.stderr)
                print("No common ancestor, so the three-way merge has no "
                      "base and its conflict counts would be noise.",
                      file=sys.stderr)
            if where:
                print("%s lives on %s" % (base_rev[:9], where),
                      file=sys.stderr)
            print("Measure against something that descends from the base "
                  "(--to <rev>), or fix win_port.json's ported_from.",
                  file=sys.stderr)
            return 1
        print("note: ported_from %s and %s have DIVERGED -- %s commit(s) to "
              "replay, and %s on the base that %s does not have."
              % (base_rev[:9], args.to, span, ahead, args.to), file=sys.stderr)
        print("      the counts below are real; a port carries %s's side "
              "only.\n" % args.to, file=sys.stderr)

    if args.commits or everything:
        per_commit(linux, base_rev, args.to, files)

    if args.areas or args.markers or everything:
        # the per-file work only pays off where there is a conflict, and in
        # practice that has been browser.py alone
        for name in files:
            got = final_merge(linux, base_rev, args.to, name)
            if got is None or got[0] == 0:
                continue
            _count, merged = got
            if args.areas or everything:
                per_area(merged, name)
            if args.markers or everything:
                per_marker(merged, name, data["markers"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
