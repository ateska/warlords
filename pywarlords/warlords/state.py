"""Mutable game state, mirroring the original memory layout.

The state can be saved to / loaded from the original WAR?.SAV format
(FUN_109f_07b4 / FUN_109f_01a5), so saves are interchangeable with DOS Warlords.
"""
import struct

from .gamedata import MAP_W, MAP_H, NEUTRAL, HERO, CITY_DX, CITY_DY
from .rng import MSRand

MAX_ARMIES = 2000
SAVE_VERSION = 2000

# army flags (+0x12)
F_ACTIVE = 0x0001
F_DONE = 0x0040
F_AI_GROUP = 0x0020
F_AI_MISSION = 0x0080
F_VISITED = 0x0200
F_AI_ERRAND = 0x0800
TEMPLE_BITS = {0: 0x02, 2: 0x04, 5: 0x08, 6: 0x10}

# map word bits
M_INDEX = 0x007f
M_OWNER = 0x0780
M_ARMY = 0x0800
M_EXPLORED = 0x8000


class Army:
	__slots__ = ('index', 'x', 'y', 'type', 'owner', 'maxmoves', 'moves', 'strength', 'home', 'serial',
		'hits', 'pad0d', 'e', 'upkeep', 'pad11', 'flags', 'goal', 'origin')

	def __init__(self, index):
		self.index = index
		self.clear()

	def clear(self):
		self.x = self.y = -1
		self.type = 0xff
		self.owner = 0xff
		self.maxmoves = 0
		self.moves = 0
		self.strength = 0
		self.home = 0
		self.serial = 0
		self.hits = 0
		self.pad0d = 0
		self.e = 0
		self.upkeep = 0
		self.pad11 = 0
		self.flags = 0
		self.goal = -1
		self.origin = -1

	@property
	def free(self):
		return self.owner == 0xff

	@property
	def is_hero(self):
		return self.type == HERO

	def pack(self):
		return struct.pack('<hhBBBbBBhBBhBBHhh', self.x, self.y, self.type & 0xff, self.owner & 0xff,
			self.maxmoves & 0xff, max(-128, min(127, self.moves)), self.strength & 0xff, self.home & 0xff,
			self.serial, self.hits & 0xff, self.pad0d, self.e, self.upkeep & 0xff, self.pad11,
			self.flags & 0xffff, self.goal, self.origin)

	def unpack(self, r):
		(self.x, self.y, self.type, self.owner, self.maxmoves, self.moves, self.strength, self.home,
			self.serial, self.hits, self.pad0d, self.e, self.upkeep, self.pad11, self.flags, self.goal,
			self.origin) = struct.unpack('<hhBBBbBBhBBhBBHhh', r)
		if self.hits > 127:
			self.hits -= 256

	def __repr__(self):
		return "<Army %d t%d o%d (%d,%d) s%d m%d/%d>" % (self.index, self.type, self.owner, self.x,
			self.y, self.strength, self.moves, self.maxmoves)


class Player:
	__slots__ = ('id', 'gold', 'razer', 'cap_x', 'cap_y', 'report_allowed', 'report_done', 'odd',
		'thrift', 'truce')

	def pack(self):
		return struct.pack('<10h', self.id, self.gold, self.razer, self.cap_x, self.cap_y,
			self.report_allowed, self.report_done, self.odd, self.thrift, self.truce)

	def unpack(self, r):
		(self.id, self.gold, self.razer, self.cap_x, self.cap_y, self.report_allowed, self.report_done,
			self.odd, self.thrift, self.truce) = struct.unpack('<10h', r)


def _i16(v):
	v &= 0xffff
	return v - 0x10000 if v & 0x8000 else v


class GameState:

	def __init__(self, data, seed=None):
		self.data = data
		self.rng = MSRand(seed)
		self.reset()

	# ------------------------------------------------------------------
	def reset(self):
		d = self.data
		self.save_name = ""
		self.armies = [Army(i) for i in range(MAX_ARMIES)]
		self.count = 10                       # DS:0xacc8 high-water mark
		self.map = list(d.map_words)
		self.cities = [c.copy() for c in d.cities]
		self.sites = [s.copy() for s in d.sites]
		self.items = [i.copy() for i in d.items]
		self.players = []
		for p in range(8):
			pl = Player()
			pl.unpack(struct.pack('<10h', *d.player_init[p]))
			self.players.append(pl)
		self.upkeep = [0] * 8                 # DS:0x20be
		self.income = d.w(0x20ce, 8)          # DS:0x20ce
		self.ncities = d.w(0x20ae, 8)         # DS:0x20ae
		self.alive = d.w(0x2322, 8)           # DS:0x2322
		self.serial = [1] * 800               # DS:0x6cc0
		self.cur_army = None                  # DS:0xb2e2 (index)
		self.aa60 = 0
		self.turn = 1
		self.group_moves = 0                  # DS:0xb716
		self.gcost = [0] * 12                 # DS:0xcfa8
		self.group_count = 0                  # DS:0xad5e
		self.hero_slot_names = [""] * 40      # DS:0xcc88
		self.hero_slot_used = [0] * 40        # DS:0x65be
		self.hero_slot_raw = [b'\0' * 20] * 40
		self.view_y = 0                       # DS:0xad60
		self.view_x = 0                       # DS:0xb712
		self.view_y2 = 7                      # DS:0xd1ca
		self.view_x2 = 8                      # DS:0xb6f6
		self.cursor_x = 0                     # DS:0xaf00
		self.cursor_y = 0                     # DS:0xaf04
		self.human = [1] * 8                  # DS:0x7e86
		self.current = 0                      # DS:0x7ea6
		self.g7ea8 = 0
		self.hatred = [[0] * 8 for _ in range(8)]   # DS:0xb804
		self.war = [-1] * 8                   # DS:0xcc74
		self.gem_seer = 0                     # DS:0x2478
		self.gem_oracle = 0                   # DS:0x247a
		self.surrender_offered = 0            # DS:0x2474
		self.level = [0] * 8                  # DS:0x7e96
		self.war_over = 0                     # DS:0x2476
		self.observe = [0] * 8                # DS:0x208e
		self.enhance = [0] * 8                # DS:0x209e
		self.name_used = [0] * 100            # DS:0xb32e
		self.suffix = 0                       # DS:0xae24
		self.intense = 0                      # DS:0x2088
		# not saved by the original
		self.group = []                       # DS:0xb2ba (army indices)
		self.group_mode = 0                   # DS:0x377c
		self.cur_hero = None                  # DS:0xb2b6
		self.extra_tough = 0                  # DS:0x2470
		self.global_observe = 1               # DS:0x2086 (menu 'Observe Off/On')
		self.supervisor = 0                   # DS:0x2080
		self.heroes_hired = [0] * 8
		self.ruin_plan = [-1] * 8             # DS:0x3a60
		self.ai_state = [-1] * 80             # DS:0xafbe
		self.last_pos = (0, 0)                # DS:0x37ae/0x37b0

	# ------------------------------------------------------------------
	# map helpers
	def tile(self, x, y):
		return self.map[y * MAP_W + x]

	def set_tile(self, x, y, w):
		self.map[y * MAP_W + x] = w & 0xffff

	def on_map(self, x, y):
		return 0 <= x < MAP_W and 0 <= y < MAP_H

	def tclass(self, x, y):
		return self.data.terrain_class[self.map[y * MAP_W + x] & M_INDEX]

	def towner(self, x, y):
		return (self.map[y * MAP_W + x] >> 7) & 0xf

	def set_towner(self, x, y, owner):
		i = y * MAP_W + x
		self.map[i] = (self.map[i] & 0xf87f) | ((owner & 0xf) << 7)

	def set_tindex(self, x, y, idx):
		i = y * MAP_W + x
		self.map[i] = (self.map[i] & 0xff80) | (idx & 0x7f)

	# ------------------------------------------------------------------
	# armies
	def live_armies(self):
		for i in range(self.count - 1, -1, -1):
			a = self.armies[i]
			if a.owner != 0xff:
				yield a

	def armies_at(self, x, y):
		"""All armies (any owner) on a tile, scanned from the top index down (FUN_2b32_0008)."""
		res = []
		for i in range(self.count - 1, -1, -1):
			a = self.armies[i]
			if a.x == x and a.y == y and a.owner != 0xff:
				res.append(a)
		return res

	def count_at(self, x, y):
		n = 0
		for i in range(self.count):
			a = self.armies[i]
			if a.x == x and a.y == y and a.owner != 0xff:
				n += 1
		return n

	def alloc_army(self, owner):
		"""FUN_2b32_027c."""
		for i in range(MAX_ARMIES):
			a = self.armies[i]
			if a.owner == 0xff:
				a.clear()
				if i + 1 > self.count:
					self.count = i + 1
				a.owner = owner
				a.flags = F_ACTIVE
				a.goal = -1
				a.origin = -1
				return a
		return None

	def free_army(self, a):
		"""FUN_2b32_0318."""
		if 0 <= a.owner < 8:
			self.upkeep[a.owner] -= a.upkeep
		x, y = a.x, a.y
		a.type = 0xff
		a.owner = 0xff
		a.x = a.y = -1
		a.goal = a.origin = -1
		a.moves = 0
		if self.cur_army == a.index:
			self.cur_army = None
		if a.index in self.group:
			self.group = [g for g in self.group if g != a.index]
		if x >= 0 and self.on_map(x, y) and self.count_at(x, y) == 0:
			i = y * MAP_W + x
			self.map[i] &= ~M_ARMY & 0xffff

	def rebuild_army_flags(self):
		"""FUN_274c_0274: recompute the 0x800 occupancy flags from the army list."""
		m = self.map
		for i in range(len(m)):
			m[i] &= 0xf7ff
		for a in self.live_armies():
			if a.x >= 0:
				i = a.y * MAP_W + a.x
				m[i] = (m[i] & 0xf87f) | ((a.owner & 0xf) << 7) | M_ARMY

	# ------------------------------------------------------------------
	# cities
	def city_at(self, x, y):
		"""City whose 2x2 area contains (x,y)."""
		for c in self.cities:
			if c.x <= x <= c.x + 1 and c.y <= y <= c.y + 1:
				return c
		return None

	def city_tiles(self, c):
		return [(c.x + CITY_DX[k], c.y + CITY_DY[k]) for k in range(4)]

	def site_at(self, x, y):
		for s in self.sites:
			if s.x == x and s.y == y:
				return s
		return None

	def gold(self, p):
		return self.players[p].gold

	def add_gold(self, p, v):
		self.players[p].gold = _i16(self.players[p].gold + v)

	def hero_name(self, a):
		if a is None or a.type != HERO:
			return ""
		return self.hero_slot_names[a.serial] if 0 <= a.serial < 40 else "Hero"

	def items_of(self, a):
		return [it for it in self.items if it.state == 3 and it.loc == a.index]

	def items_on_ground(self, x, y):
		return [it for it in self.items if it.state == 1 and it.x == x and it.y == y]

	def recount_cities(self):
		"""FUN_1b90_03f0."""
		self.ncities = [0] * 8
		for c in self.cities:
			if 0 <= c.owner < 8:
				self.ncities[c.owner] += 1

	# ------------------------------------------------------------------
	# save / load in the original format
	def save(self, path):
		out = bytearray()
		name = self.save_name.encode('latin1')[:15]
		out += name + b'\0' * (16 - len(name))
		out += struct.pack('<hh', SAVE_VERSION, self.count)
		for i in range(self.count):
			out += self.armies[i].pack()
		for w in self.map:
			out += struct.pack('<H', w & 0xffff)
		for c in self.cities:
			out += struct.pack('<bbbbbb10h', c.defence, _sb(c.owner), _sb(c.prod), c.elapsed, c.turns, c.port,
				c.income, c.vector, c.vx, c.vy, c.ai_target, c.island, c.ai_type, c.ai_strong, c.unused62,
				c.prev_owner)
		for s in self.sites:
			nm = s.name.encode('latin1')[:19]
			out += struct.pack('<hh', s.x, s.y) + nm + b'\0' * (20 - len(nm)) + bytes([s.type & 0xff,
				s.item & 0xff, s.monster & 0xff, s.pad & 0xff])
		out += struct.pack('<8h', *self.upkeep)
		out += struct.pack('<8h', *self.income)
		out += struct.pack('<8h', *self.ncities)
		for pl in self.players:
			out += pl.pack()
		for it in self.items:
			nm = it.name.encode('latin1')[:19]
			out += nm + b'\0' * (20 - len(nm)) + struct.pack('<BbBBhhh', it.kind, it.value, it.state, it.pad,
				it.loc, it.x, it.y)
		out += struct.pack('<800h', *self.serial)
		out += struct.pack('<8h', *self.alive)
		out += struct.pack('<h', (self.cur_army * 24) if self.cur_army is not None else 0)
		out += struct.pack('<h', self.aa60)
		out += struct.pack('<h', self.turn)
		out += struct.pack('<h', self.group_moves)
		out += struct.pack('<12h', *self.gcost)
		out += struct.pack('<h', self.group_count)
		for i, n in enumerate(self.hero_slot_names):
			raw = self.hero_slot_raw[i]
			if raw.split(b'\0')[0].decode('latin1') == n:
				out += raw
			else:
				b = n.encode('latin1')[:19]
				out += b + b'\0' * (20 - len(b))
		out += bytes(v & 0xff for v in self.hero_slot_used)
		out += struct.pack('<6h', self.view_y, self.view_x, self.view_y2, self.view_x2, self.cursor_x,
			self.cursor_y)
		out += struct.pack('<8h', *self.human)
		out += struct.pack('<hh', self.current, self.g7ea8)
		for r in self.hatred:
			out += struct.pack('<8h', *[max(-32768, min(32767, v)) for v in r])
		out += struct.pack('<8h', *self.war)
		out += struct.pack('<hhh', self.gem_seer, self.gem_oracle, self.surrender_offered)
		out += struct.pack('<8h', *self.level)
		out += struct.pack('<h', self.war_over)
		out += struct.pack('<8h', *self.observe)
		out += struct.pack('<8h', *self.enhance)
		out += bytes(v & 0xff for v in self.name_used)
		out += struct.pack('<hh', self.suffix, self.intense)
		with open(path, 'wb') as f:
			f.write(out)

	def load(self, path):
		with open(path, 'rb') as f:
			D = f.read()
		p = [0]

		def rd(n):
			b = D[p[0]:p[0] + n]
			p[0] += n
			return b

		def h(n=1):
			v = struct.unpack('<%dh' % n, rd(2 * n))
			return v[0] if n == 1 else list(v)

		self.reset()
		self.save_name = rd(16).split(b'\0')[0].decode('latin1')
		ver = h()
		if ver != SAVE_VERSION:
			raise ValueError("Error: Not Version 2 File")
		self.count = h()
		for i in range(self.count):
			self.armies[i].unpack(rd(24))
		self.map = list(struct.unpack('<%dH' % (MAP_W * MAP_H), rd(MAP_W * MAP_H * 2)))
		for c in self.cities:
			(c.defence, own, prod, c.elapsed, c.turns, c.port, c.income, c.vector, c.vx, c.vy, c.ai_target,
				c.island, c.ai_type, c.ai_strong, c.unused62, c.prev_owner) = struct.unpack('<bbbbbb10h', rd(26))
			c.owner = own & 0xff
			c.prod = prod
		for s in self.sites:
			r = rd(28)
			s.x, s.y = struct.unpack_from('<hh', r)
			s.name = r[4:24].split(b'\0')[0].decode('latin1')
			s.type, s.item, s.monster, s.pad = r[24], r[25], r[26], r[27]
		self.upkeep = h(8)
		self.income = h(8)
		self.ncities = h(8)
		for pl in self.players:
			pl.unpack(rd(20))
		for it in self.items:
			r = rd(30)
			it.name = r[:20].split(b'\0')[0].decode('latin1')
			it.kind, it.value, it.state, it.pad, it.loc, it.x, it.y = struct.unpack_from('<BbBBhhh', r, 20)
		self.serial = h(800)
		self.alive = h(8)
		ca = struct.unpack('<H', rd(2))[0]
		self.aa60 = h()
		self.turn = h()
		self.group_moves = h()
		self.gcost = h(12)
		self.group_count = h()
		self.hero_slot_raw = [rd(20) for _ in range(40)]
		self.hero_slot_names = [r.split(b'\0')[0].decode('latin1') for r in self.hero_slot_raw]
		self.hero_slot_used = list(rd(40))
		self.view_y, self.view_x, self.view_y2, self.view_x2, self.cursor_x, self.cursor_y = h(6)
		self.human = h(8)
		self.current, self.g7ea8 = h(2)
		self.hatred = [h(8) for _ in range(8)]
		self.war = h(8)
		self.gem_seer, self.gem_oracle, self.surrender_offered = h(3)
		self.level = h(8)
		self.war_over = h()
		self.observe = h(8)
		self.enhance = h(8)
		self.name_used = list(rd(100))
		self.suffix, self.intense = h(2)
		self.cur_army = None
		self.group = []
		self.group_mode = 0


def _sb(v):
	v &= 0xff
	return v - 256 if v > 127 else v
