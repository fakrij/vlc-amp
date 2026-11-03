# Hi-fi redesign: what VLC 3.0 skins2 cannot do

Concept: the "VLC Modular PRO" HTML mockup (2026-10-31). Everything skins2 can draw is implemented
(the hi-fi style, the only style). The rest is a list of requests for VLC developers.

| Concept feature | Why not possible | Request to VLC |
|---|---|---|
| Rewind / forward 10 s buttons | No relative-seek action. The strip's `<<` / `>>` buttons are slower / faster (playback speed) | Actions `vlc.seekRelative(<s>)` or `playlist.jump(<s>)` |
| Balance (BAL) slider | No pan / balance / stereo-mode variable | Variable `equalizer.balance` + slider support |
| STEREO chip, real codec label | No channel count or codec name in the text variables. Workaround in use: `$F` (path) in a 4-character right-aligned box shows the file extension (`.wav`, `flac`) | Text variables `$X` (channels), `$K` (codec); see draft 04 |
| Dock to top / dock to taskbar segments next to the pin | Window positioning is the OS's, skins2 has no such actions (the Windows helper does it outside VLC) | Action `vlc.dock(top|bottom)` or an on-top / edge-snap attribute |
| Playlist as columns (number, title, duration) | Playtree is a single column | Multi-column Playtree (`<Playtree columns=...>`) |
| Glow / soft shadows | X11 skins2 draws images without alpha blending (semi-transparent = black) | Alpha blending in the X11 graphics backend |
| Per-item hover / selection styling (rounded rows with border) | Playtree only supports colours, no row shapes | Row background bitmaps for Playtree |
| Title marquee with scrub fill and spec chips in one box | Text control cannot sit on a stretchable chip; chips are fixed images | none needed (done with fixed chips) |
| Strip rewind / forward, stop, grip, time box with volume fill | **Done** | - |

## Done in this fork
- Hi-fi look: bevelled buttons, accent ring on lit toggles (PL, EQ, play, pin), metallic slider knobs with accent notch, metallic EQ knobs, recessed pin well, bitrate / sample-rate chips.
- Strip: stop, slower, faster added (min width 420 -> 480). Full player: stop added.

- EQ faders: lit fill up to the knob and the dB value above each fader (drawn into the slider's 41 background frames, 1 dB each), header bars on all panels, labelled STRIP button, title box in the full player is a seek bar with progress fill.

## Playlist columns and track tags (tested 2026-11-01)
The playlist is drawn by the Playtree control: one text per row, built inside skins2 (title or file name), no
variables, no columns, no duration. Every `$A`-`$Z`, `$a`-`$z` text variable was tried: only `$B` bitrate, `$S` kHz,
`$D` / `$d` / `$T` / `$t` / `$L` / `$l` times, `$F` path, `$N` name, `$R` speed, `$V` volume resolve; there is no
artist, album, genre, year or channel variable. Request: Playtree columns (`<PlaytreeColumn var="duration" width=...>`)
and text variables for the tags of the playing item.

## Upstream issue drafts

Each row above has a draft in [docs/upstream-issues/](upstream-issues/README.md): 01 relative seek,
02 balance, 03 EQ values as text, 04 tag and codec variables, 05 Playtree columns, 06 dock / edge-snap,
07 alpha on X11, 08 Playtree row bitmaps. Nothing is filed yet.

## Codec label: can it be done without upstream changes? (H16)

**Conclusion: no.** The chip can show only what skins2 already reads. A real codec name needs a new
skins2 variable (upstream, draft 04). The `$F` extension workaround stays.

What the skin can read (3.0.x, `modules/gui/skins2/`):

- Text codes (`utils/var_text.cpp`): `$N` (title, from the `input-title-format` option), `$F` (URI),
  `$B` (bit-rate, kbps), `$S` (sample rate, kHz, integer), `$R`, times, `$V`. No codec, no channels.
- The title format (`src/text/strings.c`, `vlc_strfinput`) has tag escapes (`$a` artist, `$b` album,
  `$g` genre, `$A` date) but **no codec-name escape** and no channel count. Its `$C` is the chapter.
- Skin variables fed by VLC (`src/vlcproc.cpp`): `bitrate` from the input's `bit-rate`, `samplerate`
  from `sample-rate`, `streamName`, `streamURI`, `streamArt`. Nothing else is fed.

What a Lua interface or extension can do (`docs/lua-api-notes.md`):

- It can set VLC variables: the input's `time` (Q3), `equalizer-*` through `vlc.equalizer` (Q2), and the
  input's `bit-rate` (already used by the Lua script for FLAC bitrate, `docs/architecture.md`).
  skins2 then shows `bit-rate` as `$B`, so the path works for **numbers that skins2 already reads**.
- It cannot write into a skins2 control. There is no API for skin controls in the Lua library list
  (`vlc.var`, `vlc.playlist`, `vlc.input`, `vlc.equalizer`, `vlc.misc`, `vlc.strings`; Q1-Q5), and
  skins2 has no variable for a free text value. A codec name has no skins2 variable to be written to.
- A Lua extension is not better: extension dialogs are not drawn by skins2 (BACKLOG.md, section 2 B).

Options and what they would give:

| Option | Result |
|---|---|
| Lua sets `bit-rate` / `sample-rate` to show codec info | Numbers only; wrong meaning, not a codec |
| Lua writes the codec into the item's metadata, and the title format shows it | Would need the title box to show it (not the chip), and Lua writing item metadata is **not verified** (`lua-api-notes` lists only `metas()`) |
| Keep `$F` extension | Works for common formats; shows `flac`, `.mp3`; not the real codec (e.g. a `.mp4` with AAC) |
| Upstream: text codes `$K` / `$X` (draft 04) | The only route to a real codec label |

**Not confirmed (left open):**

- Whether Lua can set an item meta field (`metas()` is read-only in the notes, the write side was not checked).
- Whether skins2 re-reads `$N` when only metadata changes (`VlcProc` callbacks were read for `streamName` set on input change; not tested).
- Whether `input-title-format` can be changed at run time from Lua and affects `$N` at once.
- Whether `es_format` (codec, channels) is readable as an input variable from Lua (not checked; `docs/lua-api-notes.md` Q3 lists only `time`, `length`, `position`).

Close H16 with this note; reopen only if draft 04 is accepted or the Lua points above are tested and work.

## Format chip for names without an extension (PP39)

Limit, no workaround in 3.0.x. `$F` is the stream URI / local path (`utils/var_text.cpp`, `VarText::get`; value set in
`vlcproc.cpp` `update_current_input`), shown right-aligned in a 4-cell box, so "4 No extension" shows "sion" and an
http URL shows its last 4 characters. skins2 has no extension variable, substring or conditional text; the booleans a
`visible=` can test (`vlc.isPlaying`, `hasVout`, `hasAudio`, `isMute`, `equalizer.isEnabled`, `playtree.isRandom` ...) do not
depend on the name; Lua cannot change the item URI (no setter) and `$F` is not a meta. Upstream fix: a codec or
extension variable (draft 04).
