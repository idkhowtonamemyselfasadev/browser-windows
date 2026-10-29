# QA pass — the Windows edition

Against the brief in `~/claude/browser-pages/briefs/QA-PLAN.md`, 2026-10-29.

**This report covers what was actually run.** The brief has 18 sections; the
sections that need a Windows machine are marked **BLOCKED** with the reason,
because there is no Windows machine and no VM here and a guess in this document
would be worth less than a gap. `README.md` → *Unsettled, for want of a Windows
machine* is the companion list: one item per hour of somebody's time on real
hardware.

## Target environment

| | |
|---|---|
| Build under test | `browser-windows`, commit `8b46834` |
| Version it would ship as | 1.0.33 (`VERSION` 1.0 + commit count) |
| Installer | `BrowserSetup.exe`, 131,096,763 bytes, unsigned |
| Engine | Qt 6.11.0 / PyQt6 6.11.0, Chromium via QtWebEngine |
| Python | 3.14.4 (venv); the shipped exe bundles 3.13 |
| Themes / languages | 116 palettes, 12 UI languages (en + de complete) |
| Bridge surface | 129 methods, 94 of them called by the nine pages |
| **Ran on** | **Linux 7.0.0, x86_64.** Not Windows. |
| Comparison browser | Google Chrome 156.0.8078.73, Firefox 158.0 |

Everything below ran on Linux against this edition's own code. That is valid for
logic, process behaviour and anything measurable in a number; it is **not** valid
for appearance, native integration or Windows-specific API behaviour, and those
are marked BLOCKED rather than inferred.

---

## Section 1 — Installation & first launch

| Test | Status |
|---|---|
| W01-01 Installer size and what is in it | **PASS** (fixed, −19.6 MB) |
| W01-02 Signature check | **FAIL — High** (unsigned, by necessity) |
| W01-03 SmartScreen path documented | **PASS** (fixed today) |
| W01-04 Default install path / Start menu / uninstall entry | **PARTIAL** |
| W01-05 Install time, disk use | **PARTIAL** — disk measured, time BLOCKED |
| W01-06 Onboarding, default-browser prompt, import | **BLOCKED** |
| W01-07 Cold and warm launch time, 3 runs | **BLOCKED** |

### W01-01 — the installer was 19.6 MB bigger than it needed to be
**Steps** Measured the real `win_amd64` wheels CI installs, compressed with lzma2
at Inno's own preset; then read PyInstaller's `QtWebEngineCore` hook.
**Expected** The bundle contains what the browser needs.
**Actual** The hook passes `Qt6/resources` as a *whole directory* while its own
module docstring claims it takes only the four release `.pak` files. So a 72 MB
`qtwebengine_devtools_resources.debug.pak` shipped to every user, plus 53 UI
languages the browser does not offer.

    resources/*.debug.*        5 files    77.2 MB on disk → 10.5 MB of installer
    qtwebengine_locales       50 files    42.0 MB on disk →  6.6 MB
    translations/*.qm        191 files     9.5 MB on disk →  1.3 MB
    lzma2/max → ultra64 (8 → 64 MB dict)                 →  2.1 MB

**Status** PASS after fix. 151,669,890 → 131,096,763 bytes, **−19.6 MB, −13.6 %**;
bundle on disk 553.5 → 425.0 MB. Predicted ~20 MB before the build ran, landed
19.6.
**Evidence** CI run 40859944798; release v1.0.28 onward.
**Not cut, deliberately** `opengl32sw.dll` and `d3dcompiler_47.dll`, 6.5 MB of
installer. They are the software-rendering fallbacks and the machines that need
them — a VM, RDP, broken GPU drivers — are the ones that must not open to a black
window. No Windows machine here to prove it safe.

### W01-02 — the installer is unsigned and always will be
**Actual** No Authenticode signature. Every user meets the SmartScreen wall.
**Status** FAIL — **High**, and **not fixable**: a certificate costs money that is
not available. Mitigation is W01-03.

### W01-03 — SmartScreen is now explained instead of met cold
**Actual before** One clause in a paragraph: "SmartScreen will warn you: click
More info → Run anyway."
**Actual after** README and every release page carry the dialog's real words, the
fact that its only button says **Don't run**, and the three clicks through it,
plus what SmartScreen is actually claiming (unrecognised publisher, not malware).
`packaging/RELEASE_NOTES.md` so the text is reviewable like code.
**Status** PASS. **Observation of the dialog itself: BLOCKED** — the wording comes
from Microsoft's documentation, not from having clicked it.

### W01-04 — Windows integration
**Actual** Reviewed `packaging/installer.iss` and fixed four things: the Start-menu
entry was `{group}\Browser`, i.e. a *folder* called Browser containing one item
called Browser, now a single `{autoprograms}` entry Start finds by typing `brow`;
the uninstall row had a name and nothing else, now carries a support URL, an
updates URL and a version; the setup exe had no version metadata; and
`ArchitecturesAllowed=x64compatible` + `MinVersion=10.0` now refuse an
unsupported machine with a sentence instead of installing an app that cannot
start.
**Status** PARTIAL — written from the Inno Setup documentation. **What Settings →
Apps actually shows is BLOCKED.**

### W01-05 — disk cost
**Actual** Download 125 MB, installed **425 MB**, user data starts at a few
hundred KB. Now in the README; it had only ever existed in a CI log.
**Status** PARTIAL — install *time* is BLOCKED.

---

## Section 10 — Privacy & security

### W10-01 — what the browser sends at startup
**Steps** `strace -f -e trace=connect` over a clean-profile launch, 32 s,
deliberately **without** `BROWSER_NO_LIB_CHECK` so the shipped default is what is
measured. Twice: `--agent` (no window) and a normal launch (window, start page,
first-run wizard).
**Expected** If "no telemetry" is true, nothing but what the user asked for.
**Actual** Both runs, identical shape:

    1 × AF_INET  127.0.0.53:53      DNS, local stub resolver
    1 × AF_INET  140.82.121.3:443   lb-140-82-121-4-fra.github.com
    10 × AF_UNIX                    local sockets only

Total `AF_INET` connections in an entire startup: **two**, one of which is DNS.
The connecting process is a **child** that exits 0 — the `git fetch` of the update
check, not the browser's own socket. Nothing from the start page: a normal launch
that draws the start page and the wizard makes no more connections than the
headless one.
**Status** **PASS.** "No telemetry, no account, no sync" is now observed rather
than asserted.
**Three caveats that belong with it**
1. It is not "no network calls at startup". One connection goes to GitHub on every
   launch, so GitHub learns the user's IP and rough launch times. Nothing *about*
   the user is sent — it is a git ref advertisement — but a privacy-minded reader
   should be told. There is no setting to turn the update check off.
2. On the **exe** build this drops to **zero**: `exe_main.py` replaces
   `_check_updates` with `_no_check`. The quietest install route is the frozen one.
3. `QTimer.singleShot(3000, self._check_updates)` is unconditional — no headless
   guard. The `--agent` browser phones GitHub too, which matters for scripting on
   a metered or air-gapped box.

**Method note.** My first attempt sampled `ss -tnp` every 0.4 s and recorded
**zero** connections, which reads exactly like a clean result. It was not: a
`git fetch` with nothing to do finishes between samples. Polling can miss
everything and look like good news.

### W10-02 — the rest of Section 10
Cookie policy, tracker and fingerprint protection, permission prompts, clear-data
verification, private-mode leakage, mixed content, CSP, CORS, phishing warnings:
**NOT YET RUN.** These need real sites (`coveryourtracks.eff.org`, `badssl.com`)
and a driven browser; they are runnable here and are the obvious next block.

---

## Section 12 — Performance (memory)

**Method** PSS of the whole process tree from `/proc/*/smaps_rollup`, not RSS —
RSS double-counts pages shared between renderers, which in a multi-process
browser is most of the engine. One fixed local page (300 nodes, `file://`, no
network). All browsers under the same `xvfb` display at 1920×1080×24, clean
profile per run.

| | total MB | main | helpers | n helpers |
|---|---|---|---|---|
| ours, 1 tab | **323.1** | 193.0 | 130.1 | 3 |
| ours, 11 tabs | 447.3 | 199.1 | 248.2 | 13 |
| ours, 51 tabs | 892.2 | 233.2 | 659.0 | 53 |
| ours, 51 tabs, 50 asleep | **351.1** | 239.8 | 111.3 | 3 |
| Chrome, 1 tab | 426.5 | 172.6 | 254.0 | 10 |
| Chrome, 10 tabs | 525.7 | 174.2 | 351.5 | 19 |
| Chrome, 50 tabs | 971.1 | 212.7 | 758.4 | 59 |

**Result** Lighter than Chrome at every count: **−103 MB at one tab, −78 MB at
ten, −79 MB at fifty.** Per tab the two are the same (11.4 MB vs 10.9 MB) — the
entire advantage is the baseline, and the reason is the process shape: 2
infrastructure processes + 1 renderer per tab, against Chrome's ~9 + 1.

**Tab sleeping works and is already shipped.** 892.2 → 351.1 MB, **−541 MB,
−61 %**, helpers 53 → 3. It gives renderers back rather than trimming caches, and
Chrome has no equivalent one-switch.

**One number still unexplained.** The main process does not return: 193.0 at one
tab, 233.2 at 51, **239.8 after sleeping all 50** — 46.8 MB arrived and sleeping
did not reclaim it, ~0.94 MB per sleeping tab. A slept tab legitimately keeps its
page object, so this is not yet a leak; the test that separates them is *closing*
the tabs twice and watching for the baseline. **Queued.**

**The nine in-browser pages are cached by design** — `_panes[name]` is built on
first use and reused after, so they stay resident. That is the trade this brief
names: a pane that opens instantly against a renderer held for a page nobody is
looking at. Cost not yet measured; both sides go to him rather than a unilateral
choice.

**Firefox: NOT MEASURED.** Three harnesses, three implausible answers, and I
stopped rather than publish a fourth:

    --type= classifier      1 tab 196.1 MB, 10 tabs 196.0 MB, 3 processes
    profile-path pgrep      1/10/50 tabs 174.3 / 175.7 / 174.5 MB, 2 processes
    parent + child walk     1 tab 193.2 MB, 3 processes, 0 helpers

Flat across 1 and 50 tabs every time, which is not a browser, it is a process
tree I kept failing to walk: Firefox's content processes carry
`-contentproc -childID N` rather than the profile path, and the parent that does
name the profile is not where `xvfb-run` leaves it. The brief says Chrome **or**
Firefox, so Section 12 goes in with Chrome. Better a stated gap than a number I
would have to defend.

**BLOCKED** Speedometer 3 / JetStream 2 / MotionMark, battery, scroll smoothness,
input latency, and **first-launch RAM on Windows**. The ratios above should carry
to Windows; the absolute numbers will not.

---

## Section 18 — Update & uninstall

### W18-01 — the update check is broken for every pre-rewrite clone — **Critical**
`browser-windows` was deleted and recreated on 2026-10-29 to drop `refs/pull/*`
that carried personal data. Every clone taken before that shares no commits with
the new `origin/main`.

**Steps** Build a remote with two commits, clone it, rewrite the remote as an
orphan branch with three commits, `git fetch` in the clone.
**Actual**

    merge-base HEAD @{u}            (none — unrelated)
    rev-list --count HEAD..@{u}     3      ← every upstream commit
    git pull --ff-only              fatal: Not possible to fast-forward, aborting.

**Status** FAIL — **Critical.** "Update available" at every launch for ever, and
the button behind it cannot work.
**Evidence** Reproduced twice in disposable repositories: run 1 count=3, run 2
count=3, both ending in the same `fatal`. Deterministic. His find, confirmed.
**Suggested fix** `rev-list --count A..B` is not wrong, it is answering a
different question — "commits reachable from B but not A", which for unrelated
histories is all of them. Ask `git merge-base --is-ancestor` first and say
"reinstall" rather than "pull" when there is no common ancestor.

### W18-02 — which Windows install routes are exposed
`_check_updates` and `runUpdate` both branch on `(APP_DIR / ".git").exists()`.

1. **BrowserSetup.exe** — `exe_main.py` replaces the check with `_no_check`. **Not
   exposed.** No check, no git, no toast.
2. **Download ZIP + install.bat** — no `.git`, so `_check_zip_update` and
   `_zip_update`. **Not exposed**, and honest for a good reason rather than luck:
   it compares the remote main's **sha for equality**, with no ancestry assumption
   anywhere, and the action downloads a zip over the folder, which works across
   unrelated histories because git never runs. It also guards the fresh-install
   case by fetching the zip and comparing contents before announcing anything.
3. **git clone** (a developer) — **exposed, identically to Linux.**

**Status** PARTIAL. **Medium** for this edition, **Critical** for Linux: the hole
is in shared code, the exposure is what differs, and Linux is *distributed* as a
git clone.

### W18-03 — the uninstall instructions were for the wrong install route
**Actual before** "Delete the *Browser* shortcut from your desktop and remove the
folder you unzipped." That is the from-source route only. Anyone who used
`BrowserSetup.exe` — the route the Install section leads with — has a real
**Settings → Apps → Installed apps → Browser** entry and was being sent to hunt
for a folder they never unzipped.
**Status** FAIL — **Medium**, fixed. Both routes documented, and both now say the
data in `%LOCALAPPDATA%\browser` stays put, because it does.
**Actual uninstall behaviour on Windows: BLOCKED.**

---

## W-L01 — his first name was on the public branch, in thirteen files

Found by `server-71` after the baseline push, confirmed here independently:
**13 files, 71 occurrences.** `RULES.md` says nothing of his ever reaches
GitHub and names the name explicitly. It did.

    test_forms.py 39 · win_port.json 5 · test_games.py 5 · QA-REPORT.md 4
    theme_web.py 3 · test_winbranch.py 3 · test_block3.py 3
    tests/test_leakguard.py 2 · test_dev.py 2 · test_desk.py 2
    tests/harness.py 1 · test_keyboard.py 1 · test_bar.py 1

Two of those sting. `theme_web.py` is **shipped source** — three comments
naming him in a public repo with a deliberately anonymous handle. And
`tests/test_leakguard.py`, the suite whose entire job is to say nothing of
his is here, carried it twice.

**The root cause is the same blind spot in two independent tools.** gitguard's
`personal.txt` blocked his mail handle, two handles, the Strato box, the
subnet, three plug MACs, `/home/<name>`, two monitors and three secrets — and
the comment above the path rule even says the path *is* his name, so the name
was known to matter and was blocked only **inside a path**. `win_port.json`'s
own readme names the three strings it exists to keep out: home directory,
subnet, mail handle. Not the name. Both tools guarded the path and neither
guarded the word.

**Fixed as substitutions, not hand-edits, because 10 of the 13 are
`copy_files`.** A hand-edit trips the drift check and the next port brings the
name straight back; a substitution makes `have == expect` by construction and
keeps taking it out on every port. There was already a rule of exactly this
shape for `/home/<name>`. 13 new rules name the *shapes* the name appears in —
quoted fixture value, example mail address, the `otpauth://` account, the
`icacls` grant, `<Name> Tester`, and the three prose lines in `theme_web.py`.
59 replacements across 9 files, plus `tests/harness.py` on a second pass once
the globs covered `tests/*.py`.

**No rule spells it.** `{USER}` and `{User}` expand from the account in
`joined()`, which also cleared the 5 hits in the manifest itself and the 3 in
its markers. Three new markers assert `count: 0` for `\b{USER}\b` in
`browser.py`, `*.html` and `theme_web.py`. 63 markers pass.

**And the name gets no catch-all substitution, which is the point rather than
an omission.** It is three letters and the prefix of ordinary English: a rule
replacing a bare occurrence would rewrite `time`, `timer`, `timeout`,
`timestamp`, `estimate` and `optimal` in every ported file. So the rules name
the shapes, and `tests/test_leakguard.py`'s word-boundary check is what says
the list is complete — a fourteenth shape fails the suite and gets a rule.

### Two ways my own fix was wrong first

**`Path.home().name` was the wrong source.** Every suite here is required to
run with `HOME` pointed at a throwaway directory, so the derived name was the
scratch folder's. Mine was called `wf2`, the string `wf2` appears in a fixture
inside `test_leakguard.py` itself, and **the new check reported a leak that was
its own test data.** It reads `pwd.getpwuid(os.getuid()).pw_name` now, which
does not move when `HOME` does. Both the fix and the reason are in the file.

**Then a substring test reported 86 of 118 files**, for the `time`/`estimate`
reason above. That is the third check I have written today that fired for a
reason other than the one it named. The command-line grep I confirmed the
finding with had `\b` in it from the start; the check I wrote did not.

### What this does not fix

The name is already in public history: **48 commits, 40 of them carry it**,
and the same is true of linux — 85 commits, 70 of them, back to 21 October.
A fix at the tip cleans the tip. Rewriting two public repos is his decision
and it is with him with the numbers; it is not a thing to do on a peer message.
`browser-android` is the only clean baseline of the four, because it was
scrubbed before its first commit — which is the whole argument, and the only
moment the cost is zero.

Upstream still carries it: linux's `origin/main` has the identical counts, 39
in `test_forms.py`, 3 in `theme_web.py`, 1 each in `tests/harness.py` and
`test_keyboard.py`. The substitutions are this edition's shield, not the fix.

### And the sweep caught the report about the leak

`gitguard/sweep.py` arrived while this was being written — the resting-state
check, because `pre-commit` scans staged content and `pre-push` walks the
pushed commits, and **neither answers "is this repository clean"**. First run
on this tree, after the 13 files were done:

    gitguard sweep: 23 pattern(s) from personal.txt
      \btim\b   QA-REPORT.md   1

One occurrence, in the paragraph of this report explaining the leak. Fixed,
and worth leaving written down: a hand-grep said zero because I ran it before
writing the section, and the only thing that caught it was a check that looks
at the tree as it rests rather than at what is being added.

The hook refresh had the same shape. `gitguard`'s README says to copy
`template/hooks/pre-commit` into `.git/hooks/` — which in this repo replaces
the **dispatcher** that runs both `10-gitguard` and `20-pages`, silently
dropping the pages check. The dispatcher's own comment predicts it by name.
The template's `pre-commit` is byte-identical to this repo's `10-gitguard`,
so the only new file was `pre-push`; it went into its own slot and the chain
is intact — `10-gitguard`, `20-pages`, dispatcher unchanged.

### A port is already blocked, and not by this

Measured while proving the substitutions leave no drift: of 115 `copy_files`
compared against the base plus substitutions, **6 drift — and all 6 were
already drifting at `HEAD`** (`settings.html`, `history.html`, `player.html`,
`privacy.py`, `test_dev.py`, `test_media2.py`). Today's edits introduced
**zero**. Those six are the stale-base problem from the other direction: the
pages came through `pages.py port` and the base is a pre-rewrite twin 83
commits behind `origin/main`, so a port run today would refuse regardless of
anything here. `win_port.py --check` already says which commit to repoint at.

## Section 12, the two questions that were still open — answered

Both were queued this morning as *specified, scripted and unanswered*. His
brief for this is numbers, not adjectives, so these are deltas off each run's
own baseline — the two runs booted differently (3 helper processes at one
baseline, 8 at the other) and mixing their absolutes would be meaningless.

### Closing tabs: not a leak

30 tabs opened and closed, twice, because one cycle cannot tell a warm-up cost
from accumulation:

    A baseline              main=163.9  helpers=127.7  nhelpers=3   total=291.6
    B 30 open   (cycle 1)   main=187.3  helpers=452.5  nhelpers=33  total=639.8
    C all closed (cycle 1)  main=197.8  helpers=130.6  nhelpers=3   total=328.4
    B 30 open   (cycle 2)   main=188.0  helpers=456.0  nhelpers=33  total=644.0
    C all closed (cycle 2)  main=198.6  helpers=133.9  nhelpers=3   total=332.4

**The renderers come back whole** — 452.5 → 130.6 MB and 33 helper processes
→ 3, twice over. The main process does not return to baseline: **+33.9 MB**
after the first cycle. But the second identical cycle adds **+0.8 MB**, not
another 34. That is the distinction this test existed to make: a one-time
cost, not accumulation. 0.8 MB over 30 tabs opened and closed is 27 KB a tab —
caches and allocator arenas, not tabs that were never let go.

So the 46.8 MB the earlier sleeping-50-tabs run could not explain is the same
one-time cost, and **sleeping is not hiding a leak**.

**A third cycle, run because two cannot rule out a slow climb, and because
linux asked to be told if it kept going.** It does not — the increment decays:

    A baseline              main=168.5
    C all closed (cycle 1)  main=201.2   +32.7 from baseline
    C all closed (cycle 2)  main=202.0   +0.8
    C all closed (cycle 3)  main=202.3   +0.3

+32.7, +0.8, +0.3. Converging, not linear; a leak is flat or growing per
cycle, and this halves. It is also an independent reproduction of the whole
experiment off a different baseline (168.5 against 163.9), and the two agree:
+32.7 against +33.9 for the first cycle and +0.8 against +0.8 for the second.
Same shape as linux's own reading on 20 tabs, +16.8 / +0.6 / +0.1.

**But something else is linear, and it is not the process I was watching.**
The three surviving helper processes grow every cycle:

    helpers after cycle 1   135.1
    helpers after cycle 2   137.8   +2.7
    helpers after cycle 3   140.6   +2.8

`nhelpers` is back to 3 each time, so this is not processes left behind — it
is the three permanent ones (GPU, utility, zygote) holding ~2.7 MB more after
each round of thirty. Flat increments, where the main process's decayed. Three
points is thin and those processes legitimately cache, so this is **not filed
as a leak**: it is the one number in the experiment that does not look like it
converges, 2.7 MB per thirty tabs opened and closed is 90 KB a tab, and at a
hundred rounds it would be 270 MB. The test is more rounds, which is cheap and
is the obvious next measurement rather than a conclusion.

### The pane cache: 21 MB and one renderer each, and nothing is given back

The first run measured seven openers together at +178 MB, and I nearly divided
by seven. **Two of the seven are not panes**: `open_notes` and `open_player`
go through `_build_panel`, the side panel, which is why only five were ever in
`_panes`. Measured again, one at a time:

    A baseline                    total=340.9  main=205.9  nhelpers=3  cached=0
    after settings, dismissed     total=392.4  main=214.8  nhelpers=4  cached=1   +51.5
    after history, dismissed      total=412.2  main=220.1  nhelpers=5  cached=2   +19.8
    after downloads, dismissed    total=435.2  main=230.5  nhelpers=6  cached=3   +23.0
    after bookmarks, dismissed    total=459.6  main=242.6  nhelpers=7  cached=4   +24.4
    after passwords, dismissed    total=475.9  main=249.6  nhelpers=8  cached=5   +16.3

Reproduced: a second run of the seven-opener form gave total 511.4 against
510.5, 10 helper processes both times, the same five cached.

**+135.0 MB for the five, one extra renderer per pane, monotonic, and none of
it released when the pane is dismissed.** `settings` costs 51.5 MB on its own,
roughly double the others — it is by far the biggest page. The remaining ~43
MB of the seven-opener figure is `notes` and `player` in the panel, which
reconciles the two runs.

**This is the trade the brief names, and both sides are real.** A pane that
opens instantly, against 135 MB and five renderers held for pages nobody is
looking at. It is not a bug: `_panes[name]` is built on first use and reused
by design, and the W-B11 work earlier today depends on that cache existing.

**The fix already exists upstream and this tree does not have it.**
`free_idle_panes` is in linux's `origin/main` and not in `browser-windows` —
the one mac measured at 454 MiB given back. That makes it the fifth thing a
single port run closes, alongside `theme_web.py`'s real fix, the
`test_toolbar` and `test_reading2` rewrites, and the five adopted suites. It
is also the answer to the trade rather than a choice between its halves:
freeing a pane that has not been looked at for a while keeps the instant open
for the pane he actually uses and gives the other four back.

Not measured, and worth saying rather than estimating: how long
`free_idle_panes` waits, and what it costs to rebuild a freed pane on the next
open. Both are answerable here once the port lands.

## The sweep now reports this tree, and it is right to

`gitguard/sweep.py` grew a fix tonight — its `walk()` used
`ls-files --exclude-standard`, so **gitignored files were invisible to it**.
With that closed, this tree reports `rc=1`: two patterns, seven occurrences,
all of them in `.bughunt/PREAMBLE.md` — his home path twice and his name five
times. (Not quoted here; quoting a pattern into this file is how the last
round went wrong.)

`.bughunt/` is another session's working notes about this repo, untracked and
listed in `.git/info/exclude`. **Verified rather than assumed that it cannot
get out:**

  - git cannot carry it — ignored means never committed, and it is absent
    from an `actions/checkout` entirely, so CI never sees it.
  - the installer cannot carry it either. The bundle's `--add-data` patterns
    are root-level globs (`*.html`, `words-*.txt`, `browser.py`, `icon.*`)
    plus the named `backgrounds` directory; run them and 14 files match, none
    under `.bughunt`. A root-level `*.html` cannot reach into a subdirectory.

So the file is unreachable by every path that leaves this machine — and the
sweep still reports it, because the claim a sweep makes is *"this repository
is clean"* and it is not. That is the tool working. **The file is left where
it is:** deleting another session's notes to turn a guard green is making the
guard green rather than the tree clean, which is the move this report has
spent all day arguing against. `rc=1` with a named, measured, non-escaping
cause is worth more than a green nobody can explain.

Noted for whoever owns `.bughunt/`: a gitignore says *"do not commit this"*,
not *"this holds nothing of his"* — and a tar of a working tree, or a glob
less careful than this one, does not read it at all.

## W-B20 — `_boot.py` leaks a profile directory per run, into RAM

Found while checking a peer's `/tmp` report, and the evidence was already
written in this tree by whoever hit it the first time.

`_boot.py:18` makes a scratch profile and never takes it away:

    SCRATCH = Path(tempfile.mkdtemp(prefix="browsershot-"))

No `atexit`, no `rmtree`, nothing. Its sibling `tests/harness.py:22` has
`_tidy_scratch()` doing exactly that job for its own `browser-pwtest-` prefix,
and its docstring describes the consequence in detail — *"every run left its
directory behind, and a profile with a cache in it is 70-80 MB. After a few
hundred runs /tmp was full."* **The fix is in the module next door and was
never applied here.** Same shape as everything else today: the behaviour is
written down, and the code beside it does something else.

Measured rather than taken:

    /tmp                          tmpfs, 7.6 G, 4.5 G used, 60%
    browsershot-* directories     1348, of which 753 made today
    their share                   2.0 G
    newest two                    18:49 and 18:51 — this session's own runs

`/tmp` is a tmpfs, so that 2.0 G is **RAM**, which puts it squarely in the
brief this report's Section 12 work is for.

**And it did not cause the segfault, which I want on the record because the
docstring makes it tempting.** `_tidy_scratch` says a full `/tmp` shows up as
*"the last few tests of a suite segfaulting and timing out"* — which is
exactly `test_favorites`' exit 139. But there were **3.1 G free** at the time,
so the mechanism was available and the condition was not met. `test_favorites`
stays unexplained rather than being given a cause that fits the story.

`_boot.py` is in `copy_files`, so this is upstream's to fix and the fix is
`_tidy_scratch`'s shape with the other prefix. Not hand-edited here for the
same reason as `test_toolbar` and `test_reading2`: a newer copy trips the
drift check, and a green on this side would hide it upstream. Upstream's
`origin/main` copy has no `atexit` or `rmtree` either.

The 1348 directories are **not deleted**: `/tmp` is outside `~/claude`, and
the rule for this machine is that files outside it are not touched without
being asked. Reported, with the numbers, and it is already with him.

## The one guard that would have caught six of today's mistakes

Not a bug in the browser. The most repeated mistake of the day was mine and
three other sessions', and it has one shape: **a probe that cannot find what
it claims to look for, reporting the absence as a clean result.**

    a grep for a string the source wraps across two lines     all five "stale"
    a substring test for a three-letter name                  86 of 118 files
    a username read from $HOME under a throwaway HOME         matched its own fixture
    a .replace() on an anchor the file does not contain       "SILENT -- the bug"
    pgrep -f matching the waiting shell's own command line    20 minutes, twice
    `... | grep FAIL; echo exit=$?`                           reports grep's status

Every one returned something that read like good news. Four of the six were
*about* the checks written to stop exactly this.

The fix is one line, and it is mechanical rather than a thing to remember:

    assert src.count(old) == 1, "anchor missing -- the probe would " \
                                "have tested nothing again"

Make the probe fail loudly when its anchor is absent. `runall.sh` opens with a
nine-line warning about the pipe trap and it was still walked into three times
in the repo that carries the warning, twice here. A warning is read once; an
assert is typed every time.

**And the detection path that worked best was not re-reading.** Of the six,
the ones I caught myself I caught by noticing a *second* signal disagreeing
with the first — stdout empty when it should not have been, a flat number
across fifty times the tabs. One was caught by a teammate's result
contradicting the probe, and the right move there was to check their claim
rather than conclude they were wrong.

## Bugs found and fixed during this pass

Each was invisible in the same way: a call into something that does not exist, or
a forgiving fallback returning a plausible wrong value.

| ID | What | Severity | State |
|---|---|---|---|
| W-B01 | `history.html` rendered nothing — orphan `getElementById("v_searches")`, and the port needed `Bridge.siteIcons` which this edition did not have | Critical | fixed |
| W-B02 | `player.html:203` called `bridge.playerQueue` unguarded; the method does not exist, so **every** player open threw | High | fixed |
| W-B03 | Sleeping tabs veiled in black — `theme_color("base")` is not in `THEME_SOURCE`, so `#000000` on **116 of 116** themes, visibly wrong on the 30 light ones | Medium | fixed |
| W-B04 | 17 UI strings the pages ask for and the table never had, including `micTestTitle` vs `mictestTitle` — one capital apart, so the browser *had* the string and the page could not find it. `translateLang` defaults to `de`, so the microphone page was English **for the default user** | Medium | fixed |
| W-B05 | `settings.html:4510` calls `refreshSettings()`, which is defined in `start.html`. Seven Appearance buttons do their work and never refresh the page | Medium | **OPEN — upstream** |
| W-B06 | `#11111b` on `mictest.html:25`, the mic meter track, is not in `THEME_SOURCE`, so it stays near-black on all 116 themes | Low | **OPEN — upstream** |
| W-B08 | `download_dir(create=True)` creates the folder the user *chose* and returns the **default** without creating it. On a machine with no `~/Downloads`, it hands back a path that does not exist — and the docstring's whole point is that `create=True` conjures the folder up | Medium | **fixed** |
| W-B09 | `pretty_url()`'s `xn--` branch is dead — `QUrl.host()` already decodes, so the test is never true — and its comment credits decoding with the homograph protection when decoding is the hazard. ~~Not a security hole here~~ — **see W-B10, I cleared this on a grep and the grep lied** | Low | **OPEN — upstream** |
| W-B07 | Settings → Performance offers *"Sleep background tabs before the machine swaps"* with the hint *"Reads the kernel's own memory-pressure figure (PSI)"*. Windows has no PSI and no `/proc`, so that half can never fire — the switch goes on and the timer runs for nothing | Medium | **OPEN — upstream** |
| W-B10 | **Neither of the address bar's two security marks has ever been shown.** `update_bar_marks` did `QUrl(str(url))`; `str()` of a QUrl is its Python repr, which parses to an empty everything. Every real navigation arrives as a QUrl, so host was always `""` — the look-alike badge *and* the plain-http **Not secure** badge were hidden on every page load. Every http page looked exactly like an https one | High | **fixed** |
| W-B11 | The seventh tool dispatcher never tinted. Six call `tint_js`; `dev_tool` did not, and `DEV_TOOLS.update(DEV_TOOLS_PAGE)` makes it the **only** route to the five overlays that were normalised to tokens so they could be tinted — the ruler readout, hidden-field notes, perf box, key viewer, outline tints. Mocha over a latte window | Medium | **fixed** |
| W-B12 | Three more tool tables paint and are never tinted — `PAGE_TOOLS` (back-to-top button, edit badge, visited-link recolour), `MEDIA_TOOLS` (volume OSD), `READER_TOOLS` (hint markers). Their literals are not tokens either, so tinting them is a no-op until someone decides which are the browser speaking | Low | **OPEN — needs a product call** |
| W-B13 | **The badge W-B10 brought back was being painted over.** `_sync_acct` writes the bar's text margins from two guesses of its own, and `_url_changed` calls it the line *after* `show_address` — so every navigation threw away what `place_bar_extras` had just worked out. Measured: left 271 → 0 with the look-alike badge up, right 52 → 28 | High | **fixed** |
| W-B14 | The account handle and the lock button were drawn on top of each other — `_place_acct` moves the handle to x=5, `place_bar_extras` puts the lock at x=4, both 20px wide. **19px of 20 overlapping**, and neither had any margin of its own | Medium | **fixed** |
| W-B15 | The address bar showed a decoded homograph as the real domain — `https://аpple.com/` for `xn--pple-43d.com`. This is what made W-B09 more than cosmetic. mac's `idn_safe_to_show` existed and this tree did not have it | High | **fixed** |
| W-B16 | `test_reading2.py` asserts the literal `cba6f7` as the syntax highlighter's keyword colour. The off-palette work moved it off that off-palette purple onto `accentLt` (`#b4d0fb`), so the check fails. **Upstream shipped this red** — linux's `99d6deb` and their copy of the suite still has the old literal | Low | **OPEN — upstream, and red here** |
| W-B17 | The alt-drag link box took its **border** from the themed payload and filled with a hardcoded `rgba(137,180,250,0.12)` on the line below — mocha's accent at 12%. The outline moved with the theme and the fill did not, on **115 of 116**. `NAV_JS` is injected with `setSourceCode`, so nothing tints it; the colour has to be sent | Medium | **fixed** |
| W-B18 | `MEDIA_TOOLS.wheelvolume` (volume readout) and `PAGE_TOOLS.edit` (edit badge) painted in `#000`/`#fff` — three-digit, which `_recolor` cannot match at all — and their dispatchers never tinted. Normalised and tinted in the same edit, in that order | Medium | **fixed** |
| W-S02 | Five suites adopted from other editions were in **no** list in `win_port.json` — not `copy_files` (the port would raise), not `win_only` (they are not ours). A file in no list reads exactly like a file that is handled | Low | **fixed** |
| W-B20 | `_boot.py:18` makes a scratch profile with `mkdtemp` and never removes it — no `atexit`, no `rmtree`. `tests/harness.py` has `_tidy_scratch()` doing exactly that for its own prefix, with a docstring describing this consequence. **1348 directories, 2.0 GB, and `/tmp` is a tmpfs, so that is RAM** | Medium | **OPEN — upstream** |
| W-B19 | Two injected lines draw in `W.accent` while their dead fallback names a different token: the find-in-page hit marks on the scroll rail (`#f9e2af` = `yellow`) and the accessibility checker's **no alt text** outline (`#f38ba8` = `red`). Both render in the link/focus colour, so neither reads as what it is. The payloads send only `accent`/`bg`/`text`, so the fallback is the only record of the intent | Medium | **OPEN — needs the payload first** |

**W-B08 detail**, and the fix. The docstring's whole distinction is that
`create=True` conjures the folder up; the code honoured that only for a folder he
had *picked*. The one path never created was the default — which is also where a
picked folder on an unplugged external disk falls through to, the case the
docstring itself names ("or picked one that has since gone away").

Proved in a throwaway `HOME` with no `Downloads`, both directions, because
`create=False` has a promise of its own that a careless fix breaks:

                                   before fix   after fix
    create=True,  folder exists after  False        True
    create=False, folder exists after  False        False      (must stay False)
    chosen folder still made                        True
    chosen unmakeable → default made                True
    impossible default raises                       None

`if create:` + `DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)` in a try,
falling through on `OSError` — best effort like the branch above, since a
download into a folder that cannot be made fails either way and raising there
would take the window with it.

**Windows makes this worse, not better.** `DOWNLOAD_DIR` here is whatever the
shell's `FOLDERID_Downloads` answers (`_windows_downloads`), and Explorer lets
anyone move that onto another drive: Properties > Location. A moved Downloads on
a disk that is not mounted is the same absent folder. **UNVERIFIED — never
executed:** no Windows machine exists here, so that is read off the API contract,
not seen. The comment is pinned as port marker 60 so a regeneration cannot drop
it quietly.

Guard: `test_downloaddir.py`, adopted from linux rather than written again — the
bug is invisible on any machine that happens to have a `Downloads`, so the suite
has to **make** that environment rather than find it. 14 checks, and it bites:
**3 FAIL** against this repo's `HEAD` copy of `browser.py`, 0 after. It is also
why mac's reading and media suites passed at 11:13 and failed at 13:00 on
identical code — not flakiness, the throwaway `HOME` they were handed.

Then the nine suites that touch `download_dir`, `save_article` or `downloadDir`
re-run in a `HOME` that started with **0 entries** — the environment that used to
decide the result: `test_capture2`, `test_files`, `test_downloads`, `test_gaps3`,
`test_read3`, `test_reading2`, `test_saveimage`, `test_tools3`,
`tests/test_private`. All nine exit 0, 0 FAILs. Afterwards that `HOME` holds one
entry — `Downloads` — which is the fix doing its job under a real suite rather
than under a probe.

**W-B10 detail — driven, not read, and reproduced twice.** The probe records
every `show_address` call, because an empty bar has two possible causes and only
one of them is this bug. First run of the probe the bar was empty and the mark
hidden — and the bar was empty because the address bar had focus, so
`_url_changed` skipped `show_address` entirely. A hidden mark there proves
nothing. Cleared the focus and ran it again:

    urlbar has focus: False

    (A) one ordinary http page load, through the real signal
        show_address calls : 1
          handed a QUrl  PyQt6.QtCore.QUrl('http://127.0.0.1:44589/plain')
        bar shows          : 'http://127.0.0.1:44589/plain'
        'Not secure' shown : False        <-- the bug
    (B) a second navigation, same tab
        show_address calls : 1
          handed a QUrl  PyQt6.QtCore.QUrl('http://127.0.0.1:44589/two')
        bar shows          : 'http://127.0.0.1:44589/two'
        'Not secure' shown : False        <-- again
    (C) the SAME url handed in as a string
        'Not secure' shown : True  'Not secure'

So the function works; it was never given anything to work with. The bar text was
right the whole time because `bar_display_text` nine lines above has the tolerant
form — which is what made the method look healthy.

    str(QUrl('http://127.0.0.1/plain'))        "PyQt6.QtCore.QUrl('http://…')"
    QUrl(str(that)).host() / .scheme()         '' / ''
    QUrl(that.toString()).host() / .scheme()   '127.0.0.1' / 'http'

**30 sites** in this tree used `QUrl(str(...))`; the same count as linux. Five
were wrong in ways with a user-visible cost: `update_bar_marks`, the
`show_address` tooltip (it was showing the Python repr of his own URL),
`save_link_target` (scheme `""` is not https, so Alt+click-to-save and
save-image-as saved nothing), and the `group_rule_for` / `session_rule_for`
lookups (host `""`, so a rule he wrote never matched a tab opened with a QUrl).
Fixed the class rather than the five: one module-level `as_qurl(url)`, all 30
sites through it, adopted from linux's `62e5819`. `Browser._host_of` has existed
all along for exactly this, and its docstring says *"every place that takes
either has to come through here"* — 30 places did not, because the broken form
looks like the careful one.

One extra defect the fix uncovered: `update_bar_marks` never called
`place_bar_extras()`, whose own docstring says it is asked *"whenever one of them
appears"*. A mark that showed would have kept default geometry on top of the lock
button and painted over the start of the address. Nobody could see it because
nothing ever showed.

After: `test_barmarks.py` (adopted from linux) **40 checks, all ok**, and the
driven probe re-run — `'Not secure' shown : True` on both navigations.

**W-B11 detail — a green check that proved nothing, which is what the guard was
for.** Porting linux's off-palette work normalised five `DEV_TOOLS_PAGE`
overlays from upstream Catppuccin's `#11111b` to real tokens, and
`test_offpalette.py` went green: check 2 says no snippet holds an off-palette
colour (true), check 3 says `tint_js` moves them on a light theme (true, in
isolation). Neither asks whether the code that runs them calls `tint_js`.

Swept every tool table rather than checking one, and the table is the finding:

    DESK_TOOLS      13 snippets,  1 paints   dispatcher 32470   tint_js: YES
    READ_TOOLS      22 snippets,  7 paints   dispatcher 33225   tint_js: YES
    MEDIA_TOOLS2    34 snippets,  2 paints   dispatcher 34208   tint_js: YES
    PLAY_TOOLS      16 snippets,  4 paints   dispatcher 35734   tint_js: YES
    FORM_TOOLS      18 snippets,  0 paints   dispatcher 36856   tint_js: YES
    FILE_TOOLS       5 snippets,  0 paints   dispatcher 39698   tint_js: YES
    DEV_TOOLS       19 snippets,  7 paints   dispatcher 41529   tint_js: no
    PAGE_TOOLS      16 snippets,  3 paints   dispatcher 25729   tint_js: no
    MEDIA_TOOLS     16 snippets,  1 paints   dispatcher 25888   tint_js: no
    READER_TOOLS     7 snippets,  1 paints   dispatcher 28583   tint_js: no

Driven with a real window, three themes, three overlays, before and after:

    theme    overlay background, before fix      after fix
    latte    rgba(13, 13, 18, 0.95)   mocha      rgba(239, 241, 245, 0.95)
    frappe   rgba(13, 13, 18, 0.95)   mocha      rgba(48, 52, 70, 0.95)
    mocha    rgba(13, 13, 18, 0.95)              rgba(13, 13, 18, 0.95)

Read off `getComputedStyle(...).backgroundColor` in the page, not off the
snippet's text, and each theme's own `surface`. `#0d0d12` is mocha's surface, so
on mocha nothing moves — which is the half that made this invisible.

**The guard's own blind spots, three closed and one proven open.** Took
linux's patch for `test_offpalette.py` by hand (their file had already moved, so
the hunks went in against mine) — 16 checks to **18**, and three ways it used to
pass for the wrong reason:

  - `HEX` matched six digits only, so a tree with `#000` block pages read
    *"all ok"*. `_recolor`'s own regex is six-digit too, so a three-digit
    literal can never be swapped **even where the tint runs** — worse than an
    off-palette six-digit one, not more forgivable.
  - a token's own hex was excused inside a generated page. Right for the
    snippets, which go through `_recolor`; wrong for the pages, which are
    string-formatted and never recoloured. `#000000` there only happens to
    equal `bg` today.
  - the exemption list was global, so a `#ffffff` written for Minecraft chat
    excused a white background anywhere. Now keyed `(literal, where)`.

Mutation-tested here, each with only that one thing reverted:

    dev_tool's tint_js removed        FAIL (6) ['DEV_TOOLS']
    focus page back to #000           FAIL (1) #000, #cdd6f4, #89b4fa in focus_page
    a #fff background in diff_html    FAIL (1) '#fff in diff_html'
    a #111 in DESK_TOOLS.counter      FAIL (2) three-digit + (5) surface
    winfull's letterbox to #00f       FAIL (2) three-digit
    twitchgrid's letterbox to #0f0    FAIL (2) three-digit

**And one that did not fail, which is the second half of W-B12.** The first
aim of that last mutation hit `PAGE_TOOLS.edit` instead of the letterbox and
passed, so I re-aimed it and then tested the gap deliberately:

    #11111b added to PAGE_TOOLS.totop     all ok      <-- invisible
    the same #11111b in READ_TOOLS        FAIL (2)    <-- caught

`TOOLS` in the suite names seven tables; the tree has ten. So the three cold
tables are not only undecided, they are **unswept** — an off-palette literal
added to `PAGE_TOOLS`, `MEDIA_TOOLS` or `READER_TOOLS` tomorrow is invisible to
the guard that exists for exactly that. Same shape as `test_contrast.py`'s
`sheets()` listing six of nine pages. Reported upstream.

**W-B13 / W-B14 detail — the fix I shipped was being painted over.** The
previous commit brought both bar marks back and I checked they appeared. I did
not check that anything could be *read*. Two writers of the same property:

    place_bar_extras   computes the margin from the lock, both marks and the
                       four right-hand buttons that are actually showing
    _sync_acct         writes 24-or-0 on the left from the account handle
                       alone, and 28-or-0 on the right from the star

`_url_changed` calls `show_address` (which reaches `place_bar_extras`) and then
`_sync_acct` three lines later, so `_sync_acct` always won. Driven, three URL
kinds, the real methods:

                              after show_address   after _sync_acct
    a look-alike domain       left=271 right=52    left=0   right=28
    a plain http page         left= 95 right=52    left=0   right=28
    an ordinary https page    left= 24 right=52    left=0   right=28

The badge is 243px wide and starts at x=26. With left=0 the address is drawn
from the very start of the bar, straight across the badge and the lock button.
The https row is the one worth noticing: **even with no mark at all**, the 24px
that reserves the lock button went to 0, so the address has been painted over
the lock on every ordinary page, which long predates anything today.

And in measuring that I found W-B14: `_place_acct` moves the handle to x=5 and
`place_bar_extras` puts the lock at x=4, both 20px wide.

    lock         visible=True  x=4   w=20   spans  4..24
    acct handle  visible=True  x=5   w=20   spans  5..25
    overlap      YES, 19 px

After: lock 4..24, handle 26..46, margin 46, overlap none — and the margins
survive `_sync_acct` and the full `_url_changed` (271 stays 271, 95 stays 95,
24 stays 24, right stays 52). `place_bar_extras` owns both margins now and
`_sync_acct` asks it, falling back only before the extras exist.
`test_barmargins.py` adopted from linux: **26 checks, all ok**.

**W-B15 detail.** `test_barmargins` arrived with one failure this tree earned
on its own: *"the bar shows the punycode, not the look-alike"* — it showed
`https://аpple.com/`. The badge warned and the text still read as Apple. mac
wrote `idn_safe_to_show` for exactly this and three trees had it; mine did not,
which is the thing that made W-B09 more than a dead branch. Ported with its
suite (`test_idn.py`, 0 failed) and the check now reads
`<https://xn--pple-43d.com/>`.

**W-B16, and upstream shipped it red.** `test_reading2.py` asserts the literal
`cba6f7` as the syntax highlighter's keyword colour:

    FAIL the keyword is coloured, not the whole block
         <<span style="color:#b4d0fb">def</span> …>

`#cba6f7` is **off-palette** — it is the colour picker's "Purple" and the
default `privateTint`, exempted by name in the guard — so the off-palette work
moved the keyword onto `accentLt`, `#b4d0fb`, which is right. The suite was not
updated with it. `grep -n cba6f7` in linux's own `test_reading2.py` still finds
line 240, and `99d6deb`'s message says *"test_themetokens and test_downloaddir
still exit 0"* — those two were run, this one was not. So the red is upstream's
and mine is honest: `test_reading2.py` is in `copy_files`, so hand-editing it
here would make the next port raise, and a green on my side would hide their
red. Reported, left red, cause recorded.

The fix, when upstream takes it, should not be the new literal: a check named
*"the keyword is coloured, not the whole block"* that asserts a hardcoded
theme hex is the same class of bug the guard was written for.

**W-B17 / W-B18 detail, and the thing that made them takeable.** Adopting
linux's `test_offpalette.py` again — it went 18 checks to **35** — found four
failures on this tree, all real:

    no three-digit colour, which _recolor cannot swap
    every short literal left in a snippet has a written reason
    every colour is a payload fallback or a named exception
    the snippet reads it from the payload now

The first two are `#000`/`#fff` in `MEDIA_TOOLS.wheelvolume` and
`PAGE_TOOLS.edit`. Three-digit is the worse spelling: `_recolor`'s regex is
six-digit, so those could never be swapped even once a dispatcher tinted them.
The last two are the alt-drag link box: `border:1px solid (W.accent || …)` on
one line, `background:rgba(137,180,250,0.12)` on the next. Measured here —
**exactly one of 116** themes has `#89b4fa` as its accent, so the fill was
wrong on 115. `NAV_JS` is injected with `setSourceCode` and nothing tints it,
so the colour has to be sent: `nav_payload` carries `accentSoft` now and the
snippet reads it, byte-identical on mocha.

I had told the crew I was holding these back until upstream committed them,
because normalising a literal is a product decision and nobody had measured
it. The suite is what changed that: it measures both, and prints the number —
`MEDIA_TOOLS.wheelvolume reads on every theme  <worst 10.59:1 of 116>`. With
the contrast proven on all 116 the decision is no longer a guess, and holding
back would have left this tree failing its own guard for no reason.

Order mattered and the suite enforces it: normalise the literals *and* tint
the dispatcher in one edit. Tint first and it is `dev_tool` again — a call
that goes green and changes no pixel. Normalise first and check (6) flips the
table from *"cold, nothing to swap"* to a failure, which is what it did.

`READER_TOOLS` is still deliberately cold and still his call: the suite now
carries the three pen literals in a `PENDING_AT` list that fails if an entry
stops matching anything, so an undecided item cannot quietly become invisible
the way an exemption can.

**W-S02 — the same disease in my own manifest.** Five suites adopted today sat
in **no** list in `win_port.json`. Not `copy_files`, because `win_port.py`
raises on a name missing from `~/browser`; not `win_only_files`, because they
are not ours and claiming them would stop the port ever reconciling them. So
nothing clobbered them and nothing reconciled them either — a file in no list
reads exactly like a file that is handled.

`adopted_pending` names all five with where each came from, and
`tests/test_workflow.py` checks it four ways. Each proven by one mutation:

    dropped test_idn.py from the list    FAIL every suite on disk is in a list
    an entry naming a file that is gone  FAIL names nothing that is gone
    an entry with no reason              FAIL every entry says where it came from
    the same suite pending AND ported    FAIL nothing is both pending and ported

**W-B19 — a fallback that records an intent the key contradicts.** Swept all
20 blobs for `(W.x || "<literal>")` where the literal is a `THEME_SOURCE`
value, expanding three-digit forms first so `#fff` is compared as `#ffffff`:

    matching key and literal      11
    literal is not a token         1   NAV_JS (W.accentSoft || "rgba(137,180,250,0.12)")
    MISMATCHED                     4

    A11Y_JS   (W.accent || "#f38ba8")   literal is red
    NAV_JS    (W.accent || "#f9e2af")   literal is yellow
    A11Y_JS   (W.text   || "#fff")      literal is bright
    NAV_JS    (W.text   || "#fff")      literal is bright

**Two of the four are semantic and they are the bugs.** `#f9e2af` is `yellow`
and that line draws the find-in-page hit marks on the scroll rail; `#f38ba8`
is `red` and that line outlines an image with **no alt text**. Both draw in
`W.accent` instead — which on most themes is also the link colour and the
focus ring, so a search hit does not read as a search hit and a problem
marker does not read as a problem.

**The other two are not the same finding** and I am not filing them as one.
`(W.text || "#fff")` is a disagreement between `text` (`#cdd6f4` on mocha)
and `bright` (`#ffffff`), and which one was meant is genuinely ambiguous —
"pure white" is a defensible fallback for text. Reported as sloppiness, not
as intent lost.

Why none of it is visible: both payload builders send **three** colour keys,
`accent`, `bg`, `text`. No `yellow`, no `red`. So `W.accent` always arrives,
every fallback is dead code, and the fallback is the only surviving record of
what the line was for. The fix is two halves in order, the same trap as
normalise-then-tint: add `yellow` and `red` to the payloads **first**, then
change the keys. Change the key alone and `W.yellow` is undefined, the dead
fallback comes alive, and the line freezes to mocha's yellow on all 116
themes.

Found because the fallbacks were being counted for a different reason. The
check worth keeping is the one that catches the disagreement rather than the
style: *every `(W.x || "literal")` whose literal is a token's value must have
`x` equal to that token's name.*

Two refinements that came out of running it, and both argue for the human:

**`(W.text || "#fff")` is better left alone than filed.** On mocha `bright`
is `#ffffff` and `text` is `#cdd6f4`; on latte `bright` is **`#1b1c25`** — it
inverts. So "pure white as a fallback for text" would be wrong on every light
theme *if it ever ran*. Real ambiguity, zero consequence: exactly the
combination that should not become a ticket.

**And the check can pass while the payload disagrees with both.** Of the
three payload builders, one sends a different token than its key says:

    browser.py:55783  nav_payload         "bg": palette['crust']
    browser.py:57231  a11y_payload        "bg": palette['bg']
    browser.py:58174  page_look_payload   "bg": palette['bg']

So `W.bg` carries `crust` in `NAV_JS` and `bg` in `A11Y_JS` — the same name,
two colours, one builder out of three disagreeing with its siblings. On latte
that is `#e5e8ee` against `#dce0e8`, adjacent lights, invisible. Not filed:
the consequence is nil and picking which of the two is "right" is a decision
about what `W.bg` is supposed to mean. Recorded because it is the cleanest
demonstration that the literal-matches-key test can be green while the colour
behind it is a different token entirely.

**Why the injected scripts must never be tinted — measured, not assumed.**
Section 7 of the guard fixes `NAV_JS` by putting the colour in the *payload*,
not by tinting the blob, and that distinction turns out to be load-bearing.
There are **20** injected blobs in this tree. Running `tint_js(…, "latte")`
over each one, three would be damaged:

    A11Y_JS    el.style.color = bg > 0.5 ? "#000000" : "#ffffff"
                 #000000 -> #DCE0E8   #ffffff -> #1B1C25
                 rgb(255, 255, 255) -> rgb(27 28 37)
    NAV_JS     the full-screen backdrop behind an enlarged image
                 rgba(0,0,0,0.92) -> rgb(220 224 232 / 0.92)
    THEME_JS   two #000000 -> #DCE0E8, and these are the worst of all

`THEME_JS` is not a colour bug at all either — it is `_recolor`'s own twin,
the same algorithm in JS with the same shadow rule and the same 0.8 alpha
floor, and the two literals a tint rewrites are its two black branches:

    for (var lit in t.map) {
      hex[lit] = t.map[lit].toUpperCase();
      if (lit !== "#000000")            <-- keeps pure black OUT of the
        rgb[...] = t.map[lit];              rgb index, because rgb(0,0,0)
    }                                       means shadow or scrim
    ...
      if (!(av >= 0.8)) return lit;
      col = t.map["#000000"];           <-- "a near-opaque black IS the
                                            window's background"

`t.map` is keyed by the source literals — measured: 22 entries, `#000000`
is a key and maps to `#dce0e8` on latte, and **`#DCE0E8` is not a key**.
So a tint would put pure black *into* the rgb index and take latte's bg
out of it, and turn the second lookup into `undefined`. Both of
`_recolor`'s black rules break, in opposite directions, in the one place
that implements them for our own pages. The mechanism eats itself.

**And a third harm, in every blob: a tint rewrites the fallbacks.**

    -   ";background:" + (W.accentSoft || "rgba(137,180,250,0.12)")
    +   ";background:" + (W.accentSoft || "rgb(27 90 217 / 0.12)")
    -   (W.bg || "#000000") + " !important; }");
    +   (W.bg || "#DCE0E8") + " !important; }");

Nine such lines in `A11Y_JS`, four in `NAV_JS`. A fallback is what runs
when the payload does not arrive; freezing it to whichever theme was live
at injection is precisely the bug the fallback exists to prevent.

`A11Y_JS` is the worst of the three and it is not a colour at all: it is the
contrast rescue, which measures a page's own luminance and picks black or
white ink. Tinted, it picks **latte's light grey for a light background** —
it would invert the feature it implements. `NAV_JS`'s backdrop is the same
class as the video letterboxes: `rgba(0,0,0,0.92)` is above `_recolor`'s 0.8
alpha floor, so it reads as a paint and swaps, and a near-opaque light grey
behind a photo on latte is the bug. Pinned here as must-NOT-change.

This tree is correct today: **all nine `tint_js` call sites are tool-table
dispatchers** and no injected blob is tinted. That is worth a check rather
than a comment, because "nobody tints the blobs" is exactly the kind of fact
that stays true until someone adds a tenth call site — offered upstream as:
every `tint_js(` call site is a `*TOOLS*.get(name)` dispatcher, nothing else.

**The no-mark margin case, which neither suite asserts.** `test_barmargins`
is 26 green checks and every one of them has the badge present. The row that
was broken for longest is the one with no mark at all:

                              after show_address   after _sync_acct (before fix)
    a look-alike domain       left=271 right=52    left=0   right=28
    a plain http page         left= 95 right=52    left=0   right=28
    an ordinary https page    left= 24 right=52    left=0   right=28

Upstream's `place_bar_extras` reserves the lock *before* any mark is
considered — `4 + 20 + 2`, minus 2, is the 24 measured here — so it is
covered by construction. By construction is not by a check, and the third row
is the one a regression would hit first.

**Three things checked rather than taken.** All three arrived as a peer's
summary and all three needed measuring here:

  - **`PAGE_TOOLS.totop` must NOT be normalised.** Its fill is
    `rgba(20,20,20,.75)`; alpha under 0.8, so `_recolor` leaves it as a scrim
    — verified, `tint_js(…, "latte")` returns it unchanged. So only the ink
    could move, and over that unmoved scrim any text-ish token fails 4.5:1 on
    **30 of 116** themes. One correction to the number I was given: 28 of the
    30 are the light group, the other two are `character` —  `sepia` at
    **1.13:1** and `newspaper` at 1.91:1, both worse than any light theme. As
    it ships, `#fff` on that scrim is 9.30:1 on latte and 19.17:1 on mocha.
    Normalising the ink alone makes it worse than leaving it.
  - **The uppercase trap is real and this tree is clean.** `_COLOR_RE` has no
    `re.I`, so a capital literal can never be swapped: injecting `#0D0D12`
    into `READ_TOOLS.selbar` survives `tint_js(…, "latte")` where latte's
    surface is `#eff1f5`. Swept all ten tables and every generated page:
    **zero** uppercase literals. A trap, not a live bug — worth a guard, not a
    fix.
  - **android's localisation bug is not here.** AST-scanned every
    `_ui_str(...) % ...` for an English string literal in the argument:
    **0 sites**. Proven to bite first — injecting android's exact shape,
    `% ((what or host) + " (mixed letters)")`, reports
    `browser.py:40526 key=barLookalikeTip arg='(mixed letters)'`. The reason
    this tree is clean is visible at `browser.py:40524`:
    `kind, _colon, what = warning.partition(":")` keeps only `what`, the host,
    and throws the English `kind` away.

**W-B12 detail, and why it is open rather than fixed.** The other three untinted
dispatchers hold colours that are not tokens, so routing them through `tint_js`
changes nothing today — a call that looks like coverage and does nothing is the
exact shape this report keeps finding. Each needs a decision first:

    PAGE_TOOLS.totop        rgba(20,20,20,.75) + #fff   a button the BROWSER
                                draws — should follow the theme
    MEDIA_TOOLS.wheelvolume #000 + #fff                 a volume readout the
                                BROWSER draws — should follow the theme
    PAGE_TOOLS.edit         #000 + #fff                 same, an edit-mode badge
    READER_TOOLS.hints      #ffd866 on #000, #806000    a highlighter pen; a
                                marker colour may be deliberately not the theme
    PAGE_TOOLS.visited      #b48ead                     recolours the SITE's
                                visited links; arguably not ours to theme

The first three are the browser speaking and want normalising to tokens the way
linux did the other five. The last two are product calls, so they go to him
rather than being decided here.

**W-B09 detail, and a correction I got wrong in the safe direction.** What I
wrote here yesterday was: *"Not a security hole — `lookalike_warning()` is wired
to the address bar and fires on all three attacks."* **That was wrong, and the
way it was wrong matters more than the finding.** The guard fires when it is
asked. It was never asked. See **W-B10**; the honest grade for the pair is High,
and it is not an IDN finding at all.

What stands from the original W-B09: the `xn--` branch in `pretty_url` is dead
(`QUrl.host()` already decodes, so `startswith("xn--")` is never true) and its
comment credits decoding with the protection when decoding is the hazard. Still
Low on its own.

What does not stand is the evidence I used to clear it. I called
`lookalike_warning()` directly with host strings and watched it fire:

    xn--pple-43d.com    host аpple.com   → lookalike_warning 'mixed:аpple'
    xn--80ak6aa92e.com  host аррӏе.com   → 'script:аррӏе.com'
    xn--pypal-4ve.com   host pаypal.com  → 'mixed:pаypal'
    apple.com                            → ''  (quiet, correctly)
    paypal.com                           → ''  (quiet, correctly)

Every line of that is true and none of it was the question. The question was
whether the bar ever shows the badge, and for that I read the call sites — found
`lookalike_warning` defined at 1975 and called from the bar's own method — and
called it wired. **A grep tells you a line exists, not that it ever runs with a
usable argument.** The thing that found the real bug was driving the bar.

**W-B05 detail**, because of how quiet it is: `bridge.appearanceAction` *exists*, so
the theme really is saved, exported, starred or reset. Then the callback throws
`ReferenceError` and nothing re-reads. Save a theme and the list does not show it;
press Reset and the controls still show the old values. `window.onerror` sees
**nothing** — the throw is inside a Qt WebChannel callback, which does not route
through it. Present in all four editions at the same line.

## Guards added, so these classes fail a suite instead of shipping

| Suite | Asks |
|---|---|
| `test_histrender.py` | does every element a page dereferences exist? (ported — this edition shipped the bug and had no test for it) |
| `test_bridgecalls.py` | does every `bridge.X(` exist on `class Bridge`? Unguarded + missing fails; guarded + missing is pinned by name |
| `test_themetokens.py` | does every literal token handed to `theme_color` resolve? |
| `test_uistrings.py` | does every `STR.x` the pages ask for exist in the table? |
| `tests/test_workflow.py` | lints the PowerShell nothing here can execute |
| `tests/test_leakguard.py` | nothing of the user's is in any file a port writes |
| `tests/test_portbase.py` | the recorded port base is really an ancestor |
| `test_downloaddir.py` | does `create=True` create the **default** too, and `create=False` still create nothing? (ported) |
| `test_offpalette.py` | does every colour the browser PAINTS come out of the theme, and does the code that RUNS a snippet tint it? the inverse of test_themetokens (ported; 18 checks) |
| `test_barmarks.py` | does the bar's security mark fire for a QUrl as well as a string, and is `QUrl(str(…))` gone? (ported) |
| `test_barmargins.py` | does the margin that reserves room for a mark survive the rest of a navigation? drives the real widget (ported; 26 checks) |
| `test_idn.py` | is a mixed-script host shown as punycode rather than in its own letters? (ported) |
| `tests/test_workflow.py` | ...and every suite on disk is in exactly one of the port's file lists, both directions |

Each was made to fail on purpose before being trusted — the bug reintroduced in a
`git archive` copy, never in the tree.

## The suite measures itself wrongly — W-S01

**This is the most consequential finding of the pass, and it is about the
tests rather than the browser.**

`tests/harness.py`:

    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    return box.get("v")

`box.get("v")` returns `None` when the callback never fired — which is the
same value a page returns when it genuinely answers `null`. A timeout and a
real answer are indistinguishable, and 49 sites then coerce with
`js(...) or 0`, turning "I do not know" into a confident zero.

**Proof.** `test_perf2.py:286`, five runs in isolation on a quiet box:

    run 1  ok    ...and the page is near where it was  <240>
    run 2  ok    ...and the page is near where it was  <240>
    run 3  FAIL  ...and the page is near where it was  <240>
    run 4  ok    ...and the page is near where it was  <240>
    run 5  ok    ...and the page is near where it was  <0>

The assertion is `(js("window.scrollY|0", MAIN) or 0) >= 200` and the detail
is a second, separate `js()` call. Run 3 **failed while its own evidence says
240**, which is ≥ 200. Run 5 **passed while its own evidence says 0**, which is
not. Two of five runs disagree with the number printed beside them, in
opposite directions.

Run 5 is the one that matters: a green check that proves nothing, which nobody
will ever read.

**Blast radius, counted:**

| | |
|---|---|
| suites calling `js()` | 61 of 94 |
| `js()` call sites in them | 1200 |
| `check()` **verdicts** whose condition reads a `js()` value | **473** |
| of those, coerced with `js(...) or X` | 49 |
| suites defining their **own** `js()` with the same shape | 39 |

Most exposed: `test_a11y` 34 verdicts, `test_callguard` 29, `test_pageguard` 25,
`test_games` 23, `test_dev` 23 (16 coerced), `test_read3` 20.

**Status** FAIL — **High**. **OPEN — upstream** (`tests/harness.py` is in the
port set; a local fix is drift a port would overwrite).
**Suggested fix** Raise rather than return. A timeout is not a value, and all
473 verdicts are currently free to treat it as one:

    loop.exec()
    if "v" not in box:
        raise AssertionError("js() timed out after 5s: %s" % code[:80])
    return box["v"]

A suite that dies saying "js timed out" is telling the truth. A suite that says
"ok, scroll was 0" is not. The 39 private copies each need the same change, or
better, to call the harness.

**How far this goes, stated carefully.** This is very likely the explanation for
the four full runs below producing four red sets with zero overlap — each run a
different handful of those 473 verdicts lands on the wrong side, and 6 of the 8
flaky suites call `js()`. But what is *proven* is that the mechanism exists and
fires, not that it caused each specific red: `test_libs` and `test_permreload`
call `js()` nowhere and have some other cause.

## Suite status

**The baseline run, 2026-10-29 evening: 99 suites, 4 red, every one explained.**

| Suite | Reproduced | Cause | Whose |
|---|---|---|---|
| `test_toolbar` | **3/3 in isolation** | asserts `right==0` / `==28`, which were `_sync_acct`'s two removed guesses | fixed upstream |
| `test_reading2` | 2/2 | asserts the literal `cba6f7`, moved to `accentLt` by the off-palette work | fixed upstream |
| `test_screenshare` | every run today | `getDisplayMedia` has no screen under `offscreen`; identical at `9096244` | pre-dates all of this |
| `test_favorites` | **0/3 in isolation** | exit 139 inside the full run only; see below | unexplained |

**`test_toolbar` is the test pinning the bug, and here is the proof rather than
the claim.** Its two checks demanded `textMargins().right() == 0` with the star
hidden and `== 28` with it shown. Measured now:

    star shown     right=52   barcopy at 646 (w22)   text ends 648
    star hidden    right=26   barcopy at 672 (w22)   text ends 674
    star back      right=52

The star is 24 wide, so it frees exactly 26, and takes exactly 26 back. The bar
is 700 wide. **`right == 0` with the star hidden would run the address straight
under `barcopy`**, and `== 28` with the star shown would run it under both. The
two numbers were `_sync_acct`'s guesses, which is what W-B13 removed — so the
suite was asserting a bar that paints over its own buttons.

Upstream has already rewritten it as a *relation* instead of two constants —
the margin gives up exactly the star's room, takes it back, and what is left
still clears whatever else is in there — plus a check I did not have:
*"...but keeps the room the other buttons still need"*. Both reds are the same
shape and **one port run closes both**, which is why neither is hand-edited
here: `test_toolbar.py` and `test_reading2.py` are both in `copy_files`, and a
newer copy trips the drift check exactly as a hand-edit would.


99 suites — 87 at the root and 12 under `tests/` — plus two invariant blocks, which is where the "101" in an earlier draft of this report came from. Four full runs earlier today, and the red set had **zero overlap** between any
two of them:

    run 1   test_dev, test_themefix                        both pass alone
    run 2   test_downloads, test_libs, test_perf2, twostep  all pass alone
    run 3   test_bar, test_permreload                       both pass alone
    all     test_screenshare                                red every time

So the honest number is **1 real failure**, not 3–5. `test_screenshare` fails one
check, `picking a screen gives the page a live track`, `err:AbortError` —
`getDisplayMedia` under `QT_QPA_PLATFORM=offscreen` has no screen to hand it. It
fails identically at `9096244`, before any of this session's commits. Cause
formally unproven; left alone.

`tests/` is flaky under load and any single "N red" from a full run reads worse
than it is. Every red was isolated rather than quoted.

## Untested / blocked, and why

**No Windows machine or VM exists here.** That blocks, wholly or partly:

- **Section 1** — install time, onboarding, default-browser prompt, bookmark
  import, cold/warm launch time, and observing SmartScreen.
- **Section 2** — the dark title bar and whether native dialogs follow it, DPI on
  a 4K panel (the Qt rounding policy is `PassThrough`, measured in this tree's
  venv, but never *seen*), the font stack that leads with a Nerd Font no Windows
  machine has.
- **Sections 12, 13, 17** — Windows RAM and CPU, battery, NVDA/JAWS, high
  contrast, and all of mobile (that is the Android edition's).
- **Section 18** — what uninstall actually leaves behind.
- **All of `.github/workflows/build-exe.yml`** has been read and not run here.
  There is no `pwsh` on this machine and fetching a portable one was refused. CI
  has now executed it successfully, which is a better claim but a different one.

**Runnable here and not yet done:** Sections 3 (tabs/windows, session restore
after a forced kill), 4 (certificate errors via badssl.com, redirects, DNS
failure), 5 (standards and 20+ real sites), 6 (media and DRM), 7 (forms,
autofill, IME), 8 (downloads, EICAR), 9 (bookmarks/history/find-in-page), 11
(extensions), 15 (devtools), 16 (stability, tab-crash isolation, leaks over
hours), and the rest of 10.

**Not applicable:** Section 14 (sync & accounts) — **N/A: there is no account and
no sync.** That is a deliberate product decision, stated in the README, and
Section 10's trace is the evidence for it.
