# Playlist panel states, thin skin (H8)

Build: `source/build_skin.py --bar-height 40 --width 620` -> `Titlebar-bar40-100.vlt`
(harness: Xvfb `:99`, `TB_INSTANCE=hifi-h8`, real VLC 3.0.20, 100 %, window 620x676).
Measurements are on the 1x window shots (pixel = skin pixel). Crops: `docs/img-audit/h8/`
(`raw-<state>.png` = 1x window, `<state>-list-2x.png`, `<state>-left-8x.png`, `<state>-right-8x.png`).

States: `empty` (VLC started with no media), `n7` (7 items), `n7sel` (row 3 selected),
`t45top` / `t45mid` (wheel offset 9 of 32, first visible Track 10) / `t45end` (offset 32, Track 34-45).

## Geometry (x, y in window pixels)

| Element | Measured | Note |
|---|---|---|
| List box | x 12..607, y 73..276 (outer) | 596 x 204; no visible outline (outline colour within 2 levels of fill) |
| Row pitch / height | 15 px; row k top = 78 + 15(k-1) | 13 rows fit (78..272) |
| Stripes | even rows (2,4,...), 15 px tall, x 18..577 | left inset 6 px from box edge (x 12); 5 px of fill |
| Stripe end to track | last stripe px 577, track px 592 | 14 px of fill between (15 by coordinate difference). Backlog said 16: measured 14 |
| Scroll track | x 592..599 (8 px), y 78..271 (194 px) | rounded ends; right inset 8 px from box edge x 607 (7 px fill) |
| Track top / bottom in box | 5 px (73..77) / 5 px (272..276) | symmetric |
| Last row vs track | row 13 ends at y 272, track at 271 | track 1 px shorter than the row grid |
| Stripe vs track (horizontal) | left 6 px from box edge, right 8 px | **2 px asymmetry** in the side gutters |
| Selected row | x 18..577, y 108..122 (row 3) | identical to stripe geometry (aligned) |
| Text ink | x 25 (G, L, T, N) or 26 (H, P, S); top 2 px, bottom 3 px in the row | 7-8 px from stripe start, 13-14 px from box edge; vertically 0.5 px high |

## Scroll thumb

| State | Thumb y | Gap top (thumb - track top 78) | Gap bottom (track bottom 271 - thumb bottom) |
|---|---|---|---|
| empty | 78..101 | 0 | 170 |
| n7 (no overflow) | 78..101 | 0 | 170 |
| t45top (offset 0) | 78..101 | 0 | 170 |
| t45mid (offset 9/32) | 124..147 | 46 | 124 |
| t45end (offset 32/32) | 247..270 | 169 | **1** |

- Thumb is 8 x 24 px and fixed in size. A proportional thumb for 45 items in 13 visible rows would be about 56 px (13/45 x 194).
- Thumb travel is 169 px; free track is 170 px. At the bottom the thumb stops 1 px short of the track end, at the top it is flush.
- With 7 items (nothing to scroll) the thumb is still 24 px at the top, so the list looks scrollable.
- The empty list shows the same thumb and track; its only row is the VLC root label `Playlist`.

## Colours (WCAG contrast ratio)

| Pair | Colours | Ratio |
|---|---|---|
| Stripe vs box | (10,21,23) vs (7,15,16) | 1.04:1 |
| Scroll track vs box | (10,23,26) vs (7,15,16) | 1.06:1 |
| Selected row vs box | (21,46,51) vs (7,15,16) | 1.36:1 |
| Selected row vs stripe | (21,46,51) vs (10,21,23) | 1.30:1 |
| Box vs panel | (7,15,16) vs (34,41,50) | 1.32:1 |
| Thumb face vs track | (166,175,186) vs (10,23,26) | 8.2:1 |
| Cyan text vs stripe / box / selected | (102,212,232) | 10.7 / 11.2 / 8.3:1 |
| Current item text vs selected | (254,254,254) on (21,46,51) | 14.2:1 |

Stripes and selection are subtle by design. The selected row is only 1.3-1.4:1 against its neighbours; the text stays readable (8.3:1).

## Findings, in priority order

1. **Thumb does not show content size.** Fixed 24 px thumb on 7 and 45 items alike; no overflow still shows a thumb. Fix: proportional thumb (min 24 px) or hide it when the list fits.
2. **Side gutters are asymmetric.** Stripes sit 6 px from the box edge on the left, the track sits 8 px from it on the right. Pick one rule (e.g. 6 px both sides) and move track or stripes.
3. **Stripe to track gap is 14 px**, not the 16 px in the backlog. Decide the value and state it in the rule.
4. **Thumb reaches the top but stops 1 px short at the bottom**, and the track ends 1 px above the last row grid line. Make the track travel match the row grid.
5. **Selection contrast 1.36:1** against the box. Stronger tint would help, but the text is still 8.3:1.

Not checked: 125 / 150 / 200 %, light themes, mouse-drag of the thumb, keyboard selection, and the 40 px strip in its other positions.

## Method

Pillow pixel scans of the 1x shots (run lengths along rows and columns; colour samples; WCAG luminance ratios). Grids of the track corners were read as ASCII maps. Scroll with the wheel at (300,150) window-relative; offsets inferred from the first visible title.
