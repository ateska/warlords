# Warlords (1990, v2.10) computer player AI and diplomacy: implementation spec

Source: Ghidra decompilation /home/claude/gh/d3.c, checked against gdis() wherever the decompiler
garbled the code. Addresses use Ghidra segments. `dice(n,s,p)` = p + nDs (see NOTES.md).
`dist(a,b)` = FUN_3257_1b8f = (int)sqrt(dx²+dy²), plain Euclidean distance. Its 5th argument is
ignored, so there is no pathfinding inside the AI evaluations. Confidence tags: **[H]** verified in
code or asm, **[M]** decompiler output that reads cleanly but was not cross-checked in asm,
**[L]** interpretation or guess.

Much of the AI is specific to the Illuria map. It uses hard-coded city-neighbour graphs,
priority cities and island special cases (see §9). A Python port must carry these tables over unchanged.

---------------------------------------------------------------------------------------------------
## 0. Data structures

### Per player (DGROUP)
| addr | meaning |
|---|---|
| 0x2322[8] | alive |
| 0x7e86[8] | 1 = human, 0 = computer |
| 0x7e96[8] | computer level: 0 Knight, 1 Baron, 2 Lord, 3 Warlord (names at 0x3f04) |
| 0x208e[8] | "Observe" toggle (shows that computer's moves/battles; becomes 0xd1c2 during its turn) |
| 0x209e[8] | "Enhance" toggle: halves build time (any player, human too) |
| 0x20ae[8] | number of cities (recomputed by FUN_1b90_03f0 and kept current on capture) |
| 0x20be[8] / 0x20ce[8] | total upkeep / total income |
| 0x20e0+20p | +0 gold, +2 **razer flag**, +4/+6 capital x,y, +8/+0xa per-turn flags, +0xc set for odd players (unused), +0xe **thrift** 0..3, +0x10 **truce count** |
| 0xb804 (`-0x47fc`) | **H[8][8]** int hatred matrix: `H[a][b]` at 0xb804+16a+2b is how much a hates b. H[a][a] = -1000 |
| 0xcc74 (`-0x338c`) [8] | **war[p]**: declared war target (player), -1 = none |
| 0x3a60[8] | ruin-plan selector (-1 until first use, then dice(1,2,-1)) |

Globals: 0xb6d4 turn (starts 1); 0x2474 **surrender-offered flag** (set when the human is offered
surrender, stays set; called NOQ below); 0x2476 game over; 0x2478/0x247a "Seer #1 / Oracle #7
already used"; 0x2088 Intense Combat (d12); 0x2470 extra-tough (`-T` switch); 0x2472 low memory
(`-L`); 0x2080 supervisor mode (adds the turn number to "%s %s moving! (%d)").

### City record (100 B at 0x4632+100c), AI-relevant fields
+0x18 defence (byte, 3..6 initially, -1 on each capture), +0x19 owner, +0x1a canBuild[10],
+0x24 time[10], +0x2e strength[10], +0x38 moves[10], +0x42 cost[10], +0x4c production slot,
+0x4d progress, +0x4e turns-left (0 = idle), +0x4f navy exit direction, +0x50 income,
**+0x52 prevOwner** (the player who lost this city, a grudge marker; 15 = none),
+0x54 vector flag, +0x56/+0x58 vector destination x,y, **+0x5a attackTarget** (city, -1),
**+0x5c island flag** (static: Gunthang 13, Cragmorton 34, Khorfe 74, reachable by flyers only),
**+0x5e attackType** (army type whose class shapes the attack stack), **+0x60 nStrong**
(units of type<10 with str>3 in the city, refreshed by FUN_24ef_040e).

### Army record (24 B), AI-relevant fields
+0 x, +2 y, +4 type (15 hero), +5 owner, +6 base moves, +7 moves left, +8 strength, +9 home city,
+0x10 upkeep (= cost/2), **+0x12 flags**: 0x20 moved-as-group, 0x40 done this turn, 0x80 "on
mission" (single-unit raid or expansion), 0x800 hero on an explore errand;
**+0x14 target**: 0..79 city, 100+i ruin/site i, 200+i item i, -1 none;
**+0x16 origin**: the city the stack was launched from (used to fall back or retake it).
While a unit is being vectored, +0x16 = 100/101 and +0x14 is the destination (FUN_277d_0286).

### AI army class table 0x4376[16] (rewritten each computer turn, FUN_27ed_0006)
Normal (0x4396): `0,0,0,1,2,3,4,2,5,5,0,0,5,0,0,0`. Warlord (0x43b6): `0,0,0,1,0,3,0,0,5,5,0,0,5,0,0,0`.
Class 0 generic, 1 Dwarven Legion, 2 Cavalry/Wolf Riders, 3 Navy (never built by the AI), 4 Elven
Archers, 5 flyers (Pegasi, Griffins, Dragons). Hero = type 15, class 0. Warlords fold Cavalry, Archers
and Wolf Riders into class 0, so those units join any ground attack stack.

### Per-turn scratch
`state[80]` at 0xafbe (`-0x5042`): per own city, -1 idle, 0 expanding into neutral, 1 nearly empty,
2 under-garrisoned, 3 defensive, 4 vectoring, 5 staging an attack, 6 launch now.
`cand[80]` at 0xa13a (`-0x5ec6`): marks used while choosing a target.

### City tile roles (2×2 city; offsets dx={0,1,0,1}, dy={0,0,1,1}; at most 8 units per tile)
FUN_24ef_040e places each unit on one of the four tiles. Tile 0 (x,y) holds the departing or attack
stack and heroes. Tile 1 (x+1,y) is the garrison. Tile 2 (x,y+1) is garrison overflow. Tile 3
(x+1,y+1) is the reserve or second wave. Later code finds the stack to send by looking only at tile 0.

---------------------------------------------------------------------------------------------------
## 1. Turn structure

### Round loop (FUN_1312_000e) [H]
Each round, every living computer player moves first, in index order 0..7 (FUN_274c_0000). The
humans then move, also 0..7. End of round, FUN_1b90_0116: eliminated players' units are removed
("%s are no longer a threat!" / "Wretched %s! For you, the war is over!"), victory is checked, and
turn++. If no human is alive, ESC during computer play ("Hit ESC to stop computer play") turns
every player into a human.

### One computer turn: FUN_274c_0000(p) [H]
1. Show "%s %s moving!" ("is" for Elvallie (4) and Lord Bane (7), otherwise "are").
2. Rebuild the occupancy bit 0x800 on every map tile that holds an army (FUN_274c_0274).
3. If cities[p] > 0:
   a. Reset moves (FUN_1a12_0000): clear 0x40; moves = min(movesLeft,2) + baseMoves. This rule is
      the same for humans.
   b. Income (FUN_2e41_0186): gold = min(30000, gold+income); gold = max(0, gold-upkeep).
   c. Hero recruitment (FUN_2cad_0006), see §7.
   d. Production tick and vector arrivals (FUN_277d_0010): turnsLeft>1 → decrement; ==1 → unit
      created (FUN_2f0e_1010; vectored units arrive 2 turns later via FUN_277d_0286).
   e. **AI main, FUN_27ed_0006** (below).

### AI main: FUN_27ed_0006 [H, disassembly-checked]
```
set class table (Warlord variant if level==3)
truce check                              FUN_29b2_05a8   (§5.4)
if no living computer has razer flag: player[dice(1,8,-1)].razer = 1   (may land on a human/dead slot)
if livingPlayers < 2: all players := human (game ends)
heroes = #own heroes
if cities >= 4 and gold < 500:
    if heroes == 0 or (heroes == 1 and dice(1,8,-1) == 0): thrift = min(3, thrift+1)
if gold > 1000: thrift = 0
if gold < [100,75,50,25][thrift] and income < upkeep+20: thrift = min(3, thrift+1)
MOVE_ALL()                               FUN_27ed_0a3e   (§2.6) first movement pass
state[*] = -1
expanding = sum(EXPAND(c) for own c)     FUN_27ed_061e   (§2.1)
nDef = nAtk = nAtkGround = 0
for own c (79..0) with state[c] != 0:
    if c.attackTarget is now my own city: c.attackTarget = -1
    mode = 5 if c.attackTarget != -1 else (4 if c.vector else 3)
    if ORGANISE(c, mode): state[c] = mode           FUN_24ef_040e (§2.2), may change mode
    else: state[c] = -1
    if mode >= 5: nAtk++; if class(c.attackType)==0: nAtkGround++
    if mode in (3,4): nDef++
wantNew = (nDef > expanding) or (expanding == 0 and nAtk == 0)
if gold < 200 and cities > 3: wantNew = 0
if gold < [20,200,400,600,800,1000,1200][min(nAtk,6)]: wantNew = 0
if nAtk >= [1,2,4,32][level]: wantNew = 0           # max simultaneous attack groups
if level == 3 and |cities|/4 < nAtkGround: wantNew = 0
if wantNew and CHOOSE_TARGET(p,&src,&tgt):          FUN_24ef_1292 (§3)
    src.attackTarget = tgt; state[src] = 5; PICK_ATTACK_TYPE(src,-1)   FUN_27ed_1196, FUN_29b2_129e
LAUNCH()                                 FUN_27ed_11c8   (§2.4)
for own c (79..0) not currently producing (turnsLeft == 0):        FUN_29b2_01b4
    switch state[c]:  0,1 → BUILD_FAST(c)  2 → BUILD_BEST(c,-1)
                      3,4 → if gold >= 50: BUILD_FOR_FRONT(c)    5 → BUILD_ATTACK(c,-1)   (§4)
if level != Knight: HEROES_AND_MONSTERS()          FUN_1d88_000c (§6)
MOVE_ALL()                                          second movement pass
for own c (79..0):                                  # emergency refill
    empty = no army on any of the 4 tiles
    busy  = turnsLeft > 0
    if (not busy and (turn < 10 or empty)) or (busy and empty and fastestSlot != c.slot):
        BUILD_FAST(c)
```

---------------------------------------------------------------------------------------------------
## 2. City-level logic and movement

### 2.1 EXPAND(c): FUN_27ed_061e [H]
* FUN_29b2_0068: build list N of neutral, intact neighbour cities. Also pick `grab` = an enemy
  (non-own, non-neutral) neighbour whose 4 tiles are all unoccupied (the last such city found).
* If grab != -1: among own idle units in c (any tile, no target, not done, not a hero, flyers only
  if c is an island city), skip the first two and give the third `target = grab`, flag 0x80. The
  computer always grabs undefended enemy cities with a single unit.
* If c.attackTarget == -1 and N is not empty: state[c]=0; mode=0; if ORGANISE(c,0) fails, state=-1
  and return 0. Otherwise choose a neutral target:
  - Priority list (0-based) Zhoran 31, Carmel 36, Gork 77, Maridun 29, Fleymark 39, Khorfe 74: the
    first one in that order that appears in N.
  - Otherwise the n in N with the fewest own units already targeting it (only n with < 2), scored
    `4*count + dice(1,3)`, lowest wins.
  - Assign the target to every own unit on tile 0 that has no target and is not done (flyers only
    for island cities), skipping heroes unless level == Knight or the hero has 0x80. Units get flag
    0x80 if level != Knight. Return 1.

### 2.2 ORGANISE(p,c,&mode): FUN_24ef_040e. Garrison, stacking and disbanding [H]
```
L = own armies on c's 4 tiles (max 32; excess non-heroes are DELETED)
anyTargeted = any unit in L with target != -1; heroHere = hero in L
nStrong = #(type<10 and str>3); c.nStrong = nStrong
if anyTargeted and dice(1,4,-1) == 0: return 1           # 25%: leave the city untouched
(need, garrison) = THREAT(c)                              FUN_29b2_0350 (below)
if need == 0:  # only after THREAT razed the city
    t = nearest non-neutral city (FUN_29b2_0500); every unit in L: target = t; return 0
if level >= Lord and mode == 0: need = EARLY_THREAT(c)    FUN_24ef_1198
if len(L) < 2 and mode not in (0,5): mode = 1
elif nStrong < need and mode not in (0,4,5): mode = 2
if c % 4 == turn % 4 and mode == 4: return 1              # vectoring cities skip 1 turn in 4
S = L sorted: heroes first, then the first flyer, then by strength descending
if nStrong > 3: DELETE every non-hero unit with str < 4   # disband weak units
clear tile counters
if mode == 5 and len(L) > 3:                              # staging city
    if not VALIDATE_TARGET(&tgt, c):  c.attackTarget=-1; mode=3      FUN_24ef_1b68 (§3.3)
    else:
        tcls = class(c.attackType)
        (T, tN) = REGION_STR(tgt, withDefence=1); (O, _) = REGION_STR(c, 0); d = dist(c,tgt)
        stack: walk S, place on tile 0 while count < 8 and unit qualifies:
               tcls == 0 or class(u) == tcls or class(u) == 5 or hero or (tcls != 5 and type > 9);
               at most 1 hero and at most 1 Dragon (type 12) in the stack
        if count > 1 and count == len(L): move the last stacked unit to tile 1, count--   # keep 1 home
        reserve = 2 if heroHere else need
        if tcls == 0 and (d < 10 or count > 5) and tN < 8 and O > (T/2)*3 and count > 2: reserve = 0
        if reserve == 0 or (count > 7 and count + reserve <= len(L)): mode = 6     # LAUNCH
if mode not in (5,6): heroes → tile 0 (max 8); if any hero moved, flyers → tile 0 too
g = need if mode == 0 else garrison
take g non-hero units from S (strongest first): the first g-8 go to tile 2, the rest to tile 1
take (8 if mode == 0 else 0) more units → tile 3 if mode in (5,6) else tile 0     # expansion party
for every remaining unit u in S:
    keep = (u is hero)
    if level >= Lord and class(u) == 5:
        t = nearest own city with an attackTarget; if t: u.target = t; keep = 1
    if not keep and mode in (5,6) and class(c.attackType) not in (5,1): keep = 1
    keep ? place on the highest-numbered tile with < 8 units : DELETE u (upkeep saved)
return 1
```
Gameplay effect: a computer city keeps its garrison plus heroes and **disbands surplus units** that
have no job, except in staging cities. [H, deletion checked in asm at 24ef:1073..108b]

THREAT(c), FUN_29b2_0350 [H]: `need=2, garrison=2`; if gold > 5: garrison=4 and, for each neighbour
n in table order: neighbour owned by war[p] → need++, garrison=12; other enemy → need++, garrison=6
(the last assignment in the scan wins).
**Raze rule:** if the city has no own neighbours, ≥2 neighbours owned by war[p], cities[p] > 6,
c.attackTarget == -1, p.razer set, and dist(c, capital) > 20: the city is razed (FUN_3043_01d8; all
players' H[*][p] += 1), need=0, return.
**Defence repair:** if level ≥ Baron and gold > defCost[def]+200 and def < 3: def++,
gold -= defCost[def]. defCost (far seg 306d) = [50,50,50,50,75,100,150,175,350,500,800]. Captures
lower defence, so in practice this repairs captured cities back up to 3.

EARLY_THREAT(c), FUN_24ef_1198 [H]: after turn 15 return 2. Otherwise 0, then for each enemy army
within Manhattan distance 20: 1 for a computer owner, 2 for a human owner or if it targets c (return
2 at once). With 0, Lords and Warlords expand on turns ≤15 with no garrison at all.

REGION_STR(city, withDef), FUN_27ed_19d8 / FUN_27ed_1a36 [H]: for the city owner's armies in the box
x-4..x+5, y-4..y+5, **only units with str > 3**: `sum(str) + n*(heroBonus + anySpecial + anyFlyer +
itemBonus2) + (withDef ? defBonus[c.defence]*n : 0)`. heroBonus = [0,0,0,0,1,1,1,2,2,3][min(9, hero
str + command items)], with one hero assumed. anySpecial = 1 if any type 10..14. defBonus =
[0,0,1,1,1,1,1,2,2,3,3]. Both tables live in far seg 3043. Returns n.

### 2.3 Expanding and attacking stacks are just targets
Units carry a target city. Movement (§2.6) groups units with the same target and position.

### 2.4 LAUNCH(): FUN_27ed_11c8 [H]
For each own city c with state 6:
```
tgt = c.attackTarget
if level == 3 and class(c.attackType) == 5: DEEP_STRIKE(c,&tgt)    FUN_27ed_1770
for every own unit on tile 0: clear 0x40; target = tgt; origin(+0x16) = c
drop = (level < Lord) or gold < 50
if NOQ and level == 3 and owner(tgt) is a computer: drop = 1
if owner(tgt) in (me, neutral): drop = 1
if not drop:
    v = #cities whose vector destination is c;  w = #other cities with the same attackTarget
    if level == 3: drop = (v <= thrift)
    else:          drop = dice(1,10) > 4*w + v
if drop: c.attackTarget = -1          # otherwise the city keeps staging further waves
```
Knights and Barons attack in single waves. Lords and Warlords keep sending reinforcements.

DEEP_STRIKE (Warlord flyer stacks), FUN_27ed_1770 [H]: only if dist(c,tgt) < 41. Victim = player ≠ me
maximising cities + 10·[war target] + 10·[human]. Among the victim's cities whose neighbours are all
the victim's or neutral (interior cities), score `dice(1,3) − defendersInCity + #victim/neutral
neighbours + 32`; the highest becomes tgt.

### 2.5 Attack decision at the gate: FUN_29b2_1566 [H]
Called when a stack arrives next to an enemy-owned (non-neutral) target city. Neutral cities are
always attacked (FUN_2491_0341).
```
if turn < 20: attack
home = stack.origin (or the capital city if -1); tgt = stack.target
if home != tgt and not tgt.island:
    own = strength of my armies around the stack (FUN_27ed_1a36)
    T = max(0, REGION_STR(tgt,1) - 10)        # (0 if < 10)
    if own <= T*3/2:
        among tgt's neighbours n (not mine, prevOwner==me or owner==war[p]):
            if REGION_STR(n,1) < T and dist(home,tgt)+dist(tgt,n) < dist(home,n)+6:  best = weakest
        if best: retarget the whole stack to best; do not attack this turn
attack (FUN_2289_119e → battle FUN_2289_067a)
```
Before turn 20, or when no softer neighbour exists, the computer attacks whatever the odds.

### 2.6 MOVE_ALL(): FUN_27ed_0a3e [H/M]
Repeat until nothing is left to move, in two passes; pass 1 skips groups already flagged 0x20:
* Any own unit with type<10, no target, standing outside a city gets
  `target = BEST_CITY(mode=1 own)` (FUN_27ed_144c), i.e. it retreats to a weak or near own city.
* Take the first not-done unit that has a target, plus up to 7 more with the same target and
  position, as the stack (leader = first; the hero is remembered). allFlyers = every non-special
  member is a flyer.
* REEVALUATE (FUN_27ed_0eec), only while the leader is outside a city:
  - If origin is enemy-owned and closer to the leader than the target, target = origin (retake home).
  - Else if the target is my own city or has been razed (unless allFlyers): rescore origin and its
    neighbours by `200 − dist(leader,city)`, +5 if prevOwner==me; own city +5 (+15 instead if it has an
    attackTarget); city of war[p] +20; neutral 0. Best > 0 becomes the target. If origin is enemy,
    target = origin.
  - **No target found → heroes get target −1, all other members are DELETED.**
* Move along the path toward the target (FUN_3257_04c6 → FUN_3257_0004). Results: arrived; next to
  an enemy city → §2.5; enemy stack on the path → attack it; no path → target = nearest non-neutral
  city (FUN_29b2_0500). A hero arriving at a ruin or item explores it (§6.3). On arrival, target and
  origin are cleared.
* A lone unit with 0x80 and no target is retargeted with BEST_CITY(mode 2, enemy) and keeps moving
  while it has moves.
* Units still with the leader get 0x20. If the stack did not move, all get 0x40 (done).

BEST_CITY(p, mode, flyer, x,y, &cur): FUN_27ed_144c [H]
```
if not flyer and x < 20 and y < 26: return Amenal(6)          # NW island always goes to its port
if mode == 2 and any enemy army within Manhattan 12 of (x,y): return none
for each intact city t (terrain City):
    skip t in {2,6,10} unless flyer; mode1: only own; mode2/0: only non-own
    if NOQ and mode != 1: only neutral or human-owned t
    d = dist((x,y),t); skip if d >= 21 and not flyer
    s = 300 − (d/4 + REGION_STR(t,1))
    if t in neighbours(cur): s += 10
    elif not flyer and t in {43,44,36,42,45,5,7}: s −= 50        # 0x4400 hard-to-reach list
    if owner(t) == war[p]: s += 15
    if neutral: s += (not flyer or (x<20 and y<26)) ? 10 : −150
best s > 0
```

---------------------------------------------------------------------------------------------------
## 3. Choosing a new attack: CHOOSE_TARGET(p): FUN_24ef_1292 [H]
```
UPDATE_WAR(p)                                  FUN_24ef_0004 (§5.2)
T = war[p]; if T == -1: return 0
if FLYER_STRIKE(): (it already set up a target) …   FUN_24ef_181e, see 3.2; then continue normally
nDef = #own cities state 3; nAtk = #state 5/6; nAtkWar = those whose target is owned by T
(lead, leader) = LEAD()                         FUN_24ef_032e
alt = -1
if (cities[p] > 20 and cities[T] < 5) or (nAtkWar == 0 and cities[T] < 6):   # war nearly won
    best = 0
    for j ∉ {p,T}, alive: s = H[p][j] + dice(1,2) + (j==leader ? lead : 0)
        if s > best: best = s; if nAtk == 0 or s > 5: alt = j
cand[*] = -1; own cities in state 3 or 2 (or 4 if nDef > 5) → cand = -2 (possible launch sites)
enemy (non-own, non-neutral) neighbours of those → cand = 0
tgt = argmax over cand==0 of score > 25:                FUN_24ef_164c
      score = dice(1,20) + (owner==T ? 60 : prevOwner==me or owner==alt ? 40 :
                            (H[p][owner] > 4 and nAtkWar == 0) ? 20 : 0)
            + Σ over tgt's neighbours n: owner(n)==T ? 10 : prevOwner(n)==me ? 7 :
                                         (H[p][owner(n)] > 4 and nAtkWar == 0) ? 5 : 0
src = among cand==-2 cities adjacent to tgt, maximise dist(tgt,src) + dice(1,4)   # the FARTHEST one [H]
return both found
```
The caller sets src.attackTarget = tgt, state 5, and chooses the attack type (§4.4).

### 3.2 FLYER_STRIKE: FUN_24ef_181e [H]
Pick a random city X of war[p] (highest dice(1,100)). If any own city already has a flyer-class
attack, stop. Otherwise take the own city with no attackTarget, nStrong > 2, that can build Pegasi or
Griffins, and has only own or neutral neighbours, nearest to X. It gets attackTarget = X,
PICK_ATTACK_TYPE(city, 9) (flyer) and state 5. Runs at every level whenever wantNew is set.

### 3.3 VALIDATE_TARGET(&tgt, src): FUN_24ef_1b68 [H]
Returns `owner(tgt) != neutral` unless an alternative is found. Alternatives are considered only for
level ≥ Lord, a non-flyer attack type, and a non-island target:
range = max(10, dist(src,tgt)); thr = |5·REGION_STR(tgt,1)|/4.
Candidates: src's neighbours c ≠ tgt that are not mine, with prevOwner==me or owner==war[p]. A Warlord
also accepts any city of a human with cities ≥ mine+5. Choose the weakest with dist(src,c) < range and
REGION_STR(c,1) < thr. That city replaces tgt (src.attackTarget = c).

---------------------------------------------------------------------------------------------------
## 4. Production (computer cities)

The AI orders **one unit at a time** and pays the full cost when ordering:
BUY(c, slot, vectorTo), FUN_29b2_0278 [H]:
```
if gold < cost[slot] + 30 and turn > 5: refuse
slot := slot; progress = 0; turnsLeft = Enhance ? (time-1)//2 + 1 : time
gold -= cost          # turns 1..5 skip the check, so gold can go negative;
                      # the income step clamps it back to 0 (free units early on) [H]
vector = (vectorTo != -1) → vector x,y = vectorTo's x,y
```
On completion the unit appears (or is vectored, arriving 2 turns later). Its upkeep is cost/2. The
city then sits idle until it gets a new order.

Unit score used below: `s = 10 − (str − time)`; a flyer gets `s −= dice(1,2)` (1 or 2); lowest s wins.
Ties go to higher strength, then lower cost. Comparison is unsigned 8-bit.
* **BUILD_FAST(c)**, FUN_29b2_0ac4: any buildable non-navy unit (flyers only for an island-targeting
  city) with minimum time; tie → higher strength. No vector.
* **BUILD_BEST(c, v)**, FUN_29b2_0b8e: non-navy, str ≥ 4, best s. Vector to v if v != -1.
* **BUILD_ATTACK(c, v)**, FUN_29b2_0cd6: if v == -1, first run the ANALYSIS. If fewer than 2 cities
  vector into c, look for another staging city (role 3, fewer than 4 incoming vectors, same
  attack-type class, weaker target value). If found, c drops its own attack (attackTarget=-1,
  state=4) and v = that city. Then build the best-s unit **of c.attackType's class**, str ≥ 4, vector
  to v.
* **BUILD_FOR_FRONT(c)**, FUN_29b2_10f4 (state 3/4, gold ≥ 50): skip if c cannot build any str≥4
  unit. Clear the vector. ANALYSIS(c,0) assigns each own city a role: 1 = c itself, 2 = no
  attackTarget and nStrong < 2, 3 = staging city whose attack type c can build. Value = nStrong for
  roles 1/2. For role 3 the value is REGION_STR(target), −10 per neighbour of that city owned by war[p],
  min 0. Pick the destination by priority:
  1. a role-1/2 city with value < 2 and no incoming vectors;
  2. otherwise the role-3 city with < 4 incoming vectors and the lowest value (the softest target);
  3. otherwise a role-1/2 city with < 4 incoming, value < garrison(THREAT) and maximal
     `max(0, garrison − nStrong) + dice(1,2)`.
  If the destination is c itself: state 2, BUILD_BEST(c,-1). Otherwise state 4. For priority 2:
  copy the destination's attackType, then BUILD_ATTACK(c, dest). Else BUILD_BEST(c, dest).
* **PICK_ATTACK_TYPE(c, cls)**, FUN_29b2_129e: if c.attackTarget is an island city that c does not
  neighbour, cls = 9 (Griffins → flyers). Choose the best-s buildable non-navy unit (of cls's class if
  given) as c.attackType. If none: drop the target if it is an island, else attackType = 2 (Light Inf.).

---------------------------------------------------------------------------------------------------
## 5. Diplomacy and hatred

### 5.1 Storage and display
`H[a][b]` (a's hatred of b) and `war[a]` as in §0. The "How the other leaders view you" report
(FUN_1888_0a5e) shows, for leader a viewing human h:
`lvl = clamp(H[a][h] + (h == leader ? lead : 0), 0, 5)`; `if war[a] == h: lvl = 6`.
Names (0x2cec): 0 Apathy, 1 Distrust, 2 Dislike, 3 Disdain, 4 Disgust, 5 Hatred, 6 Loathing.
Loathing only ever means "has declared war on you".

LEAD(), FUN_24ef_032e: leader = most cities; second = most among the others;
`lead = max(0, cities[leader] − cities[second] − m)` with m = 5, or m = 0 when the current player is a
Warlord and the leader is human. A runaway leader is hated more by everyone.

### 5.2 Changes to H and war[]
* **New game** (FUN_274c_0088, computers only): H[i][j] = dice(1,3,-1) (0..2); H[i][i] = -1000;
  then a natural enemy E (50/50 from tables A/B) gets H[i][E] += dice(1,3,1) (2..4); war[*] = -1.
  A = 0x3f42 `[3,4,5,0,0,6,7,6]`, B = 0x3f52 `[4,4,6,7,1,2,2,3]`. For example Sirians → Orcs or
  Elvallie, Storm Giants → Elvallie, Grey Dwarves → Selentines or Horse Lords, Orcs → Sirians or Bane,
  Elvallie → Sirians or Storm Giants, Selentines → Horse Lords or Dwarves, Horse Lords → Bane or
  Dwarves, Bane → Horse Lords or Orcs.
* **City captured** (FUN_2289_09c0): if the loser is a computer, H[loser][winner] += 2. Pillage
  g = (loserGold / loserCities)/2: winner += g, loser −= 2g. City prevOwner = loser (or 15 if the
  winner is recapturing its own former city). Defence −1.
* **City razed** (FUN_3043_01d8): H[i][razer] += 1 for every i.
* **UPDATE_WAR(p)**, FUN_24ef_0004, runs only from CHOOSE_TARGET, i.e. when the computer wants a new
  attack:
  ```
  old = war[p]
  if old != -1 and old is dead: (Warlord: H[p][h] += 5 for every living human h); war[p] = -1
  (lead, leader) = LEAD()
  if Warlord and p != leader and lead > 4:
      H[p][j] -= 1 for j ≠ leader, non-human, with H[p][j] > 10      # calm down to gang up
  for j: score[j] = -1000 if dead or j==p else
         H[p][j] + 3·[j==war[p] or war[j]==p] + (j==leader ? lead : 0)
         if cities[p] > 40: H[p][j] = max(H[p][j], 5)
  best = max(0, max score); if best > 0: war[p] = argmax with a dice(1,10) tie-break
  if Warlord and war[p] is human: prevOwner = 15 for cities owned by p or with prevOwner == p
  if war[p] invalid (−1, dead, no cities): war[p] = -1
  elif war[p] != old: message "%s declares war on %s"
  ```
* A 15-turn decay also exists (FUN_274c_017a: every turn divisible by 15, H −1 toward players with
  < 25 cities, floor 0). **No caller was found (dead code) [M].**

### 5.3 Effects of war[] and H
war[p] directs everything: target scoring (+60/+10), BEST_CITY +15, retake/retarget logic, garrison
sizes (12 next to the war target), raze rule, and production dampening (−10 per neighbour). H only
feeds into choosing war[p] and the secondary "alt" enemy (threshold H > 4).

### 5.4 Truce: FUN_29b2_05a8 (each computer turn, 25% roll) [H]
Applies only between two Warlords, and at most once per player per game:
```
E = war[me]; L = alive player with most cities
require: dice(1,4,-1)==0, E != -1, level[me]==3, E is computer, level[E]==3, truceCount[me]==0,
         war[E]==me, L ∉ {me,E}, cities[me] > 9, cities[E] > 9, |cities[me]−cities[E]| < 6,
         |cities[me]−cities[L]| > 4, |cities[E]−cities[L]| > 4
truceCount[me]++
H[me][E] = 0; H[me][L] += 10; H[E][me] = 0; H[E][L] += 10
clear prevOwner grudges between me and E; drop attackTargets aimed at each other's cities;
armies targeting the other side's cities: target = origin
"%s signs a truce with %s"; war[me] = war[E] = -1
```

### 5.5 Surrender offer to a dominant human: FUN_1b90_0434 [H]
Checked at the end of each human turn while NOQ == 0. Requires exactly one living human, with more
than 40 cities and more than (largest computer's cities + 15). Then NOQ = 1 and the BEG picture is
shown: "Your seneschal reports strangers at the gate!" / "Crawling towards you they humbly present a
scroll", followed by a dialog with two buttons:
* **"Accept a grovelling surrender!"** → FUN_1b90_0666: game over (0x2476=1), every slot becomes
  human, "Under your enlightened rule ... Illuria has entered a new golden age".
* **"Off with their miserable heads!"** → FUN_1b90_0730 (HEAD picture, "No Quarter !!!"): for every
  living i and living j, if j is human: H[i][j] = dice(1,1000,100) and war[i] = the human; else
  H[i][j] = 0.
With NOQ set: computers target only neutral or human cities (BEST_CITY), Warlords drop launched
attacks on computer cities, no more hero recruitment, the hero AI goes for the war target, and the
offer is never repeated.
If no human remains: "And so the war continues... without you!".

---------------------------------------------------------------------------------------------------
## 6. Heroes, monsters and ruins (level ≥ Baron only: Knights skip FUN_1d88_000c entirely) [H/M]

### 6.1 Per turn, for each own unit with type ≥ 10 that is not done
* If Warlord at war with a human: clear prevOwner = 15 on own cities, and on others' cities where it
  is me (unless the owner is human).
* **Turn 1:** the first such unit gets a target from 0x3b08[p][dice(1,4,-1)] (1-based city, 0 =
  none): Sirians Ssuri/Troy/Herueth, Storm Giants Himelton, Dwarves Cragmorton/Zhoran, Orcs
  Gimlad/Thurtz, Elvallie Charling, Selentines Ak-Enlie, Horse Lords Maridun/Derridon/Derridon,
  Bane none. Processing then stops for that turn.
* A hero picks up items on its tile. An invalid ruin/item target is reset. Find the city it stands in.
* **Monsters** (type 10..14, FUN_1d88_119a): outside a city with no target →
  BEST_CITY(mode 0, flyer if class 5) plus flag 0x80. Inside a city → JOIN(unit, city, 1).
* **Heroes** (FUN_1d88_03a9): inside a city, grab the items lying there; a hero with >2 items hands
  extras to heroes there holding ≤1. If target == −1:
  - flag 0x800 set (on an explore errand): clear it, NEXT_ERRAND (6.2).
  - turn < 15 and a **preferred** ruin exists (6.3, prefOnly): target = 100+ruin, also given to the
    flyers and heroes on its tile (FUN_1d88_109c, unless the hero has 0x80).
  - outside a city: Warlord flyer escort → attack the weakest city of war[p] or of a human
    (REGION_STR + d10, FUN_1d88_1f5a). Otherwise BEST_CITY(mode 1 own), else BEST_CITY(mode 0).
  - inside a city: JOIN(hero, city, 0) (FUN_1d88_0868). If the city has nStrong > 2 and no
    attackTarget, the hero goes to a neighbouring own city that has an attackTarget (joins the
    attack). Otherwise HERO_PLAN (FUN_1d88_0a46): find an own city with an attackTarget, else stop.
    - Flyers idle on the hero's tile: if nStrong < flyers+2, wait. If the hero carries no items:
      nearest item (score dist+50−8·bonus, dist < 40) → 200+i, else any ruin with dist < 40 → 100+i.
      If neither: when NOQ == 0 and heroes ≤ 5, 95% go to the own staging city; otherwise attack the
      weakest war[p] city. The target goes to the hero and its flying escort.
    - No flyers here: if no flyer is already coming, order an idle flyer from the nearest own city
      with a flyer-class attack to come and fetch the hero.
* New computer heroes (FUN_2cad_0438) immediately run NEXT_ERRAND.

### 6.2 NEXT_ERRAND(hero), FUN_1d88_1c60
Allies = own type 10..14 units on the hero's tile. With no Dragon there and position in the NW region
(x<19, y<25): nothing. With < 2 allies: thr = 15 (30 if all allies are Dragons or none). Nearest
ruin (any) with dist < thr (or < 50 with a Dragon) → 100+i. Else nearest item with dist < 30 (< 50
with a Dragon) → 200+i. Set the target on the hero and allies, flag 0x800. With ≥ 2 allies including
a Dragon: Warlord strike (FUN_1d88_1f5a).

### 6.3 Ruin choice and exploration
RUIN_SEARCH(x,y,prefOnly), FUN_1d88_12d6 [H, asm]: over the 40 sites, skip explored ones (map bit
0x8000), Libraries (type 1), Temples (type 3), Seer #1 if 0x2478 and Oracle #7 if 0x247a.
`score = dist + 300 − dice(1,10)`. If the site is on the player's preference list (list A 0x3a68 or
B 0x3a98, chosen once per player with 0x3a60 = dice(1,2,-1); 6 entries each), subtract
[140,120,100,80,40,20][rank] and mark it eligible. Without prefOnly every site is eligible. Lowest
score wins. A loop meant to skip ruins targeted by another hero does nothing (both branches
continue) [H].
EXPLORE (computer hero at the site), FUN_1d88_1803 [H]:
* Types other than 2 and 8: fight the guardian (FUN_307e_07d6). If the hero loses it is removed.
* type 2 (Seer/Oracle): gold += dice(3,1000,800). Sets 0x2478 (site 1) or 0x247a (site 7). The site
  is not marked explored.
* Otherwise mark explored, type=0. Contents assigned at game start (FUN_2de9_0004): the 14 items go
  to random ruins 8..39; the other ruins get min(8, dice(1,6,4)).
  4 item → hero; 5 str += dice(1,2,-1), cap 9; 6 str += dice(1,3,-2), clamp 1..9;
  7 gold += dice(3,1000,500); 8 allies: 2 if dice(1,3)==3 else 1, each sent to BEST_CITY(mode 0)
  with 0x80.
* Afterwards the hero has 0 moves and target −1.

---------------------------------------------------------------------------------------------------
## 7. Hero recruitment: FUN_2cad_0006 (all players) [H]
Skipped when NOQ is set. maxHeroes = 5, or (cities−30)/10+5 if cities ≥ 40. No recruitment if the
player has maxHeroes or the world has 40 heroes. Price: 0 on turn 1, otherwise dice(1,400,300) with no
hero yet, else dice(1,600,600). Offer if gold ≥ price and (dice(1,30) ≤ 6 or turn 1). City: a random
own city. A Warlord computer with > 30 cities instead uses the non-flyer staging city with the
highest d6. **Computer accepts** if turn 1 or price+300 < gold.

---------------------------------------------------------------------------------------------------
## 8. Difficulty, options and computer advantages [H]
* Setup screen (FUN_26d5_0008/030c): each slot cycles Human → Knight → Baron → Lord → Warlord →
  Human. "Difficulty Rating %d%%" = Σ over computer slots of [5,8,11,14][level], shown as 100 if
  > 97. The rating is informational only.
* Level effects, as listed above: Knight has no hero or monster AI, no defence repair, 1 attack group
  and single-wave attacks. Baron adds heroes and repair and allows 2 groups. Lord allows 4 groups,
  multi-wave attacks, early no-garrison expansion, opportunistic retargeting (3.3) and surplus flyers
  joining attacks. Warlord allows 32 groups (capped by cities/4 ground attacks), uses the merged class
  table, deep flyer strikes, truces, a human-focused grudge policy, thrift-based wave control and
  staging-city hero placement.
* **Extra tough mode** (command-line `-T`, 0x2470): at new-game start every non-human slot gets
  Enhance=1. In-game warning "Warning: Computer is in extra tough mode!".
* **Enhance** (in-game options column, 0x209e[p]): build time (t−1)//2+1 for that player, human or
  computer.
* **Observe** (0x208e[p]): show that computer's movements and battles (0xd1c2). It does not change
  any decision.
* "Intense Combat" (0x2088): battle dice d12 instead of d10, for everyone.
* No hidden gold, production or combat-strength bonus for computers was found. Battle code only
  checks human/computer for display purposes. Effective advantages are: free over-spending on turns
  1..5 (negative gold clamped to 0), Seer gold for computer heroes (803..3800) where humans get
  information, and the computer disbanding surplus units to save upkeep.

---------------------------------------------------------------------------------------------------
## 9. Hard-coded Illuria tables (copy verbatim from DGROUP)
* Neighbours: 0x3f8a, 80 × 6 words, 1-based, 0xffff = none (FUN_29b2_000c). Example: Deserton(0) →
  1,9; Bane's Citadel(11) → 8,9,19,21.
* Priority neutral targets 0x43f4 (1-based): 32,37,78,30,40,75.
* Ground penalty list 0x4400 (1-based): 44,45,37,43,46,6,8.
* NW island: cities 2 Beleri, 6 Amenal, 10 Vival; region x<20 & y<26 (x<19 & y<25 in a few places).
* Turn-1 hero targets 0x3b08 [8][4]; ruin preference lists 0x3a68/0x3a98 [8][6] (site indices,
  0 = none), with bonuses 0x3a54.
* Natural enemies 0x3f42/0x3f52; class tables 0x4396/0x43b6; thrift thresholds 0x43ec
  [100,75,50,25]; attack-gold thresholds 0x43de; max attacks 0x43d6 [1,2,4,32]; level names 0x3f04;
  rating 0x3f34 [5,8,11,14].

## 10. Open points / confidence
* FUN_27ed_0006 decompiles as garbage after its switch. The structure in §1 comes from asm
  27ed:0006..061c (jump table at 27ed:04c2: 0,1→0ac4, 2→0b8e, 3,4→10f4 (gold≥50), 5→0cd6) [H].
* The pass-1 skip of 0x20-flagged groups in MOVE_ALL reads a slot pointer whose initial value is
  unclear [L]. Treat it as "groups that already moved together are handled in pass 2".
* The pathfinder FUN_3257_0004 (route choice, terrain, boats) was not decoded. Treat it as
  "shortest path toward target; return arrived / adjacent / blocked by enemy / no path".
* FUN_2c5c_000c and FUN_1cdf_08fc are Ghidra mega-merges that contain copies of the AI code. Ignore them.
* The Accept/Off-with-heads button → handler mapping is inferred from the order of the button table
  at 13fc:09a4/09ba [M].
