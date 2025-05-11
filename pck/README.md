# Warlords .PCK Decoder

This tool extracts and reconstructs image data from the `.PCK` files used in the classic DOS game *Warlords* (1990) by Strategic Studies Group.

It decodes the compressed sprite/image format used in the original game and converts the output into a standard RGB image using the VGA planar memory model and palette.

## Features

- ✅ Decompresses `.PCK` files using reverse-engineered [LZSS](https://en.wikipedia.org/wiki/Lempel–Ziv–Storer–Szymanski)-style backreference scheme  
- ✅ Reconstructs VGA planar images (4 planes, 1-bit per plane)  
- ✅ Converts to true 8-bit RGB output using the standard 16-color VGA palette  
- ✅ Outputs the image via `matplotlib` or saves to `.png`

## Dependencies

- Python 3.7+
- `numpy`
- `Pillow`
- `matplotlib`

## Usage

```
% python3 ./warlords-pck.py --help
usage: warlords-pck.py [-h] [-o OUTPUT] [-t TRANSPARENT] [-p {auto,game,main}] [-S] file

Decode Warlords .PCK files.
PCK files are stored in the game's PICTS directory and contain game graphics.

positional arguments:
  file                  Path to the .PCK file to decode

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path to the output PNG file
  -t TRANSPARENT, --transparent TRANSPARENT
                        Transparent color index
  -p {auto,game,main}, --palette {auto,game,main}
                        Use palette
  -S, --show            Show image

Written by Ales Teska, 2025
```

## Example

```
% python3 ./warlords-pck.py -S /Applications/Warlords.app/Contents/Resources/game/PICTS/MAIN.PCK
```

