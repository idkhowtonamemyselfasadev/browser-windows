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
looking at. Cost not yet measured; both sides go to Tim rather than a unilateral
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
count=3, both ending in the same `fatal`. Deterministic. Tim's find, confirmed.
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
| W-B08 | `download_dir(create=True)` creates the folder the user *chose* and returns the **default** without creating it. On a machine with no `~/Downloads`, it hands back a path that does not exist — and the docstring's whole point is that `create=True` conjures the folder up | Medium | **OPEN — upstream** |
| W-B09 | `pretty_url()`'s `xn--` branch is dead — `QUrl.host()` already decodes, so the test is never true — and its comment credits decoding with the homograph protection when decoding is the hazard. **Not a security hole here:** `lookalike_warning()` is wired to the address bar and fires on all three attacks | Low | **OPEN — upstream** |
| W-B07 | Settings → Performance offers *"Sleep background tabs before the machine swaps"* with the hint *"Reads the kernel's own memory-pressure figure (PSI)"*. Windows has no PSI and no `/proc`, so that half can never fire — the switch goes on and the timer runs for nothing | Medium | **OPEN — upstream** |

**W-B09 detail**, because a finding that says *"not a security hole"* needs its
evidence as much as one that says it is. The decoded host really does read as the
real domain — `pretty_url("https://xn--pple-43d.com/login")` returns
`https://аpple.com/login` — so the dead branch and its backwards comment are real.
What makes it Low rather than High is that the protection exists elsewhere and
works:

    xn--pple-43d.com    host аpple.com   → lookalike_warning 'mixed:аpple'
    xn--80ak6aa92e.com  host аррӏе.com   → 'script:аррӏе.com'
    xn--pypal-4ve.com   host pаypal.com  → 'mixed:pаypal'
    apple.com                            → ''  (quiet, correctly)
    paypal.com                           → ''  (quiet, correctly)

`lookalike_warning()` (browser.py:1975) does mixed-script detection, a
CONFUSABLES fold against a `WELL_KNOWN_HOSTS` list and a Cyrillic/Greek
catch-all, and `browser.py:40360` puts `barLookalike` in the address bar when it
fires. I had this written up as a High before I checked whether the user was
warned.

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

96 suites. Four full runs today, and the red set had **zero overlap** between any
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
