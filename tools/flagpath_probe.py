"""Run the real startup flag path over a config whose safeFlags are set,
and print the one string the engine is actually handed."""
import os
import sys
import atexit

import json
import shutil
import tempfile

#: what to put in the config, to see what comes out the other end. Two
#: questions in one run: are safeFlags read back at all, and does a
#: feature asked for in the free-text box survive to the engine.
PROBE_CONFIG = {
    "safeFlags": ["--enable-zero-copy", "--enable-gpu-rasterization",
                  "--enable-features=VaapiVideoDecoder,VaapiVideoEncoder"],
    "chromiumFlags": "--enable-features=ProbeFeatureFromTheTextBox",
}

HOME = tempfile.mkdtemp(prefix="flagpath-probe-")
os.makedirs(os.path.join(HOME, "browser"), exist_ok=True)
with open(os.path.join(HOME, "browser", "config.json"), "w") as fh:
    json.dump(PROBE_CONFIG, fh)
atexit_home = HOME
os.environ["HOME"] = HOME
os.environ["BROWSER_HOME"] = os.path.join(HOME, "browser")
os.environ["XDG_DATA_HOME"] = HOME
os.environ["XDG_CONFIG_HOME"] = HOME
os.environ["XDG_CACHE_HOME"] = HOME
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.pop("QTWEBENGINE_CHROMIUM_FLAGS", None)
# the edition this probe is run from, not a path baked in
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
atexit.register(shutil.rmtree, atexit_home, True)

import browser  # noqa: E402  (import-time block runs _startup_flags)

print("config read from :", browser.CONFIG_FILE)
print("exists           :", browser.CONFIG_FILE.exists())
print()
print("after import (_startup_flags + the three idempotent appends):")
print("  ", os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "(unset)").strip())
print()
browser._install_proxy_flags()
final = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
print("after _install_proxy_flags (the --enable-features owner):")
for part in final.split():
    print("   ", part)
print()
print("--- the two questions ---")
curated = ["--enable-zero-copy", "--enable-gpu-rasterization"]
for c in curated:
    print("  %-30s in the final string: %s" % (c, c in final))
feats = [p for p in final.split() if p.startswith("--enable-features=")]
print("  --enable-features flags present   : %d" % len(feats))
for f in feats:
    print("      %s" % f)
print("  Chromium honours only the LAST one: %s"
      % (feats[-1] if feats else "(none)"))
print("  the text box's feature survives   : %s"
      % ("ProbeFeatureFromTheTextBox" in (feats[-1] if feats else "")))
