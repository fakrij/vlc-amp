# Hi-fi redesign - backlog

Fork of the Titlebar skin rebuilt after the "VLC Modular PRO" concept. Last tidied 2026-11-01.
One style only: flat panels, hairline outlines, no header bars / separators, no side outlines. The former
standard and flat styles are gone (H4, H5).

Build: `python3 source/build_skin.py --bar-height 24` (the default strip, for a title bar; window 620 px wide,
minimum 490). `--bar-height 36` = taskbar, `--bar-height 40` = the concept's floating strip. `--scale 1.25 / 1.5 / 2.0`
for Windows display scaling. Names: `Titlebar-[taskbar-|bar<N>-]<pct>.vlt`. Test in real VLC: `tools/vlc-test.sh build 1 24`,
then `start`, `shot`, `click` (see `tools/README.md`); screenshots: `tools/doc-shots.sh` writes `docs/img-thin/`.

## Where things stand
- The design is finished and merged: thin style, 24 px strip, Midnight and Paper (plus the other themes), memory about
  +16 MB per theme over the original skin.
- The agents' branches and worktrees are deleted (all merged); only `main` exists in this fork.
- Open: the Windows test (only Jiri can run it), a few optional items (below), and the parked configurator.

## Decisions (Jiri)
| Decision | Result |
|---|---|
| Style | **Thin only** (H4); standard and flat styles removed; H5 cancelled |
| Strip height | **24 px default** (H2); 36 (taskbar) and 40 (floating) stay as options |
| Font | **Keep DejaVu Sans Mono** (H13); JetBrains Mono is the only equal alternative |
| Playlist row stripes | **Medium** (stripe contrast about 1.15:1) |
| Paper (light theme) | **Adjustment applied** (H24): dim label 3.3:1, light-theme box outlines doubled (1.9:1); dark themes unchanged |
| Seek knob | **Overhang kept**: the knob is centred on the groove ends (6 / 5 px); an inset turns into a gap on resize |
| Title progress | **Keep the filled box + thumb**; the underline prototype and the pipes idea (H27) are not pursued |
| Seek bar ends | **Not pill-shaped**: groove radius 3 px, fill radius 1 px stay |
| Online configurator | **Parked** (H12) |

## Open items
P1 = before Jiri tests on Windows, P2 = before release, P3 = later. Assignee: Jiri = needs the real machine or a decision;
Haiku = mechanical / report, Sonnet = build, Opus = design.

| # | P | Item | Assignee | Done when |
|---|---|---|---|---|
| H3 | P1 | **Windows 11 test** at 100 / 125 / 150 %: alpha rendering, edges and corners, strip in the title bar, taskbar dock (the helper's window-shape constants and click points were updated from `theme.xml` only, never run), theme follows system dark / light, installers (`Install.cmd`, `Setup.cmd`). Send `%TEMP%\titlebar-helper.log` if the helper misbehaves. | Jiri | Issues listed here; fixes assigned. |
| H12 | parked | **Online configurator**: see "Parked" at the end. | - | - |
| H28 | P3 | **Title frames 51 -> 26** (`title_fill` / `ftitle_fill`): saves about 4 MB per theme (about 9 at 150 %). Risk: a visible step at the playhead. skins2 shows frame `floor(value * (n - 1))` (measured on the seek bar), so a half-step lead like `SEEK_LEAD` should make it safe; untested. | Sonnet | Measured memory, crops at 0 / 50 / 93 % at 620 and 920 px, no visible step; or rejected. |
| H29 | P3 | **More memory headroom**: the thin skin is about 16 MB per theme over the original (budget was about 10). Candidates: H28, the volume sheet, the remaining EQ sheets. | Sonnet | Only reductions with a measured win and no visible change. |
| H30 | P2 | **Wider hit-test coverage** (H26 left it): panels-above layout, footer and transport buttons, menu / minimize / quit, real clicks at 150 / 200 %, all four edges above 125 %; the 40 px title seek "outside-left" reading (4565 px in one sweep, 80 px on retest) was not explained. | Haiku | `docs/hit-test-report.md` extended; failures listed. |
| H31 | P2 | **Spot checks after the final changes**: Ember, Forest, Nord, Dusk, Rose, Custom were only glanced at; the 36 and 40 px strips were not re-shot after the last fixes; confirm the empty-band fix and the click zone at **200 %** (needs `TB_SCREEN=2560x1900x24`). | Sonnet | Contact sheets and a short report; deviations fixed. |
| H32 | P3 | **`linux/setup.sh`** was only syntax-checked (`bash -n`), never run; same for the Linux package. | Sonnet | Run on a clean home directory (or a container); result noted. |
| H33 | P3 | **Soft horizontal icons** (minimize, collapse, menu): after the crisp-icon fix (H22) the 1.4-1.6 px bars straddle two rows at about 80 % instead of one full + one faint row. Same weight, slightly softer. Jiri to look at them on the real screen. | Jiri | Accepted, or a rule to snap thin bars to one row. |
| H34 | P3 | **File the VLC issues**: eight upstream-ready drafts are in `docs/upstream-issues/` (relative seek, balance, EQ values as text, tag / codec variables, Playtree columns incl. length, dock actions, alpha on X11, row bitmaps), with an index and how to file. Sources were read from summaries: check the cited skins2 code before filing. | Jiri | Issues filed, links added to `docs/upstream-issues/README.md`. |
| H35 | P3 | **`--font` does not change the bold labels** (`FONT_BOLD`: PL, EQ, STRIP, button labels stay DejaVu Sans Bold). Only matters if the font is ever switched. | Sonnet | `--font` covers both, or documented. |

### Known limits (not planned)
- The playlist scroll thumb is a fixed 8 x 24 bitmap: no proportional size, cannot be hidden (H20b).
- The playlist cannot show length, number, tags or columns: the Playtree has one text per row and no variables (`docs/vlc-feature-requests.md`).
- No real codec label: `$F` (path) in a 4-character right-aligned box shows only the file extension (H16).
- No rewind / forward by 10 s, balance, EQ presets, dock-to-edge actions (skins2 has no actions for them).
- The window's outer corners are stair-stepped: the window shape is binary (H18: a darker rim was tried, not better).
- Fractional scales (125 / 150 %): the outline is 1.25 / 1.5 px; fills that sit inside it cover the half pixel, so one side can look half a pixel thinner.

## Rules for every agent
- Each agent works in its own git worktree (`git worktree add ../vlc-modular-wt/<id> -b hifi/<id> main`) with its own
  `TB_INSTANCE` and `TB_DISPLAY_NUM` (93 is the main session's); `TB_SCREEN=2560x1900x24` for 200 %. Remove worktree and branch after merging.
- Look at zoomed pixels (Pillow, NEAREST, 6-10x), never at downscaled screenshots; use numeric checks where possible
  (the `/pixel-perfect` skill has the procedure). Tools: `tools/theme-audit.py` (contrast per theme), `tools/bitmap-audit.py`
  (semi-transparent bitmaps), `tools/icon-symmetry.py`, `tools/sync-configurator.py`.
- Fix in the generator and fix the rule, not one element. Record a baseline of staged output first and report exactly which
  files differ after a change (byte-compare `stage-*` directories).
- Do not commit design changes without Jiri's review; docs and tooling freely.
- Memory budget: one theme should stay near 10 MB RSS at 100 % (`smaps_rollup`, 8 s after start, several runs).
  skins2 copies each frame sheet into every slider control: cost = pixels x 4 B x (controls + 1).

## Design rules (what "consistent" means here)
- Margins: 12 px from the window edge to every box, groove and button row; header buttons end at W - 12.
- Corner radii: sections 6 (outer corners only, joined corners square), boxes 4, small boxes / chips 3, buttons 4 (3 below 18 px high).
- Lines: 1 px everywhere; a join between sections is one line (the lower section's top outline).
- Heights: header buttons 22, strip buttons 24 (18 in the 24 px strip), transport buttons 28, chips 16; content centred in its band.
- Thin style: no gradients, no bevel rows, no inner shadow in boxes, EQ and playlist boxes without outline, no side outline on sections,
  title bars draw nothing. Dark themes use light outlines, light themes dark ones (`box_edge`, `EDGE`; light x2).
- Text colours: `CYAN_TXT` values, `CYAN2` secondary, `CYAN_DIM` labels (`tools/theme-audit.py`).
- Fills that sit inside an outline start `inset()` = `int(S)` device px from the box edge.

## Technical notes (things that bite)
- **Naming / window:** `Titlebar-[taskbar-|bar<N>-]<pct>.vlt`; old names such as `Titlebar-150.vlt` still parse. The window is 676 px tall
  (232 + 164 + 280); the Windows helper's `DockShape` constants, pin / theme / flip click points (`VlcDock.cs`), `linux/titlebar-pin.py` and
  `tools/vlc-test.sh quit` were derived from the generated `theme.xml`. Packages: Windows = 24 and 36 px, 100 / 125 / 150 / 200 %,
  Midnight + Paper; Linux = 24 px, Midnight (`tools/make-*-package.sh`).
- **skins2 behaviour (measured / read in source):** `findHitControl` skips hidden controls (hidden duplicate sections cannot steal clicks);
  slider curve points scale with the control on resize (so a knob inset becomes a gap); frame sheets scale horizontally only, height is
  fixed; the frame shown is `floor(value * (n - 1))`; fully transparent pixels are not drawn but still take clicks; a thumb is not clipped to
  its control; Playtree thumb is fixed. X11 draws without alpha blending (semi-transparent pixels turn black), Windows blends: every bitmap
  must be opaque or fully transparent (`tools/bitmap-audit.py` = 0).
- **Resize tab:** its own `resizeE` control (`grip_tab()`), 9 px at x = W - 11, centred on the section's main box; the background slices only move the window.
- **Title progress:** fill frames (51, `TITLE_FRAMES`) + a thumb 2 x `TITLE_S` (10) wide: left half fill colour, right half box colour, accent line at the
  centre; the path is inset by `TITLE_S`; frame 0 is lit too (otherwise the first ~2 s of a track show a dark band at the left).
  Known trade-off: about 10 px lit at 0 % and the bar stops about 10 px short at 100 %. The underline alternative is behind `TB_TITLE_MODE=underline`
  (-6.5 MB at 100 %, -15 MB at 150 %), off.
- **Seek bar:** 101 frames, 10 px high; each frame is drawn half a step ahead (`SEEK_LEAD` = 0.5) so the knob always hides the fill's edge
  (without it the fill fell up to 5 px behind the knob on windows about 920 px wide).
- **EQ faders:** per fader an invisible full-width click slider (`eqclick`), a dB-label slider and a groove slider (21 frames: every 2nd dB, the knob hides
  the gap); knob travel is computed in device pixels (`eq_travel()`); 0 dB ticks are part of `eq_bands`.
- **Icons:** `icon()` draws in `Canvas.crisp` mode (a pixel is set when its centre is inside the shape) and snaps the glyph centre to half device pixels.
- **Section corners:** only the outer corners of the stack are round; bar / EQ backgrounds exist in rounded and square variants that switch with the EQ / playlist state
  (`cap_tag`); the lower section of a join keeps the single line.

## Closed items
| # | Item | Result |
|---|---|---|
| H1 | Helper vs new names | Naming rule above; helper constants for the 676 px window fixed; packages built; Windows side unverified (H3) |
| H2 | 24 px strip audit | Decided 24 px; audited at 100 / 125 / 150 / 200 %; fixed a missing bottom outline (shared slice middles); default width 620 |
| H4 / H5 | Style decision | Thin only (TG: generator, TS: scripts / helper / packages / docs); the standard-style audit was cancelled |
| H6 | Video window | `video-l` only (the skin has no `video-min` or fullscreen controller): 12 px frame, 1 px outline, resize tab in the corner; real video untested |
| H7 | Other themes | Carbon, Sand, Sage accents adjusted (dim label >= 3:1); contact sheets in `docs/img-audit/h7/` |
| H8 | Playlist states | Report `docs/pl-states-report.md` |
| H9 | Control states | Hover / pressed rects and hit boxes exact at 100 %; fixed flip-arrow centring, chip state rules, mode-button pressed colour, scroll knob end |
| H10 / H23 | Memory | Thin was +34 MB per theme over the original skin at 100 % (121.4 vs 87.2 MB), now +16 (103.6; at 150 %: 181.5 -> 141.0 vs 102.0); EQ sheets cropped / split, pixel-identical |
| H11 | Docs and tooling | README, `doc-shots.sh`, architecture notes, `tools/README.md`; `windows-sim.py` marked legacy |
| H13 | Font | Keep DejaVu; JetBrains Mono equal; Share Tech Mono breaks the format chip, Roboto Mono clips descenders (`docs/font-notes.md`) |
| H14 | Progress bar options | Current look kept; underline prototype behind a switch (`docs/architecture.md`, "Progress bar options") |
| H15 / H16 | Upstream drafts | 8 drafts written (filing is H34); no real codec label without upstream |
| H17 / H19 | Resize tab | One placement rule; own control; the reported dead lower half did not reproduce (hidden controls do not take hits) |
| H18 | Window corner rim | Rejected (no better on dark desktops, may break the outline) |
| H20 | Playlist details | Gutters 6 px both sides, stripes medium; proportional thumb impossible |
| H21 | Knob overhang | Seek kept; volume and EQ knobs inside the groove (EQ travel in device px) |
| H22 | Icon halo | Crisp rendering: 341 asymmetric icon renders -> 0 (468 renders checked) |
| H24 | Paper adjustment | Applied (see Decisions) |
| H25 | Package image path | Packages read `docs/img-thin`; `docs/img-hifi` removed |
| H26 | Hit-test sweep | No reproducible failures at 125 / 150 / 200 % (24 px) and 100 / 150 % (40 px); coverage gaps are H30 |
| H27 | Pipes progress idea | Mockups made (`A` lit only, `B` lit + faint, `C` wide, `D` short); current look kept |
| - | Review fixes (Jiri) | EQ click zone widened again (invisible slider), EQ labels no longer cut at the top, empty band beside the title fill removed (inset + no inner shadow), title fill lighter on dark themes (contrast 1.36 -> 1.83), frame 0 lit (dark band at the start of each track), seek fill lead (fill fell behind the knob on wide windows), separator line under the seek bar removed |

## Parked: online configurator (H12)
Jiri, 2026-11-01: stop working on the configurator for now. State when parked: `configurator/build_skin.py` equals the generator of commit 322d8de
(byte-identical, verified by `tools/sync-configurator.py`: 8 cases identical, a page-style build under Pyodide identical once). It goes stale with every later
generator change: do not re-sync or touch `configurator/` until Jiri reopens it. When reopened: run `tools/sync-configurator.py`, then check the page in a real
browser (never done), memory and run time under Pyodide at 150 / 200 % (not measured), custom fonts through the page (not tested).
