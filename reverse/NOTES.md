# Warlords (DOS, v2.10, SSG 1990) reverse-engineering notes — shared context

## Files
- Original EXE: /home/claude/data/WARLORDS.EXE (332182 bytes, MZ, Microsoft C 5.x 1988, medium/large model, header 0x3000 bytes)
- Patched EXE (MS FP-emulator INT 34h-3Dh replaced by real x87 opcodes): /home/claude/data/WARLORDS_P.EXE
- Ghidra decompilation of the patched EXE, all 822 functions, with string literals annotated inline
  as `0x1234/*"text"*/`: **/home/claude/gh/d3.c** (1.2 MB). Each function starts with a line
  `// ==== NAME @ SEG:OFF`. Use grep/awk/sed on it (e.g. `awk '/^\/\/ ==== FUN_2289_067a/,/^\/\/ ==== FUN_2289_090f/' d3.c`).
- Python helper: /home/claude/re/wl.py  (`cd /home/claude/re; python3 -c "from wl import *; gdis(0x2289,0x67a,600)"`)
  - `gdis(ghidra_seg, off, nbytes, stop_ret=True)` disassembles (capstone, x87 patched) using GHIDRA segment numbers.
  - `IMG` = load image (file minus header). `DSB` = linear offset of DGROUP in IMG. `dsstr(off)`, `dsw(off)` read DGROUP data.
  - `xrefs(dsoff)` finds code bytes referencing a 16-bit immediate (heuristic).
- Save game sample: /home/claude/data/War1.sav (53330 bytes) — useful to validate struct layouts.
- Map: /home/claude/data/ILLURIA.MAP (109 x 156 words)

## Address conventions
- Ghidra segment = image segment + 0x1000. Ghidra function FUN_2289_067a == image 1289:067a.
- DGROUP (DS) is image segment 0x44c0 (Ghidra 0x54c0). File offset of DS:0 = 293888 (0x47c00).
  So `DS:x` file offset = 293888 + x. Ghidra prints DS-relative constants like `*(int *)0x7ea6`.
- CAUTION: many globals live in other (far BSS) segments; the code loads ES from a table of segment
  words at DS:0x9302..0x93xx before accessing e.g. `es:[0xbc1e]`. Ghidra drops the segment, so two
  different variables may print with the same offset. When in doubt, disassemble with gdis().
- Runtime library: rand = FUN_39e5_2c92 (MS C LCG: seed = seed*0x343FD + 0x269EC3; return (seed>>16)&0x7FFF),
  srand = FUN_39e5_2c80, sprintf = FUN_39e5_24c2, chkstk = FUN_39e5_0264, __ftol = FUN_39e5_38da, abs = FUN_39e5_2c6a?
- `dice(n, sides, plus)` = FUN_1b90_0026 = plus + sum_{n times} (int)(rand()/32767.0*sides + 1.0)   (i.e. nDs + plus)

## Known data (DGROUP offsets)
- 0x7ea6: current player index (0..7). Clans: 0 Sirians, 1 Storm Giants, 2 Grey Dwarves, 3 Orcs of Kor,
  4 Elvallie, 5 Selentines, 6 Horse Lords, 7 Lord Bane; 15 (0x0f) = neutral. (names at DS 0x7d7f..)
- Castle (city) table: 80 records x 100 bytes at DS:0x4632 (file 311858). Layout so far:
  +0x00 x (word), +0x02 y (word), +0x04 name[20], +0x18 defence (byte, 3..6), +0x19 owner (byte, 15=neutral),
  +0x1A..+0x23 can-produce flags[10], +0x24 time[10] (turns), +0x2E ?[10] (strength?), +0x38 ?[10] (moves?),
  +0x42 cost[10] (gp), +0x4C current production slot (char, -1 none?), +0x4D ?, +0x4E turns left (char), +0x4F ?,
  +0x50 income? (word), +0x52.., +0x54 (word), +0x56/+0x58 vector target x,y? (0x4688/0x468a), +0x5A..+0x63 words.
  Cities occupy 2x2 map tiles with top-left at (x,y).
- Production slot index 0..9 corresponds to army type 0..9 (see army type list below).
- Ruins/special sites: 40 records x 28 bytes at DS:0x7ec6: x (byte), 0, y (byte), 0, name[20], type, ...
  type 1 = Library, 2 = Sage/Seer/Oracle, 3 = Temple, 4 = Ruin  (needs confirmation).
- Item names (14 items, 30-byte records) at DS ~0x2196 ("Firesword"...).
- Hero names list at DS ~0x2700.. (Comte d'Trout ...).
- Army type names: DS:0x444c.. pointer table at DS:0x44e8? Order:
  0 Giant Warriors, 1 Heavy Infantry, 2 Light Infantry, 3 Dwarven Legion, 4 Cavalry, 5 Navy, 6 Elven Archers,
  7 Wolf Riders, 8 Pegasi, 9 Griffins, 10 Wizard, 11 Undead, 12 Dragons, 13 Demons, 14 Devils, 15 Hero
- Terrain classes (names at DS 0x2125..): 0 Road, 1 Bridge, 2 Water, 3 Shore, 4 Forest, 5 Hill, 6 Mountain,
  7 Plain, 8 Marsh, 9 Tower, 10 City, 11 Ruins
- Terrain index -> class table: 128 words at DS:0x3934.
- Movement cost table: words at DS:0x37b4 + armytype*24 + class*2 (66 = impassable).
- Monster names (ruins): Troll, Giant, Wolf, Goblin, Dragon, Demon, Devil, Wizard, Ghost (DS ~0x2045).
- Map in memory: word per tile, row stride 0xDA (109 words), accessed as `*(uint*)(y*0xda + x*2 + 0x42)`
  in some far segment. Word bits: &0x7F = terrain/graphic index (0..125), (w&0x780)>>7 = owner (15 neutral),
  0x800 = flag (?), 0x1000 tower flag?, 0x2000 city flag? (file bytes are [lo=flags, hi=0x80|index])
- Army records: 24 bytes (0x18) each, up to 2000, array at offset 0 of a far segment. +0 x (word), +2 y (word),
  +4 ?, +5 owner? (0xff = free), +0xc hit points (byte)...  To be confirmed (see save loader FUN_109f_01a5).
- Save file: name[16], version word (=2000), army count word, armies*24, map 156*109 words,
  80 * 26 bytes dynamic castle data, 0x460 bytes ruins @DS:0x7ec6, 0x10 bytes @0x20be, ... (see FUN_109f_01a5/07b4)

## Battle resolution (FUN_2289_067a) — already decoded
Attacker units a=0..nA-1 (strength array A[], hp array), defenders d=0..nD-1 (strength D[]).
Loop: rA = dice(1,10,0); rD = dice(1,10,0)   (dice(1,12,0) for both if "Intense Combat" flag DS:0x2088 set)
  defender scores if rA <= D[d]; attacker scores if rD <= A[a]; if both or neither score -> reroll.
  If only defender scores: attacker hp[a]-- (and army +0xc--); if hp < 0 the unit dies, a++.
  If only attacker scores: defender hp[d]-- likewise, d++ when dead.
Ends when a == nA (defender wins, returns 0) or d == nD (attacker wins, returns 1).

## Sound (PC speaker only)
- Sound switch DS:0x208c (menu " Sound On "/" Sound Off"). DS:0xac0 selects the device: 0 = PC speaker,
  4 = an external device (codes 0x53/0x52 sent through FUN_12b7_023c) - only the speaker path matters.
- FUN_12ab_0048(n) -> FUN_1fac_00f8(n): table DS:0x3ba0, 10 bytes per sound: +0 file name, +2 player
  routine index into DS:0x3b94, +4 far pointer to the loaded data, +8 length. Files: 0 war.sjh,
  1 drumroll.sjh, 2 dramatic.sjh, 3 horn.sjh (routine 2), 4 ring.sjh (never played). FUN_1fac_0282 loads the
  whole file adding 1 to every byte.
- Player: timer 0 reprogrammed to 0x48 (1193182/72 = 16572 Hz), int 8 hooked with a bare EOI; the routine
  `hlt; lodsb; out 42h,al` (channel 2 in one-shot mode 0) outputs one PWM pulse of `value` ticks per sample.
  Routine 0 (1fe3:00a9) every tick, routine 1 (1fe3:00f0) every 2nd tick = 8286 Hz, routine 2 (1fe3:0139)
  every 3rd tick = 5524 Hz. The call is synchronous: the sample replaces the delay.
- Sample values 0..70 around 35 (half of the 72 tick period). 48 byte header, trailing ^Z.
- Calls: 3 at start-up over the title picture, 1 after Start on the setup screen, 0 for the WAR explosion
  of every shown battle (FUN_1ae7_0000 area, sound off: 20 tick delay) and after the raze picture,
  2 at the start of a ruin search (FUN_307e_038b), 3 for "Player %d, %s: You have won!".
- FUN_1224_0004: the beep, music driver (seg 3952, tick 18.2 Hz) playing the tune at DS:0x89fe = note 'B'
  for 2 ticks. Note word: low byte bit0 = command ((b>>1)&15: 0 end, 1 jump, 4 instrument), else
  (b>>1)&15 = note (frequency table DS:0x8946: 55,58,62,...,104 Hz; 0 = rest), (b>>5)&7 = octave shift,
  high byte = duration in ticks; PIT divisor = 0x122870 / (freq << octave). 'B' = 220 Hz.
  Used for unknown keys / invalid input and for each hit in a battle (FUN_1ae7_0084).
- The title tune at DS:0x8a8e (3 voices 0x8a8e/0x8b16/0x8b76 for Tandy) and the sweep/noise effects
  FUN_1224_0039/0095/00c6/00f7 (FUN_1881_000e/0040) have no callers.
