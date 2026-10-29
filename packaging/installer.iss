; Inno Setup script for BrowserSetup.exe. Built by .github/workflows/build-exe.yml
; from PyInstaller's dist\Browser folder. Installs per user (no admin prompt)
; into %LOCALAPPDATA%\Programs\Browser; user data stays in %LOCALAPPDATA%\browser.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppUrl "https://github.com/idkhowtonamemyselfasadev/browser-windows"

[Setup]
AppId={{6F1C2B7E-4A8D-4C1B-9E3F-B0A5D2C7E914}
AppName=Browser
AppVersion={#AppVersion}
AppPublisher=idkhowtonamemyselfasadev
AppPublisherURL={#AppUrl}
; Settings -> Apps -> Installed apps shows these three next to the entry.
; Without them the row has a name and nothing else, which reads like
; something that installed itself.
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases/latest
UninstallDisplayName=Browser
; So the downloaded file's Properties -> Details actually carries a
; version. An unsigned exe with no version metadata is the shape of file
; people are told to distrust.
VersionInfoVersion={#AppVersion}
VersionInfoCompany=idkhowtonamemyselfasadev
VersionInfoDescription=Browser installer
DefaultDirName={localappdata}\Programs\Browser
DefaultGroupName=Browser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=BrowserSetup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Browser.exe
; max is only an 8 MB dictionary; ultra64 is 64 MB. It costs 742 MB of
; RAM on the build runner and 64 MB on the user's machine when they run
; the installer, both of which are nothing, and it is the one size cut
; that removes no files.
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
; The build is win_amd64 only. x64compatible is also true under ARM64
; emulation, so ARM laptops still install; a genuinely 32-bit machine
; gets a sentence instead of an app that cannot start.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Qt 6 does not run on Windows 8 or earlier. Saying so here beats a
; missing-DLL box after the install finished.
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Browser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; {autoprograms}\Browser, not {group}\Browser: DefaultGroupName would put
; the shortcut inside a Start-menu FOLDER called Browser containing one
; item also called Browser, so the user has to open a folder to reach it.
; This puts a single Browser entry straight in the app list, where
; typing "brow" into Start finds it.
Name: "{autoprograms}\Browser"; Filename: "{app}\Browser.exe"
Name: "{userdesktop}\Browser"; Filename: "{app}\Browser.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Browser.exe"; Description: "Start Browser"; Flags: nowait postinstall skipifsilent
