"""Computer player ("AI by Roger Keating"), ported from WARLORDS.EXE v2.10.

Function names in doc strings refer to the original code (Ghidra naming).
The AI is strongly tied to the Illuria map through hard-coded tables
(city neighbours, priority cities, ruin preference lists ...), which are read
from the executable like everything else.
"""
from .gamedata import (CITY_DX, CITY_DY, MAP_W, NEUTRAL, HERO, NAVY, DRAGON, WIZARD, CITY, PEGASI,
	GRIFFIN, LIGHT)
from .state import F_DONE, F_AI_GROUP, F_AI_MISSION, F_AI_ERRAND, M_ARMY, M_EXPLORED
from .rng import dist

NW_CITIES = (2, 6, 10)


class AI:

	def __init__(self, game):
		self.g = game
		self.s = game.s
		self.d = game.data
		self.cls_table = list(self.d.ai_class_normal)

	# ==================================================================
	# helpers
	# ==================================================================
	@property
	def p(self):
		return self.s.current

	def cls(self, t):
		if t < 0 or t > 15:
			return 0
		return self.cls_table[t]

	def city(self, i):
		return self.s.cities[i]

	def owner(self, i):
		return self.s.cities[i].owner

	def intact(self, i):
		c = self.s.cities[i]
		return self.s.tclass(c.x, c.y) == CITY

	def neighbours(self, i):
		return self.d.neighbours[i]

	def armies_in_city(self, c, owner=None):
		res = []
		for a in self.s.live_armies():
			if c.x <= a.x <= c.x + 1 and c.y <= a.y <= c.y + 1 and (owner is None or a.owner == owner):
				res.append(a)
		return res

	def own_armies(self):
		p = self.p
		return [a for a in self.s.live_armies() if a.owner == p]

	def region_str(self, ci, with_def):
		"""FUN_27ed_19d8: strength of the city owner's armies around a city. Returns (value, n)."""
		s = self.s
		c = s.cities[ci]
		return self._area_str(c.owner, c.x, c.y, with_def, c.defence)

	def _area_str(self, owner, x, y, with_def=False, defence=0):
		s = self.s
		d = self.d
		total = 0
		n = 0
		hero = 0
		special = 0
		flyer = 0
		items = 0
		for a in s.live_armies():
			if a.owner != owner or not (x - 4 <= a.x <= x + 5 and y - 4 <= a.y <= y + 5):
				continue
			if a.strength <= 3:
				continue
			total += a.strength
			n += 1
			if a.type == HERO:
				cmd = self.g.cmd_items(a)
				hero = max(hero, min(9, a.strength + cmd))
				items += cmd
			if WIZARD <= a.type <= 14:
				special = 1
			if self.d.flyer_class[a.type] == 5:
				flyer = 1
		bonus = d.hero_cmd[min(9, hero)] + special + flyer + items
		val = total + n * bonus
		if with_def:
			val += d.city_def_bonus[max(0, min(10, defence))] * n
		return val, n

	def city_index_at(self, x, y):
		c = self.s.city_at(x, y)
		return c.index if c else -1

	def nearest_nonneutral(self, x, y):
		"""FUN_29b2_0500."""
		best = 10000
		res = -1
		for i in range(79, -1, -1):
			c = self.s.cities[i]
			if c.owner == NEUTRAL:
				continue
			dd = dist(x, y, c.x, c.y)
			if dd < best and (i not in NW_CITIES or (x < 20 and y < 26)) and \
					(i in NW_CITIES or x > 18 or y > 24):
				res = i
				best = dd
		return res

	def lead(self):
		"""FUN_24ef_032e."""
		s = self.s
		alive = [q for q in range(8) if s.alive[q]]
		if not alive:
			return 0, -1
		leader = max(alive, key=lambda q: s.ncities[q])
		others = [q for q in alive if q != leader]
		second = max([s.ncities[q] for q in others] or [0])
		m = 5
		if s.level[self.p] == 3 and s.human[leader]:
			m = 0
		return max(0, s.ncities[leader] - second - m), leader

	# ==================================================================
	# production (FUN_277d_0010)
	# ==================================================================
	def production(self, p):
		g = self.g
		g.transit_arrivals(p, False)
		for c in self.s.cities:
			g.production_tick(c, False)

	def buy(self, c, slot, vector_to=-1):
		"""FUN_29b2_0278."""
		s = self.s
		p = self.p
		if slot is None or slot < 0:
			return False
		if s.players[p].gold < c.cost[slot] + 30 and s.turn > 5:
			return False
		c.prod = slot
		c.elapsed = 0
		c.turns = self.g.build_time(c, slot, p)
		s.players[p].gold -= c.cost[slot]
		if vector_to != -1 and vector_to is not None:
			v = s.cities[vector_to]
			c.vector = 1
			c.vx, c.vy = v.x, v.y
		else:
			c.vector = 0
		return True

	def _score(self, c, t):
		s = 10 - (c.strength[t] - c.time[t])
		if self.cls(t) == 5:
			s -= self.s.rng.dice(1, 2, 0)
		return s & 0xff

	def build_fast(self, c):
		"""FUN_29b2_0ac4."""
		best = None
		for t in range(10):
			if not c.can[t] or t == NAVY:
				continue
			if c.island and self.cls(t) != 5:
				continue
			if best is None or c.time[t] < c.time[best] or (c.time[t] == c.time[best] and c.strength[t] > c.strength[best]):
				best = t
		if best is not None:
			self.buy(c, best, -1)

	def build_best(self, c, v=-1, want_cls=None):
		"""FUN_29b2_0b8e."""
		best = None
		bs = None
		for t in range(10):
			if not c.can[t] or t == NAVY or c.strength[t] < 4:
				continue
			if want_cls is not None and self.cls(t) != want_cls and not (want_cls == 0):
				continue
			sc = self._score(c, t)
			if best is None or sc < bs or (sc == bs and (c.strength[t] > c.strength[best] or
					(c.strength[t] == c.strength[best] and c.cost[t] < c.cost[best]))):
				best, bs = t, sc
		if best is not None:
			self.buy(c, best, v)
			return True
		return False

	def build_attack(self, c, v=-1):
		"""FUN_29b2_0cd6."""
		s = self.s
		if v == -1:
			incoming = len(self.g.vectors_into(c))
			if incoming < 2:
				roles = self.analysis(c)
				best = None
				bval = None
				my_cls = self.cls(c.ai_type) if c.ai_type >= 0 else 0
				for i, (role, val) in roles.items():
					if role != 3 or i == c.index:
						continue
					o = s.cities[i]
					if len(self.g.vectors_into(o)) >= 4:
						continue
					if self.cls(o.ai_type) != my_cls:
						continue
					if bval is None or val < bval:
						best, bval = i, val
				if best is not None:
					myval = roles.get(c.index, (0, 1 << 15))[1] if c.ai_target != -1 else None
					tval = self._target_value(c)
					if bval is not None and bval < tval:
						c.ai_target = -1
						s.ai_state[c.index] = 4
						v = best
		want = self.cls(c.ai_type) if c.ai_type >= 0 else 0
		best = None
		bs = None
		for t in range(10):
			if not c.can[t] or t == NAVY or c.strength[t] < 4:
				continue
			if want != 0 and self.cls(t) != want:
				continue
			sc = self._score(c, t)
			if best is None or sc < bs or (sc == bs and c.strength[t] > c.strength[best]):
				best, bs = t, sc
		if best is None:
			return self.build_best(c, v)
		self.buy(c, best, v)
		return True

	def _target_value(self, c):
		if c.ai_target < 0:
			return 1 << 15
		v, _ = self.region_str(c.ai_target, True)
		war = self.s.war[self.p]
		for n in self.neighbours(c.ai_target):
			if self.owner(n) == war:
				v -= 10
		return max(0, v)

	def analysis(self, src):
		"""Role of every own city as seen from src (part of FUN_29b2_10f4)."""
		s = self.s
		p = self.p
		roles = {}
		for c in s.cities:
			if c.owner != p:
				continue
			if c.index == src.index:
				roles[c.index] = (1, c.ai_strong)
			elif c.ai_target == -1 and c.ai_strong < 2:
				roles[c.index] = (2, c.ai_strong)
			elif c.ai_target != -1 and c.ai_type >= 0 and c.ai_type < 10 and src.can[c.ai_type]:
				roles[c.index] = (3, self._target_value(c))
		return roles

	def build_for_front(self, c):
		"""FUN_29b2_10f4."""
		s = self.s
		if not any(c.can[t] and t != NAVY and c.strength[t] >= 4 for t in range(10)):
			return
		c.vector = 0
		roles = self.analysis(c)
		dest = None
		prio = 0
		# 1. a weak (value < 2) own city with no incoming vectors
		for i, (role, val) in roles.items():
			if role in (1, 2) and val < 2 and not self.g.vectors_into(s.cities[i]):
				dest = i
				prio = 1
				break
		if dest is None:
			bv = None
			for i, (role, val) in roles.items():
				if role == 3 and len(self.g.vectors_into(s.cities[i])) < 4:
					if bv is None or val < bv:
						bv = val
						dest = i
						prio = 2
		if dest is None:
			bs = None
			for i, (role, val) in roles.items():
				if role in (1, 2) and len(self.g.vectors_into(s.cities[i])) < 4:
					need, garrison = self.threat(s.cities[i], dry=True)
					if val < garrison:
						sc = max(0, garrison - val) + s.rng.dice(1, 2, 0)
						if bs is None or sc > bs:
							bs = sc
							dest = i
							prio = 3
		if dest is None or dest == c.index:
			s.ai_state[c.index] = 2
			self.build_best(c, -1)
			return
		s.ai_state[c.index] = 4
		if prio == 2:
			c.ai_type = s.cities[dest].ai_type
			self.build_attack(c, dest)
		else:
			self.build_best(c, dest)

	def pick_attack_type(self, c, want=-1):
		"""FUN_29b2_129e."""
		s = self.s
		if c.ai_target >= 0:
			t = s.cities[c.ai_target]
			if t.island and c.ai_target not in self.neighbours(c.index):
				want = GRIFFIN
		want_cls = self.cls(want) if want >= 0 else None
		best = None
		bs = None
		for t in range(10):
			if not c.can[t] or t == NAVY:
				continue
			if want_cls is not None and self.cls(t) != want_cls:
				continue
			sc = self._score(c, t)
			if best is None or sc < bs:
				best, bs = t, sc
		if best is None:
			if c.ai_target >= 0 and s.cities[c.ai_target].island:
				c.ai_target = -1
			else:
				c.ai_type = LIGHT
		else:
			c.ai_type = best

	# ==================================================================
	# city management
	# ==================================================================
	def threat(self, c, dry=False):
		"""FUN_29b2_0350: (need, garrison); may raze the city or repair its defence."""
		s = self.s
		p = self.p
		need, garrison = 2, 2
		if s.players[p].gold > 5:
			garrison = 4
			war = s.war[p]
			own_n = warn = 0
			for n in reversed(self.neighbours(c.index)):
				o = self.owner(n)
				if o == p:
					own_n += 1
				elif o == war:
					warn += 1
					need += 1
					garrison = 12
				elif o != NEUTRAL:
					need += 1
					garrison = 6
			if dry:
				return need, garrison
			pl = s.players[p]
			if own_n == 0 and warn > 1 and s.ncities[p] > 6 and c.ai_target == -1 and pl.razer and \
					dist(c.x, c.y, pl.cap_x, pl.cap_y) > 20:
				self.g.raze_city(c, p)
				return 0, garrison
			if s.level[p] > 0:
				dc = self.d.def_cost
				if 0 <= c.defence < 3 and dc[c.defence] + 200 < pl.gold:
					c.defence += 1
					pl.gold -= dc[c.defence]
		return need, garrison

	def early_threat(self, c):
		"""FUN_24ef_1198."""
		s = self.s
		if s.turn > 15:
			return 2
		res = 0
		p = self.p
		for a in s.live_armies():
			if a.owner == p or a.x < 0:
				continue
			if abs(a.x - c.x) + abs(a.y - c.y) <= 20:
				if s.human[a.owner] or a.goal == c.index:
					return 2
				res = max(res, 1)
		return res

	def _place(self, a, c, k, counts):
		s = self.s
		a.x, a.y = c.x + CITY_DX[k], c.y + CITY_DY[k]
		counts[k] += 1
		i = a.y * MAP_W + a.x
		s.map[i] = (s.map[i] & 0xf87f) | (a.owner << 7) | M_ARMY

	def organise(self, c, mode):
		"""FUN_24ef_040e: garrison, stacking and disbanding in one city.
		Returns (ok, new_mode)."""
		s = self.s
		p = self.p
		lvl = s.level[p]
		L = []
		any_targeted = False
		hero_here = False
		n_strong = 0
		for a in list(s.live_armies()):
			if a.owner == p and c.x <= a.x <= c.x + 1 and c.y <= a.y <= c.y + 1:
				if a.goal != -1:
					any_targeted = True
				if a.type == HERO:
					hero_here = True
				if a.type < 10 and a.strength > 3:
					n_strong += 1
				if len(L) < 32 or a.type == HERO:
					L.append(a)
				else:
					s.free_army(a)
		c.ai_strong = n_strong
		if any_targeted and s.rng.dice(1, 4, -1) == 0:
			return True, mode
		need, garrison = self.threat(c)
		if need == 0:
			t = self.nearest_nonneutral(c.x, c.y)
			for a in L:
				a.goal = t
			return False, mode
		if lvl >= 2 and mode == 0:
			need = self.early_threat(c)
		if len(L) < 2 and mode not in (0, 5):
			mode = 1
		elif n_strong < need and mode not in (0, 4, 5):
			mode = 2
		if c.index % 4 == s.turn % 4 and mode == 4:
			return True, mode
		# sort: heroes / first flyer / strength descending (same scan as the original)
		pool = list(L)
		S = []
		fly_taken = False
		while True:
			pick = -1
			best_str = -1
			best_i = -1
			for i in range(len(pool) - 1, -1, -1):
				a = pool[i]
				if a is None:
					continue
				pick = i
				if a.type == HERO:
					break
				if not fly_taken and self.d.flyer_class[a.type] == 5:
					fly_taken = True
					break
				if a.strength > best_str:
					best_str = a.strength
					best_i = i
				pick = -2
			if pick == -1:
				break
			if pick == -2:
				pick = best_i
			S.append(pool[pick])
			pool[pick] = None
		if n_strong > 3:
			for i, a in enumerate(S):
				if a is not None and a.strength < 4 and a.type != HERO:
					S[i] = None
					s.free_army(a)
		for k in range(4):
			x, y = c.x + CITY_DX[k], c.y + CITY_DY[k]
			s.map[y * MAP_W + x] &= 0xf7ff
		counts = [0, 0, 0, 0]
		extra = 0
		if mode == 0:
			extra = 8
		elif mode == 5:
			if len([a for a in S if a is not None]) > 3:
				tgt = self.validate_target(c.ai_target, c)
				if tgt is None:
					c.ai_target = -1
					mode = 3
				else:
					c.ai_target = tgt
					tcls = self.cls(c.ai_type) if c.ai_type >= 0 else 0
					T, tN = self.region_str(tgt, True)
					O, _ = self.region_str(c.index, False)
					dd = dist(c.x, c.y, s.cities[tgt].x, s.cities[tgt].y)
					count = 0
					last = None
					got_hero = got_dragon = False
					for i, a in enumerate(S):
						if a is None or count >= 8:
							continue
						ac = self.cls(a.type)
						if tcls == 0 or ac == tcls or ac == 5 or a.type == HERO or (tcls != 5 and a.type > 9):
							if (a.type != HERO or not got_hero) and (a.type != DRAGON or not got_dragon):
								count += 1
								S[i] = None
								self._place(a, c, 0, counts)
								last = a
							if a.type == HERO:
								got_hero = True
							elif a.type == DRAGON:
								got_dragon = True
					if count > 1 and count == len(L) and last is not None:
						last.x, last.y = c.x + 1, c.y
						i = last.y * MAP_W + last.x
						s.map[i] = (s.map[i] & 0xf87f) | (p << 7) | M_ARMY
						count -= 1
					reserve = 2 if hero_here else need
					if tcls == 0 and (dd < 10 or count > 5) and tN < 8 and (T // 2) * 3 < O and count > 2:
						reserve = 0
					if reserve == 0 or (count > 7 and count + reserve <= len(L)):
						mode = 6
		if mode not in (5, 6):
			moved = False
			for i, a in enumerate(S):
				if a is not None and a.type == HERO and counts[0] < 8:
					S[i] = None
					moved = True
					self._place(a, c, 0, counts)
			if moved:
				for i, a in enumerate(S):
					if a is not None and self.d.flyer_class[a.type] == 5 and counts[0] < 8:
						S[i] = None
						self._place(a, c, 0, counts)
		gcount = need if mode == 0 else garrison
		while gcount > 0:
			idx = None
			for i, a in enumerate(S):
				if a is not None and a.type != HERO:
					idx = i
					break
			if idx is None:
				break
			a = S[idx]
			S[idx] = None
			self._place(a, c, 1 if gcount < 9 else 2, counts)
			gcount -= 1
		while extra > 0:
			idx = None
			for i, a in enumerate(S):
				if a is not None:
					idx = i
					break
			if idx is None:
				break
			a = S[idx]
			S[idx] = None
			self._place(a, c, 3 if mode in (5, 6) else 0, counts)
			extra -= 1
		for i, a in enumerate(S):
			if a is None:
				continue
			keep = a.type == HERO
			if lvl >= 2 and self.d.flyer_class[a.type] == 5:
				best = None
				bd = 10000
				for j in range(79, -1, -1):
					o = s.cities[j]
					if o.owner == p and o.ai_target != -1:
						dd = dist(c.x, c.y, o.x, o.y)
						if dd < bd:
							bd = dd
							best = j
				if best is not None:
					a.goal = best
					keep = True
			if not keep and mode in (5, 6) and self.cls(c.ai_type) not in (5, 1):
				keep = True
			if keep:
				k = 3
				while k > 0 and counts[k] > 7:
					k -= 1
				self._place(a, c, k, counts)
			else:
				s.free_army(a)
		return True, mode

	def expand(self, c):
		"""FUN_27ed_061e: grab undefended enemy cities, expand into neutral neighbours."""
		s = self.s
		p = self.p
		lvl = s.level[p]
		N = []
		grab = -1
		for n in self.neighbours(c.index):
			if not self.intact(n):
				continue
			o = self.owner(n)
			if o == NEUTRAL:
				N.append(n)
			elif o != p:
				nc = s.cities[n]
				if not any(s.tile(nc.x + CITY_DX[k], nc.y + CITY_DY[k]) & M_ARMY for k in range(4)):
					grab = n
		if grab != -1:
			skip = 2
			for a in list(s.live_armies()):
				if a.owner == p and not (a.flags & F_DONE) and a.goal == -1 and a.type != HERO and \
						(not c.island or self.cls(a.type) == 5) and c.x <= a.x <= c.x + 1 and c.y <= a.y <= c.y + 1:
					if skip == 0:
						a.flags |= F_AI_MISSION
						a.goal = grab
						break
					skip -= 1
		if c.ai_target == -1 and N:
			s.ai_state[c.index] = 0
			ok, mode = self.organise(c, 0)
			if not ok:
				s.ai_state[c.index] = -1
				return 0
			tgt = -1
			for k in range(5, -1, -1):
				if self.d.ai_priority[k] in N:
					tgt = self.d.ai_priority[k]
			if tgt == -1:
				cnt = [0] * len(N)
				for a in s.live_armies():
					if a.owner == p and a.goal != -1:
						for j, n in enumerate(N):
							if a.goal == n:
								cnt[j] += 1
				bs = 100
				for j in range(len(N) - 1, -1, -1):
					if cnt[j] < 2:
						sc = cnt[j] * 4 + s.rng.dice(1, 3, 0)
						if sc < bs:
							bs = sc
							tgt = N[j]
			if tgt != -1:
				for a in s.live_armies():
					if a.owner == p and not (a.flags & F_DONE) and (not c.island or self.cls(a.type) == 5) and \
							a.goal == -1 and a.x == c.x and a.y == c.y and \
							(a.type != HERO or lvl == 0 or (a.flags & F_AI_MISSION)):
						a.goal = tgt
						if lvl != 0:
							a.flags |= F_AI_MISSION
				return 1
		return 0

	# ==================================================================
	# targets and diplomacy
	# ==================================================================
	def update_war(self):
		"""FUN_24ef_0004."""
		s = self.s
		p = self.p
		lvl = s.level[p]
		old = s.war[p]
		if old != -1 and not s.alive[old]:
			if lvl == 3:
				for h in range(8):
					if s.alive[h] and s.human[h]:
						s.hatred[p][h] += 5
			s.war[p] = -1
		ld, leader = self.lead()
		if lvl == 3 and p != leader and ld > 4:
			for j in range(8):
				if j != leader and not s.human[j] and s.hatred[p][j] > 10:
					s.hatred[p][j] -= 1
		best = 0
		bj = -1
		btie = -1
		for j in range(8):
			if not s.alive[j] or j == p:
				continue
			if s.ncities[p] > 40:
				s.hatred[p][j] = max(s.hatred[p][j], 5)
			sc = s.hatred[p][j] + (3 if (j == s.war[p] or s.war[j] == p) else 0) + (ld if j == leader else 0)
			if sc > best:
				best = sc
				bj = j
				btie = s.rng.dice(1, 10, 0)
			elif sc == best and sc > 0:
				t = s.rng.dice(1, 10, 0)
				if t > btie:
					bj = j
					btie = t
		if best > 0:
			s.war[p] = bj
		w = s.war[p]
		if lvl == 3 and w != -1 and s.human[w]:
			for c in s.cities:
				if c.owner == p or c.prev_owner == p:
					c.prev_owner = NEUTRAL
		if w == -1 or not s.alive[w] or s.ncities[w] == 0:
			s.war[p] = -1
		elif w != old:
			self.g.ui.status("%s declares war on %s" % (self.g.clan_name(p), self.g.clan_name(w)))

	def choose_target(self):
		"""FUN_24ef_1292: pick a new (source city, enemy city) pair."""
		s = self.s
		p = self.p
		self.update_war()
		T = s.war[p]
		if T == -1:
			return None
		self.flyer_strike()
		nDef = sum(1 for c in s.cities if c.owner == p and s.ai_state[c.index] == 3)
		atk = [c for c in s.cities if c.owner == p and s.ai_state[c.index] in (5, 6)]
		nAtk = len(atk)
		nAtkWar = sum(1 for c in atk if c.ai_target >= 0 and self.owner(c.ai_target) == T)
		ld, leader = self.lead()
		alt = -1
		if (s.ncities[p] > 20 and s.ncities[T] < 5) or (nAtkWar == 0 and s.ncities[T] < 6):
			best = 0
			for j in range(8):
				if j in (p, T) or not s.alive[j]:
					continue
				sc = s.hatred[p][j] + s.rng.dice(1, 2, 0) + (ld if j == leader else 0)
				if sc > best:
					best = sc
					if nAtk == 0 or sc > 5:
						alt = j
		cand = [-1] * 80
		for c in s.cities:
			if c.owner == p and (s.ai_state[c.index] in (3, 2) or (nDef > 5 and s.ai_state[c.index] == 4)):
				cand[c.index] = -2
		for i in range(80):
			if cand[i] == -2:
				for n in self.neighbours(i):
					o = self.owner(n)
					if o != p and o != NEUTRAL and cand[n] != -2:
						cand[n] = 0
		tgt = -1
		bsc = 25
		for i in range(80):
			if cand[i] != 0:
				continue
			o = self.owner(i)
			c = s.cities[i]
			sc = s.rng.dice(1, 20, 0)
			if o == T:
				sc += 60
			elif c.prev_owner == p or o == alt:
				sc += 40
			elif s.hatred[p][o] > 4 and nAtkWar == 0:
				sc += 20
			for n in self.neighbours(i):
				on = self.owner(n)
				if on == T:
					sc += 10
				elif s.cities[n].prev_owner == p:
					sc += 7
				elif on < 8 and s.hatred[p][on] > 4 and nAtkWar == 0:
					sc += 5
			if sc > bsc:
				bsc = sc
				tgt = i
		if tgt == -1:
			return None
		src = -1
		bs = -1
		tc = s.cities[tgt]
		for n in self.neighbours(tgt):
			if cand[n] == -2:
				o = s.cities[n]
				sc = dist(tc.x, tc.y, o.x, o.y) + s.rng.dice(1, 4, 0)
				if sc > bs:
					bs = sc
					src = n
		if src == -1:
			return None
		return src, tgt

	def flyer_strike(self):
		"""FUN_24ef_181e."""
		s = self.s
		p = self.p
		T = s.war[p]
		if T == -1:
			return
		X = -1
		bx = -1
		for c in s.cities:
			if c.owner == T:
				r = s.rng.dice(1, 100, 0)
				if r > bx:
					bx = r
					X = c.index
		if X == -1:
			return
		for c in s.cities:
			if c.owner == p and c.ai_target != -1 and c.ai_type >= 0 and self.cls(c.ai_type) == 5:
				return
		xc = s.cities[X]
		best = None
		bd = 10000
		for c in s.cities:
			if c.owner != p or c.ai_target != -1 or c.ai_strong <= 2:
				continue
			if not (c.can[PEGASI] or c.can[GRIFFIN]):
				continue
			if any(self.owner(n) not in (p, NEUTRAL) for n in self.neighbours(c.index)):
				continue
			dd = dist(c.x, c.y, xc.x, xc.y)
			if dd < bd:
				bd = dd
				best = c
		if best is not None:
			best.ai_target = X
			self.pick_attack_type(best, GRIFFIN)
			s.ai_state[best.index] = 5

	def validate_target(self, tgt, src):
		"""FUN_24ef_1b68. Returns a target index or None."""
		s = self.s
		p = self.p
		if tgt is None or tgt < 0:
			return None
		lvl = s.level[p]
		res = tgt if self.owner(tgt) != NEUTRAL else None
		if lvl >= 2 and (src.ai_type < 0 or self.cls(src.ai_type) != 5) and not s.cities[tgt].island:
			tc = s.cities[tgt]
			rng = max(10, dist(src.x, src.y, tc.x, tc.y))
			thr = abs(5 * self.region_str(tgt, True)[0]) // 4
			best = None
			bv = None
			for n in self.neighbours(src.index):
				if n == tgt:
					continue
				o = self.owner(n)
				if o == p:
					continue
				nc = s.cities[n]
				ok = nc.prev_owner == p or o == s.war[p]
				if lvl == 3 and o < 8 and s.human[o] and s.ncities[o] >= s.ncities[p] + 5:
					ok = True
				if not ok:
					continue
				if dist(src.x, src.y, nc.x, nc.y) >= rng:
					continue
				v = self.region_str(n, True)[0]
				if v < thr and (bv is None or v < bv):
					bv = v
					best = n
			if best is not None:
				src.ai_target = best
				return best
		return res

	def truce(self):
		"""FUN_29b2_05a8."""
		s = self.s
		me = self.p
		if s.rng.dice(1, 4, -1) != 0:
			return
		E = s.war[me]
		if E == -1 or s.level[me] != 3 or s.human[E] or s.level[E] != 3 or s.players[me].truce != 0:
			return
		if s.war[E] != me:
			return
		alive = [q for q in range(8) if s.alive[q]]
		L = max(alive, key=lambda q: s.ncities[q])
		if L in (me, E):
			return
		cm, ce, cl = s.ncities[me], s.ncities[E], s.ncities[L]
		if not (cm > 9 and ce > 9 and abs(cm - ce) < 6 and abs(cm - cl) > 4 and abs(ce - cl) > 4):
			return
		s.players[me].truce += 1
		s.hatred[me][E] = 0
		s.hatred[me][L] += 10
		s.hatred[E][me] = 0
		s.hatred[E][L] += 10
		for c in s.cities:
			if (c.owner == me and c.prev_owner == E) or (c.owner == E and c.prev_owner == me):
				c.prev_owner = NEUTRAL
			if c.owner == me and c.ai_target >= 0 and self.owner(c.ai_target) == E:
				c.ai_target = -1
			if c.owner == E and c.ai_target >= 0 and self.owner(c.ai_target) == me:
				c.ai_target = -1
		for a in s.live_armies():
			if 0 <= a.goal < 80:
				if (a.owner == me and self.owner(a.goal) == E) or (a.owner == E and self.owner(a.goal) == me):
					a.goal = a.origin if 0 <= a.origin < 80 else -1
		self.g.ui.status("%s signs a truce with %s" % (self.g.clan_name(me), self.g.clan_name(E)))
		s.war[me] = s.war[E] = -1

	# ==================================================================
	# launching attacks
	# ==================================================================
	def launch(self):
		"""FUN_27ed_11c8."""
		s = self.s
		p = self.p
		lvl = s.level[p]
		for ci in range(79, -1, -1):
			if s.ai_state[ci] != 6:
				continue
			c = s.cities[ci]
			tgt = c.ai_target
			if tgt < 0:
				continue
			if lvl == 3 and c.ai_type >= 0 and self.cls(c.ai_type) == 5:
				tgt = self.deep_strike(c, tgt)
			for a in s.live_armies():
				if a.owner == p and a.x == c.x and a.y == c.y:
					a.flags &= ~F_DONE
					a.goal = tgt
					a.origin = ci
			drop = lvl < 2 or s.players[p].gold < 50
			o = self.owner(tgt)
			if s.surrender_offered and lvl == 3 and o < 8 and not s.human[o]:
				drop = True
			if o in (p, NEUTRAL):
				drop = True
			if not drop:
				v = w = 0
				for k in range(79, -1, -1):
					o2 = s.cities[k]
					if o2.vector and o2.vx == c.x and o2.vy == c.y:
						v += 1
					elif o2.ai_target == c.ai_target:
						w += 1
				if lvl == 3:
					drop = v <= s.players[p].thrift
				else:
					drop = s.rng.dice(1, 10, 0) > w * 4 + v
			if drop:
				c.ai_target = -1

	def deep_strike(self, c, tgt):
		"""FUN_27ed_1770."""
		s = self.s
		p = self.p
		tc = s.cities[tgt]
		if dist(c.x, c.y, tc.x, tc.y) >= 41:
			return tgt
		victim = -1
		bv = -1
		for q in range(8):
			if q == p or not s.alive[q]:
				continue
			v = s.ncities[q] + (10 if s.war[p] == q else 0) + (10 if s.human[q] else 0)
			if v > bv:
				bv = v
				victim = q
		if victim == -1:
			return tgt
		best = tgt
		bs = None
		for k in s.cities:
			if k.owner != victim:
				continue
			nb = self.neighbours(k.index)
			if not all(self.owner(n) in (victim, NEUTRAL) for n in nb):
				continue
			defenders = len(self.armies_in_city(k, victim))
			sc = s.rng.dice(1, 3, 0) - defenders + sum(1 for n in nb if self.owner(n) in (victim, NEUTRAL)) + 32
			if bs is None or sc > bs:
				bs = sc
				best = k.index
		return best

	def gate_decision(self, leader, group):
		"""FUN_29b2_1566: attack now (True) or retarget to a softer neighbour."""
		s = self.s
		p = self.p
		if s.turn < 20:
			return True
		home = leader.origin if 0 <= leader.origin < 80 else self.city_index_at(s.players[p].cap_x, s.players[p].cap_y)
		tgt = leader.goal
		if not (0 <= tgt < 80) or home == tgt or s.cities[tgt].island:
			return True
		own, _ = self._area_str(p, leader.x, leader.y)
		T = self.region_str(tgt, True)[0] - 10
		if T < 0:
			T = 0
		if own > (T * 3) // 2:
			return True
		hc = s.cities[home] if home >= 0 else None
		tc = s.cities[tgt]
		best = None
		bv = T
		for n in self.neighbours(tgt):
			nc = s.cities[n]
			if nc.owner == p:
				continue
			if not (nc.prev_owner == p or nc.owner == s.war[p]):
				continue
			v = self.region_str(n, True)[0]
			if v < bv and hc is not None and \
					dist(hc.x, hc.y, tc.x, tc.y) + dist(tc.x, tc.y, nc.x, nc.y) < dist(hc.x, hc.y, nc.x, nc.y) + 6:
				bv = v
				best = n
		if best is not None:
			for a in group:
				a.goal = best
			return False
		return True

	# ==================================================================
	# heroes and monsters (FUN_1d88_000c)
	# ==================================================================
	def heroes_and_monsters(self):
		s = self.s
		p = self.p
		lvl = s.level[p]
		war = s.war[p]
		if lvl == 3 and war != -1 and s.human[war]:
			for c in s.cities:
				if c.owner == p or (c.prev_owner == p and not (c.owner < 8 and s.human[c.owner])):
					c.prev_owner = NEUTRAL
		if s.ruin_plan[p] == -1:
			s.ruin_plan[p] = max(0, min(1, s.rng.dice(1, 2, -1)))
		for a in list(s.live_armies()):
			if a.owner != p or a.x == -1 or a.type < 10 or (a.flags & F_DONE) or a.owner == 0xff:
				continue
			if s.turn == 1:
				k = s.rng.dice(1, 4, -1) + p * 4
				k = max(0, min(31, k))
				t = self.d.ai_turn1_targets[k // 4][k % 4]
				if t != 0:
					a.goal = t - 1
					return
			if a.type == HERO:
				self.pick_up(a)
			if self.goal_done(a.goal):
				a.goal = -1
			ci = self.city_index_at(a.x, a.y)
			if a.type == HERO:
				self.hero_logic(a, ci)
			else:
				self.monster_logic(a, ci)

	def goal_done(self, goal):
		"""FUN_1d88_1751."""
		s = self.s
		if goal < 81:
			return False
		if goal < 200:
			k = goal - 100
			if not (0 <= k < 40):
				return True
			st = s.sites[k]
			if (s.tile(st.x, st.y) & M_EXPLORED) or (k == 1 and s.gem_seer) or (k == 7 and s.gem_oracle):
				return True
			return False
		k = goal - 200
		if 0 <= k < 14 and s.items[k].state == 1:
			return False
		return True

	def pick_up(self, h):
		"""FUN_1d88_166e: a computer hero takes the items lying on its tile."""
		for it in self.s.items:
			if it.state == 1 and it.x == h.x and it.y == h.y:
				it.state = 3
				it.loc = h.index

	def monster_logic(self, a, ci):
		"""FUN_1d88_119a."""
		if ci == -1:
			if a.goal == -1:
				t = self.best_city(2 if False else 0, self.cls(a.type) == 5, a.x, a.y, -1)
				if t is not None:
					a.goal = t
					a.flags |= F_AI_MISSION
		else:
			self.join(a, ci, 1)

	def join(self, a, ci, monster):
		"""FUN_1d88_0868: send a unit from a quiet city toward a city that is attacking."""
		s = self.s
		p = self.p
		c = s.cities[ci]
		if c.ai_strong > 2 and (c.ai_target == -1 or (c.island and monster and self.cls(a.type) != 5)):
			best = -1
			for n in reversed(self.neighbours(ci)):
				nc = s.cities[n]
				if nc.owner == p and nc.ai_target != -1:
					best = n
			if best == -1:
				if not monster:
					self.hero_plan(a, ci)
			else:
				a.goal = best

	def hero_logic(self, h, ci):
		"""FUN_1d88_03a9."""
		s = self.s
		p = self.p
		if ci != -1:
			c = s.cities[ci]
			for it in s.items:
				if it.state == 1 and c.x <= it.x <= c.x + 1 and c.y <= it.y <= c.y + 1:
					it.state = 3
					it.loc = h.index
		if h.goal != -1:
			return
		if h.flags & F_AI_ERRAND:
			h.flags &= ~F_AI_ERRAND
			self.next_errand(h)
			return
		if s.turn < 15:
			k = self.ruin_search(h.x, h.y, True)
			if k is not None:
				h.goal = k + 100
				self.share_goal(h, h.goal)
				return
		if ci == -1:
			t = self.best_city(1, False, h.x, h.y, -1)
			if t is None:
				t = self.best_city(0, False, h.x, h.y, -1)
			if t is not None:
				self.share_goal(h, t)
		else:
			self.join(h, ci, 0)

	def share_goal(self, h, goal):
		"""FUN_1d88_109c."""
		s = self.s
		for a in s.live_armies():
			if a.owner == self.p and a.x == h.x and a.y == h.y and not (h.flags & F_AI_MISSION) and \
					(self.d.flyer_class[a.type] == 5 or a.type == HERO):
				a.goal = goal
		h.goal = goal

	def hero_plan(self, h, ci):
		"""FUN_1d88_0a46 (simplified where the original is unclear)."""
		s = self.s
		p = self.p
		c = s.cities[ci]
		if c.ai_target != -1:
			return
		flyers_here = [a for a in s.live_armies() if a.owner == p and not (a.flags & F_DONE) and a.goal == -1
			and self.d.flyer_class[a.type] == 5 and a.x == h.x and a.y == h.y]
		if not flyers_here:
			return
		if c.ai_strong < len([a for a in flyers_here if a.type < 10]) + 2:
			return
		goal = -1
		if not s.items_of(h):
			best = None
			bd = 10000
			for it in s.items:
				if it.state == 1:
					dd = dist(h.x, h.y, it.x, it.y)
					sc = dd + 50 - 8 * it.value
					if dd < 40 and sc < bd:
						bd = sc
						best = it.index
			if best is not None:
				goal = best + 200
			else:
				k = self.ruin_search(h.x, h.y, False)
				if k is not None:
					st = s.sites[k]
					if dist(h.x, h.y, st.x, st.y) < 40:
						goal = k + 100
		if goal == -1:
			nheroes = sum(1 for a in s.live_armies() if a.owner == p and a.type == HERO)
			if not s.surrender_offered and nheroes < 6 and s.rng.dice(1, 100, 0) <= 95:
				for o in s.cities:
					if o.owner == p and o.ai_target != -1:
						goal = o.index
						break
			if goal == -1:
				bv = 10000
				for o in s.cities:
					if o.owner == s.war[p]:
						v = self.region_str(o.index, True)[0]
						if v < bv:
							bv = v
							goal = o.index
		if goal != -1:
			self.share_goal(h, goal)

	def next_errand(self, h):
		"""FUN_1d88_1c60."""
		s = self.s
		p = self.p
		allies = [a for a in s.live_armies() if a.owner == p and 10 <= a.type <= 14 and a.x == h.x and a.y == h.y]
		dragon = any(a.type == DRAGON for a in allies)
		if not dragon and h.x < 19 and h.y < 25:
			return
		thr = 15
		if not allies or all(a.type == DRAGON for a in allies):
			thr = 30
		if dragon:
			thr = 50
		k = self.ruin_search(h.x, h.y, False)
		goal = -1
		if k is not None:
			st = s.sites[k]
			if dist(h.x, h.y, st.x, st.y) < thr:
				goal = k + 100
		if goal == -1:
			best = None
			bd = 30 if not dragon else 50
			for it in s.items:
				if it.state == 1:
					dd = dist(h.x, h.y, it.x, it.y)
					if dd < bd:
						bd = dd
						best = it.index
			if best is not None:
				goal = best + 200
		if goal != -1:
			h.goal = goal
			h.flags |= F_AI_ERRAND
			for a in allies:
				a.goal = goal

	def new_hero(self, h):
		if self.s.level[self.p] > 0:
			self.next_errand(h)

	def ruin_search(self, x, y, pref_only):
		"""FUN_1d88_12d6."""
		s = self.s
		p = self.p
		plan = s.ruin_plan[p] if s.ruin_plan[p] in (0, 1) else 0
		prefs = self.d.ai_ruin_pref[plan][p]
		best = None
		bs = None
		for k in range(40):
			st = s.sites[k]
			if s.tile(st.x, st.y) & M_EXPLORED:
				continue
			if st.type in (1, 3):
				continue
			if (k == 1 and s.gem_seer) or (k == 7 and s.gem_oracle):
				continue
			sc = dist(x, y, st.x, st.y) + 300 - s.rng.dice(1, 10, 0)
			eligible = not pref_only
			if k in prefs and k != 0:
				sc -= self.d.ai_ruin_bonus[prefs.index(k)]
				eligible = True
			if eligible and (bs is None or sc < bs):
				bs = sc
				best = k
		return best

	def explore(self, h):
		"""FUN_1d88_1803: computer hero at a site."""
		s = self.s
		g = self.g
		rng = s.rng
		st = s.site_at(h.x, h.y)
		if st is None or (s.tile(h.x, h.y) & M_EXPLORED):
			return 0
		t = st.type
		if t not in (8, 2):
			if g.ruin_fight_lost(st, h):
				g.hero_death(h, h.x, h.y)
				s.free_army(h)
				s.rebuild_army_flags()
				return 0
		if t != 2:
			s.map[h.y * MAP_W + h.x] |= M_EXPLORED
			st.type = 0
		p = self.p
		if t == 2:
			gg = rng.dice(3, 1000, 800)
			if st.index == 1:
				s.gem_seer = 1
			elif st.index == 7:
				s.gem_oracle = 1
			s.add_gold(p, gg)
		elif t == 4:
			it = s.items[st.item]
			it.state = 3
			it.loc = h.index
		elif t == 5:
			r = rng.dice(1, 2, -1)
			if h.strength + r > 9:
				h.strength = 9
			else:
				h.strength += rng.dice(1, 2, -1)
		elif t == 6:
			r = rng.dice(1, 3, -2)
			if h.strength + r > 9:
				h.strength = 9
			else:
				h.strength += rng.dice(1, 3, -2)
			h.strength = max(h.strength, 1)
		elif t == 7:
			s.add_gold(p, rng.dice(3, 1000, 500))
		elif t == 8:
			n = 2 if rng.dice(1, 3, 0) == 3 else 1
			for _ in range(n):
				if 5 <= st.monster <= 9:
					a = g.place_ally(st.monster - 5, h.x, h.y)
					if a is not None:
						a.goal = -1
						t2 = self.best_city(0, self.cls(a.type) == 5, a.x, a.y, -1)
						if t2 is not None:
							a.flags |= F_AI_MISSION
							a.goal = t2
		h.moves = 0
		h.goal = -1
		return 1

	# ==================================================================
	# movement
	# ==================================================================
	def best_city(self, mode, flyer, x, y, cur):
		"""FUN_27ed_144c. mode 1 = own cities, 2 = enemy (avoid nearby enemies), 0 = non-own."""
		s = self.s
		p = self.p
		if not flyer and x < 20 and y < 26:
			return 6
		if mode == 2:
			for a in s.live_armies():
				if a.owner != p and a.x >= 0 and abs(a.x - x) + abs(a.y - y) < 12:
					return None
		nb = self.neighbours(cur) if 0 <= cur < 80 else []
		best = None
		bs = 0
		for i in range(80):
			c = s.cities[i]
			if not flyer and i in NW_CITIES:
				continue
			if mode == 1 and c.owner != p:
				continue
			if mode in (0, 2) and c.owner == p:
				continue
			if s.tclass(c.x, c.y) != CITY:
				continue
			if s.surrender_offered and mode != 1 and not (c.owner == NEUTRAL or (c.owner < 8 and s.human[c.owner])):
				continue
			dd = dist(x, y, c.x, c.y)
			if dd >= 21 and not flyer:
				continue
			sc = 300 - (dd // 4 + self.region_str(i, True)[0])
			if i in nb:
				sc += 10
			elif not flyer and i in self.d.ai_penalty:
				sc -= 50
			if s.war[p] == c.owner:
				sc += 15
			if c.owner == NEUTRAL:
				sc += 10 if (not flyer or (x < 20 and y < 26)) else -150
			if sc > bs:
				bs = sc
				best = i
		return best

	def reevaluate(self, leader, group, origin, goal, all_flyers):
		"""FUN_27ed_0eec. Returns True if the group must not move (deleted or nothing to do)."""
		s = self.s
		p = self.p
		if s.tclass(leader.x, leader.y) == CITY:
			return False
		if origin == -1:
			origin = goal
		if not (0 <= origin < 80):
			return False
		newt = -1
		oo = self.owner(origin)
		if oo not in (NEUTRAL, p) and 0 <= goal < 80:
			gc = s.cities[goal]
			oc = s.cities[origin]
			if dist(oc.x, oc.y, leader.x, leader.y) < dist(gc.x, gc.y, leader.x, leader.y):
				newt = origin
		if newt == -1:
			if goal == -1 or goal > 79:
				return False
			if self.intact(goal):
				if all_flyers:
					return False
				if self.owner(goal) != p:
					return False
			if oo in (NEUTRAL, p):
				best = 0
				for ci in list(self.neighbours(origin)) + [origin]:
					c = s.cities[ci]
					sc = 200 - dist(leader.x, leader.y, c.x, c.y)
					if c.prev_owner == p:
						sc += 5
					if c.owner == p:
						sc = sc + 15 if c.ai_target != -1 else sc + 5
					elif c.owner == s.war[p]:
						sc += 20
					elif c.owner == NEUTRAL:
						sc = 0
					if sc > best:
						best = sc
						newt = ci
			else:
				newt = origin
		if newt == -1:
			for a in group:
				if a.type == HERO:
					a.goal = -1
				else:
					s.free_army(a)
			return True
		for a in group:
			a.goal = newt
		return False

	def ai_move(self, moved_as_group):
		"""FUN_3257_04c6 + FUN_3257_0004: move the selected group toward its goal."""
		s = self.s
		g = self.g
		p = self.p
		if s.cur_army is None:
			return 0
		cur = s.armies[s.cur_army]
		if s.group_moves < 4:
			return 0
		goal = cur.goal
		target_city = None
		site_goal = False
		if 0 <= goal < 80:
			c = s.cities[goal]
			tx, ty = c.x, c.y
			target_city = c
			if c.owner == p:
				tx, ty = tx + 1, ty + 1
			else:
				if tx < cur.x:
					tx += 1
				if ty < cur.y:
					ty += 1
		elif 100 <= goal < 200:
			st = s.sites[goal - 100]
			tx, ty = st.x, st.y
			site_goal = True
		elif 200 <= goal < 214:
			it = s.items[goal - 200]
			tx, ty = it.x, it.y
			site_goal = True
		else:
			return 0
		res, nx, ny = self.step_path(tx, ty, agg=1 if moved_as_group else 0)
		group = g.selected()
		if res == 4:
			t = self.nearest_nonneutral(cur.x, cur.y)
			for a in group:
				a.goal = t
			return 0
		if not site_goal and target_city is not None and target_city.owner != p and res == 1:
			res = 2
		if res == 1:
			if site_goal and s.cur_hero is not None:
				self.explore(s.armies[s.cur_hero])
			for a in group:
				if a.owner != 0xff:
					a.origin = -1
					a.goal = -1
			return 1
		if res == 2:
			if site_goal:
				if s.cur_hero is not None:
					self.explore(s.armies[s.cur_hero])
				return 1
			if s.group_moves > 1 and s.on_map(nx, ny) and s.tclass(nx, ny) == CITY and target_city is not None:
				if target_city.owner == NEUTRAL:
					self.assault_neutral(nx, ny)
				elif target_city.owner != p:
					if not self.gate_decision(cur, group):
						return 1
					self.attack(nx, ny)
				for a in g.selected():
					if a.owner != 0xff:
						a.origin = -1
						a.goal = -1
			return 1
		if res == 5:
			self.attack(nx, ny)
			return 1
		return 1

	def step_path(self, tx, ty, agg=0):
		"""FUN_3257_0004. Returns (code, next_x, next_y): 1 arrived, 2 adjacent/blocked by city,
		3 stopped, 4 no path, 5 enemy army in the way."""
		s = self.s
		g = self.g
		p = self.p
		cur = s.armies[s.cur_army]
		path = g.pf.find(cur.x, cur.y, tx, ty, s.gcost, p, agg=agg)
		nx, ny = cur.x, cur.y
		if not path:
			dd = dist(tx, ty, cur.x, cur.y)
			if dd == 0:
				return 1, nx, ny
			if dd == 1:
				return 2, nx, ny
			return 4, nx, ny
		for i, d in enumerate(path + [0xff]):
			if d == 0xff or i > 49:
				if (cur.x, cur.y) == (tx, ty):
					return 1, nx, ny
				return (3 if dist(tx, ty, cur.x, cur.y) > 1 else 2), nx, ny
			ox, oy = cur.x, cur.y
			if s.cur_hero is not None:
				self.pick_up(s.armies[s.cur_hero])
			from .gamedata import DX, DY
			nx, ny = cur.x + DX[d], cur.y + DY[d]
			if not s.on_map(nx, ny):
				return 3, nx, ny
			w = s.tile(nx, ny)
			cls = s.data.terrain_class[w & 0x7f]
			own = (w >> 7) & 0xf
			cost = s.gcost[cls]
			if s.group_moves < cost:
				return (1 if (nx, ny) == (tx, ty) else 3), nx, ny
			if own != p and cls == CITY:
				return 2, nx, ny
			if own != p and (w & M_ARMY):
				return 5, nx, ny
			if s.count_at(nx, ny) + s.group_count > 8:
				return 3, nx, ny
			s.group_moves = max(0, s.group_moves - cost)
			g.capture_towers(nx, ny)
			movers = g.selected()
			for m in movers:
				m.moves = max(0, m.moves - cost)
				m.x, m.y = nx, ny
			i2 = ny * MAP_W + nx
			s.map[i2] = (s.map[i2] & 0xf87f) | (p << 7) | M_ARMY
			if s.count_at(ox, oy) == 0:
				s.map[oy * MAP_W + ox] &= 0xf7ff
			g.ui.army_moved(g, movers, ox, oy, nx, ny)
			if s.group_moves == 0:
				return 3, nx, ny
		return 3, nx, ny

	def attack(self, tx, ty):
		"""FUN_2289_119e: computer attack on a tile with enemies or an enemy city."""
		s = self.s
		g = self.g
		p = self.p
		group = g.selected()
		if not group:
			return
		w = s.tile(tx, ty)
		defender = (w >> 7) & 0xf
		b = g.battle_setup(tx, ty, group)
		for a in group:
			a.x, a.y = tx, ty
			a.moves = max(0, a.moves - 2)
		s.group_moves -= 2
		show = (defender < 8 and s.human[defender]) or g.ui.show_moves(g, p)
		dname = g.clan_name(defender)
		g.battle_resolve(b)
		if show:
			g.ui.battle(g, b, "%s: you are being attacked!" % dname)
		s.rebuild_army_flags()
		if show:
			if b.result == 0:
				g.ui.status("%s: you are victorious!" % dname)
			elif s.cur_hero is not None and s.armies[s.cur_hero].owner == p:
				g.ui.status("%s has won the battle!" % s.hero_name(s.armies[s.cur_hero]))
			else:
				g.ui.status("%s: you have lost!" % dname)
		g.battle_aftermath(b)
		if b.result == 1:
			s.map[ty * MAP_W + tx] |= M_ARMY
		alive = [a for a in group if a.owner == p]
		s.group = [a.index for a in alive]
		s.cur_army = alive[0].index if alive else None
		if not alive:
			s.cur_hero = None

	def assault_neutral(self, tx, ty):
		"""FUN_2491_0341."""
		s = self.s
		g = self.g
		group = g.selected()
		if not group:
			return
		for a in group:
			a.x, a.y = tx, ty
			a.moves = max(0, a.moves - 2)
		s.group_moves -= 2
		g.neutral_assault(tx, ty, human=False, attackers=group)
		alive = [a for a in group if a.owner == self.p]
		s.group = [a.index for a in alive]
		s.cur_army = alive[0].index if alive else None

	def move_all(self):
		"""FUN_27ed_0a3e."""
		s = self.s
		g = self.g
		p = self.p
		pss = 0
		guard = 0
		while True:
			guard += 1
			if guard > 3000:
				break
			goal = None
			group = []
			for i in range(s.count - 1, -1, -1):
				a = s.armies[i]
				if a.owner != p or a.x == -1:
					continue
				if a.goal == -1 and a.type < 10 and s.tclass(a.x, a.y) != CITY:
					t = self.best_city(1, False, a.x, a.y, -1)
					if t is not None:
						a.goal = t
				if not (a.flags & F_DONE) and a.goal != -1 and (pss != 0 or not (a.flags & F_AI_GROUP)):
					if goal is None:
						goal = a.goal
						origin = a.origin
						lx, ly = a.x, a.y
						group.append(a)
					elif a.goal == goal and a.x == lx and a.y == ly:
						group.append(a)
						if len(group) == 8:
							break
			if not group:
				if pss != 0:
					return
				pss = 1
				continue
			leader = group[0]
			s.group = [a.index for a in group]
			s.cur_army = leader.index
			s.cur_hero = None
			for a in group:
				if a.type == HERO:
					s.cur_hero = a.index
			all_flyers = all(self.d.flyer_class[a.type] == 5 for a in group if a.type < 10)
			if self.reevaluate(leader, group, origin, goal, all_flyers):
				continue
			s.group_mode = 1 if len(group) > 1 else 0
			x0, y0 = leader.x, leader.y
			mv0 = [a.moves for a in group]
			moved_as_group = any(a.flags & F_AI_GROUP for a in group)
			g.compute_group()
			if s.group_mode == 0:
				s.group_moves = leader.moves
			if self.goal_done(leader.goal):
				for a in group:
					a.goal = -1
				res = 1
			else:
				res = self.ai_move(moved_as_group)
			if s.group_mode == 0 and s.cur_army is not None:
				cur = s.armies[s.cur_army]
				if cur.owner == p and (cur.flags & F_AI_MISSION) and cur.goal == -1:
					for _ in range(10):
						mv = cur.moves
						if cur.goal == -1:
							t = self.best_city(2, self.cls(cur.type) == 5, cur.x, cur.y, -1)
							if t is None:
								cur.flags &= ~F_AI_MISSION
								break
							cur.goal = t
						g.compute_group()
						s.group_moves = cur.moves
						self.ai_move(moved_as_group)
						if s.cur_army is None or cur.owner != p:
							break
						if cur.moves == mv or cur.moves == 0:
							break
			stuck = True
			for a, m0 in zip(group, mv0):
				if a.owner != p:
					continue
				if a.x == x0 and a.y == y0:
					if not (a.flags & F_AI_GROUP):
						res = 1
					a.flags |= F_AI_GROUP
				else:
					a.flags &= ~F_AI_GROUP
				if a.moves != m0 or (a.x, a.y) != (x0, y0):
					stuck = False
			if res == 0 or stuck:
				for a in group:
					if a.owner == p:
						a.flags |= F_DONE
			g.deselect()

	# ==================================================================
	# main (FUN_27ed_0006)
	# ==================================================================
	def main(self, p):
		s = self.s
		g = self.g
		lvl = s.level[p]
		self.cls_table = list(self.d.ai_class_warlord if lvl == 3 else self.d.ai_class_normal)
		self.truce()
		if not any(s.players[q].razer for q in range(8) if s.alive[q] and not s.human[q]):
			s.players[s.rng.dice(1, 8, -1) & 7].razer = 1
		if sum(1 for q in range(8) if s.alive[q]) < 2:
			for q in range(8):
				s.human[q] = 1
			return
		pl = s.players[p]
		heroes = sum(1 for a in s.live_armies() if a.owner == p and a.type == HERO)
		if s.ncities[p] >= 4 and pl.gold < 500:
			if heroes == 0 or (heroes == 1 and s.rng.dice(1, 8, -1) == 0):
				pl.thrift = min(3, pl.thrift + 1)
		if pl.gold > 1000:
			pl.thrift = 0
		if pl.gold < self.d.ai_thrift_gold[max(0, min(3, pl.thrift))] and s.income[p] < s.upkeep[p] + 20:
			pl.thrift = min(3, pl.thrift + 1)
		self.move_all()
		s.ai_state = [-1] * 80
		expanding = 0
		for c in s.cities:
			if c.owner == p:
				expanding += self.expand(c)
		nDef = nAtk = nAtkGround = 0
		for ci in range(79, -1, -1):
			c = s.cities[ci]
			if c.owner != p or s.ai_state[ci] == 0:
				continue
			if c.ai_target != -1 and self.owner(c.ai_target) == p:
				c.ai_target = -1
			mode = 5 if c.ai_target != -1 else (4 if c.vector else 3)
			ok, mode = self.organise(c, mode)
			s.ai_state[ci] = mode if ok else -1
			if mode >= 5:
				nAtk += 1
				if c.ai_type < 0 or self.cls(c.ai_type) == 0:
					nAtkGround += 1
			if mode in (3, 4):
				nDef += 1
		want = (nDef > expanding) or (expanding == 0 and nAtk == 0)
		if pl.gold < 200 and s.ncities[p] > 3:
			want = False
		if pl.gold < self.d.ai_attack_gold[min(nAtk, 6)]:
			want = False
		if nAtk >= self.d.ai_max_attacks[max(0, min(3, lvl))]:
			want = False
		if lvl == 3 and s.ncities[p] // 4 < nAtkGround:
			want = False
		if want:
			r = self.choose_target()
			if r is not None:
				src, tgt = r
				sc = s.cities[src]
				sc.ai_target = tgt
				s.ai_state[src] = 5
				self.pick_attack_type(sc, -1)
		self.launch()
		for ci in range(79, -1, -1):
			c = s.cities[ci]
			if c.owner != p or c.turns > 0:
				continue
			st = s.ai_state[ci]
			if st in (0, 1):
				self.build_fast(c)
			elif st == 2:
				self.build_best(c, -1)
			elif st in (3, 4):
				if pl.gold >= 50:
					self.build_for_front(c)
			elif st in (5, 6):
				self.build_attack(c, -1)
		if lvl != 0:
			self.heroes_and_monsters()
		self.move_all()
		for ci in range(79, -1, -1):
			c = s.cities[ci]
			if c.owner != p:
				continue
			empty = not any(s.tile(c.x + CITY_DX[k], c.y + CITY_DY[k]) & M_ARMY for k in range(4))
			busy = c.turns > 0
			fastest = self._fastest_slot(c)
			if (not busy and (s.turn < 10 or empty)) or (busy and empty and fastest != c.prod):
				self.build_fast(c)
		g.deselect()

	def _fastest_slot(self, c):
		best = None
		for t in range(10):
			if not c.can[t] or t == NAVY:
				continue
			if c.island and self.cls(t) != 5:
				continue
			if best is None or c.time[t] < c.time[best] or (c.time[t] == c.time[best] and c.strength[t] > c.strength[best]):
				best = t
		return best
