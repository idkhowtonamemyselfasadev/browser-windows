; Inno Setup script for BrowserSetup.exe. Built by .github/workflows/build-exe.yml
; from PyInstaller's dist\Browser folder. Installs per user (no admin prompt)
; into %LOCALAPPDATA%\Programs\Browser; user data stays in %LOCALAPPDATA%\browser.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2B7E-4A8D-4C1B-9E3F-B0A5D2C7E914}
AppName=Browser
AppVersion={#AppVersion}
AppPublisher=idkhowtonamemyselfasadev
AppPublisherURL=https://github.com/idkhowtonamemyselfasadev/browser-windows
DefaultDirName={localappdata}\Programs\Browser
DefaultGroupName=Browser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=BrowserSetup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Browser.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Browser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Browser"; Filename: "{app}\Browser.exe"
Name: "{userdesktop}\Browser"; Filename: "{app}\Browser.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Browser.exe"; Description: "Start Browser"; Flags: nowait postinstall skipifsilent
