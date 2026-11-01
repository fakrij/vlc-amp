"""Mirror-diff every icon (H22): LR / UD alpha difference per icon, bar height and scale. Usage: python tools/icon-symmetry.py <source dir> <out.json>  (needs numpy)"""
import sys, os, json
src=sys.argv[1]; out=sys.argv[2]
sys.argv=['x']
sys.path.insert(0, src)
import build_skin as b
from PIL import Image, ImageChops
import numpy as np
AX={'expand':'LU','collapse':'LU','prev':'U','next':'U','play':'U','pause':'LU','stop':'LU','pin':'L','minimize':'L','close':'LU','menu':'LU','arrow_up':'L','arrow_down':'L','sun':'LU','moon':'U','speaker':'U','slower':'','faster':''}
calls={}
orig=b.icon
def rec(c,name,ox,oy,size,color):
    calls[(name,c.w,c.h,c.ox,c.oy,ox,oy,size)]=1
    return orig(c,name,ox,oy,size,color)
b.icon=rec
res=[]
# make sure sun/moon etc. get drawn too
for bh in (24,36,40):
  for sc in (1.0,1.25,1.5,2.0):
    calls.clear(); b.S=sc
    b.set_themes(['midnight']); b.apply_theme(0)
    skin=b.Skin(); b.build(skin,620,bh)
    for name in AX:
        calls[(name,16,16,0,0,2,2,12)]=1   # synthetic centred placement
    for (name,w,h,cox,coy,ox,oy,size) in sorted(calls):
        c=b.Canvas(w,h); c.ox,c.oy=cox,coy
        orig(c,name,ox,oy,size,'#ffffff')
        a=np.array(c.done().getchannel('A')).astype(int)
        ys,xs=np.where(a>0)
        if not len(xs): continue
        g=a[ys.min():ys.max()+1, xs.min():xs.max()+1]
        row=dict(bh=bh,sc=sc,name=name,w=w,h=h,size=size,ox=ox,oy=oy,bw=g.shape[1],bh_=g.shape[0])
        row['LR']=int(np.abs(g-g[:,::-1]).sum()) if 'L' in AX[name] else None
        row['UD']=int(np.abs(g-g[::-1,:]).sum()) if 'U' in AX[name] else None
        # centring offset in device px (bbox centre vs canvas centre), weighted by alpha
        ww=a.sum(); cx=(a.sum(0)*np.arange(a.shape[1])).sum()/ww+.5; cy=(a.sum(1)*np.arange(a.shape[0])).sum()/ww+.5
        row['cx']=round(cx-a.shape[1]/2,2); row['cy']=round(cy-a.shape[0]/2,2); row['ink']=int(ww)
        res.append(row)
json.dump(res,open(out,'w'))
bad=[r for r in res if (r['LR'] or 0)>0 or (r['UD'] or 0)>0]
print(len(res),'icon renders;',len(bad),'asymmetric')
from collections import Counter
print(Counter((r['name']) for r in bad))
