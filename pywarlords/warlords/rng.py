"""Random numbers exactly as the original game generates them.

Warlords was compiled with Microsoft C 5.x; rand() is the classic LCG
    seed = seed * 0x343FD + 0x269EC3;  return (seed >> 16) & 0x7FFF
and the game's own helper (FUN_1b90_0026) rolls n dice of `sides` faces:
    plus + sum(int(rand() / 32767.0 * sides + 1.0))
Note the original quirk: rand() == 32767 yields sides + 1.
"""
import math
import time


class MSRand:

	def __init__(self, seed=None):
		if seed is None:
			seed = int(time.time()) & 0xFFFF
		self.seed = seed & 0xFFFFFFFF

	def srand(self, seed):
		self.seed = seed & 0xFFFFFFFF

	def rand(self):
		self.seed = (self.seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF
		return (self.seed >> 16) & 0x7FFF

	def dice(self, n, sides, plus=0):
		"""n dice with `sides` faces plus a constant (FUN_1b90_0026)."""
		if sides == 0:
			return plus
		total = 0
		for _ in range(n):
			total += int(self.rand() / 32767.0 * sides + 1.0)
		return total + plus


def dist(x1, y1, x2, y2):
	"""Integer Euclidean distance (FUN_3257_1b8f)."""
	s = (x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2)
	if s > 0x7FFFFFFF:
		return 10000
	return int(math.sqrt(s))
