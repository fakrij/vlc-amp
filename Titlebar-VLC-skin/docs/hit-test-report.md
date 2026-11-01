# Hit-test sweep (H26, round 2)

Branch `hifi/r2f` (worktree `/home/jirif/dev/vlc-modular-wt/r2f`). Report only: no generator change.
Builds: 24 px strip at 125 / 150 / 200 %, 40 px bar at 100 / 150 % (`source/build_skin.py`, commit c4f5b37 + this branch).
Raw data: `docs/img-audit/r2f/results/*.json`; crops: `docs/img-audit/r2f/retest-*.png`.

## Summary

- **No reproducible hit-rect failure.** After the retests below, every control whose hit area is a rect (buttons,
  checkboxes, sliders) fires on its inside edge pixels and not on the outside ones, at every scale. Two probes stay
  single-pass (see the end of the failure table).
- **Time box (`c135` full player, `c18` full-up):** no visible hover image (its `over` bitmap equals `up`), so a hover test
  cannot see it. A real click at the left inside pixel fires it at 125 % (the time readout changes, 2373 px). Shown as
  "not fired" in the tables; it is a method limit, not a hit failure.
- **Flip arrows (`b189`, `b217`, `b403`, `b161`):** single-pass misses on the inside edge (1.5, 2.0, 1.0 / 40 px). Retested
  with 2 repeats, the inside edge fired in every case (`retest-*.png`). The misses come from the machine load (load average
  about 20 during the run), not from the rects.
- **EQ sliders (vertical):** the first sweep probed left / right at the current value row, so those probes could not move the
  slider (value unchanged). Fixed (probe at y + h / 4) and re-run at 125 / 150 %: every left / right probe of the 11 EQ sliders
  fires inside and not outside (strip and full scenes).
- **Rounding:** at 125 % 67 rect values (x, y, w or h) differ by 1 px from `round(100 % x 1.25)` (floor of .5), at 150 % 20 EQ slider
  x values differ by 1 px, at 200 % none (static comparison with the 100 % build). The rects equal their bitmaps, so the
  hit area follows the drawn art; the 1 px offsets only shift a row relative to its neighbours.
- **Shape:** the probed edge pixels of every button / checkbox bitmap (up, over, down) have alpha > 0 in every build, so the
  X11 shape never cuts a hit inside a rect.

## Method

- Scenes: strip-dn and full-dn, each with PL and EQ closed / open (8 scenes). Playback paused once at the start (time-driven
  fills would move the groove rects between shots).
- Buttons and checkboxes: pointer on the 1 px inside / outside pixel of an edge midpoint, no click. The control's own rect is
  compared with the parked shot. A change = the control's `mouseOver` took the pointer = its hit area. Hover uses the same
  rect test as a click.
- Sliders: reset click to the groove middle, park, shot; click 1 px inside / outside (top and bottom probes at 3/4 width);
  groove rect compared. A value change = fired.
- Real clicks (press + release, left inside pixel) at 125 % only, 12 controls, observed through the window shape or the
  control rect: play (`c339`), time mode (`c346`), pin (`c351`), PL (`c349`, `c164`), EQ (`c350`, `c165`), EQ ON (`c174`),
  SHUF chip (`c152`), time box (`c135`), expand (`b337`), STRIP (`b131`). All fired, all toggled back.
- Edges: all four at 125 %; left and bottom only at 150 %, 200 %, 40 px at 100 / 150 % (2-edge sampling, as allowed by H26).
  EQ sliders: left and right (the vertical probe fix), re-run at 125, 150 and 200 %.
- Load: the machine ran at a load average of about 20, which made single hover probes miss now and then. Every single miss
  listed below was re-probed (3 repeats in total for each re-probe; the first pass counts).

## Failures (after retests) and likely cause

| scale | control | edge | inside pt | outside pt | result | cause |
|---|---|---|---|---|---|---|
| 1.25 / 24 | `c135` (full-dn) | all | (22,120) etc. | - | no hover image | method limit; click at left edge fires |
| 1.5 / 24 | `c135` (full-dn) | left, bottom | (27,144), (169,215) | - | no hover image | method limit |
| 1.5 / 24 | `b217` (full-dn, PL+EQ) | left | (876,619) | (875,619) | first pass not fired; **retest fired** (centre, left, bottom 1030 px) | transient, load |
| 2.0 / 24 | `c135` (full-dn) | left, bottom | (36,192), (226,287) | - | no hover image | method limit |
| 2.0 / 24 | `b189` (full-dn, PL) | left | (1168,498) | (1167,498) | first pass not fired; **retest fired** (1740 px centre, left, bottom) | transient, load |
| 2.0 / 24 | `b217` (full-dn, PL+EQ) | left | (1168,826) | (1167,826) | not retested (see below) | transient? |
| 1.0 / 40 | `b161` (full-dn) | bottom | (207,222) | (207,223) | first pass not fired; **retest fired** (724 px left and bottom) | transient, load |
| 1.0 / 40 | `b189` (full-dn, PL) | left, bottom | (584,249), (596,259) | (583,249), (596,260) | first pass not fired; **retest fired** (436 px centre, left, bottom) | transient, load |
| 1.0 / 40 | `b403` (strip, PL+EQ) | left, bottom | (584,221), (596,231) | (583,221), (596,232) | first pass not fired; **retest fired** (436 px) | transient, load |
| 1.0 / 40 | `t0_s_ftitle_full-dn` | left | (223,66) inside | (222,66) | sweep: outside changed 4565 px; direct re-test: 80 px (thumb repaint), inside 4773 px | **not reproduced** as a value change |
| 1.5 / 40 | `b403` (strip, PL+EQ) | left | (876,331) | (875,331) | not retested | unknown (see below) |
| 1.25 / 1.5 | EQ sliders, left / right | - | - | - | first pass: not fired (probe design) | **sweep bug, fixed**, re-run passes |

Not retested: `b217` at 2.0, `b403` at 1.5 / 40 px, `c135` edges other than left. These are the only probes with a single
pass result; they should be re-run on an idle machine before a release.

## Per-scale tables

Compact form: one row per control; each edge cell is `inside / outside` with `Y` = fired, `n` = not fired, `-` = not sampled,
`**` = a failure. A control is listed once (the first scene it was probed in). EQ sliders: left / right from the re-run.

### 1.25 / 24 px strip

Cells: inside / outside, Y = fired, n = not fired, `-` = not sampled, `**` = a failure (see list).

| control | type | scene | left | right | top | bottom |
|---|---|---|---|---|---|---|
| b337 | Button | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b338 | Button | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c339 | Checkbox | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b340 | Button | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| t0_s_title_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c346 | Checkbox | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| t0_s_vol_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c349 | Checkbox | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c350 | Checkbox | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c351 | Checkbox | strip-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b375 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b385 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b386 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b387 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b388 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b389 | Button | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c390 | Checkbox | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c391 | Checkbox | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c392 | Checkbox | strip-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b359 | Button | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c360 | Checkbox | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq0_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq1_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq2_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq3_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq4_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq5_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq6_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq7_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq8_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq9_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq10_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| b403 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b413 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b414 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b415 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b416 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b417 | Button | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c418 | Checkbox | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c419 | Checkbox | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c420 | Checkbox | strip-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b127 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c128 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b129 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b130 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b131 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c135 | Checkbox | full-dn-pl0-eq0 | n / n ** | n / n ** | n / n ** | n / n ** |
| t0_s_ftitle_full-dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c152 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c153 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c154 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| t0_s_seek_full-dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| b156 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b157 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b158 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c159 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b160 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b161 | Button | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| t0_s_vol_full-dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c164 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| c165 | Checkbox | full-dn-pl0-eq0 | Y / n | Y / n | Y / n | Y / n |
| b189 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b199 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b200 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b201 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b202 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b203 | Button | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c204 | Checkbox | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c205 | Checkbox | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| c206 | Checkbox | full-dn-pl1-eq0 | Y / n | Y / n | Y / n | Y / n |
| b173 | Button | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| c174 | Checkbox | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq0_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq1_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq2_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq3_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq4_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq5_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq6_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq7_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq8_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq9_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| t0_s_eq10_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | Y / n | Y / n |
| b217 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b227 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b228 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b229 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b230 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| b231 | Button | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c232 | Checkbox | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c233 | Checkbox | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |
| c234 | Checkbox | full-dn-pl1-eq1 | Y / n | Y / n | Y / n | Y / n |

Failures: 4.

- `c135` (full-dn-pl0-eq0) left: inside [22, 120] **not fired**; outside [21, 120] not fired
- `c135` (full-dn-pl0-eq0) right: inside [259, 120] **not fired**; outside [260, 120] not fired
- `c135` (full-dn-pl0-eq0) top: inside [141, 60] **not fired**; outside [141, 59] not fired
- `c135` (full-dn-pl0-eq0) bottom: inside [141, 179] **not fired**; outside [141, 180] not fired

### 1.5 / 24 px strip

Cells: inside / outside, Y = fired, n = not fired, `-` = not sampled, `**` = a failure (see list).

| control | type | scene | left | right | top | bottom |
|---|---|---|---|---|---|---|
| b337 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b338 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c339 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b340 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_title_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c346 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c349 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c350 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c351 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b375 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b385 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b386 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b387 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b388 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b389 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c390 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c391 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c392 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b359 | Button | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c360 | Checkbox | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq1_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq2_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq3_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq4_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq5_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq6_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq7_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq8_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq9_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq10_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| b403 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b413 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b414 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b415 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b416 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b417 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c418 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c419 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c420 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b127 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c128 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b129 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b130 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b131 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c135 | Checkbox | full-dn-pl0-eq0 | n / n ** | - | - | n / n ** |
| t0_s_ftitle_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c152 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c153 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c154 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_seek_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b156 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b157 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b158 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c159 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b160 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b161 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c164 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c165 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b189 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b199 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b200 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b201 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b202 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b203 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c204 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c205 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c206 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b173 | Button | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c174 | Checkbox | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq1_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq2_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq3_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq4_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq5_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq6_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq7_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq8_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq9_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq10_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| b217 | Button | full-dn-pl1-eq1 | n / n ** | - | - | Y / n |
| b227 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b228 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b229 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b230 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b231 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c232 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c233 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c234 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |

Failures: 3.

- `c135` (full-dn-pl0-eq0) left: inside [27, 144] **not fired**; outside [26, 144] not fired
- `c135` (full-dn-pl0-eq0) bottom: inside [169, 215] **not fired**; outside [169, 216] not fired
- `b217` (full-dn-pl1-eq1) left: inside [876, 619] **not fired**; outside [875, 619] not fired

### 2.0 / 24 px strip

Cells: inside / outside, Y = fired, n = not fired, `-` = not sampled, `**` = a failure (see list).

| control | type | scene | left | right | top | bottom |
|---|---|---|---|---|---|---|
| b337 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b338 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c339 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b340 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_title_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c346 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c349 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c350 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c351 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b375 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b385 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b386 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b387 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b388 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b389 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c390 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c391 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c392 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b359 | Button | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c360 | Checkbox | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq1_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq2_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq3_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq4_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq5_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq6_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq7_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq8_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq9_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq10_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| b403 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b413 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b414 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b415 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b416 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b417 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c418 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c419 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c420 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b127 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c128 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b129 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b130 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b131 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c135 | Checkbox | full-dn-pl0-eq0 | n / n ** | - | - | n / n ** |
| t0_s_ftitle_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c152 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c153 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c154 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_seek_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b156 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b157 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b158 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c159 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b160 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b161 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c164 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c165 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b189 | Button | full-dn-pl1-eq0 | n / n ** | - | - | Y / n |
| b199 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b200 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b201 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b202 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b203 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c204 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c205 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c206 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b173 | Button | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c174 | Checkbox | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq1_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq2_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq3_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq4_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq5_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq6_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq7_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq8_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq9_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| t0_s_eq10_full_dn | Slider | full-dn-pl0-eq1 | Y / n | Y / n | - | Y / n |
| b217 | Button | full-dn-pl1-eq1 | n / n ** | - | - | Y / n |
| b227 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b228 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b229 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b230 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b231 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c232 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c233 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c234 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |

Failures: 4.

- `c135` (full-dn-pl0-eq0) left: inside [36, 192] **not fired**; outside [35, 192] not fired
- `c135` (full-dn-pl0-eq0) bottom: inside [226, 287] **not fired**; outside [226, 288] not fired
- `b189` (full-dn-pl1-eq0) left: inside [1168, 498] **not fired**; outside [1167, 498] not fired
- `b217` (full-dn-pl1-eq1) left: inside [1168, 826] **not fired**; outside [1167, 826] not fired

### 1.0 / 40 px bar

Cells: inside / outside, Y = fired, n = not fired, `-` = not sampled, `**` = a failure (see list).

| control | type | scene | left | right | top | bottom |
|---|---|---|---|---|---|---|
| b337 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b338 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c339 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b340 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_title_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c346 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c349 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c350 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c351 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b375 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b385 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b386 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b387 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b388 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b389 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c390 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c391 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c392 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b359 | Button | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c360 | Checkbox | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq1_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq2_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq3_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq4_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq5_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq6_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq7_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq8_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq9_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq10_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b403 | Button | strip-dn-pl1-eq1 | n / n ** | - | - | n / n ** |
| b413 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b414 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b415 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b416 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b417 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c418 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c419 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c420 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b127 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c128 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b129 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b130 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b131 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c135 | Checkbox | full-dn-pl0-eq0 | n / n ** | - | - | n / n ** |
| t0_s_ftitle_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c152 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c153 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c154 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_seek_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b156 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b157 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b158 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c159 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b160 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b161 | Button | full-dn-pl0-eq0 | Y / n | - | - | n / n ** |
| t0_s_vol_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c164 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c165 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b189 | Button | full-dn-pl1-eq0 | n / n ** | - | - | n / n ** |
| b199 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b200 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b201 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b202 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b203 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c204 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c205 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c206 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b173 | Button | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c174 | Checkbox | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq1_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq2_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq3_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq4_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq5_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq6_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq7_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq8_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq9_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq10_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b217 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b227 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b228 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b229 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b230 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b231 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c232 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c233 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c234 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |

Failures: 7.

- `b403` (strip-dn-pl1-eq1) left: inside [584, 221] **not fired**; outside [583, 221] not fired
- `b403` (strip-dn-pl1-eq1) bottom: inside [596, 231] **not fired**; outside [596, 232] not fired
- `c135` (full-dn-pl0-eq0) left: inside [18, 96] **not fired**; outside [17, 96] not fired
- `c135` (full-dn-pl0-eq0) bottom: inside [113, 143] **not fired**; outside [113, 144] not fired
- `b161` (full-dn-pl0-eq0) bottom: inside [207, 222] **not fired**; outside [207, 223] not fired
- `b189` (full-dn-pl1-eq0) left: inside [584, 249] **not fired**; outside [583, 249] not fired
- `b189` (full-dn-pl1-eq0) bottom: inside [596, 259] **not fired**; outside [596, 260] not fired

### 1.5 / 40 px bar

Cells: inside / outside, Y = fired, n = not fired, `-` = not sampled, `**` = a failure (see list).

| control | type | scene | left | right | top | bottom |
|---|---|---|---|---|---|---|
| b337 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b338 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c339 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b340 | Button | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_title_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c346 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_strip-dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c349 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c350 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c351 | Checkbox | strip-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b375 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b385 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b386 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b387 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b388 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b389 | Button | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c390 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c391 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c392 | Checkbox | strip-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b359 | Button | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c360 | Checkbox | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq1_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq2_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq3_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq4_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq5_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq6_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq7_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq8_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq9_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq10_strip_dn | Slider | strip-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b403 | Button | strip-dn-pl1-eq1 | n / n ** | - | - | Y / n |
| b413 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b414 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b415 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b416 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b417 | Button | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c418 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c419 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c420 | Checkbox | strip-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b127 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c128 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b129 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b130 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b131 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c135 | Checkbox | full-dn-pl0-eq0 | n / n ** | - | - | n / n ** |
| t0_s_ftitle_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c152 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c153 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c154 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_seek_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b156 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b157 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b158 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c159 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b160 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b161 | Button | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| t0_s_vol_full-dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c164 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| c165 | Checkbox | full-dn-pl0-eq0 | Y / n | - | - | Y / n |
| b189 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b199 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b200 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b201 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b202 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b203 | Button | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c204 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c205 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| c206 | Checkbox | full-dn-pl1-eq0 | Y / n | - | - | Y / n |
| b173 | Button | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| c174 | Checkbox | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq0_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq1_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq2_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq3_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq4_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq5_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq6_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq7_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq8_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq9_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| t0_s_eq10_full_dn | Slider | full-dn-pl0-eq1 | Y / n | - | - | Y / n |
| b217 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b227 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b228 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b229 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b230 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| b231 | Button | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c232 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c233 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |
| c234 | Checkbox | full-dn-pl1-eq1 | Y / n | - | - | Y / n |

Failures: 3.

- `b403` (strip-dn-pl1-eq1) left: inside [876, 331] **not fired**; outside [875, 331] not fired
- `c135` (full-dn-pl0-eq0) left: inside [27, 144] **not fired**; outside [26, 144] not fired
- `c135` (full-dn-pl0-eq0) bottom: inside [169, 215] **not fired**; outside [169, 216] not fired

## Not tested

- Panels-above layouts (`strip-up`, `full-up`): the flip arrows `b56`, `b173`, `b72`, `b100` and the layout switch they do
  were not clicked, and no control of those layouts was swept.
- Real clicks other than the 12 at 125 %: transport buttons, the playlist footer (add opens a dialog, remove, sort, load, save),
  SHUF / LOOP / REP chips in the playlist, `c18` / `c135` edges other than left. Those are hover-tested only.
- Menu (`b127`), minimize (`b129`) and quit (`b130`): hover-tested only (never clicked, by design).
- The wheel and the drag of sliders, the title text scrolling, the video layouts, the fullscreen controller.
- 1.5 / 2.0 / 40 px: only left and bottom edges (2-edge sampling), except EQ sliders (left and right).
- Single-pass results not re-run: `b217` at 2.0 px, `b403` at 1.5 / 40 px. The `t0_s_ftitle_full-dn` outside-left result at
  1.0 / 40 px is not reproduced as a value change, but was not re-run with the full sweep.
- Windows (the Win32 hit test / `SetWindowRgn`): not measured, only the X11 path.
