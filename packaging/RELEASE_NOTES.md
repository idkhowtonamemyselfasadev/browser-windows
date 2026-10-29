Windows installer for Browser @VERSION@, built from `@SHA@`.

## Windows will try to stop you

This installer is not signed with a paid certificate, so Windows shows a
blue full-screen warning first:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognised app from starting.
> Running this app might put your PC at risk.

The only button on it is **Don't run**. The way through is the small
**More info** link above that button:

1. Click **More info**.
2. A line appears: *Publisher: Unknown publisher*. Below it, a new
   button: **Run anyway**.
3. Click **Run anyway**.

That is the whole wall. SmartScreen is saying it does not recognise the
publisher, not that it found anything wrong in the file. It says this
about every unsigned installer, including the first build of anything.

If you would rather check the download first, the SHA-256 of
`BrowserSetup.exe` is at the bottom of this page. Compare it in
PowerShell:

```
Get-FileHash BrowserSetup.exe
```

## What it does

- Installs for your user only, into `%LOCALAPPDATA%\Programs\Browser` —
  no admin prompt.
- Adds a **Browser** entry to the Start menu, and a desktop shortcut if
  you tick the box.
- Uninstall through **Settings → Apps → Installed apps → Browser**.
- Python and Qt are bundled. Nothing else needs installing.
- Your data stays in `%LOCALAPPDATA%\browser` and uninstalling does not
  delete it.

The exe does not update itself. A new version is a new installer from
this page.
