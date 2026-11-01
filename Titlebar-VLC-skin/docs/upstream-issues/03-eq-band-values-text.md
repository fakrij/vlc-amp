# skins2: equalizer band values as text (dB readout)

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface.
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

Each EQ fader should show its dB value as text (e.g. "+3.0") above the slider, and the
current preamp value too. skins2 only moves the slider; the number cannot be shown by a Text
control, so the skin draws the dB value into the slider's background frames (41 frames, 1 dB
steps), which costs memory and cannot follow a value that is not one of the frames.

## Current behaviour and evidence

- `modules/gui/skins2/vars/equalizer.cpp` (`3.0.x`): each band is a `VarPercent` (float 0..1,
  mapped to dB by `dB = 40 * p - 20`, so -20 .. +20 dB). It is not a text variable.
- The dB text exists only inside `EqualizerBands::onUpdate()`, where the band values are serialised
  into the `equalizer-bands` string written to the VLC variable / config. That string is not a
  skin variable that a Text control can read.
- `modules/gui/skins2/utils/var_text.cpp`: the text codes handled are `$H $T $t $L $l $D $d $V $N
  $F $B $S $R`. None reads an equalizer band or the preamp. So a Text control cannot show
  `equalizer.band(i)` or the preamp.
- `vlcproc.cpp` registers `equalizer.isEnabled`, `equalizer.preamp` and `equalizer.band(i)` as
  variables. They are sliders' values, not text.
- The skin's current workaround is in `source/build_skin.py` (slider frames with the dB value drawn in).

**Unverified:** whether a Text control created with `text="$<code>"` could be pointed at a
`VarPercent` by a generic mechanism in the 3.0.x parser. The `var_text.cpp` table suggests not;
confirm with the parser code (`parser/builder.cpp`) before filing.

## Proposed API

- Text codes (any letter that is free): `$E<i>` = band i in dB with one decimal, for i = 0..9, and
  `$E` for preamp. Alternatively a Text attribute `variable="equalizer.band(3)" format="%+.1f"`.
- Keep the value formatted in the skin language's decimal separator, as `$V` is.

## Example theme XML (proposed)

```xml
<Text id="t_eq_b3" x="120" y="4" width="30" height="10" font="lcd10"
      text="$E3" alignment="center" scrolling="none" focus="false" />
```

## Acceptance criteria

1. The text shows the band's dB value with one decimal, `-20.0` .. `+20.0`, updated when the slider
   moves (mouse, keyboard, preset change).
2. With the equaliser off, the text shows the value of the last set band (or "0.0"), not blank.
3. Works for all 10 bands and the preamp; no memory cost per band (no frame sheets).
4. The format is documented next to `$V` / `$B` in the skins2 text codes.
