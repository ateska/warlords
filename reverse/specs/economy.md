# Warlords (DOS v2.10) — Economy, Setup, City Production, Heroes, Victory

Implementation spec, reverse-engineered from the Ghidra decompilation `/home/claude/gh/d3.c`. Wherever the
decompiler was garbled or dropped a far segment, the code was disassembled (`wl.gdis`, plus the helper
`/home/claude/re/tools/cg.py`, which builds a call graph and annotated disassembly). Struct layouts were
checked against `/home/claude/data/War1.sav` (`/home/claude/re/tools/sav.py` parses it).

Conventions: `DS:x` is a DGROUP offset. Function names use **Ghidra** segment numbers (`FUN_2f0e_0ad8`).
`dice(n,s,p)` = `p + Σ_{n} (int)(rand()/32767.0*s + 1.0)` (FUN_1b90_0026). The arguments are pushed
right to left, so the source order is `dice(n, sides, plus)`. A `rand()` of exactly 32767 returns `s+1`
for that die. This edge case can index past the end of some tables (noted where it applies).
"int8" values are signed C `char`. All arithmetic is 16-bit signed unless stated otherwise.

Confidence tags: **[H]** verified in disassembly and/or the save file, **[M]** read from clean
decompiled code, **[L]** inferred.

---------------------------------------------------------------------------------------------------

## 0. Corrections to NOTES.md (important)

* `FUN_2c5c_000c` is **not** the main loop. It is a 0x130-byte command dispatcher (a jump table on
  `es:[0xbc12]`, see §3.3). Ghidra merged unrelated code into it. The real per-round main loop is
  **`FUN_1312_000e`**. Ghidra inlined a garbled copy of it into `FUN_1260_0004` (main/init).
* Ghidra mislabels several near/far calls. Examples: `FUN_274c_0000` really calls `FUN_277d_0008`
  (= `FUN_277d_0010`, AI production), not `FUN_274c_0318`. `FUN_2f0e_0ad8` calls near `2f0e:1010`
  (unit creation), not `FUN_200c_0030`. On "City full" it calls `2f0e:0fe6`, not `FUN_1fe3_0296`.
* Neutral cities have **no garrison armies**. A neutral city is taken or failed with a single
  percentage roll (§5.9).
* Production options are **static**. The `+0x1A..+0x4B` arrays are never written and are not saved.
  Nothing is randomised at setup.
* There are no starting armies apart from the turn‑1 hero.

---------------------------------------------------------------------------------------------------

## 1. Data structures

### 1.1 Castle / city record — 80 × 100 bytes at DS:0x4632 (file offset 311858) [H]

| off | type | meaning | written by |
|---|---|---|---|
| +0x00 | i16 | x (top-left of the 2×2 city) | static |
| +0x02 | i16 | y | static |
| +0x04 | char[20] | name | static |
| +0x18 | i8 | **defence** (static 3..6, runtime 0..10) | build (+1), conquest (−1), AI (+1) |
| +0x19 | i8 | **owner** 0..7, 15 = neutral | conquest, raze |
| +0x1A | i8[10] | **canProduce[type]** for army types 0..9 | static |
| +0x24 | i8[10] | **buildTime[type]** in turns | static |
| +0x2E | i8[10] | **strength[type]**, copied to army +8 | static |
| +0x38 | i8[10] | **moves[type]**, copied to army +6 and +7 | static |
| +0x42 | i8[10] | **cost[type]** in gp. Paid when production (re)starts. Unit upkeep = cost/2 | static |
| +0x4C | i8 | current production type (0..9). Set to 0xFF when a vector target is lost. Static 0 | prod UI / AI |
| +0x4D | i8 | turns elapsed. Set to 0 on (re)start, +1 on each countdown tick (display only) | prod |
| +0x4E | i8 | **turns left**. 0 = idle / not producing | prod |
| +0x4F | i8 | **port index** 0..12 (0 = no port). Nonzero ⇔ the city can build Navy (§B.1) | static |
| +0x50 | i16 | **income** gp/turn (static per city, never changes) | static |
| +0x52 | i16 | previous owner (static 15). On conquest: `= (old+0x52 == conqueror) ? 15 : oldOwner`. On raze: 15 | conquest/raze |
| +0x54 | i16 | **vector active** flag | prod UI / AI |
| +0x56 | i16 | vector target x (target city's top-left) | |
| +0x58 | i16 | vector target y | |
| +0x5A | i16 | AI: target city index (−1 = none). Also reset to −1 when the vector is cancelled by conquest or raze | AI |
| +0x5C | i16 | static flag, set only for Gunthang(13), Cragmorton(34), Khorfe(74). AI builds only flyers (category 5) there [M] | static |
| +0x5E | i16 | AI: planned army type for +0x5A | AI |
| +0x60 | i16 | AI: planned force size / threat | AI |
| +0x62 | i16 | unused (saved and loaded only) | — |

Static values of +0x4C..+0x63 for every city: `0,0,0,port, income, 15, 0,0,0, -1, island, 0,0,0`.

**Save file (26 bytes per city, FUN_109f_01a5 / FUN_109f_07b4)** [H], in this order:
`+18,+19,+4C,+4D,+4E,+4F (bytes), +50,+54,+56,+58,+5A,+5C,+5E,+60,+62,+52 (words)`.
In War1.sav every city with `+4E>0` satisfies `+4D + +4E == buildTime` (or the Enhance-halved time
when the owner has Enhance on). All 43 cases match.

### 1.2 Army record (24 bytes, 2000 slots, far segment) — fields used by economy code [H]
`+0 x, +2 y` (−1,−1 = not on the map, e.g. in transit). `+4 type` (0xFF = free). `+5 owner` (0xFF = free).
`+6 maxMoves`, `+7 movesLeft`, `+8 strength`, `+9 home city index`.
`+0xA` per-(city,type) serial number (heroes: hero slot 0..39). `+0xC` byte, set to 1 at creation (hits).
`+0xE` word = 0. `+0x10` **upkeep** (i8). `+0x12` flags (bit0 set on alloc; bit 0x40 cleared at turn start).
`+0x14` transit destination city index, or −1. `+0x16` transit state: 100 = just produced,
101 = travelling, −1 = none.
`DS:0xacc8` = slot high-water mark. It is set to 10 at new game, so slots 0..9 start free.
Allocation (FUN_2b32_027c) takes the first slot whose owner is 0xFF and returns NULL when all 2000 are
used. Deletion (FUN_2b32_0318) subtracts `+0x10` from the owner's upkeep total and frees the slot.
Turn-start move reset (FUN_1a12_0000): `movesLeft = min(movesLeft,2) + maxMoves`, applied to
on-map armies only.

### 1.3 Player record — 8 × 20 bytes at DS:0x20de [H for +0,+2,+6,+8; M for the rest]
`+0 id, +2 gold, +4 AI "aggressor" flag, +6/+8 capital x,y, +0xA prodReportAllowed (DS:0x20e8),
+0xC prodReportDone (DS:0x20ea), +0xE` AI flag (set to 1 for odd-numbered AI players),
`+0x10` AI economic stress 0..3, `+0x12` AI.

### 1.4 Other globals
| DS | meaning |
|---|---|
| 0x20ae[8] | city count per player (recounted by FUN_1b90_03f0, also updated incrementally) |
| 0x20be[8] | upkeep total per player (Σ army+0x10). Recomputed every turn by FUN_2e41_01de |
| 0x20ce[8] | income total per player (Σ city+0x50). Recomputed every turn |
| 0x2322[8] | alive |
| 0x7e86[8] | 1 = human, 0 = computer |
| 0x7e96[8] | computer level 0 Knight, 1 Baron, 2 Lord, 3 Warlord (names at DS:0x3f04) |
| 0x209e[8] | **Enhance** (halves build time, §4.6) |
| 0x208e[8] | Observe (show this AI's moves). 0x2086 = global observe |
| 0x2088 | Intense Combat (d12 instead of d10) |
| 0x2470 | "extra tough" (command-line switch `t`) |
| 0x2474 | surrender has been offered (also disables all hero events) |
| 0x2476 | war over (golden age / no humans left). Disables production reports |
| 0xb6d4 | turn number (starts at 1) |
| 0x6cc0[80][10] | unit serial counters (static initial value 1, not reset by a new game) |
| 0x65be[40] | hero slot used. 0xcc88[40][20] = hero names |
| 0xb804[8][8] | hatred matrix, i16, row = AI player |
| 0xcc74[8] | AI current target enemy |

---------------------------------------------------------------------------------------------------

## 2. Game setup

### 2.1 Program start (FUN_1260_0004) [H]
* Command-line switches (first letter, case-folded): `e` EGA, `v` VGA, `x` no mouse, `s` no sound,
  `l` low memory (DS:0x2472), `w` war sound resident, and the undocumented **`t` = extra tough**
  (`DS:0x2470 = 1`).
* `srand(time())` (FUN_1b90_0096, seed stored at DS:0xaa42). This is the only seeding.

### 2.2 New-game setup screen (FUN_26d5_0008, FUN_26d5_030c) [H]
* Initially all 8 players are Human (`0x7e86=1, 0x7e96=0`).
* Clicking player p cycles **Human → Knight(0) → Baron(1) → Lord(2) → Warlord(3) → Human**.
* `Difficulty Rating = Σ_{computer p} T[level]` with `T = [5, 8, 11, 14]` (DS:0x3f34).
  If the sum is greater than 97 it is shown as 100. The rating is display-only.
* "New game" (button 0xF): if `extra tough`, every computer player gets **`Enhance[p] = 1`**.
  That is the only effect of `t` apart from the warning "Computer is in extra tough mode!" shown on
  the first human turn.
* The in-game *Control* panel (FUN_200c_2414/2520/25ac/271c/2796) toggles at any time: Observe
  (computer players only), Human/Computer (restores the saved level), **Enhance (any alive player)**,
  and Intense Combat.

### 2.3 World init (FUN_1312_000e → FUN_1b90_0006 → FUN_16c7_000c, FUN_2de9_0004) [H]
In RNG order:
1. `0x2474 = 0x2478 = 0x247a = 0`, `turn = 1`, `acc8 = 10`, all 2000 army slots freed. AI memory
   (0xb8e6, 8×0x270 bytes) is cleared.
2. The 4 map tiles of each capital get owner bits = p. Capitals come from player records (§B.6).
3. `playerRec[dice(1,8,-1)].+4 = 1` (one random AI-aggressor flag).
4. FUN_274c_0088 (hatred init), for p = 0..7: if p is a computer player, then for j = 0..7:
   `hatred[p][j] = (j==p) ? -1000 : dice(1,3,-1)`, with j in ascending order.
   Then `e = (dice(1,2)==1) ? A[p] : B[p]` with `A=[3,4,5,0,0,6,7,6]`, `B=[4,4,6,7,1,2,2,3]`,
   and `hatred[p][e] += dice(1,3,1)`.
   `0xcc74[p] = -1` for every p.
5. FUN_2de9_0004: ruins and items (owned by the ruins spec).

Everything else comes straight from the EXE's initialised data and is **not reset** (§B.6):
* **starting gold** = `[400, 25, 100, 25, 25, 50, 50, 50]` for players 0..7
* city count = 1 (the capital only)
* income totals `[32, 20, 37, 30, 33, 35, 27, 30]`
* all players alive
* city owners as in the static table: 8 capitals, 72 neutral

**No starting armies.** On turn 1 every player gets one free hero in the capital (§6). Each human
must open the capital's production dialog on turn 1 (§3.2). AI players buy production through the
AI planner (§4.7).

**Neutral garrisons: none.** Neutral cities hold no army records. Attacking one is resolved by the
formula in §5.9.

---------------------------------------------------------------------------------------------------

## 3. Main loop and turn order (FUN_1312_000e) [H]

```
init (seed, setup screen or load, world init); turn = 1
loop forever:                                   # one round
    for p in 0..7: rec[p].reportAllowed = rec[p].reportDone = (warOver != 0)
    # --- phase 1: ALL computer players, in index order ---
    for p in 0..7:
        if alive[p] and not human[p]: AI_turn(p)         # FUN_274c_0000
        (ESC during AI play when no human is alive: turn everyone into humans → observe end)
    # --- phase 2: human players, in index order ---
    for p in 0..7:
        if human[p] and alive[p]:
            start_human_turn(p)                          # FUN_1a12_007e
            event loop until End Turn:
                if rec[p].reportAllowed and not rec[p].reportDone and not warOver
                   and no modal dialog open and not capital-dialog (bc14!=7) and turn > 1:
                    production_phase_human()             # FUN_2f0e_091a
                    rec[p].reportDone = 1
                if turn == 1 and not rec[p].reportDone:
                    open production dialog for capital (FUN_1312_226a); rec[p].reportDone = 1
                handle UI command (FUN_2c5c_000c dispatch)
                on End Turn (cmd 0x16): if surrender_check() == 0 (FUN_1b90_0434): end turn
    end_of_round()                                       # FUN_1b90_0116
    turn += 1
```
**All computer players move before all human players in every round.** This is confirmed in the
disassembly at 1312:0121..01ee and 1312:020e.

### 3.1 AI turn (FUN_274c_0000)
```
show "<Clan> is/are moving!"
current = p; if cities[p] == 0: return        # alive but city-less AIs do nothing
reset_moves(p)                 # FUN_1a12_0000
income_upkeep(p)               # FUN_2e41_0186  §4.1
hero_event(p)                  # FUN_2cad_0006  §6
ai_production(p)               # FUN_277d_0010: transit arrivals then countdown/creation §4.3–4.5
ai_brain(p)                    # FUN_27ed_0006: moves, buys production (§4.7), improves defences, razes ...
```

### 3.2 Human turn start (FUN_1a12_007e)
```
current = p; clear selection
if city at capital(p) is not owned by p: relocate_capital(p)    # §5.8
FUN_31e1_04e0; reset_moves(p); map-flag refresh; centre view on capital
message "<Clan>: Click when ready!"
(once per session) "Warning: Computer is in extra tough mode!" if 0x2470
income_upkeep(p)                                               # §4.1
if hero_event(p) == 0: rec[p].reportAllowed = 1                # otherwise set when the hero dialog closes
```
The production phase (§4.3) therefore runs **after** income/upkeep and after the hero offer has
been resolved.

### 3.3 Commands (FUN_2c5c_000c, jump table cs:0xcc on `0xbc12`) [H]
`12` Raze (FUN_3043_0000), `13` Build (FUN_2c41_0002), `14` Winning (FUN_2e41_0002),
`15` Armies list, `17/18/32` take/drop/inventory items, `22` End Turn (handled in the main loop),
`26` Search ruins (FUN_307e_000c), `27` **Capital = centre the view on the capital only**
(FUN_1a12_0a42), `29` Disband (FUN_2b32_0812), `30` centre on the selected army,
`31` Heroes list, `34` Gold report, `35` Cities report, `36` Production report, `37` Armies report.
Commands 1, 4 and 43 open dialogs 0xC, 4 and 0xB.

---------------------------------------------------------------------------------------------------

## 4. Per-turn economy

### 4.1 Income and upkeep (FUN_2e41_0186 + FUN_2e41_01de) [H]
```
upkeep[p] = Σ army.upkeep for armies with owner == p     # includes armies in transit and allies
income[p] = Σ city.income for cities with owner == p
gold = min(gold + income[p], 30000)
gold = gold - upkeep[p]; if gold < 0: gold = 0
if human[p] and gold < 1: message "Your treasuries are exhausted!"
```
**Running out of gold has no other effect.** Nothing deserts or is disbanded. Production simply
cannot be restarted while gold < cost. AI gold can go negative when the AI buys production on
turns ≤ 5 (§4.7). It is clamped back to 0 at the next upkeep.

### 4.2 Upkeep per unit
`upkeep = cost/2` (C truncation), set at creation (FUN_2f0e_1010):
LI/HI/DW/EA 2, GW 2 (3 where it costs 6), CV 4 (3/5 where it costs 6/10), Navy 10 (9 where it costs 18),
Wolf 4, Pegasi 8, Griffins 8. Heroes 0. Allies: Dragons 4, Demons 4, Devils 4, Wizard 6, Undead 1.

### 4.3 Production phase order (per player turn)
Human (FUN_2f0e_091a): `transit_arrivals(p, human=1)` (FUN_277d_0286(0)), then
`report_index = 0; production_report()` (FUN_2f0e_095c).
AI (FUN_277d_0010): `transit_arrivals(p, human=0)`, then a countdown/creation pass over cities 0..79.

### 4.4 Countdown and unit creation for one city c of the current player [H]
(FUN_2f0e_0ad8 = human, FUN_277d_0010 = AI. Differences are noted.)
```
if c.owner != p or c.turnsLeft == 0: skip
if c.turnsLeft >= 2: c.turnsLeft -= 1; c.elapsed += 1; return NOTHING
# turnsLeft == 1 → try to produce
(dx,dy) = (c.x, c.y)
if c.vector:
    (dx,dy) = (c.vecX, c.vecY); di = index of city at (dx,dy)
    AI only: if di not found or city[di].owner != p:
             c.turnsLeft = 0; c.vector = 0; return       # production stops, no unit
t = c.prodType
if t == NAVY(5):
    (px,py) = (dx,dy) + PORT[c.port]                    # §B.1 (normally the city itself)
    n = units_on_tile(px,py)                            # counts ALL armies on the tile, any owner
    if tileOwner(px,py) == p or n < 1:
        if n < 8: create(c, px,py, dest=-1); msg "<unit> - Produced!"; tileOwner(px,py)=p; return PRODUCED
        else:     msg "%s: Port full. No room to produce." (human); c.turnsLeft = 0   # production stops
    else:
        human: msg "%s: Port occupied by enemy! Cannot produce."; AI: silently
        # turnsLeft stays 1 → retried every turn
elif c.vector:
    create(c, dx,dy, dest=di)                           # unit is created IN TRANSIT
    msg "<unit> -> <dest city>"; return PRODUCED
else:
    for (ox,oy) in [(0,0),(1,0),(0,1),(1,1)]:           # top-left, top-right, bottom-left, bottom-right
        if units_on_tile(c.x+ox, c.y+oy) < 8: create(c, c.x+ox, c.y+oy, -1); msg " - Produced!"; return PRODUCED
    human: msg "%s: City full. No room to produce."; also clears the vector flag of the
           LAST REPORTED city (DS:0xa352) — a bug, see §8
    AI: silently. turnsLeft stays 1 → retried next turn.
```
The **maximum stack is 8**: a tile accepts a new unit while it holds fewer than 8 armies.

`create(c, x, y, dest)` (FUN_2f0e_1010):
```
a = alloc(); if NULL: return            # (human path would then dereference NULL – edge case)
if dest == -1: a.x,a.y = (Navy ? (x,y)+PORT[c.port] : (x,y))   # else stays (-1,-1)
a.type = t; a.owner = p; a.maxMoves = a.movesLeft = c.moves[t]; a.strength = c.strength[t]
a.home = c; a.serial = serial[c][t]++ (starts at 1); a.hits = 1; a.e = 0
a.upkeep = c.cost[t] / 2; upkeep[p] += a.upkeep
c.turnsLeft = 0                                       # cycle finished; must be paid again to continue
if dest == -1: a.transitDest = a.transitState = -1; put on map (FUN_2b32_0252)
else:          a.transitDest = dest; a.transitState = 100
if Navy: tileOwner(port) = p
```
Unit name for messages: `"<city> <Nth> <type>"`, e.g. "Marthos 3rd Light Infantry" (FUN_2b32_0632).

### 4.5 Vectored units in transit (FUN_277d_0286) — run at the start of the owner's production phase [H]
```
for each army a of p (index descending):
    if a.transitState == 100: a.transitState = 101; continue
    if a.transitState == 101:
        d = a.transitDest; a.transitState = a.transitDest = -1
        place on the first of city d's tiles (0,0),(1,0),(0,1),(1,1) holding fewer than 8 units
        if a tile was found and city[d].owner == p: put unit there; human: msg "<unit> reaches <city>"
        else: DELETE the unit (destination full or lost)
```
Timeline: produced in turn T (state 100), turn T+1 becomes 101, **arrives at the start of turn T+2**,
before that turn's production. Total delay = build time + 2 turns.

### 4.6 Starting / restarting production — cost and time [H]
The cost is paid **up front** each time a production cycle starts. There is no refund on Stop or on
a change of production.
`time' = Enhance[p] ? (buildTime-1)/2 + 1 : buildTime` (C int division), e.g. 1→1, 2→1, 3→2, 5→3,
11→6, 15→8.

| path | function | gold check | Enhance applied |
|---|---|---|---|
| City dialog "Prod" (turn 1, captured city, own city) | FUN_2f0e_02b2 | gold < cost → "Not enough gold!" | yes |
| City dialog "Loc" + click target city (vector) | FUN_2f0e_0002 | gold ≥ cost | yes |
| Report "Yes" (keep producing) | FUN_2f0e_0f26 | gold < cost → "You do not have enough gold!" | yes |
| Report "End Report" (auto-yes for the rest) | FUN_2f0e_0f26 + FUN_2f0e_09cc | silently skip if gold < cost | yes |
| **Production screen** "Prod"/"Loc" (Info → Production) | FUN_200c_13f4 | silently ignored if gold < cost | **NO (quirk)** |
| AI | FUN_29b2_0278 | refuse if gold < cost+30 **and** turn > 5 | yes |

Each path does `c.prodType = t; c.elapsed = 0; c.turnsLeft = time'; gold -= cost[t]`.
Prod paths set `c.vector = 0`. Vector paths set `vecX,vecY = target top-left; vector = 1`.
"Keep producing" keeps the existing vector.
**Stop** (FUN_2f0e_03b6 / screen button 0x62): `turnsLeft = 0; vector = 0`.

### 4.6a Human production report (FUN_2f0e_095c / 0f0c, buttons 0x17/0x18/0x19) [H]
```
report_index = 0 at phase start
loop: if report_index == 79: report_index = 0; return          # quirk: city 79 can be skipped (§8)
      while report_index < 80:
          r = countdown_and_create(report_index); report_index += 1
          if r == PRODUCED: show "<msg>\nKeep producing these?" [Yes][No][End Report]; return
Yes        → restart city (pay, §4.6), continue loop
No         → city stays idle AND its vector is cancelled (FUN_2f0e_0fe6: vector = 0), continue loop
End Report → restart this city (Yes), then for all remaining cities (report_index..79):
             countdown_and_create; if produced, gold ≥ cost and turnsLeft == 0: restart silently
```
Failure messages (port/city full, port occupied) are shown as plain messages without the dialog.

### 4.7 Vectoring rules [H]
* Human small dialog: the "Loc" button is disabled when the selected type is Navy or the player owns
  only 1 city. The click must land on a city tile owned by the player and different from the source.
  At most **4** cities may vector to the same target ("full" icon otherwise).
  Message "Production transferred from %s to %s".
* Production screen: the click picks the nearest own city within distance 6 (FUN_3257_1b8f), with
  the same limit of 4. Production is (re)started without Enhance.
* Conquest or raze of a target city: every city vectoring to it gets `turnsLeft = 0, vector = 0,
  vecX = vecY = 0, prodType = 0xFF`. This applies to cities of any owner. The captured or razed
  city's own vector is cleared (`vector = 0, +0x5A = -1`).

### 4.8 AI production choice (summary; details belong to the AI spec) [M]
The planner FUN_27ed_0006 / FUN_27ed_11c8 calls choosers FUN_29b2_0ac4/0b8e/0cd6/129e, which then call
FUN_29b2_0278. For example, 0ac4 picks the producible non-Navy type with minimum time (ties: higher
strength); in island cities (+0x5C) only flyers are allowed. 0b8e scores `10-(str-time)`, with
`-dice(1,2)` for flyers. The AI type-category table DS:0x4376 is copied at each AI turn from
DS:0x43b6 for Warlord level, otherwise from DS:0x4396.
AI defence improvement (FUN_29b2_0350, level > 0 only): if `gold > 5`, `def < 3` and
`gold > DEFCOST0[def] + 200`, then `def += 1; gold -= DEFCOST0[def]` (in practice 50 gp, cap 3).

---------------------------------------------------------------------------------------------------

## 5. City actions

### 5.1 Build (cmd 13, FUN_2c41_0002 → dialog FUN_1888_0878 → Yes FUN_2c41_0144) [H]
Requires a selected stack. The terrain class of the stack's tile decides the action:
* **City (class 10)**, owned by the current player (else silently nothing):
  if `def > 9` → "Your defences are already legendary!". Otherwise the
  **cost is `DEFCOST[def+1]`** with `DEFCOST = [50,50,50,50,75,100,150,175,350,500,800]`
  (far table at seg 0x306d, read at offset +2).
  So def 0→50, 1→50, 2→50, 3→75, 4→100, 5→150, 6→175, 7→350, 8→500, 9→800. **Maximum defence 10.**
  The dialog shows "Improve City Defences? / Current Defences: %d / Improvement cost %d gp".
  Yes: `def += 1`, `gold -= cost`, "You have improved your defences!".
* **Plain (class 7)**: Build a Tower, **cost 100**. Yes: map tile index ← `p+2` (tower of player p,
  class 9), `gold -= 100`, "You have built a tower!".
* Anything else → "Towers must be built on plains!". Gold < cost → "You do not have sufficient gold!".

### 5.2 Raze (cmd 12, FUN_3043_0000 / 009a / 01d8) [H]
Allowed only when the stack stands on a city or tower tile owned by the current player
(else "You can only raze cities and towers"). The dialog offers [Raze it!] [Cancel]. No cost.
* **Tower**: tile index ← 12 (ruins, class 11), "The tower is destroyed!".
* **City**:
  ```
  income[p] -= c.income; cities[p] -= 1; c.owner = 15; c.prevOwner = 15
  4 city tiles: index ← 12 (ruins, class 11)          # the city leaves play for good
  if c.vector: c.vector = 0; c.+5A = -1
  every city vectoring to c: turnsLeft=0, vector=0, vec=0, prodType=0xFF
  if c is p's capital: relocate_capital(p)
  for i in 0..7: hatred[i][p] += 1                     # everyone hates the razer more
  "Your troops ravage %s!" (picture), then "%s is in ruins!"
  ```

### 5.3 Capital (cmd 27)
Centres the view on the capital and nothing else. The capital cannot be chosen by the player. It
moves automatically (§5.8).

### 5.4 Disband (cmd 29, FUN_2b32_0812 → FUN_2b32_08a8) [H]
"Disband this army?" / "Disband these armies?". Deletes every selected non-hero army, with no refund
(the upkeep total drops at once). A selection of heroes only → "You cannot disband heroes!".

### 5.5 Change production — §4.6. Buying units outright is not possible.

### 5.6 Capturing an owned city (FUN_2289_09c0, return 0x21) [H]
Applies when the defender owner `L` is a player (0..7):
```
if not human[L]: hatred[L][W] += 2
g = (cities[L] < 2) ? gold[L] : gold[L] / cities[L];  g = g/2;  if g < 0: g = 0
gold[W] += g; gold[L] -= 2*g;  human W and g>0: "Your armies pillage %d gp!"
c.prevOwner = (c.prevOwner == W) ? 15 : L
c.owner = W; c.turnsLeft = 0                     # production stops; prodType kept
if c.def > 0: c.def -= 1                         # every conquest knocks a level off
4 tiles → graphic 0x5A + 4*W + i, owner bits W
income[W] += c.income; cities[W] += 1; cities[L] -= 1; income[L] -= c.income
if c was L's capital: relocate_capital(L)
vector cleanup as in §4.7
human W: open the production dialog for c (FUN_1312_226a)
```
Capturing a tower tile (class 9) sets its index to `W+2`.

### 5.7 Tower/terrain index notes
Map tile index → class (DS:0x3934): 0 plain, 1..9 tower (2+p = player p's tower), 10..12 ruins,
86..89 neutral city, 90+4p..93+4p player p's city corners (0 TL, 1 TR, 2 BL, 3 BR).

### 5.8 Capital relocation (FUN_2289_1075) [H, BUG reproduced]
Intended: the nearest owned city with squared distance < 1,000,000. The threshold is never updated,
so the result is **the owned city with the highest index**. `capital(p) = city[max i : owner==p]`.
Nothing happens if p owns no city. Triggered at the start of a human's turn (capital not owned), on
capture of the capital and on razing the capital.

### 5.9 Attacking a neutral city (FUN_2491_000a human / FUN_2491_0341 AI) [H]
No defenders exist. After the normal combat setup (FUN_23cd_000c computes each attacker's
modified strength `S_i` with all bonuses, capped at 9, over the attacking stack sorted by type)
the code does:
```
score = Σ_{i=0..n-1} S_i * (i+1)          # weighted by position in the sorted stack
roll  = dice(1,100,0)
if roll <= 110 - 10*city.def + score:   CAPTURED
    c.owner = p; income[p] += c.income; cities[p] += 1; tiles → p's graphics
    (no pillage, defence NOT reduced, prevOwner unchanged, production state unchanged but idle)
    human: "You are victorious!", production dialog for c
else:                                    ALL attacking units are destroyed (heroes drop items first)
    human: "You have been defeated!"
```
Example: defence 4, a single LI (S=3): P(win) = (110−40+3)/100 = 73%.

---------------------------------------------------------------------------------------------------

## 6. Heroes (FUN_2cad_0006 emergence/offer, FUN_2cad_0438 creation, FUN_2cad_030e payment/allies) [H]

Called once per player turn, after income. RNG order is exact:
```
if surrenderOffered: return 0
maxHeroes = 5 if cities[p] < 40 else (cities[p]-30)/10 + 5       # 40..49→6 … 80→10
total = #armies of type HERO(15) (any owner); own = # owned by p; hadHero = own > 0
if total == 40 or own >= maxHeroes: return 0
price = (turn==1) ? 0 : hadHero ? dice(1,600,600) : dice(1,400,300)   # 601..1200 / 301..700
if gold[p] < price: return 0
r = dice(1,30,0)
if r > 6 and turn != 1: return 0                                   # 20% per turn (always on turn 1)
k = dice(1, cities[p], 0)
city = -1
if level[p]==3 and not human[p] and cities[p] > 30:                # Warlord AI: smart pick
    best = 0
    for i in 79..0: if owner(i)==p and i.+5A != -1 and CAT[i.+5E] != 5:
        d = dice(1,6,0); if d > best: best = d; city = i
if city == -1: city = the k-th (1-based) city of p in index order
if human[p]:
    turn 1: "In %s, a hero emerges!" → name dialog (default = random name, editable) → create
    else:   dialog "A hero in %s offers / to join you for %d gp! / You have %d gp" [Accept][Reject]
            Accept → name dialog → create (+ pay, allies); Reject → nothing
else:
    if turn == 1 or price + 300 < gold[p]: create(random name)      # otherwise declines
return 1                                                            # an event occurred
```
**Hero creation (FUN_2cad_0438)**:
* Take the first free slot of 40 (`0x65be`) and store the name there. The name "SUPERVISOR" turns on
  cheat mode ("Supervisor Mode is on!", DS:0x2080).
* Tile: humans and turn 1 try the city tiles (0,0),(1,0),(0,1),(1,1) in that order. AI on later
  turns uses the reverse order. The first tile with fewer than 8 units wins. If none is free, there
  is no hero (and no payment).
* Stats: `type 15, maxMoves = movesLeft = (turn==1 ? 12 : 16), strength 5, home = city,
  serial = slot, hits 1, upkeep 0`. The turn‑1 hero therefore keeps 12 base moves; later heroes
  have 16.
* If `turn > 1`: pay (FUN_2cad_030e): `gold -= price`, heroesHired++.
  **Allies only if the player already had a hero (`hadHero`)**:
  ```
  if dice(1,100,0) < 75:                      # 74%
      type = dice(1,5,-1)                     # 0..4 → template §B.4
      cnt  = ALLYCNT[dice(1,7,-1)]            # [1,1,2,2,2,2,3]
      human: "And the hero brings %d allies!"
      repeat cnt: place_ally(type, heroX, heroY)
  ```
  `place_ally` (FUN_307e_1320) tries up to 10 times. The tile qualifies if (count, +1 when it is the
  hero's own tile) < 8 and (owned by p or empty). Otherwise `x += dice(1,3,-2); y += dice(1,3,-2)`
  (a cumulative random walk). The ally copies type, moves, strength and upkeep from the template,
  with `home = 0`, `serial = 0`, owner p, and adds its upkeep.
* **Names** (FUN_1888_0fe2): `i = dice(1,63,-1)`, name = `HERONAME[i] + SUFFIX[0xae24]`. The "used"
  flags (DS:0xb32e) are never set, so the first pick always succeeds and names can repeat. The suffix
  index starts at 0 (empty suffix). The suffix branch (all 63 flags used) is unreachable in practice.
* When a hero dies (FUN_2289_139e) its slot is freed and its items are dropped.

---------------------------------------------------------------------------------------------------

## 7. Victory, defeat, reports

### 7.1 End of round (FUN_1b90_0116) [H]
```
recount cities (FUN_1b90_03f0)
for p in 0..7: if alive[p] and cities[p] == 0:
    delete all of p's armies (heroes drop items first)
    human: "Wretched  %s!  For you, the war is over!"   (two spaces, sic)
    AI:    "%s are no longer a threat!"
    alive[p] = 0; gold[p] = 0
if nobody alive: farewell messages, exit to DOS
if no alive human but some human player exists: warOver=1, "As no further human resistance is
   possible the battle for Illuria will continue without you ..." (observe mode)
if not warOver and exactly 1 alive human and 0 alive AI:
   warOver=1, "Player %d, %s: You have won!", "You now rule all of Illuria ..."
```
A player is eliminated **only by having 0 cities at the end of a round**. Armies do not count.

### 7.2 Surrender offer (FUN_1b90_0434, run when a human presses End Turn) [H]
```
if surrenderOffered: return 0 (end turn)
recount cities; H = #alive humans
if H == 0 and !DS:0x2082: "And so the war continues..." "...without you!"; return 0
h = cities of the (last) alive human; m = max cities among alive AIs
if h > 40 and H == 1 and h > m + 15:
    surrenderOffered = 1      # permanently disables hero events and future offers
    "Your seneschal reports strangers at the gate!", "Crawling towards you they humbly present a scroll"
    scroll: "MIGHTY WARLORD!! The fickle tides of war have turned your way ..."
    [Accept a grovelling surrender!] → FUN_1b90_0666: warOver=1, all players set human (AI stops),
        "Under your enlightened rule ... Illuria has entered a new golden age ... You may now inspect your domain."
    [Off with their miserable heads!] → FUN_1b90_0730: "No Quarter !!!"; for every alive i and alive j:
        hatred[i][j] = human[j] ? dice(1,1000,100) : 0; and for human j: aiTarget[i] = current player
    return 1 (the turn continues; End Turn must be pressed again)
return 0
```
The surrender test is "more than 40 cities and 15 more than the strongest AI". It is not 2/3 of the
cities.

### 7.3 Report bars (display only) [H]
* **Winning** (FUN_2e41_0002), alive players only:
  `score = (gold + upkeep + 5*income + Σ_{owned c} c.income*c.def) / 30`, computed in 32 bits,
  clamped to 1..500. Dead players score 0.
* Gold: `gold/20` clamped to 1..500. Cities: `cities*500/80`. Armies: FUN_2e41_069c.
  Produce: FUN_2e41_0856.

---------------------------------------------------------------------------------------------------

## 8. Quirks and bugs to reproduce
1. AI players always move before humans within a round (§3).
2. Capital relocation picks the highest-index owned city, not the nearest (§5.8).
3. The Production screen (FUN_200c_13f4) ignores Enhance when setting build time. The other paths
   apply it.
4. Production report: if a dialog is raised for city 78, city 79 (Marthos) is skipped for that
   turn's countdown (FUN_2f0e_095c returns early when the index equals 79).
5. "City full" on the human path clears the vector flag of DS:0xa352 (the last city that raised a
   report dialog), not the full city's own flag.
6. The cost is paid at the start of every cycle with no refunds. Changing production mid-cycle wastes
   the gold already paid.
7. AI may buy production with insufficient gold during turns 1..5, so gold can go negative (§4.6).
8. Hero names repeat because the used flags are never set. The suffix table skips " VIII".
9. Allies only accompany a player's second and later heroes. The turn‑1 hero has 12 base moves,
   later heroes 16.
10. `dice(1,5,-1)` / `dice(1,7,-1)` can return 5 / 7 on `rand()==32767`, which reads an all-zero ally
    template / an out-of-table count (≈1/32768).
11. Starting gold, serial counters and the hero-name state are static data and are not
    reinitialised for a new game in the same session (there is no "new game" without restarting
    the program).
12. A vectored unit whose destination is full or lost on arrival is silently deleted.

## 9. Confidence summary and open points
* [H]: castle layout and save mapping, income/upkeep, production countdown/creation/transit,
  restart costs, Enhance, build/raze/disband costs and effects, hero emergence and allies, neutral
  capture formula, victory/elimination/surrender, turn order.
* [M]: meaning of the AI-only city fields (+0x5A/+0x5C/+0x5E/+0x60) and player record
  +4/+0xE/+0x10/+0x12. Dialog 0xF, opened by clicking an already-selected item in the city dialog,
  was not decoded (it seems to be UI only).
* Not covered here: AI decision logic (FUN_27ed_*, FUN_29b2_*, FUN_24ef_*, FUN_1d88_*), the combat
  strength bonuses inside FUN_23cd_000c (city defence bonus table §B.3 is included), ruins/items.

---------------------------------------------------------------------------------------------------

## Appendix B — tables

**B.1 Port offsets** (far seg 0x3073, dx at +0, dy at +0x1A), index = city+0x4F:
```
idx: 0  1  2  3  4  5  6  7  8  9 10 11 12
dx : 0  0  1  2  2  2  2  1  0 -1 -1 -1 -1
dy : 0 -1 -1 -1  0  1  2  2  2  2  1  0 -1
```
The offsets go clockwise around the 2×2 city starting above the top-left tile. All 25 Navy cities
have port ≠ 0, and their port tile is terrain class 3 (Shore) on ILLURIA.MAP (verified).

**B.2 Defence improvement cost** (seg 0x306d): `DEFCOST0 = [50,50,50,50,75,100,150,175,350,500,800]`.
Human cost = `DEFCOST0[def+1]`. AI cost = `DEFCOST0[newDef]`.

**B.3 City defence combat bonus** (seg 0x3043+0): `def 0..10 → [0,0,1,1,1,1,1,2,2,3,3]`
(used by FUN_23cd_000c when the defender stands in a city).

**B.4 Ally templates** (seg 0x307b, 24-byte army records):
| idx | type | moves | str | upkeep |
|---|---|---|---|---|
| 0 | Dragons (12) | 18 | 8 | 4 |
| 1 | Demons (13) | 14 | 7 | 4 |
| 2 | Devils (14) | 12 | 8 | 4 |
| 3 | Wizard (10) | 50 | 6 | 6 |
| 4 | Undead (11) | 12 | 7 | 1 |
Ally count table DS:0x6608 = `[1,1,2,2,2,2,3]`.

**B.5 Hero names** (DS:0x2a1c, 63): Comte d'Trout, Baron Roger, Sir Gregor, Don Stephano, Earl Steven,
Brus sans Pitie, Brus avec Pitie, Sir Ector, Sir Kay, Sir Gawain, Alex the Black, Rowan the Red, Lord Graeme,
Viscount Nick, Green Knight, Duke Tintagel, Manx Andrew, Sir Gareth, Sir Mordred, Sir Lancelot, Sir Galahad,
Sir Bors, Sir Lamerok, Sir Percivale, Sir Palomides, Angwyshaunce, Lord Melyodas, Sir Tristram, Brandegoris,
Clarivaunce, Morganoure, Byrhtnoth, Eadric, Wulfstan, Aelfere, Wulfmaer, Eadweard, Aelfnoth, Aelfwine, Aelfric,
Ealhelm, Godric, Leofsunu, Aescferth, Ecglaf, Sibyrht, Aethelstan, Robin Hood, Little John, Will Scarlet,
Friar Tuck, Beowulf, Lady Lai, Baroness Lucy, Countess Phil, Countess Lyn, Lady Donna, Joan d'Arc, Lord Falkner,
Lady Janeen, Siegfried, Attila the Hut, S.C.Fawkner.
Suffixes DS:0x2a06: `"", " II", " III", " IV", " V", " VI", " VII", " IX", " X", " XI", " XII"`.

**B.6 Initial player records** (DS:0x20de; id, gold, capital):
| p | clan | gold | capital (city #) | income |
|---|---|---|---|---|
| 0 | Sirians | 400 | Marthos (79) 62,143 | 32 |
| 1 | Storm Giants | 25 | Stormheim (61) 19,107 | 20 |
| 2 | Grey Dwarves | 100 | Khamar (32) 39,62 | 37 |
| 3 | Orcs of Kor | 25 | Kor (53) 100,90 | 30 |
| 4 | Elvallie | 25 | Elvallie (72) 41,124 | 33 |
| 5 | Selentines | 50 | Enmouth (20) 7,39 | 35 |
| 6 | Horse Lords | 50 | Dunethel (37) 60,71 | 27 |
| 7 | Lord Bane | 50 | Bane's Citadel (11) 92,24 | 30 |

**B.7 Army type summary** (typical values. Per-city values in Appendix A take precedence):
GW Giant Warriors str6 mv12 4gp, HI str5 mv8 4gp, LI str3 mv10 4gp, DW Dwarven Legion str5 mv9 4gp,
CV Cavalry str6 mv16 8gp, NV Navy str5 mv18 20gp, EA Elven Archers str4 mv12 4gp, WR Wolf Riders str5 mv14 8gp,
PG Pegasi str4 mv16 16gp, GR Griffins str5 mv16 16gp.
Typical build times when producible: HI 2, LI 1, CV 4–6, NV 11, EA 1–3, WR 3, PG 5–7, GR 5–8.

---------------------------------------------------------------------------------------------------

## Appendix A — the 80 cities (static data from DS:0x4632)

`own`: owner at game start (Sir/StG/GrD/Ork/Elv/Sel/HoL/Ban, `-` = neutral). `inc` = income.
`port` = +0x4F. `isl` = +0x5C.
Production options list only the producible slots (`canProduce` = 1):
`TYPE time/cost s=strength m=moves`. Codes: GW Giant Warriors, HI Heavy Inf, LI Light Inf,
DW Dwarven Legion, CV Cavalry, NV Navy, EA Elven Archers, WR Wolf Riders, PG Pegasi, GR Griffins.

| # | name | x,y | def | own | inc | port | isl | production options  `type time/cost s=str m=moves` |
|---|---|---|---|---|---|---|---|---|
| 0 | Deserton | 93,1 | 4 | - | 20 | 11 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 1 | Zaigonne | 83,4 | 4 | - | 20 | 2 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 2 | Beleri | 15,5 | 6 | - | 35 | 1 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 6/8 s6 m16; NV 11/20 s5 m18 |
| 3 | Tal | 51,6 | 4 | - | 16 | 10 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 4 | Minbourne | 70,6 | 4 | - | 25 | 1 | 0 | LI 1/4 s3 m10; NV 11/20 s4 m18 |
| 5 | Tirfing | 68,11 | 4 | - | 23 | 0 | 0 | LI 2/4 s4 m9 |
| 6 | Amenal | 12,14 | 4 | - | 16 | 0 | 0 | LI 1/4 s3 m10 |
| 7 | Pareth | 57,16 | 5 | - | 22 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 5/8 s5 m14 |
| 8 | Ungor | 87,18 | 4 | - | 20 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10 |
| 9 | Gorag | 94,18 | 4 | - | 19 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10 |
| 10 | Vival | 6,19 | 3 | - | 12 | 0 | 0 | LI 1/4 s3 m10 |
| 11 | Bane's Citadel | 92,24 | 6 | Ban | 30 | 0 | 0 | GW 4/4 s6 m10; LI 1/4 s3 m10; CV 4/8 s6 m16; WR 3/8 s5 m14 |
| 12 | Needleton | 56,27 | 4 | - | 24 | 0 | 0 | LI 1/4 s3 m10 |
| 13 | Gunthang | 32,30 | 5 | - | 25 | 0 | 1 | HI 2/4 s5 m8; EA 3/4 s4 m12; PG 5/16 s4 m16 |
| 14 | Deephallow | 60,30 | 4 | - | 23 | 0 | 0 | LI 1/4 s3 m10 |
| 15 | Ak-Giriel | 28,31 | 4 | - | 20 | 0 | 0 | HI 2/4 s5 m8; EA 3/4 s4 m12; PG 7/16 s4 m16 |
| 16 | Ak-Enlie | 20,34 | 4 | - | 20 | 0 | 0 | HI 2/4 s5 m8; EA 3/4 s4 m12 |
| 17 | Ak-Farzon | 33,34 | 4 | - | 20 | 0 | 0 | HI 2/4 s5 m8; EA 3/4 s4 m12 |
| 18 | Meneloth | 67,37 | 5 | - | 25 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 5/8 s5 m15 |
| 19 | Malikor | 98,37 | 4 | - | 16 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 6/8 s6 m13 |
| 20 | Enmouth | 7,39 | 6 | Sel | 35 | 10 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 4/8 s6 m20; NV 8/20 s6 m18 |
| 21 | Argrond | 88,39 | 4 | - | 17 | 0 | 0 | HI 2/4 s6 m7; LI 1/4 s3 m10 |
| 22 | Barthel | 32,40 | 5 | - | 21 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10 |
| 23 | Marton | 18,45 | 4 | - | 20 | 1 | 0 | HI 2/4 s4 m8; LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 24 | Waybourne | 4,51 | 4 | - | 22 | 11 | 0 | HI 2/4 s5 m8; NV 11/20 s5 m18 |
| 25 | Dethal | 98,51 | 4 | - | 20 | 0 | 0 | LI 1/4 s3 m10; WR 5/8 s5 m14 |
| 26 | Greenweigh | 29,52 | 4 | - | 20 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; DW 3/4 s5 m9 |
| 27 | Upway | 46,53 | 3 | - | 13 | 0 | 0 | LI 2/4 s3 m10 |
| 28 | Darclan | 91,55 | 4 | - | 19 | 0 | 0 | LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 29 | Maridun | 57,57 | 4 | - | 18 | 0 | 0 | LI 2/4 s3 m10; CV 3/8 s6 m18 |
| 30 | Jessarton | 6,58 | 4 | - | 19 | 11 | 0 | LI 3/4 s2 m10; NV 12/20 s3 m18 |
| 31 | Zhoran | 28,61 | 5 | - | 25 | 0 | 0 | DW 1/4 s5 m9; GR 5/16 s5 m16 |
| 32 | Khamar | 39,62 | 6 | GrD | 37 | 0 | 0 | DW 2/4 s5 m9; GR 5/16 s6 m18 |
| 33 | Upbourne | 11,63 | 4 | - | 17 | 11 | 0 | HI 2/4 s5 m8; NV 11/20 s5 m18 |
| 34 | Cragmorton | 34,65 | 4 | - | 23 | 0 | 1 | DW 2/4 s5 m9; GR 7/16 s5 m16 |
| 35 | Paynor | 83,65 | 3 | - | 18 | 0 | 0 | LI 2/4 s3 m10 |
| 36 | Carmel | 19,70 | 5 | - | 20 | 0 | 0 | LI 2/4 s5 m12 |
| 37 | Dunethel | 60,71 | 6 | HoL | 27 | 0 | 0 | LI 1/4 s3 m10; CV 3/6 s6 m19 |
| 38 | Derridon | 54,72 | 4 | - | 20 | 0 | 0 | LI 2/4 s3 m9; CV 4/8 s6 m18 |
| 39 | Fleymark | 68,73 | 4 | - | 20 | 0 | 0 | LI 1/4 s3 m10; CV 3/6 s6 m18 |
| 40 | Pa-Kur | 86,79 | 5 | - | 25 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 4/8 s6 m16 |
| 41 | Ar-Arak | 95,79 | 5 | - | 26 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 4/8 s6 m16 |
| 42 | Dhar-Khosis | 37,80 | 6 | - | 30 | 0 | 0 | HI 2/4 s5 m8; DW 2/4 s5 m9; GR 6/16 s5 m16 |
| 43 | Citadel of Fire | 59,81 | 5 | - | 24 | 4 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 44 | Citadel of Ice | 63,81 | 5 | - | 26 | 11 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 45 | Hithos | 20,84 | 6 | - | 28 | 1 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 5/8 s6 m16; NV 10/20 s5 m20 |
| 46 | Ubar | 48,85 | 4 | - | 20 | 8 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 47 | Galin | 41,87 | 4 | - | 20 | 2 | 0 | LI 1/4 s3 m10; CV 8/10 s6 m16; NV 11/20 s5 m18 |
| 48 | Herzag | 78,87 | 4 | - | 23 | 11 | 0 | LI 1/4 s3 m10; NV 13/20 s5 m15; WR 3/8 s5 m14 |
| 49 | Gimlad | 89,87 | 4 | - | 20 | 0 | 0 | LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 50 | Vernon | 48,89 | 5 | - | 24 | 4 | 0 | HI 3/4 s5 m7; LI 1/4 s3 m10; NV 11/20 s6 m18 |
| 51 | Thurtz | 85,89 | 4 | - | 18 | 0 | 0 | LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 52 | Kazrak | 58,90 | 4 | - | 21 | 11 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 53 | Kor | 100,90 | 6 | Ork | 30 | 0 | 0 | GW 5/6 s6 m10; HI 2/4 s5 m8; WR 3/8 s5 m14 |
| 54 | Ilnyr | 71,93 | 4 | - | 21 | 9 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 55 | Ohmsmouth | 7,94 | 5 | - | 24 | 10 | 0 | HI 2/4 s5 m8; NV 10/18 s5 m18 |
| 56 | Himelton | 22,95 | 3 | - | 14 | 0 | 0 | LI 1/4 s3 m10; CV 6/8 s5 m16 |
| 57 | Wellmore | 4,103 | 4 | - | 20 | 11 | 0 | HI 2/4 s5 m8; NV 11/20 s5 m18 |
| 58 | Balad Naran | 90,103 | 6 | - | 29 | 1 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; NV 11/20 s5 m18; WR 2/8 s6 m15 |
| 59 | Lador | 31,105 | 4 | - | 16 | 0 | 0 | LI 1/4 s3 m10 |
| 60 | Duinoth | 68,105 | 4 | - | 19 | 0 | 0 | LI 1/4 s3 m10; CV 5/8 s6 m16 |
| 61 | Stormheim | 19,107 | 6 | StG | 20 | 0 | 0 | GW 2/4 s6 m12 |
| 62 | Angbar | 54,109 | 4 | - | 20 | 0 | 0 | LI 1/4 s3 m10; CV 4/8 s5 m16 |
| 63 | Ssuri | 59,111 | 4 | - | 19 | 0 | 0 | LI 1/4 s3 m10; CV 4/8 s5 m16 |
| 64 | Tasme | 8,112 | 4 | - | 19 | 5 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 65 | Argenthorn | 42,113 | 4 | - | 22 | 0 | 0 | HI 2/4 s5 m8; EA 1/4 s4 m12; PG 7/16 s4 m16 |
| 66 | Troy | 56,114 | 3 | - | 13 | 0 | 0 | LI 1/4 s3 m10; CV 4/8 s6 m15 |
| 67 | Garom | 87,114 | 4 | - | 20 | 0 | 0 | LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 68 | Quiesce | 15,119 | 4 | - | 21 | 11 | 0 | LI 1/4 s3 m10; NV 11/20 s5 m18 |
| 69 | Varde | 8,121 | 4 | - | 23 | 2 | 0 | LI 1/4 s3 m10; CV 5/8 s5 m16; NV 11/20 s5 m18 |
| 70 | Charling | 48,121 | 3 | - | 16 | 0 | 0 | LI 1/4 s3 m10 |
| 71 | Herueth | 65,122 | 6 | - | 26 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 6/8 s6 m16 |
| 72 | Elvallie | 41,124 | 6 | Elv | 33 | 0 | 0 | HI 2/4 s5 m10; EA 1/4 s4 m12; PG 6/16 s4 m16 |
| 73 | Gildenhome | 33,125 | 5 | - | 24 | 0 | 0 | HI 2/4 s5 m8; EA 1/4 s4 m12; PG 7/16 s4 m16 |
| 74 | Khorfe | 8,129 | 5 | - | 26 | 0 | 1 | DW 2/4 s5 m9; GR 8/16 s5 m16 |
| 75 | Gluk | 84,129 | 4 | - | 17 | 0 | 0 | GW 3/4 s6 m10; LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 76 | Loremark | 43,132 | 4 | - | 21 | 0 | 0 | HI 2/4 s5 m8; EA 1/4 s4 m12; PG 7/16 s4 m16 |
| 77 | Gork | 86,132 | 4 | - | 15 | 0 | 0 | GW 3/4 s6 m12; LI 1/4 s3 m10; WR 3/8 s5 m14 |
| 78 | Alfar's Gap | 22,141 | 4 | - | 18 | 0 | 0 | LI 1/4 s3 m10; CV 5/8 s5 m16 |
| 79 | Marthos | 62,143 | 6 | Sir | 32 | 0 | 0 | HI 2/4 s5 m8; LI 1/4 s3 m10; CV 4/8 s6 m16; PG 7/16 s5 m15 |
