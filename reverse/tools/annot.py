import os
import re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wl import *
src=open(sys.argv[1]).read()
def is_str(o):
    if o<0 or DSB+o>=len(IMG): return None
    if o>0 and IMG[DSB+o-1]!=0: return None
    e=IMG.find(b'\0',DSB+o)
    s=IMG[DSB+o:e]
    if 3<=len(s)<80 and all(32<=c<127 for c in s): return s.decode()
    return None
def rep(m):
    v=int(m.group(1),16)
    s=is_str(v)
    if s: return m.group(0)+'/*"%s"*/'%s.replace('*/','*_/')
    return m.group(0)
out=re.sub(r'\b0x([0-9a-f]{3,4})\b', rep, src)
open(sys.argv[2],'w').write(out)
