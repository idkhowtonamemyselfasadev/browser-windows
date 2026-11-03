"""What the GPU picker does to the video decoder on a two-card machine.

browser.py sets LIBVA_DRIVER_NAME=nvidia at import time whenever an
NVIDIA driver is installed (line 123). gpu_env/gpu_apply are then
supposed to keep the decoder on the same card as the drawing, because
the file says twice what happens otherwise -- line 238 and line 437:
a hardware-decoded stream comes out BLACK while its sound plays on.

gpu_apply takes its env as an argument, so this needs no mocking: hand
it the environment that import-time line would have left, and read what
comes back.
"""
import os
import sys
import shutil
import tempfile

HOME = tempfile.mkdtemp(prefix="gpuenv-probe-")
os.makedirs(os.path.join(HOME, "browser"), exist_ok=True)
os.environ["HOME"] = HOME
os.environ["BROWSER_HOME"] = os.path.join(HOME, "browser")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# the edition this probe sits in, never a path baked in
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

import browser  # noqa: E402

# his desktop, as reported: Intel Arrow Lake-S iGPU + NVIDIA RTX 5080
CARDS = [
    {"slot": "00:02.0", "vendor": "0x8086", "device": "0x7d51",
     "name": "Intel Arrow Lake-S iGPU"},
    {"slot": "01:00.0", "vendor": "0x10de", "device": "0x2c02",
     "name": "NVIDIA RTX 5080"},
]

WATCH = ["LIBVA_DRIVER_NAME", "NVD_BACKEND", "DRI_PRIME",
         "__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME",
         "MESA_VK_DEVICE_SELECT"]


def arm(label, choice):
    # the environment the import-time line leaves on a machine with an
    # NVIDIA driver installed, which his has
    env = {"LIBVA_DRIVER_NAME": "nvidia", "NVD_BACKEND": "direct"}
    browser.gpu_apply(choice, CARDS, env=env)
    decoder = env.get("LIBVA_DRIVER_NAME", "(unset)")
    draws = ("NVIDIA" if env.get("__NV_PRIME_RENDER_OFFLOAD")
             else ("pinned " + env["DRI_PRIME"] if env.get("DRI_PRIME")
                   else "whatever the system picks"))
    print("  %-22s decoder=%-9s drawing=%s" % (label, decoder, draws))
    return decoder, draws


print("gpuCard setting -> what decodes, and what draws")
print()
a = arm('unset / "auto"', "auto")
arm('unset (empty)', "")
b = arm("the NVIDIA card", "01:00.0")
c = arm("the Intel iGPU", "00:02.0")
print()
print("--- the asymmetry ---")
print("  on auto, is LIBVA_DRIVER_NAME cleared?  %s"
      % ("yes" if a[0] == "(unset)" else "NO -- left at " + a[0]))
print("  on auto, is NVIDIA forced to draw?      %s"
      % ("yes" if "NVIDIA" in a[1] else "no -- " + a[1]))
print("  so on the DEFAULT setting the decoder is pinned to one card")
print("  while nothing pins the drawing to it. Both explicit choices")
print("  agree with themselves: %s / %s" % (b[0], c[0]))
shutil.rmtree(HOME, ignore_errors=True)
