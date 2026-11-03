"""Ask the live engine three things, headless:

  1. which GL backend the GPU process actually chose (WebGL unmasked
     renderer -- not a string scraped out of the binary)
  2. what it CLAIMS it can decode (MediaSource.isTypeSupported)
  3. what it ACTUALLY decodes to a non-black frame (drawImage the
     playing video onto a canvas and read the pixels back)

(2) vs (3) is the whole point: browser.py:3509 says this engine can
claim AV1 and then hand the player a black rectangle. That claim is
testable without a display, because drawImage reads the decoded frame,
not the compositor.

Flags come in through QTWEBENGINE_CHROMIUM_FLAGS, set by the caller.

Reading the exit code: 134 and 139 AFTER a full result are the engine's
known teardown crash (a sip wrapper touched once its C++ object is gone)
and say nothing about the arm. A flag the engine refuses looks different
and is unmistakable -- NO result at all, because the process dies before
the first page loads. Judge an arm by whether its rows printed, never by
its exit code.
"""
import os
import sys
import atexit
import shutil
import tempfile
import threading
import http.server
import socketserver
import functools

PREFIX = "blackvid-probe-"
DATA = os.path.join(tempfile.gettempdir(), PREFIX + str(os.getpid()))


def _tidy_old():
    """Remove this probe's own leftovers, by liveness and not by age.

    The engine's teardown crash (134/139) can take the process down
    before the rmtree at the end of a run, so a tidy-up that only
    happens on the way out does not happen. Each run owns exactly the
    directory named after its pid, so a directory whose pid is gone is
    nobody's -- which is the test, rather than how old it looks. Only
    this prefix is ever touched: /tmp is shared.
    """
    root = tempfile.gettempdir()
    for name in os.listdir(root):
        if not name.startswith(PREFIX):
            continue
        tail = name[len(PREFIX):]
        if not tail.isdigit():
            continue
        pid = int(tail)
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 0)          # alive: another run owns it
            continue
        except ProcessLookupError:
            pass
        except OSError:
            continue                 # someone else's, or not ours to ask
        shutil.rmtree(os.path.join(root, name), ignore_errors=True)


_tidy_old()
shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA, exist_ok=True)
atexit.register(shutil.rmtree, DATA, True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# never the real home: DATA_DIR on non-Windows is ~/.local/share/browser
os.environ["HOME"] = DATA
os.environ["XDG_DATA_HOME"] = DATA
os.environ["XDG_CONFIG_HOME"] = DATA
os.environ["XDG_CACHE_HOME"] = DATA

from PyQt6.QtWidgets import QApplication                        # noqa: E402
from PyQt6.QtCore import QUrl, QTimer, QEventLoop               # noqa: E402
from PyQt6.QtWebEngineWidgets import QWebEngineView             # noqa: E402

CODECS = [
    ('vp9-webm',  'video/webm; codecs="vp9"'),
    ('vp9-mp4',   'video/mp4; codecs="vp09.00.10.08"'),
    ('av1-mp4',   'video/mp4; codecs="av01.0.08M.08"'),
    ('av1-webm',  'video/webm; codecs="av01.0.05M.08"'),
    ('h264',      'video/mp4; codecs="avc1.640028"'),
    ('vp8',       'video/webm; codecs="vp8"'),
    ('hevc',      'video/mp4; codecs="hvc1.1.6.L93.B0"'),
    ('opus',      'audio/webm; codecs="opus"'),
    ('aac',       'audio/mp4; codecs="mp4a.40.2"'),
]

CLIPS = [('vp9', 'clip_vp9.webm'), ('vp8', 'clip_vp8.webm'),
         ('av1', 'clip_av1.mp4'), ('h264', 'clip_h264.mp4')]

#: the clips are a solid mid-blue, so a frame that comes back near zero
#: is the bug and not a dark scene. Encoded here rather than committed:
#: four binaries in the repo to answer a question ffmpeg answers in two
#: seconds, and a clip made on the box is a clip whose colour is known.
CLIP_COLOUR = "0x30A0FF"
CLIP_ENCODERS = {"clip_vp9.webm": "libvpx-vp9", "clip_vp8.webm": "libvpx",
                 "clip_av1.mp4": "libsvtav1", "clip_h264.mp4": "libx264"}
#: what the colour above decodes to, give or take yuv420p rounding
CLIP_EXPECT = "rgb(48,160,253)"


def make_clips(into):
    """Encode the test clips. Returns the ones ffmpeg managed.

    A missing encoder is not a failure of the probe: it means this
    machine cannot ask that codec's question, which is reported as a
    missing row rather than as a pass.
    """
    import subprocess
    made = []
    for name, enc in CLIP_ENCODERS.items():
        out = os.path.join(into, name)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "lavfi",
               "-i", "color=c=%s:s=320x180:d=2:r=25" % CLIP_COLOUR,
               "-pix_fmt", "yuv420p", "-c:v", enc, "-b:v", "300k", out]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            print("  no %-16s %s: %s" % (name, enc, type(exc).__name__))
            continue
        made.append(name)
    return made

PAGE = """<!doctype html><meta charset=utf-8><body>
<script>
window.__done = false; window.__out = {};

function glinfo() {
  var o = {};
  try {
    var c = document.createElement("canvas");
    var gl = c.getContext("webgl2") || c.getContext("webgl");
    if (!gl) return {err: "no webgl context"};
    var d = gl.getExtension("WEBGL_debug_renderer_info");
    o.vendor = d ? gl.getParameter(d.UNMASKED_VENDOR_WEBGL) : "(masked)";
    o.renderer = d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : "(masked)";
    o.version = gl.getParameter(gl.VERSION);
  } catch (e) { o.err = String(e); }
  return o;
}

function claims(list) {
  var o = {};
  for (var i = 0; i < list.length; i++) {
    var name = list[i][0], t = list[i][1], ms = "?", cp = "?";
    try { ms = MediaSource.isTypeSupported(t) ? "yes" : "no"; }
      catch (e) { ms = "throw"; }
    try { cp = document.createElement("video").canPlayType(t) || "(empty)"; }
      catch (e) { cp = "throw"; }
    o[name] = ms + " / " + cp;
  }
  return o;
}

// Decodes one clip and reads the frame back through a canvas.
// SEEKS rather than plays: offscreen the view is never visible, and
// Chromium pauses video-only background media to save power, which
// refuses play() for a reason that has nothing to do with this bug.
// A seek still has to decode a frame, which is the thing being asked.
function frame(name, url) {
  return new Promise(function (resolve) {
    var v = document.createElement("video");
    v.muted = true; v.preload = "auto"; v.src = url;
    var settled = false, seeked = false;
    function give(r) { if (!settled) { settled = true; resolve([name, r]); } }
    setTimeout(function () {
      give("TIMEOUT readyState=" + v.readyState
           + " sought=" + seeked
           + " err=" + (v.error ? v.error.code : "-"));
    }, 10000);
    v.addEventListener("error", function () {
      give("ERROR code=" + (v.error ? v.error.code : "?")
           + " " + (v.error ? v.error.message : ""));
    });
    v.addEventListener("loadeddata", function () {
      try { v.currentTime = 0.8; seeked = true; }
      catch (e) { give("SEEK " + String(e)); }
    });
    v.addEventListener("seeked", function () {
      if (v.videoWidth === 0) { give("NO DIMENSIONS after seek"); return; }
      try {
        var c = document.createElement("canvas");
        c.width = v.videoWidth; c.height = v.videoHeight;
        var x = c.getContext("2d");
        x.drawImage(v, 0, 0);
        var px = x.getImageData(0, 0, c.width, c.height).data;
        var r = 0, g = 0, b = 0, n = c.width * c.height;
        for (var i = 0; i < px.length; i += 4) {
          r += px[i]; g += px[i + 1]; b += px[i + 2];
        }
        r = Math.round(r / n); g = Math.round(g / n); b = Math.round(b / n);
        // the clips are a solid 0x30A0FF, so anything near 0 is the bug
        var black = (r + g + b) < 12;
        give((black ? "BLACK" : "PAINTS") + "  rgb(" + r + "," + g + "," + b
             + ")  " + c.width + "x" + c.height
             + "  t=" + v.currentTime.toFixed(2));
      } catch (e) { give("CANVAS " + String(e)); }
    });
  });
}

window.__run = function (codecs, clips) {
  window.__out.gl = glinfo();
  window.__out.claims = claims(codecs);
  Promise.all(clips.map(function (c) { return frame(c[0], c[1]); }))
    .then(function (rows) {
      window.__out.frames = {};
      rows.forEach(function (r) { window.__out.frames[r[0]] = r[1]; });
      window.__done = true;
    });
};
</script></body>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


def serve():
    socketserver.TCPServer.allow_request = True
    h = functools.partial(Handler, directory=DATA)
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def wait(view, js, timeout_ms):
    """Spin the event loop until js returns true, or give up."""
    loop = QEventLoop()
    state = {"ok": False}

    def poll():
        def got(v):
            if v:
                state["ok"] = True
                loop.quit()
        view.page().runJavaScript(js, got)
    t = QTimer()
    t.timeout.connect(poll)
    t.start(250)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    t.stop()
    return state["ok"]


def grab(view, js):
    loop = QEventLoop()
    box = {}

    def got(v):
        box["v"] = v
        loop.quit()
    view.page().runJavaScript(js, got)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    return box.get("v")


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else "(none)"
    print("### arm: %s" % arm)
    print("### QTWEBENGINE_CHROMIUM_FLAGS=%s"
          % (os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") or "(unset)"))
    print("### clips: encoding into the scratch dir")
    made = make_clips(DATA)
    clips = [c for c in CLIPS if c[1] in made]
    if not clips:
        print("no clip could be encoded -- is ffmpeg installed?")
        return 1
    srv = serve()
    port = srv.server_address[1]
    app = QApplication(sys.argv[:1])
    view = QWebEngineView()
    view.resize(900, 600)
    view.load(QUrl("http://127.0.0.1:%d/" % port))
    if not wait(view, "document.readyState === 'complete' && !!window.__run",
                20000):
        print("page never loaded")
        return 1
    import json
    view.page().runJavaScript(
        "window.__run(%s, %s)" % (json.dumps(CODECS), json.dumps(clips)))
    if not wait(view, "window.__done === true", 60000):
        print("probe never finished")
    out = grab(view, "JSON.stringify(window.__out)")
    data = json.loads(out) if out else {}
    gl = data.get("gl", {})
    print("GL  vendor   : %s" % gl.get("vendor", "-"))
    print("GL  renderer : %s" % gl.get("renderer", "-"))
    print("GL  version  : %s" % gl.get("version", gl.get("err", "-")))
    print("claims (MediaSource.isTypeSupported / canPlayType):")
    for name, _t in CODECS:
        print("  %-9s %s" % (name, data.get("claims", {}).get(name, "-")))
    print("decoded frame read back off a canvas:")
    print("    (a solid %s clip; %s is right, near-zero is the bug)"
          % (CLIP_COLOUR, CLIP_EXPECT))
    for name, _f in clips:
        print("  %-9s %s" % (name, data.get("frames", {}).get(name, "-")))
    view.setParent(None)
    view.deleteLater()
    app.processEvents()
    srv.shutdown()
    return 0


if __name__ == "__main__":
    code = main()
    shutil.rmtree(DATA, ignore_errors=True)
    sys.exit(code)
