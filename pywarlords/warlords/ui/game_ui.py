"""pygame front-end recreating the original Warlords screens."""
import os
import time

import pygame

from ..gamedata import (MAP_W, MAP_H, DX, DY, CITY_DX, CITY_DY, NEUTRAL, HERO, NAVY, CITY, TOWER, RUINS,
	PLAIN, WATER, SHORE, FOREST, HILL, MOUNTAIN, MARSH, BRIDGE, ROAD)
from ..engine import Game
from ..ai import AI
from ..ui_base import UIBase
from ..state import M_ARMY, M_EXPLORED, F_ACTIVE, F_DONE
from ..pathfind import dirto
from .sound import Sound
from .assets import Assets, NATIVE_W, NATIVE_H
from .screen import (Screen, BLACK, WHITE, LGREY, GREY, DGREY, BLACK2, BROWN, DBROWN, CYAN, BLUE, DGREEN,
	GREEN, LGREEN, RED, ORANGE, YELLOW, DIR_CURSORS)

MAP_X, MAP_Y = 8, 5
VIEW_W, VIEW_H = 9, 8
MINI_X, MINI_Y = 408, 5
STATUS_Y = 166
CLAN_COLOURS = [WHITE, YELLOW, ORANGE, RED, LGREEN, CYAN, BLUE, BLACK2]

# button column (x, y, w, h) and the grey/red sprite positions in ARMIES.PCK
BUTTONS = [
	('army', (370, 5, 36, 38), (552, 72), (512, 72)),
	('prod', (370, 44, 36, 39), (552, 110), (512, 110)),
	('info', (370, 84, 36, 17), (552, 149), (512, 149)),
	('ctr', (370, 102, 36, 15), (552, 166), (512, 166)),
	('nxt', (370, 118, 36, 15), (592, 87), (592, 72)),
	('quit', (370, 134, 36, 15), (592, 117), (592, 102)),
	('def', (370, 150, 36, 15), (592, 147), (592, 132)),
]

MENUS = [
	("About", 18, [("About Warlords ?", 'about', '')]),
	("Game", 74, [("Observe Off", 'observe', 'alt O'), ("Sound Off", 'sound', 'alt M'), None,
		("Save Game", 'save', 'alt S'), ("Load Game", 'load', 'alt L'), None, ("Quit", 'quit', '^ Q')]),
	("Orders", 122, [("Build", 'build', '- B'), ("Capital", 'capital', '- C'), ("Disband", 'disband', '- Q'),
		("Raze", 'raze', '- R')]),
	("Reports", 202, [("Armies", 'r_armies', '- A'), ("Cities", 'r_cities', '- S'), ("Gold", 'r_gold', '- G'),
		("Hatreds", 'r_hatreds', '- H'), ("Production", 'r_prod', '- P'), ("Winning", 'r_winning', '- W')]),
	("Heroes", 270, [("Drop", 'drop', '- D'), ("Find", 'find', '- F'), ("Inv", 'inv', '- I'),
		("Search", 'search', '- Z'), ("Take", 'take', '- T')]),
	("View", 338, [("Stack", 'v_stack', '- M'), ("Production", 'v_prod', '- L'), ("Heroes", 'v_heroes', '- K'),
		("Ruins", 'v_ruins', '- J'), None, ("Control", 'v_control', '- O')]),
	("Turn", 386, [("End Turn", 'endturn', 'alt E')]),
]

KEYS = {
	pygame.K_b: 'build', pygame.K_c: 'capital', pygame.K_q: 'disband', pygame.K_r: 'raze',
	pygame.K_a: 'r_armies', pygame.K_s: 'r_cities', pygame.K_g: 'r_gold', pygame.K_h: 'r_hatreds',
	pygame.K_p: 'r_prod', pygame.K_w: 'r_winning', pygame.K_d: 'drop', pygame.K_f: 'find', pygame.K_i: 'inv',
	pygame.K_z: 'search', pygame.K_t: 'take', pygame.K_m: 'v_stack', pygame.K_l: 'v_prod', pygame.K_k: 'v_heroes',
	pygame.K_j: 'v_ruins', pygame.K_o: 'v_control', pygame.K_n: 'nxt', pygame.K_SPACE: 'nxt',
}
ALT_KEYS = {pygame.K_o: 'observe', pygame.K_m: 'sound', pygame.K_s: 'save', pygame.K_l: 'load', pygame.K_e: 'endturn',
	pygame.K_q: 'quit'}
NUMPAD = {pygame.K_KP8: 0, pygame.K_KP9: 1, pygame.K_KP6: 2, pygame.K_KP3: 3, pygame.K_KP2: 4, pygame.K_KP1: 5,
	pygame.K_KP4: 6, pygame.K_KP7: 7, pygame.K_UP: 0, pygame.K_RIGHT: 2, pygame.K_DOWN: 4, pygame.K_LEFT: 6}


class QuitGame(Exception):
	pass


class GameUI(UIBase):

	headless = False

	def __init__(self, data, scale=2, fullscreen=False, seed=None, save_dir=None):
		super().__init__()
		self.data = data
		pygame.init()
		pygame.display.set_mode((NATIVE_W * scale, NATIVE_H * 2 * scale))
		self.assets = Assets(data)
		self.scr = Screen(self.assets, scale, fullscreen)
		self.seed = seed
		self.save_dir = save_dir or data.game_dir
		self.game = None
		self.snd = Sound(data.game_dir)
		self.mode = 'army'            # army / prod / info
		self.status_msg = None
		self.info_lines = None
		self.overlay = None           # callable drawing over the main screen
		self.menu_open = False
		self.last_click = (0, (-1, -1))
		self.sound = True
		self.anim = 0
		self.hover = None
		self.delay_scale = 1.0

	# ==================================================================
	# event handling
	# ==================================================================
	def events(self):
		return self._raw_events()

	def _raw_events(self):
		out = []
		for ev in pygame.event.get():
			if ev.type == pygame.QUIT:
				raise QuitGame()
			elif ev.type == pygame.VIDEORESIZE:
				if not self.scr.fullscreen:
					self.scr.window = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
			elif ev.type == pygame.MOUSEMOTION:
				self.scr.mouse = self.scr.to_native(ev.pos)
				out.append(('motion', self.scr.mouse, ev.buttons))
			elif ev.type == pygame.MOUSEBUTTONDOWN:
				self.scr.mouse = self.scr.to_native(ev.pos)
				if ev.button in (1, 3):
					out.append(('down', self.scr.mouse, ev.button))
				elif ev.button in (4, 5):
					out.append(('wheel', self.scr.mouse, ev.button))
			elif ev.type == pygame.MOUSEBUTTONUP:
				self.scr.mouse = self.scr.to_native(ev.pos)
				if ev.button in (1, 3):
					out.append(('up', self.scr.mouse, ev.button))
			elif ev.type == pygame.KEYDOWN:
				if ev.key == pygame.K_F11 or (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT):
					self.scr.toggle_fullscreen()
					continue
				out.append(('key', ev.key, ev.mod, ev.unicode))
		return out

	def wait(self, ms):
		"""Delay while keeping the window responsive."""
		if getattr(self, 'fast', False):
			ms = 0
		end = pygame.time.get_ticks() + int(ms * self.delay_scale)
		while pygame.time.get_ticks() < end:
			for e in self._raw_events():
				if e[0] == 'key' and e[1] == pygame.K_ESCAPE:
					self.fast = True
					end = 0
			self.scr.present()
			self.scr.tick(60)

	# ------------------------------------------------------------------
	# sound (FUN_12ab_0048: the samples play synchronously, FUN_1224_0004: beep)
	# ------------------------------------------------------------------
	def play_sound(self, name, sync=True, fallback_ms=0):
		length = 0
		if self.sound and not getattr(self, 'fast', False):
			length = self.snd.play(name)
		if not length:
			if fallback_ms:
				self.wait(fallback_ms)
			return
		if sync:
			end = pygame.time.get_ticks() + int(length * 1000) + 100
			while self.snd.busy() and pygame.time.get_ticks() < end:
				stop = False
				for e in self._raw_events():
					if e[0] == 'down' or e[0] == 'key':
						if e[0] == 'key' and e[1] == pygame.K_ESCAPE:
							self.fast = True
						stop = True
				if stop:
					self.snd.stop()
					break
				self.scr.present()
				self.scr.tick(60)

	def beep(self):
		if self.sound:
			self.snd.play('beep')

	def wait_click(self, draw=None):
		"""Wait for a click or a key press."""
		while True:
			if draw:
				draw()
			self.scr.present()
			for e in self.events():
				if e[0] == 'down' or (e[0] == 'key' and e[1] not in (pygame.K_LSHIFT, pygame.K_RSHIFT,
						pygame.K_LALT, pygame.K_RALT, pygame.K_LCTRL, pygame.K_RCTRL)):
					return e
			self.scr.tick(30)

	# ==================================================================
	# top level flow
	# ==================================================================
	def run(self, load_path=None, quick=None):
		try:
			if load_path is None and quick is None:
				self.title_screen()
			while True:
				if quick is not None:
					res = ('start', quick[0], quick[1])
					quick = None
				elif load_path is not None:
					res = ('load', load_path)
					load_path = None
				else:
					res = self.setup_screen()
				if res is None:
					return
				g = Game(self.data, self, seed=self.seed)
				g.ai = AI(g)
				self.game = g
				if res[0] == 'start':
					g.new_game(res[1], res[2])
					g.run()
				else:
					g.s.load(res[1])
					g.recompute_totals_all()
					if not g.s.human[g.s.current] or not g.s.alive[g.s.current]:
						g.run()
					else:
						g.run(resume_player=g.s.current)
				if getattr(g, 'restart', None):
					load_path = g.restart if g.restart != 'setup' else None
					continue
				return
		except QuitGame:
			return

	# ------------------------------------------------------------------
	def title_screen(self):
		s = self.scr
		img = self.assets.surface('MAIN', 3)
		s.blit(img, (0, 0))
		s.present()
		self.play_sound('horn', sync=False)
		t0 = pygame.time.get_ticks()
		while pygame.time.get_ticks() - t0 < 8000:
			s.blit(img, (0, 0))
			s.present()
			for e in self.events():
				if e[0] in ('up', 'key'):
					return
			s.tick(30)

	def setup_screen(self):
		"""The player selection screen (SETUP.PCK)."""
		s = self.scr
		human = [1] * 8
		level = [0] * 8
		img = self.assets.surface('SETUP')
		row_y = [12 + 15 * i for i in range(8)]
		load_btn = (48, 137, 108, 17)
		start_btn = (216, 137, 108, 17)
		pressed = [None]

		def draw():
			s.fill((0, 0, 640, 200), GREY)
			s.blit(img, (0, 0), (0, 0, 580, 158))
			s.fill((574, 0, 66, 166), GREY)
			s.fill((0, 158, 640, 8), GREY)
			s.fill((4, 156, 352, 2), DGREY)
			s.fill((360, 158, 216, 2), DGREY)
			s.blit(img, (48, 137), (354, 178, 108, 17))      # Load button
			for i in range(8):
				y = row_y[i]
				self._draw_level_icon(176, y - 1, human[i], level[i])
				lvl = "Human" if human[i] else self.data.level_names[level[i]]
				s.text(224, y, lvl)
				s.text(322, y, "F%d" % (i + 1))
			if pressed[0] == 'start':
				s.blit(img, (216, 137), (354, 160, 108, 17))
			if pressed[0] == 'load':
				s.blit(img, (48, 137), (354, 160, 108, 17))
			s.fill((0, 166, 640, 34), GREY)
			s.hline(0, 639, 165, BLACK)
			s.hline(0, 639, 166, LGREY)
			if not all(human):
				r = sum(self.data.difficulty_points[level[i]] for i in range(8) if not human[i])
				if r > 97:
					r = 100
				s.text_center(320, 178, "Difficulty Rating %d%%" % r)

		def cycle(i):
			if human[i]:
				human[i] = 0
				level[i] = 0
			elif level[i] < 3:
				level[i] += 1
			else:
				human[i] = 1

		def begin():
			draw()
			s.fill((368, 5, 266, 156), BLACK)
			y = 14
			for wd in ["Let", "the", "War", "Begin.."]:
				s.text_center(500, y, wd, ORANGE)
				y += 30
			s.present()
			self.play_sound('drumroll', fallback_ms=800)

		while True:
			draw()
			s.cursor = 'arrow'
			s.present()
			for e in self.events():
				if e[0] == 'key':
					if pygame.K_F1 <= e[1] <= pygame.K_F8:
						cycle(e[1] - pygame.K_F1)
					elif e[1] in (pygame.K_s, pygame.K_RETURN):
						begin()
						return ('start', human, level)
					elif e[1] == pygame.K_l:
						p = self.load_dialog()
						if p:
							return ('load', p)
					elif e[1] == pygame.K_ESCAPE:
						return None
				elif e[0] == 'down' and e[2] == 1:
					x, y = e[1]
					if _inside(e[1], load_btn):
						pressed[0] = 'load'
					elif _inside(e[1], start_btn):
						pressed[0] = 'start'
					else:
						for i in range(8):
							if 10 <= x < 350 and row_y[i] - 2 <= y < row_y[i] + 12:
								cycle(i)
				elif e[0] == 'up' and e[2] == 1:
					if pressed[0] == 'start' and _inside(e[1], start_btn):
						begin()
						return ('start', human, level)
					if pressed[0] == 'load' and _inside(e[1], load_btn):
						pressed[0] = None
						p = self.load_dialog()
						if p:
							return ('load', p)
					pressed[0] = None
			s.tick(30)

	def _draw_level_icon(self, x, y, human, level):
		"""Human / computer level icons (right strip of SETUP.PCK)."""
		k = 0 if human else 1 + max(0, min(3, level))
		self.scr.blit(self.assets.sprite('SETUP', 591, 15 * k, 36, 14, 0, None), (x - 4, y))

	# ==================================================================
	# main screen drawing
	# ==================================================================
	@property
	def s(self):
		return self.game.s

	def draw_main(self, status=True):
		scr = self.scr
		scr.fill((0, 0, 640, 200), GREY)
		scr.hline(0, 639, 0, LGREY)
		scr.hline(0, 639, 3, DGREY)
		scr.hline(0, 639, 4, BLACK)
		self.draw_map()
		scr.fill((368, 5, 2, 161), BLACK)
		scr.fill((406, 5, 2, 161), BLACK)
		self.draw_buttons()
		self.draw_minimap()
		scr.hline(0, 639, 165, BLACK)
		scr.hline(0, 639, 166, LGREY)
		if status:
			self.draw_status()
		if self.overlay:
			self.overlay()

	def draw_buttons(self):
		for name, rect, grey, red in BUTTONS:
			active = (name == self.mode and name != 'army') or name == getattr(self, 'pressed_button', None)
			sx, sy = red if active else grey
			self.scr.blit(self.assets.sprite('ARMIES', sx, sy, rect[2], rect[3], 0, None), rect[:2])

	def draw_map(self):
		s = self.s
		a = self.assets
		scr = self.scr
		vx, vy = s.view_x, s.view_y
		for j in range(VIEW_H):
			for i in range(VIEW_W):
				x, y = vx + i, vy + j
				w = s.map[y * MAP_W + x] if (0 <= x < MAP_W and 0 <= y < MAP_H) else 0x24
				scr.blit(a.tile(w & 0x7f), (MAP_X + i * 40, MAP_Y + j * 20))
		# items lying on the ground (FUN_1a12_08da): bag sprite
		for it in s.items:
			if it.state == 1 and vx <= it.x < vx + VIEW_W and vy <= it.y < vy + VIEW_H:
				scr.blit(a.sprite('ARMIES', 192, 166, 64, 20), (MAP_X + (it.x - vx) * 40, MAP_Y + (it.y - vy) * 20))
		self.draw_armies()
		self.draw_selection()

	def draw_armies(self):
		"""FUN_1a12_0536 / 07a0: one sprite per tile (highest priority type), flag with the stack size."""
		s = self.s
		a = self.assets
		scr = self.scr
		d = self.data
		vx, vy = s.view_x, s.view_y
		tops = {}
		counts = {}
		cur = s.armies[s.cur_army] if s.cur_army is not None else None
		for ar in s.live_armies():
			if ar.x < 0 or not (vx <= ar.x < vx + VIEW_W and vy <= ar.y < vy + VIEW_H):
				continue
			k = (ar.x, ar.y)
			counts[k] = counts.get(k, 0) + 1
			t = tops.get(k)
			if t is None or d.prio[t.type] < d.prio[ar.type]:
				tops[k] = ar
		if cur is not None and cur.x >= 0 and not s.group_mode and (cur.x, cur.y) in counts and cur.owner != 0xff:
			tops[(cur.x, cur.y)] = cur
		for (x, y), ar in tops.items():
			px = MAP_X + (x - vx) * 40
			py = MAP_Y + (y - vy) * 20
			owner = (s.map[y * MAP_W + x] >> 7) & 0xf
			owner = ar.owner if owner > 7 else owner
			scr.blit(a.army(ar.type, owner), (px + 12, py + 6))
			scr.blit(a.sprite('ARMIES', 32, 126, 32, 14), (px + 3, py + 6))
			n = counts[(x, y)]
			fy = 140 + 5 * owner
			if n > 4:
				scr.blit(a.sprite('ARMIES', 160, fy, 16, 5), (px + 5, py + 8))
				n -= 4
			n = min(n, 4)
			fx = [0, 0, 32, 64, 96][n]
			fw = [16, 16, 32, 32, 48][n]
			scr.blit(a.sprite('ARMIES', fx, fy, fw, 5), (px + 2, py + 1))

	def draw_selection(self):
		s = self.s
		if s.cur_army is None:
			return
		cur = s.armies[s.cur_army]
		if cur.x < 0:
			return
		vx, vy = s.view_x, s.view_y
		if vx <= cur.x < vx + VIEW_W and vy <= cur.y < vy + VIEW_H:
			px = MAP_X + (cur.x - vx) * 40
			py = MAP_Y + (cur.y - vy) * 20
			if (self.anim // 8) % 2 == 0:
				spr = self.scr._cursors.get('select')
				if spr:
					img, hot = spr
					self.scr.blit(img, (px + 28 - img.get_width() // 2, py + 13 - img.get_height() // 2))

	def draw_minimap(self, markers=None):
		s = self.s
		a = self.assets
		scr = self.scr
		scr.blit(a.surface('STRAT'), (MINI_X, MINI_Y))
		for c in s.cities:
			if c.owner < 8:
				scr.blit(a.sprite('ARMIES', 392, 112 + 3 * c.owner, 6, 3, 0, None),
					(MINI_X + 2 * c.x + 2, MINI_Y + c.y + 2))
			elif s.tile(c.x, c.y) & 0x7f == 12:
				scr.blit(a.sprite('ARMIES', 392, 136, 6, 3, 0, None), (MINI_X + 2 * c.x + 2, MINI_Y + c.y + 2))
		if markers:
			markers()
		# viewport rectangle
		x0 = MINI_X + 2 + 2 * s.view_x
		y0 = MINI_Y + 2 + s.view_y
		col = WHITE if (self.anim // 6) % 2 == 0 else BLACK
		scr.box((x0, y0, 18, 8), col)

	def draw_status(self):
		scr = self.scr
		s = self.s
		scr.fill((0, 167, 640, 33), GREY)
		if self.status_msg:
			lines = self.status_msg.split('\n')
			y = 182 - len(lines) * 5
			for ln in lines:
				scr.text_center(320, y, ln)
				y += 10
			return
		if self.info_lines:
			self._draw_columns(self.info_lines)
			return
		p = s.current
		cmd = {'army': "None", 'prod': "Production", 'info': "Info"}[self.mode]
		if s.cur_army is not None and s.armies[s.cur_army].owner == p:
			a = s.armies[s.cur_army]
			if s.group_mode:
				mv = s.group_moves
				strn = max(m.strength for m in self.game.selected())
				cmd = "Group" if self.mode == 'army' else cmd
			else:
				mv = a.moves
				strn = a.strength
				cmd = "Move Army" if self.mode == 'army' else cmd
			cols = [[("Name:", self.game.clan_name(p)), ("Move:", str(mv)), ("Army:", self.game.army_name(a))],
				[], [("Command:", cmd), ("Strength:", str(strn))]]
			self._draw_columns(cols)
		else:
			cols = [[("Name:", self.game.clan_name(p)), ("Income:", "%d gp" % s.income[p]),
					("Cities:", str(s.ncities[p]))],
				[("", ""), ("Gold:", "%d gp" % s.players[p].gold), ("Turn:", str(s.turn))],
				[("Command:", cmd), ("Upkeep:", "%d gp" % s.upkeep[p])]]
			self._draw_columns(cols)

	def _draw_columns(self, cols):
		scr = self.scr
		xs = [(132, 142), (297, 304), (468, 475)]
		for ci, col in enumerate(cols):
			for li, (lab, val) in enumerate(col):
				y = 168 + li * 10
				if lab:
					scr.text_right(xs[ci][0], y, lab)
				if val:
					scr.text(xs[ci][1], y, val)

	# ==================================================================
	# UIBase hooks
	# ==================================================================
	def message(self, text, wait=True):
		self.log.append(text)
		if self.game is None:
			return
		self.status_msg = text
		self.draw_main()
		if wait:
			self.wait_click(self.draw_main)
		self.status_msg = None

	def status(self, text):
		self.log.append(text)
		if self.game is None:
			return
		self.status_msg = text
		self.draw_main()
		self.scr.present()
		self.wait(700)
		self.status_msg = None

	def picture(self, name, lines=()):
		"""RAZE / BEG / HEAD pictures (FUN_11a6_067c): two panels plus a message."""
		scr = self.scr
		key = {'raze': ('RAZE', 0), 'beg': ('BEG', 1), 'head': ('HEAD', 2)}.get(name)
		if key is None:
			for ln in lines:
				self.message(ln)
			return
		img = self.assets.surface(key[0], key[1])
		w, h = img.get_size()

		def draw():
			scr.fill((0, 0, 640, 200), GREY)
			scr.bevel((0, 0, 640, 166))
			if name == 'raze':
				scr.blit(img, ((640 - w) // 2, 3))
			else:
				scr.blit(img, (13, 7), (0, 0, 350, 156))
				scr.blit(img, (409, 7), (352, 0, 219, 156))
			scr.fill((0, 166, 640, 34), GREY)
			scr.hline(0, 639, 166, LGREY)
			y = 182 - len(cur) * 5
			for ln in cur:
				scr.text_center(320, y, ln)
				y += 10

		cur = list(lines)
		if name == 'raze':
			draw()
			self.play_sound('war')
		self.wait_click(draw)

	def ask(self, lines, buttons, default=0):
		"""Modal dialog box in the middle of the map (FUN_1312_20d8 style)."""
		scr = self.scr
		f = self.assets.fant
		bw = [max(40, f.width(b.strip()) + 14) for b in buttons]
		w = max([f.width(l) for l in lines] + [sum(bw) + 10 * (len(bw) - 1)]) + 40
		w = min(w, 360)
		h = len(lines) * 11 + 40
		x = MAP_X + (360 - w) // 2
		y = MAP_Y + max(4, (160 - h) // 2)
		rects = []
		bx = x + (w - (sum(bw) + 10 * (len(bw) - 1))) // 2
		for k, b in enumerate(buttons):
			rects.append((bx, y + h - 22, bw[k], 15))
			bx += bw[k] + 10
		pressed = [None]

		def draw():
			self.draw_main()
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			yy = y + 8
			for ln in lines:
				scr.text_center(x + w // 2, yy, ln)
				yy += 11
			for k, b in enumerate(buttons):
				scr.button(rects[k], b.strip(), pressed[0] == k)

		while True:
			draw()
			self.scr.cursor = 'arrow'
			scr.present()
			for e in self.events():
				if e[0] == 'down' and e[2] == 1:
					for k, r in enumerate(rects):
						if _inside(e[1], r):
							pressed[0] = k
				elif e[0] == 'up' and e[2] == 1:
					if pressed[0] is not None and _inside(e[1], rects[pressed[0]]):
						return pressed[0]
					pressed[0] = None
				elif e[0] == 'key':
					if e[1] == pygame.K_ESCAPE:
						return len(buttons) - 1
					if e[1] in (pygame.K_RETURN, pygame.K_KP_ENTER):
						return default
					ch = (e[3] or '').lower()
					for k, b in enumerate(buttons):
						if ch and b.strip().lower().startswith(ch):
							return k
			scr.tick(30)

	def hero_offer(self, city_name, price, gold):
		return self.ask(["A hero in %s offers" % city_name, "to join you for %d gp!" % price,
			"You have %d gp" % gold], [" Accept ", " Reject "]) == 0

	def name_hero(self, default):
		return self.text_input("Name of Hero", default)

	def text_input(self, title, default, maxlen=15):
		scr = self.scr
		text = default
		x, y, w, h = 86, 56, 190, 52
		while True:
			self.draw_main()
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.text_center(x + w // 2, y + 6, title)
			scr.fill((x + 20, y + 19, w - 40, 12), DGREY)
			scr.text(x + 23, y + 21, text + ("_" if (self.anim // 10) % 2 == 0 else ""), BLACK)
			scr.button((x + w // 2 - 25, y + h - 18, 50, 15), "Done")
			self.anim += 1
			scr.present()
			for e in self.events():
				if e[0] == 'key':
					if e[1] in (pygame.K_RETURN, pygame.K_KP_ENTER):
						return text.strip() or default
					if e[1] == pygame.K_ESCAPE:
						return default
					if e[1] == pygame.K_BACKSPACE:
						text = text[:-1]
					elif e[3] and 32 <= ord(e[3]) < 127 and len(text) < maxlen:
						text += e[3]
				elif e[0] == 'up' and e[2] == 1 and _inside(e[1], (x + w // 2 - 25, y + h - 18, 50, 15)):
					return text.strip() or default
			scr.tick(30)

	def production_report(self, text, city=None):
		"""Shown in the status area like the original: Yes / No / End Report."""
		scr = self.scr
		if city is not None:
			self.game.center_view(city.x, city.y)
		btns = [('yes', (38, 183, 48, 13), "Yes"), ('no', (104, 183, 44, 13), "No"),
			('end', (518, 183, 98, 13), "End Report")]
		pressed = [None]
		while True:
			self.draw_main(status=False)
			scr.fill((0, 167, 640, 33), GREY)
			scr.text_center(320, 171, text)
			scr.text_center(320, 184, "Keep producing these?")
			for k, r, label in btns:
				scr.button(r, label, pressed[0] == k, ci=BLACK, hot=BLACK)
			scr.cursor = 'arrow'
			scr.present()
			for e in self.events():
				if e[0] == 'down' and e[2] == 1:
					for k, r, label in btns:
						if _inside(e[1], r):
							pressed[0] = k
				elif e[0] == 'up' and e[2] == 1:
					if pressed[0] is not None:
						for k, r, label in btns:
							if k == pressed[0] and _inside(e[1], r):
								return k
					pressed[0] = None
				elif e[0] == 'key':
					if e[1] in (pygame.K_y, pygame.K_RETURN, pygame.K_KP_ENTER):
						return 'yes'
					if e[1] == pygame.K_n:
						return 'no'
					if e[1] in (pygame.K_e, pygame.K_ESCAPE):
						return 'end'
			scr.tick(30)

	def choose(self, title, options):
		"""Scrollable list (sage questions, take/drop items)."""
		if not options:
			return None
		scr = self.scr
		top = 0
		sel = 0
		n = 7
		x, y, w, h = 60, 20, 250, 130
		while True:
			self.draw_main()
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.text_center(x + w // 2, y + 5, title)
			for i in range(n):
				k = top + i
				if k >= len(options):
					break
				ry = y + 18 + i * 12
				if k == sel:
					scr.fill((x + 8, ry - 1, w - 50, 11), YELLOW)
				scr.text(x + 12, ry, options[k])
			up = (x + w - 36, y + 18, 26, 14)
			dn = (x + w - 36, y + 34, 26, 14)
			ok = (x + 30, y + h - 20, 50, 15)
			cancel = (x + w - 90, y + h - 20, 60, 15)
			scr.button(up, "Up")
			scr.button(dn, "Dn")
			scr.button(ok, "OK")
			scr.button(cancel, "Cancel")
			scr.present()
			for e in self.events():
				if e[0] == 'key':
					if e[1] == pygame.K_ESCAPE:
						return None
					if e[1] in (pygame.K_RETURN, pygame.K_KP_ENTER):
						return sel
					if e[1] == pygame.K_UP:
						sel = max(0, sel - 1)
					if e[1] == pygame.K_DOWN:
						sel = min(len(options) - 1, sel + 1)
				elif e[0] == 'wheel':
					sel = max(0, min(len(options) - 1, sel + (1 if e[2] == 5 else -1)))
				elif e[0] == 'up' and e[2] == 1:
					p = e[1]
					if _inside(p, up):
						sel = max(0, sel - 1)
					elif _inside(p, dn):
						sel = min(len(options) - 1, sel + 1)
					elif _inside(p, ok):
						return sel
					elif _inside(p, cancel):
						return None
					else:
						for i in range(n):
							if x + 8 <= p[0] < x + w - 40 and y + 17 + i * 12 <= p[1] < y + 29 + i * 12:
								if top + i < len(options):
									if sel == top + i:
										return sel
									sel = top + i
				if sel < top:
					top = sel
				if sel >= top + n:
					top = sel - n + 1
			scr.tick(30)

	def show_moves(self, game, player):
		s = game.s
		return bool(s.global_observe or s.observe[player]) or not any(s.human[q] and s.alive[q] for q in range(8))

	def ai_turn_start(self, game, p):
		s = game.s
		self.mode = 'army'
		name = game.clan_name(p)
		txt = "%s %s moving!" % (name, "is" if p in (4, 7) else "are")
		if s.supervisor:
			txt += " (%d)" % s.turn
		self.status_msg = txt
		self.draw_main()
		self.scr.present()
		for e in self._raw_events():
			if e[0] == 'key' and e[1] == pygame.K_ESCAPE and not any(s.human[q] and s.alive[q] for q in range(8)):
				for q in range(8):
					s.human[q] = 1
		if self.show_moves(game, p):
			self.wait(400)

	def ai_turn_end(self, game, p):
		self.status_msg = None

	def army_moved(self, game, armies, x0, y0, x1, y1):
		s = game.s
		human_move = s.human[s.current]
		if not human_move and not self.show_moves(game, s.current):
			return
		if not (s.view_x <= x1 < s.view_x + VIEW_W and s.view_y <= y1 < s.view_y + VIEW_H) or \
				not (1 <= x1 - s.view_x <= VIEW_W - 2 and 1 <= y1 - s.view_y <= VIEW_H - 2):
			game.center_view(x1, y1)
		self.draw_main()
		self.scr.present()
		self.wait(60 if human_move else 40)

	def refresh(self, game):
		self.draw_main()
		self.scr.present()

	def game_over(self, game, lines):
		for ln in lines:
			self.message(ln)

	# ==================================================================
	# battle screen
	# ==================================================================
	def battle(self, game, b, caption=None):
		"""The battle as in the original: WAR explosion, then the battle box over the map with the
		defenders on top and the attackers below, and (for the player's own attacks) a battle scene in
		place of the strategic map."""
		scr = self.scr
		a = self.assets
		s = game.s
		human_involved = s.human[b.attacker] or (b.def_clan < 8 and s.human[b.def_clan])
		if not human_involved and not self.show_moves(game, b.attacker):
			return
		self.status_msg = caption
		try:
			self._battle(game, b, caption)
		finally:
			self.status_msg = None

	def _battle(self, game, b, caption):
		scr = self.scr
		a = self.assets
		s = game.s
		tx, ty = b.target
		if not (s.view_x <= tx < s.view_x + VIEW_W and s.view_y <= ty < s.view_y + VIEW_H):
			game.center_view(tx, ty)
		# 1. the WAR explosion over the attacked tile
		px = MAP_X + (tx - s.view_x) * 40 + 20
		py = MAP_Y + (ty - s.view_y) * 20 + 10
		war = a.sprite('ARMIES', 528, 0, 112, 56)
		self.draw_main()
		scr.blit(war, (max(MAP_X, min(MAP_X + 360 - 112, px - 56)), max(MAP_Y, min(MAP_Y + 160 - 56, py - 28))))
		scr.present()
		self.play_sound('war', fallback_ms=500)
		att = list(b.attackers)
		dfn = list(b.defenders)
		alive_a = [1] * len(att)
		alive_d = [1] * len(dfn)
		hp_a = [u.hits + sum(1 for r in b.rounds if r[2] == 'a' and r[0] == i) for i, u in enumerate(att)]
		hp_d = [u.hits + sum(1 for r in b.rounds if r[2] == 'd' and r[1] == i) for i, u in enumerate(dfn)]
		hit = [None]
		dead = [None]
		cur_a = [0]
		BX, BY, BW, BH = 43, 35, 290, 100

		def unit_pos(side, i):
			row, col = divmod(i, 8)
			x = BX + 18 + col * 32
			if side == 'd':
				y = BY + 12 + row * 16
			else:
				y = BY + BH - 26 - row * 16
			return x, y

		def draw():
			self.draw_main(status=True)
			if caption is None:
				self.battle_scene(game, b)
			scr.fill((BX - 1, BY - 1, BW + 2, BH + 2), BLACK)
			scr.bevel((BX, BY, BW, BH))
			for side, units, alive in (('d', dfn, alive_d), ('a', att, alive_a)):
				for i, u in enumerate(units):
					if not alive[i]:
						continue
					x, y = unit_pos(side, i)
					owner = u.owner if u.owner < 8 else (b.attacker if side == 'a' else b.def_clan)
					if dead[0] == (side, i):
						scr.blit(a.sprite('ARMIES', 96, 126, 32, 14), (x, y))
						continue
					scr.blit(a.army(u.type, owner & 7), (x, y))
					if hit[0] == (side, i):
						scr.blit(a.sprite('ARMIES', 64, 126, 32, 14), (x, y))
			if att and cur_a[0] < len(att) and alive_a[cur_a[0]]:
				x, y = unit_pos('a', cur_a[0])
				sw = self.scr._cursors.get('sword')
				if sw:
					scr.blit(sw[0], (x + 4, y - 2))

		if b.neutral or not dfn:
			draw()
			self.wait(600)
			if b.result == 0:
				for i in range(len(att)):
					hit[0] = ('a', i)
					draw()
					self.wait(150)
					hit[0] = None
					dead[0] = ('a', i)
					draw()
					self.wait(150)
					dead[0] = None
					alive_a[i] = 0
			draw()
			self.wait(700)
			return
		draw()
		self.wait(500)
		for (ia, idd, loser) in b.rounds:
			cur_a[0] = ia
			side, idx = ('a', ia) if loser == 'a' else ('d', idd)
			hit[0] = (side, idx)
			draw()
			self._war_sound()
			self.wait(140)
			hit[0] = None
			if side == 'a':
				hp_a[idx] -= 1
				killed = hp_a[idx] < 0
			else:
				hp_d[idx] -= 1
				killed = hp_d[idx] < 0
			if killed:
				dead[0] = (side, idx)
				draw()
				self.wait(160)
				dead[0] = None
				if side == 'a':
					alive_a[idx] = 0
				else:
					alive_d[idx] = 0
			draw()
			self.wait(60)
		draw()
		self.wait(800)

	def battle_scene(self, game, b):
		"""Right panel during a battle: sky, the two shields, the terrain and the banners."""
		scr = self.scr
		a = self.assets
		X, Y = MINI_X, MINI_Y
		scr.fill((X, Y, 226, 161), BLACK)
		scr.fill((X + 2, Y + 2, 222, 157), CYAN)
		cls = b.cls
		c1 = a.surface('COMBAT1')
		if cls in (WATER, SHORE):
			scr.blit(c1, (X + 1, Y + 95), (0, 0, 224, 65))
			scr.blit(c1, (X + 80, Y + 95), (416, 0, 64, 65))
		elif cls in (CITY, TOWER, RUINS):
			scr.blit(c1, (X + 1, Y + 95), (0, 0, 224, 65))
			scr.blit(c1, (X + 30, Y + 95), (224, 0, 192, 65))
		elif cls in (HILL, MOUNTAIN):
			scr.blit(c1, (X + 1, Y + 95), (0, 0, 224, 65))
			scr.blit(a.surface('COMBAT2', 0, 0), (X + 66, Y + 95 + 6), (228, 0, 92, 30))
		elif cls in (FOREST, MARSH):
			scr.blit(c1, (X + 1, Y + 95), (0, 0, 224, 65))
			scr.blit(a.surface('COMBAT2', 0, 0), (X + 1, Y + 95 + 2), (0, 0, 224, 30))
		else:
			scr.blit(c1, (X + 1, Y + 95), (0, 0, 224, 65))
		shields = [(544, 0), (576, 0), (608, 0), (576, 20), (608, 20), (576, 40), (608, 40), (544, 20)]
		sx, sy = shields[b.attacker & 7]
		scr.blit(a.sprite('COMBAT2', sx, sy, 32, 17), (X + 12, Y + 8))
		if b.def_clan < 8:
			sx, sy = shields[b.def_clan]
			scr.blit(a.sprite('COMBAT2', sx, sy, 32, 17), (X + 180, Y + 8))
		# banners: one flag per army, attacker left, defender right
		self._banners(X + 20, Y + 118, b.attacker, len([u for u in b.attackers]))
		if b.def_clan < 8:
			self._banners(X + 120, Y + 118, b.def_clan, len(b.defenders))

	def _banners(self, x, y, owner, n):
		a = self.assets
		scr = self.scr
		for i in range(min(n, 8)):
			col = i % 4
			row = i // 4
			px = x + col * 20
			py = y + row * 12
			scr.blit(a.sprite('ARMIES', 0, 140 + 5 * (owner & 7), 16, 5), (px, py))
			scr.vline(px, py, py + 9, BLACK)

	def _war_sound(self):
		self.beep()

	# ==================================================================
	# city production panel (status area) - FUN_200c_0516
	# ==================================================================
	def city_production(self, game, city, captured=False):
		self.production_panel(city)

	def production_panel(self, city):
		g = self.game
		s = self.s
		scr = self.scr
		a = self.assets
		p = s.current
		g.center_view(city.x, city.y)
		slots = [t for t in range(10) if city.can[t]][:4]
		sel = [city.prod if (city.turns > 0 and city.prod in slots) else None]
		btns = {'Prod': (438, 168, 36, 12), 'Loc': (491, 168, 30, 12), 'Stop': (540, 168, 36, 12),
			'Exit': (592, 168, 36, 12)}
		opt_pos = [(4, 168), (4, 184), (172, 168), (172, 184)]
		pressed = [None]
		msg = [None]

		def draw():
			self.draw_main(status=False)
			scr.fill((0, 167, 640, 33), GREY)
			for k, t in enumerate(slots):
				x, y = opt_pos[k]
				scr.text(x, y + 2, "F%d" % (k + 5))
				if sel[0] == t:
					scr.box((x + 26, y - 2, 28, 16), BLACK)
				scr.blit(a.army(t, p), (x + 24, y))
				scr.text(x + 86, y + 2, "%dt/%dgp" % (g.build_time(city, t, p), city.cost[t]))
			for name, r in btns.items():
				dis = (name == 'Loc' and (sel[0] == NAVY or s.ncities[p] < 2 or sel[0] is None))
				scr.button(r, name, pressed[0] == name, ci=DGREY if dis else BLACK, hot=BLACK)
			scr.text_right(492, 186, "Current:")
			if city.turns > 0 and 0 <= city.prod < 10:
				scr.blit(a.army(city.prod, p), (498, 183))
				t = "%dt" % city.turns
				if city.vector:
					dc = s.city_at(city.vx, city.vy)
					t += " -> %s" % (dc.name if dc else "?")
				scr.text(536, 186, t)
			else:
				scr.text(540, 186, "None")
			if msg[0]:
				scr.text_center(320, 178, msg[0], RED)
			# mark the city on the map
			self._mark_city(city)

		while True:
			draw()
			self.anim += 1
			self.scr.cursor = 'arrow'
			scr.present()
			for e in self.events():
				act = None
				if e[0] == 'key':
					if pygame.K_F5 <= e[1] <= pygame.K_F8:
						k = e[1] - pygame.K_F5
						if k < len(slots):
							sel[0] = slots[k]
					elif e[1] in (pygame.K_ESCAPE, pygame.K_e, pygame.K_RETURN):
						return
					elif e[1] == pygame.K_p:
						act = 'Prod'
					elif e[1] == pygame.K_l:
						act = 'Loc'
					elif e[1] == pygame.K_s:
						act = 'Stop'
				elif e[0] == 'down' and e[2] == 1:
					for name, r in btns.items():
						if _inside(e[1], r):
							pressed[0] = name
					for k, t in enumerate(slots):
						x, y = opt_pos[k]
						if x <= e[1][0] < x + 150 and y - 2 <= e[1][1] < y + 14:
							sel[0] = t
				elif e[0] == 'up' and e[2] == 1:
					if pressed[0] and _inside(e[1], btns[pressed[0]]):
						act = pressed[0]
					pressed[0] = None
				msg[0] = None
				if act == 'Exit':
					return
				if act == 'Stop':
					g.stop_production(city)
				if act == 'Prod' and sel[0] is not None:
					if not g.start_production(city, sel[0]):
						msg[0] = "Not enough gold!"
						self.message("Not enough gold!")
				if act == 'Loc' and sel[0] is not None and sel[0] != NAVY and s.ncities[p] > 1:
					tgt = self.pick_city_on_map("Click on the destination city")
					if tgt is not None and tgt.owner == p and tgt is not city:
						if len(g.vectors_into(tgt)) >= 4:
							self.message("%s is full!" % tgt.name)
						elif g.start_production(city, sel[0], vector_to=tgt):
							self.message("Production transferred from %s to %s" % (city.name, tgt.name))
						else:
							self.message("Not enough gold!")
			scr.tick(30)

	def _mark_city(self, c):
		s = self.s
		if s.view_x <= c.x < s.view_x + VIEW_W and s.view_y <= c.y < s.view_y + VIEW_H:
			px = MAP_X + (c.x - s.view_x) * 40
			py = MAP_Y + (c.y - s.view_y) * 20
			if (self.anim // 8) % 2 == 0:
				self.scr.box((px, py, 80, 40), YELLOW)

	def pick_city_on_map(self, prompt):
		"""Let the player click a city (vectoring). Returns a City or None."""
		s = self.s
		self.status_msg = prompt
		try:
			while True:
				self.draw_main()
				self.scr.cursor = 'tower'
				self.scr.present()
				for e in self.events():
					if e[0] == 'key' and e[1] == pygame.K_ESCAPE:
						return None
					if e[0] == 'up' and e[2] == 3:
						return None
					if e[0] == 'up' and e[2] == 1:
						t = self.tile_at(e[1])
						if t:
							return s.city_at(*t)
						m = self.mini_at(e[1])
						if m:
							self.game.center_view(*m)
				self.scr.tick(30)
		finally:
			self.status_msg = None

	# ==================================================================
	# coordinates
	# ==================================================================
	def tile_at(self, pos):
		x, y = pos
		if MAP_X <= x < MAP_X + 360 and MAP_Y <= y < MAP_Y + 160:
			return (self.s.view_x + (x - MAP_X) // 40, self.s.view_y + (y - MAP_Y) // 20)
		return None

	def mini_at(self, pos):
		x, y = pos
		if MINI_X + 2 <= x < MINI_X + 220 and MINI_Y + 2 <= y < MINI_Y + 158:
			return ((x - MINI_X - 2) // 2, y - MINI_Y - 2)
		return None

	# ==================================================================
	# the human turn
	# ==================================================================
	def human_turn(self, game, p):
		self.game = game
		self.fast = False
		s = game.s
		self.mode = 'army'
		self.info_lines = None
		self.end_turn = False
		self.result = None
		first = True
		rdown = None
		while not self.end_turn and not game.quit:
			if first:
				first = False
				game.human_turn_production(p)
				if s.turn == 1:
					self.info_lines = None
			self.anim += 1
			self.update_cursor()
			self.draw_main()
			if rdown is not None:
				self.draw_menu(self.scr.mouse)
			self.scr.present()
			for e in self.events():
				if e[0] == 'down' and e[2] == 3:
					rdown = e[1]
					self.info_lines = None
				elif e[0] == 'up' and e[2] == 3:
					cmd = self.menu_hit(e[1])
					start = rdown
					rdown = None
					if cmd:
						self.command(cmd)
					else:
						t = self.tile_at(e[1])
						if t and start and self.tile_at(start) == t:
							self.info_lines = self.tile_info(*t)
				elif rdown is not None:
					continue
				elif e[0] == 'down' and e[2] == 1:
					self.info_lines = None
					self.left_click(e[1])
				elif e[0] == 'wheel':
					pass
				elif e[0] == 'key':
					self.key(e[1], e[2])
				if self.end_turn or game.quit:
					break
			self.scr.tick(30)
		game.deselect()
		return 'quit' if game.quit else 'end'

	def update_cursor(self):
		s = self.s
		pos = self.scr.mouse
		t = self.tile_at(pos)
		c = 'arrow'
		if t is not None:
			if self.mode == 'info':
				c = 'info'
			elif self.mode == 'prod':
				c = 'tower'
			elif s.cur_army is not None:
				cur = s.armies[s.cur_army]
				if t == (cur.x, cur.y):
					c = 'select'
				elif self.game.attack_target_ok(*t):
					c = 'sword'
				else:
					d = dirto(cur.x, cur.y, t[0], t[1])
					c = DIR_CURSORS[d] if d != 0xff else 'arrow'
		self.scr.cursor = c

	def left_click(self, pos):
		g = self.game
		s = self.s
		for name, rect, grey, red in BUTTONS:
			if _inside(pos, rect):
				self.button(name)
				return
		m = self.mini_at(pos)
		if m is not None:
			g.center_view(*m)
			return
		t = self.tile_at(pos)
		if t is None:
			return
		x, y = t
		p = s.current
		now = pygame.time.get_ticks()
		double = (now - self.last_click[0] < 400 and self.last_click[1] == t)
		self.last_click = (now, t)
		if self.mode == 'info':
			self.info_lines = self.tile_info(x, y)
			return
		if self.mode == 'prod':
			c = s.city_at(x, y)
			if c is not None and c.owner == p:
				self.production_panel(c)
			return
		own_here = [a for a in s.armies_at(x, y) if a.owner == p]
		if s.cur_army is not None:
			cur = s.armies[s.cur_army]
			if (x, y) == (cur.x, cur.y):
				mods = pygame.key.get_mods()
				if double or mods & (pygame.KMOD_ALT | pygame.KMOD_SHIFT):
					g.select_stack(x, y, True)
				else:
					g.select_stack(x, y, False)
				return
			if g.attack_target_ok(x, y):
				g.attack(x, y)
				return
			if own_here and max(abs(x - cur.x), abs(y - cur.y)) > 1 and False:
				g.select_stack(x, y, False)
				return
			n = g.move_to(x, y)
			if n == -1:
				self.message("You cannot move there!", wait=False)
			return
		if own_here:
			mods = pygame.key.get_mods()
			g.select_stack(x, y, bool(double or mods & (pygame.KMOD_ALT | pygame.KMOD_SHIFT)))
			return
		g.center_view(x, y)

	def button(self, name):
		g = self.game
		s = self.s
		if name == 'army':
			if self.mode == 'army':
				g.deselect()
			self.mode = 'army'
		elif name == 'prod':
			self.mode = 'army' if self.mode == 'prod' else 'prod'
			if self.mode == 'prod':
				g.deselect()
		elif name == 'info':
			self.mode = 'army' if self.mode == 'info' else 'info'
		elif name == 'ctr':
			if s.cur_army is not None:
				a = s.armies[s.cur_army]
				g.center_view(a.x, a.y)
			else:
				g.center_on_capital()
		elif name == 'nxt':
			self.mode = 'army'
			a = g.next_army()
			if a is not None:
				g.center_view(a.x, a.y)
			else:
				self.message("No more armies to move!", wait=False)
		elif name == 'quit':
			g.skip()
		elif name == 'def':
			g.sentry()

	def key(self, k, mod):
		g = self.game
		s = self.s
		if mod & pygame.KMOD_ALT and k in ALT_KEYS:
			self.command(ALT_KEYS[k])
			return
		if mod & pygame.KMOD_CTRL and k == pygame.K_q:
			self.command('quit')
			return
		if k in NUMPAD and s.cur_army is not None:
			d = NUMPAD[k]
			cur = s.armies[s.cur_army]
			tx, ty = cur.x + DX[d], cur.y + DY[d]
			if g.attack_target_ok(tx, ty):
				g.attack(tx, ty, d)
			else:
				g.step(d)
			return
		if k == pygame.K_ESCAPE:
			self.mode = 'army'
			g.deselect()
			return
		if k in (pygame.K_e,) and mod & pygame.KMOD_SHIFT:
			self.command('endturn')
			return
		if k in KEYS:
			self.command(KEYS[k])
		elif 32 <= k < 127 and not mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
			self.beep()

	# ==================================================================
	# menus
	# ==================================================================
	def draw_menu(self, pos):
		scr = self.scr
		mono = self.assets.mono
		scr.fill((0, 0, 640, 10), WHITE)
		scr.blit(self.assets.sprite('ARMIES', 0, 191, 640, 9, 0, None), (0, 1))
		hit = self._menu_title_at(pos)
		for mi, (title, x, items) in enumerate(MENUS):
			if hit is not None and hit[0] == mi:
				scr.fill((x, 1, mono.width(title) + 4, 9), ORANGE)
				scr.text(x + 2, 2, title, WHITE, mono)
				self._draw_dropdown(mi, pos)

	def _menu_title_at(self, pos):
		x, y = pos
		mono = self.assets.mono
		if not hasattr(self, '_menu_sel'):
			self._menu_sel = None
		if y < 11:
			for mi, (title, tx, items) in enumerate(MENUS):
				if tx - 4 <= x < tx + mono.width(title) + 8:
					self._menu_sel = mi
		return (self._menu_sel,) if self._menu_sel is not None else None

	def _dropdown_rect(self, mi):
		mono = self.assets.mono
		title, x, items = MENUS[mi]
		w = max(mono.width(it[0]) + mono.width(it[2]) + 32 for it in items if it) + 8
		h = sum(10 if it else 4 for it in items) + 4
		x = min(x, 640 - w - 2)
		return (x, 11, w, h)

	def _draw_dropdown(self, mi, pos):
		scr = self.scr
		mono = self.assets.mono
		title, tx, items = MENUS[mi]
		x, y, w, h = self._dropdown_rect(mi)
		scr.fill((x, y, w, h), BLACK)
		scr.fill((x + 1, y, w - 2, h - 1), WHITE)
		yy = y + 2
		for it in items:
			if it is None:
				scr.hline(x + 1, x + w - 2, yy + 1, BLACK)
				yy += 4
				continue
			label, cmd, key = it
			label = self._menu_label(cmd, label)
			if x <= pos[0] < x + w and yy <= pos[1] < yy + 10:
				scr.fill((x + 1, yy, w - 2, 10), ORANGE)
				col = WHITE
			else:
				col = BLACK
			scr.text(x + 4, yy + 1, label, col, mono)
			scr.text(x + w - mono.width(key) - 4, yy + 1, key, col, mono)
			yy += 10

	def _menu_label(self, cmd, label):
		s = self.s
		if cmd == 'observe':
			return "Observe Off" if s.global_observe else "Observe On "
		if cmd == 'sound':
			return "Sound On " if not self.sound else "Sound Off"
		return label

	def menu_hit(self, pos):
		sel = getattr(self, '_menu_sel', None)
		self._menu_sel = None
		if sel is None:
			return None
		title, tx, items = MENUS[sel]
		x, y, w, h = self._dropdown_rect(sel)
		yy = y + 2
		for it in items:
			if it is None:
				yy += 4
				continue
			if x <= pos[0] < x + w and yy <= pos[1] < yy + 10:
				return it[1]
			yy += 10
		return None

	# ==================================================================
	# commands
	# ==================================================================
	def command(self, cmd):
		g = self.game
		s = self.s
		p = s.current
		if cmd == 'endturn':
			if g.surrender_check() == 0:
				self.end_turn = True
		elif cmd == 'quit':
			ans = self.ask(["Exit to DOS?", "This won't be popular!"], [" Yes ", " No "])
			if ans == 0:
				g.quit = True
		elif cmd == 'about':
			self.about()
		elif cmd == 'observe':
			s.global_observe = 0 if s.global_observe else 1
		elif cmd == 'sound':
			self.sound = not self.sound
		elif cmd == 'save':
			self.save_dialog()
		elif cmd == 'load':
			path = self.load_dialog()
			if path:
				g.restart = path
				g.quit = True
		elif cmd == 'build':
			g.build()
		elif cmd == 'capital':
			g.center_on_capital()
		elif cmd == 'disband':
			g.disband()
		elif cmd == 'raze':
			g.raze()
		elif cmd == 'search':
			if s.cur_army is None:
				self.message("An army must be selected to search")
			else:
				g.search()
		elif cmd == 'take':
			self.take()
		elif cmd == 'drop':
			self.drop()
		elif cmd == 'inv':
			self.inventory()
		elif cmd == 'find':
			self.find_hero()
		elif cmd == 'nxt':
			self.button('nxt')
		elif cmd.startswith('r_'):
			self.report(cmd[2:])
		elif cmd == 'v_stack':
			self.view_stack()
		elif cmd == 'v_prod':
			self.view_production()
		elif cmd == 'v_heroes':
			self.view_heroes()
		elif cmd == 'v_ruins':
			self.view_ruins()
		elif cmd == 'v_control':
			self.view_control()

	def about(self):
		lines = ["W A R L O R D S  Ver 2.10", "Design, Graphics & Programming", "by Steve Fawkner",
			"AI by Roger Keating", "IBM version by Stephen Hart", "A Gregor Whiley Production",
			"", "Python reimplementation (pywarlords)"]
		self.ask(lines, ["  OK  "])

	# ------------------------------------------------------------------
	def tile_info(self, x, y):
		s = self.s
		g = self.game
		p = s.current
		w = s.tile(x, y)
		cls = s.tclass(x, y)
		names = ["Road", "Bridge", "Water", "Shore", "Forest", "Hill", "Mountain", "Plain", "Marsh", "Tower",
			"City", "Ruins"]
		lands = g.region_name(x, y)
		col1 = [("Name:", g.clan_name(p))]
		col3 = [("Command:", "Info")]
		if cls == CITY:
			c = s.city_at(x, y)
			col1 += [("City:", c.name), ("Owner:", g.clan_name(c.owner))]
			col3 += [("Defence:", str(c.defence)), ("Income:", "%d gp" % c.income)]
		elif cls == RUINS:
			st = s.site_at(x, y)
			if st is not None:
				if (w & 0x7f) == 11:
					kind = {1: "Library", 2: "Sage", 3: "Healers"}.get(st.type, "Ruins")
					col1 += [("Location:", st.name), ("Status:", kind)]
				else:
					col1 += [("Location:", st.name), ("Status:", "Explored" if w & M_EXPLORED else "Unexplored")]
			else:
				col1 += [("Terrain:", "Ruins")]
			col3 += [("Lands:", lands)]
		else:
			col1 += [("Terrain:", names[cls]), ("Lands:", lands)]
		return [col1, [], col3]

	# ------------------------------------------------------------------
	# items
	def take(self):
		g = self.game
		s = self.s
		if s.cur_army is None or s.cur_hero is None:
			self.message("Hero must be selected to take an item")
			return
		h = s.armies[s.cur_hero]
		its = s.items_on_ground(h.x, h.y)
		if not its:
			self.message("You have found nothing!")
			return
		k = self.choose("Taking an item ...", [it.name for it in its])
		if k is not None:
			g.take_item(its[k])

	def drop(self):
		g = self.game
		s = self.s
		if s.cur_army is None or s.cur_hero is None:
			self.message("Hero must be selected to drop an item")
			return
		h = s.armies[s.cur_hero]
		its = s.items_of(h)
		if not its:
			self.message("%s has no items!" % s.hero_name(h))
			return
		k = self.choose("Dropping an item ...", [it.name for it in its])
		if k is not None:
			g.drop_item(its[k])

	def inventory(self):
		s = self.s
		if s.cur_army is None or s.cur_hero is None:
			self.message("Hero must be selected to Inventory")
			return
		h = s.armies[s.cur_hero]
		its = s.items_of(h)
		lines = ["Inventory of items ...", ""]
		if not its:
			lines.append("None")
		for it in its:
			lines.append("%s  %s %d" % (it.name, "Bat +" if it.kind == 1 else "Com +", it.value))
		self.ask(lines, ["  OK  "])

	def find_hero(self):
		g = self.game
		s = self.s
		heroes = [a for a in s.live_armies() if a.owner == s.current and a.type == HERO and a.x >= 0]
		if not heroes:
			self.message("You have no heroes!")
			return
		k = self.choose("Your heroes...", [s.hero_name(h) for h in heroes])
		if k is not None:
			h = heroes[k]
			g.center_view(h.x, h.y)
			g.select_stack(h.x, h.y, False)
			s.cur_army = h.index
			s.group = [h.index]
			g.compute_group()
			g.set_group_mode(0)

	# ==================================================================
	# reports
	# ==================================================================
	def report(self, kind):
		g = self.game
		s = self.s
		if kind == 'hatreds':
			return self.report_hatreds()
		vals = [0] * 8
		label = {'armies': "Armies", 'cities': "Cities", 'gold': "Gold", 'prod': "Produce",
			'winning': "Winning"}[kind]
		for q in range(8):
			if not s.alive[q]:
				continue
			if kind == 'armies':
				n = sum(1 for a in s.live_armies() if a.owner == q)
				vals[q] = max(1, min(500, n * 500 // 300))
			elif kind == 'cities':
				vals[q] = s.ncities[q] * 500 // 80
			elif kind == 'gold':
				vals[q] = max(1, min(500, s.players[q].gold // 20))
			elif kind == 'prod':
				pr = sum(c.strength[c.prod] for c in s.cities if c.owner == q and c.turns > 0 and 0 <= c.prod < 10)
				vals[q] = max(1, min(500, pr * 10))
			elif kind == 'winning':
				sc = s.players[q].gold + s.upkeep[q] + 5 * s.income[q] + sum(
					c.income * c.defence for c in s.cities if c.owner == q)
				vals[q] = max(1, min(500, sc // 30))
		scr = self.scr

		def draw():
			self.draw_main(status=False)
			scr.fill((0, 167, 640, 33), GREY)
			for q in range(8):
				w = vals[q] * 520 // 500 if vals[q] else 0
				if w:
					scr.fill((18, 169 + q * 4, w, 2), CLAN_COLOURS[q])
			scr.vline(534, 167, 199, DGREY)
			scr.text_center(586, 178, label)

		self.wait_click(draw)

	def report_hatreds(self):
		g = self.game
		s = self.s
		scr = self.scr
		p = s.current
		lead, leader = (0, -1)
		if g.ai is not None:
			old = s.current
			lead, leader = g.ai.lead()
		x, y, w, h = 15, 5, 345, 159

		def draw():
			self.draw_main(status=False)
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.bevel((x + 6, y + 4, w - 12, h - 8), raised=False)
			for q in range(8):
				yy = y + 15 + q * 16
				scr.text(x + 20, yy, g.clan_name(q).replace("The ", ""))
				if not s.alive[q]:
					st = "Deceased"
				elif s.human[q]:
					st = "Human"
				else:
					lvl = s.hatred[q][p] + (lead if p == leader else 0)
					lvl = max(0, min(5, lvl))
					if s.war[q] == p:
						lvl = 6
					st = ["Apathy", "Distrust", "Dislike", "Disdain", "Disgust", "Hatred", "Loathing"][lvl]
				self._draw_level_icon(x + 161, yy - 2, s.human[q], s.level[q])
				scr.text(x + 205, yy, st)
				sw = (600, 20 + q * 16) if s.alive[q] else (600, 148)
				scr.blit(self.assets.sprite('SCENERY', sw[0], sw[1], 34, 16, 0, None), (x + 290, yy - 4))
			scr.fill((0, 167, 640, 33), GREY)
			scr.text_center(320, 178, "How the other leaders view you")

		self.wait_click(draw)

	# ==================================================================
	# views
	# ==================================================================
	def view_stack(self):
		g = self.game
		s = self.s
		if s.cur_army is None:
			self.message("An army must be selected!")
			return
		cur = s.armies[s.cur_army]
		stack = [a for a in s.armies_at(cur.x, cur.y) if a.owner == s.current][:8]
		chosen = set(s.group if s.group_mode else [s.cur_army])
		scr = self.scr
		x, y, w, h = 8, 5, 360, 160

		def draw():
			self.draw_main(status=False)
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.text(x + 50, y + 6, "Name")
			scr.text(x + 230, y + 6, "Move")
			scr.text(x + 280, y + 6, "Strn")
			for i, a in enumerate(stack):
				yy = y + 20 + i * 15
				if a.index in chosen:
					scr.fill((x + 6, yy - 2, w - 12, 14), YELLOW)
				scr.blit(self.assets.army(a.type, a.owner), (x + 8, yy - 2))
				scr.text(x + 50, yy, g.army_name(a)[:30])
				scr.text(x + 236, yy, str(a.moves))
				scr.text(x + 286, yy, str(a.strength))
			scr.button((x + 30, y + h - 20, 50, 15), "All")
			scr.button((x + w - 80, y + h - 20, 50, 15), "OK")
			scr.fill((0, 167, 640, 33), GREY)
			scr.text_center(320, 178, "Select the armies to move")

		while True:
			draw()
			scr.present()
			for e in self.events():
				if e[0] == 'key' and e[1] in (pygame.K_ESCAPE, pygame.K_RETURN):
					g.select_subset([a.index for a in stack if a.index in chosen])
					return
				if e[0] == 'up' and e[2] == 1:
					px, py = e[1]
					if _inside(e[1], (x + 30, y + h - 20, 50, 15)):
						chosen = set(a.index for a in stack)
					elif _inside(e[1], (x + w - 80, y + h - 20, 50, 15)):
						if chosen:
							g.select_subset([a.index for a in stack if a.index in chosen])
						return
					else:
						for i, a in enumerate(stack):
							if x + 6 <= px < x + w - 6 and y + 18 + i * 15 <= py < y + 32 + i * 15:
								if a.index in chosen:
									chosen.discard(a.index)
								else:
									chosen.add(a.index)
			scr.tick(30)

	def view_production(self):
		g = self.game
		s = self.s
		own = [c for c in s.cities if c.owner == s.current]
		if not own:
			return
		k = 0
		if s.cur_army is not None:
			a = s.armies[s.cur_army]
			c = s.city_at(a.x, a.y)
			if c in own:
				k = own.index(c)
		while True:
			c = own[k]
			ans = self._prod_dialog(c)
			if ans == 'next':
				k = (k + 1) % len(own)
			elif ans == 'prev':
				k = (k - 1) % len(own)
			else:
				return

	def _prod_dialog(self, c):
		g = self.game
		s = self.s
		scr = self.scr
		a = self.assets
		p = s.current
		x, y, w, h = 8, 5, 360, 160
		slots = [t for t in range(10) if c.can[t]][:4]
		sel = [c.prod if (c.turns > 0 and c.prod in slots) else (slots[0] if slots else None)]
		btns = {'Next': (x + 18, y + 64, 50, 15), 'Prev': (x + 82, y + 64, 50, 15), 'Prod': (x + 170, y + 64, 50, 15),
			'Loc': (x + 234, y + 64, 40, 15), 'Stop': (x + 288, y + 64, 50, 15), 'OK': (x + 280, y + 138, 60, 15)}
		pressed = [None]
		g.center_view(c.x, c.y)

		def draw():
			self.draw_main(status=False)
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.fill((x + 52, y + 10, 136, 12), DGREEN)
			scr.text(x + 56, y + 12, c.name, YELLOW)
			if c.turns > 0 and 0 <= c.prod < 10:
				scr.fill((x + 196, y + 8, 30, 16), DGREEN)
				scr.blit(a.army(c.prod, p), (x + 195, y + 9))
				scr.text(x + 236, y + 12, "%dt" % c.turns)
			for k, t in enumerate(slots):
				xx = x + 12 + (k % 2) * 170
				yy = y + 30 + (k // 2) * 16
				scr.text(xx, yy + 2, "F%d" % (k + 5))
				if sel[0] == t:
					scr.box((xx + 24, yy - 2, 30, 16), BLACK)
				scr.blit(a.army(t, p), (xx + 23, yy))
				scr.text(xx + 66, yy + 2, "%dt/%dgp" % (c.time[t], c.cost[t]))
			for name, r in btns.items():
				scr.button(r, name, pressed[0] == name)
			# incoming vectors
			inc = g.vectors_into(c)
			for i in range(4):
				yy = y + 88 + i * 15
				scr.fill((x + 52, yy, 136, 12), DGREEN)
				if i < len(inc):
					o = inc[i]
					scr.text(x + 56, yy + 2, o.name, YELLOW)
					if 0 <= o.prod < 10:
						scr.blit(a.army(o.prod, p), (x + 195, yy - 1))
			scr.fill((x + 52, y + 140, 136, 12), DGREEN)
			if c.vector:
				dc = s.city_at(c.vx, c.vy)
				scr.text(x + 22, y + 142, "->")
				scr.text(x + 56, y + 142, dc.name if dc else "?", YELLOW)
			self._mark_city(c)

		while True:
			draw()
			self.anim += 1
			scr.cursor = 'arrow'
			scr.present()
			for e in self.events():
				act = None
				if e[0] == 'key':
					if pygame.K_F5 <= e[1] <= pygame.K_F8 and e[1] - pygame.K_F5 < len(slots):
						sel[0] = slots[e[1] - pygame.K_F5]
					elif e[1] in (pygame.K_ESCAPE, pygame.K_RETURN):
						return 'ok'
					elif e[1] == pygame.K_n:
						return 'next'
				elif e[0] == 'down' and e[2] == 1:
					for name, r in btns.items():
						if _inside(e[1], r):
							pressed[0] = name
					for k, t in enumerate(slots):
						xx = x + 12 + (k % 2) * 170
						yy = y + 30 + (k // 2) * 16
						if xx <= e[1][0] < xx + 150 and yy - 2 <= e[1][1] < yy + 14:
							sel[0] = t
				elif e[0] == 'up' and e[2] == 1:
					if pressed[0] and _inside(e[1], btns[pressed[0]]):
						act = pressed[0]
					pressed[0] = None
				if act == 'OK':
					return 'ok'
				if act == 'Next':
					return 'next'
				if act == 'Prev':
					return 'prev'
				if act == 'Stop':
					g.stop_production(c)
				if act == 'Prod' and sel[0] is not None:
					# the production screen ignores Enhance (original quirk)
					if not g.start_production(c, sel[0], enhance=False):
						self.message("Not enough gold!")
				if act == 'Loc' and sel[0] is not None and sel[0] != NAVY:
					tgt = self.pick_city_on_map("Click on the destination city")
					if tgt is not None and tgt.owner == p and tgt is not c:
						if len(g.vectors_into(tgt)) < 4:
							g.start_production(c, sel[0], vector_to=tgt, enhance=False)
			scr.tick(30)

	def view_heroes(self):
		g = self.game
		s = self.s
		heroes = [a for a in s.live_armies() if a.owner == s.current and a.type == HERO and a.x >= 0][:12]
		if not heroes:
			self.message("You have no heroes!")
			return
		scr = self.scr
		k = 0
		while True:
			h = heroes[k]
			g.center_view(h.x, h.y)
			bat = g.bat_bonus(h)
			cmd = g.cmd_items(h)
			c = s.city_at(h.x, h.y)
			near = c
			if c is None:
				best = 10000
				from ..rng import dist
				for cc in reversed(s.cities):
					d = dist(h.x, h.y, cc.x, cc.y)
					if d < best:
						best = d
						near = cc
			lines = [s.hero_name(h), "%s %s" % ("In" if c is not None else "Near", near.name if near else ""),
				"Strength: %d   Move: %d" % (h.strength, h.moves), "Bat + %d   Com + %d" % (bat, cmd)]
			for it in s.items_of(h):
				lines.append("%s  %s %d" % (it.name, "Bat +" if it.kind == 1 else "Com +", it.value))
			ans = self.ask(lines, [" Next ", " Prev ", " Exit "])
			if ans == 0:
				k = (k + 1) % len(heroes)
			elif ans == 1:
				k = (k - 1) % len(heroes)
			else:
				return

	def view_ruins(self):
		"""'Status of special locations': markers on the strategic map."""
		s = self.s
		a = self.assets
		scr = self.scr

		def markers():
			for k in range(39, -1, -1):
				st = s.sites[k]
				explored = s.tile(st.x, st.y) & M_EXPLORED
				if st.type == 3:
					sx = 124
				elif st.type == 1:
					sx = 133
				elif (st.type == 2 and ((k == 1 and s.gem_seer) or (k == 7 and s.gem_oracle))) or \
						(st.type not in (1, 2, 3) and explored):
					sx = 121
				else:
					sx = 112
				scr.blit(a.sprite('ARMIES', 392, sx, 6, 3, 0, None), (MINI_X + 2 * st.x + 2, MINI_Y + st.y + 2))

		def draw():
			self.draw_main(status=False)
			scr.blit(a.surface('STRAT'), (MINI_X, MINI_Y))
			markers()
			scr.fill((0, 167, 640, 33), GREY)
			scr.text_center(320, 178, "Status of special locations")

		self.wait_click(draw)

	def view_control(self):
		g = self.game
		s = self.s
		scr = self.scr
		x, y, w, h = 8, 5, 360, 160
		cols = [("Player", 14), ("Control", 140), ("Observe", 205), ("Enhance", 275)]

		def draw():
			self.draw_main(status=False)
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			for name, cx in cols:
				scr.text(x + cx, y + 6, name)
			for q in range(8):
				yy = y + 20 + q * 15
				scr.text(x + 14, yy, g.clan_name(q))
				if not s.alive[q]:
					scr.text(x + 150, yy, "Deceased")
					continue
				scr.text(x + 140, yy, "Human" if s.human[q] else self.data.level_names[s.level[q]])
				if not s.human[q]:
					scr.text(x + 215, yy, "Yes" if s.observe[q] else "No")
				scr.text(x + 285, yy, "Yes" if s.enhance[q] else "No")
			scr.text(x + 14, y + h - 18, "Intense Combat: %s" % ("On" if s.intense else "Off"))
			scr.button((x + w - 70, y + h - 20, 50, 15), "OK")
			scr.fill((0, 167, 640, 33), GREY)
			scr.text_center(320, 178, "Click to change the settings")

		while True:
			draw()
			scr.present()
			for e in self.events():
				if e[0] == 'key' and e[1] in (pygame.K_ESCAPE, pygame.K_RETURN):
					return
				if e[0] == 'up' and e[2] == 1:
					px, py = e[1]
					if _inside(e[1], (x + w - 70, y + h - 20, 50, 15)):
						return
					if y + h - 20 <= py < y + h - 6 and x + 10 <= px < x + 200:
						s.intense = 0 if s.intense else 1
					for q in range(8):
						if y + 18 + q * 15 <= py < y + 32 + q * 15 and s.alive[q]:
							if x + 150 <= px < x + 205 and q != s.current:
								s.human[q] = 0 if s.human[q] else 1
							elif x + 205 <= px < x + 265 and not s.human[q]:
								s.observe[q] = 0 if s.observe[q] else 1
							elif x + 265 <= px < x + 330:
								s.enhance[q] = 0 if s.enhance[q] else 1
			scr.tick(30)

	# ==================================================================
	# save / load
	# ==================================================================
	def _slot_path(self, i):
		return os.path.join(self.save_dir, "WAR%d.SAV" % (i + 1))

	def _slot_names(self):
		import struct
		names = []
		for i in range(8):
			p = self._slot_path(i)
			alt = os.path.join(self.save_dir, "war%d.sav" % (i + 1))
			if not os.path.exists(p) and os.path.exists(alt):
				p = alt
			if os.path.exists(p):
				with open(p, 'rb') as f:
					names.append(f.read(16).split(b'\0')[0].decode('latin1') or "(saved)")
			else:
				names.append(None)
		return names

	def _slots_dialog(self, title):
		scr = self.scr
		names = self._slot_names()
		x, y, w, h = 56, 24, 210, 116
		sel = [0]
		draw_bg = self.draw_main if self.game is not None else (lambda: None)

		def draw():
			draw_bg()
			scr.fill((x - 1, y - 1, w + 2, h + 2), BLACK)
			scr.bevel((x, y, w, h))
			scr.button((x + 10, y + 6, 50, 14), title)
			scr.button((x + w - 64, y + 6, 54, 14), "Cancel")
			for i in range(8):
				cx = x + 10 + (i // 4) * 100
				cy = y + 28 + (i % 4) * 20
				scr.button((cx, cy, 14, 14), str(i + 1), sel[0] == i)
				scr.fill((cx + 18, cy + 1, 72, 12), DGREY if sel[0] != i else YELLOW)
				scr.text(cx + 20, cy + 3, (names[i] or "not used")[:11])

		while True:
			draw()
			scr.cursor = 'arrow'
			scr.present()
			for e in self.events():
				if e[0] == 'key':
					if e[1] == pygame.K_ESCAPE:
						return None, names
					if pygame.K_1 <= e[1] <= pygame.K_8:
						sel[0] = e[1] - pygame.K_1
					if e[1] in (pygame.K_RETURN, pygame.K_KP_ENTER):
						return sel[0], names
				if e[0] == 'up' and e[2] == 1:
					if _inside(e[1], (x + 10, y + 6, 50, 14)):
						return sel[0], names
					if _inside(e[1], (x + w - 64, y + 6, 54, 14)):
						return None, names
					for i in range(8):
						cx = x + 10 + (i // 4) * 100
						cy = y + 28 + (i % 4) * 20
						if _inside(e[1], (cx, cy, 92, 14)):
							sel[0] = i
			scr.tick(30)

	def load_dialog(self):
		k, names = self._slots_dialog("Load")
		if k is None or names[k] is None:
			return None
		p = self._slot_path(k)
		if not os.path.exists(p):
			p = os.path.join(self.save_dir, "war%d.sav" % (k + 1))
		return p

	def save_dialog(self):
		k, names = self._slots_dialog("Save")
		if k is None:
			return
		name = self.text_input("Name", names[k] or "")
		self.s.save_name = name
		try:
			self.s.save(self._slot_path(k))
			self.message("Game saved.")
		except OSError:
			self.message("Error occured in saving")


def _inside(p, r):
	return r[0] <= p[0] < r[0] + r[2] and r[1] <= p[1] < r[1] + r[3]
