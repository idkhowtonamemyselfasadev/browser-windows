"""What the card picker does to the video decoder and to the browser's
GL device, on a two-card machine, without needing two cards.

READ THE SECOND COLUMN NAME CAREFULLY. The variables gpu_env sets --
DRI_PRIME and the three __NV_* ones -- choose the GL device THE BROWSER
PROCESS renders on. They do NOT choose which card composites the screen.
The compositor runs on whichever card owns the displays, which is a
hardware fact no function here can tell you. An earlier version of this
probe printed that column as "drawing", and the report drew a conclusion
about the compositor from it that was wrong and would have steered a
user onto the card that breaks his machine. Hence the long name, and
hence the topology section below: the third column has to come from
sysfs, not from the function.

Two sections:
  1. gpu_cards() over a fake /sys/class/drm, so a topology can be tried
     without the machine that has it. BROWSER_DRM_ROOT is the hook.
  2. gpu_apply() per choice. It takes its env as an argument, so this
     needs no mocking -- hand it the environment the import-time NVIDIA
     line would have left (browser.py:123) and read what comes back.
"""
import os
import sys
import shutil
import tempfile

#: a topology to try. Default is the dual-GPU desktop this was written
#: for: the DISCRETE card owns the displays, which is the opposite of
#: the laptop hybrid these code paths assume.
#: (card, vendor, device, slot, boot_vga, connected outputs)
TOPOLOGY = [
    ("card1", "0x8086", "0x7d51", "0000:00:02.0", "0", 0),
    ("card2", "0x10de", "0x2c02", "0000:02:00.0", "1", 3),
]

ROOT = tempfile.mkdtemp(prefix="gpuenv-probe-")
os.environ["HOME"] = ROOT
os.environ["BROWSER_HOME"] = os.path.join(ROOT, "browser")
os.makedirs(os.environ["BROWSER_HOME"], exist_ok=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

DRM = os.path.join(ROOT, "drm")
for card, vendor, device, slot, boot, outs in TOPOLOGY:
    dev = os.path.join(DRM, card, "device")
    os.makedirs(dev, exist_ok=True)
    for what, val in (("vendor", vendor), ("device", device),
                      ("boot_vga", boot)):
        with open(os.path.join(dev, what), "w") as fh:
            fh.write(val + "\n")
    with open(os.path.join(dev, "uevent"), "w") as fh:
        fh.write("PCI_SLOT_NAME=%s\n" % slot)
    # the output nodes. gpu_cards() skips these by design -- "card1-DP-1
    # is an output, not a card" -- which is why the count that decides
    # who owns the displays never reaches the card dicts.
    for i in range(outs):
        os.makedirs(os.path.join(DRM, "%s-DP-%d" % (card, i + 1)),
                    exist_ok=True)
os.environ["BROWSER_DRM_ROOT"] = DRM

# the edition this probe sits in, never a path baked in
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

import browser  # noqa: E402

OUTPUTS = {card: outs for card, _v, _d, _s, _b, outs in TOPOLOGY}
TRIO = ("__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME",
        "__VK_LAYER_NV_optimus")


def main():
    cards = browser.gpu_cards()
    print("1. gpu_cards(), in the order the chooser presents them")
    for i, c in enumerate(cards):
        print("   %d. %-28s slot=%-14s boot_vga=%-5s outputs=%s"
              % (i + 1, c["maker"], c["slot"], c["boot"],
                 OUTPUTS.get(c["card"], "?")))
    first = cards[0] if cards else {}
    print('   the sort comment claims "the discrete card first":'
          ' first is %s' % first.get("maker", "-"))
    print()

    print("2. gpu_apply() per choice")
    print("   %-10s %-9s %-26s %s" % ("choice", "decoder",
                                      "browser's GL device",
                                      "PRIME offload vars"))
    arms = [("auto", "auto")] + [(c["maker"], c["slot"]) for c in cards]
    for label, choice in arms:
        env = {"LIBVA_DRIVER_NAME": "nvidia", "NVD_BACKEND": "direct"}
        browser.gpu_apply(choice, cards, env=env)
        gl = ("pinned " + env["DRI_PRIME"] if env.get("DRI_PRIME")
              else "not pinned by us")
        print("   %-10s %-9s %-26s %d of 3"
              % (label[:10], env.get("LIBVA_DRIVER_NAME", "(unset)"),
                 gl, sum(1 for k in TRIO if k in env)))
    print()
    print("   PRIME render-offload asserts the display is on the OTHER")
    print("   card. Compare it against the outputs column above, never")
    print("   against the decoder column: two settings agreeing with")
    print("   each other can still agree on the wrong card.")


try:
    main()
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
