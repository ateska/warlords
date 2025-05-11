# Warlords ILLURIA.MAP decoder


This tool reverse-engineers the game map (`ILLURIA.MAP`) from the classic DOS game Warlords (1990).
It decodes the tile structure and renders the full map using the original in-game graphics from `PICT/SCENERY.PCK`.


## Features

* Parses `ILLURIA.MAP` (raw 16-bit tile map with no header)
* Loads tile graphics from `SCENERY.png` (extracted from `PICTS/SCENERY.PCK`)
* Supports rendering the full map into a PNG image
* Optional overlay of tile ID and attributes on each tile
* Detects and maps various terrain types, roads, castles, bridges, etc.


## Preparations

`SCENERY.png` must be prepared from `PICTS/SCENERY.PCK`:

```
../pck/warlords-pck.py /Applications/Warlords.app/Contents/Resources/game/PICTS/SCENERY.PCK -o SCENERY.png
```

## Requirements

* Python 3
* `numpy`
* `Pillow`
* `matplotlib` (optional for preview)


## Usage

```
% python3 ./warlords-map.py --help        
usage: warlords-map.py [-h] [-s SCENERY] [-o OUTPUT] [-t] file

Decode Warlords ILLURIA.MAP file.

positional arguments:
  file                  Path to the ILLURIA.MAP file to decode (default: ILLURIA.MAP)

options:
  -h, --help            show this help message and exit
  -s SCENERY, --scenery SCENERY
                        PNG file with scenery tiles (default: SCENERY.png)
  -o OUTPUT, --output OUTPUT
                        Path to the output PNG file (default: ILLURIA.png)
  -t, --text            Draw tile ID and attributes in the center of each tile

Written by Ales Teska, 2025
```

## Example

```
python3 ./warlords-map.py /Applications/Warlords.app/Contents/Resources/game/ILLURIA.MAP -t
```
