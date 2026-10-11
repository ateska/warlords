# pywarlords — Warlords (1990) in Python

A faithful reimplementation of **Warlords** (Strategic Studies Group, 1990, DOS version 2.10) in pure
Python + [pygame](https://www.pygame.org). The game logic was transcribed from a Ghidra decompilation of
`WARLORDS.EXE` (combat, movement and path finding, production, economy, heroes, ruins/temples/sages,
diplomacy and Roger Keating's computer AI), and the screens are rebuilt from the original pictures.

**No game assets are included.** Everything — graphics, the map, city and unit tables, names, palettes,
AI tables — is read at start-up from *your* copy of the original game (for example the GOG release
*Warlords 1 + 2 Deluxe*).

![main screen](docs/main.png)

## Requirements

* Python 3.8+ on Windows, macOS or Linux
* `pip install pygame numpy` (or `pip install -r requirements.txt`)
* The original game files: `WARLORDS.EXE` (v2.10, plain or LZEXE packed), `ILLURIA.MAP` and the `PICTS/`
  folder with the `.PCK` files.

## Running

```
cd pywarlords
python3 -m warlords --data /path/to/warlords/game/folder
```

Without `--data` the game looks in the current folder, `../warlords` (this repository's layout) and
`/Applications/Warlords.app/Contents/Resources/game` (GOG on macOS).

| option | |
|---|---|
| `--scale N` | window size (default 2 = 1280×800). The window can be resized, `F11` toggles fullscreen |
| `--quick 0` | skip the title and setup screens: Sirians are human, everybody else is a computer player |
| `--quick 0,3 --level 3` | two humans (hot seat), computer players at Warlord level |
| `--load WAR1.SAV` | load a saved game. **The original `WAR?.SAV` files work**, and games saved here load in DOS Warlords |
| `--seed N` | fixed random seed (the original MS C `rand()` is reproduced exactly) |
| `--nosound` | start with the sound off (`Alt+M` or *Game → Sound Off* toggles it) |
| `--tough` | the hidden `t` switch of the original: computer players get *Enhance* |

## How to play (the original controls)

* **Left click** your army to select it, click it again to cycle through the stack, **double click**
  (or Alt/Shift+click) to select the whole stack. Click a destination to move; click an adjacent enemy
  (sword cursor) to attack.
* **Hold the right mouse button** to open the menu bar (Amiga style) and release it over a command.
  A short right click on the map shows information about that tile.
* The button column: *army mode*, *production mode* (then click one of your cities), *info mode*,
  **Ctr** centre, **Nxt** next army, **Quit** done with this army for the turn, **Def** defend (sentry,
  *Next* skips it).
* Keys: `N`/space next army, numeric keypad or arrow keys to step, `B` build, `R` raze, `Z` search,
  `T` take, `D` drop, `I` inventory, `F` find hero, `M` stack, `L` production, `K` heroes, `J` ruins,
  `O` control, `A` `S` `G` `H` `P` `W` reports, `Alt+E` end turn, `Alt+S`/`Alt+L` save/load,
  `Ctrl+Q` quit. `F5`–`F8` choose a unit in the production panel.

## What is implemented

* The whole rules engine: strength modifiers (unit/terrain, clan/terrain, hero command, flyers,
  special units, items, city/tower/ruin defence), the battle dice loop (d10, or d12 with *Intense
  Combat*), neutral city assaults, pillage, capital relocation, production with vectoring, upkeep,
  hero offers and allies, ruins (monsters, items, altars, thrones, gold, allies), temples, sages and
  libraries, towers, razing, city defences, surrender offers, victory and elimination.
* The original path finder and the computer players (production, garrisons, expansion, attack waves,
  war targets, hatreds, truces, hero errands and ruin exploration) at all four levels.
* Original quirks are kept on purpose (for example capital relocation picks the highest numbered
  city, and a vectored unit is lost if its destination is full). One deliberate fix: the original
  battle loop never ends when both units have strength 0 or less; here both are treated as strength 1.
* Screens: title, setup, main map with strategic map and status bar, menus, production panel and
  production view, stack view, battles, reports (armies, cities, gold, hatreds, production, winning),
  heroes, ruins, control panel, save/load, and the raze and surrender pictures.

* Sound: the original PC speaker effects — the digitised samples (`*.SJH`, played at the original
  8286/5524 Hz rates: the horn on the title screen and for victory, the drum roll when a game starts, the
  war cry for battles and razing, the ruin search fanfare) and the beep for battle hits and invalid keys.

## Layout

```
warlords/
  gamedata.py   static tables read from WARLORDS.EXE (lzexe.py unpacker, pck.py picture decoder)
  state.py      game state; saves in the original WAR?.SAV format
  engine.py     rules: movement, combat, production, heroes, exploration, turn structure
  pathfind.py   the original path finder
  ai.py         computer players
  ui/           pygame front-end (assets, screen, game_ui)
tests/          headless AI games, scripted UI runs, fuzzing
```

The reverse-engineering specifications the code is based on are in `../reverse/`.
