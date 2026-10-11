# Warlords 2.10 — Exploration rules spec (ruins, temples, sages, libraries, altars, thrones, items)

Source: Ghidra decompilation `/home/claude/gh/d3.c`, verified instruction-by-instruction with
`gdis()` wherever the decompiler garbled far/stack accesses. Addresses are Ghidra `SEG:OFF`
(image segment + 0x1000). `DS:x` = DGROUP offset (file offset 293888 + x).
Validated against `/home/claude/data/War1.sav` (mid-game save) — see section 10.

Confidence tags: **[H]** verified in disassembly, **[M]** decompiler + partial check, **[L]** inferred.

---------------------------------------------------------------------------------------------------
## 0. Shared primitives

```
rand():  seed = (seed*0x343FD + 0x269EC3) & 0xFFFFFFFF ; return (seed>>16) & 0x7FFF     # FUN_39e5_2c92
dice(n, sides, plus):                                                                    # FUN_1b90_0026 [H]
    if sides == 0: return plus            # NOTE: no rand() consumed
    s = 0
    repeat n times: s += int(rand()/32767.0*sides + 1.0)   # trunc toward 0; rand()==32767 gives sides+1
    return s + plus                        # n <= 0 -> returns plus, no rand()
dist(x1,y1,x2,y2) = int(sqrt(dx*dx+dy*dy))   # FUN_3257_1b8f; (extra 5th arg pushed by callers is ignored)
```
All messages are shown with `FUN_1312_2016(str)` (modal message line). They do not consume RNG.

Relevant globals:
| DS addr | meaning |
|---|---|
| 0x7ea6 | current player 0..7 |
| 0xb2e2 (far ptr) | CurrentArmy (selected army) |
| 0xb2b6 (far ptr) | CurrentHero = hero (army type 15) in the selected stack, or NULL (see 0.1) |
| 0x377c | group mode flag (selected stack of up to 8 armies in far ptr array DS:0xb2ba, 8×4 bytes) |
| 0xb716 | group movement points (min of members) |
| 0x20de + 20*p | player record (20 bytes); **gold = word at +2** (DS:0x20e0+20p) |
| 0x20be + 2*p | per-player total upkeep (word) |
| 0x2478 / 0x247a | "gem already given" flags for site 1 (Seer of the River) / site 7 (Grand Oracle) — **global, not per player** |
| 0xcc88 + 20*i | hero name table (40 × char[20]); hero army `+0x0a` = name index i |
| 0x65be + i | hero-name-in-use flags (40 bytes) |
| 0xaf00 / 0xaf04 | map cursor x / y (viewport centre; follows the selected army) [M] |

### 0.1 CurrentHero selection (FUN_1c8b_049c) [M]
Single-army mode: CurrentHero = CurrentArmy if `CurrentArmy.type (+4) == 15` else NULL.
Group mode: scan slots 7..0, every member with type 15 overwrites CurrentHero → the **lowest slot
index hero** wins.

### 0.2 Army record fields used here (24 bytes, far array, index 0..count-1, count = DS:0xacc8)
`+0 x(w) +2 y(w) +4 type(b) +5 owner(b, 0xFF=free slot) +6 max moves(b) +7 moves left(b)
+8 strength(b, 0..9) +9 ?(b) +0x0a hero name index(w) +0x0c hp(b) +0x0e (w) +0x10 upkeep(b)
+0x12 flags(w) +0x14 AI goal(w) +0x16 (w)`.
`+0x12` bits: 0x01 set on selection/creation; **0x02/0x04/0x08/0x10 = blessed at temple site
0/2/5/6** (section 4).

### 0.3 Map tile word (far seg, `tile(x,y)` = word at y*0xDA + x*2 + 0x42)
`&0x7F` graphic index, `(w>>7)&0xF` owner/occupant, `0x0800` army-present, **`0x8000` = site
explored**. Graphic → class via table DS:0x3934; graphics 10, 11, 12 → class 11 ("Ruins").
Graphic 11 is the building (temple/sage/library); 10 and 12 are ruin graphics.

### 0.4 Movement-point deduction FUN_307e_153b(who, n) [H]
```
who==1 (hero):  hero.moves = max(0, hero.moves - n)
                if group mode: group_moves(0xb716) = min(group_moves, hero.moves)
who==0 (stack): if not group mode: CurrentArmy.moves = max(0, CurrentArmy.moves - n)
                else: group_moves = max(0, group_moves-n); for each of the 8 slots: m.moves = max(0, m.moves-n)
                      (original does not null-check slots — implement as "for each non-null member")
```

---------------------------------------------------------------------------------------------------
## 1. Special-site table — 40 records × 28 bytes at DS:0x7ec6 [H]

| off | size | field |
|---|---|---|
| +0x00 | word | x |
| +0x02 | word | y |
| +0x04 | char[20] | name (NUL-terminated) |
| +0x18 | byte | **type / contents** (see below) |
| +0x19 | byte | item index 0..13 (meaningful when type==4; left stale afterwards) |
| +0x1a | byte | monster index 0..9 (0 = none). For type 8 it is the ally kind |
| +0x1b | byte | unused (always 0) |

The "explored" flag is **not in the record**: it is bit 0x8000 of the map tile at (x,y).
Save file: whole 0x460-byte block at byte 48756.

### 1.1 Type values
| value | meaning | where it occurs |
|---|---|---|
| 0 | empty / already looted (item taken or AI-explored) | ruins after exploration |
| 1 | Library | sites 3,4 (fixed) |
| 2 | Sage / Seer / Oracle | sites 1,7 (fixed) |
| 3 | Temple | sites 0,2,5,6 (fixed) |
| 4 | Ruin holding an item (+0x19) | randomised, 14 ruins |
| 5 | Ruin holding a Holy Altar | randomised |
| 6 | Ruin holding a Golden Throne | randomised |
| 7 | Ruin holding gold | randomised |
| 8 | Ruin holding allies (kind = +0x1a) | randomised |

Descriptive phrase per type (pointer table DS:0x7c82, used by the Sage "Locations" answer):
0 `""`, 1 `It is a truly magnificent collection of books!`, 2 `Ahhh grasshopper! A place to seek wisdom!`,
3 `Blessed is he who visits this place!`, 4 `An ancient artifact is there!`,
5 `An altar to an ancient God resides there`, 6 `A throne from days past sits there gleaming!`,
7 `I believe there is much gold there!`, 8 `Friendship is possible!`.

### 1.2 Static table (initial EXE data; types 1-3 fixed, all ruins 8..39 start as 4 and are re-rolled)
| # | name | x | y | initial type |
|---|---|---|---|---|
|  0 | Temple of Iris       |  22 |  66 | 3 |
|  1 | Seer of the River    |  45 |  30 | 2 |
|  2 | Temple of Emrik      |  72 |  57 | 3 |
|  3 | Golden Library       | 102 |   1 | 1 |
|  4 | Great Library        |  11 | 117 | 1 |
|  5 | Temple of Miridine   |  38 |  93 | 3 |
|  6 | Temple of Lurinth    |  74 | 147 | 3 |
|  7 | Grand Oracle         | 105 | 133 | 2 |
|  8 | Greyport Ruins       |  21 |  24 | 4 |
|  9 | Emperors' Crypt      |   7 |  34 | 4 |
| 10 | Harvest Stone        |  18 |  53 | 4 |
| 11 | Old Woods Tower      |  12 |  54 | 4 |
| 12 | Druids' Temple       |  29 |  24 | 4 |
| 13 | Ruins of Kabor       |  49 |  11 | 4 |
| 14 | Nirn's Crypt         |  44 |  57 | 4 |
| 15 | Nirn's Deep          |  45 |  71 | 4 |
| 16 | Mirk's Decay         |  55 |  36 | 4 |
| 17 | Wizard's Hearth      |  69 |  18 | 4 |
| 18 | Dragon Halls         |  68 |  66 | 4 |
| 19 | Bridgetower          |  76 |  41 | 4 |
| 20 | Crypt of Molok       |  92 |   6 | 4 |
| 21 | Halls of Chaos       | 100 |  62 | 4 |
| 22 | Dragontower Ruins    |  86 |  50 | 4 |
| 23 | Nev Dolar            |  93 |  68 | 4 |
| 24 | The Old Inn          |  16 |  99 | 4 |
| 25 | Throne of Horan      |  24 | 122 | 4 |
| 26 | Throne of Balnor     |  18 | 133 | 4 |
| 27 | Giant's Tomb         |  24 | 126 | 4 |
| 28 | Tower of Death       |  33 |  81 | 4 |
| 29 | Ruins of Haviel      |  42 | 118 | 4 |
| 30 | Dusk Stone           |  34 | 145 | 4 |
| 31 | Dawn Stone           |  37 | 145 | 4 |
| 32 | Gemhold              |  69 | 132 | 4 |
| 33 | Dark Barrows         |  66 | 102 | 4 |
| 34 | Dwarf Halls          |  57 |  81 | 4 |
| 35 | Guardian             |  77 | 121 | 4 |
| 36 | Tower of Night       | 100 | 109 | 4 |
| 37 | Crypt of Baal        |  87 | 125 | 4 |
| 38 | Tomb of Naar         |  82 | 117 | 4 |
| 39 | Monolyth             |  94 | 122 | 4 |

(Site names like "Throne of Horan" or "Druids' Temple" are just names; behaviour comes from the
type byte.) Initial +0x19/+0x1a/+0x1b are 0 for all.

### 1.3 Monsters (names: pointer table DS:0x242e; strengths: word table DS:0x2442) [H]
| idx | name | strength | ally army type if allies (template idx = idx-5) |
|---|---|---|---|
| 0 | "" (none) | 0 | – |
| 1 | Troll | 5 | – |
| 2 | Giant | 7 | – |
| 3 | Wolf | 4 | – |
| 4 | Goblin | 3 | – |
| 5 | Dragon | 8 | 12 Dragons |
| 6 | Demon | 8 | 13 Demons |
| 7 | Devil | 8 | 14 Devils |
| 8 | Wizard | 8 | 10 Wizard |
| 9 | Ghost | 7 | 11 Undead |

### 1.4 Game-start randomisation — FUN_2de9_0004 (called from FUN_1b90_0006 at new game) [H]
`used[40]` is a byte array in far segment image 0x306f (pointer DS:0x9388); its EXE initial value is
`[1]*8 + [0]*32`. **It is not cleared by this function** (a second new game in the same process would
loop forever; treat it as re-initialised to that value at every new game).
```
for s in 0..39: tile(site[s].x, site[s].y) &= ~0x8000            # clear explored flags

for i in 0..13:                                                   # place the 14 items
    do: s = dice(1,32,7)          # 8..39 (40 on rand()==32767: out of bounds in original)
    until used[s] == 0
    used[s] = 1
    item[i].state = 2 ; item[i].loc = s
    site[s].type = 4 ; site[s].item = i

for s in 8..39:                                                   # remaining 18 ruins
    if used[s] == 0:
        t = dice(1,6,4)           # 5..10
        site[s].type = min(t, 8)  # P: altar 1/6, throne 1/6, gold 1/6, allies 3/6
        site[s].item = 0
        used[s] = 1

for s in 0..7: site[s].monster = 0

for s in 8..39:                                                   # guardians / ally kinds
    if site[s].type == 8: site[s].monster = dice(1,5,4)   # 5..9 (Dragon..Ghost)
    else:                 site[s].monster = dice(1,9,0)   # 1..9 (any monster, incl. on item/altar/throne/gold)
    if site[s].type == 8 and s in (9,14,24,29) and site[s].monster in (5,8):
        site[s].monster += 1      # Dragon->Demon, Wizard->Ghost at those four sites
```
RNG call order is exactly as written (item loop with rejection, then types for ascending s, then monsters).

---------------------------------------------------------------------------------------------------
## 2. The Search command — FUN_307e_000c (key Z, menu " Search") [H]

```
search():
    A = CurrentArmy
    if A is NULL or A.moves < 1: return 0                    # nothing happens
    (x,y) = A.x, A.y
    cls = class(tile(x,y))
    site = None
    if cls == 11:
        idx = first s in 0..39 with site[s].x==x and site[s].y==y
        if none: cls = 7  else: site = site[idx]
    H = CurrentHero
    explored = tile(x,y) & 0x8000
    if H is NULL or explored:
        if cls==11 and site.type==3: temple(idx)              # any stack, no MP cost
        else:
            list_ground_items(x,y)    # items with state==1 at (x,y)
            if none: msg "You have found nothing!"
            else for each: msg "You have found: %s" (item name)   # display only, NOT picked up
            mp_deduct(0, 4)           # whole stack loses 4 MP
        return 1
    if cls != 11:                                             # hero on a non-site tile
        same ground-item listing as above, then mp_deduct(1, 4)  # hero loses 4 MP
        return 1
    # hero on an unexplored site
    if   site.type == 1: library()                            # section 6
    elif site.type == 2: sage(idx)                            # section 5
    elif site.type == 3: temple(idx)                          # section 4
    else:                search_ruin(site, x, y)              # section 3 (types 0,4,5,6,7,8)
    return 1
```
Consequences: only a stack containing a hero can explore ruins/sages/libraries; non-hero stacks only
"find nothing". Temples, sages and libraries never get the 0x8000 flag, so they can be revisited.

---------------------------------------------------------------------------------------------------
## 3. Searching a ruin — human player, FUN_307e_038b(site, x, y) [H]

```
search_ruin(site, x, y):
    mp_deduct(1, 20)                                          # hero loses 20 MP first (clamp 0)
    (UI only: redraw, sound FUN_12ab_0048(2))
    if site.type != 8:
        if site.monster == 0:
            msg "It appears to be uninhabited!"
        else:
            msg "%s encounters a %s!" (hero name, monster name)
            if ruin_fight_lost(site):                         # FUN_307e_07d6, below
                hero_dies(H, H.x, H.y)                        # FUN_2289_139e: drop items (section 7.5)
                delete_army(H)                                # FUN_2b32_0318
                msg "...and is slain by it!"
                return 1                                      # site unchanged, still unexplored
            msg "...and is victorious!"
            site.monster = 0
    switch site.type:
      case 4:  msg "%s has found the %s!" (hero, item name)
               tile(x,y) |= 0x8000
               site.type = 0                                  # site.item left as is (stale)
               it = item[site.item]
               it.state = 1 ; it.loc = 0 ; it.x = H.x ; it.y = H.y
               # The item is placed ON THE GROUND at the ruin; the hero must use Take (7.2).
      case 5:  open "Holy Altar" yes/no dialog  (FUN_1312_20d8(1)) -> section 4.2 on "Yes"
      case 6:  open "Golden Throne" yes/no dialog (FUN_1312_20d8(2)) -> section 4.3 on "Yes"
      case 7:  g = dice(3,1000,500)                           # 503..3500
               msg "%s has found %d gp!"
               tile(x,y) |= 0x8000 ; gold[player] += g        # site.type stays 7
      case 8:  tile(x,y) |= 0x8000                            # no fight for type 8
               r = dice(1,3,0); n = 2 if r == 3 else 1        # P(2)=1/3
               if n == 1: msg "A %s offers to join %s"       (monster name, hero name)
               else:      msg "%d %ss offer to join %s"      (n, monster name, hero name) e.g. "2 Dragons offer..."
               repeat n: create_ally(site.monster - 5, x, y)  # FUN_307e_1320, 3.2
               # site.type stays 8, site.monster stays (it is the ally kind)
      case 0 / other: nothing (no explored flag set!)
    return 1
```
Altar/throne: the monster (if any) is fought and cleared **before** the dialog. If the player answers
"No", nothing is flagged: the ruin can be searched again later (another 20 MP, no monster).

### 3.1 Ruin fight — FUN_307e_07d6(site) → returns 1 if the hero dies [H]
```
battle_bonus = sum(item.value for item carried by H if item.btype == 1)    # Bat+ items only
n = number of army records (any owner, any type, including H itself) with (x,y) == (H.x,H.y)
roll = dice(1,100,0)
T = (H.strength - monster_strength[site.monster] + battle_bonus) * 5 + n*3 + 90
hero_dies = roll > T
```
Example: hero str 5 alone vs Troll(5): T=93 → 7% death; vs Dragon(8): T=78 → 22%; with a stack of
8: +21. Command (btype 2) items do not help. Hero strength is the raw `+8` value (no cap here).

### 3.2 Ally creation — FUN_307e_1320(tmpl, x, y) [H]
Ally templates: 24-byte records in far segment image 0x307b (DS:0x939e), file offset 0x337b0:
| tmpl | from monster | army type | max moves (+6) | moves (+7) | strength (+8) | hp (+0xc) | upkeep (+0x10) |
|---|---|---|---|---|---|---|---|
| 0 | 5 Dragon | 12 Dragons | 18 | 18 | 8 | 1 | 4 |
| 1 | 6 Demon  | 13 Demons  | 14 | 14 | 7 | 1 | 4 |
| 2 | 7 Devil  | 14 Devils  | 12 | 12 | 8 | 1 | 4 |
| 3 | 8 Wizard | 10 Wizard  | 50 | 50 | 6 | 1 | 6 |
| 4 | 9 Ghost  | 11 Undead  | 12 | 12 | 7 | 1 | 1 |
```
create_ally(t, x0, y0):
    cx, cy = x0, y0 ; tries = 10
    loop:
        cnt = count of army records at (cx,cy)                  # FUN_2b32_0008 (no owner check)
        if (cx,cy) == (x0,y0): cnt += 1                         # the ruin tile counts one extra
        if cnt < 8 and (tile_owner(cx,cy) == player or cnt == 0): break   # place here
        cx += dice(1,3,-2) ; cy += dice(1,3,-2)                 # random walk -1..+1 (x roll first)
        tries -= 1
        if tries == 0: return NULL                              # ally lost (10 positions tested)
    a = alloc_army()      # first record with owner==0xFF; count=max(count,idx+1); owner=player,
                          # flags=0x0001, +0x14=+0x16=-1
    a.x,a.y = cx,cy ; a.type = T.type ; a.owner = player
    a.maxmoves,a.moves,a.strength = T[+6],T[+7],T[+8]
    a[+9]=0 ; a[+0xa]=0 ; a.hp=1 ; a[+0xe]=0 ; a.upkeep=T[+0x10]
    upkeep_total[player] += a.upkeep                           # DS:0x20be
    tile(cx,cy).owner = player ; tile(cx,cy) |= 0x0800
```
No terrain / bounds check is performed (faithful). Allies arrive with full movement.

---------------------------------------------------------------------------------------------------
## 4. Temples, Holy Altar, Golden Throne

### 4.1 Temple — FUN_307e_0ad5(site_index) [H]
Reached by Search on a type-3 site by **any** stack (hero not required, explored flag irrelevant).
No MP cost (but Search requires CurrentArmy.moves >= 1).
```
msg "You have found a temple..."
bit = {0:0x02, 2:0x04, 5:0x08, 6:0x10}.get(site_index)      # only these four temples exist
members = group slots 0..7 (non-null) if group mode else [CurrentArmy]
count = 0
for a in members:
    if bit and not (a.flags & bit):
        a.strength += 1 ; a.flags |= bit ; count += 1
    if a.strength > 9: a.strength = 9         # applied to every member; a str-9 army is still "blessed"
if count == 0: msg "You have already received our blessing! Try another temple!"
elif count == 1: msg "You have been blessed!  Seek more blessings in far temples!"
else: msg "%d Armies have been blessed!  Seek more blessings in far temples!" (count)
```
Every army type (not only heroes) can be blessed once per temple: max +4 total, cap 9.

### 4.2 Holy Altar ("You have found a Holy Altar / Will you pray at this Altar?", Yes = cmd 13) — FUN_307e_0911 [H]
```
r = dice(1,2,-1)                               # 0 or 1  (2 on rand()==32767)
if r == 1 and H.strength < 9:
    H.strength += 1 ; msg "The Gods hear! %s's strength increases to %d!"
else:
    msg "The Gods ignore %s!"
tile(H.x,H.y) |= 0x8000                        # either way; site.type stays 5
```
"No" (cmd 14) just closes; nothing flagged.

### 4.3 Golden Throne ("You have found a huge / Golden Throne / Will you sit in the throne?", Yes = cmd 15) — FUN_307e_09d4 [H]
```
roll = dice(1,100,0)
d = +1 if roll < 80 else -1                     # +1 with 79%, -1 with 21% (rolls 80..100)
if (H.strength == 9 and d == +1) or (H.strength == 0 and d == -1):
    msg "You see a vision of yourself as Warlord of all Illuria!"     # no change
else:
    H.strength += d
    msg "%s's strength %s to %d!"  (hero, "increases" if d==+1 else "decreases", new strength)
tile(H.x,H.y) |= 0x8000                        # site.type stays 6
```
"No" (cmd 16) closes; nothing flagged.

### 4.4 Sage gem — inside FUN_307e_000c [H]
On every hero visit to a type-2 site (no explored flag is ever set there):
```
if (idx == 1 and DS:0x2478 == 0) or (idx == 7 and DS:0x247a == 0):
    set that flag = 1                      # global: only the first visitor of each sage, any player
    g = dice(3,1000,500)
    msg "You are greeted warmly..." ; msg "... the Seer gives you a gem..." ; msg "...worth %d gp" (g)
    gold[player] += g
open Sage dialog (FUN_1312_20d8(3))          # section 5
```

---------------------------------------------------------------------------------------------------
## 5. Sage dialog ("A sign says / The Great Sage / Master of Wisdom, / Information on: / Magical Items /
and Locations / The sage welcomes you / What do you wish to know?") [H]

Buttons (dialog def DS:0xff2): cmd 8 `Cancel`, cmd 9 `Items`, cmd 10 `Locations`.
- Items (FUN_307e_0f6b): selection list of all 14 item names; choice → FUN_307e_10c8(item).
- Locations (FUN_307e_0f34): list of all 40 site names; choice → FUN_307e_0fa2(site).
(dispatch FUN_2e03_038c on DS:0xb32c = 1 / 2). Each answered question costs the hero 4 MP
(`mp_deduct(1,4)` at the end of both functions). One question per Search.

### 5.1 Item query — FUN_307e_10c8(i) [H]
```
msg "The %s can be found ..." (item name)
switch item[i].state:
  0: (sprintf "... no more in the lands of Illuria!" but the original NEVER displays it — bug)
  2: s = first site index 0..39 with site[s].item == i         # NB: searches the stale +0x19 bytes,
     msg "... at %s!" (site name)                              #   e.g. item 0 in a ruin -> "Temple of Iris"
  1 or 3:
     (px,py) = (item.x,item.y) if state==1 else position of army[item.loc]
     best = 10000 ; c* = -1
     for c in 79 down to 0: d = dist(px,py, city[c].x, city[c].y); if d < best: best=d; c*=c
     own = city[c*].owner ; if own == 15: own = 8
     state 1: msg "... in the vicinity of the %s city of %s"  (clan[own], city name)
     state 3: msg "... near %s with a hero of the %s"         (city name, clan[army[item.loc].owner])
  other: msg "What???"
mp_deduct(1,4)
```
`clan[]` = DS:0x7eac: Sirians, Storm Giants, Grey Dwarves, Orcs of Kor, Elvallie, Selentines,
Horse Lords, Lord Bane, Neutral. Ties in nearest city resolve to the highest city index.

### 5.2 Location query — FUN_307e_0fa2(s) [H]
```
if site[s].monster == 0:                 msg "Nothing evil lives here!"
elif not (tile(site[s]) & 0x8000):       msg "It is inhabited by a %s!" (monster name)
else:                                    msg "It has already been explored!"
msg phrase[site[s].type]                 # table 1.1 (type 0 gives an empty message)
if site[s].type == 4: msg "The %s!" (item name)
mp_deduct(1,4)
```

---------------------------------------------------------------------------------------------------
## 6. Library — FUN_307e_0ce0 [H]
Hero searching an (always unexplored) type-1 site. Repeatable.
```
msg "You enter a great Library..." ; msg "Searching through the books, you find..."
r = dice(1,3,0)
if r == 1:  msg quote[dice(1,12,-1)]
elif r == 2:
    i = dice(1,14,-1)
    state 0: "The %s is lost from Illuria!"
    state 1: "The %s is lying in %s!"  (item, region[ ((2*cursor_y)//156)*4 + (4*cursor_x)//109 ])
             # BUG (faithful): uses the MAP CURSOR (DS:0xaf00/0xaf04), not the item position.
             # The cursor sits on the searching hero, i.e. the library itself:
             # Golden Library -> "Argundor", Great Library -> "Western Sulador".  [M]
    state 2: "The %s is in the %s!"    (item, site[item.loc].name)     # correct index here
    state 3: "The %s is owned by a hero!"
elif r == 3:
    s = dice(1,32,7)                           # ruins 8..39 only
    if site[s].monster == 0: "%s is uninhabited!" (site name)
    else: "A %s lives in %s!" (monster name, site name)   # reports ally kind for type 8, and
                                                          # AI-explored ruins still show their monster
(r == 4 on rand()==32767: no message)
mp_deduct(1,4)
```
Regions (DS:0x68a4, index row*4+col): 0 Western Lauredor, 1 Central Lauredor, 2 Eastern Lauredor,
3 Argundor, 4 Western Sulador, 5 Central Sulador, 6 Eastern Sulador, 7 Huinedor.

Quotes (DS:0x781a, index 0..11):
0 `Never leave Lord Bane behind you! - Great Orc` · 1 `Real power is power over life and death! - Greenbow` ·
2 `Never give a Sirian an even break!` · 3 `The pen is mightier than the Dwarf! - Lord Biros` ·
4 `Elves do very nasty things to small animals!` · 5 `Never play leapfrog with a Unicorn!` ·
6 `A mouse with one hole is soon eaten! - Baron de Chat` · 7 `My kingdom for an Orc! - Richard 111th` ·
8 `War has no rules!` · 9 `War is the natural extension of nature!` ·
10 `You can never have enough money! - Eldros` · 11 `For great computer games, go to SSG! - Don Stephano`

---------------------------------------------------------------------------------------------------
## 7. Items — 14 records × 30 bytes at DS:0x217e [H]

| off | size | field |
|---|---|---|
| +0x00 | char[20] | name |
| +0x14 | byte | bonus type: **1 = battle ("Bat +")**, **2 = command ("Com +")** |
| +0x15 | signed byte | bonus value |
| +0x16 | byte | state: 0 lost (never set in play), 1 lying on the ground, 2 in a ruin, 3 carried |
| +0x17 | byte | pad (0) |
| +0x18 | word | loc: site index (state 2), army index of carrier (state 3), 0 otherwise |
| +0x1a | word | x (where it lies / where a human hero found it) |
| +0x1c | word | y |
Save file: 420 bytes at byte 50084.

### 7.1 Item table (EXE data)
| # | name | type | value |
|---|---|---|---|
| 0 | Firesword | 1 Bat | +1 |
| 1 | Icesword | 1 Bat | +1 |
| 2 | Lightsword | 1 Bat | +2 |
| 3 | Darksword | 1 Bat | +2 |
| 4 | Staff of Might | 1 Bat | +3 |
| 5 | Crown of Loriel | 2 Com | +1 |
| 6 | Sceptre of Loriel | 2 Com | +1 |
| 7 | Orb of Loriel | 2 Com | +1 |
| 8 | Ring of Power | 2 Com | +2 |
| 9 | Staff of Ruling | 2 Com | +3 |
| 10 | Spear of Ank | 1 Bat | +1 |
| 11 | Bow of Eldros | 1 Bat | +2 |
| 12 | Horn of Ages | 2 Com | +2 |
| 13 | Crimson Banner | 2 Com | +1 |
No movement or income bonuses exist. Initial placement: section 1.4 (all 14 in distinct random ruins).

### 7.2 Take (key T, FUN_2cad_06bc / FUN_2cad_0734) [H]
Requires CurrentArmy and CurrentHero ("Hero must be selected to take an item"). Shows the list of
items with state 1 at (H.x,H.y) ("Taking an item ..."); the chosen one becomes
`state=3, loc=index of H in the army array` (x,y untouched). One item per command, no MP cost,
**no limit on items per hero**.

### 7.3 Drop (key D, FUN_2cad_07c0 / FUN_2cad_0832) [H]
Requires a hero; lists the hero's items; chosen item → `state=1, loc=0, x=H.x, y=H.y`. No MP cost.

### 7.4 Inventory (key I, FUN_2cad_087e)
Lists the hero's items (state 3 and loc == hero's army index; list builder FUN_2e03_0000 mode 2).

### 7.5 Hero death — FUN_2289_139e(hero, x, y) [H]
Called for ruin deaths and battle deaths. `hero_name_used[hero.name] = 0`, hero counter DS:0xb8c4 -= 1,
every item carried → `state=1, loc=0, x, y` (dropped on the given tile).

### 7.6 How bonuses act (combat, FUN_23cd_000c / FUN_23cd_0bdc) [M]
- Battle items: added to the carrying hero's own combat strength, and to the hero value used for the
  stack's hero-leadership bonus (`max over heroes of min(9, str + battle_bonus)` → table lookup).
- Command items: values of all command items of all heroes in the stack are summed and added to every
  unit of the stack. Final unit strength capped at 9.
- Ruin fights use battle items only (3.1).
(Exact combat composition belongs to the combat spec.)

### 7.7 AI item handling (for completeness) [M]
- FUN_1d88_166e: items lying on a tile are given (state 3) to a hero of the moving AI on that tile.
- FUN_1d88_03a9: an AI hero in a city picks up items lying on the 4 city tiles and, if it holds more
  than 2 items, passes items to other heroes on the same tile that hold <= 1.

---------------------------------------------------------------------------------------------------
## 8. AI exploration — FUN_1d88_1803 (different rules!) [H]
Used when an AI hero reaches its target site (via FUN_3257_04c6). AI targets (FUN_1d88_12d6) are sites
whose tile is unexplored, type not 1 or 3, and not a sage whose gem flag is set.
```
ai_search():
    if CurrentArmy NULL or H NULL: return 0
    s = site at (H.x,H.y) else return 0 ; if tile explored: return 0
    t = site.type
    if t != 8 and t != 2:
        if ruin_fight_lost(site):      # same formula 3.1, EVEN IF site.monster == 0 (strength 0)
            hero_dies(H,H.x,H.y); delete_army(H); return 0
        # NOTE: monster is NOT cleared
    if t != 2: tile |= 0x8000 ; site.type = 0
    switch t:
      2: g = dice(3,1000,800); set flag 0x2478 (s==1) / 0x247a (s==7); gold += g   (no flag check here)
      4: item.state = 3 ; item.loc = index of H    # goes straight to the hero; item x,y NOT updated
      5: r = dice(1,2,-1); if H.str + r > 9: H.str = 9 else: H.str += dice(1,2,-1)   # 2nd roll!
      6: r = dice(1,3,-2); if H.str + r > 9: H.str = 9 else: H.str += dice(1,3,-2)   # 2nd roll!
         H.str = max(H.str, 1)
      7: gold += dice(3,1000,500)
      8: n = 2 if dice(1,3,0)==3 else 1
         repeat n: a = create_ally(site.monster-5, H.x, H.y)
                   if a: a[+0x14] = -1 ; flyer = (movetype[a.type] (DS:0x4376 word) == 5)
                         if FUN_27ed_144c(player, 0, flyer, a.x, a.y, &dest): a.flags |= 0x80 ; a[+0x14] = dest
    H.moves = 0 ; H[+0x14] = -1
    return 1
```
No messages, no 20-MP cost (moves set to 0 instead).

---------------------------------------------------------------------------------------------------
## 9. Reports

### 9.1 "Ruins" report = "Status of special locations" (menu " Ruins", key J) — FUN_200c_22b6 [H]
Draws the strategic map and a 6×3 marker at pixel (2x+2, y+2) for each site, s = 39..0:
```
k = 4 if type==3 (temple) ; 7 if type==1 (library)
    3 if (type==2 and gem flag of that sage set) or (type not 1/2/3 and tile explored)
    0 otherwise (unexplored ruin / sage with gem)
sprite x = word DS:0x247e[k] (0:112 unexplored, 3:121 explored, 4:124 temple, 7:133 library), sprite y = DS:0x247c (392)
```
then message "Status of special locations".

### 9.2 "Heroes" report (menu " Heroes", key K) — FUN_200c_1492 + FUN_200c_1a7a [M]
List: up to 12 heroes of the current player (scan army index descending). Order: first the hero with
the smallest `2*y + x`, then repeatedly the nearest remaining hero (dist, strict <, scanning slots
11..0). None → "You have no heroes!" map (FUN_1224_0004 / FUN_2c6f_0210 "Your heroes...").
Per-hero page: name; "  In" (tile class 10 = city) or "Near" + nearest city (79..0, strict <);
strength (+8); moves left (+7); total Bat+ of carried items; total Com+; up to 7 other own armies on
the same tile; scrollable item list showing name and "Com +"/"Bat +" value (FUN_200c_1fd2).
Hero markers on the map use sprite DS:0x2484, the selected hero DS:0x247e.

### 9.3 Info on a site tile (FUN_2d3c_05f8): graphic 11 → "Library"/"Sage"/"Healers"(temple);
ruin graphics → "Unexplored"/"Explored" (tile bit 0x8000); plus the region of the cursor.

---------------------------------------------------------------------------------------------------
## 10. Validation against War1.sav [H]
Save layout (from save writer FUN_109f_07b4): sites @48756 (0x460), upkeep 0x20be @49876, 0x20ce @49892,
0x20ae @49908, players 0x20de @49924 (8×20, gold at +2), items @50084 (0x1a4), 0x6cc0 @50504 (0x640),
..., hero names 0xcc88 @52154 (0x320), name-used 0x65be @52954 (40), ..., 0x2478 @53170, 0x247a @53172,
total 53330 = file size.
Checks (all consistent with this spec):
- Types 1/2/3 at sites 0..7 unchanged; ruins hold only types 0,4,5,8; ally sites (8,28,35,37,39) have
  monsters 5..9; others 1..9.
- Items in ruins (state 2): Icesword@15, Darksword@17, Staff of Might@20, Crown@38, Horn@33 — each
  site has type 4 and matching +0x19; their tiles are unexplored.
- Human-found items (x,y = ruin coords, later taken → state 3): Sceptre (7,34)=site 9, Ring (12,54)=11,
  Staff of Ruling (68,66)=18, Spear (18,53)=10, Banner (29,24)=12 — those sites have type 0, monster 0,
  tile explored.
- AI-found items (state 3 with x=y=0): Firesword (site 13), Lightsword (23), Orb (24), Bow (32) — those
  sites have type 0 but monster still set (AI does not clear it). Other type-0 explored ruins with a
  monster (16,19,21,22,25,26,27,29,30,31,36) are AI-explored altar/throne/gold/ally ruins.
- Explored type-8 ruins (8, 28) keep type 8 + monster (human ally recruit); explored type-5 ruin 14 =
  human altar prayed (type kept, monster cleared). Unexplored: 15,17,20,33,34,35,37,38,39.
- Hero army 170 has flags 0x05 (blessed at Temple of Emrik, bit 0x04); army 296 has 0x43 (Temple of Iris).

---------------------------------------------------------------------------------------------------
## 11. Function index (evidence)
| function | role |
|---|---|
| FUN_2de9_0004 | game-start site/item randomisation |
| FUN_307e_000c | Search command dispatcher |
| FUN_307e_038b | human ruin search |
| FUN_307e_07d6 | ruin fight (returns hero died) |
| FUN_307e_0911 / 09d4 | altar / throne effect (Yes buttons cmd 13 / 15 in FUN_1312_11e0) |
| FUN_307e_0ad5 | temple blessing |
| FUN_307e_0ce0 | library |
| FUN_307e_0f34 / 0f6b | sage Locations / Items list setup |
| FUN_307e_0fa2 / 10c8 | sage location / item answers |
| FUN_307e_1320 | ally army creation (templates far seg 0x307b) |
| FUN_307e_153b | movement point deduction |
| FUN_1312_20d8 | modal dialog opener (1 altar, 2 throne, 3 sage, 5 item list) |
| FUN_2e03_0000 | list builder (mode 2 hero items, 3 ground items at x,y, 4 all sites, 5 all items) |
| FUN_2cad_06bc/0734, 07c0/0832, 087e | Take / Drop / Inventory |
| FUN_2289_139e | hero death: drop items |
| FUN_1d88_1803, 12d6, 166e, 03a9, 1751 | AI exploration, AI target choice, AI item pickup/sharing |
| FUN_200c_22b6, 1492, 1a7a, 1fd2 | Ruins report, Heroes report |
| FUN_23cd_000c / 0bdc | combat strength incl. item bonuses |

## 12. Open points / caveats
- DS:0xaf00/0xaf04 identified as map cursor from usage (cursor movement code, save/restore, viewport
  derivation) — library "lying in" region therefore = searcher's region [M].
- dice() edge case rand()==32767 returns sides+1 per die (affects dice(1,32,7)=40 out of range etc.);
  reproduce only if bit-exactness with the original RNG stream is required.
- Search does not consume RNG except inside the documented dice() calls; UI calls in between
  (FUN_1b90_0970, FUN_12ab_0048, redraws) were checked not to call rand() on the paths shown [M].
- Hero initial strength appears to be 5 (hero creation in seg 2cad sets +8 = 5) [M] — heroes spec.
