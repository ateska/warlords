"""The Warlords rules engine.

Everything in here follows the reverse-engineered behaviour of WARLORDS.EXE
v2.10 (see the specs in the repository's `re/` notes). Function names of the
original are given in the doc strings (Ghidra SEG:OFF naming).
"""
from .gamedata import (DX, DY, CITY_DX, CITY_DY, MAP_W, MAP_H, NEUTRAL, IMPASSABLE,
	HERO, NAVY, PEGASI, GRIFFIN, DRAGON, WIZARD, DEVIL,
	ROAD, BRIDGE, WATER, SHORE, MOUNTAIN, PLAIN, TOWER, CITY, RUINS)
from .state import (GameState, F_ACTIVE, F_DONE, F_VISITED, M_ARMY, M_EXPLORED, TEMPLE_BITS)
from .pathfind import PathFinder
from .rng import dist
from .ui_base import UIBase

ORDINALS = {1: "st", 2: "nd", 3: "rd"}


def ordinal(n):
	if 10 <= n % 100 <= 20:
		return "%dth" % n
	return "%d%s" % (n, ORDINALS.get(n % 10, "th"))


class Battle:
	"""Everything about one battle, also used by the front-end to animate it."""

	def __init__(self):
		self.attackers = []       # sorted army objects
		self.defenders = []
		self.sa = []              # effective strengths
		self.sd = []
		self.hpa = []
		self.hpd = []
		self.alive_a = []
		self.alive_d = []
		self.tiles = []
		self.target = (0, 0)
		self.cls = 0
		self.def_clan = NEUTRAL
		self.attacker = 0
		self.city = None
		self.rounds = []          # (a_index, d_index, loser) loser 'a' or 'd'
		self.result = 0           # 1 = attacker won
		self.fled = False
		self.neutral = False
		self.captured = False
		self.pillage = 0


class Game:

	def __init__(self, data, ui=None, seed=None):
		self.data = data
		self.s = GameState(data, seed)
		self.ui = ui or UIBase()
		self.pf = PathFinder(self)
		self.ai = None
		self.quit = False

	# ==================================================================
	# small helpers
	# ==================================================================
	def clan_name(self, p):
		return self.data.clan_names[p if 0 <= p < 8 else 8]

	def army_name(self, a):
		"""FUN_2b32_0632: '<city> <Nth> <type>' or the hero's name."""
		if a.type == HERO:
			return self.s.hero_name(a)
		if a.serial == 0:
			return self.data.army_names[a.type]
		c = self.s.cities[a.home]
		return "%s %s %s" % (c.name, ordinal(a.serial), self.data.army_names[a.type])

	def cost_of(self, a):
		return self.data.move_cost[a.type]

	def region_name(self, x, y):
		return self.data.region_names[((2 * y) // MAP_H) * 4 + (4 * x) // MAP_W]

	# ==================================================================
	# new game
	# ==================================================================
	def new_game(self, human, level, intense=0):
		"""World initialisation (FUN_1b90_0006, FUN_16c7_000c, FUN_274c_0088, FUN_2de9_0004)."""
		s = self.s
		rng = s.rng
		s.reset()
		s.human = list(human)
		s.level = list(level)
		s.intense = intense
		if s.extra_tough:
			for p in range(8):
				if not s.human[p]:
					s.enhance[p] = 1
		s.surrender_offered = s.gem_seer = s.gem_oracle = 0
		s.turn = 1
		s.count = 10
		# capitals: owner bits of the 4 city tiles
		for p in range(8):
			cx, cy = s.players[p].cap_x, s.players[p].cap_y
			for k in range(4):
				s.set_towner(cx + CITY_DX[k], cy + CITY_DY[k], p)
		s.players[rng.dice(1, 8, -1) & 7].razer = 1
		self.init_hatred()
		self.init_sites()
		s.recount_cities()
		self.recompute_totals_all()

	def init_hatred(self):
		"""FUN_274c_0088."""
		s = self.s
		rng = s.rng
		for p in range(8):
			if not s.human[p]:
				for j in range(8):
					s.hatred[p][j] = -1000 if j == p else rng.dice(1, 3, -1)
				e = self.data.natural_enemy[0][p] if rng.dice(1, 2, 0) == 1 else self.data.natural_enemy[1][p]
				s.hatred[p][e] += rng.dice(1, 3, 1)
			s.war[p] = -1

	def init_sites(self):
		"""FUN_2de9_0004: put the 14 items in ruins, roll ruin contents and guardians."""
		s = self.s
		rng = s.rng
		used = [1] * 8 + [0] * 32
		for site in s.sites:
			i = site.y * MAP_W + site.x
			s.map[i] &= ~M_EXPLORED & 0xffff
		for i in range(14):
			while True:
				k = rng.dice(1, 32, 7)
				if k > 39:
					continue
				if used[k] == 0:
					break
			used[k] = 1
			it = s.items[i]
			it.state = 2
			it.loc = k
			s.sites[k].type = 4
			s.sites[k].item = i
		for k in range(8, 40):
			if used[k] == 0:
				t = rng.dice(1, 6, 4)
				s.sites[k].type = min(t, 8)
				s.sites[k].item = 0
				used[k] = 1
		for k in range(8):
			s.sites[k].monster = 0
		for k in range(8, 40):
			site = s.sites[k]
			if site.type == 8:
				site.monster = min(rng.dice(1, 5, 4), 9)
			else:
				site.monster = min(rng.dice(1, 9, 0), 9)
			if site.type == 8 and k in (9, 14, 24, 29) and site.monster in (5, 8):
				site.monster += 1

	# ==================================================================
	# economy
	# ==================================================================
	def recompute_totals(self, p):
		"""FUN_2e41_01de."""
		s = self.s
		up = 0
		for a in s.live_armies():
			if a.owner == p:
				up += a.upkeep
		s.upkeep[p] = up
		inc = 0
		for c in s.cities:
			if c.owner == p:
				inc += c.income
		s.income[p] = inc

	def recompute_totals_all(self):
		for p in range(8):
			self.recompute_totals(p)

	def income_upkeep(self, p):
		"""FUN_2e41_0186."""
		s = self.s
		self.recompute_totals(p)
		g = min(s.players[p].gold + s.income[p], 30000)
		g -= s.upkeep[p]
		if g < 0:
			g = 0
		s.players[p].gold = g
		if s.human[p] and g < 1:
			self.ui.message("Your treasuries are exhausted!")

	def build_time(self, c, t, p, enhance=True):
		tm = c.time[t]
		if enhance and self.s.enhance[p]:
			tm = (tm - 1) // 2 + 1
		return tm

	def start_production(self, c, t, vector_to=None, enhance=True, check_gold=True):
		"""Pay and start a production cycle (FUN_2f0e_02b2 / 2f0e_0002 / 2f0e_0f26)."""
		s = self.s
		p = c.owner
		if check_gold and s.players[p].gold < c.cost[t]:
			return False
		c.prod = t
		c.elapsed = 0
		c.turns = self.build_time(c, t, p, enhance)
		s.add_gold(p, -c.cost[t])
		if vector_to is None:
			c.vector = 0
		else:
			c.vector = 1
			c.vx, c.vy = vector_to.x, vector_to.y
		return True

	def stop_production(self, c):
		c.turns = 0
		c.vector = 0

	def vectors_into(self, target):
		return [c for c in self.s.cities if c.vector and c.vx == target.x and c.vy == target.y]

	def create_unit(self, c, x, y, dest):
		"""FUN_2f0e_1010."""
		s = self.s
		p = s.current
		t = c.prod
		a = s.alloc_army(p)
		if a is None:
			return None
		if dest == -1:
			if t == NAVY:
				a.x, a.y = x + self.data.port_dx[c.port], y + self.data.port_dy[c.port]
			else:
				a.x, a.y = x, y
		a.type = t
		a.owner = p
		a.maxmoves = a.moves = c.moves[t]
		a.strength = c.strength[t]
		a.home = c.index
		k = c.index * 10 + t
		a.serial = s.serial[k]
		s.serial[k] += 1
		a.hits = 1
		a.e = 0
		a.upkeep = c.cost[t] // 2
		s.upkeep[p] += a.upkeep
		c.turns = 0
		if dest == -1:
			a.goal = a.origin = -1
			s.set_towner(a.x, a.y, p)
			s.map[a.y * MAP_W + a.x] |= M_ARMY
		else:
			a.goal = dest
			a.origin = 100
		return a

	def production_tick(self, c, human):
		"""Countdown and creation for one city (FUN_2f0e_0ad8 human / FUN_277d_0010 AI).
		Returns (code, message): code 0 nothing, 1 produced, 2 failure message."""
		s = self.s
		p = s.current
		if c.owner != p or c.turns == 0:
			return 0, None
		if c.turns >= 2:
			c.turns -= 1
			c.elapsed += 1
			return 0, None
		dx, dy = c.x, c.y
		di = -1
		if c.vector:
			dx, dy = c.vx, c.vy
			dcity = None
			for k in s.cities:
				if k.x == dx and k.y == dy:
					dcity = k
					break
			di = dcity.index if dcity else -1
			if not human and (dcity is None or dcity.owner != p):
				c.turns = 0
				c.vector = 0
				return 0, None
		t = c.prod
		if t == NAVY:
			px, py = dx + self.data.port_dx[c.port], dy + self.data.port_dy[c.port]
			n = s.count_at(px, py)
			if s.towner(px, py) == p or n < 1:
				if n < 8:
					a = self.create_unit(c, dx, dy, -1)
					s.set_towner(px, py, p)
					return 1, "%s - Produced!" % self.army_name(a) if a else None
				else:
					c.turns = 0
					return 2, "%s: Port full. No room to produce." % c.name
			return 2, "%s: Port occupied by enemy! Cannot produce." % c.name
		if c.vector:
			a = self.create_unit(c, dx, dy, di)
			if a is None:
				return 0, None
			dname = s.cities[di].name if di >= 0 else "?"
			return 1, "%s -> %s" % (self.army_name(a), dname)
		for k in range(4):
			x, y = c.x + CITY_DX[k], c.y + CITY_DY[k]
			if s.count_at(x, y) < 8:
				a = self.create_unit(c, x, y, -1)
				if a is None:
					return 0, None
				return 1, "%s - Produced!" % self.army_name(a)
		return 2, "%s: City full. No room to produce." % c.name

	def transit_arrivals(self, p, human):
		"""FUN_277d_0286: vectored units travel for two turn starts."""
		s = self.s
		for a in list(s.live_armies()):
			if a.owner != p:
				continue
			if a.origin == 100:
				a.origin = 101
				continue
			if a.origin == 101:
				d = a.goal
				a.origin = a.goal = -1
				city = s.cities[d] if 0 <= d < 80 else None
				placed = False
				if city is not None and city.owner == p:
					for k in range(4):
						x, y = city.x + CITY_DX[k], city.y + CITY_DY[k]
						if s.count_at(x, y) < 8:
							a.x, a.y = x, y
							s.set_towner(x, y, p)
							s.map[y * MAP_W + x] |= M_ARMY
							placed = True
							break
				if placed:
					if human:
						self.ui.message("%s reaches %s" % (self.army_name(a), city.name))
				else:
					s.free_army(a)

	def production_phase_human(self, p):
		"""FUN_2f0e_091a / FUN_2f0e_095c: produce units, ask whether to keep producing."""
		s = self.s
		self.transit_arrivals(p, True)
		i = 0
		auto = False
		while i < 80:
			if i == 79 and not auto and self._report_raised_at_78:
				# quirk: city 79 is skipped when a dialog was raised for city 78
				break
			c = s.cities[i]
			code, msg = self.production_tick(c, True)
			i += 1
			if code == 1:
				self._report_raised_at_78 = (i - 1 == 78)
				if auto:
					if s.players[p].gold >= c.cost[c.prod] and c.turns == 0:
						keep_vec = c.vector
						self._restart(c, keep_vec)
					continue
				ans = self.ui.production_report(msg, c)
				if ans == 'yes':
					if s.players[p].gold < c.cost[c.prod]:
						self.ui.message("You do not have enough gold!")
					else:
						self._restart(c, c.vector)
				elif ans == 'end':
					if s.players[p].gold >= c.cost[c.prod]:
						self._restart(c, c.vector)
					auto = True
				else:
					c.vector = 0
			elif code == 2:
				if not auto:
					self.ui.message(msg)
				if "City full" in msg and self._last_report_city is not None:
					self._last_report_city.vector = 0
			if code == 1:
				self._last_report_city = c
		self._report_raised_at_78 = False

	_report_raised_at_78 = False
	_last_report_city = None

	def _restart(self, c, keep_vector):
		"""FUN_2f0e_0f26: pay again, keep the current vector."""
		s = self.s
		t = c.prod
		vec, vx, vy = c.vector, c.vx, c.vy
		c.elapsed = 0
		c.turns = self.build_time(c, t, c.owner)
		s.add_gold(c.owner, -c.cost[t])
		c.vector, c.vx, c.vy = (vec, vx, vy) if keep_vector else (0, vx, vy)

	# ==================================================================
	# capital, cities
	# ==================================================================
	def relocate_capital(self, p):
		"""FUN_2289_1075 (bug reproduced: picks the highest index city)."""
		s = self.s
		best = None
		for c in s.cities:
			if c.owner == p:
				best = c
		if best is not None:
			s.players[p].cap_x, s.players[p].cap_y = best.x, best.y

	def capital_city(self, p):
		pl = self.s.players[p]
		return self.s.city_at(pl.cap_x, pl.cap_y)

	def set_city_owner_tiles(self, c, owner):
		s = self.s
		for k in range(4):
			x, y = c.x + CITY_DX[k], c.y + CITY_DY[k]
			idx = 86 + 4 * (owner + 1) + k if owner < 8 else 86 + k
			s.set_tindex(x, y, idx)
			s.set_towner(x, y, owner)

	def cancel_vectors_to(self, target):
		for c in self.s.cities:
			if c.vector and c.vx == target.x and c.vy == target.y:
				c.prod = -1
				c.turns = 0
				c.vector = 0
				c.vx = c.vy = 0

	# ==================================================================
	# selection and group movement (UI-level state with rules effects)
	# ==================================================================
	def compute_group(self):
		"""FUN_1cdf_07b2."""
		s = self.s
		mem = [s.armies[i] for i in s.group]
		s.group_count = len(mem)
		gmp = 100
		all_heroes = True
		has_navy = False
		navy_min = 20
		for m in mem:
			gmp = min(gmp, m.moves)
			if m.type != HERO:
				all_heroes = False
			if m.type == NAVY:
				has_navy = True
				navy_min = min(navy_min, m.moves)
		mc = self.data.move_cost
		if has_navy:
			gmp = navy_min
			s.gcost = list(mc[NAVY])
		else:
			g = []
			for c in range(12):
				v = mc[HERO][c] if all_heroes else 0
				for m in mem:
					if m.type != HERO:
						v = max(v, mc[m.type][c])
				g.append(v)
			s.gcost = g
		s.group_moves = gmp

	def set_group_mode(self, g):
		"""FUN_1c8b_049c."""
		s = self.s
		s.group_mode = g if len(s.group) > 1 else 0
		for i in s.group:
			s.armies[i].flags |= F_ACTIVE
		s.cur_hero = None
		if s.group_mode:
			for i in reversed(s.group):
				if s.armies[i].type == HERO:
					s.cur_hero = i
		elif s.cur_army is not None and s.armies[s.cur_army].type == HERO:
			s.cur_hero = s.cur_army

	def select_stack(self, x, y, group=True):
		"""Select all own armies on a tile (FUN_2b32_036a)."""
		s = self.s
		p = s.current
		mem = [a for a in s.armies_at(x, y) if a.owner == p][:8]
		if not mem:
			return False
		if not group and s.cur_army is not None and s.armies[s.cur_army].x == x and s.armies[s.cur_army].y == y:
			# cycle the current army through the stack, single mode
			idx = [a.index for a in mem]
			k = idx.index(s.cur_army) if s.cur_army in idx else -1
			s.cur_army = idx[(k + 1) % len(idx)]
			s.group = [s.cur_army]
			self.compute_group()
			self.set_group_mode(0)
			return True
		best = None
		for a in mem:
			if best is None or self.data.prio[a.type] > self.data.prio[best.type]:
				best = a
		s.group = [a.index for a in mem]
		s.cur_army = best.index
		self.compute_group()
		self.set_group_mode(1 if group else 0)
		if not group:
			s.group = [best.index]
			self.compute_group()
			self.set_group_mode(0)
		s.last_pos = (x, y)
		return True

	def select_subset(self, indices):
		"""Stack dialog (FUN_2b32_0f76)."""
		s = self.s
		if not indices:
			return
		s.group = list(indices)[:8]
		if s.cur_army not in s.group:
			best = None
			for i in s.group:
				a = s.armies[i]
				if best is None or self.data.prio[a.type] > self.data.prio[best.type]:
					best = a
			s.cur_army = best.index
		self.compute_group()
		self.set_group_mode(1 if len(s.group) > 1 else 0)

	def deselect(self):
		"""FUN_2b32_0918."""
		s = self.s
		s.cur_army = None
		s.group = []
		s.group_mode = 0
		s.cur_hero = None

	def mark_done(self):
		"""FUN_1c8b_043a."""
		s = self.s
		if s.group_mode:
			for i in s.group:
				s.armies[i].flags |= F_DONE
		elif s.cur_army is not None:
			s.armies[s.cur_army].flags |= F_DONE

	def selected(self):
		s = self.s
		if s.cur_army is None:
			return []
		if s.group_mode:
			return [s.armies[i] for i in s.group]
		return [s.armies[s.cur_army]]

	def next_army(self):
		"""'Next' button (FUN_1c8b_0076 / 013e / 02c0)."""
		s = self.s
		p = s.current
		lx, ly = s.last_pos
		if s.cur_army is not None:
			a = s.armies[s.cur_army]
			lx, ly = a.x, a.y
		cands = [a for a in s.live_armies() if a.owner == p and a.x != -1 and (a.flags & F_ACTIVE)
			and not (a.flags & F_DONE)]
		if not cands:
			self.deselect()
			return None
		fresh = [a for a in cands if not (a.flags & F_VISITED)]
		if not fresh:
			for a in cands:
				a.flags &= ~F_VISITED
			fresh = cands
		best = None
		bd = None
		for a in fresh:
			d = abs(a.x - lx) + abs(a.y - ly)
			if d == 0:
				d = 9000
			if bd is None or d < bd:
				best, bd = a, d
		self.select_stack(best.x, best.y, True)
		for i in s.group:
			s.armies[i].flags |= F_VISITED
		s.last_pos = (best.x, best.y)
		return best

	def skip(self):
		"""Skip the selected army for this turn (1c8b:00c8)."""
		self.mark_done()
		self.deselect()

	def sentry(self):
		"""'Def' button: clear the active flag (1c8b:00d6)."""
		for a in self.selected():
			a.flags &= ~F_ACTIVE
		self.deselect()

	# ==================================================================
	# movement
	# ==================================================================
	def capture_towers(self, x, y):
		"""FUN_1cdf_06c2: towers next to (or under) a moving army change hands."""
		s = self.s
		p = s.current
		for dy in (-1, 0, 1):
			for dx in (-1, 0, 1):
				nx, ny = x + dx, y + dy
				if not s.on_map(nx, ny):
					continue
				w = s.tile(nx, ny)
				if s.data.terrain_class[w & 0x7f] == TOWER and (not (w & M_ARMY) or ((w >> 7) & 0xf) == p):
					s.set_tindex(nx, ny, 2 + p)

	def step(self, d):
		"""FUN_1cdf_02d2: move the selection one tile. Returns True if it moved."""
		s = self.s
		if s.cur_army is None:
			return False
		cur = s.armies[s.cur_army]
		p = s.current
		ox, oy = cur.x, cur.y
		nx, ny = ox + DX[d], oy + DY[d]
		if not s.on_map(nx, ny):
			return False
		w = s.tile(nx, ny)
		cls = s.data.terrain_class[w & 0x7f]
		cost = s.gcost[cls] if s.group_mode else self.data.move_cost[cur.type][cls]
		if w & M_ARMY:
			if ((w >> 7) & 0xf) != p:
				return False
			n = s.count_at(nx, ny)
			if s.group_mode and n + s.group_count > 8:
				return False
			if not s.group_mode and n + 1 > 8:
				return False
		if cls in (BRIDGE, WATER, SHORE) and (w & M_ARMY) and any(a.owner == p for a in s.armies_at(nx, ny)):
			cost = 2
		mp = s.group_moves if s.group_mode else cur.moves
		if mp < cost:
			self.mark_done()
			self.deselect()
			return False
		if cls == CITY and ((w >> 7) & 0xf) != p:
			return False
		s.set_towner(nx, ny, p)
		self.capture_towers(nx, ny)
		movers = self.selected()
		if not s.group_mode:
			cur.moves = max(cur.moves - cost, 0)
			cur.x, cur.y = nx, ny
		else:
			s.group_moves = max(s.group_moves - cost, 0)
			for m in movers:
				m.moves = max(m.moves - cost, 0)
				m.x, m.y = nx, ny
		s.map[ny * MAP_W + nx] |= M_ARMY
		if s.count_at(ox, oy) == 0:
			s.map[oy * MAP_W + ox] &= ~M_ARMY & 0xffff
		self.ui.army_moved(self, movers, ox, oy, nx, ny)
		left = s.group_moves if s.group_mode else cur.moves
		if left < 1:
			self.mark_done()
			self.deselect()
		return True

	def move_to(self, tx, ty):
		"""FUN_1cdf_0000: walk the selection toward a clicked tile."""
		s = self.s
		if s.cur_army is None or not s.on_map(tx, ty):
			return 0
		cur = s.armies[s.cur_army]
		p = s.current
		w = s.tile(tx, ty)
		cls = s.data.terrain_class[w & 0x7f]
		board = cls in (WATER, BRIDGE, SHORE) and (w & M_ARMY) and any(
			a.type == NAVY and a.owner == p for a in s.armies_at(tx, ty))
		table = s.gcost if s.group_mode else self.data.move_cost[cur.type]
		if not board:
			if table[cls] == IMPASSABLE:
				return -1
		path = self.pf.find(cur.x, cur.y, tx, ty, table, p, board=board)
		n = 0
		for i, d in enumerate(path):
			if i == 50:
				break
			if not self.step(d):
				break
			n += 1
		return n

	# ==================================================================
	# combat
	# ==================================================================
	def attack_target_ok(self, tx, ty):
		"""Would clicking (tx,ty) be an attack? (cursor shape logic, FUN_31e1_0042)."""
		s = self.s
		if s.cur_army is None or not s.on_map(tx, ty):
			return False
		p = s.current
		w = s.tile(tx, ty)
		cls = s.data.terrain_class[w & 0x7f]
		own = (w >> 7) & 0xf
		if (w & M_ARMY) and own != p:
			return True
		if cls == CITY and own != p:
			return True
		return False

	def attack(self, tx, ty, d=None):
		"""FUN_2289_0004: human attack toward a clicked tile. Returns a Battle or None."""
		s = self.s
		if s.cur_army is None:
			return None
		cur = s.armies[s.cur_army]
		p = s.current
		if max(abs(tx - cur.x), abs(ty - cur.y)) > 1:
			if d is None:
				from .pathfind import dirto
				d = dirto(cur.x, cur.y, tx, ty)
			tx, ty = cur.x + DX[d], cur.y + DY[d]
		if not s.on_map(tx, ty):
			return None
		w = s.tile(tx, ty)
		cls = s.data.terrain_class[w & 0x7f]
		if s.group_mode:
			if s.group_moves < 2:
				return None
			cost = s.gcost[cls]
		else:
			if cur.moves < 2:
				return None
			cost = self.data.move_cost[cur.type][cls]
		if cost == IMPASSABLE:
			return None
		own = (w >> 7) & 0xf
		if cls == CITY and own == NEUTRAL:
			return self.neutral_assault(tx, ty, human=True)
		if ((w & M_ARMY) and own != p) or (cls == CITY and own != p and not (w & M_ARMY)):
			self.attack_move(tx, ty)
			b = self.battle_setup(tx, ty)
			self.battle_resolve(b)
			self.ui.battle(self, b)
			s.rebuild_army_flags()
			if b.result == 1:
				if b.fled:
					self.ui.message("The garrison has fled before you!")
				elif s.cur_hero is not None:
					self.ui.message("%s has won the battle!" % s.hero_name(s.armies[s.cur_hero]))
				else:
					self.ui.message("You are victorious!")
			else:
				self.ui.message("You have been defeated!")
			r = self.battle_aftermath(b)
			if b.result == 1:
				s.map[ty * MAP_W + tx] |= M_ARMY
			if r == 0x21 and s.human[p]:
				self.ui.city_production(self, b.city, captured=True)
			return b
		return None

	def attack_move(self, tx, ty):
		"""FUN_2289_0466: attackers step onto the target, -2 MP."""
		s = self.s
		cur = s.armies[s.cur_army]
		if s.group_mode:
			s.group_moves -= 2
			for m in self.selected():
				m.x, m.y = tx, ty
				m.moves -= 2
		else:
			cur.x, cur.y = tx, ty
			cur.moves -= 2

	def bat_bonus(self, h):
		return sum(it.value for it in self.s.items_of(h) if it.kind == 1)

	def cmd_items(self, h):
		return sum(it.value for it in self.s.items_of(h) if it.kind == 2)

	def _sort_side(self, units, water):
		keys = []
		fly_marked = False
		for u in units:
			k = u.type
			if u.type == NAVY:
				k = 127
			elif water and not fly_marked and self.data.flyer_class[u.type] == 5:
				k = u.type + 100
				fly_marked = True
			keys.append(k)
		order = sorted(range(len(units)), key=lambda i: keys[i])   # stable
		return [units[i] for i in order]

	def _side_bonus(self, units, clan, defender, cls, city):
		d = self.data
		best = 0
		fly = special = cmd = 0
		for u in units:
			if u.type == HERO:
				v = u.strength + self.bat_bonus(u)
				if v > best:
					best = min(v, 9)
				cmd += self.cmd_items(u)
			if u.type in (PEGASI, GRIFFIN, DRAGON):
				fly = 1
			if WIZARD <= u.type <= DEVIL:
				special = 1
		ct = d.clan_terrain[clan & 0xf]
		b = ct[cls] + d.hero_cmd[best] + fly + special + cmd
		if defender:
			if cls == TOWER:
				b += 2
			elif cls == RUINS:
				b += 1
			elif cls == CITY and city is not None:
				b += d.city_def_bonus[max(0, min(10, city.defence))]
		return b

	def battle_setup(self, tx, ty, attackers=None):
		"""FUN_23cd_000c: build, sort and evaluate both sides."""
		s = self.s
		d = self.data
		b = Battle()
		p = s.current
		b.attacker = p
		b.target = (tx, ty)
		w = s.tile(tx, ty)
		b.def_clan = (w >> 7) & 0xf
		if d.terrain_class[w & 0x7f] == CITY:
			city = None
			for c in s.cities:
				if c.x in (tx, tx - 1) and c.y in (ty, ty - 1):
					city = c
					break
			b.city = city
			b.tiles = [(city.x + CITY_DX[k], city.y + CITY_DY[k]) for k in range(4)] if city else [(tx, ty)]
		else:
			b.tiles = [(tx, ty)]
		b.cls = s.tclass(*b.tiles[0])
		water = s.tclass(tx, ty) in (WATER, SHORE, MOUNTAIN)
		A = attackers if attackers is not None else self.selected()
		D = []
		for k in range(len(b.tiles) - 1, -1, -1):
			x, y = b.tiles[k]
			for j in range(s.count - 1, -1, -1):
				a = s.armies[j]
				if a.x == x and a.y == y and a.owner != 0xff and a.owner != p:
					D.append(a)
		D = D[:32]
		b.attackers = self._sort_side(list(A), water)
		b.defenders = self._sort_side(D, water)
		ba = self._side_bonus(b.attackers, p, False, b.cls, b.city)
		bd = self._side_bonus(b.defenders, b.def_clan, True, b.cls, b.city)
		for units, bonus, out in ((b.attackers, ba, b.sa), (b.defenders, bd, b.sd)):
			for u in units:
				v = d.type_terrain[u.type][b.cls] + u.strength + bonus
				if u.type == HERO:
					v += self.bat_bonus(u)
				out.append(min(v, 9))
		b.hpa = [u.hits for u in b.attackers]
		b.hpd = [u.hits for u in b.defenders]
		b.alive_a = [1] * len(b.attackers)
		b.alive_d = [1] * len(b.defenders)
		return b

	def battle_resolve(self, b):
		"""FUN_2289_067a: the battle dice loop."""
		s = self.s
		rng = s.rng
		nA, nD = len(b.attackers), len(b.defenders)
		if nA == 0 or nD == 0:
			b.fled = True
			b.result = 1
			return 1
		a = dd = 0
		N = 12 if s.intense else 10
		while True:
			r1 = rng.dice(1, N, 0)
			r2 = rng.dice(1, N, 0)
			sd, sa = b.sd[dd], b.sa[a]
			if sd < 1 and sa < 1:
				# The original loops forever when both strengths are <= 0.
				# Deliberate fix: treat both sides as strength 1.
				sd = sa = 1
			def_hit = r1 <= sd
			att_hit = r2 <= sa
			if def_hit == att_hit:
				continue
			if def_hit:
				b.hpa[a] -= 1
				b.attackers[a].hits -= 1
				b.rounds.append((a, dd, 'a'))
				if b.hpa[a] < 0:
					b.alive_a[a] = 0
					a += 1
			else:
				b.hpd[dd] -= 1
				b.defenders[dd].hits -= 1
				b.rounds.append((a, dd, 'd'))
				if b.hpd[dd] < 0:
					b.alive_d[dd] = 0
					dd += 1
			if dd == nD:
				b.result = 1
				return 1
			if a == nA:
				b.result = 0
				return 0

	def hero_death(self, h, x, y):
		"""FUN_2289_139e."""
		s = self.s
		if 0 <= h.serial < 40:
			s.hero_slot_used[h.serial] = 0
		for it in s.items_of(h):
			it.state = 1
			it.loc = 0
			it.x, it.y = x, y

	def battle_aftermath(self, b):
		"""FUN_2289_09c0. Returns 0x21 when a city was captured."""
		s = self.s
		p = b.attacker
		tx, ty = b.target
		survivors = [u for i, u in enumerate(b.attackers) if b.alive_a[i]]
		for i, u in enumerate(b.attackers):
			if not b.alive_a[i]:
				if u.type == HERO:
					self.hero_death(u, tx, ty)
				s.free_army(u)
		for i, u in enumerate(b.defenders):
			if not b.alive_d[i]:
				if u.type == HERO:
					self.hero_death(u, tx, ty)
				s.free_army(u)
		if survivors and s.human[p]:
			s.group = [u.index for u in survivors]
			s.cur_army = survivors[0].index
			self.compute_group()
			self.set_group_mode(1 if len(survivors) > 1 else 0)
		elif not survivors:
			if s.cur_army is not None and s.armies[s.cur_army].owner == 0xff:
				self.deselect()
		t0 = b.tiles[0]
		if b.result == 0:
			s.set_towner(t0[0], t0[1], b.def_clan)
			return 1
		s.set_towner(t0[0], t0[1], p)
		if b.cls == TOWER:
			s.set_tindex(tx, ty, p + 2)
		if b.cls == CITY and b.city is not None:
			self.capture_city(b.city, p, b)
			return 0x21
		return 1

	def capture_city(self, c, p, b=None):
		"""City conquest part of FUN_2289_09c0."""
		s = self.s
		L = c.owner
		if 0 <= L < 8:
			if not s.human[L]:
				s.hatred[L][p] += 2
			g = s.players[L].gold
			n = s.ncities[L]
			pv = g if n < 2 else int(g / n)
			pv = int(pv / 2)
			if pv < 0:
				pv = 0
			if s.human[p] and pv > 0:
				self.ui.message("Your armies pillage %d gp!" % pv)
			s.add_gold(p, pv)
			s.add_gold(L, -2 * pv)
			if b is not None:
				b.pillage = pv
		c.prev_owner = NEUTRAL if c.prev_owner == p else L
		c.owner = p
		c.turns = 0
		if c.defence > 0:
			c.defence -= 1
		for k in range(4):
			x, y = c.x + CITY_DX[k], c.y + CITY_DY[k]
			s.map[y * MAP_W + x] &= ~M_ARMY & 0xffff
		self.set_city_owner_tiles(c, p)
		s.income[p] += c.income
		s.ncities[p] += 1
		if 0 <= L < 8:
			s.ncities[L] -= 1
			s.income[L] -= c.income
			pl = s.players[L]
			if (pl.cap_x, pl.cap_y) == (c.x, c.y):
				self.relocate_capital(L)
		if c.vector:
			c.vector = 0
			c.ai_target = -1
		self.cancel_vectors_to(c)
		s.rebuild_army_flags()
		if b is not None:
			b.captured = True

	def neutral_assault(self, tx, ty, human=True, attackers=None):
		"""FUN_2491_000a / FUN_2491_0341: one roll against the city defence."""
		s = self.s
		p = s.current
		if attackers is None:
			self.attack_move(tx, ty)
		b = self.battle_setup(tx, ty, attackers)
		b.neutral = True
		score = sum(sv * (i + 1) for i, sv in enumerate(b.sa))
		r = s.rng.dice(1, 100, 0)
		city = b.city
		if r > 110 - (10 * city.defence - score):
			b.result = 0
			b.alive_a = [0] * len(b.attackers)
			if human:
				self.ui.battle(self, b)
			for u in b.attackers:
				if u.type == HERO:
					self.hero_death(u, tx, ty)
				s.free_army(u)
			if s.cur_army is not None and s.armies[s.cur_army].owner == 0xff:
				self.deselect()
			s.rebuild_army_flags()
			if human:
				self.ui.message("You have been defeated!")
			return b
		b.result = 1
		b.captured = True
		if human:
			self.ui.battle(self, b)
		city.owner = p
		s.income[p] += city.income
		s.ncities[p] += 1
		self.set_city_owner_tiles(city, p)
		s.map[ty * MAP_W + tx] |= M_ARMY
		s.rebuild_army_flags()
		if human:
			self.ui.message("You are victorious!")
			if s.human[p]:
				self.ui.city_production(self, city, captured=True)
		return b

	# ==================================================================
	# city orders: build, raze, disband
	# ==================================================================
	def build(self):
		"""FUN_2c41_0002 / 0144: tower on plains, or improve city defences."""
		s = self.s
		if s.cur_army is None:
			return
		p = s.current
		a = s.armies[s.cur_army]
		cls = s.tclass(a.x, a.y)
		if cls == CITY:
			c = s.city_at(a.x, a.y)
			if c is None or c.owner != p:
				return
			if c.defence > 9:
				self.ui.message("Your defences are already legendary!")
				return
			cost = self.data.def_cost[c.defence + 1]
			ans = self.ui.ask(["Improve City Defences?", "Current Defences: %d" % c.defence,
				"Improvement cost %d gp" % cost, "You have %d gp" % s.players[p].gold], [" Yes ", " No "])
			if ans != 0:
				return
			if s.players[p].gold < cost:
				self.ui.message("You do not have sufficient gold!")
				return
			c.defence += 1
			s.add_gold(p, -cost)
			self.ui.message("You have improved your defences!")
		elif cls == PLAIN:
			cost = 100
			ans = self.ui.ask(["Build a Tower?", "Cost: %d" % cost, "You have %d gp" % s.players[p].gold],
				[" Yes ", " No "])
			if ans != 0:
				return
			if s.players[p].gold < cost:
				self.ui.message("You do not have sufficient gold!")
				return
			s.set_tindex(a.x, a.y, p + 2)
			s.add_gold(p, -cost)
			self.ui.message("You have built a tower!")
		else:
			self.ui.message("Towers must be built on plains!")

	def raze(self):
		"""FUN_3043_0000 / 009a / 01d8."""
		s = self.s
		if s.cur_army is None:
			return
		p = s.current
		a = s.armies[s.cur_army]
		cls = s.tclass(a.x, a.y)
		if cls not in (CITY, TOWER) or s.towner(a.x, a.y) != p:
			self.ui.message("You can only raze cities and towers")
			return
		if cls == CITY:
			c = s.city_at(a.x, a.y)
			if c is None or c.owner != p:
				self.ui.message("You can only raze cities and towers")
				return
		if self.ui.ask(["Raze this %s?" % ("city" if cls == CITY else "tower")], [" Raze it! ", " Cancel "]) != 0:
			return
		if cls == TOWER:
			s.set_tindex(a.x, a.y, 12)
			self.ui.message("The tower is destroyed!")
			return
		self.raze_city(c, p, show=True)

	def raze_city(self, c, p, show=False):
		s = self.s
		s.income[p] -= c.income
		s.ncities[p] -= 1
		c.owner = NEUTRAL
		c.prev_owner = NEUTRAL
		for k in range(4):
			s.set_tindex(c.x + CITY_DX[k], c.y + CITY_DY[k], 12)
		if c.vector:
			c.vector = 0
			c.ai_target = -1
		self.cancel_vectors_to(c)
		pl = s.players[p]
		if (pl.cap_x, pl.cap_y) == (c.x, c.y):
			self.relocate_capital(p)
		for i in range(8):
			s.hatred[i][p] += 1
		if show:
			self.ui.picture('raze', ["Your troops ravage %s!" % c.name])
			self.ui.message("%s is in ruins!" % c.name)

	def disband(self):
		"""FUN_2b32_0812 / 08a8."""
		s = self.s
		sel = self.selected()
		if not sel:
			return
		non_heroes = [a for a in sel if a.type != HERO]
		if not non_heroes:
			self.ui.message("You cannot disband heroes!")
			return
		q = "Disband these armies?" if len(sel) > 1 else "Disband this army?"
		if self.ui.ask([q], [" Yes ", " No "]) != 0:
			return
		for a in non_heroes:
			s.free_army(a)
		heroes = [a for a in sel if a.type == HERO]
		if heroes:
			s.group = [h.index for h in heroes]
			s.cur_army = heroes[0].index
			self.compute_group()
			self.set_group_mode(1 if len(heroes) > 1 else 0)
		else:
			self.deselect()
		s.rebuild_army_flags()

	# ==================================================================
	# heroes
	# ==================================================================
	def random_hero_name(self):
		"""FUN_1888_0fe2 (the 'used' flags are never set, names may repeat)."""
		s = self.s
		i = s.rng.dice(1, 63, -1)
		i = max(0, min(62, i))
		return self.data.hero_names[i] + self.data.hero_suffixes[s.suffix]

	def hero_event(self, p):
		"""FUN_2cad_0006: hero emergence (turn 1) or offer. Returns 1 if an event happened."""
		s = self.s
		rng = s.rng
		if s.surrender_offered:
			return 0
		n = s.ncities[p]
		maxh = 5 if n < 40 else (n - 30) // 10 + 5
		total = own = 0
		for a in s.live_armies():
			if a.type == HERO:
				total += 1
				if a.owner == p:
					own += 1
		had = own > 0
		if total == 40 or own >= maxh:
			return 0
		if s.turn == 1:
			price = 0
		elif had:
			price = rng.dice(1, 600, 600)
		else:
			price = rng.dice(1, 400, 300)
		if s.players[p].gold < price:
			return 0
		r = rng.dice(1, 30, 0)
		if r > 6 and s.turn != 1:
			return 0
		k = rng.dice(1, n, 0) if n > 0 else 0
		city = None
		if s.level[p] == 3 and not s.human[p] and n > 30:
			best = 0
			for c in reversed(s.cities):
				if c.owner == p and c.ai_target != -1 and self.data.flyer_class[max(0, c.ai_type) & 15] != 5:
					dd = rng.dice(1, 6, 0)
					if dd > best:
						best = dd
						city = c
		if city is None:
			j = 0
			for c in s.cities:
				if c.owner == p:
					j += 1
					if j == k:
						city = c
						break
			if city is None:
				for c in s.cities:
					if c.owner == p:
						city = c
						break
		if city is None:
			return 0
		if s.human[p]:
			if s.turn == 1:
				self.ui.message("In %s, a hero emerges!" % city.name)
				name = self.ui.name_hero(self.random_hero_name())
				self.create_hero(p, city, name, 0, had)
			else:
				if self.ui.hero_offer(city.name, price, s.players[p].gold):
					name = self.ui.name_hero(self.random_hero_name())
					self.create_hero(p, city, name, price, had)
		else:
			if s.turn == 1 or price + 300 < s.players[p].gold:
				h = self.create_hero(p, city, self.random_hero_name(), price, had)
				if h is not None and self.ai is not None:
					self.ai.new_hero(h)
		return 1

	def create_hero(self, p, city, name, price, had):
		"""FUN_2cad_0438 (+ FUN_2cad_030e payment and allies)."""
		s = self.s
		rng = s.rng
		slot = None
		for i in range(40):
			if not s.hero_slot_used[i]:
				slot = i
				break
		if slot is None:
			return None
		if name.strip().upper() == "SUPERVISOR":
			s.supervisor = 1
			self.ui.message("Supervisor Mode is on!")
		order = range(4) if (s.human[p] or s.turn == 1) else range(3, -1, -1)
		pos = None
		for k in order:
			x, y = city.x + CITY_DX[k], city.y + CITY_DY[k]
			if s.count_at(x, y) < 8:
				pos = (x, y)
				break
		if pos is None:
			return None
		a = s.alloc_army(p)
		if a is None:
			return None
		s.hero_slot_used[slot] = 1
		s.hero_slot_names[slot] = name[:19]
		a.x, a.y = pos
		a.type = HERO
		a.maxmoves = a.moves = 12 if s.turn == 1 else 16
		a.strength = 5
		a.home = city.index
		a.serial = slot
		a.hits = 1
		a.upkeep = 0
		s.set_towner(pos[0], pos[1], p)
		s.map[pos[1] * MAP_W + pos[0]] |= M_ARMY
		if s.turn > 1:
			s.add_gold(p, -price)
			s.heroes_hired[p] += 1
			if had and rng.dice(1, 100, 0) < 75:
				t = rng.dice(1, 5, -1)
				cnt = self.data.ally_count[min(6, rng.dice(1, 7, -1))]
				if t <= 4:
					if s.human[p]:
						self.ui.message("And the hero brings %d allies!" % cnt)
					for _ in range(cnt):
						self.place_ally(t, a.x, a.y)
		return a

	def place_ally(self, t, x0, y0):
		"""FUN_307e_1320."""
		s = self.s
		rng = s.rng
		p = s.current
		cx, cy = x0, y0
		tries = 10
		while True:
			if s.on_map(cx, cy):
				cnt = s.count_at(cx, cy)
				if (cx, cy) == (x0, y0):
					cnt += 1
				if cnt < 8 and (s.towner(cx, cy) == p or cnt == 0):
					break
			cx += rng.dice(1, 3, -2)
			cy += rng.dice(1, 3, -2)
			tries -= 1
			if tries == 0:
				return None
		a = s.alloc_army(p)
		if a is None:
			return None
		tm = self.data.ally_templates[t]
		a.x, a.y = cx, cy
		a.type = tm['type']
		a.maxmoves, a.moves, a.strength = tm['maxmoves'], tm['moves'], tm['strength']
		a.home = 0
		a.serial = 0
		a.hits = 1
		a.e = 0
		a.upkeep = tm['upkeep']
		s.upkeep[p] += a.upkeep
		s.set_towner(cx, cy, p)
		s.map[cy * MAP_W + cx] |= M_ARMY
		return a

	# ==================================================================
	# exploration
	# ==================================================================
	def mp_deduct(self, who, n):
		"""FUN_307e_153b: who 1 = hero, 0 = stack."""
		s = self.s
		if who == 1:
			if s.cur_hero is None:
				return
			h = s.armies[s.cur_hero]
			h.moves = max(0, h.moves - n)
			if s.group_mode:
				s.group_moves = min(s.group_moves, h.moves)
		else:
			if not s.group_mode:
				if s.cur_army is not None:
					a = s.armies[s.cur_army]
					a.moves = max(0, a.moves - n)
			else:
				s.group_moves = max(0, s.group_moves - n)
				for m in self.selected():
					m.moves = max(0, m.moves - n)

	def _list_ground(self, x, y):
		its = s_items = self.s.items_on_ground(x, y)
		if not its:
			self.ui.message("You have found nothing!")
		for it in s_items:
			self.ui.message("You have found: %s" % it.name)

	def search(self):
		"""FUN_307e_000c."""
		s = self.s
		if s.cur_army is None:
			return 0
		A = s.armies[s.cur_army]
		if A.moves < 1:
			return 0
		x, y = A.x, A.y
		cls = s.tclass(x, y)
		site = None
		if cls == RUINS:
			site = s.site_at(x, y)
			if site is None:
				cls = PLAIN
		H = s.armies[s.cur_hero] if s.cur_hero is not None else None
		explored = s.tile(x, y) & M_EXPLORED
		if H is None or explored:
			if cls == RUINS and site.type == 3:
				self.temple(site.index)
			else:
				self._list_ground(x, y)
				self.mp_deduct(0, 4)
			return 1
		if cls != RUINS:
			self._list_ground(x, y)
			self.mp_deduct(1, 4)
			return 1
		if site.type == 1:
			self.library()
		elif site.type == 2:
			self.sage(site.index)
		elif site.type == 3:
			self.temple(site.index)
		else:
			self.search_ruin(site, x, y)
		return 1

	def ruin_fight_lost(self, site, H):
		"""FUN_307e_07d6."""
		s = self.s
		n = s.count_at(H.x, H.y)
		roll = s.rng.dice(1, 100, 0)
		T = (H.strength - self.data.monster_strength[site.monster] + self.bat_bonus(H)) * 5 + n * 3 + 90
		return roll > T

	def search_ruin(self, site, x, y):
		"""FUN_307e_038b."""
		s = self.s
		d = self.data
		H = s.armies[s.cur_hero]
		p = s.current
		self.mp_deduct(1, 20)
		hname = s.hero_name(H)
		self.ui.play_sound('dramatic')
		if site.type != 8:
			if site.monster == 0:
				self.ui.message("It appears to be uninhabited!")
			else:
				self.ui.message("%s encounters a %s!" % (hname, d.monster_names[site.monster]))
				if self.ruin_fight_lost(site, H):
					self.hero_death(H, H.x, H.y)
					s.free_army(H)
					s.cur_hero = None
					s.rebuild_army_flags()
					self.ui.message("...and is slain by it!")
					return 1
				self.ui.message("...and is victorious!")
				site.monster = 0
		i = y * MAP_W + x
		if site.type == 4:
			it = s.items[site.item]
			self.ui.message("%s has found the %s!" % (hname, it.name))
			s.map[i] |= M_EXPLORED
			site.type = 0
			it.state = 1
			it.loc = 0
			it.x, it.y = H.x, H.y
		elif site.type == 5:
			if self.ui.ask(["You have found a Holy Altar", "Will you pray at this Altar?"], [" Yes ", " No "]) == 0:
				self.altar(H)
		elif site.type == 6:
			if self.ui.ask(["You have found a huge", "Golden Throne", "Will you sit in the throne?"],
					[" Yes ", " No "]) == 0:
				self.throne(H)
		elif site.type == 7:
			g = s.rng.dice(3, 1000, 500)
			self.ui.message("%s has found %d gp!" % (hname, g))
			s.map[i] |= M_EXPLORED
			s.add_gold(p, g)
		elif site.type == 8:
			s.map[i] |= M_EXPLORED
			r = s.rng.dice(1, 3, 0)
			n = 2 if r == 3 else 1
			mname = d.monster_names[site.monster]
			if n == 1:
				self.ui.message("A %s offers to join %s" % (mname, hname))
			else:
				self.ui.message("%d %ss offer to join %s" % (n, mname, hname))
			for _ in range(n):
				if 5 <= site.monster <= 9:
					self.place_ally(site.monster - 5, x, y)
		return 1

	def altar(self, H):
		"""FUN_307e_0911."""
		s = self.s
		r = s.rng.dice(1, 2, -1)
		if r == 1 and H.strength < 9:
			H.strength += 1
			self.ui.message("The Gods hear! %s's strength increases to %d!" % (s.hero_name(H), H.strength))
		else:
			self.ui.message("The Gods ignore %s!" % s.hero_name(H))
		s.map[H.y * MAP_W + H.x] |= M_EXPLORED

	def throne(self, H):
		"""FUN_307e_09d4."""
		s = self.s
		roll = s.rng.dice(1, 100, 0)
		d = 1 if roll < 80 else -1
		if (H.strength == 9 and d == 1) or (H.strength == 0 and d == -1):
			self.ui.message("You see a vision of yourself as Warlord of all Illuria!")
		else:
			H.strength += d
			self.ui.message("%s's strength %s to %d!" % (s.hero_name(H), "increases" if d == 1 else "decreases",
				H.strength))
		s.map[H.y * MAP_W + H.x] |= M_EXPLORED

	def temple(self, idx):
		"""FUN_307e_0ad5."""
		s = self.s
		self.ui.message("You have found a temple...")
		bit = TEMPLE_BITS.get(idx)
		count = 0
		for a in self.selected():
			if bit and not (a.flags & bit):
				a.strength += 1
				a.flags |= bit
				count += 1
			if a.strength > 9:
				a.strength = 9
		if count == 0:
			self.ui.message("You have already received our blessing! Try another temple!")
		elif count == 1:
			self.ui.message("You have been blessed!  Seek more blessings in far temples!")
		else:
			self.ui.message("%d Armies have been blessed!  Seek more blessings in far temples!" % count)

	def sage(self, idx):
		"""Sage / Seer: gem (once per sage per game) then a question."""
		s = self.s
		p = s.current
		if (idx == 1 and not s.gem_seer) or (idx == 7 and not s.gem_oracle):
			if idx == 1:
				s.gem_seer = 1
			else:
				s.gem_oracle = 1
			g = s.rng.dice(3, 1000, 500)
			self.ui.message("You are greeted warmly...")
			self.ui.message("... the Seer gives you a gem...")
			self.ui.message("...worth %d gp" % g)
			s.add_gold(p, g)
		ans = self.ui.ask(["A sign says", "The Great Sage", "Master of Wisdom,", "Information on:",
			"Magical Items", "and Locations", "The sage welcomes you", "What do you wish to know?"],
			["Cancel", "Items", "Locations"], 0)
		if ans == 1:
			i = self.ui.choose("Items", [it.name for it in s.items])
			if i is not None:
				self.sage_item(i)
		elif ans == 2:
			i = self.ui.choose("Locations", [st.name for st in s.sites])
			if i is not None:
				self.sage_location(i)

	def sage_item(self, i):
		"""FUN_307e_10c8."""
		s = self.s
		it = s.items[i]
		self.ui.message("The %s can be found ..." % it.name)
		if it.state == 0:
			pass                # the original never displays its message (bug)
		elif it.state == 2:
			site = None
			for st in s.sites:
				if st.item == i:
					site = st
					break
			if site is not None:
				self.ui.message("... at %s!" % site.name)
		elif it.state in (1, 3):
			if it.state == 1:
				px, py = it.x, it.y
			else:
				h = s.armies[it.loc]
				px, py = h.x, h.y
			best = 10000
			bc = None
			for c in reversed(s.cities):
				dd = dist(px, py, c.x, c.y)
				if dd < best:
					best = dd
					bc = c
			own = bc.owner if bc.owner < 8 else 8
			if it.state == 1:
				self.ui.message("... in the vicinity of the %s city of %s" % (self.data.clan_names[own], bc.name))
			else:
				self.ui.message("... near %s with a hero of the %s" % (bc.name,
					self.clan_name(s.armies[it.loc].owner)))
		else:
			self.ui.message("What???")
		self.mp_deduct(1, 4)

	def sage_location(self, k):
		"""FUN_307e_0fa2."""
		s = self.s
		st = s.sites[k]
		if st.monster == 0:
			self.ui.message("Nothing evil lives here!")
		elif not (s.tile(st.x, st.y) & M_EXPLORED):
			self.ui.message("It is inhabited by a %s!" % self.data.monster_names[st.monster])
		else:
			self.ui.message("It has already been explored!")
		ph = self.data.site_phrases[st.type] if 0 <= st.type < 9 else ""
		if ph:
			self.ui.message(ph)
		if st.type == 4:
			self.ui.message("The %s!" % s.items[st.item].name)
		self.mp_deduct(1, 4)

	def library(self):
		"""FUN_307e_0ce0."""
		s = self.s
		d = self.data
		rng = s.rng
		self.ui.message("You enter a great Library...")
		self.ui.message("Searching through the books, you find...")
		r = rng.dice(1, 3, 0)
		if r == 1:
			self.ui.message(d.quotes[min(11, rng.dice(1, 12, -1))])
		elif r == 2:
			i = min(13, rng.dice(1, 14, -1))
			it = s.items[i]
			if it.state == 0:
				self.ui.message("The %s is lost from Illuria!" % it.name)
			elif it.state == 1:
				self.ui.message("The %s is lying in %s!" % (it.name, self.region_name(s.cursor_x, s.cursor_y)))
			elif it.state == 2:
				self.ui.message("The %s is in the %s!" % (it.name, s.sites[it.loc].name))
			elif it.state == 3:
				self.ui.message("The %s is owned by a hero!" % it.name)
		elif r == 3:
			k = min(39, rng.dice(1, 32, 7))
			st = s.sites[k]
			if st.monster == 0:
				self.ui.message("%s is uninhabited!" % st.name)
			else:
				self.ui.message("A %s lives in %s!" % (d.monster_names[st.monster], st.name))
		self.mp_deduct(1, 4)

	def take_item(self, it):
		"""FUN_2cad_0734."""
		s = self.s
		if s.cur_hero is None:
			return False
		it.state = 3
		it.loc = s.cur_hero
		return True

	def drop_item(self, it):
		"""FUN_2cad_0832."""
		s = self.s
		if s.cur_hero is None:
			return False
		h = s.armies[s.cur_hero]
		it.state = 1
		it.loc = 0
		it.x, it.y = h.x, h.y
		return True

	# ==================================================================
	# turns
	# ==================================================================
	def reset_moves(self, p):
		"""FUN_1a12_0000."""
		for a in self.s.live_armies():
			if a.owner == p and a.x != -1:
				a.flags &= ~F_DONE
				a.moves = min(a.moves, 2) + a.maxmoves

	def start_human_turn(self, p):
		"""FUN_1a12_007e."""
		s = self.s
		s.current = p
		self.deselect()
		cap = s.city_at(s.players[p].cap_x, s.players[p].cap_y)
		if cap is None or cap.owner != p:
			self.relocate_capital(p)
		self.reset_moves(p)
		s.rebuild_army_flags()
		for a in s.live_armies():
			if a.owner == p:
				a.flags &= ~(F_DONE | F_VISITED)
		self.center_on_capital()
		self.ui.message("%s: Click when ready!" % self.clan_name(p))
		if s.extra_tough and not getattr(self, '_tough_warned', False):
			self._tough_warned = True
			self.ui.message("Warning: Computer is in extra tough mode!")
		self.income_upkeep(p)
		self.hero_event(p)
		s.players[p].report_allowed = 1

	def center_on_capital(self):
		s = self.s
		p = s.current
		self.center_view(s.players[p].cap_x, s.players[p].cap_y)

	def center_view(self, x, y):
		s = self.s
		s.cursor_x, s.cursor_y = x, y
		vx = max(0, min(MAP_W - 9, x - 4))
		vy = max(0, min(MAP_H - 8, y - 4))
		s.view_x, s.view_y = vx, vy
		s.view_x2, s.view_y2 = vx + 8, vy + 7

	def human_turn_production(self, p):
		"""The production report / turn-1 capital dialog at the start of a human turn."""
		s = self.s
		pl = s.players[p]
		if pl.report_allowed and not pl.report_done and not s.war_over and s.turn > 1:
			self.production_phase_human(p)
			pl.report_done = 1
		if s.turn == 1 and not pl.report_done:
			cap = self.capital_city(p)
			if cap is not None:
				self.ui.city_production(self, cap)
			pl.report_done = 1

	def end_of_round(self):
		"""FUN_1b90_0116."""
		s = self.s
		s.recount_cities()
		for p in range(8):
			if s.alive[p] and s.ncities[p] == 0:
				for a in list(s.live_armies()):
					if a.owner == p:
						if a.type == HERO:
							self.hero_death(a, a.x, a.y)
						s.free_army(a)
				if s.human[p]:
					self.ui.message("Wretched  %s!  For you, the war is over!" % self.clan_name(p))
				else:
					self.ui.message("%s are no longer a threat!" % self.clan_name(p))
				s.alive[p] = 0
				s.players[p].gold = 0
		alive = [p for p in range(8) if s.alive[p]]
		if not alive:
			self.ui.game_over(self, ["As no players are involved in the..",
				"game I bid you a fond 'FAREWELL' ...", "Hit any key to return to DOS."])
			self.quit = True
			return
		humans_alive = [p for p in alive if s.human[p]]
		if not humans_alive and any(s.human) and not s.war_over:
			s.war_over = 1
			self.ui.message("As no further human resistance is ...")
			self.ui.message("possible the battle for Illuria ...")
			self.ui.message("will continue without you ...")
		ai_alive = [p for p in alive if not s.human[p]]
		if not s.war_over and len(humans_alive) == 1 and not ai_alive and len(alive) == 1:
			s.war_over = 1
			w = humans_alive[0]
			self.ui.play_sound('horn')
			self.ui.game_over(self, ["Player %d, %s: You have won!" % (w + 1, self.clan_name(w)),
				"You now rule all of Illuria ...", "You may now inspect your domain."])

	def surrender_check(self):
		"""FUN_1b90_0434 (run when a human presses End Turn). Returns 1 if the turn continues."""
		s = self.s
		if s.surrender_offered:
			return 0
		s.recount_cities()
		humans = [p for p in range(8) if s.alive[p] and s.human[p]]
		if not humans:
			return 0
		h = s.ncities[humans[-1]]
		m = max([s.ncities[p] for p in range(8) if s.alive[p] and not s.human[p]] or [0])
		if h > 40 and len(humans) == 1 and h > m + 15:
			s.surrender_offered = 1
			self.ui.picture('beg', ["Your seneschal reports strangers at the gate!",
				"Crawling towards you they humbly present a scroll"])
			ans = self.ui.ask(["MIGHTY WARLORD!!", "The fickle tides of war have turned",
				"your way and the Gods favour you!", "The few remaining leaders send",
				"ambassadors to offer you all their", "lands if you will but spare their",
				"insignificant, wretched lives!"],
				[" Accept a grovelling surrender! ", " Off with their miserable heads! "])
			if ans == 0:
				s.war_over = 1
				for p in range(8):
					s.human[p] = 1
				self.ui.game_over(self, ["Under your enlightened rule ...", "Illuria has entered a new golden age ...",
					"You may now inspect your domain."])
			else:
				self.no_quarter()
			return 1
		return 0

	def no_quarter(self):
		"""FUN_1b90_0730."""
		s = self.s
		self.ui.picture('head', ["No Quarter !!!"])
		for i in range(8):
			if not s.alive[i]:
				continue
			for j in range(8):
				if not s.alive[j]:
					continue
				if s.human[j]:
					s.hatred[i][j] = s.rng.dice(1, 1000, 100)
					s.war[i] = s.current
				else:
					s.hatred[i][j] = 0

	def ai_turn(self, p):
		"""FUN_274c_0000."""
		s = self.s
		self.ui.ai_turn_start(self, p)
		s.current = p
		s.rebuild_army_flags()
		if s.ncities[p] > 0:
			self.reset_moves(p)
			self.income_upkeep(p)
			self.hero_event(p)
			if self.ai is not None:
				self.ai.production(p)
				self.ai.main(p)
		self.ui.ai_turn_end(self, p)

	def run(self, resume_player=None):
		"""FUN_1312_000e: the main round loop."""
		s = self.s
		first = True
		while not self.quit:
			start = 0
			skip_ai = False
			if first and resume_player is not None:
				skip_ai = True
				start = resume_player
			if not skip_ai:
				for p in range(8):
					s.players[p].report_allowed = s.players[p].report_done = 1 if s.war_over else 0
				for p in range(8):
					if self.quit:
						return
					if s.alive[p] and not s.human[p]:
						self.ai_turn(p)
			for p in range(start, 8):
				if self.quit:
					return
				if s.human[p] and s.alive[p]:
					if not (first and resume_player is not None and p == resume_player):
						self.start_human_turn(p)
					s.current = p
					r = self.ui.human_turn(self, p)
					if r == 'quit':
						self.quit = True
						return
			first = False
			self.end_of_round()
			s.turn += 1
			if not any(s.alive[p] and s.human[p] for p in range(8)) and not any(s.human):
				pass
