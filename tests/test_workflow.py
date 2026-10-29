#!/usr/bin/env python3
"""The Windows build runs PowerShell that nothing here can execute.

There is no pwsh on this machine and no Windows machine to put one on,
so every line of .github/workflows/build-exe.yml ships unrun. On
2026-10-29 that cost a build: PowerShell reads `$build:` as a
*scope-qualified* variable -- the `$scope:name` form that makes
`$env:PATH` work -- so

    Write-Error "commit count is $build: the checkout is shallow..."

was a ParserError, not a runtime one. A ParserError aborts the whole
script before its first statement, which has two consequences worth
having a test for. The obvious one: a message that only ever prints on
a failure path took down the happy path too. The quiet one: parsing
stops at the FIRST bad token, so any further mistake in the same file
is still hidden, and the only way to find them is one CI run per bug.

So this reads the pwsh in that file and checks the things that can be
checked without running it. It is not a PowerShell parser and does not
pretend to be -- it is the handful of mistakes that have actually been
made here, plus the two orderings that were got wrong and fixed:

  (1) `$name:` where `name` is not a real scope or provider. Valid:
      $env:, $global:, $script:, $local:, $private:, $using:,
      $variable:, $function:, $alias:. Anything else is a parse error.
  (2) a `@"` here-string inside a YAML block scalar. PowerShell wants
      its closing `"@` at column zero; YAML wants every line of a block
      scalar indented. They cannot both have it, and the YAML is what
      breaks. Release notes go in a file instead.
  (3) brackets that do not balance across a step.
  (4) fetch-depth: 0 on the checkout. The build number is the commit
      count, and a shallow clone counts 1, which is how "Browser 1.0.1"
      got published over a 1.0.4.
  (5) the trim runs before the smoke test, so the 25-second start
      exercises the bundle that actually ships rather than the one
      before the prune.
  (6) the publish step turns off $PSNativeCommandUseErrorActionPreference.
      `gh release view` is MEANT to fail the first time a version is
      published; under PS 7.4's default that expected failure becomes a
      failed job, i.e. the first build of every new version.

Static, reads one file, writes nothing, no Qt, no network, no PyYAML
(the venv the suite runs in has none). Runs from anywhere.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parent / ".github" / "workflows" / "build-exe.yml"

fails = []


def check(what, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what
          + (("  <" + str(detail) + ">") if detail != "" else ""))
    if not ok:
        fails.append(what)


# The scopes and providers a colon may legitimately follow. Everything
# else after `$name` makes the colon part of a variable reference that
# cannot resolve, and PowerShell refuses the file.
SCOPES = ("env", "global", "script", "local", "private", "using",
          "variable", "function", "alias")
SCOPED = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*):")


def steps(text):
    """(name, body) for every step, body being its raw lines.

    Textual on purpose: the suite's interpreter has no PyYAML, and a
    check that cannot run is worth less than a crude one that does.
    """
    out = []
    name = None
    body = []
    for line in text.splitlines():
        if re.match(r"^      - (name|uses):", line):
            if name is not None:
                out.append((name, body))
            name = line.split(":", 1)[1].strip() or "(unnamed)"
            body = []
        elif name is not None:
            body.append(line)
    if name is not None:
        out.append((name, body))
    return out


def code_of(body):
    """The `run:` block with its comment lines dropped.

    Each of the three checks that was wrong on first run was wrong this
    way: it searched the text when it meant the code, so a comment
    explaining why github.run_number is gone read as github.run_number
    still being used. A guard that its own explanation sets off is the
    same mistake as a guard that spells out the string it forbids.
    """
    return "\n".join(l for l in script_of(body)
                      if not l.lstrip().startswith("#"))


def script_of(body):
    """Just the `run:` block of a step, without the YAML around it."""
    lines = []
    taking = False
    for line in body:
        if re.match(r"^        run: *[|>]", line):
            taking = True
            continue
        if taking:
            if line.strip() and not line.startswith("          "):
                break
            lines.append(line)
    return lines


text = WORKFLOW.read_text(encoding="utf-8")
ALL = steps(text)

print("(1) no variable reference PowerShell will read as a scope")
check("the workflow is there and has steps", len(ALL) >= 8, len(ALL))

# Every step on windows-latest runs in pwsh, declared or not: that is
# the runner's default shell. So all of them are scanned, not only the
# ones that say `shell: pwsh`.
bad_scope = []
for name, body in ALL:
    for num, line in enumerate(script_of(body), 1):
        if line.lstrip().startswith("#"):
            continue
        for var in SCOPED.findall(line):
            if var not in SCOPES:
                bad_scope.append("%s line %d: $%s:" % (name, num, var))
check("no $name: outside the real scopes", not bad_scope, bad_scope[:3])

# and the check has to be able to fail, or it is decoration: the line
# that actually broke the build, put back.
broke = 'Write-Error "commit count is $build: the checkout is shallow"'
caught = [v for v in SCOPED.findall(broke) if v not in SCOPES]
check("...and it catches the line that broke the 2026-10-29 build",
      caught == ["build"], caught)
check("...while $env: and the other providers pass",
      not [v for v in SCOPED.findall(
          "$env:VER $global:x $script:y $using:z") if v not in SCOPES])


print()
print("(2) nothing that YAML and PowerShell cannot both have")
heredoc = []
for name, body in ALL:
    for num, line in enumerate(script_of(body), 1):
        if (re.search(r"(?:^|[\s=(,])@\"\s*$", line)
                or re.match(r"^\s*\"@\s*$", line)):
            heredoc.append("%s line %d" % (name, num))
check("no @\" here-string inside a block scalar", not heredoc,
      heredoc[:3])
check("the release notes live in a file instead",
      "--notes-file" in text and "RELEASE_NOTES.md" in text)


print()
print("(3) brackets balance in every step")
for name, body in ALL:
    script = "\n".join(script_of(body))
    # comments carry prose brackets ("(see x)"), and they are not code
    code = "\n".join(l for l in script.splitlines()
                     if not l.lstrip().startswith("#"))
    for open_c, close_c in (("{", "}"), ("(", ")"), ("[", "]")):
        a, b = code.count(open_c), code.count(close_c)
        check("%s: %s%s balance" % (name, open_c, close_c), a == b,
              "%d vs %d" % (a, b) if a != b else "")


print()
print("(4) the orderings that were got wrong once already")
names = [n for n, _ in ALL]


def at(needle):
    for i, n in enumerate(names):
        if needle.lower() in n.lower():
            return i
    return -1


checkout = next((b for n, b in ALL if "checkout" in n), [])
check("the checkout is not shallow: fetch-depth: 0",
      any("fetch-depth: 0" in l for l in checkout),
      [l.strip() for l in checkout if "fetch-depth" in l] or "absent")
code = "\n".join(code_of(b) for _n, b in ALL)
check("the build number is the commit count, not run_number",
      "rev-list --count HEAD" in code and "github.run_number" not in code,
      "run_number still used" if "github.run_number" in code else "")
check("there is a VERSION file to read",
      (HERE.parent / "VERSION").is_file()
      and re.match(r"^\d+\.\d+$",
                   (HERE.parent / "VERSION").read_text().strip()) is not None,
      (HERE.parent / "VERSION").read_text().strip()
      if (HERE.parent / "VERSION").is_file() else "missing")

trim, smoke, build = at("trim"), at("smoke"), at("build installer")
check("the trim, the smoke test and the installer all exist",
      -1 not in (trim, smoke, build), (trim, smoke, build))
check("the smoke test starts the bundle that ships (trim first)",
      trim < smoke, "trim %d, smoke %d" % (trim, smoke))
check("...and both happen before the installer is packed",
      smoke < build, "smoke %d, installer %d" % (smoke, build))

publish = next((b for n, b in ALL if "publish" in n.lower()), [])
pub = "\n".join(script_of(publish))
check("the publish step lets gh release view fail as intended",
      "$PSNativeCommandUseErrorActionPreference = $false" in pub)
check("...and checks $LASTEXITCODE by hand instead",
      pub.count("$LASTEXITCODE") >= 3, pub.count("$LASTEXITCODE"))
check("the release is tagged by version, not by build number",
      're $tag' not in pub and "$tag = \"v$env:VER\"" in pub)


print()
print("(5) the prunes still assert what they expect to find")
trim_body = next((b for n, b in ALL if "trim" in n.lower()), [])
trim_text = "\n".join(script_of(trim_body))
check("each prune is given a minimum file count",
      trim_text.count("Prune ") >= 3, trim_text.count("Prune "))
check("...and refuses rather than silently saving nothing",
      "would silently save nothing" in trim_text)
check("the release .pak files are checked to have survived",
      "qtwebengine_resources.pak" in trim_text
      and "the prune removed" in trim_text)
trim_code = code_of(trim_body)
pruned = [n for n in ("opengl32sw", "d3dcompiler") if n in trim_code]
check("the software-rendering fallbacks are left alone", not pruned,
      pruned)
check("...and the comment says why they are kept",
      "opengl32sw.dll" in trim_text and "black" in trim_text)

print()
print("(6) the edition's own files are all declared and all present")
# win_port.json's win_only_files is the record of what belongs to this
# edition and must never be clobbered by a port. Nothing in
# win_port.py reads it, so it is documentation -- and documentation
# nobody checks goes stale quietly. Six files of the installer work
# were missing from it.
import json

man = json.loads((HERE.parent / "tools" / "win_port.json")
                 .read_text(encoding="utf-8"))
only = man["win_only_files"]
gone = [f for f in only if not (HERE.parent / f).exists()]
check("every file win_only_files names is on disk", not gone, gone)

in_port = set(n for n in man["merge_files"] + man["copy_files"]
              if not n.startswith("#"))
both = sorted(set(only) & in_port)
check("...and none of them is also in the port's file set", not both, both)

# the installer is this edition's whole reason to exist; if a port could
# overwrite it the edition would quietly become the Linux one
for needed in ("packaging/installer.iss", ".github/workflows/build-exe.yml",
               "VERSION", "tests/test_workflow.py"):
    check("...including %s" % needed, needed in only)

print()
if fails:
    print("FAILED (%d): %s" % (len(fails), "; ".join(fails[:6])))
else:
    print("all good")
sys.exit(1 if fails else 0)
