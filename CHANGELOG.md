# Changelog

## 2026-10-04 — Update never throws work away

- **Update no longer wipes uncommitted changes in a git copy.** When a
  pull could not fast-forward, it ran `git reset --hard origin/HEAD`:
  uncommitted edits were gone, unpushed commits dropped out of sight, and
  a feature branch was moved onto main - and it said "Updated!". Now it
  stops and says why when there are uncommitted changes, resets only onto
  the branch's own upstream, and keeps the old version as a branch
  `update-backup-<time>` first. Zip installs were never affected.

## 2026-10-04 — the Windows bug sweep

- **Logins survive closing the browser.** It used to end itself before
  Chromium had written its cookies to disk (it does that only every
  thirty seconds or so), so whatever you had just signed in to was
  forgotten at the next start. The cookie jars are now closed properly
  first.
- **No more see-through window.** Every look made the window
  translucent, and Windows does not blur what is behind one: the
  desktop showed straight through, with a strip under the tabs that
  filled with leftover junk. The window is solid on Windows now, Liquid
  Glass included — it keeps its shapes on the theme's own base.
- **Themes are readable again.** Most of the "unreadable" was text
  drawn over the desktop through that hole. The browser also uses one
  style of its own on Windows now, instead of Windows 11's, which mixed
  light system colours into dark themes.
- **Search suggestions no longer run into each other.** The highlighted
  row stands out, the scroll bar is dark, and the last row is no longer
  cut off.
- **Update works.** A fresh install did not know which version it was,
  so it always said "Update available" and "Updated!" changed nothing;
  it now checks its own files. The check no longer uses GitHub's API,
  which stopped answering after sixty checks an hour from one network.
  An update is written beside the old files and swapped in, so an
  interrupted one cannot leave a broken browser behind.
- **Saved passwords are no longer destroyed on Windows.** Windows
  quietly turned every line-feed byte in the password files into two
  bytes, so after a restart the vault read as empty or the master
  password was refused. Fixed — and a vault damaged that way is
  repaired the next time it is opened, so passwords that "vanished"
  come back, as long as no password was saved since.
- **A lost password key no longer costs the vault.** The vault it
  belonged to is put aside as passwords.json.unreadable-… instead of
  being written over, so restoring the key from a backup still opens it.
- **No more crash when a site joins a call** (Meet, Discord): a
  Linux-only option ended the browser on the spot.
- **A website can no longer install a plugin without asking.** A
  download named *.user.js went straight into the plugins folder and ran
  on every site from then on. You are asked first now, and No saves it
  as an ordinary download.
- **Your data files are written safely.** Settings, history, bookmarks,
  downloads and known sites are written beside the old file and swapped
  in, so a crash or power cut mid-save leaves the old file rather than
  half of one; a file that cannot be read is put aside
  (name.corrupt-…), not silently replaced with nothing.
- **Open tabs survive a crash.** They are saved every thirty seconds,
  not only when the browser closes normally.
- **An unexpected error no longer makes the window vanish.** The
  browser keeps going and writes what happened to crash.log in its data
  folder.
- 1Password: names and passwords with umlauts are no longer garbled, and
  no console window flashes up on every call.
- A second Windows user on the same PC can open the browser while the
  first has it open.
- Downloads go to your real Downloads folder, even when it was moved to
  another drive.
- install.bat makes the shortcut start the same Python it installed
  into; with two Pythons on the PC the shortcut used to do nothing.
- "Open in player" finds VLC where Windows installs it.
- Crash detection works on Windows.
- **Esc leaves video fullscreen.** It reached the video and the window
  stayed fullscreen; closing or leaving that tab stranded the window
  with no tabs and no address bar.
- **Shift+Tab moves back through a form again.** It was taken for
  switching virtual browsers, which also closed Settings mid-form. That
  is Ctrl+Alt+PgDown / Ctrl+Alt+PgUp now.
- **Pop-ups need a click.** Any page could open tabs on its own.
- The address bar understands localhost:3000, 127.0.0.1:8000, router
  addresses, http://… and file:///… typed out, and a Windows path
  pasted from Explorer — instead of searching Google for them.
- Opening a new tab and closing it at once no longer crashes the
  browser.
- A link opened from a tab in another virtual browser lands in that
  browser instead of as an empty tab.
- Renaming a group keeps it in its own virtual browser; "Add tab to
  group" only offers the tab's own browser's groups.
- Closing the last private tab no longer kills its downloads, and
  closing a virtual browser with private tabs forgets their cookies.
- A permission question goes away with the tab that asked it.
- Picking a suggestion with Enter loads the page once, not twice.
- **A proxy profile with a bad port can no longer stop the browser
  starting**, and picking a proxy profile in Settings selects it
  instead of deleting it.
- Frutiger Aero: the bottom of the Settings sidebar and footer are
  readable again.
- One broken address in the history no longer hides every older entry;
  the time column no longer wraps in 12-hour locales.

## 2026-07-28 — the browser's own pages stop being pages

- **Settings, Downloads, History, Bookmarks and the password manager
  now open over what you were looking at, and Esc puts it back.** They
  were pages you navigated to; four of them cost you a tab, an entry in
  your own history, and the address bar for as long as they were up.
  None of them does any of that now.
- **Esc is the way out of all five**, and it leaves you exactly where
  you were — the same tab, on the same page, scrolled where you left
  it. Closing one used to be able to hand you a fresh start page
  instead of the page you came from, which is what made them feel like
  somewhere you had gone rather than something you had opened.
- **The keys you know work both ways now.** Ctrl+, Ctrl+H, Ctrl+J,
  Ctrl+Shift+O and Ctrl+Shift+P open their page, and pressing the same
  keys again closes it. Opening one twice brings up the one you already
  had rather than a second copy.
- Each is loaded fresh every time it comes up, so it shows what is true
  now — a download that finished while it was closed, a bookmark added
  from the bar, a password saved in another window.
- **They are never reopened as tabs when the browser starts.** If an
  older version left one saved in your session it is quietly dropped,
  so you no longer come back to a stale Downloads tab that no longer
  works.

## 2026-07-28 — the buttons at the top are yours

- **Pick the buttons on the toolbar.** The row up there was whatever
  someone else had decided it should be. Now it is a list you own:
  right-click the toolbar for a menu of every button with a tick beside
  the ones that are there, or open **Settings → Toolbar** for the same
  list with switches, and arrows to push a button left or right along
  the row. Nothing moves on its own — the set you start with is exactly
  the set that was there before.
- **Eight buttons that were only ever shortcuts can come up.** New tab,
  find on page, history, downloads, bookmarks, the password manager,
  settings and full screen were all keys and nothing else. They are all
  off to begin with, and any of them can join the row.
- **Four of them stay.** Back, forward, reload and the address bar
  cannot be taken away. A browser with no way back is a broken browser,
  and there is no undoing it from a window you have just broken. Their
  switch is dimmed, and clicking the row says so rather than ignoring
  you.
- **The star and the tab groups button can go too.** They do not live
  on the row — the star rides inside the address bar, the tab groups
  button sits in the corner of the tab strip — so they can be taken
  away but not moved, and Settings says so.
- **A button you take away is gone, not hiding**, and its keyboard
  shortcut keeps working: Ctrl+P still prints with no print button.
- **A menu entry you cannot pick now looks like one.** The window's own
  stylesheet was setting the menu's text colour, which quietly overrode
  the greying-out, so an entry that did nothing looked exactly like one
  that did. Everywhere, not just here.

## 2026-07-28 — the page you start on, and the way back to it

- **"When the browser starts" is a setting of its own.** It sits in
  **Settings → Browsing**, just above "What a new tab shows": the start
  page, or an address you type. Put YouTube there and the browser opens
  on YouTube — while a new tab still shows the start page. The two are
  separate and neither one writes the other.
- Tabs from last time still win. With "reopen tabs from last time" on
  and something to come back to, those come back, and no start-up page
  is pushed on top of them.
- **Alt+Home goes to the start page, and there is a ⌂ button next to
  reload.** Once you set a page of your own for new tabs there was no
  way back to the start page at all: it is a file on this computer with
  a name nobody could type. Now there are two.
- **A tab you opened and typed an address into is still there
  tomorrow.** An empty tab is deliberately not saved, so the strip does
  not grow at every launch — but type fast enough and the browser filed
  your destination as "where an empty tab rests" and never counted the
  tab as yours again. Open a tab, go to one page, leave it overnight,
  and it was gone in the morning with no message and no way back.
- **The address boxes in Settings save themselves.** The page promises
  every change is saved the moment you make it, and these were the only
  controls that broke that promise — typing an address and closing
  Settings wrote nothing at all.
- **An address the browser will not take stays in the box** where you
  can fix it, and the red line names the address still in force rather
  than only saying no.
- **Settings can no longer come up blank.** One unreachable call used
  to leave no theme picker, no plugin list, no password summary and no
  line to say why. The page always ends up drawn now, and says so if a
  part of it would not.

## 2026-07-28 — setup catches up

- **Setup asks about the colours.** A new second step offers twelve of
  the 114 themes — four dark, four light, four with a character of
  their own — and picking one paints the browser while you are still
  standing in setup. Twelve and not 114: that is a catalogue to browse,
  not a question to answer, and the line underneath points at
  Settings → Theme, which has all of them and a search box.
- **Setup asks what the browser opens on**, at the top of the start-page
  step: the start page, or an address you type. Same pair of cards
  Settings has, same refusal for an address it cannot make sense of.
- **The bookmarks bar is offered where you would look for it.**
- Both new answers are on the summary, and both survive leaving setup
  with Esc and coming back. Setup is eight steps now instead of seven.

## 2026-07-28 — the themes, made readable

- **Every one of the 114 themes can now be read.** A hint, a
  placeholder or a disabled label used to sit a fixed fraction of the
  way from the background to the text. That keeps the proportion and
  throws the contrast away — on a pale background the same fraction is
  a far fainter colour, and on half the shelf the quiet text, the
  warning lines and the accent had faded into the page. Every colour is
  now pushed out until it clears 4.5:1 against the page and against
  every island it can land on, and each is kept a step clear of the one
  below it so the hierarchy does not collapse onto the floor.
- **Catppuccin Mocha is untouched**, down to the byte.
- **A light theme no longer leaves the websites dark.** Auto-darkening
  is switched in two places and only one of them was being told, so a
  browser you had just made light was full of black pages. Every tab
  and every pane is re-asked the moment the theme lands, rather than
  waiting until you navigate.
- **A card under the mouse is no longer a black box**, a texture is
  painted behind the page rather than on a sheet of glass over it, and
  the wash behind the clock on the start page is the theme's own colour
  instead of black on someone's bright wallpaper.
- **Colours a theme could never reach** — the password strength bar,
  the flags on a weak or reused password, the vault line in Settings,
  the mark beside the virtual browser you are in — read the palette now
  instead of fixed Catppuccin values.
- **A corrupted theme name no longer stops the browser starting.**
- All of it is measured rather than eyeballed: 6612 contrast ratios,
  every pair the pages and the window produce in every theme.

## 2026-07-28 — signing in with two accounts

- **When you clear the sign-in box to type your other account, it stays
  clear.** The browser filled the saved address, and every time you
  emptied the box to put the second account in, the address came
  straight back — often landing in front of what you had just started
  typing, so the box ended up holding both addresses stuck together.
  Microsoft's sign-in rebuilds that box constantly, and a rebuilt box
  is an empty one, which the browser read as "nobody is signing in here
  yet, fill the saved account".
- The rule now is the one the password box already followed: the
  browser fills the account once, and the moment you change or clear
  it, that is your choice for the rest of the page.
- **Two accounts on one sign-in fill the right password**, and the Site
  box in the password manager no longer eats a URL you paste into it.

## 2026-07-27 — 114 themes

- The browser is no longer one colour scheme. **Settings → Theme** has
  114 of them, on three shelves: Dark, Light and With character. Type
  in the box above the list to find one, or type its name into the
  search on the left — the whole catalogue is searchable either way.
- Each theme is its own card, painted in its own colours: the window,
  an island on it, a line of text and the accent. The list is the
  preview.
- Clicking one applies it **immediately** — the window, the tabs, the
  address bar, the menus, and every page the browser brings with it
  (start, settings, history, downloads, bookmarks, passwords). Nothing
  is reloaded and nothing has to be restarted.
- Most are well-known palettes, credited on the card: Catppuccin,
  Gruvbox, Nord, Dracula, Solarized, Tokyo Night, Everforest, Rosé
  Pine, Kanagawa, Monokai, One, Ayu, Material, Oxocarbon, Nightfox,
  GitHub, VS Code and more. The rest are drawn here — Steam, Autumn,
  Nautical, Deep Sea, Volcano, Cyberpunk and so on.
- Nine of them are more than a palette. **Steampunk** brings brass,
  oxblood and a slab serif with a rule under every heading;
  **Terminal Green** and **Amber CRT** bring scanlines and a phosphor
  glow; **Blueprint** brings drafting paper; **Newspaper** and **Sepia
  Paper** bring print; **Synthwave '84**, **Game Boy** and
  **Commodore 64** bring what their names say.
- **Nothing changes unless you change it.** The theme you already have
  is called Catppuccin Mocha and it is still the default, down to the
  last hex digit.
- **Light themes and websites.** Which version of itself a website
  serves — its light one or its dark one — is decided when the browser
  starts and cannot be changed while it runs. Pick a light theme and
  the browser is light straight away; a line under the list says
  websites are still being asked for their dark version and offers to
  restart. While a light theme is on, "auto-darken light websites" is
  held off, so a white browser is never full of black pages. Your
  setting is left exactly where you put it.
- Websites themselves are never repainted by a theme, and neither is
  anyone else's HTML file you happen to open. A theme is the browser,
  not the web.
## 2026-07-28

- The update button digs itself out of a half-finished merge. One that
  was interrupted left the folder in a state where every update failed
  with "Exiting because of an unresolved conflict", for good. It clears
  that first now, and when an update genuinely cannot arrive it says
  why in words rather than passing git's own along.

## 2026-07-27 — Settings, cleaned up

- **The bar that crept along the top of Settings is gone.** It measured
  how far down the list of sections you were, which is not a thing
  anyone needed measured, and it re-drew itself every time you clicked.
- **Searching Settings now points at the setting, not just the
  section.** Type a word and the rail says how many settings in each
  section answer to it; inside the section the ones that match keep
  their colour and get a mark down the left, and the rest step back.
- **The search box keeps the keyboard.** ↑ and ↓ walk the sections that
  matched, Enter drops you onto the first setting one of them found,
  and Esc empties the box. Esc anywhere else still closes Settings.
- **Switches can be reached with Tab now**, and flipped with Space.
- Settings moves a little: a section slides up a few pixels as it
  arrives, the rail lights up under the pointer, the switches slide
  rather than jump. All of it is off if your system asks for less
  motion.

## 2026-07-27 — caught up with the Linux edition

This edition was a long way behind. Everything below arrives at once.

- **Vault Password**: the password manager is now optional and has a
  name. Setup asks whether you want it, and Settings → Plugins, under
  Built-in features, switches it on and off whenever you like. Off
  means off — the part that watches for logins is never put into a page
  at all. Switching it off deletes nothing; your saved logins are all
  there again when you switch it back on.
- **A password manager of its own** (Ctrl+Shift+P), instead of a list
  inside Settings: search across everything, secure notes, payment
  cards and identities, tags, favourites, a password generator
  (Ctrl+Shift+G), two-factor codes with a countdown, a health check,
  and CSV import/export.
- **1Password** can be the store instead of the built-in file vault,
  through the official `op` command-line tool.
- **Two-step logins** fill properly — the Amazon and Microsoft kind,
  where the email comes first and the password on a second screen.
- **Saved passwords fill when you click the box you want filled.**
  Clicking into the email or password field was the one gesture that
  did nothing, so the commonest way to start a login was the way that
  never worked.
- **Changing account no longer submits the previous account's
  password.** Pressing Ctrl, Shift or an arrow key used to be read as
  "done here" and dropped the last-used account's password into the
  box, where nothing could replace it.
- The saved-password file is now actually protected on Windows. It asked
  for owner-only permissions the POSIX way, which Windows quietly ignores,
  so the file only ever had the protection its folder happened to give it.
  It now gets an ACL of its own: this user, nobody else.

## 2026-07-26

- Settings fills the whole window now — address bar and tabs included —
  instead of sitting below them; Esc or the ✕ closes it
- Settings is sorted into General / Privacy / Advanced / Browser, and the
  page says which section you are in
- The page-zoom and minimum-text-size sliders are actually visible on the
  black theme: a filled track and a square white handle
- Settings is no longer auto-darkened on top of its own dark theme
- Find in page (Ctrl+F): match count, Enter / Shift+Enter to step,
  match case, Esc to close; follows the tab you switch to
- Print and Save as PDF (Ctrl+P), also from the toolbar printer button;
  the PDF lands in your download folder and on the downloads page
- Reopen closed tab (Ctrl+Shift+T), back in its group and its
  virtual browser
- Tab search (Ctrl+Shift+A): every open tab across every virtual
  browser, filtered as you type
- Bookmarks: a star in the address bar (Ctrl+D), a bookmarks bar with
  favicons under the toolbar (Ctrl+Shift+B), folders, and a bookmark
  manager page (Ctrl+Shift+O) to search, rename, reorder and delete
- Microphone works: clicking Allow now actually reaches the engine,
  so a site that asks for the mic really records (camera too)
- Setup wizard rebuilt as a full-screen, seven-page walk-through:
  language, search engine, wallpaper and search-bar placement (with a
  live preview of the start page), how websites look, privacy, quick
  links, and a summary of everything picked
- Setup can be left with Esc without pretending to be finished, picks
  up where it left off, and shows your current choices when re-run
- New privacy switch: offer to save passwords
- Screen sharing asks at last: a black picker listing your screens and
  windows, where before every screen-share attempt failed instantly
- Permissions are remembered per site, not per host name: allowing the
  mic on one site no longer quietly allows the same name on another port
- A local HTML file gets its own answer instead of sharing one with
  every other file on the disk, and it is never remembered for good
- Settings now looks like the setup wizard: the same left rail with a
  marker on where you are, the same big title with a line under it, the
  same option cards and square switches, the same footer — and a filter
  box, because the list of settings keeps growing
- Offer to save passwords is in Settings too, not only in setup
- Search suggestions can be switched off: nothing you type in the
  address bar is sent to the search engine
- New switches: block videos from playing on their own, smooth
  scrolling, open PDFs in the browser instead of downloading them,
  check spelling as you type (with its own language)
- Pick your download folder, or keep ~/Downloads
- Clear history and/or cookies when the browser closes
- Choose where a new tab opens (at the end, or right after this tab)
  and what it shows (the start page, or an address you pick)
- "Right after this tab" no longer scrambles the tab strip when the
  browser reopens the tabs from last time
- The settings filter searches everything on the page, not just the
  words that were there before it loaded: search engines, spell-check
  languages, saved logins, proxy profiles, the option cards
- Filtering to nothing leaves no half-open section behind, and there is
  an "All settings" button to get back
- Clear history / cookies when the browser closes survives a crash: a
  wipe the last run did not get to do happens at the next start
- Changing the browser's language moves the spell checker with it
- The new-tab address says what it turned into, and says so when it is
  not an address at all instead of quietly falling back

## 2026-07-23

- Pitch-black theme with square corners; no blue accents in the chrome
- Google pages repainted true black
- Faster loading on natively dark sites (GitHub, YouTube, …)
- First-run setup wizard: drag the search bar anywhere, pick a wallpaper
- Update button in settings + update-available popup at startup
- Esc closes the history page back into the settings panel
- Light-colored settings switches; various start-page fixes

## 2026-07-22

- First release: tabs, smart address bar, downloads bar, history,
  start page with quick links and backgrounds, single instance,
  fullscreen video, default-browser support
