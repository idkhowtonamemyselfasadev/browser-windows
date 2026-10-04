@echo off
rem ── browser for Windows ── installer ──────────────────────────────
rem Installs Python if needed, then PyQt6 WebEngine, then puts a
rem "Browser" shortcut on the desktop.

rem -- is Python there? --
py -3 --version >nul 2>&1 || python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed yet - installing it with winget...
    winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements --override "/quiet PrependPath=1 Include_launcher=1"
    if errorlevel 1 (
        echo.
        echo winget could not install Python automatically.
        echo Please install it yourself from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH", then run install.bat again.
        pause
        exit /b 1
    )
    echo.
    echo Python is installed. Close this window and run install.bat once more.
    pause
    exit /b 0
)

echo Installing PyQt6 WebEngine (this can take a minute)...
py -3 -m pip install --upgrade PyQt6 PyQt6-WebEngine 2>nul || python -m pip install --upgrade PyQt6 PyQt6-WebEngine
if errorlevel 1 (
    echo.
    echo pip failed - check your internet connection and try again.
    pause
    exit /b 1
)

rem -- the shortcut must start the same Python that pip just installed into:
rem    with two Pythons on the PC, "pythonw" on PATH can be the other one,
rem    and then the shortcut fails silently on a missing PyQt6 --
set "PYW="
for /f "delims=" %%i in ('py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do set "PYW=%%i"
if not defined PYW for /f "delims=" %%i in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do set "PYW=%%i"
echo Creating desktop shortcut...
powershell -NoProfile -Command ^
  "$pyw = $env:PYW; if (-not $pyw -or -not (Test-Path $pyw)) { $pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source }; " ^
  "if (-not $pyw) { $pyw = (Get-Command python).Source -replace 'python\.exe$','pythonw.exe' }; " ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Browser.lnk'); " ^
  "$s.TargetPath = $pyw; " ^
  "$s.Arguments = '\"%~dp0browser.py\"'; " ^
  "$s.WorkingDirectory = '%~dp0'; " ^
  "$s.IconLocation = '%~dp0icon.ico'; " ^
  "$s.Description = 'browser'; " ^
  "$s.Save()"

echo.
echo Done! Double-click "Browser" on your desktop to start.
pause
