"""Graphics loaded from the original PICTS/*.PCK files."""
import numpy as np
import pygame

from ..pck import load_pck
from ..gamedata import find_file

NATIVE_W, NATIVE_H = 640, 200


class Font:
	"""A bitmap font: glyph masks for ASCII 32..127."""

	def __init__(self, masks, widths, height, spacing=0):
		self.masks = masks      # dict ch -> np.bool_ array (h, w)
		self.widths = widths
		self.height = height
		self.spacing = spacing
		self._cache = {}

	def width(self, text):
		return sum(self.widths.get(ord(c), self.widths.get(32, 4)) for c in text)

	def glyph(self, code, color):
		key = (code, color)
		g = self._cache.get(key)
		if g is None:
			m = self.masks.get(code)
			if m is None:
				m = self.masks.get(ord('?'))
			h, w = m.shape
			arr = np.zeros((w, h, 4), np.uint8)
			arr[..., 0] = color[0]
			arr[..., 1] = color[1]
			arr[..., 2] = color[2]
			arr[..., 3] = (m.T * 255).astype(np.uint8)
			g = pygame.image.frombuffer(arr.transpose(1, 0, 2).copy().tobytes(), (w, h), 'RGBA').convert_alpha()
			self._cache[key] = g
		return g

	def render(self, surf, x, y, text, color, first_color=None):
		for i, ch in enumerate(text):
			code = ord(ch)
			col = first_color if (first_color is not None and i == 0) else color
			if ch != ' ':
				surf.blit(self.glyph(code, col), (x, y))
			x += self.widths.get(code, self.widths.get(32, 4))
		return x


class Assets:

	def __init__(self, data):
		self.data = data
		self.pal = [list(p) for p in data.palettes]
		self.idx = {}
		for name in ('ARMIES', 'SCENERY', 'STRAT', 'FONTS', 'FANT', 'MOUSE', 'CURS', 'COMBAT1', 'COMBAT2',
				'MAIN', 'SETUP', 'RAZE', 'WLC', 'BEG', 'HEAD'):
			path = find_file(data.game_dir, 'PICTS/%s.PCK' % name)
			if path is None:
				raise FileNotFoundError("PICTS/%s.PCK not found" % name)
			self.idx[name] = load_pck(path)
		self.surf = {}
		self.sprite_surf = {}
		self._build_fonts()

	def surface(self, name, pal=0, key=None):
		k = (name, pal, key)
		s = self.surf.get(k)
		if s is None:
			arr = np.array(self.pal[pal], np.uint8)[self.idx[name]]
			h, w = arr.shape[:2]
			s = pygame.image.frombuffer(arr.tobytes(), (w, h), 'RGB').convert()
			if key is not None:
				s.set_colorkey(self.pal[pal][key])
				mask = self.idx[name] == key
				# colour 5 is also black but opaque; make the key colour unique
				arr2 = arr.copy()
				arr2[mask] = (255, 0, 255)
				s = pygame.image.frombuffer(arr2.tobytes(), (w, h), 'RGB').convert()
				s.set_colorkey((255, 0, 255))
			self.surf[k] = s
		return s

	def sprite(self, name, x, y, w, h, pal=0, key=0):
		k = (name, x, y, w, h, pal, key)
		s = self.sprite_surf.get(k)
		if s is None:
			s = self.surface(name, pal, key).subsurface((x, y, w, h)).copy()
			if key is not None:
				s.set_colorkey((255, 0, 255))
			self.sprite_surf[k] = s
		return s

	def color(self, i, pal=0):
		return self.pal[pal][i]

	def tile(self, index):
		d = self.data
		col = d.tile_sheet_col[index & 0x7f]
		row = d.tile_sheet_row[index & 0x7f]
		return self.sprite('SCENERY', col * 40, row * 20, 40, 20, 0, None)

	def army(self, t, owner):
		return self.sprite('ARMIES', t * 32, (owner & 7) * 14, 32, 14)

	# ------------------------------------------------------------------
	def _build_fonts(self):
		f = self.idx['FANT']
		masks = {}
		widths = {}
		for code in range(32, 128):
			k = code - 32
			cx, cy = (k % 16) * 16, (k // 16) * 9
			cell = f[cy:cy + 9, cx:cx + 16]
			m = cell == 0
			cols = np.where(m.any(axis=0))[0]
			w = (cols[-1] + 2) if len(cols) else 6
			masks[code] = m[:, :max(w, 1)]
			widths[code] = w
		widths[32] = 5
		masks[32] = np.zeros((9, 5), bool)
		self.fant = Font(masks, widths, 9)
		g = self.idx['FONTS']
		masks = {}
		widths = {}
		band = g[48:72]           # black on white
		for code in range(32, 128):
			k = code - 32
			cx, cy = (k % 32) * 8, (k // 32) * 8
			cell = band[cy:cy + 8, cx:cx + 8]
			masks[code] = cell != 1
			widths[code] = 8
		self.mono = Font(masks, widths, 8)
