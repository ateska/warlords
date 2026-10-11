# Reverse engineering notes for WARLORDS.EXE v2.10

These are the notes and specifications the Python port in [`../pywarlords`](../pywarlords) was written
from. They describe the original game's data structures and rules with addresses into the executable
as evidence.

* [`NOTES.md`](NOTES.md) — memory layout, address conventions, the battle loop, data tables, PC
  speaker sound (sample format, playback rates, which sound plays when).
* [`specs/combat.md`](specs/combat.md) — who fights, strength modifiers, the dice loop, neutral city
  assaults, pillage and capture.
* [`specs/movement.md`](specs/movement.md) — the army record, movement costs, groups, boarding ships,
  the original path finder, map word bits.
* [`specs/economy.md`](specs/economy.md) — setup, turn order, income/upkeep, production and vectoring,
  heroes and allies, victory and surrender, plus the static table of all 80 cities.
* [`specs/exploration.md`](specs/exploration.md) — ruins, temples, sages, libraries, altars, thrones,
  items.
* [`specs/ai.md`](specs/ai.md) — the computer player and diplomacy.

## How it was done

1. The Microsoft C floating point emulator calls (`INT 34h`–`3Dh`) were patched into real x87
   instructions so the decompiler could follow them (`tools/wl.py` builds the patched image).
2. Ghidra 11.3 (headless) analysed the MZ executable; `tools/CreateFuncs.java` adds every far call
   target as a function, `tools/DecompAll.java` decompiles all ~820 functions and `tools/annot.py`
   annotates string literals.
3. Subsystems were decoded from the decompiled code, checked against the disassembly where the
   decompiler mangled far-segment accesses, and validated against a real save game (`tools/sav.py`).
4. The DOS original was run in DOSBox to compare screens and behaviour.

The decompiled C itself is not included in the repository.

Address conventions: Ghidra segment = load image segment + 0x1000; `DS:x` is an offset into DGROUP,
which starts at file offset 0x47C00 (293888).
