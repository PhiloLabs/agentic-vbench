#!/usr/bin/env python3
"""Fingerprint a Minecraft screen from its pixels: locate the button-like slabs.
Blind navigation needs a state signal, and the count/geometry of buttons identifies the screen."""
import sys
import numpy as np
from PIL import Image
a=np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(int)
h,w,_=a.shape; g=a.mean(axis=2)
btn=((g>85)&(g<185)).astype(int)
rows=np.where(btn.sum(axis=1) > w*0.08)[0]
bands=[]
if len(rows):
    s=prev=rows[0]
    for r in rows[1:]:
        if r-prev>4: bands.append((s,prev)); s=r
        prev=r
    bands.append((s,prev))
out=[]
for y0,y1 in bands:
    if y1-y0<8: continue
    col=btn[y0:y1+1].sum(axis=0) > (y1-y0)*0.55
    idx=np.where(col)[0]
    if len(idx)<60: continue
    out.append(((idx.min()+idx.max())//2, (y0+y1)//2, idx.max()-idx.min()+1, y1-y0+1))
print(f"brightness={a.mean():.1f} buttons={len(out)}")
for cx,cy,bw,bh in out: print(f"  centre=({cx},{cy}) size={bw}x{bh}")
