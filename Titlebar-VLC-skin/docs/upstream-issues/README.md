# Upstream issue drafts (VLC skins2)

One draft per request from [docs/vlc-feature-requests.md](../vlc-feature-requests.md). Drafts only:
nothing here is filed yet. Jiri files them (BACKLOG-hifi.md, H34).

| # | Draft | Request | Verification |
|---|---|---|---|
| 01 | [relative seek](01-relative-seek.md) | seek by +/- N s from a button | source (skins2 commands, vlcproc); full command grep unverified |
| 02 | [balance](02-balance.md) | balance variable and slider | source; core balance option name unverified |
| 03 | [EQ band values as text](03-eq-band-values-text.md) | dB readout per band | source (equalizer.cpp, var_text.cpp); parser path unverified |
| 04 | [tag and codec variables](04-tag-codec-variables.md) | artist, album, genre, year, codec, channels | source (var_text.cpp, vlcproc.cpp, strings.c); es_format unverified |
| 05 | [Playtree columns](05-playtree-columns.md) | number, title, duration, artist columns | source (ctrl_tree.cpp, skin_parser.cpp) |
| 06 | [dock / edge-snap](06-dock-edge-snap.md) | dock actions; partial prior art: Theme `magnet` | source; magnet on X11 unverified |
| 07 | [alpha on X11](07-alpha-x11.md) | per-pixel alpha in the X11 backend | source; visual result unverified (needs a screenshot test) |
| 08 | [Playtree row bitmaps](08-playtree-row-bitmaps.md) | per-row background / state images | source (ctrl_tree.cpp) |

Not drafted, on purpose: the marquee row (no request needed, done with fixed chips) and the rows
marked done in the feature-request table.

## Source used

- VLC 3.0.x branch, `modules/gui/skins2/` (fetched from `raw.githubusercontent.com/videolan/vlc/3.0.x`,
  2026-11-01). Files: `src/vlcproc.cpp`, `src/top_window.cpp`, `src/window_manager.cpp`,
  `src/generic_window.cpp`, `src/vlcproc.cpp`, `utils/var_text.cpp`, `vars/equalizer.cpp`,
  `controls/ctrl_tree.cpp`, `commands/cmd_input.cpp`, `commands/cmd_audio.cpp`, `x11/x11_graphics.cpp`,
  `x11/x11_graphics.hpp`, `x11/x11_window.cpp`, `x11/x11_display.cpp`, `parser/skin_parser.cpp`,
  `parser/builder.cpp`. Also `src/text/strings.c`.
- The fetch tool returned summaries, not raw files; line numbers were not always available. Before
  filing, check each cited function in the tagged source.
- Lua facts: [docs/lua-api-notes.md](../lua-api-notes.md) (T5, 3.0.x).

## How to file

1. Check the current contribution page and the issue tracker rules before filing. Notes from the
   wiki page "Report a bug" (fetched 2026-11-01): feature requests go to the VLC GitLab; search the
   open and closed issues first and check the `enhancement`-labelled list; one request per issue; give the
   VLC version, OS, and the steps. The GitLab page itself could not be read (access check page).
2. Project: `videolan/vlc` on code.videolan.org, issues at
   https://code.videolan.org/videolan/vlc/-/issues (account needed).
3. Label: `skins2` if the label exists on the project. **Unverified:** the labels page returned an access
   check, so the label was not confirmed. If it does not exist, use the component / `enhancement` label
   the maintainers use, and say "skins2" in the title.
4. Title: copy the first heading of the draft. Body: the sections of the draft in order; attach the
   example theme XML as a text block.
5. Put the link to the filed issue into the matching row of the table in
   [docs/vlc-feature-requests.md](../vlc-feature-requests.md) and into BACKLOG-hifi.md H34.
6. Test a nightly build before filing items 06 and 07 (behaviour may have changed on newer code).
