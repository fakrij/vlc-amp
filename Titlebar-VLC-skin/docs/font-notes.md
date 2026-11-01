# Font notes (T19, for the online configurator)

Checked against VLC 3.0.x `modules/gui/skins2` (`parser/builder.cpp`
`Builder::addFont` / `getFilePath`, `src/ft2_font.cpp`) and by running real
VLC 3.0.20 under the test harness with a throwaway skin (not in the repo).

## How skins2 loads fonts

- `<Font id=".." file="fonts/X.ttf" size="N"/>`: `size` is pixels
  (`FT_Set_Pixel_Sizes(face, 0, N)`). The `.vlt` is a tar.gz unpacked to a
  temp dir; `file` is resolved as `<unpacked dir>/<file>` (`/` is the
  separator on every OS, `\` only warns). If that fails, VLC tries
  `<VLC resource path>/fonts/<file>`. No system font lookup, no fallback font.
- The whole file is read into memory and opened with `FT_New_Memory_Face`,
  **face index 0**, then the Unicode charmap is selected. Any format FreeType
  reads works: `.ttf` and `.otf` (CFF) both load. The file name needs no
  special form, but keep it ASCII.
- Glyphs are rendered with `FT_LOAD_DEFAULT` (hinted), advance = integer
  pixels (`advance.x >> 6`), plus `FT_Get_Kerning` (kern table / legacy
  kerning only). No HarfBuzz: **OpenType features (`tnum`, `zero`, ligatures,
  GPOS kerning) are never applied.**
- Variable fonts load only their **default instance**; the weight cannot be
  chosen. A font with a missing / invalid file is skipped (log error); texts
  using that font id then fail, so ship the file you reference.

## Test result (screenshots at 100 % = 12 / 26 px, 150 % = 18 / 39 px)

Test strings `1111111`, `8888888`, `0:00:00`, `-8:88:88`, left aligned.

| Font | File | Size (bytes) | Loads | Digits tabular | Verdict |
|---|---|---|---|---|---|
| DejaVu Sans Mono (current) | .ttf | 343,140 | yes | yes, 7/11/16/23 px at 12/18/26/39 | ok |
| JetBrains Mono Regular | .ttf | 270,224 | yes | yes, same advances | ok |
| Roboto Mono (variable, default = Regular) | .ttf | 183,700 | yes | yes | ok |
| Source Code Pro Regular | .otf (CFF) | 131,128 | yes | yes | ok, proves .otf works |
| Source Sans 3 (variable) | .ttf | 646,340 | yes | digits equal (6/9/12 px) but colon is narrow; default instance is ExtraLight | usable only as a static Regular, looks thin |
| Inter (variable) | .ttf | 876,576 | yes | **no**: digit advance 5-8 px at 12 px (`1` is narrow); `tnum` is not applied | rejected, time would jitter |

Rule for the configurator: accept a font only if all ten digits have the same
advance at the sizes used (check with Pillow `getlength` per digit at the
hinted pixel size, as in the test); monospace fonts always pass. Prefer static
Regular files over variable ones. The mono fonts leave a wide gap around `:`
(a full cell), exactly like DejaVu Sans Mono today.

Widths in the 150 % row at 39 px were clipped by the test's cell width; this is
a test artefact, not a font problem.

## Licences

All tested fonts are OFL 1.1 (DejaVu: Bitstream Vera licence, already shipped
as `fonts/LICENSE-DejaVu.txt`). Shipping a font inside a `.vlt` is
redistribution, so put the licence text next to it (`fonts/LICENSE-<name>.txt`,
the copyright line included): OFL.txt for JetBrains Mono, Roboto Mono, Inter,
Source Sans 3; LICENSE.md (OFL) for Source Code Pro. Source Sans 3 and Source
Code Pro have Reserved Font Name "Source": do not subset or modify them under
that name (a subset counts as modification), ship the unmodified file.
Fonts must not be sold on their own; the skin is free, so that is fine.
A user-supplied TTF in the configurator stays on the user's machine; the page
must not re-host it, and its licence is the user's responsibility.

## Hi-fi font test 2026-11-01

Task H13: keep DejaVu Sans Mono, or take the concept's font (Share Tech Mono / JetBrains Mono).
Network was available. Fonts downloaded into their own directories (`/tmp/h13fonts/<name>/`), read only
with `python -I`: JetBrains Mono Regular (JetBrains/JetBrainsMono master), Share Tech Mono Regular and
Roboto Mono `[wght]` variable default = Regular (google/fonts `ofl/`). Builds:
`source/build_skin.py --bar-height {24,40} --width 620 --scale {1,1.5} --font <ttf> --out <dir>`
(16 builds), run in real VLC 3.0.20 under Xvfb, strip and full player (expand click scaled), 100 % and 150 %.
Crops (NEAREST, zoomed) are in `docs/img-audit/h13/`: `full_100.png`, `full_150.png`, `strip_bar24_*`,
`strip_bar40_*`, `digits30_*`, `title14_*`, `chips_labels_*`, `elapsed_of*`, `descenders_strip24/40_100`,
`timebox_strip24_100`.

| Font | Loads in skins2 | 24 px strip (12 px text) | 40 px strip | 30 px digits | Chip ".wav" in 24 px box | Licence | .ttf / .vlt (24, 100 %) |
|---|---|---|---|---|---|---|---|
| DejaVu Sans Mono (current) | yes | clean, title and "p" fit | good | solid, tabular (18 px) | fits exactly (4 x 6 = 24) | Bitstream Vera (shipped) | 343,140 / 297,751 |
| JetBrains Mono | yes | clean, "p" fits, a bit taller line (17 vs 15) | good | tabular (18 px), dotted zero, fine | fits (4 x 6 = 24) | OFL 1.1, (c) 2020 JetBrains Mono Project Authors | 270,224 / 223,780 |
| Share Tech Mono | yes | thin, smaller, hinting blurs "kHz", "REP1", "PRE" | thin | tabular (16 px), slashed zero, clearly smaller and lighter | **breaks**: advance 5 px at 10 px, 4 chars = 20 px, the box shows a 5th char ("r. wav") | OFL 1.1, Reserved Font Name "Share" (do not modify/subset) | 43,272 / 114,483 |
| Roboto Mono | yes | **"p" descender clipped, time digits sit low** (line 17 px) | digits ok | slashed zero, tabular at 30; **not tabular at 14 px (8/9 px)**; 4 chars = 23 px | fits | OFL 1.1, (c) 2015 Roboto Mono Project Authors | 183,700 (variable) / 222,765 |

Findings
- All four load and render; the bitmap-baked texts (Canvas.text, FONT_MONO "mono" kind) use the same `--font`, but
  FONT_BOLD (labels like PL, EQ, STRIP, DejaVuSans-Bold) is NOT changed by `--font`; so with a switched font the
  bold button labels stay DejaVu Sans Bold. They look consistent in the crops (different role, sans vs mono).
- Digit advances: DejaVu, JetBrains, Share Tech tabular at every used size (10/12/14/26/30/45 px); Roboto Mono
  loses it at 14 px. The colon takes a full cell in all mono fonts, so "00: 14" looks the same gap everywhere.
- Share Tech Mono is the concept's look but is visibly smaller and thinner at 8-10 px and breaks the
  format-chip logic (the chip shows the end of the path in a 24 px box, relying on 6 px advance). Using it needs
  the chip text box narrowed to 20 px per font and a re-test of hinting; not worth it.
- JetBrains Mono is equal or slightly crisper than DejaVu at 30 px and 14 px, the same advances, and the
  .vlt is 74 KB smaller; the zero has a dot (DejaVu: dot too). At 8-10 px "SHUF / LOOP / REP1" is the same
  legibility as DejaVu (no "PKE" artefact seen in either at 100 % or 150 %).

### Recommendation

**Keep DejaVu Sans Mono as default.** No candidate is clearly better; JetBrains Mono is the only equal
alternative (same advances, same chip fit, smaller file) and the one to use if the concept's engineering look is wanted.
To apply JetBrains Mono (not wired in; the licence must ship with it):

```
cp OFL.txt fonts/LICENSE-JetBrainsMono.txt          # from the JetBrains/JetBrainsMono repo
python3 source/build_skin.py --bar-height 24 --width 620 --font fonts/JetBrainsMono-Regular.ttf
```
Generator change for a default switch: `FONT_MONO` and `FONT_FILE` in `source/build_skin.py` (lines ~40/49) to
`fonts/JetBrainsMono-Regular.ttf`, and the `0.602` advance in `bar_metrics` to `0.600`.

Unverified: 125 / 200 % scales, Windows rendering (FreeType hinting differs from Xvfb Linux), light themes,
hour-format times ("-1:23:45") and other chip texts (".mp3", "flac", "opus").
