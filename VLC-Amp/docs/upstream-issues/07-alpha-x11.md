# skins2: per-pixel alpha blending of skin bitmaps on the X11 backend

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 on X11 (Windows has its own backend).
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

Soft shadows and glow around a skin's panels need semi-transparent PNG pixels drawn over the desktop
(or over the skin's own layers). On X11 the skin can only show fully opaque pixels or cut-outs.
The skin author works around this by baking the shadow onto an opaque background, which does not
follow the desktop.

## Current behaviour and evidence

- `modules/gui/skins2/x11/x11_graphics.cpp` (`3.0.x`), `drawGraphics()`: copies the source with
  `XCopyArea` and a clip region built from the source mask. No alpha compositing.
- `drawBitmap(..., bool blend)`: when `blend` is true it calls the blend pixel function, which computes
  `out = src + floor(dst * (255 - a) / 255)` per channel (`x11_display.cpp`, `blendPixel<type>`).
  This is additive and does not scale the source by alpha, so it is not standard "over" compositing.
  The default is `blend = false` (`x11_graphics.hpp`). In the fetched files no caller passes
  `blend = true`.
- The window mask is binary: `drawBitmap` adds any pixel with `a > 0` to the mask, and the window
  shape is applied with `XShapeCombineRegion(ShapeBounding)` (`x11_graphics.cpp`). A semi-transparent
  pixel therefore becomes fully visible in the window shape.
- No XRender, no ARGB visual, no per-pixel window alpha in the X11 backend.
- Window-level opacity exists: `x11_window.cpp`, `setOpacity()` sets `_NET_WM_WINDOW_OPACITY`
  (deleted at 255). It affects the whole window, not single pixels, and only if the window manager
  or compositor honours it. The skin theme's `alpha` attribute is passed to `setAlphaValue()`
  (`builder.cpp`, `window_manager.cpp`).
- Our own generator comments say the same (`source/build_skin.py`, around lines 393 and 909: "VLC
  cuts windows on alpha, keep it binary"; "without alpha blending"). That is our reading, not a
  test result.

**Unverified:** what a semi-transparent pixel looks like on screen in practice with the current
X11 code (the old note "semi-transparent = black" was not re-tested in this review). A screenshot
test with a 50 % pixel over a coloured desktop is needed before filing.

## Proposed API

- Use an ARGB visual and XRender (`XRenderComposite` with `PictOpOver`) for `drawBitmap` when the
  bitmap has alpha and the window has an ARGB visual, falling back to the current path otherwise.
- Keep the shape mask, or switch to a compositing window when a compositor is running.
- Theme attribute to opt in, for example `<Theme alpha-blend="true">`, so old skins do not change.

## Example theme XML (proposed)

```xml
<Theme version="1.0" alpha-blend="true">
  <Image id="shadow" image="shadow_panel" x="0" y="0" width="620" height="240" />
</Theme>
```

## Acceptance criteria

1. A bitmap with a 50 % alpha edge over a coloured desktop shows the desktop blended, on a
   compositing and a non-compositing X server (Xvfb with and without a compositor).
2. Skins without `alpha-blend` render byte-identical to today (pixel compare).
3. No change in window hit testing for opaque pixels; transparent pixels stay outside the shape.
4. Measured CPU cost of a 620 x 240 blended draw recorded.
