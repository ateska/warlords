"""The original Warlords path finder (FUN_3257_0957 and helpers).

A greedy line follower with a reverse search, 37 fixed waypoints and a
smoothing pass. It is deliberately "dumb" exactly like the original, and it
consumes the shared random number generator (one dice(1,8,-1) roll when it has
to pick a random direction), so it must be called in the same order as in the
DOS game to keep the RNG stream identical.
"""
from .gamedata import DX, DY, MAP_W, MAP_H, CITY, IMPASSABLE
from .rng import dist

END = 0xff


def dirto(x, y, tx, ty):
	"""FUN_3257_1c15."""
	if x == tx and y == ty:
		return END
	if x == tx:
		return 0 if ty < y else 4
	if y == ty:
		return 6 if tx < x else 2
	if tx < x:
		return 7 if ty < y else 5
	return 1 if ty < y else 3


class PathFinder:

	def __init__(self, game):
		self.g = game

	def find(self, sx, sy, tx, ty, cost_table, player, board=False, agg=0):
		"""Return a list of directions (0..7), at most 50 long."""
		s = self.g.s
		self.map = s.map
		self.tclass = s.data.terrain_class
		self.rng = s.rng
		self.P = player
		self.SRC = (sx, sy)
		self.DST = (tx, ty)
		self.BOARD = board
		self.PC = list(cost_table)
		self.AGG = agg
		self.RESULT = [END] * 50
		self.BEST = 0
		self.A440 = END
		self.A43A = 0
		self.A43E = 0
		self.A4C2 = dist(sx, sy, tx, ty)
		self.A4C6 = 1 if self._cls(tx, ty) == CITY else 0
		if (sx, sy) == (tx, ty):
			return []
		self.A43E = 0
		self.BEST = 0
		self.A43A = 1
		self._search(self.SRC, self.DST)
		found = self._accept(0)
		self.A43A = 0
		self._search(self.SRC, self.DST)
		found |= self._accept(0)
		if (sx < 20 and sy < 26) or (tx < 20 and ty < 26):
			found += 1
		if not found:
			self._pick_waypoints()
		self.A43A = 1
		k = 0
		while not found:
			wp = self.W[k]
			if wp != END and (self.F[k] == 0 or self.RESULT[0] == END):
				self.A43E = 4
				self._search(self.g.data.waypoints[wp], self.DST)
				if self.C[0] != END:
					save, s_steps, s_cost = list(self.C), self.Csteps, self.Ccost
					self.A43E = 20
					self._search(self.SRC, self.g.data.waypoints[wp])
					if self.C[0] != END:
						self.Csteps += s_steps
						self.Ccost += s_cost
						j = 0
						for i in range(50):
							if self.C[i] == END:
								self.C[i] = save[j]
								j += 1
						found = self._accept(1)
			if self.A43A == 0:
				k += 1
				self.A43A = 1
			else:
				self.A43A = 0
			if k >= 8:
				found += 1
		self._smooth(self.RESULT)
		res = []
		for d in self.RESULT:
			if d == END:
				break
			res.append(d)
		return res

	# ------------------------------------------------------------------
	def _cls(self, x, y):
		return self.tclass[self.map[y * MAP_W + x] & 0x7f]

	def _owner(self, x, y):
		return (self.map[y * MAP_W + x] >> 7) & 0xf

	def _scan(self, x, y):
		nb = []
		for d in range(9):
			nx, ny = x + DX[d], y + DY[d]
			if 0 <= nx < MAP_W and 0 <= ny < MAP_H:
				nb.append(self.tclass[self.map[ny * MAP_W + nx] & 0x7f])
			else:
				nb.append(END)
		return nb

	def _choose(self, x, y):
		"""FUN_3257_158b."""
		NB = self._scan(x, y)
		PC = self.PC
		a = self.A4A8
		av = [1] * 8
		if (x, y) == self.SRC:
			for d in range(7, -1, -1):
				if NB[d] == CITY and self.A4C2 > 3 and self._owner(x + DX[d], y + DY[d]) != self.P:
					av[d] = 0
		for d in range(7, -1, -1):
			if NB[d] in (1, 2, 3) and (x + DX[d], y + DY[d]) == self.DST and self.BOARD:
				continue
			if NB[d] == END or PC[NB[d]] == IMPASSABLE:
				av[d] = 0
		lazy = False
		ds = dd = 0
		for d in range(7, -1, -1):
			if self.AGG or NB[d] == CITY:
				if NB[d] == END:
					continue
				if not lazy:
					ds = dist(self.SRC[0], self.SRC[1], x, y)
					dd = dist(self.DST[0], self.DST[1], x, y) if self.A4C6 else 100
					lazy = True
				thr = 1 if self.AGG else 2
				nx, ny = x + DX[d], y + DY[d]
				if (thr < self.A4C2 and ds < 3 and self.map[ny * MAP_W + nx] & 0x800) or \
						(dd > 3 and not self.AGG and self._owner(nx, ny) != self.P):
					av[d] = 0
		prev = self.A440
		sa = av[prev] if prev != END else 0
		sb = av[a]
		for b in (a, prev):
			if b != END:
				av[(b + 3) & 7] = av[(b + 4) & 7] = av[(b + 5) & 7] = 0
		if prev != END:
			av[prev] = sa
		av[a] = sb
		if not any(av):
			self.A354 = END
			return
		if self.A43A and self.A4C0 > 1:
			m = 0x7fff
			for d in range(7, -1, -1):
				if av[d] and NB[d] != END and PC[NB[d]] < m and NB[d] != CITY and self.A4C0 > 2:
					m = PC[NB[d]]
			keep = [d for d in range(8) if av[d] and NB[d] != END and PC[NB[d]] == m]
			if keep:
				av = [1 if d in keep else 0 for d in range(8)]
		for k in (0, 1, 7, 2, 6):
			if av[(a + k) & 7]:
				ch = (a + k) & 7
				break
		else:
			n = self.rng.dice(1, 8, -1) + 1
			ch = 0
			guard = 0
			while n:
				ch = (ch + 1) & 7
				if av[ch]:
					n -= 1
				guard += 1
				if guard > 100:
					break
		self.A354 = ch
		self.A440 = ch

	def _walk(self, x, y, tx, ty, reverse):
		"""FUN_3257_12ad. Returns (ok, B, steps, cost)."""
		d0 = dist(x, y, tx, ty)
		ox, oy = x, y
		B = [END] * 50
		retries = 2
		cost = 0
		steps = 0
		self.A440 = END
		budget = d0 + (d0 >> 2) + 4
		if budget < 10:
			budget = 10
		if self.RESULT[0] == END:
			budget += self.A43E
		while True:
			d = dist(x, y, tx, ty)
			self.A4C0 = d
			if d == 0:
				return True, B, steps, cost
			self.A4A8 = dirto(x, y, tx, ty)
			if d == 1:
				self.A440 = END
			while True:
				self._choose(x, y)
				if self.A354 != END:
					break
				if retries == 0:
					return False, B, steps, cost
				self.A440 = END
				retries -= 1
			nx, ny = x + DX[self.A354], y + DY[self.A354]
			if not (nx < 0 or ny < 0 or nx == MAP_W or ny == MAP_H):
				x, y = nx, ny
			steps += 1
			budget -= 1
			cost += self.PC[self._cls(x, y)]
			if (budget & 0xffff) < d:
				return False, B, steps, cost
			if (x, y) == (ox, oy):
				return False, B, steps, cost
			if reverse:
				B = [(self.A354 + 4) & 7] + B[:49]
			elif steps - 1 < 50:
				B[steps - 1] = self.A354

	def _search(self, a, b):
		"""FUN_3257_1160."""
		self.C = [END] * 50
		self.Ccost = 0x7fff
		self.Csteps = 0
		ok, B, steps, cost = self._walk(a[0], a[1], b[0], b[1], False)
		if ok:
			self.C, self.Csteps, self.Ccost = B, steps, cost
		ok, B, steps, cost = self._walk(b[0], b[1], a[0], a[1], True)
		if ok and (self.C[0] == END or cost < self.Ccost):
			self.C, self.Csteps, self.Ccost = B, steps, cost

	def _accept(self, p):
		"""FUN_3257_0e49."""
		if self.C[0] == END:
			return 0
		if self.RESULT[0] == END or (self.Ccost & 0xffff) < (self.BEST & 0xffff):
			self.BEST = self.Ccost
			self.RESULT = list(self.C)
			return 0 if (2 * self.A4C2 < self.BEST and p == 0) else 1
		return 0

	def _pick_waypoints(self):
		"""FUN_3257_0ee5."""
		WP = self.g.data.waypoints
		sx, sy = self.SRC
		tx, ty = self.DST
		D = dist(tx, ty, sx, sy)
		self.W = [END] * 8
		self.F = [0] * 8
		score = [END] * 37
		far = [0] * 37
		for i in range(36, -1, -1):
			px, py = WP[i]
			if self.PC[self._cls(px, py)] != IMPASSABLE and (px, py) != self.SRC and (px, py) != self.DST:
				s = dist(px, py, sx, sy) + dist(px, py, tx, ty)
				score[i] = s
				if s >= D + 10:
					far[i] = 1
		for k in range(8):
			best = END
			bs = 10000
			for i in range(36, -1, -1):
				if score[i] != END and score[i] < bs:
					bs = score[i]
					best = i
			if best == END:
				break
			self.W[k] = best
			self.F[k] = 1 if (far[best] or k > 4) else 0
			score[best] = END

	def _smooth(self, P):
		"""FUN_3257_0ce0."""
		rules = self.g.data.smooth_rules
		i = 0
		while not (P[i] == END or i + 2 > 49):
			r = rules.get((P[i], P[i + 1]))
			if r is None:
				i += 1
				continue
			if r == END:
				del P[i:i + 2]
				P.extend([END, END])
			else:
				P[i] = r
				del P[i + 1]
				P.append(END)
			i = 0
