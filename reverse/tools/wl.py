import struct, re, collections
from capstone import *
import os
D = open(os.environ.get('WARLORDS_EXE', 'WARLORDS.EXE'),'rb').read()
HDR = 0x3000
IMG = D[HDR:]
DSEG = 0x44c0
DSB = DSEG*16
md = Cs(CS_ARCH_X86, CS_MODE_16); md.detail = False
def ds(o): return IMG[DSB+o:DSB+o+1]
def dsstr(o):
    e = IMG.index(b'\0', DSB+o); return IMG[DSB+o:e].decode('latin1')
def dsw(o): return struct.unpack_from('<H', IMG, DSB+o)[0]
def lin(seg, off): return seg*16+off
def dis(seg, off, n=200, stop_ret=True, out=True):
    base = lin(seg, off)
    res=[]
    for i in md.disasm(IMG[base:base+n], off):
        s='%04x:%04x  %-7s %s'%(seg, i.address, i.mnemonic, i.op_str)
        res.append((i,s))
        if out: print(s)
        if stop_ret and i.mnemonic in ('ret','retf','iret'): break
    return res
# far call targets
def far_calls():
    t=collections.Counter()
    for m in re.finditer(rb'\x9a(..)(..)', IMG[:DSB], re.S):
        off,seg=struct.unpack('<HH', m.group(1)+m.group(2))
        if seg < DSEG and lin(seg,off) < DSB:
            t[(seg,off)]+=1
    return t
def xrefs(dsoff, code_end=DSB):
    pat = struct.pack('<H', dsoff)
    res=[]
    for m in re.finditer(re.escape(pat), IMG[:code_end]):
        p=m.start()
        if p>0 and IMG[p-1] in (0xb8,0xb9,0xba,0xbb,0xbe,0xbf,0x68): res.append(p-1)
        elif p>1 and IMG[p-2]==0xc7: res.append(p-2)
        elif p>2 and IMG[p-3]==0xc7: res.append(p-3)
        elif p>1 and IMG[p-2] in (0x8b,0x89,0x8a,0x88,0x8d,0x3b,0x39,0x03,0x2b,0x80,0x81,0x83,0xff,0xc6,0xf6,0xf7,0xfe,0xa0,0xa1,0xa2,0xa3) : res.append(p-2)
        elif p>0 and IMG[p-1] in (0xa0,0xa1,0xa2,0xa3): res.append(p-1)
        elif p>2 and IMG[p-3] in (0x8b,0x89,0x8a,0x88,0x8d,0x3b,0x39,0x80,0x81,0x83,0xff,0xc6,0xf6,0xfe,0x03,0x2b): res.append(p-3)
    return res
SEGS = sorted(set(s for (s,o),c in far_calls().items()))
def seg_of(lin_addr):
    best=None
    for s in SEGS:
        if s*16<=lin_addr: best=s
    return best
def func_start(lin_addr):
    # scan back for push bp; mov bp,sp
    p=lin_addr
    while p>0 and lin_addr-p<0x3000:
        if IMG[p:p+3]==b'\x55\x8b\xec': return p
        p-=1
    return None
def where(p):
    s=seg_of(p); f=func_start(p)
    return '%05x seg %04x off %04x func %04x:%04x'%(p, s, p-s*16, s, (f-s*16) if f else -1)
def str_xrefs(s):
    off = IMG.find(s.encode()+b'\0', DSB)-DSB
    return off, [where(p) for p in xrefs(off)]
# patched image with MS FP-emulator interrupts replaced by real x87 opcodes
PIMG = bytearray(IMG)
for _m in re.finditer(rb'\xcd([\x34-\x3d])', IMG[:DSB]):
    _p=_m.start(); _k=_m.group(1)[0]
    if 0x34<=_k<=0x3b: PIMG[_p]=0x9b; PIMG[_p+1]=0xd8+(_k-0x34)
    elif _k==0x3d: PIMG[_p]=0x90; PIMG[_p+1]=0x9b
PIMG=bytes(PIMG)
def gdis(gseg, off, n=200, stop_ret=True, out=True):
    seg=gseg-0x1000; base=lin(seg,off); res=[]
    for i in md.disasm(PIMG[base:base+n], off):
        s='%04x:%04x  %-7s %s'%(gseg, i.address, i.mnemonic, i.op_str)
        res.append((i,s))
        if out: print(s)
        if stop_ret and i.mnemonic in ('ret','retf','iret'): break
    return res
