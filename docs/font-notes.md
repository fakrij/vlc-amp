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
