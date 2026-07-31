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


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def names(seq):
    """The file lists carry inline commentary — entries starting with an
    underscore are prose, not paths. JSON has no comments, and a list of
    two dozen file names with no explanation is how the next person
    guesses wrong."""
    return [n for n in seq if not n.startswith("_")]


def apply_substitutions(files, rules):
    """Returns (files, per-rule hit counts). Idempotent by construction:
    each replacement no longer matches its own pattern."""
    counts = []
    for rule in rules:
        hits = 0
        for name, text in files.items():
            if not matches(name, rule["files"]):
                continue
            n = text.count(rule["find"])
            if n:
                files[name] = text.replace(rule["find"], rule["replace"])
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
        rx = re.compile(m["pattern"], re.MULTILINE)
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
    linux = Path(manifest["linux_repo"]).expanduser()
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
            print("  subst   %-4d %s" % (hit, rule["find"][:58]))
    for rule, hit in zip(manifest["substitutions"], counts):
        if hit < rule.get("min", 1):
            raise PortError(
                "substitution %r matched %d time(s), expected at least %d.\n"
                "Linux probably renamed it — update win_port.json."
                % (rule["find"], hit, rule.get("min", 1)))

    return files, to_sha


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
                    help="only verify the tree as it stands")
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
        print("  tree is a valid Windows edition of linux %s"
              % manifest["ported_from"])
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
