# skins2: text variables for track tags and codec (artist, album, genre, year, codec, channels)

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface.
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

A skin wants to show the playing track's artist and album in its own boxes, and the codec and channel
count in the format chip (STEREO, MP3, FLAC). skins2 has no text code for any of them. The only
format chip today shows the file extension (`$F`, right-aligned, see
`docs/vlc-feature-requests.md`), because the true codec is not available.

## Current behaviour and evidence

- `modules/gui/skins2/utils/var_text.cpp` (`3.0.x`): the text codes are `$H $T $t $L $l $D $d $V $N
  $F $B $S $R`. `$N` is the stream name, `$F` the stream URI, `$B` bit-rate in kbps, `$S` sample
  rate in kHz (integer). No artist, album, genre, year, codec or channel.
- `modules/gui/skins2/src/vlcproc.cpp`: `VlcProc::update_current_input` builds `streamName` with
  `vlc_strfinput( pInput, psz_fmt )` where `psz_fmt` is the `input-title-format` option. `bitrate` and
  `samplerate` come from the input's `bit-rate` and `sample-rate` variables. No codec, no tags as
  separate variables.
- `src/text/strings.c` (`3.0.x`, `vlc_strfinput`): the title-format escapes include metadata
  `$a` artist, `$b` album, `$g` genre, `$A` date, `$t` title, `$n` track number, and the input
  variables `$B`, `$S`, `$C` (chapter), and the item `$D`, `$F`, `$N`. **There is no codec-name escape,
  and the function never reads the elementary-stream format, so channel count is not available.**
- Consequence: artist / album can reach a skin only as one combined string, through the title box
  (`$N` with a title format such as `$a - $b`). They cannot be placed in separate boxes.
- Lua can read tags and the item (`vlc.playlist.get` item `metas()`, `docs/lua-api-notes.md` Q4),
  but a Lua interface cannot make a skins2 text control show them (see
  `docs/vlc-feature-requests.md`, the codec section).

**Unverified:** whether `es_format` (codec fourcc, channels) is available through an input variable
that skins2 could read. Not checked; the request is written so that either way works.

## Proposed API

Text codes (free letters to be chosen by the maintainers), each reading the playing input item:

| Code | Value | Source (proposed) |
|---|---|---|
| `$G` | artist | item meta `artist` |
| `$A`? | album | item meta `album` (letter to be chosen; `$A` is taken by date in strfinput) |
| `$Y` | year | item meta `date` |
| `$E`? | genre | item meta `genre` (letter to be chosen) |
| `$K` | codec short name, e.g. `FLAC`, `MP3` | elementary stream `fmt.i_codec` |
| `$X` | channel layout, e.g. `2.0`, `5.1` (letter chosen to avoid `$C`, which is chapter in the title-format escapes) | audio `fmt.audio.i_channels` |

The codes are suggestions. The request is for the data, the letters are up to the maintainers.
Also note: `$G` and `$K` are not used by `var_text.cpp` or `strings.c` in 3.0.x (checked for these two only).

## Example theme XML (proposed)

```xml
<Image id="chip_codec" x="358" y="90" width="41" height="16" image="chip_fmt" />
<Text id="t_codec" x="367" y="92" width="24" height="10" font="lcd10"
      text="$K" alignment="right" scrolling="none" focus="false" />
<Text id="t_artist" x="222" y="6" width="300" height="12" font="lcd10"
      text="$G" scrolling="none" focus="false" />
```

## Acceptance criteria

1. `$K` shows `MP3`, `FLAC`, `AAC` ... for the playing track, empty when no track plays.
2. `$X` shows the channel layout; mono, stereo and 5.1 files give different values.
3. `$G`, the album and the year codes show the item's tags, empty when the tag is missing.
4. Values update when a new track starts (no stale value from the previous track).
5. Codes are documented next to `$N` / `$B` / `$S`.
