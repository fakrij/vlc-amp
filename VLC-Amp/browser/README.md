# Play links from the browser in VLC Amp

Right-click a page, a link or a video > **Play in VLC Amp** (or **Play audio
only in VLC Amp**), or click the extension's toolbar button: VLC plays it. Works
for YouTube and the ~1800 other sites [yt-dlp](https://github.com/yt-dlp/yt-dlp)
knows, and for direct media links (`.mp4`, `.mp3`, `.m3u8`, radio streams).

- **Video**: up to 1080p, H.264 where the site has it (least CPU; VP9 / AV1
  otherwise), with the best m4a audio.
- **Audio only**: the best audio stream (m4a first), no video.
- A running VLC gets the item in its playlist and plays it; otherwise VLC starts.
- The playlist shows the video's title.

## Set up

1. **Setup** answers it for you: Windows `Install.cmd` / `Setup.cmd` asks
   "Play videos and music from web pages in VLC?" and can install yt-dlp with
   winget; Linux `sh Install.sh` (or `linux/setup.sh --links`) asks the same.
   This registers the `vlc-amp:` link handler (no admin rights).
2. **yt-dlp** must be installed and **current**: YouTube changes often and an
   old yt-dlp gets HTTP 403 after the first megabytes.
   - Windows: `winget install yt-dlp.yt-dlp`, update with `winget upgrade yt-dlp.yt-dlp`
     (or `yt-dlp -U` for the standalone exe).
   - Linux: `pipx install yt-dlp`, update with `pipx upgrade yt-dlp` (distro
     packages are often too old).
   - Optional: [Deno](https://deno.com) (or Node.js) lets yt-dlp read more
     YouTube formats; it is used when it is on the PATH.
3. **The Chrome extension** (also works in Edge, Brave and Vivaldi):
   - Chrome: open `chrome://extensions`, turn on **Developer mode** (top
     right), click **Load unpacked** and pick the `browser\extension` folder
     (Windows: `%LOCALAPPDATA%\VLC-Amp\browser\extension`; Linux: the
     `browser/extension` folder of the unpacked package). Pin it from the
     puzzle-piece menu to get the toolbar button.
   - Keep the folder where it is: Chrome loads an unpacked extension from that
     folder every time it starts.
   - Edge: the same at `edge://extensions`.
   - Firefox is not supported (its extensions need a different background
     page); the bookmarklet below works there.
4. The first time, Chrome asks "Open Windows Script Host?" (Linux:
   "Open xdg-open?"); tick **Always allow ... to open links of this type** and
   click **Open**.

### Without the extension: a bookmarklet

Make a bookmark with this as its URL, then click it on a video page:

```
javascript:location.href='vlc-amp:play?mode=video&url='+encodeURIComponent(location.href)
```

For audio only, use `mode=audio`.

## How it works

```
browser --vlc-amp:play?mode=video&url=...--> vlc-amp-url.vbs (Windows, no window) / vlc-amp-url.desktop (Linux)
        --> vlc-amp-url.ps1 / vlc-amp-url.py --yt-dlp--> stream URLs (video + audio)
        --> VLC running?  yes: VLC's web interface (127.0.0.1:48080, Setup's password) in_play + item options
                          no:  vlc <video> :input-slave=<audio> :meta-title=<title>
```

- **The relay.** YouTube serves its streams only in closed byte ranges: a
  request for "the rest of the file", which is what VLC sends, gets HTTP 403.
  So those streams go through a small local relay on `127.0.0.1:48081`
  (`VlcAmpRelay.cs` on Windows, the `--relay` mode of `vlc-amp-url.py` on
  Linux). It fetches 10 MB ranges and passes them on as one response, so VLC
  plays and seeks normally. It starts on demand, listens on this computer only,
  takes only URLs with its secret (a random string in
  `%LOCALAPPDATA%\VLC-Amp-state\relay-secret` / `~/.local/state/vlc-amp/relay-secret`)
  and quits after 6 hours without use.
- **Why the web interface.** The audio stream goes to VLC as the item option
  `:input-slave`. VLC ignores that option when it comes from a playlist file
  (it is "unsafe") and drops all item options that come over D-Bus (Linux
  one-instance), but keeps them from its command line and from its web
  interface. On Linux, a running VLC without the web interface (`--no-web`)
  gets a single stream instead: 360p with sound, or audio only.
- **The link is checked.** Only `http://` and `https://` page URLs are
  accepted; on Windows the link reaches the script in an environment variable,
  never on a command line.

## Limits

- Stream URLs expire after about 6 hours and only work from your own IP
  address: a web item saved in a playlist stops playing later. Open it from
  the browser again.
- A playlist page plays its first video.
- Separate video and audio streams can drift slightly apart in VLC 3 on some
  videos.
- Sites with DRM (Netflix, Spotify, ...) cannot be played.
- A page that needs a login (age-restricted or members-only video) needs yt-dlp
  cookies, which this does not set up.

## Files

| File | What |
|---|---|
| `extension/` | The browser extension (Manifest V3): context menu entries and the toolbar button |
| `vlc-amp-url.py` | Linux: the `vlc-amp:` handler and the relay (`--relay`), `--resolve URL` to test yt-dlp |
| `vlc-amp-url.ps1`, `vlc-amp-url.vbs` | Windows: the handler (`-Resolve URL` to test), started hidden by the `.vbs` |
| `VlcAmpRelay.cs` | Windows: the relay (compiled by `vlc-amp-url.ps1 -Relay`) |
| `find-ytdlp.ps1` | Windows: finds `yt-dlp.exe` (PATH or winget's folders) |

Logs: `%TEMP%\vlc-amp-url.log` (Windows), `~/.local/state/vlc-amp/url.log` (Linux).
