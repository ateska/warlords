import struct, sys
import os
D=open(os.environ.get('WARLORDS_SAV', 'WAR1.SAV'),'rb').read()
p=0
def rd(n):
    global p; b=D[p:p+n]; p+=n; return b
name=rd(16); ver,=struct.unpack('<H',rd(2)); na,=struct.unpack('<H',rd(2))
armies=[rd(24) for _ in range(na)]
mapw=rd(156*109*2)
castles=[rd(26) for _ in range(80)]
fields=[('ruins',0x460),('g20be',16),('g20ce',16),('g20ae',16),('players20de',160),('items217e',0x1a4),('g6cc0',0x640),('alive2322',16),('b2e2',2),('aa60',2),('turn_b6d4',2),('b716',2),('cfa8',24),('ad5e',2),('cc88',800),('g65be',40),('ad60',2),('b712',2),('d1ca',2),('b6f6',2),('af00',2),('af04',2),('g7e86',16),('cur7ea6',2),('g7ea8',2),('b804',128),('cc74',16),('g2478',2),('g247a',2),('g2474',2),('g7e96',16),('g2476',2),('g208e',16),('g209e',16),('b32e',100),('ae24',2),('intense2088',2)]
G={}
for n,s in fields: G[n]=rd(s)
G['_rest']=D[p:]
