"""Scan every bitmap for semi-transparent pixels (X11 turns them black): 4 scales, 4 themes.

Usage: ~/.cache/titlebar-test/venv/bin/python tools/bitmap-audit.py
"""
import sys, re
sys.argv=['x']
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source'))
import build_skin as b
OK=re.compile(r'(_fill|eq_bands|flag_px|thumb_none|^vol\d|^seek$|eqfill)')
tot=0
for scale in (1.0, 1.25, 1.5, 2.0):
  for th in ('midnight','paper','sand','nord'):
      b.set_themes([th]); b.apply_theme(0); b.S=scale
      skin=b.Skin(); b.build(skin,620,int(os.environ.get("BH","40")))
      bad=[]
      for bid,im in skin.bitmaps.items():
          name=re.sub(r't\d+_','',bid)
          a=im.convert('RGBA').getchannel('A'); h=a.histogram()
          semi=sum(h[1:255])
          if semi and not OK.search(name): bad.append((name,semi))
      tot+=len(bad)
      if bad: print(scale, th, bad[:6])
print('bitmaps with semi-transparent pixels (excluding fill frames):', tot)
