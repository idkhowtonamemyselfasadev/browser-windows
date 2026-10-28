"""Entry point of the packaged Browser.exe.

browser.py is generated from the Linux edition and keeps itself current
the way a folder of source does: git pull, or a fresh zip unpacked over
the top, and pip for the Qt libraries. None of that works inside a
frozen exe -- the code is compiled into the bundle, there is no pip and
nothing to pull into -- so those few methods are swapped here instead
of teaching browser.py about a second way of being installed. A new
version is a new installer from the releases page.
"""
import os
import sys

import browser

RELEASES = ("https://github.com/idkhowtonamemyselfasadev/browser-windows"
            "/releases/latest")


def _no_check(self, *args, **kwargs):
    """The startup look for updates: nothing to compare against."""


def _update_from_releases(self):
    """Settings -> Update: point at the installer instead of a zip."""
    self._updating = None
    self.updateFinished.emit(
        "This is the installed .exe version - download the newest "
        "BrowserSetup.exe from " + RELEASES)


def _restart(self):
    """Relaunch the exe itself rather than python on browser.py."""
    if getattr(self, "_instance_server", None) is not None:
        self._instance_server.close()
        browser.QLocalServer.removeServer(browser.SINGLE_INSTANCE_SOCKET)
    os.environ["BROWSER_RESTART_WAIT"] = str(os.getpid())
    browser.QProcess.startDetached(sys.executable, [])
    browser.QApplication.instance().quit()


browser.Browser._check_updates = _no_check
browser.Browser._check_lib_updates = _no_check
browser.Browser._lib_update_now = _no_check
browser.Browser.restart = _restart
browser.Bridge._update_without_clone = _update_from_releases

if __name__ == "__main__":
    sys.exit(browser.main())
