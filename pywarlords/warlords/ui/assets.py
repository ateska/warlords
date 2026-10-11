"""Graphics loaded from the original PICTS/*.PCK files."""
import pygame

from ..pck import load_pck, IndexImage
from ..gamedata import find_file

NATIVE_W, NATIVE_H = 640, 200


class Font:
	"""A bitmap font: glyph masks for ASCII 32..127."""

	def __init__(self, masks, widths, height, spacing=0):
		self.masks = masks      # dict ch -> IndexImage of 0/1 (1 = ink)
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
			g = indexed_surface(m, [(255, 0, 255), tuple(color)] + [(0, 0, 0)] * 254, key_index=0)
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
			colors = [tuple(c) for c in self.pal[pal]]
			colors += [(0, 0, 0)] * (256 - len(colors))
			if key is not None:
				# colour 5 is also black but opaque; make the key colour unique
				colors[key] = (255, 0, 255)
			s = indexed_surface(self.idx[name], colors, key_index=key)
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
		ink = bytes(1 if i == 0 else 0 for i in range(256))
		masks = {}
		widths = {}
		for code in range(32, 128):
			k = code - 32
			cx, cy = (k % 16) * 16, (k // 16) * 9
			cell = f.crop(cx, cy, cx + 16, cy + 9).map(ink)
			cols = [x for x in range(16) if any(cell.pixel(x, y) for y in range(9))]
			w = (cols[-1] + 2) if cols else 6
			masks[code] = cell.crop(0, 0, max(min(w, 16), 1), 9)
			widths[code] = w
		widths[32] = 5
		masks[32] = IndexImage(5, 9, bytes(45))
		self.fant = Font(masks, widths, 9)
		g = self.idx['FONTS']
		ink = bytes(0 if i == 1 else 1 for i in range(256))
		masks = {}
		widths = {}
		for code in range(32, 128):
			k = code - 32
			cx, cy = (k % 32) * 8, 48 + (k // 32) * 8          # black on white band, rows 48..72
			masks[code] = g.crop(cx, cy, cx + 8, cy + 8).map(ink)
			widths[code] = 8
		self.mono = Font(masks, widths, 8)


def indexed_surface(img, colors, key_index=None):
	"""An IndexImage as a pygame surface (8 bit palette surface, then converted)."""
	s = pygame.image.frombuffer(img.data, (img.width, img.height), 'P')
	s.set_palette(colors)
	if key_index is not None:
		s.set_colorkey(colors[key_index])
	try:
		s = s.convert()
	except pygame.error:
		pass
	if key_index is not None:
		s.set_colorkey(colors[key_index])
	return s
