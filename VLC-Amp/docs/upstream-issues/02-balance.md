# skins2: stereo balance variable and balance slider

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface.
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

A hi-fi style skin shows a BAL (balance) slider next to VOL. skins2 has a volume variable and a
mute variable, but nothing for left / right balance, so the slider cannot be drawn with a value and
cannot change the balance.

## Current behaviour and evidence

- `modules/gui/skins2/src/vlcproc.cpp`, `VlcProc::VlcProc`: the variables are `volume`,
  `vlc.isMute`, `vlc.hasAudio`, `equalizer.*`, `speed`, `bitrate`, `samplerate`, ... No balance,
  pan or stereo variable. Callbacks in the same file: `volume`, `mute`, `audio-filter`, no balance.
- `modules/gui/skins2/commands/cmd_audio.cpp`: the only audio command class is `CmdSetEqualizer`
  (enable / disable the `equalizer` filter). It sets no volume, mute, balance or pan.
- The skin's volume commands are `playlist_VolumeUp` / `playlist_VolumeDown` (`cmd_input.cpp`).
- Background note: BACKLOG.md, "Flat style" section: "no pan, balance or stereo-mode variable in
  `libskins2_plugin.so`; no custom actions".

**Unverified:** which VLC audio option or variable carries the balance in 3.0.x (the name of a core
balance / stereo option was not checked against the source). Please confirm before filing, so the
request names the right core variable.

## Proposed API

- Variable `equalizer.balance` (or `volume.balance`), range -100 .. +100 (percent, 0 = centre),
  readable as a `VarPercent` like `volume`, and settable.
- A Slider bound to it, with the same `value` / `points` syntax as the `volume` slider.
- Optional action `vlc.balance(<-100..100>)` for buttons (e.g. "centre" reset).

## Example theme XML (proposed)

```xml
<Slider id="s_bal" x="200" y="8" width="60" height="8" value="balance"
        points="(0,4),(59,4)" thickness="8" tooltiptext="Balance" />
<Button id="b_bal_c" x="262" y="8" width="16" height="8"
        action="vlc.balance(0)" tooltiptext="Centre balance" />
```

## Acceptance criteria

1. Balance slider moves the stereo image left and right; centre (0) is the default after a restart.
2. The slider follows changes made elsewhere (keyboard, VLC menu, Lua).
3. Works with the audio output in use (no effect or a clear log message when the output has
   fewer than 2 channels).
4. Value is restored from `vlcrc` on start, as `volume` is.
5. Documented as a skin variable.
