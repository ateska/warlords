"""python -m warlords [--data GAME_DIR]"""
import argparse
import os
import sys


def find_game_dir(cands):
	from .gamedata import find_file
	for c in cands:
		if c and os.path.isdir(c) and find_file(c, 'WARLORDS.EXE') and find_file(c, 'PICTS/SCENERY.PCK'):
			return c
	return None


def main(argv=None):
	ap = argparse.ArgumentParser(prog="warlords", description="Warlords (SSG, 1990) reimplemented in Python. "
		"Needs the original game files (WARLORDS.EXE, ILLURIA.MAP, PICTS/*.PCK).")
	ap.add_argument("--data", "-d", help="folder with the original game files")
	ap.add_argument("--scale", "-s", type=int, default=2, help="window scale (default 2 = 1280x800)")
	ap.add_argument("--fullscreen", "-f", action="store_true")
	ap.add_argument("--load", "-l", help="load a saved game (original WAR?.SAV format)")
	ap.add_argument("--seed", type=int, help="random seed")
	ap.add_argument("--quick", "-q", metavar="CLANS", help="skip the title/setup screens. CLANS lists the human "
		"players, e.g. 0 (Sirians) or 0,3; everybody else is a computer player (--level)")
	ap.add_argument("--level", type=int, default=1, choices=[0, 1, 2, 3],
		help="computer level for --quick: 0 Knight, 1 Baron, 2 Lord, 3 Warlord")
	ap.add_argument("--nosound", action="store_true", help="start with the sound switched off (Alt+M toggles)")
	ap.add_argument("--tough", action="store_true", help="the hidden 't' switch: computer players get Enhance")
	args = ap.parse_args(argv)

	here = os.path.dirname(os.path.abspath(__file__))
	cands = [args.data, os.environ.get("WARLORDS_DATA"), os.getcwd(), os.path.join(os.getcwd(), "warlords"),
		os.path.join(here, "..", "..", "warlords"), os.path.join(here, "..", "game"),
		"/Applications/Warlords.app/Contents/Resources/game"]
	game_dir = find_game_dir(cands)
	if game_dir is None:
		print("Cannot find the original Warlords files. Use --data to point to the folder with "
			"WARLORDS.EXE, ILLURIA.MAP and PICTS/.", file=sys.stderr)
		return 2
	from .gamedata import GameData
	data = GameData(game_dir)
	from .ui.game_ui import GameUI
	ui = GameUI(data, scale=args.scale, fullscreen=args.fullscreen, seed=args.seed)
	if args.nosound:
		ui.sound = False
	quick = None
	if args.quick is not None:
		humans = [int(x) for x in args.quick.split(',') if x.strip() != '']
		quick = ([1 if p in humans else 0 for p in range(8)], [args.level] * 8)
	if args.tough:
		ui.extra_tough = True
	ui.run(load_path=args.load, quick=quick)
	return 0


if __name__ == "__main__":
	sys.exit(main())
