import os
import sys, re, struct, collections, pickle, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wl import *
# function list from d3.c headers
F=[]
for line in open(os.environ.get('WARLORDS_DECOMP', 'd3.c')):
    if line.startswith('// ==== '):
        nm, at = line.split()[2], line.split()[4]
        s,o = at.split(':'); F.append((int(s,16)-0x1000, int(o,16), nm))
F.sort(key=lambda t: t[0]*16+t[1])
LIN=[s*16+o for s,o,n in F]
NAME={(s,o):n for s,o,n in F}
import bisect
def func_at(lin):
    i=bisect.bisect_right(LIN, lin)-1
    return F[i] if i>=0 else None
def func_range(nm):
    for i,(s,o,n) in enumerate(F):
        if n==nm:
            end = LIN[i+1] if i+1<len(F) else s*16+o+0x1000
            return s,o,end-(s*16+o)
def lindis(start,end,o):
    p=start
    while p<end:
        got=False
        for ins in md.disasm(PIMG[p:end], o+(p-start)):
            got=True; yield ins; last=ins
        if got: p=start+(last.address-o)+last.size
        else: p+=1
        if not got: continue
        # capstone stopped early: skip a byte
        if p<end: p+=0
        nxt=list(md.disasm(PIMG[p:p+16], o+(p-start), count=1))
        if not nxt: p+=1
CACHE='/tmp/claude-0/cg.pkl'
def build():
    calls=collections.defaultdict(set)
    for i,(s,o,n) in enumerate(F):
        start=s*16+o; end=LIN[i+1] if i+1<len(F) else start+0x800
        if end-start>0x10000: end=start+0x10000
        for ins in lindis(start,end,o):
            if ins.mnemonic=='lcall':
                m=re.match(r'0x([0-9a-f]+), (0x[0-9a-f]+|\d+)', ins.op_str)
                if m:
                    ts,to=int(m.group(1),16),int(m.group(2),0)
                    calls[n].add(NAME.get((ts,to),'%04x:%04x'%(ts+0x1000,to)))
            elif ins.mnemonic=='call' and ins.op_str.startswith('0x'):
                to=int(ins.op_str,16)
                calls[n].add(NAME.get((s,to),'near_%04x:%04x'%(s+0x1000,to)))
    return calls
if os.path.exists(CACHE): calls=pickle.load(open(CACHE,'rb'))
else:
    calls=build(); pickle.dump(calls,open(CACHE,'wb'))
callers=collections.defaultdict(set)
for a,bs in calls.items():
    for b in bs: callers[b].add(a)
def sdis(nm=None, gseg=None, off=None, n=None):
    """annotated disassembly of a whole function"""
    if nm: s,o,n2=func_range(nm); n=n or n2
    else: s,o=gseg-0x1000,off
    base=s*16+o
    for ins in lindis(base,base+n,o):
        t=ins.op_str; ann=''
        if ins.mnemonic=='lcall':
            m=re.match(r'0x([0-9a-f]+), (0x[0-9a-f]+|\d+)', t)
            if m: ts,to=int(m.group(1),16),int(m.group(2),0); ann=NAME.get((ts,to),'')
        for m in re.finditer(r'0x([0-9a-f]{3,4})\b', t):
            v=int(m.group(1),16)
            try:
                if IMG[DSB+v-1]==0:
                    e=IMG.index(b'\0',DSB+v); st=IMG[DSB+v:e]
                    if 3<=len(st)<70 and all(32<=c<127 for c in st): ann+=' "%s"'%st.decode()
            except Exception: pass
        print('%04x:%04x  %-6s %s%s'%(s+0x1000, ins.address, ins.mnemonic, t, ('   ; '+ann) if ann else ''))
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='calls': print(sorted(calls[sys.argv[2]]))
    elif cmd=='callers': print(sorted(callers[sys.argv[2]]))
    elif cmd=='dis': sdis(sys.argv[2])
    elif cmd=='disr': sdis(gseg=int(sys.argv[2],16), off=int(sys.argv[3],16), n=int(sys.argv[4],16))
