"""Static game data read directly from the original WARLORDS.EXE (v2.10).

Nothing copyrighted is shipped with this package: every table (cities, sites,
items, names, movement costs, combat modifiers, palettes, AI tables ...) is
read at start-up from the user's own copy of the game.

Offsets are DGROUP (DS) offsets as found by reverse engineering, or absolute
load-image offsets for tables living in far data segments.
"""
import os
import struct

from . import lzexe

# --- army types -----------------------------------------------------------
GIANT, HEAVY, LIGHT, DWARF, CAVALRY, NAVY, ELVES, WOLF, PEGASI, GRIFFIN, \
	WIZARD, UNDEAD, DRAGON, DEMON, DEVIL, HERO = range(16)

# --- terrain classes ------------------------------------------------------
ROAD, BRIDGE, WATER, SHORE, FOREST, HILL, MOUNTAIN, PLAIN, MARSH, TOWER, CITY, RUINS = range(12)

NEUTRAL = 15
IMPASSABLE = 66
MAP_W, MAP_H = 109, 156

DX = (0, 1, 1, 1, 0, -1, -1, -1, 0)
DY = (-1, -1, 0, 1, 1, 1, 0, -1, 0)
CITY_DX = (0, 1, 0, 1)
CITY_DY = (0, 0, 1, 1)

HATRED_NAMES = ["Apathy", "Distrust", "Dislike", "Disdain", "Disgust", "Hatred", "Loathing"]


class City:
	__slots__ = ('index', 'x', 'y', 'name', 'defence', 'owner', 'can', 'time', 'strength', 'moves',
		'cost', 'prod', 'elapsed', 'turns', 'port', 'income', 'prev_owner', 'vector', 'vx', 'vy',
		'ai_target', 'island', 'ai_type', 'ai_strong', 'unused62')

	def copy(self):
		c = City.__new__(City)
		for k in City.__slots__:
			v = getattr(self, k)
			setattr(c, k, list(v) if isinstance(v, list) else v)
		return c


class Site:
	__slots__ = ('index', 'x', 'y', 'name', 'type', 'item', 'monster', 'pad')

	def copy(self):
		s = Site.__new__(Site)
		for k in Site.__slots__:
			setattr(s, k, getattr(self, k))
		return s


class Item:
	__slots__ = ('index', 'name', 'kind', 'value', 'state', 'pad', 'loc', 'x', 'y')

	def copy(self):
		s = Item.__new__(Item)
		for k in Item.__slots__:
			setattr(s, k, getattr(self, k))
		return s


def _find_game_file(folder, *names):
	if os.path.isfile(folder) and not names:
		return folder
	try:
		entries = os.listdir(folder)
	except OSError:
		return None
	lower = {e.lower(): e for e in entries}
	for n in names:
		if n.lower() in lower:
			return os.path.join(folder, lower[n.lower()])
	return None


def find_file(folder, relpath):
	"""Case-insensitive lookup of 'PICTS/SCENERY.PCK' style paths."""
	parts = relpath.replace('\\', '/').split('/')
	cur = folder
	for p in parts:
		nxt = _find_game_file(cur, p)
		if nxt is None:
			return None
		cur = nxt
	return cur


class GameData:
	"""All static data of Warlords, extracted from the executable."""

	def __init__(self, game_dir):
		self.game_dir = game_dir
		exe = find_file(game_dir, 'WARLORDS.EXE')
		if exe is None:
			raise FileNotFoundError("WARLORDS.EXE not found in %r" % game_dir)
		with open(exe, 'rb') as f:
			raw = f.read()
		if lzexe.is_lzexe(raw):
			img = lzexe.unpack_image(raw)
		else:
			hdr = struct.unpack_from('<H', raw, 8)[0] * 16
			img = raw[hdr:]
		self.img = img
		ds = img.find(b'MS Run-Time Library')
		if ds < 0 or b'Warlords Version 2.10' not in img:
			raise ValueError("Unsupported WARLORDS.EXE (expected version 2.10)")
		self.dsb = ds - 8
		self._load()
		mp = find_file(game_dir, 'ILLURIA.MAP')
		if mp is None:
			raise FileNotFoundError("ILLURIA.MAP not found in %r" % game_dir)
		with open(mp, 'rb') as f:
			mdata = f.read()
		words = struct.unpack('<%dH' % (MAP_W * MAP_H), mdata[:MAP_W * MAP_H * 2])
		# the game byte-swaps every word when loading the map (FUN_109f_0f9c)
		self.map_words = [((w >> 8) | ((w & 0xff) << 8)) for w in words]

	# --- low level readers ---
	def w(self, off, n=None):
		if n is None:
			return struct.unpack_from('<h', self.img, self.dsb + off)[0]
		return list(struct.unpack_from('<%dh' % n, self.img, self.dsb + off))

	def b(self, off, n):
		return list(struct.unpack_from('<%db' % n, self.img, self.dsb + off))

	def ub(self, off, n):
		return list(self.img[self.dsb + off:self.dsb + off + n])

	def s(self, off):
		p = self.dsb + off
		e = self.img.index(b'\0', p)
		return self.img[p:e].decode('latin1')

	def strs(self, ptr_off, n):
		return [self.s(p & 0xffff) for p in self.w(ptr_off, n)]

	def far_w(self, img_off, n):
		return list(struct.unpack_from('<%dh' % n, self.img, img_off))

	def _load(self):
		# palettes: 4 sets of R[16], G[16], B[16] VGA DAC values (6 bit)
		self.palettes = []
		for k in range(4):
			r = self.w(0x940 + 32 * k, 16)
			g = self.w(0x9c0 + 32 * k, 16)
			b = self.w(0xa40 + 32 * k, 16)
			self.palettes.append([((rr << 2) | (rr >> 4), (gg << 2) | (gg >> 4), (bb << 2) | (bb >> 4))
				for rr, gg, bb in zip(r, g, b)])

		self.army_names = self.strs(0x44f2, 16)
		self.clan_names = self.strs(0x7eac, 9)
		self.terrain_class = self.w(0x3934, 128)
		self.move_cost = [self.w(0x37b4 + t * 24, 12) for t in range(16)]
		self.prio = self.ub(0x32ea, 16)
		self.monster_names = self.strs(0x242e, 10)
		self.monster_strength = self.w(0x2442, 10)
		self.region_names = self.strs(0x68a4, 8)
		self.quotes = self.strs(0x781a, 12)
		self.site_phrases = self.strs(0x7c82, 9)
		self.hero_names = self.strs(0x2a1c, 63)
		self.hero_suffixes = self.strs(0x2a06, 11)
		self.level_names = self.strs(0x3f04, 4)
		self.tile_sheet_col = self.w(0x3090, 126)
		self.tile_sheet_row = self.w(0x318c, 126)

		# cities
		self.cities = []
		for i in range(80):
			o = self.dsb + 0x4632 + 100 * i
			r = self.img[o:o + 100]
			c = City.__new__(City)
			c.index = i
			c.x, c.y = struct.unpack_from('<hh', r, 0)
			c.name = r[4:24].split(b'\0')[0].decode('latin1')
			c.defence = struct.unpack_from('<b', r, 0x18)[0]
			c.owner = r[0x19]
			c.can = list(r[0x1a:0x24])
			c.time = list(r[0x24:0x2e])
			c.strength = list(r[0x2e:0x38])
			c.moves = list(r[0x38:0x42])
			c.cost = list(r[0x42:0x4c])
			c.prod = struct.unpack_from('<b', r, 0x4c)[0]
			c.elapsed = struct.unpack_from('<b', r, 0x4d)[0]
			c.turns = struct.unpack_from('<b', r, 0x4e)[0]
			c.port = struct.unpack_from('<b', r, 0x4f)[0]
			(c.income, c.prev_owner, c.vector, c.vx, c.vy, c.ai_target, c.island, c.ai_type,
				c.ai_strong, c.unused62) = struct.unpack_from('<10h', r, 0x50)
			self.cities.append(c)

		# special sites
		self.sites = []
		for i in range(40):
			o = self.dsb + 0x7ec6 + 28 * i
			r = self.img[o:o + 28]
			s = Site.__new__(Site)
			s.index = i
			s.x, s.y = struct.unpack_from('<hh', r, 0)
			s.name = r[4:24].split(b'\0')[0].decode('latin1')
			s.type, s.item, s.monster, s.pad = r[24], r[25], r[26], r[27]
			self.sites.append(s)

		# items
		self.items = []
		for i in range(14):
			o = self.dsb + 0x217e + 30 * i
			r = self.img[o:o + 30]
			it = Item.__new__(Item)
			it.index = i
			it.name = r[0:20].split(b'\0')[0].decode('latin1')
			it.kind = r[0x14]
			it.value = struct.unpack_from('<b', r, 0x15)[0]
			it.state = r[0x16]
			it.pad = r[0x17]
			it.loc, it.x, it.y = struct.unpack_from('<hhh', r, 0x18)
			self.items.append(it)

		# initial player records (8 x 20 bytes at DS:0x20de)
		self.player_init = [self.w(0x20de + 20 * p, 10) for p in range(8)]
		self.start_gold = [r[1] for r in self.player_init]
		self.capitals = [(r[3], r[4]) for r in self.player_init]

		# combat tables (far segment, image offset 0x30430)
		cb = 0x30430
		self.city_def_bonus = self.far_w(cb + 0x0000, 11)
		self.hero_cmd = self.far_w(cb + 0x0016, 10)
		self.type_terrain = [self.far_w(cb + 0x002a + t * 24, 12) for t in range(16)]
		self.clan_terrain = [self.far_w(cb + 0x01aa + p * 24, 12) for p in range(16)]
		# economy tables (far segments)
		self.def_cost = self.far_w(0x306d0, 11)
		self.port_dx = self.far_w(0x30730, 13)
		self.port_dy = self.far_w(0x30730 + 0x1a, 13)
		self.ally_templates = []
		for k in range(5):
			o = 0x307b0 + 24 * k
			r = self.img[o:o + 24]
			self.ally_templates.append({'type': r[4], 'maxmoves': r[6], 'moves': r[7],
				'strength': r[8], 'upkeep': r[0x10]})
		self.ally_count = self.w(0x6608, 7)

		# AI tables
		self.ai_class_normal = self.w(0x4396, 16)
		self.ai_class_warlord = self.w(0x43b6, 16)
		self.neighbours = []
		for c in range(80):
			n = self.w(0x3f8a + c * 12, 6)
			self.neighbours.append([v - 1 for v in n if v > 0])
		self.ai_priority = [v - 1 for v in self.w(0x43f4, 6)]
		self.ai_penalty = [v - 1 for v in self.w(0x4400, 7)]
		self.ai_turn1_targets = [self.w(0x3b08 + p * 8, 4) for p in range(8)]
		self.ai_ruin_pref = [[self.ub(0x3a68 + p * 6, 6) for p in range(8)],
			[self.ub(0x3a98 + p * 6, 6) for p in range(8)]]
		self.ai_ruin_bonus = self.w(0x3a54, 6)
		self.natural_enemy = [self.w(0x3f42, 8), self.w(0x3f52, 8)]
		self.difficulty_points = self.w(0x3f34, 4)
		self.ai_max_attacks = self.w(0x43d6, 4)
		self.ai_attack_gold = self.w(0x43de, 7)
		self.ai_thrift_gold = self.w(0x43ec, 4)
		self.flyer_class = self.w(0x4376, 16)

		# path finder tables
		wp = self.w(0x8428, 74)
		self.waypoints = [(wp[2 * i], wp[2 * i + 1]) for i in range(37)]
		pairs = self.w(0x84bc, 64)
		res = self.w(0x853c, 32)
		self.smooth_rules = {}
		for i in range(32):
			key = (pairs[2 * i] & 0xff, pairs[2 * i + 1] & 0xff)
			self.smooth_rules.setdefault(key, res[i] & 0xff)

	def tile_class(self, w):
		return self.terrain_class[w & 0x7f]
