"""Window, scaling and drawing primitives for the 640x200 (EGA/VGA) screen."""
import os
import asyncio
import sys

import pygame

from .assets import NATIVE_W, NATIVE_H

# palette indices of the game palette
BLACK = 0
WHITE = 1
LGREY = 2
GREY = 3
DGREY = 4
BLACK2 = 5
BROWN = 6
DBROWN = 7
CYAN = 8
BLUE = 9
DGREEN = 10
GREEN = 11
LGREEN = 12
RED = 13
ORANGE = 14
YELLOW = 15

# cursor regions in MOUSE.PCK (x0, y0, x1, y1, hotspot)
CURSOR_REGIONS = {
	'arrow': (0, 0, 10, 11, (0, 0)),
	'mapmove': (0, 12, 10, 23, (0, 0)),
	'tower': (16, 0, 31, 23, None),
	'info': (32, 0, 42, 13, None),
	'sword': (46, 4, 68, 17, None),
	'no': (78, 0, 103, 19, None),
	'select': (112, 0, 140, 19, None),
	'ring': (142, 0, 158, 9, None),
	'n': (0, 24, 20, 45, None),
	'ne': (22, 24, 46, 45, None),
	'e': (50, 24, 92, 40, None),
	'se': (92, 24, 128, 45, None),
	'mapmove2': (130, 24, 152, 45, None),
	's': (94, 44, 128, 60, None),
	'sw': (0, 44, 24, 60, None),
	'w': (34, 44, 66, 60, None),
	'nw': (70, 44, 100, 60, None),
	'wait': (118, 44, 136, 60, None),
	'watch': (136, 44, 152, 60, None),
}
DIR_CURSORS = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']


WEB = sys.platform == 'emscripten'


class Screen:

	def __init__(self, assets, scale=2, fullscreen=False):
		self.assets = assets
		self.surface = pygame.Surface((NATIVE_W, NATIVE_H)).convert()
		self.scale = scale
		self.fullscreen = fullscreen
		self._make_window()
		pygame.mouse.set_visible(False)
		self.cursor = 'arrow'
		self._cursors = {}
		self._build_cursors()
		self.mouse = (0, 0)
		self.clock = pygame.time.Clock()

	def _make_window(self):
		flags = pygame.RESIZABLE
		if WEB:
			# the page scales the canvas; 640x400 keeps the 2:1 pixel aspect of the original
			self.window = pygame.display.set_mode((NATIVE_W, NATIVE_H * 2))
		elif self.fullscreen:
			self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
		else:
			self.window = pygame.display.set_mode((NATIVE_W * self.scale, NATIVE_H * 2 * self.scale), flags)
		pygame.display.set_caption("Warlords")

	def toggle_fullscreen(self):
		if WEB:
			return
		self.fullscreen = not self.fullscreen
		self._make_window()

	def _build_cursors(self):
		from .assets import indexed_surface
		idx = self.assets.idx['MOUSE']
		colors = [tuple(c) for c in self.assets.pal[0]] + [(0, 0, 0)] * 240
		colors[9] = (255, 0, 255)                  # colour 9 is transparent in MOUSE.PCK
		for name, (x0, y0, x1, y1, hot) in CURSOR_REGIONS.items():
			sub = idx.crop(x0, y0, x1, y1)
			pts = [(x, y) for y in range(sub.height) for x in range(sub.width) if sub.pixel(x, y) != 9]
			if not pts:
				continue
			xs = [p[0] for p in pts]
			ys = [p[1] for p in pts]
			sub = sub.crop(min(xs), min(ys), max(xs) + 1, max(ys) + 1)
			s = indexed_surface(sub, colors, key_index=9)
			if hot is None:
				hot = (sub.width // 2, sub.height // 2)
			self._cursors[name] = (s, hot)

	# ------------------------------------------------------------------
	def rect_dest(self):
		ww, wh = self.window.get_size()
		aspect = NATIVE_W / (NATIVE_H * 2.0)
		if ww / wh > aspect:
			h = wh
			w = int(h * aspect)
		else:
			w = ww
			h = int(w / aspect)
		return pygame.Rect((ww - w) // 2, (wh - h) // 2, w, h)

	def to_native(self, pos):
		r = self.rect_dest()
		x = (pos[0] - r.x) * NATIVE_W // max(1, r.w)
		y = (pos[1] - r.y) * NATIVE_H // max(1, r.h)
		return max(0, min(NATIVE_W - 1, x)), max(0, min(NATIVE_H - 1, y))

	def present(self, draw_cursor=True):
		frame = self.surface
		if draw_cursor and pygame.mouse.get_focused():
			frame = self.surface.copy()
			c = self._cursors.get(self.cursor) or self._cursors['arrow']
			s, hot = c
			frame.blit(s, (self.mouse[0] - hot[0], self.mouse[1] - hot[1]))
		r = self.rect_dest()
		self.window.fill((0, 0, 0))
		pygame.transform.scale(frame, (r.w, r.h), self.window.subsurface(r))
		pygame.display.flip()

	async def tick(self, fps=30):
		"""End of a frame of a modal loop: hand control back (to the browser under pygbag)."""
		if WEB:
			await asyncio.sleep(0)
		else:
			self.clock.tick(fps)

	# ------------------------------------------------------------------
	# drawing helpers (palette index colours)
	def col(self, i):
		return self.assets.pal[0][i]

	def fill(self, rect, ci):
		self.surface.fill(self.col(ci), rect)

	def hline(self, x0, x1, y, ci):
		self.surface.fill(self.col(ci), (x0, y, x1 - x0 + 1, 1))

	def vline(self, x, y0, y1, ci):
		self.surface.fill(self.col(ci), (x, y0, 1, y1 - y0 + 1))

	def bevel(self, rect, raised=True, face=GREY, lw=4, lh=2):
		"""The SSG style frame: 4 px light left, 2 px light top, dark right/bottom."""
		x, y, w, h = rect
		lt, dk = (LGREY, DGREY) if raised else (DGREY, LGREY)
		self.fill((x, y, w, h), face)
		self.fill((x, y, w, lh), lt)
		self.fill((x, y, lw, h), lt)
		self.fill((x, y + h - lh, w, lh), dk)
		self.fill((x + w - lw, y, lw, h), dk)
		# diagonal corners
		for i in range(lh):
			self.fill((x + w - lw + i * 2, y + i, lw - i * 2, 1), lt if i == 0 else dk)

	def box(self, rect, ci):
		x, y, w, h = rect
		self.fill((x, y, w, 1), ci)
		self.fill((x, y + h - 1, w, 1), ci)
		self.fill((x, y, 1, h), ci)
		self.fill((x + w - 1, y, 1, h), ci)

	def text(self, x, y, s, ci=BLACK, font=None, first=None):
		f = font or self.assets.fant
		return f.render(self.surface, x, y, s, self.col(ci), self.col(first) if first is not None else None)

	def text_center(self, cx, y, s, ci=BLACK, font=None, first=None):
		f = font or self.assets.fant
		return self.text(cx - f.width(s) // 2, y, s, ci, f, first)

	def text_right(self, rx, y, s, ci=BLACK, font=None):
		f = font or self.assets.fant
		return self.text(rx - f.width(s), y, s, ci, f)

	def width(self, s, font=None):
		return (font or self.assets.fant).width(s)

	def button(self, rect, label, pressed=False, ci=RED, hot=BLACK, font=None):
		"""A text button as used in the dialogs ('Load', 'Start', 'OK'...)."""
		x, y, w, h = rect
		self.fill(rect, BLACK)
		self.bevel((x + 1, y + 1, w - 2, h - 2), raised=not pressed, lw=2, lh=1)
		f = font or self.assets.fant
		tw = f.width(label)
		self.text(x + (w - tw) // 2, y + (h - f.height) // 2, label, ci, f, hot)

	def blit(self, surf, pos, area=None):
		self.surface.blit(surf, pos, area)
