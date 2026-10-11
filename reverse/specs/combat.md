# Warlords (DOS v2.10) — Combat specification

Source: Ghidra decompilation `/home/claude/gh/d3.c`, checked against capstone disassembly (`gdis()` in
`/home/claude/re/wl.py`) wherever far-segment accesses or stack arguments mattered. Addresses are **Ghidra**
segment:offset (image segment + 0x1000). `DS:x` = DGROUP offset x. `dice(n,s,p)` = FUN_1b90_0026 (see NOTES.md).

Confidence: **H** = verified in disassembly, **M** = clear in decompile, not fully re-verified, **L** = inferred.

---------------------------------------------------------------------------------------------------------
## 0. Data structures

### 0.1 Army record (24 bytes, far array `38f4:0000` in image segs, up to 2000 records; DS:0xacc8 = highest used index + 1)

| off | type | meaning | evidence |
|----:|------|---------|----------|
| +0x00 | int16 | x (-1 = free / not on map) | 2b32:0318 sets -1 |
| +0x02 | int16 | y | |
| +0x04 | int8  | army type 0..15 (15 = Hero); 0xFF = free slot | 23cd sort key; 2cad:0438 hero = 0x0F |
| +0x05 | int8  | owner 0..7 (0xFF = free slot) | 2b32_027c alloc searches `+5 == -1` |
| +0x06 | int8  | max movement points | 2f0e_1010: city +0x38[slot] |
| +0x07 | int8  | movement points left (attack needs >= 2, costs 2) | 2289_0004 / 2289_0466 |
| +0x08 | int8  | strength (base combat value) | 2f0e_1010: city +0x2E[slot]; hero = 5 at creation |
| +0x09 | int8  | home city index (0..79) | 2f0e_1010 |
| +0x0A | int16 | serial number (per city & type counter DS:0x6cc0[city*10+type]); for heroes: hero-name slot (name at DS:0xcc88 + 20*slot, slot-used flag DS:0x65be[slot]) | 2f0e_1010, 2cad_0438, 2289_139e |
| +0x0C | int8  | **hit points** (1 at creation; decremented in battle; dies when < 0; never restored) | 2289:07e7/0864, the only writes are `=1` at 2cad:0615, 2f0e:1101, 307e:14a7 |
| +0x0E | int16 | 0 at creation (not used by combat) | |
| +0x10 | int8  | upkeep gp/turn (= city cost/2; 0 for heroes); player upkeep total DS:0x20be[p] | 2f0e_1010, 2b32_0318 |
| +0x12 | uint8 | flags: 0x01 in use, 0x40 sentry/fortified, 0x20/0x80 AI flags | 2b32_027c, 1c8b_043a |
| +0x13 | uint8 | more flags (bit1) | 1c8b |
| +0x14/+0x16 | int16×2 | goto/vector destination (‑1,‑1 = none) | 2b32_027c |

Save-file cross-check (`War1.sav`, records from byte 20, 527 records, 42 free): type/str/upkeep consistent with
city tables (e.g. type 1 Heavy Inf str 5 upkeep 2; type 8 Pegasi upkeep 8; type 15 heroes upkeep 0, str 5–6);
`+0x0C`: 472 records = 1, **13 records = 0** (wounded survivors — confirms persistent damage); flags 0x01/0x41/...;
hero items in the save's item table have holder = army index of a type‑15 record. (H)

### 0.2 Item record (14 items, 30 bytes each, DS:0x217e; saved in the save file)
`name[20], kind:int8 (+0x14), value:int8 (+0x15), state:int8 (+0x16), pad, holder:int16 (+0x18), x:int16 (+0x1a), y:int16 (+0x1c)`
- kind 1 = **battle** bonus ("Bat +": adds to the carrying hero's own strength); kind 2 = **command** bonus ("Com +": adds to every unit in the hero's stack). (H, 200c_1fd2 labels)
- state 3 = carried, holder = army index; state 1 = lying on map at (x,y); state 2 = in a site/ruin.

| # | name | kind | value |
|--:|------|-----:|------:|
| 0 | Firesword | 1 | 1 |
| 1 | Icesword | 1 | 1 |
| 2 | Lightsword | 1 | 2 |
| 3 | Darksword | 1 | 2 |
| 4 | Staff of Might | 1 | 3 |
| 5 | Crown of Loriel | 2 | 1 |
| 6 | Sceptre of Loriel | 2 | 1 |
| 7 | Orb of Loriel | 2 | 1 |
| 8 | Ring of Power | 2 | 2 |
| 9 | Staff of Ruling | 2 | 3 |
| 10 | Spear of Ank | 1 | 1 |
| 11 | Bow of Eldros | 1 | 2 |
| 12 | Horn of Ages | 2 | 2 |
| 13 | Crimson Banner | 2 | 1 |

Helper: `items_of(hero)` = FUN_2e03_0000(2,0,0,hero): finds the hero's array index (scan acc8-1..0), returns all items
with `state==3 && holder==index` (list DS:0xa97a, count DS:0xa86a).
- `bat_bonus(hero)` = Σ value of its kind‑1 items (FUN_23cd_0bdc).
- `cmd_items(hero)` = Σ value of its kind‑2 items (inline in 23cd_000c).

### 0.3 Other globals used
- Castle record (100 B, DS:0x4632): +0x18 defence (int8; 3..6 at start), +0x19 owner, +0x4c production slot,
  +0x4e production turn counter, +0x50 income, +0x52 "previous/claimant owner" word, +0x54 vector flag,
  +0x56/+0x58 vector target x,y, +0x5a word.
- Player data: gold DS:0x20e0+20*p (int16), capital x/y DS:0x20e4/0x20e6+20*p, city count DS:0x20ae[p],
  income DS:0x20ce[p], upkeep DS:0x20be[p], human flag DS:0x7e86[p] (1 = human), alive DS:0x2322[p].
- Hatred matrix DS:0xb804: `hate[row][col]` int16, row stride 16 bytes (8 cols).
- Map word: `&0x7F` tile index → class via DS:0x3934; `(w>>7)&0xF` owner (of city/tower, or of armies on it);
  `0x800` = tile occupied by armies (recomputed for whole map by FUN_274c_0274 from all live armies).
- Terrain classes: 0 Road, 1 Bridge, 2 Water, 3 Shore, 4 Forest, 5 Hill, 6 Mountain, 7 Plain, 8 Marsh, 9 Tower,
  10 City, 11 Ruins. City tiles: index `0x5A + owner*4 + k` (k = quadrant); tower tile index `owner+2` (1..9);
  ruin/razed tile index 0x0C (class 11).

### 0.4 Combat tables (far data segment image 0x3043 = Ghidra 0x4043; static, only read by 23cd_000c and display/AI code)
All int16. Extracted from the EXE image (file offset 0x3000 + 0x30430 + off).

**CITY_DEF_BONUS[defence]** @ 0x0000 (11 entries, index = castle +0x18):
`[0, 0, 1, 1, 1, 1, 1, 2, 2, 3, 3]`

**HERO_CMD[s]** @ 0x0016 (10 entries, s = best hero strength 0..9):
`[0, 0, 0, 0, 1, 1, 1, 2, 2, 3]`

**TYPE_TERRAIN[type][class]** @ 0x002A (16 × 12), columns Road,Bridge,Water,Shore,Forest,Hill,Mountain,Plain,Marsh,Tower,City,Ruins:
```
 0 Giant Warriors  [0,0,0,0,-1, 0,0,0, 0,0,0,0]
 1 Heavy Infantry  [0,0,0,0,-1,-1,0,0,-1,0,0,0]
 2 Light Infantry  [0,0,0,0,-1,-1,0,0, 0,0,0,0]
 3 Dwarven Legion  [0,0,0,0,-1, 1,0,0, 0,0,0,0]
 4 Cavalry         [0,0,0,0,-1,-1,0,0,-1,0,0,0]
 5 Navy            [0,0,0,0, 0, 0,0,0, 0,0,0,0]
 6 Elven Archers   [0,0,0,0, 1,-1,0,0,-1,0,0,0]
 7 Wolf Riders     [0,0,0,0,-1,-1,0,0, 0,0,0,0]
 8 Pegasi          [0,0,0,0, 1, 0,0,0, 0,0,0,0]
 9 Griffins        [0,0,0,0, 0, 1,0,0, 0,0,0,0]
10 Wizard          [0,0,0,0, 0, 0,0,0, 0,0,0,0]
11 Undead          [0,0,0,0,-1, 0,0,0, 1,0,0,0]
12 Dragons         [0,0,0,0, 0, 0,0,0, 0,0,0,0]
13 Demons          [0,0,0,0,-1, 0,0,0, 0,0,0,0]
14 Devils          [0,0,0,0,-1, 0,0,0, 0,0,0,0]
15 Hero            [0,0,0,0, 0, 0,0,0, 0,0,0,0]
```

**CLAN_TERRAIN[clan][class]** @ 0x01AA (rows 0..7 are real data):
```
0 Sirians       [0,0,0,0, 0, 0,0,0, 0,0,0,0]
1 Storm Giants  [0,0,0,0, 0, 1,0,0,-1,0,0,0]
2 Grey Dwarves  [0,0,0,0,-1, 2,0,0,-1,0,0,0]
3 Orcs of Kor   [0,0,0,0,-1, 0,0,0, 1,0,0,0]
4 Elvallie      [0,0,0,0, 1,-1,0,0,-1,0,0,0]
5 Selentines    [0,0,1,1, 0, 0,0,0, 0,0,0,0]
6 Horse Lords   [1,0,0,0,-1,-1,0,1, 0,0,0,0]
7 Lord Bane     [0,0,0,0,-1, 0,0,0, 1,0,0,0]
```
Row 15 (neutral owner) is an out-of-bounds read of unrelated data at 0x0312:
`[-1,-1,-1,-1,0,-1,-1,-1,0,1,2,2]`. It is only reached if the normal battle path fights a tile whose owner
nibble is 15 (neutral armies outside a city), which normal play does not seem to produce (neutral cities use §3). (M)

**Flyer class** DS:0x4376[type] (movement class): `[0,0,0,1,2,3,4,2,5,5,0,0,5,0,0,0]` — value 5 = flying (types 8, 9, 12).

---------------------------------------------------------------------------------------------------------
## 1. Entry points and attack preconditions

| function | role |
|----------|------|
| 2289_0004 | human attack (click/direction). Calls 2491_000a for neutral cities, else the normal battle |
| 2289_119e | AI attack on an owned enemy city (called from the AI 3257_04c6); same battle |
| 2491_000a | human assault on a **neutral city** (single d100 roll, §3) |
| 2491_0341 | AI assault on a neutral city (same roll, no UI) |
| 23cd_000c | builds both unit lists, sorts them, computes strengths and hp (§2) |
| 2289_067a | battle roll loop (already decoded, summarized in §4) |
| 2289_09c0 | after the battle: removal, tile ownership, city capture, pillage (§5) |
| 2289_139e | hero death: drops its items |
| 3043_009a / 3043_01d8 | raze tower / city (player command, §6) |
(FUN_27ed_0006 and FUN_2c5c_000c in d3.c are Ghidra mis-decodes of the same code as 2289_0004/24ef_0004 — ignore.)

The attacking side is the **currently selected group**: if more than one unit is selected (DS:0x377c != 0, set when
group slot 2 is non-null), the group list DS:0xb2ba (up to 8 far ptrs, count DS:0xad5e); otherwise the single active
army DS:0xb2e2. This is whatever the player or AI put in the group (the whole stack or only part of it). Units left on the source tile do not fight.

Human attack (2289_0004), target tile T = clicked tile if it is within 1 of the active army (Chebyshev), otherwise
the active army position + direction delta (DS:0x32aa/0x32ba). (H)
```
if group:  if group_moves (DS:0xb716 = min +7 of group, or min of navies if any navy) < 2: no attack
           cost = GROUP_COST[class(T)]  (DS:0xcfa8; built by 1cdf_07b2: navy row if any Navy in group,
                  else max over non-hero members of MOVE[type][class], hero row if all heroes)
else:      if army.moves < 2: no attack
           cost = MOVE[army.type][class(T)]     (DS:0x37b4 + type*24 + class*2)
if cost == 66: no attack (impassable)
if class(T)==City and owner(T)==15:  -> neutral city assault (§3)
battle if (T.occupied(0x800) and owner(T) != me) or
          (class(T)==City and owner(T) != me and not T.occupied)    # empty enemy city
otherwise: not an attack (normal move)
```
Sequence for a battle (H):
1. 2289_0466: every attacking unit gets `x,y = T` and `moves -= 2` (group: also DS:0xb716 -= 2). Attackers are on T before the fight.
2. 23cd_000c(T) (§2). (The AI path 2289_119e calls 23cd_000c before 2289_0466; the result is the same.)
3. r = 2289_067a() (§4). 1 = attacker won.
4. Display; FUN_274c_0274 recomputes occupancy flags; message:
   win: `"The garrison has fled before you!"` if there were no defenders (DS:0xbbc0), else `"%s has won the battle!"`
   (hero name) if the group has a leader hero (DS:0xb2b6), else `"You are victorious!"`; loss: `"You have been defeated!"`.
   AI path: `"%s: you are being attacked!"`, then `"%s: you are victorious!"` / `"%s has won the battle!"` / `"%s: you have lost!"` shown to the human defender.
5. 2289_09c0(r, T.x, T.y) (§5). If r==1: T |= 0x800. If 09c0 returned 0x21 (city captured), the human gets the city production dialog.

No random numbers are consumed anywhere in this flow except inside 2289_067a (and the d100 in §3). Checked by
transitive call-graph search for rand/dice from all called functions. (M)

---------------------------------------------------------------------------------------------------------
## 2. Building the battle (FUN_23cd_000c) — all (H)

### 2.1 Target tiles
```
w = map[T]
def_clan = (w >> 7) & 0xF                       # DS seg309d:0x851c
if class(w) == City:
    city = first c in 0..79 with c.x in {T.x, T.x-1} and c.y in {T.y, T.y-1}
    tiles = [(city.x+DX[k], city.y+DY[k]) for k in 0..3],  DX=[0,1,0,1], DY=[0,0,1,1]   (DS:0x3dce/0x3dd6)
else:
    tiles = [T]
cls = class(map[tiles[0]])          # 0xbbc2 = tile word of tiles[0]; for a city, the top-left tile (class 10)
water = class(map[T]) in {Water(2), Shore(3), Mountain(6)}   # terrain only flyers/navies can stand on
```

### 2.2 Unit lists and order
```
A = attacking group in group-list order (len nA <= 8)
D = []
for k = len(tiles)-1 downto 0:                  # city: (1,1),(0,1),(1,0),(0,0)
    for j = army_count-1 downto 0:              # DS:0xacc8
        if army[j].x,y == tiles[k] and army[j].owner != current_player:   (byte compare)
            D.append(army[j])                   # max 32
```
All non-own armies on the tile(s) defend. No check on terrain or type.

Order: for each list separately (A, then D: same procedure):
```
key(u) = u.type
for u in list: if u.type == Navy(5): key = 127                     # always: navies fight last
               elif water and no flyer marked yet in this list and FLYCLASS[u.type]==5:
                    key = u.type + 100; mark                        # first flyer in list order: 2nd-to-last
stable insertion sort ascending by key (signed byte compare)
```
So units fight in **ascending army-type index**: 0 Giant Warriors, 1 Heavy Inf, 2 Light Inf, 3 Dwarves, 4 Cavalry,
6 Elves, 7 Wolf Riders, 8 Pegasi, 9 Griffins, 10 Wizard, 11 Undead, 12 Dragons, 13 Demons, 14 Devils, 15 Heroes;
then (on water/shore/mountain only) the first flyer of the original list, then all Navies. Ties keep their list order.
It is **not** sorted by strength. (The code does this by temporarily overwriting `army.type` with the key and restoring it afterwards.)

### 2.3 hp
`hpA[i] = (int8)A[i].hp(+0x0C)`, `hpD[i] = (int8)D[i].hp`. All alive flags = 1.
A unit with hp h absorbs h+1 hits (fresh unit h=1 → 2 hits; wounded h=0 → 1 hit).

### 2.4 Effective strength
```
def side_bonus(units, clan, defender):
    best = 0                                   # hero leadership
    fly = special = cmd = 0
    for u in units:
        if u.type == 15:
            v = u.str + bat_bonus(u)
            if v > best: best = min(v, 9)
            cmd += cmd_items(u)                # summed over ALL heroes of the side
        if u.type in (8, 9, 12):  fly = 1      # Pegasi, Griffins, Dragons
        if 10 <= u.type <= 14:    special = 1  # Wizard, Undead, Dragons, Demons, Devils
    b = CLAN_TERRAIN[clan][cls] + HERO_CMD[best] + fly + special + cmd
    if defender:
        if   cls == Tower(9):  b += 2
        elif cls == Ruins(11): b += 1
        elif cls == City(10):  b += CITY_DEF_BONUS[city.defence]     # castle +0x18
    return b

bA = side_bonus(A, current_player, False)
bD = side_bonus(D, def_clan, True)
for each unit u of a side with bonus b:
    s = TYPE_TERRAIN[u.type][cls] + u.str + b
    if u.type == 15: s += bat_bonus(u)
    s = min(s, 9)                 # upper cap only, NO lower bound (s may be <= 0)
```
Notes:
- Both sides use the class of the **defended** tile (`cls`), never the attacker's own tile.
- The clan row is the attacker = current player, the defender = owner nibble of the clicked tile T.
- Fly/special/hero/item bonuses are each counted once per side and apply to every unit of that side, heroes included.
- Ruins class 11 includes razed cities/towers (tile 0x0C).
- Arrays: attacker strength `38f4:bc62`, hp `309d:0000`, type `309d:851e`, owner `309d:0010`, alive `38f4:bc0a`;
  defender strength `309d:8530`, hp `38f4:bb80`, type `38f4:bc72`, owner `38f4:bbca`, alive `309d:0022`;
  pointer lists DS:0xb6d6 (attackers) / DS:0xa89e (defenders); counts nA `38f4:bc1e`, nD `309d:851a` (image segs).

---------------------------------------------------------------------------------------------------------
## 3. Neutral city assault (2491_000a human, 2491_0341 AI) — (H)
Neutral cities have **no garrison battle**. One roll is made against the castle defence:
```
move attackers onto T, moves -= 2                         (2289_0466)
run 23cd_000c(T)  -> sorted A with strengths SA (cls = City, so terrain rows add 0)
score = sum_{i=0}^{nA-1} SA[i] * (i+1)                     # weight = position in fight order
r = dice(1,100,0)                                          # 1..100 (101 with p = 1/32768)
win = r <= 110 - (10*city.defence - score)                 # i.e. r <= 110 - 10*def + score
```
- Loss: every attacking unit dies: heroes drop items at T (2289_139e(hero, T.x, T.y)), all freed (2b32_0318);
  active army cleared. Message `"You have been defeated!"`.
- Win (return 0x21): city.owner = me; income[me] += city.income(+0x50); cities[me] += 1; the 4 city tiles get index
  `0x5A + me*4 + k` and owner nibble = me; T |= 0x800; `"You are victorious!"`. No pillage, no defence
  reduction, no hatred change, +0x4e/+0x52 untouched. Any armies that were on the city tiles (normally none) are ignored and not removed.

---------------------------------------------------------------------------------------------------------
## 4. Battle loop (2289_067a) — summary, (H)
```
bbc0 = 0
if nA == 0 or nD == 0: bbc0 = 1; return 1                 # "garrison has fled": no RNG used
a = d = 0
loop:
    N = 12 if DS:0x2088 ("Intense Combat" option, toggled in 200c_2796) else 10
    r1 = dice(1,N,0); r2 = dice(1,N,0)                    # r1 first
    defHit = r1 <= SD[d];  attHit = r2 <= SA[a]
    if defHit == attHit: continue                         # both or neither: reroll
    if defHit: hpA[a] -= 1; A[a].hp -= 1; if hpA[a] < 0: aliveA[a]=0; log(1); a += 1
    else:      hpD[d] -= 1; D[d].hp -= 1; if hpD[d] < 0: aliveD[d]=0; log(0); d += 1
    if d == nD: return 1 ;  if a == nA: return 0
```
- Each roll: `(int)(rand()/32767.0*N + 1.0)`; values 1..N, plus N+1 when rand()==32767. A roll of N+1 can never hit.
- If both current strengths are <= 0, neither side can ever hit and the original **loops forever**.
  This can happen, e.g. a str‑2 Light Infantry of Grey Dwarves in forest (−1 type, −1 clan) against a similar unit.
  An implementation should either reproduce this or add a guard; either way, document the choice.
- Damage to army +0x0C persists after the battle (no healing exists anywhere in the EXE).
- The death log (`38f4:bc30`, count `309d:0020`) is only used for the battle animation.

---------------------------------------------------------------------------------------------------------
## 5. After the battle (2289_09c0(r, x, y)) — (H)
```
group = [A[i] for i in sorted order if aliveA[i]];  active army = group[0] or null   # survivors keep fight order
for i in A not alive: if type==15: hero_death(A[i], x, y);  free(A[i])
for i in D not alive: if type==15: hero_death(D[i], x, y);  free(D[i])
t0 = tiles[0]                                           # T, or city top-left
if r == 0: map[t0].owner = def_clan;  return 1
map[t0].owner = me
if cls == Tower:  map[T].index = me + 2                 # tower changes colour (T = (x,y))
if cls == City:   capture (below); return 0x21
return 1
```
**free(u)** (2b32_0318): upkeep[u.owner] -= u.upkeep; type = owner = 0xFF; x = y = -1; +0x14/+0x16 = -1; moves = 0.

**hero_death(h, x, y)** (2289_139e): `heroNameUsed[h.nameSlot] = 0`; hero count DS:0xb8c4 -= 1; each item carried:
`state = 1, holder = 0, x,y = battle tile T` (it lies on T, for both attacker and defender heroes).

**City capture** (attacker won on a City; def = def_clan, me = current player):
```
if human[def] == 0:  hate[def][me] += 2                              # DS:0xb804 + def*16 + me*2
g = gold[def]                                                         # int16, signed
p = g if cities[def] < 2 else g / cities[def]                         # C int division (toward 0)
p = p / 2 (toward 0);  if p < 0: p = 0
if human[me] and p > 0: message "Your armies pillage %d gp!"
gold[me] += p;  gold[def] -= 2*p
city.prevOwner(+0x52) = 15 if city.prevOwner == me else city.owner(+0x19)  # old owner
city.owner = me;  city.prodTurns(+0x4e) = 0
if city.defence > 0: city.defence -= 1                                # permanent per capture
for k in 3..0: tile[k].flags &= ~0x800; tile[k].index = 0x5A + me*4 + k; tile[k].owner = me
income[me] += city.income; cities[me] += 1; cities[def] -= 1; income[def] -= city.income
if capital[def] == (city.x, city.y): relocate_capital(def)
if city.vector(+0x54): city.vector = 0; city(+0x5a) = -1
for every city c with c.vector != 0 and (c.vx, c.vy) == (city.x, city.y):
    c.prod(+0x4c) = -1; c.prodTurns = 0; c.vector = c.vx = c.vy = 0    # their production is cancelled
AI bookkeeping 24ef_1a46 (no rules effect)
```
`cities[def]` used for pillage is the count before the decrement (it still includes this city).

**relocate_capital(p)** (2289_1075): if cities[p]==0 → unchanged. Otherwise the capital becomes the
**highest-index** city owned by p. The code meant to choose the nearest city, but its "best distance" is a constant
1,000,000 that never updates, so every owned city qualifies and the last one wins. (H)

No experience, no strength gain, no morale effects come from combat. Hero strength increases only from sites
("The Gods hear! %s's strength increases", 307e_*), and armies are blessed in temples. These are outside combat.

---------------------------------------------------------------------------------------------------------
## 6. Razing (player command, not automatic) — (H)
Allowed when the active army stands on a city or tower tile owned by the current player (3043_0000;
otherwise `"You can only raze cities and towers"`).
- Tower (3043_009a): tile index = 0x0C (ruins, class 11). `"The tower is destroyed!"`
- City (3043_01d8): income[me] -= city.income; cities[me] -= 1; city.owner = 15; city.prevOwner = 15;
  all 4 tiles index = 0x0C (owner nibble unchanged); own vectoring cancelled (+0x54=0, +0x5a=-1); cities vectoring
  to it get production cancelled (as in §5); capital relocated if it was the capital; **hate[q][me] += 1 for all q = 0..7**.
  `"Your troops ravage %s!"`, `"%s is in ruins!"`.

---------------------------------------------------------------------------------------------------------
## 7. Diplomacy side effects (for completeness)
- The only hatred change caused by battle is the +2 on city capture (§5); razing gives +1 (§6).
- `"%s declares war on %s"` (24ef_0004) is the AI's per-turn war-target selection (DS:0xcc74[p]), driven by the hatred
  matrix. It is **not** triggered by combat itself.
- "No Quarter !!!" (1b90_0730) is a menu command (called from 1312 dispatch at 1312:1864). For every living p and
  living q: if q is human, `hate[p][q] = dice(1,1000,100)` and `warTarget[p] = current player`; otherwise `hate[p][q] = 0`.

---------------------------------------------------------------------------------------------------------
## 8. Randomness summary
| where | call | use |
|-------|------|-----|
| 2289_067a | 2 × dice(1,10,0) per round (dice(1,12,0) with Intense Combat) | battle rounds, r1 then r2 |
| 2491_000a / 0341 | 1 × dice(1,100,0) | neutral city assault |
| 1b90_0730 | dice(1,1000,100) per (p,human q) | No Quarter hatred |
Nothing else in the attack flow calls rand().

## 9. Open points / uncertainty
- CLAN_TERRAIN row 15 garbage (§0.4) only matters for neutral non-city armies (believed not to exist). (M)
- How groups are formed (which units of a stack are selected) is UI code (1c8b_049c / 1cdf_07b2) and was not traced in full. (M)
- Castle +0x4e is assumed to be the production turn counter and +0x52 the "previous owner" (as used by AI). (L)
