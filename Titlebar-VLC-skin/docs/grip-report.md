# H17: right-edge resize grip (report only)

Build: `source/build_skin.py --width 620` (thin and standard, `--bar-height 40` and `24`), real VLC 3.0.20 under Xvfb
(`TB_DISPLAY_NUM=104`, `TB_INSTANCE=hifi-h17`). Pixel scans with Pillow on scale-1 screenshots. Crops (8x NEAREST):
`docs/img-audit/h17/` (`thin40-strip-tab.png`, `thin40-eq-tab-top.png`, `thin40-eq-tab.png`, `thin40-pl-tab.png`,
`thin24-strip-tab.png`, `std40-strip-tab.png`, `std40-eq-tab-top.png`, `std40-pl-tab.png`).

## Measured (window coordinates, thin 40 px bar)

| Section | Tab x | Tab y | Ribs x | Gap top / bottom | Centre vs section |
|---|---|---|---|---|---|
| Strip (0-39) | 610-618 (9 px) | 3-36 | 612, 614, 616 (rows 6-33) | 3 / 3 | centred (19.5) |
| EQ (40-203) | 610-618 | 100-169 (70 px) | same | - | tab 134.5 vs section 121.5 (+13); body below title bar 96 (within 1 px) |
| PL (204-483, EQ open) | 610-618 | 284-353 (70 px) | same | - | tab 318.5 vs section 343.5 (-25); body below title 358 |

- Thin 24 px strip: tab 610-618, rows 3-20 (18 px), ribs 612/614/616 rows 6-17. Centred.
- Standard 40 px strip: identical x, y, rib positions and colours (tab 394555, ribs 8b95a2). Strip background is a gradient; the tab is not.
- Colours: tab and rib colours are the code's `BTN["up"]` and `mix(BTN["up"], ICON["up"], 0.6)`. Not sampled against a button fill on screen (unverified).
- Margin: the 12 px right margin is x 608-619. The tab lies entirely inside it: 2 px gap on the left (608-609), 1 px to the window edge (619).

## Drag behaviour (thin 40, `tools/vlc-test.sh drag`)

- Strip tab, drag +30 at W-6: window grows by 30. Works. Also works at 24 px (620 -> 650).
- One px outside (x = W-11, left of the tab): the window moves, width unchanged. Correct.
- EQ tab: drag +30 grows the window.
- **PL tab: problem.** A zone scan (probe every 2 px at x = W-6, EQ open) gives:
  resize for y 54-306, move for y 310-318, no action for y 322 onward. So the lower half of the drawn PL tab
  (307-353) does not resize; it moves the window or does nothing. The lower limit 307 matches the bottom of a
  hidden duplicate PL section (near copy, y 40-319), so the hit-test appears to come from a copy that is not
  visible while the EQ is open. The PL-only layout gives the same resize band (54-306), which is the hidden
  copy's `mr` slice. Cause is inferred from the coordinates, not from the code paths.

## Inconsistencies

1. Vertical centre differs per section: strip centred on its band; EQ tab centred on the body below its title bar;
   PL tab 25 px above the centre of its body. Full bar: not measured.
2. The PL grip's hit area is not the drawn tab (see above). Strip and EQ hit areas match.
3. The tab sits in the 12 px margin, not on a box edge, so there is no content edge to align the ribs to.

## Proposed single rule

- x: the 9 px tab centred in the 12 px right margin, i.e. starting at `W - 12 + (12 - 9) // 2 = W - 11`
  (current is W-10: 1 px right of centre; left gap 2, right gap 1 becomes 1 / 2). Or keep W-10 and state the rule as
  "1 px from the window edge". Choose one and apply to all sections.
- y: centred on the section's body (below its title bar), same offset rule for strip and panels.
- Ribs: 3 ribs at tab x + 2, +4, +6, height tab - 6 (current; consistent across sections).
- Hit area: exactly the drawn tab. Make the grip its own control per section so it does not depend on the
  `mr` slice of hidden duplicate layouts.

## Unverified

- Full player bar (`--bar-height` 40 full layout, FH 232): not scanned, not dragged.
- Standard EQ and PL sections: crops made, numbers not scanned.
- Thin 24 px EQ/PL: not run.
- Whether the PL hit-test gap is caused by the hidden duplicate: inferred from coordinates only.
- Hit areas for 125 / 150 / 200 %: not tested.
