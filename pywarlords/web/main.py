"""Browser entry point (pygbag). Built by web/build.py; see web/README.md."""
import asyncio
import sys
import traceback

import pygame


def check(folder):
	from warlords.gamedata import find_file
	for f in ('WARLORDS.EXE', 'ILLURIA.MAP', 'PICTS/SCENERY.PCK', 'PICTS/ARMIES.PCK'):
		if not find_file(folder, f):
			return "%s is missing." % f
	try:
		from warlords.gamedata import GameData
		GameData(folder)
	except Exception as e:
		traceback.print_exc()
		return "These files could not be read as Warlords 2.10 (%s)." % e
	return None


async def bench(folder, turns=20):
	"""?bench: time computer-only turns (no drawing) to measure the WebAssembly speed."""
	import time
	from warlords import web
	from warlords.gamedata import GameData
	from warlords.engine import Game
	from warlords.ai import AI
	from warlords.ui_base import UIBase
	g = Game(GameData(folder), UIBase(), seed=1)
	g.ai = AI(g)
	g.new_game([0] * 8, [3] * 8)
	s = g.s
	t0 = time.time()
	while s.turn <= turns:
		for p in range(8):
			s.players[p].report_allowed = s.players[p].report_done = 0
		for p in range(8):
			if s.alive[p]:
				await g.ai_turn(p)
		await g.end_of_round()
		web.report('bench', "turn %d %.1fs cities %s" % (s.turn, time.time() - t0, s.ncities))
		s.turn += 1
		await asyncio.sleep(0)
	web.report('bench_done', "%.2f" % (time.time() - t0))


async def main():
	from warlords import web
	pygame.init()
	pygame.display.set_mode((640, 400))
	folder = await web.obtain_game_dir(check)
	if 'bench' in str(web.window.location.search):
		await bench(folder)
		return
	from warlords.gamedata import GameData
	from warlords.ui.game_ui import GameUI
	data = GameData(folder)
	ui = GameUI(data, scale=1)
	while True:                 # there is no DOS to quit to: back to the title screen
		await ui.run()


asyncio.run(main())
