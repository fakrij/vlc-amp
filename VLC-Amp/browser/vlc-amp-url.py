#!/usr/bin/env python3
"""vlc-amp-url.py - play a web page's video or audio in VLC (Linux side of "open links from the browser").

    vlc-amp-url.py 'vlc-amp:play?mode=video&url=https%3A%2F%2F...'   handle a vlc-amp: link (the .desktop handler)
    vlc-amp-url.py --resolve [--audio] URL                            print what would be sent to VLC (no VLC)
    vlc-amp-url.py --relay                                            run the local relay (started on demand)

A vlc-amp: link comes from the browser extension or the bookmarklet (browser/README.md). The page URL is
resolved with yt-dlp (YouTube and ~1800 other sites): up to 1080p H.264 video + m4a audio, or audio only
(mode=audio). The two streams go to VLC as one playlist item (video + :input-slave=audio).

Streams that a server only hands out in bounded chunks (YouTube: a request without a closed byte range
gets HTTP 403, and VLC never sends one) go through the relay: a small HTTP server on 127.0.0.1:48081 that
fetches the stream in 10 MB ranges and passes it on, so VLC can play and seek it. Its URLs carry a secret
(~/.local/state/vlc-amp/relay-secret), so other web pages cannot use it. It exits after 6 h without use
(the stream URLs expire then anyway).

The item goes to a running VLC through its web interface (linux/setup.sh switches it on: 127.0.0.1:48080,
password in vlcrc), which keeps the item options; otherwise VLC is started with the options on its command
line (Exec of vlc-amp.desktop). A running VLC without the web interface gets the item over D-Bus, which
drops item options: then a single stream is played (360p with sound, or audio only).

Log: ~/.local/state/vlc-amp/url.log. Errors also go to notify-send when it is there.
"""
import base64
import http.client
import http.server
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

RELAY_PORT = 48081
CHUNK = int(os.environ.get("VLCAMP_CHUNK") or 10 * 1024 * 1024)   # yt-dlp's chunk size for YouTube (tests: smaller)
VLC_UA = "VLC/3.0.20 LibVLC/3.0.20"  # when yt-dlp names no User-Agent: what VLC itself would send
RELAY_IDLE = 6 * 3600             # seconds without a request before the relay exits
WEB_PORT = 48080                  # VLC's web interface (linux/setup.sh HTTP_PORT)

FORMATS = {
    # H.264 first: hardware decoding and the least CPU; VP9 / AV1 when there is no H.264 at that height
    "video": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
    "audio": "ba[ext=m4a]/ba/b",
    # one stream with sound: for a running VLC that only takes plain URLs (D-Bus)
    "single": "b[height<=1080][vcodec!=none][acodec!=none]/b",
}

# what yt-dlp prints (one JSON line per video; a playlist page gives its first video: --playlist-items 1)
FIELDS = "%(.{title,format_id,url,protocol,http_headers,downloader_options,requested_formats})j"

STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "vlc-amp")
LOG = os.path.join(STATE, "url.log")
SECRET_FILE = os.path.join(STATE, "relay-secret")


def log(text):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + text + "\n")
    except OSError:
        pass


def fail(text):
    log("error: " + text)
    print("vlc-amp-url: " + text, file=sys.stderr)
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "VLC Amp", "-i", "vlc", "VLC Amp", text], check=False)
    sys.exit(1)


# ---------------------------------------------------------------- the link

def parse_link(link):
    """vlc-amp:play?mode=video|audio&url=<encoded> -> (url, mode). Also vlc-amp://<url> and a bare URL."""
    mode = "video"
    if link.startswith("vlc-amp:"):
        rest = link[len("vlc-amp:"):]
        if rest.startswith("//") and not rest.startswith("//play"):
            url = urllib.parse.unquote(rest[2:])            # vlc-amp://https://... (typed by hand)
        else:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query or rest.partition("?")[2])
            url = (q.get("url") or [""])[0]
            mode = (q.get("mode") or ["video"])[0]
    else:
        url = link
    if mode not in ("video", "audio"):
        mode = "video"
    if not re.match(r"(?i)^https?://[^\s/]+", url):
        fail("not a web link: " + url[:200])
    return url, mode


# ---------------------------------------------------------------- yt-dlp

def find_ytdlp():
    """Of all the yt-dlp copies (PATH, ~/.local/bin), the one installed or updated last: an old distro copy
    first on the PATH must not hide a current pipx one (YouTube cuts old versions off)."""
    found = []
    for d in os.environ.get("PATH", "").split(os.pathsep) + [os.path.expanduser("~/.local/bin")]:
        p = os.path.join(d, "yt-dlp")
        if d and os.path.isfile(p) and os.access(p, os.X_OK):
            found.append((os.path.getmtime(p), p))
    return max(found)[1] if found else None


def resolve(url, mode):
    """yt-dlp for one video. Returns (title, [main stream, audio stream or None]); a stream is
    {"url", "headers", "chunked"}."""
    exe = find_ytdlp()
    if not exe:
        fail("yt-dlp is not installed (needed to play web pages). Install it, e.g. pipx install yt-dlp")
    cmd = [exe, "--no-update", "--no-playlist", "--playlist-items", "1", "--no-warnings", "-f", FORMATS[mode], "-O", FIELDS]
    for rt in ("deno", "node"):                              # a JavaScript runtime gives yt-dlp more YouTube formats
        if shutil.which(rt):
            cmd += ["--js-runtimes", rt]
    cmd += ["--", url]
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        fail("yt-dlp took too long for " + url)
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
        fail("yt-dlp could not read the page: %s\n(an old yt-dlp is the usual cause: update it)" % err[:300])
    lines = r.stdout.strip().splitlines()
    if not lines:
        fail("yt-dlp found nothing to play on " + url)
    info = json.loads(lines[0])
    log("resolved %s (%s) in %.1f s: %s" % (url, mode, time.time() - t, info.get("format_id")))

    def stream(f):
        chunked = bool((f.get("downloader_options") or {}).get("http_chunk_size")) or \
            urllib.parse.urlsplit(f["url"]).hostname.endswith(".googlevideo.com")
        return {"url": f["url"], "headers": f.get("http_headers") or {}, "chunked": chunked,
                "protocol": f.get("protocol", "")}

    fmts = info.get("requested_formats") or [info]
    streams = [stream(f) for f in fmts]
    if len(streams) == 1:
        streams.append(None)
    return info.get("title") or url, streams[:2]


# ---------------------------------------------------------------- relay

def relay_secret():
    try:
        with open(SECRET_FILE, encoding="ascii") as f:
            s = f.read().strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{20,}", s):
            return s
    except OSError:
        pass
    os.makedirs(STATE, exist_ok=True)
    s = secrets.token_urlsafe(24)
    fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(s)
    return s


def relay_url(s):
    q = {"u": s["url"]}
    if s["headers"].get("User-Agent"):
        q["ua"] = s["headers"]["User-Agent"]
    if s["headers"].get("Referer"):
        q["ref"] = s["headers"]["Referer"]
    return "http://127.0.0.1:%d/%s/s?%s" % (RELAY_PORT, relay_secret(), urllib.parse.urlencode(q))


def relay_alive():
    try:
        c = http.client.HTTPConnection("127.0.0.1", RELAY_PORT, timeout=1)
        c.request("GET", "/%s/ping" % relay_secret())
        ok = c.getresponse().status == 200
        c.close()
        return ok
    except OSError:
        return False


def ensure_relay():
    if relay_alive():
        return
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--relay"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        time.sleep(0.1)
        if relay_alive():
            return
    fail("the local relay did not start (port %d in use?)" % RELAY_PORT)


class Upstream(http.client.HTTPSConnection):
    """Tries the address that worked last time first, then each address of the host with a short connect
    timeout (Python has no "happy eyeballs": one dead address would otherwise stall every chunk for the
    whole timeout), then reads with a long timeout."""
    good = {}                                                # (host, port) -> address that connected

    def connect(self):
        key = (self.host, self.port)
        addrs = [a for a in socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)]
        addrs.sort(key=lambda a: a[4][0] != Upstream.good.get(key))
        err = OSError("no address for " + self.host)
        for fam, kind, proto, _, addr in addrs:
            s = socket.socket(fam, kind, proto)
            s.settimeout(4)
            try:
                s.connect(addr)
            except OSError as e:
                s.close()
                err = e
                continue
            Upstream.good[key] = addr[0]
            s.settimeout(30)
            self.sock = self._context.wrap_socket(s, server_hostname=self.host)
            return
        raise err


class UpstreamError(OSError):
    def __init__(self, code):
        super().__init__("HTTP %d" % code)
        self.code = code


def fetch(url, headers, hops=5):
    """GET with headers, following redirects; the response (2xx), else UpstreamError / OSError."""
    u = urllib.parse.urlsplit(url)
    c = Upstream(u.hostname, u.port or 443)
    c.request("GET", (u.path or "/") + ("?" + u.query if u.query else ""), headers=headers)
    r = c.getresponse()
    if r.status in (301, 302, 303, 307, 308) and hops > 0 and r.getheader("Location"):
        loc = urllib.parse.urljoin(url, r.getheader("Location"))
        r.close()
        c.close()
        if not loc.startswith("https://"):
            raise UpstreamError(r.status)
        return fetch(loc, headers, hops - 1)
    if r.status >= 300:
        r.close()
        c.close()
        raise UpstreamError(r.status)
    return r


class Relay(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    secret = ""
    last = time.time()
    active = 0
    lock = threading.Lock()

    def log_message(self, fmt, *args):
        pass

    def do_HEAD(self):
        self.serve(body=False)

    def do_GET(self):
        self.serve(body=True)

    def upstream(self, url, ua, ref, start, end):
        return fetch(url, {"Range": "bytes=%d-%d" % (start, end), "User-Agent": ua or VLC_UA, "Connection": "close",
                           **({"Referer": ref} if ref else {})})

    def serve(self, body):
        cls = Relay
        with cls.lock:
            cls.active += 1
            cls.last = time.time()
        try:
            self._serve(body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass                                             # VLC closed the connection (seek, stop)
        finally:
            with cls.lock:
                cls.active -= 1
                cls.last = time.time()

    def _serve(self, body):
        path, _, query = self.path.partition("?")
        if path == "/%s/ping" % self.secret:
            return self.reply(200, b"ok")
        if path != "/%s/s" % self.secret:
            return self.reply(404, b"")
        q = urllib.parse.parse_qs(query)
        url = (q.get("u") or [""])[0]
        if not url.startswith("https://"):
            return self.reply(400, b"")
        ua, ref = (q.get("ua") or [""])[0], (q.get("ref") or [""])[0]
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        start = int(m.group(1)) if m and m.group(1) else 0
        last = int(m.group(2)) if m and m.group(2) else None
        try:
            r = self.upstream(url, ua, ref, start, min(start + CHUNK - 1, last if last is not None else 1 << 62))
        except UpstreamError as e:
            if e.code == 416:
                return self.reply(416, b"")
            log("relay: upstream HTTP %d" % e.code)
            return self.reply(502, b"")
        except OSError as e:
            log("relay: upstream %s" % e)
            return self.reply(502, b"")
        total = None
        cr = re.match(r"bytes \d+-\d+/(\d+)", r.getheader("Content-Range") or "")
        if cr:
            total = int(cr.group(1))
        elif r.status == 200 and r.getheader("Content-Length"):
            total = start + int(r.getheader("Content-Length"))
        if total is None:
            log("relay: upstream gave no length")
            return self.reply(502, b"")
        end = total - 1 if last is None else min(last, total - 1)
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", r.getheader("Content-Type") or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if m:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, total))
        self.end_headers()
        if not body:
            r.close()
            return
        pos = start
        while pos <= end:
            while True:
                buf = r.read(64 * 1024)
                if not buf:
                    break
                buf = buf[:end - pos + 1]
                self.wfile.write(buf)
                pos += len(buf)
                Relay.last = time.time()
            r.close()
            if pos > end:
                break
            for attempt in range(3):                         # next chunk (retry a dropped one)
                try:
                    r = self.upstream(url, ua, ref, pos, min(pos + CHUNK - 1, end))
                    break
                except OSError as e:
                    log("relay: chunk at %d: %s" % (pos, e))
                    time.sleep(1 + attempt)
            else:
                return

    def reply(self, code, data):
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)


class RelayServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_relay():
    Relay.secret = relay_secret()
    try:
        srv = RelayServer(("127.0.0.1", RELAY_PORT), Relay)
    except OSError as e:
        log("relay: cannot listen on %d: %s" % (RELAY_PORT, e))
        sys.exit(1)
    log("relay: started (pid %d)" % os.getpid())

    def idle():
        while True:
            time.sleep(60)
            if Relay.active == 0 and time.time() - Relay.last > RELAY_IDLE:
                log("relay: idle, exiting")
                srv.shutdown()
                return
    threading.Thread(target=idle, daemon=True).start()
    srv.serve_forever()


# ---------------------------------------------------------------- VLC

def vlcrc_candidates():
    cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return [os.path.join(cfg, "vlc", "vlcrc"),
            os.path.expanduser("~/.var/app/org.videolan.VLC/config/vlc/vlcrc"),
            os.path.expanduser("~/snap/vlc/common/.config/vlc/vlcrc")]


def web_interface():
    """(port, password) of VLC's web interface from the vlcrc that linux/setup.sh wrote, or None."""
    for rc in vlcrc_candidates():
        try:
            with open(rc, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        val = lambda k: (re.findall(r"(?m)^%s=(.*)$" % re.escape(k), text) or [""])[-1].strip()
        if "http" in val("extraintf").split(":") and val("http-password"):
            return int(val("http-port") or WEB_PORT), val("http-password")
    return None


def web_request(web, query):
    """GET requests/status.json?<query> with the password; the HTTP status."""
    port, password = web
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    auth = base64.b64encode((":" + password).encode()).decode()
    c.request("GET", "/requests/status.json" + ("?" + query if query else ""), headers={"Authorization": "Basic " + auth})
    r = c.getresponse()
    r.read()
    c.close()
    return r.status


def vlc_running():
    me = str(os.getuid())
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if str(os.stat("/proc/" + pid).st_uid) != me:
                continue
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                argv0 = f.read().split(b"\0")[0]
        except OSError:
            continue
        if os.path.basename(argv0) in (b"vlc", b"cvlc"):
            return True
    return False


def vlc_command():
    """VLC's command from the "VLC Amp" launcher (native, Flatpak or Snap), else plain vlc."""
    if os.environ.get("VLCAMP_VLC"):                         # tests: the VLC to start
        return shlex.split(os.environ["VLCAMP_VLC"])
    data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    try:
        with open(os.path.join(data, "applications", "vlc-amp.desktop"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("Exec="):
                    argv = [a for a in shlex.split(line[5:].strip())
                            if a not in ("%U", "%u", "%F", "%f", "@@u", "@@", "--started-from-file")]
                    if argv:
                        return argv
    except (OSError, ValueError):
        pass
    return ["vlc", "--no-media-library"]


def play(url, mode):
    running = vlc_running()
    web = web_interface() if running else None
    if web:
        try:
            if web_request(web, "") != 200:
                log("web interface refused the password")
                web = None
        except OSError as e:
            log("web interface: %s" % e)
            web = None
    if running and not web:
        mode = "single" if mode == "video" else mode        # D-Bus takes no item options: one stream
    title, (main, audio) = resolve(url, mode)
    if any(s and s["chunked"] for s in (main, audio)):
        ensure_relay()

    def mrl(s):
        return relay_url(s) if s["chunked"] else s["url"]

    opts = ["meta-title=" + title.replace("\n", " ")]
    if audio:
        opts.append("input-slave=" + mrl(audio))
    if not main["chunked"]:
        if main["headers"].get("User-Agent"):
            opts.append("http-user-agent=" + main["headers"]["User-Agent"])
        if main["headers"].get("Referer"):
            opts.append("http-referrer=" + main["headers"]["Referer"])
    item = mrl(main)

    if web:
        q = urllib.parse.urlencode([("command", "in_play"), ("input", item)] + [("option", o) for o in opts],
                                   quote_via=urllib.parse.quote)    # %20: VLC's web interface keeps a "+"
        try:
            if web_request(web, q) == 200:
                log("sent to the running VLC: %s" % title)
                return
            log("web interface refused the request")
        except OSError as e:
            log("web interface: %s" % e)
    cmd = vlc_command()
    if running:
        cmd += ["--one-instance", item]                      # D-Bus: into the running VLC (it drops item options)
    else:
        cmd += [item] + [":" + o for o in opts]
    log("starting: %s ... (%s)" % (cmd[0], title))
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def main(argv):
    if argv[:1] == ["--relay"]:
        return run_relay()
    if argv[:1] == ["--resolve"]:
        rest = argv[1:]
        mode = "audio" if "--audio" in rest else "video"
        rest = [a for a in rest if a != "--audio"]
        if not rest:
            fail("usage: --resolve [--audio] URL")
        title, streams = resolve(rest[0], mode)
        print(json.dumps({"title": title, "streams": streams}, indent=1))
        return
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        sys.exit(2)
    url, mode = parse_link(argv[0])
    log("link: %s (%s)" % (url, mode))
    play(url, mode)


if __name__ == "__main__":
    main(sys.argv[1:])
