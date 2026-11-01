"""Contrast table of every theme: text / label / outline / LED.

Usage: ~/.cache/titlebar-test/venv/bin/python tools/theme-audit.py
"""
import sys
sys.argv=['x']
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source'))
import build_skin as b
names=[t[1] for t in b.THEME_SEEDS if t[1]!='Custom']
print('%-9s %5s %5s %5s %5s %5s | %5s %5s %5s' % ('theme','txt','cyan2','dim','label','icon','edge','boxed','fill'))
for n in names:
    b.set_themes([n.lower()]); b.apply_theme(0)
    g=b
    def c(a,bg): return b.contrast(a,bg)
    ledoff=b.LED_OFF
    row=(n, c(b.CYAN_TXT,b.LCD_BG), c(b.CYAN2,b.LCD_BG), c(b.CYAN_DIM,b.LCD_BG), c(b.LABEL,b.mix(b.BG_TOP,b.BG_BOT,.5)), c(b.ICON["up"],b.BTN["up"][1]),
         c(b.EDGE,b.mix(b.BG_TOP,b.BG_BOT,.5)), c(b.box_edge(0.13),b.LCD_BG), c(b.TITLE_FILL,b.LCD_BG))
    print('%-9s %5.2f %5.2f %5.2f %5.2f %5.2f | %5.2f %5.2f %5.2f' % row, ' ledoff/btn %.2f' % c(ledoff,b.BTN["up"][1]))
