# Warlords (DOS v2.10) — Army records, movement, path finding and map rules

Implementation-ready spec, reverse-engineered from the Ghidra output `/home/claude/gh/d3.c` with
disassembly checks (`gdis()` in `/home/claude/re/wl.py`). Addresses are Ghidra `SEG:OFF` (image
segment + 0x1000). `DS:x` means DGROUP offset x. Words are little-endian 16-bit. "signed char" means
the field is read with `cbw/cwde`.

Confidence tags: **[H]** verified in disassembly or against the save file, **[M]** read from the
decompiler only and plausible, **[L]** inferred or guessed.

> Warning: `/home/claude/gh/funcs_index.txt` line numbers do not match `d3.c`, so function names you get
> from it are off by one function. Rebuild the index from the `// ==== ` lines of `d3.c`.

---------------------------------------------------------------------------------------------------

## 0. Global state used by movement

| DS addr | type | meaning | conf |
|---|---|---|---|
| 0x7ea6 | int | current player 0..7 | H |
| 0xacc8 | int | number of army slots in use (high-water mark, ≤ 2000). Loops go `for i = acc8-1 .. 0` | H |
| 0xb2e2/0xb2e4 | far ptr | **current army** (offset = index·24, segment 0x48f4). NULL means nothing is selected | H |
| 0xb2ba[8] | far ptr ×8 (= DS:-0x4d46) | **group members** (the selected stack) | H |
| 0x377c | int | **group mode**: 0 = only the current army moves, 1 = all of b2ba moves | H |
| 0xad5e | int | number of non-null entries in b2ba (set by 1cdf_07b2) | H |
| 0xb716 | int | **group movement points** (set by 1cdf_07b2, decreased per step) | H |
| 0xcfa8[12] | int (= DS:-0x3058) | **group terrain cost table** per terrain class (set by 1cdf_07b2) | H |
| 0xb2b6/0xb2b8 | far ptr | hero in the selection (set by 1c8b_049c), or NULL | H |
| 0xb6d4 | int | turn number (1 = first turn) | M |
| 0xaf00/0xaf04 | int | map cursor x,y (tile) | M |
| 0xb712,0xad60,0xb6f6,0xd1ca | int | viewport left, top, right(=left+8), bottom(=top+7) (9×8 tiles of 40×20 px) | H |

The save file stores b2e2(2 bytes, offset only), b716, cfa8(24 bytes) and ad5e, so the selection
survives a save and load (see FUN_109f_01a5).

---------------------------------------------------------------------------------------------------

## 1. Army record (24 bytes, 2000 slots, segment 0x48f4 offset 0)

| off | size | field | notes / evidence | conf |
|---|---|---|---|---|
| +0x00 | int16 | **x** (0..108); −1 means not on the map | free slots and armies being vectored have x = y = −1 | H |
| +0x02 | int16 | **y** (0..155); −1 means not on the map | | H |
| +0x04 | int8 | **type** 0..15 (15 = Hero); 0xff when the slot is free | army names at DS:0x44f2 | H |
| +0x05 | int8 | **owner** 0..7; **0xff = free slot** (the allocator FUN_2b32_027c looks for +5 == −1) | | H |
| +0x06 | int8 | **max moves** (base movement allowance) | set at creation only. From city: `city+0x38[type]`. Hero: 16, or 12 for the first-turn hero. Allies come from the template table at seg 0x407b (Ghidra) / image 0x307b | H |
| +0x07 | signed char | **moves left** (current MP) | | H |
| +0x08 | int8 | **strength** 0..9 | from city `+0x2e[type]`; hero 5; +1 per temple blessing, capped at 9 | H |
| +0x09 | int8 | **home city index** (0..79) | hero: the city it appeared in; allies: 0 | H |
| +0x0a | int16 | serial number: the n-th unit of this type built in the home city (counter at DS:0x6cc0[city·10+type]). **For heroes: hero name index** (name = DS:0xcc88 + 20·idx, 40 names) | H |
| +0x0c | int8 | **hits**: 1 = "Good", 0 = "Poor" (shown via table DS:0x68b4). Set to 1 at creation; lowered in battle (FUN_2289_067a); the unit dies below 0 | H (display) / M |
| +0x0d | — | pad (always 0) | save | H |
| +0x0e | int16 | unknown. Set to 0 at creation, 0 in every save record, no reads found | L |
| +0x10 | int8 | **upkeep** (gp per turn) = city cost[type]/2; hero 0. Added to and subtracted from DS:0x20be[owner] | H |
| +0x11 | — | pad | | H |
| +0x12 | uint16 | **flags** (see below) | | H/M |
| +0x14 | int16 | **goal / vector destination**. Land unit being vectored: destination city index. AI: goal (<80 city index, 100..199 = site index+100, ≥200 = item index+200). −1 = none | H (vector), M (AI) |
| +0x16 | int16 | **vector state**: 100 = just produced (in transit), 101 = arrives at the next turn start. AI: other values (city index). −1 = none | H |

Flags word at +0x12 (bit = value in the 16-bit word):

| bit | meaning | set / cleared by | conf |
|---|---|---|---|
| 0x0001 | **active** (not sentried). Only active armies are picked by "next army" | set on creation and on every selection (1c8b_049c); cleared by the Defend/sentry command (code at 1c8b:00d6, which Ghidra did not split into a function) | H |
| 0x0002 | blessed at Temple of Iris (site 0) | 307e_0ad5 | H |
| 0x0004 | blessed at Temple of Emrik (site 2) | 307e_0ad5 | H |
| 0x0008 | blessed at Temple of Miridine (site 5) | 307e_0ad5 | H |
| 0x0010 | blessed at Temple of Lurinth (site 6) | 307e_0ad5 | H |
| 0x0020 | AI internal | 27ed_0a3e, 2c5c_000c | M |
| 0x0040 | **done for this turn**: skipped by "next army" | set when a move fails for lack of MP or MP reaches 0 (1c8b_043a), and by Skip (1c8b:00c8). Cleared for all own armies at turn start (1a12_0000, 1c8b_0004) | H |
| 0x0080 | AI flag (set on turn 1 for some units) | 1d88_000c | M |
| 0x0200 | already visited in the current "next army" cycle | set on the whole stack by 1c8b_02c0; cleared at turn start (1c8b_0004) and when a cycle ends | H |
| 0x0800 | AI (hero) flag | 1d88_* | M |

There is no fortify flag, and no field for stack or group membership: a stack is simply all armies on
the same tile. Hero items are not stored in the army record. The item table (14 records × 30 bytes
at DS:0x217e) has: `+0x14 kind, +0x15 bonus, +0x16 status (0 = not in play/in ruin, 1 = lying at
(+0x1a,+0x1c), 3 = carried by the army whose index is in +0x18)`. No item changes movement.

**Allocation.** FUN_2b32_027c finds the first slot with +5 == 0xff and sets `acc8 = max(acc8, i+1)`,
`+5 = current player`, `+0x12 = 0x0001`, `+0x14 = +0x16 = −1`.
**Deletion.** FUN_2b32_0318: `upkeep[owner] -= +0x10`; `type = owner = 0xff`; `x = y = −1`;
`+0x14 = +0x16 = −1`; `+7 = 0`. The count acc8 never shrinks.

### Save-file check (War1.sav: name "yoyo1a", version 2000, count 527)
Decoded by `/tmp/claude-0/.../scratchpad/sav.py`, which is easy to recreate:
```
idx   x   y type        own mx  mv str home  ser hp up flags  f14  f16
  0   8 122 Giant ( 0)  1 12  14   6   61    2  0   2 0x0001   -1   -1
  1  41 124 Hero  (15)  1 12  14   6   61    1  1   0 0x0001   -1   -1   <- first-turn hero: max 12; str 6 = blessed once
  4  84   4 Heavy ( 1)  7  8  10   5    9    7  1   2 0x0001   -1   -1
  9  38  99 Cav   ( 4)  1 16  10   6   47    2  1   5 0x0041   59   47   <- 0x40 = done; AI goal
 10   7  94 Hero  (15)  1 16  18   5   55   16  1   0 0x0001   -1   -1   <- normal hero: max 16
 12  62 143 Peg   ( 8)  0 16  18   4   65    1  1   8 0x0001   -1   -1
 17  64 121 Heavy ( 1)  3  8   4   5   53   17  1   2 0x0041   62   71   <- moved this turn (4 of 8 left)
 19  19 108 Giant ( 0)  4 12  12   6   61   22  1   2 0x0001   -1   -1
 20  -1  -1 Heavy ( 1)  0  8   8   5   43   10  1   2 0x0001   60  100   <- vectored to city 60, in transit
 29  60  30 Light ( 2)  2 10  10   3   14    8  1   2 0x0001   -1   -1
 31   8 130 Dwarf ( 3)  4  9  11   5   74    1  1   2 0x0001   -1   -1
 37  48  89 Hero  (15)  2 16  18   5   50   13  1   0 0x0001   -1   -1
```
Statistics over all 527 records: 470 on the map, 42 free (owner 0xff), 15 in transit (10 with
f16 = 100, 5 with f16 = 101). For 383 records `mv − mx = 2`, which is the turn-start rule
`mv = min(mv,2) + mx` applied to an unmoved army. Every on-map army stands on a tile with map bit 0x800,
and the tile's owner bits equal the army owner in 100% of cases. Bytes +0x0d, +0x11 and +0x0e are
always 0.

---------------------------------------------------------------------------------------------------

## 2. Terrain, costs and constants

Terrain class of a tile = `CLASS[w & 0x7f]` (DS:0x3934, 128 words) [H]:

| tile index | class |
|---|---|
| 0 | 7 Plain |
| 1..9 | 9 Tower (1 = unowned/original tower graphic, 2+p = tower of player p) |
| 10, 12 | 11 Ruins (two ruin graphics; 12 is also used for razed cities and razed towers) |
| 11 | 11 Ruins (special site graphic: temple, library, seer) |
| 13 | 8 Marsh |
| 14..28 | 0 Road |
| 29..35, 37..41 | 3 Shore (coastal **water**) |
| 36, 42 | 2 Water |
| 43..56 | 4 Forest |
| 57..70 | 5 Hill |
| 71..85 | 6 Mountain |
| 86..121 | 10 City (9 sets × 4 tiles) |
| 122..125 | 1 Bridge |
| 126, 127 | 0xffff (unused) |

Movement cost `COST[type][class]` = word at DS:0x37b4 + type·24 + class·2; **66 = impassable** [H]:

```
        Road Brdg Watr Shor Frst Hill Mtn  Plain Mrsh Towr City Ruin
Giant      1    1   66   66    5    4   66     2    5    2    1    2
Heavy      1    1   66   66    4    6   66     2    5    2    1    2
Light      1    1   66   66    4    6   66     2    5    2    1    2
Dwarf      1    1   66   66    6    3   66     2    6    2    1    2
Cavalry    1    1   66   66    5    6   66     2    5    2    1    2
Navy      66    2    1    2   66   66   66    66   66   66   66   66
Elves      1    1   66   66    2    5   66     2    6    2    1    2
Wolf       1    1   66   66    4    6   66     2    4    2    1    2
Pegasi     1    1    2    2    2    2    3     2    2    2    1    2
Griffins   1    1    2    2    2    2    3     2    2    2    1    2
Wizard     1    1   66   66    4    6   66     2    5    2    1    2
Undead     1    1   66   66    4    5   66     2    4    2    1    2
Dragons    1    1    2    2    2    2    3     2    2    2    1    2
Demons     1    1   66   66    4    5   66     2    5    2    1    2
Devils     1    1   66   66    4    5   66     2    5    2    1    2
Hero       1    1   66   66    4    6   66     2    5    2    1    2
```
The cost depends only on the class of the **destination** tile. There is **no diagonal surcharge**:
all 8 directions cost the same [H]. Roads and bridges cost 1. A navy may pass a bridge tile (cost 2).

Direction index (tables DS:0x32aa/0x32ba, 0x858e/0x857c, 0x85b2/0x85a0, 0x85d6/0x85c4) [H]:
```
d : 0  1  2  3  4  5  6  7   (8 = centre, only in the 9-entry tables)
dx: 0 +1 +1 +1  0 -1 -1 -1   0
dy:-1 -1  0 +1 +1 +1  0 -1   0        0=N 1=NE 2=E 3=SE 4=S 5=SW 6=W 7=NW
```
City tile i (TL, TR, BL, BR) = (cx + [0,1,0,1][i], cy + [0,0,1,1][i]) (DS:0x3dce/0x3dd6, also
0x4356/0x435e) [H].

Base unit stats are **per city** (city record +0x2e strength[10], +0x38 moves[10], +0x42 cost[10]).
Values in the shipped map: Giant 10/12 mv, Heavy 8 (7..10), Light 10 (9..12), Dwarves 9,
Cavalry 16 (13..20), Navy 18 (15..20), Elves 12, Wolves 14 (15), Pegasi 16 (15), Griffins 16 (18).
Ally template table (image segment 0x307b; slot = ruin reward type − 5): Dragons mv 18/str 8/upkeep 4,
Demons 14/7/4, Devils 12/8/4, Wizard 50/6/6, Undead 12/7/1 [H for the data, M for the 0x307b → ally
mapping].

---------------------------------------------------------------------------------------------------

## 3. Selection and group formation

* **Click on own stack** (FUN_2b32_036a): a second click on the same tile within a time threshold
  (DS:0x451a[min(speed,5)]), or Alt held (`_bios_keybrd(2) & 8`), or a call with param≠0, gives
  "group" = 1. Then b2ba = all own armies on the tile (at most 8, scanned from index acc8−1
  down), current army = the member with the highest `PRIO[type]` (DS:0x32ea =
  `[4,1,0,3,6,15,2,5,7,8,10,9,13,12,11,14]`, ties go to the first found), 1cdf_07b2 runs, and
  1c8b_049c(1) sets group mode. Without "group" and with an army already selected, the click cycles
  the current army through the stack and stays in single mode. [H]
* **Next army** (1c8b_0076 → 1c8b_013e → 1c8b_02c0): picks the nearest (Manhattan distance from the
  last position DS:0x37ae/0x37b0; distance 0 is treated as 9000) own army with x≠−1, flag 0x01 set
  and 0x40 clear. Armies with 0x200 clear are preferred. It then selects that army's **whole stack**
  in group mode and sets 0x200 on all of them. [H]
* **Stack dialog** (2b32_0f76): the player picks a subset of the stack, which becomes b2ba
  (1cdf_07b2 runs if the subset has more than one army).
* 1c8b_049c(g): `group_mode = g` unless b2ba[1] is NULL (a 1-army group is always single mode).
  Sets flag 0x01 on all selected armies and remembers a hero (b2b6). [H]

**FUN_1cdf_07b2, group movement values** [H]:
```
ad5e = 0; gmp = 100; allHeroes = True; hasNavy = False; navyMin = 20
for m in b2ba (non-null):
    ad5e += 1
    gmp = min(gmp, m.mv)                       # signed char compare
    if m.type != 15: allHeroes = False
    if m.type == 5:  hasNavy = True; navyMin = min(navyMin, m.mv)
if hasNavy:
    gmp = navyMin                              # note: capped at 20
    GCOST[c] = COST[5][c] for all c            # the ship carries everyone
else:
    for c in 0..11:
        GCOST[c] = COST[15][c] if allHeroes else 0
        for m in b2ba: if m.type != 15: GCOST[c] = max(GCOST[c], COST[m.type][c])
b716 = gmp
```
Consequences:
* A stack moves at the pace of its **slowest member** (gmp = min MP), and every terrain costs the
  **worst** member's cost.
* **Heroes are ignored when building the cost table**, so a hero stacked with Pegasi, Griffins or
  Dragons flies with them over water and mountains. Heroes still count toward the MP minimum.
* Any **Navy** in the group makes the whole group use Navy costs and navy MP only, which is how
  land units are carried.
* Flying units do **not** carry non-hero land units: water stays at 66 because of the land unit.

---------------------------------------------------------------------------------------------------

## 4. One step: FUN_1cdf_02d2(dir) [H, disassembly-verified]

```
def step(dir):                                  # returns True if the army moved
    if cur is None: return False
    ox, oy = cur.x, cur.y
    nx, ny = ox + DX[dir], oy + DY[dir]         # no bounds check here (the path never leaves the map)
    w = MAP[ny][nx]; cls = CLASS[w & 0x7f]
    cost = GCOST[cls] if group_mode else COST[cur.type][cls]
    if w & 0x800:                               # armies on the target tile
        if owner(w) != P: return False          # enemy army: no move (attacking is a separate action, §6)
        n = count_armies_at(nx, ny)             # FUN_2b32_0008
        if group_mode and n + ad5e > 8: return False
        if not group_mode and n + 1 > 8: return False
    if cls in (1, 2, 3) and (w & 0x800) and any own army at (nx, ny):
        cost = 2                                # boarding / joining units on water or a bridge
    mp = b716 if group_mode else cur.mv
    if mp < cost:                               # includes cost 66 = impassable
        mark_done()                             # flag 0x40 on cur or on all members (1c8b_043a)
        deselect(redraw=True)                   # FUN_2b32_0918(0,1,1)
        return False
    if cls == 10 and owner(w) != P: return False    # enemy or neutral city: no move
    MAP[ny][nx] = (w & 0xf87f) | (P << 7)       # tile owner bits := mover
    capture_towers(nx, ny)                      # §4.1
    if not group_mode:
        cur.mv = max(cur.mv - cost, 0); cur.x, cur.y = nx, ny
    else:
        b716 = max(b716 - cost, 0)
        for m in b2ba (non-null): m.mv = max(m.mv - cost, 0); m.x, m.y = nx, ny
    MAP[ny][nx] |= 0x800
    if no army left at (ox, oy): MAP[oy][ox] &= ~0x800   # FUN_2b32_0102
    (scroll viewport, redraw, status panel)
    if (b716 if group_mode else cur.mv) < 1:
        mark_done(); deselect(redraw=True)
    return True
```
Notes:
* Members of a group pay the same cost and are clamped at 0 individually. A fast unit therefore keeps
  its surplus, and ships' passengers lose MP while sailing.
* The cost-2 rule applies to **every** step onto a water, shore or bridge tile that already holds an
  own army, for land and naval units alike. A land unit boards a ship by stepping onto the ship's tile
  for 2 MP, even though its own row says 66. Disembarking is an ordinary step of a single land unit
  (or of a non-navy subgroup) onto land, paid from that unit's own row.
* Quirk: if a navy is moved in single mode, its passengers stay behind on the water tile. They can
  then only move onto land or onto other own-occupied water.
* Ruin and temple tiles (class 11) are ordinary tiles costing 2 for land units. Entering has no
  effect; searching is a separate command (FUN_307e_000c, needs ≥1 MP).
* Moving into your **own city** is a normal step (cost 1). Any non-own city tile refuses the step.
* There is at most **8 armies per tile**; a 2×2 city holds 32.

### 4.1 Tower capture: FUN_1cdf_06c2(x,y) [H]
For the 9 tiles (x+dx, y+dy) with dx,dy ∈ {−1,0,1} (tables DS:0x3a42/0x3a30): if the tile is on
the map, has class 9 (tower), and has no army or an own army (`!(w&0x800) || owner(w)==P`), then its
tile index becomes `2 + P` (owner bits unchanged). Towers are therefore taken just by **moving next
to them** (or onto them). They are also captured by winning a battle on a tower tile (2289_09c0), and
built on plain tiles (§8).

---------------------------------------------------------------------------------------------------

## 5. Moving to a clicked tile: FUN_1cdf_0000(tx,ty) [H]

The human UI is mouse-driven. FUN_31e1_0042 picks the cursor: a sword (attack mode, DS:0xbc14 = 1)
when hovering over an enemy army or a non-own city with an army selected, otherwise a directional
arrow (move mode, bc14 = 0). Clicking (FUN_3232_000e) calls FUN_1cdf_0000(0,0) in move mode (the
target is the clicked tile) or FUN_2289_0004(dir) in attack mode. There is no keyboard step-move.

```
def move_to(tx, ty):
    if cur is None or not (0 <= tx < 109 and 0 <= ty < 156): return
    w = MAP[ty][tx]; cls = CLASS[w & 0x7f]
    board = cls in (2, 1, 3) and (w & 0x800) and any army at (tx,ty) with type == 5 and owner == P
    if not board:
        c = GCOST[cls] if group_mode else COST[cur.type][cls]
        if c == 66: beep(); return               # destination must be passable
    path = find_path(tx, ty, board)              # §7, ≤ 50 directions, 0xff-terminated
    if army off-screen: recentre
    for i, d in enumerate(path):
        if d == 0xff or i == 50: break
        if not step(d): break                    # stops on blocked step or lack of MP
        (short delay ~2 timer ticks)
```
**Multi-turn moves do not exist for human players.** The path is computed and walked at once. When MP
runs out partway (step fails, or MP reaches 0) the army is marked done (0x40), deselected, and the
rest of the path is thrown away. Nothing is stored in +0x14/+0x16 and no dots are drawn. Next turn
the player clicks again. "%s %s moving! (%d)" (FUN_274c_01ea) is only the banner shown while a
computer player takes its turn ("Sirians are moving!"); it is not a path display.

---------------------------------------------------------------------------------------------------

## 6. Attacking (entering enemy and neutral cities or armies)

**FUN_2289_0004(dir)** [H]:
```
target = clicked tile if max(|dx|,|dy|) <= 1 from cur, else cur + (DX[dir], DY[dir])
cls = CLASS[target]
if group_mode: if b716 < 2: return    else: if cur.mv < 2: return
c = GCOST[cls] if group_mode else COST[cur.type][cls];  if c == 66: return
if cls == 10 and owner(target) == 15: neutral_city_attack(target)   # FUN_2491_000a
elif ((w&0x800) and owner(w) != P) or (cls == 10 and owner(w) != P and not w&0x800):
    FUN_2289_0466: attackers' x,y := target; mv -= 2 (cur, or b716 and every member)  # no clamp
    battle (FUN_23cd_000c setup, FUN_2289_067a resolve)
    FUN_2289_09c0: delete the dead on both sides; winner's armies stay on target.
       If the attacker won: tile owner bits := attacker, tile |= 0x800; tower tile -> index 2+attacker;
       city -> all 4 tiles index 86+4*(attacker+1)+i, owner bits := attacker, city owner changes,
       pillage gold etc.  If the attacker lost: tile owner bits := defender owner.
    FUN_274c_0274 rebuilds every 0x800 flag from the army list.
```
* An attack always costs **2 MP** whatever the terrain, but the terrain must be passable for the
  attacker. The winners **end up on the target tile**. When the target is a city, the defenders are
  every army on all 4 city tiles (23cd_000c).
* **Neutral city** (owner 15), FUN_2491_000a: no tactical battle. The attackers move in (−2 MP);
  then `score = Σ_i S[i]·(i+1)` over the sorted attacker strength list DS:0xbc62; if
  `dice(1,100,0) > 110 − (city.defence·10 − score)` all attackers die. Otherwise the city is taken:
  owner = P, 4 tiles get index 86+4(P+1)+i and owner bits P, the target tile gets 0x800. [M for the
  formula, which belongs to the combat spec]

---------------------------------------------------------------------------------------------------

## 7. Path finder: FUN_3257_08b7 → FUN_3257_0957 [H, disassembly-verified]

This is a deterministic greedy line-follower with retries, a reverse search, waypoints and a smoothing
pass, plus **one random choice**: `dice(1,8,-1)` uses the global MS-C LCG, so replicate the call
order exactly. It does not look at army positions except near cities, and it ignores stack limits and
the cost-2 boarding rule. Each step is validated later by `step()`.

### 7.1 State
```
SRC = (cur.x, cur.y); DST = (tx, ty); BOARD = board flag; P = current player
PC[12] = GCOST if group_mode else COST[cur.type]   # copied to seg [0x93ac]:0
AGG = DS:0x8416                                   # 0 for humans; set only around AI moves (3257_04c6)
RESULT[50] (DS:0xa358 -> caller buffer), BEST = A4BE
A4C2 = dist(SRC, DST); A4C6 = (CLASS[DST] == 10)
```
Helpers:
* `dist(a,b,c,d) = (int)sqrt((a-c)^2 + (b-d)^2)`, truncated (FUN_3257_1b8f; returns 10000 if the
  square sum overflows). The 5th argument is a debug tag and is ignored.
* `dirto(x,y,tx,ty)` (1c15): 0xff if equal; same x → 0 if ty<y else 4; same y → 6 if tx<x else 2;
  tx<x → 7 if ty<y else 5; else 1 if ty<y else 3.
* `scan(x,y)` (1d43): `NB[d] = CLASS[MAP[y+DY[d]][x+DX[d]]]` for d = 0..8, or 0xff if off-map.
  NB[8] is the centre.
* `dice(n,s,p) = p + Σ int(rand()/32767.0*s + 1.0)`.

### 7.2 choose(x,y): FUN_3257_158b. Uses A4A8 = dirto(cur→walk target), A4C0 = dist(cur, walk target), A440 = previous direction, A43A = cheap-terrain mode
```
scan(x,y); a = A4A8; av = [1]*8
if (x,y) == SRC:                                  # leaving the army's own square
    for d in 7..0: if NB[d]==10 and A4C2 > 3 and owner(x+DX[d],y+DY[d]) != P: av[d]=0
for d in 7..0:                                    # passability
    if NB[d] in (1,2,3) and (x+DX[d],y+DY[d]) == DST and BOARD: continue
    if NB[d] == 0xff or PC[NB[d]] == 66: av[d] = 0
lazy = False
for d in 7..0:                                    # cities
    if AGG or NB[d] == 10:
        if not lazy: ds = dist(SRC,(x,y)); dd = dist(DST,(x,y)) if A4C6 else 100; lazy = True
        thr = 1 if AGG else 2; n = (x+DX[d], y+DY[d])
        if (thr < A4C2 and ds < 3 and MAP[n] & 0x800) or (dd > 3 and not AGG and owner(n) != P):
            av[d] = 0
sa = av[A440] (if A440 != 0xff); sb = av[a]       # never turn back
for b in (a, A440): if b != 0xff: av[(b+3)&7] = av[(b+4)&7] = av[(b+5)&7] = 0
if A440 != 0xff: av[A440] = sa
av[a] = sb
if no av[d] == 1: A354 = 0xff; return
if A43A and A4C0 > 1:                             # cheapest-terrain filter
    m = 0x7fff
    for d in 7..0: if av[d] and PC[NB[d]] < m and NB[d] != 10 and A4C0 > 2: m = PC[NB[d]]
    keep = [d for d in 0..7 if av[d] and PC[NB[d]] == m]
    if keep: av = [d in keep for d in 0..7]
for k in (0, 1, 7, 2, 6):                         # prefer the straight line, then near it
    if av[(a+k)&7]: ch = (a+k)&7; break
else:
    n = dice(1,8,-1) + 1; ch = 0                  # random available direction
    while n: ch = (ch+1)&7; if av[ch]: n -= 1
A354 = ch; A440 = ch
```

### 7.3 walk(x,y,tx,ty,reverse): FUN_3257_12ad → (ok, B[50], steps A35A, cost A4BC)
```
d0 = dist(x,y,tx,ty); ox,oy = x,y; B = [0xff]*50; retries = 2; cost = 0; steps = 0; A440 = 0xff
budget = d0 + (d0 >> 2) + 4; if budget < 10: budget = 10
if RESULT[0] == 0xff: budget += A43E
loop:
    d = dist(x,y,tx,ty); A4C0 = d
    if d == 0: return OK
    A4A8 = dirto(x,y,tx,ty)
    if d == 1: A440 = 0xff
    while True:
        choose(x,y)
        if A354 != 0xff: break
        if retries == 0: return FAIL
        A440 = 0xff; retries -= 1
    (x,y) += dir A354 unless the result is off the map (x<0, y<0, x==109, y==156)
    steps += 1; budget -= 1; scan(x,y); cost += PC[NB[8]]
    if budget < d: return FAIL                    # unsigned compare; d = distance before this step
    if (x,y) == (ox,oy): return FAIL
    if reverse: B = [(A354+4)&7] + B[:49]         # prepend the reversed direction
    elif steps-1 < 50: B[steps-1] = A354
```
(DS:0xa4ca, 0xa4cc and 0xa356 are written but never read.)

### 7.4 search(a,b): FUN_3257_1160 → C[50], Csteps (A424), Ccost (A4C4)
```
C = [0xff]*50; Ccost = 0x7fff
if walk(a→b, reverse=False) ok: C,Csteps,Ccost = B,steps,cost
if walk(b→a, reverse=True)  ok and (C[0]==0xff or cost < Ccost): C,Csteps,Ccost = B,steps,cost
```
### 7.5 accept(p): FUN_3257_0e49
```
if C[0] == 0xff: return 0
if RESULT[0] == 0xff or Ccost < BEST:             # unsigned
    BEST = Ccost; RESULT = C
    return 0 if (2*A4C2 < BEST and p == 0) else 1
return 0
```
### 7.6 Top level: FUN_3257_0957
```
RESULT = [0xff]*50
if SRC == DST: return
A43E = 0; BEST = 0
A43A = 1; search(SRC,DST); found  = accept(0)
A43A = 0; search(SRC,DST); found |= accept(0)
if (SRC.x < 20 and SRC.y < 26) or (DST.x < 20 and DST.y < 26): found += 1    # NW corner: no waypoints
if not found: pick_waypoints()                    # 7.7
A43A = 1; k = 0
while not found:
    wp = W[k]
    if wp != 0xff and (F[k] == 0 or RESULT[0] == 0xff):
        A43E = 4;  search(WP[wp], DST)
        if C[0] != 0xff:
            save, s_steps, s_cost = C, Csteps, Ccost
            A43E = 20; search(SRC, WP[wp])
            if C[0] != 0xff:
                Csteps += s_steps; Ccost += s_cost
                j = 0; for i in 0..49: if C[i] == 0xff: C[i] = save[j]; j += 1
                found = accept(1)
    if A43A == 0: k += 1; A43A = 1
    else: A43A = 0                                # every waypoint is tried twice: A43A=1, then 0
    if k >= 8: found += 1
smooth(RESULT)                                    # 7.8
```
### 7.7 pick_waypoints: FUN_3257_0ee5
37 fixed waypoints WP at DS:0x8428 (x,y words):
`(8,102) (17,100) (12,124) (37,121) (57,139) (70,137) (89,126) (53,101) (20,90) (28,87) (12,86)
(27,66) (77,95) (92,99) (86,50) (99,12) (40,49) (24,126) (60,89) (8,45) (80,19) (57,54) (38,62)
(61,5) (45,58) (55,74) (15,40) (47,93) (40,25) (61,93) (75,97) (13,81) (5,97) (75,104) (74,47)
(51,44) (74,1)`
```
D = dist(DST,SRC); W = [0xff]*8; F = [0]*8; score = [0xff]*37; far = [0]*37
for i in 36..0:
    p = WP[i]
    if PC[CLASS[p]] != 66 and p != SRC and p != DST:
        s = dist(p,SRC) + dist(p,DST); score[i] = s
        if s >= D + 10: far[i] = 1                # signed compare
for k in 0..7:
    best = 0xff; bs = 10000
    for i in 36..0: if score[i] != 0xff and score[i] < bs: bs = score[i]; best = i   # ties -> highest i
    if best == 0xff: break
    W[k] = best; F[k] = 1 if (far[best] or k > 4) else 0; score[best] = 0xff
```
### 7.8 smooth: FUN_3257_0ce0
32 pair rules at DS:0x84bc/0x853c, as (d1,d2) → r with r = 0xff meaning "remove both":
opposite pairs (0,4) (1,5) (2,6) (3,7) (4,0) (5,1) (6,2) (7,3) → remove; (2,7) (1,6) (7,2) (6,1) → 0;
(0,2) (2,0) → 1; (0,3) (3,0) (1,4) (4,1) → 2; (2,4) (4,2) → 3; (3,6) (6,3) (5,2) (2,5) → 4;
(6,4) (4,6) → 5; (7,4) (4,7) (5,0) (0,5) → 6; (0,6) (6,0) → 7.
```
i = 0
while not (P[i] == 0xff or i + 2 > 49):
    r = rule for (P[i], P[i+1])
    if none: i += 1; continue
    if r == 0xff: delete P[i], P[i+1]  (shift left 2, pad 0xff)
    else:         P[i] = r; delete P[i+1] (shift left 1, pad 0xff)
    i = 0                                          # restart from the beginning
```
The smoothing **ignores terrain**. A merged diagonal can lead onto an impassable or blocked tile, and
then the real move stops at that step.

A prototype of §7 (scratchpad `pf.py`, not delivered) found legal paths for 26 of 31 random
reachable land pairs within 25 tiles, which is in line with the game's known weak path finding.

---------------------------------------------------------------------------------------------------

## 8. Turn start, MP reset and carry-over

Per player turn start (human: FUN_1a12_007e; AI: FUN_274c_0000):
1. **FUN_1a12_0000** [H]: for every army with owner == P and x ≠ −1:
   `flags &= ~0x40; mv = min(mv, 2) + maxmv`. Up to **2 unused MP carry over** to the next turn.
   Armies in transit (x = −1) are not reset.
2. FUN_274c_0274: rebuild map bit 0x800 from the army list.
3. FUN_1c8b_0004: clear flags 0x40 and 0x200 on own armies; restore the "next army" anchor.
4. Hero appearance (2cad_0006), etc.
5. Production phase, once per turn (human: FUN_2f0e_091a from the main loop when turn > 1; AI: 277d_0010):
   **first** FUN_277d_0286 advances vectored units, **then** cities produce (2f0e_0ad8 → 2f0e_1010).
   * Vectoring [H]: production with a vector target creates the army off-map with
     `x = y = −1, +0x14 = destination city, +0x16 = 100`. At each later turn start, 100 → 101, and
     101 → arrival: the army is placed on the first city tile (TL, TR, BL, BR) holding fewer than 8
     armies. If the city is no longer owned by P, or all 4 tiles are full, the army is **destroyed**.
     A vectored unit therefore appears 2 turns after it was produced.
   * A new army starts with mv = maxmv (no +2).
   * Navy: placed at `city + PORT[city+0x4f]` (port index 1..12 around the 2×2 city, table at image
     segment 0x3073: dx `0,0,1,2,2,2,2,1,0,-1,-1,-1,-1`, dy `0,-1,-1,-1,0,1,2,2,2,2,1,0,-1`; 0 means
     no port). Refused if the port tile is enemy-held or full. Quirk: a vectored navy appears
     **immediately** at the destination city's coordinates + the producing city's port offset. [M]

---------------------------------------------------------------------------------------------------

## 9. Map structure

**File ILLURIA.MAP**: 156 rows × 109 words, no header. On load (FUN_109f_0f9c) every word is
**byte-swapped**: `mem = (file >> 8) | ((file & 0xff) << 8)`. The save file stores the in-memory
words unchanged. Under that swap, the "lo = flags (0,7,23,39), hi = 0x80|index" description of the
file means: file lo byte → bits 8..15 (0x07 → owner bits 0x700, +0x10 → 0x1000, +0x20 → 0x2000), and
file hi byte → bits 0..7 (0x80 = lowest owner bit, low 7 bits = index). A file word 0x0000 is plain
with owner 0 (5704 tiles); 0x8007 is plain with owner 15. [H]

**In-memory word** (array at far seg 0x409d, `MAP[y][x]` = word at 0x42 + y·0xda + x·2) [H]:

| bits | meaning |
|---|---|
| 0x007f | tile/graphic index 0..125 (class via DS:0x3934) |
| 0x0780 | owner (bits 7..10): **city tiles = city owner; any other tile = owner of the last army that entered it** (written on every step, battle, spawn). Reliable only where 0x800 is set (it then equals the occupants' owner; the save check is 100%). Army sprites on the main map are drawn in the colour of the tile owner bits (1a12_0536) |
| 0x0800 | at least one army is on the tile (kept in sync; rebuilt by 274c_0274) |
| 0x1000 | original-tower marker from the map file (all 64 index-1 towers). **Never read** by the code; not set on built towers |
| 0x2000 | city-tile marker from the map file (320 tiles). **Never read** |
| 0x4000 | unused |
| 0x8000 | site visited: ruin searched or explored ("Explored" vs "Unexplored" in the info panel, 2d3c_05f8), temple vision taken (307e_09d4), AI goal done (1d88_1751) |

**Graphic index changes** [H]:
* City captured by P (2289_09c0 / 2491_000a / 2491_0341 / AI): tile i (TL,TR,BL,BR) gets index
  `86 + 4·(P+1) + i` and owner bits P. Neutral is `86 + i`. Checked on all 320 city tiles of the
  save. (The code that sets the capitals' graphics at a new game was not found. FUN_16c7_000c only
  sets their owner bits.)
* Tower: unowned index 1; owned by P index `2+P` (captured by adjacency §4.1, by battle, or built).
  **Building** (FUN_2c41_0002/0144): a selected army on a **plain** tile (class 7, index 0) and
  100 gp turns the tile into index 2+P (class 9). In an own city the same command raises city defence
  (+0x18) by 1, at a cost of word[2 + 2·defence] (the segment is unclear, [M]). Refused at defence > 9
  ("legendary").
* **Raze** (FUN_3043_0000/009a/01d8): only on an own city or tower tile (owner bits == P). A tower
  becomes index 12. A city's 4 tiles become index 12 (ruin graphic, class 11), city owner = 15,
  production and vectors cleared. Owner bits of the tiles are left alone.
* Ruins: index 10 or 12 (16 each). Special sites (temple, library, seer): index 11. The site table
  (DS:0x7ec6, 40 × 28 bytes: x, y, name[20], +0x18 type 1 Library, 2 Seer/Oracle, 3 Temple,
  4 Ruin (re-rolled into rewards 4..8), +0x19 item, +0x1a guardian) matches 8 index-11 tiles and
  32 ruin tiles.
* Main-view graphic lookup: sheet column `DS:0x3090[idx]` (×40 px) and row `DS:0x318c[idx]` (×20 px).
  The main view tile size is 40×20.

**Regions ("Lands:")** (2d3c_028e/05f8/0762, 307e_0ce0) [H]: `region = NAMES[(2*y)//156 * 4 + (4*x)//109]`,
using the cursor tile. NAMES (pointer table DS:0x68a4): 0 Western Lauredor, 1 Central Lauredor,
2 Eastern Lauredor, 3 Argundor, 4 Western Sulador, 5 Central Sulador, 6 Eastern Sulador, 7 Huinedor.
The map is cut into a 4×2 grid (columns of 109/4 tiles, rows of 78).

---------------------------------------------------------------------------------------------------

## 10. Fog of war and minimap

* **There is no fog of war or exploration state.** No per-player visibility array exists in memory
  or in the save. "Unexplored"/"Explored" refer only to ruins (bit 0x8000). [H for the strings, M
  that nothing else exists]
* **Minimap** (FUN_16c7_0150 → 2e41_0296/032c): the static picture STRAT.PCK (ESTRAT.PCK on EGA),
  224×160 = 2 px per tile across × 1 px per tile down, offset (2,2), blitted at screen (408,5). On top,
  each **owned city** is drawn as a 6×3 block copied from the ARMIES sheet at source
  `(392, 112 + 3·owner)` to `(2·cx + 2, cy + 2)` (DS:0x247c/0x247e). A **razed city** (owner 15 and
  TL index == 12) uses source row 136 (slot 8). Unrazed neutral cities and armies are not drawn
  (they come from the background or are absent). [H for the cities; M that armies are absent]

---------------------------------------------------------------------------------------------------

## 11. AI step loop (for completeness): FUN_3257_0004(tx,ty) [M]
The same path finder is used (with AGG = DS:0x8416 = the AI's parameter). For each direction:
`cost = GCOST[cls]` (always the group table and b716). If `b716 < cost` → stop (returns 1 if at the
target, else 3). A non-own city → 2 (attack). An enemy army → 5. If `count_at_tile + ad5e > 8` →
3. Otherwise apply the same updates as step(): b716 and per-member MP clamped at 0, tower capture,
owner bits, 0x800 set and cleared. If a hero is in the group, items lying on its current tile are
picked up before each step (1d88_166e). There is **no** cost-2 boarding rule. At the end of the path:
1 if at the target, else 2 when `dist ≤ 1`, otherwise 3.

---------------------------------------------------------------------------------------------------

## 12. Function index (evidence)
| function | role |
|---|---|
| 109f_01a5 / 109f_07b4 | load / save game (army count at DS:0xacc8, 24-byte records) |
| 109f_0f9c | load ILLURIA.MAP (byte swap) |
| 2b32_027c / 2b32_0318 | allocate / free army slot |
| 2b32_0008 | list armies at (x,y) (≤8) + top unit by PRIO; returns count |
| 2b32_0102, 2b32_01a2, 2b32_0252 | clear 0x800 if tile empty / set 0x800 |
| 2b32_036a, 1c8b_0076/013e/02c0/049c, 2b32_0f76 | selection, next army, stack dialog, group mode |
| 1cdf_07b2 | group MP and cost table |
| 1cdf_0000 | move to clicked tile (path + steps) |
| 1cdf_02d2 | one step |
| 1cdf_06c2 | tower capture around a tile |
| 1c8b_043a, 1c8b:00c8, 1c8b:00d6 | mark done (0x40), skip, sentry (clear 0x01) |
| 2b32_0918 | deselect |
| 3257_08b7/0957/1160/12ad/158b/0e49/0ee5/0ce0/1b8f/1c15/1ccd/1d43 | path finder |
| 3257_0004, 3257_04c6 | AI move along path, AI goal → coordinates |
| 2289_0004, 2289_0466, 23cd_000c, 2289_067a, 2289_09c0 | attack, attack MP and position, battle setup, battle, aftermath and capture |
| 2491_000a / 2491_0341 | neutral city attack (human / AI) |
| 1a12_0000 | turn-start MP reset and carry-over |
| 1a12_007e, 274c_0000 | turn start (human / AI) |
| 277d_0286 | vectored army transit and arrival |
| 2f0e_0ad8, 2f0e_1010, 200c_0030 | production, spawn |
| 2c41_0002/0144 | build tower / improve defence |
| 3043_0000/009a/01d8 | raze |
| 307e_000c, 307e_038b, 307e_0ad5 | search site, explore ruin, temple blessing |
| 2d3c_028e, 2d3c_05f8 | region name, tile info |
| 16c7_0150, 2e41_0296/032c | minimap |
| 1a12_0536 | draw armies on the main view (colour = tile owner bits) |

## 13. Open questions and low-confidence items
* Army +0x0e: purpose unknown (always 0).
* Code that sets the capitals' city graphics at a new game: not located. The formula itself is
  confirmed by the save.
* The neutral-city win formula and battle details belong to the combat spec.
* The quick-double-click threshold table DS:0x451a was not dumped (UI only).
* The ally template table (image segment 0x307b) could in theory be modified at runtime. No writes
  were seen.
