# skins2: relative seek action (seek by +/- N seconds from a skin button)

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface (all platforms).
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

A skin author wants a "rewind 10 s" and "forward 10 s" button, as on every hi-fi / media-player
transport. skins2 has no action that moves the position by an offset. The only seek a skin can
do is absolute: a Slider bound to the `time` variable jumps to the value under the pointer.

## Current behaviour and evidence

- `modules/gui/skins2/src/vlcproc.cpp`, `VlcProc::VlcProc`: the time variable is `time`; the
  registered variables include `time` and `vlc.isSeekable`. No seek action is registered.
- `modules/gui/skins2/commands/cmd_input.cpp` (`3.0.x`): the eight commands are CmdPlay, CmdPause,
  CmdStop, CmdSlower, CmdFaster, CmdMute, CmdVolumeUp, CmdVolumeDown. None calls
  `input_ControlPush`. `CmdSlower` / `CmdFaster` trigger `rate-slower` / `rate-faster`, which change
  playback **speed**, not position. A skin using them as "rewind" plays slower, it does not go back.
- The skin's verified action list (BACKLOG.md, section 2) has no seek entry.
- Lua can do it (`vlc.var.set(vlc.object.input(), "time", t)` in microseconds,
  `docs/lua-api-notes.md` Q3), but a Lua interface cannot add a skin button. Verified in the same notes.

**Unverified:** no full grep of every `commands/*.cpp` file for a seek command. The file listing of
`commands/` shows no `cmd_seek.*`. Please check before filing.

## Proposed API

- Action `vlc.seekRelative(<seconds>)`: negative or positive integer / float seconds, clamped to
  `[0, length]`, no-op when nothing is seekable (`vlc.isSeekable` false).
- Optional: a `vlc.seekRelative` variant on the `playlist` / `input` namespace if the maintainers
  prefer that naming. The name is a suggestion, not an existing API.
- Implementation hint: `input_ControlPush( p_input, INPUT_CONTROL_SET_TIME, &t )` with
  `t = current_time + offset`, the same path the `time` slider already uses.

## Example theme XML (proposed)

```xml
<Button id="b_rew10" x="40" y="60" width="24" height="24"
        action="vlc.seekRelative(-10)" tooltiptext="Back 10 s" />
<Button id="b_fwd10" x="68" y="60" width="24" height="24"
        action="vlc.seekRelative(10)"  tooltiptext="Forward 10 s" />
```

## Acceptance criteria

1. `vlc.seekRelative(-10)` at 3 s goes to 0 s (clamped), at 30 s goes to 20 s.
2. `vlc.seekRelative(+10)` near the end stops at the end and advances the playlist as a normal end-of-track.
3. No effect and no error when nothing is playing or the input is not seekable (streams).
4. Works with the `time` slider in the same skin (no desync: the slider shows the new position).
5. Documented in the skins2 action list.
