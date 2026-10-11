"""Sound effects.

The original only has PC speaker sound (WARLORDS.EXE 1fac:00f8, 1fe3:00a9..0139, 3952:*):

* five digitised samples, ``*.SJH``: one byte per sample, the value is the pulse width (in PIT
  ticks, 0..70 around a centre of 35) of a 72 tick PWM period. The timer interrupt runs at
  1193182/72 Hz and the player routine outputs a sample every 2nd tick (8286 Hz) or, for
  ``HORN.SJH``, every 3rd tick (5524 Hz). The 48 byte header and the trailing ^Z are skipped here.
  Sound numbers: 0 WAR (battle, razing), 1 DRUMROLL (new game started), 2 DRAMATIC (ruin
  search), 3 HORN (title, victory), 4 RING (unused).
* a short beep from the little music driver (tune at DS:0x89fe: note 'B' = 220 Hz for two
  18.2 Hz ticks), used for invalid input and for every hit in a battle.

Everything here is optional: without an audio device the game runs silently.
"""

import os
import sys
from array import array

try:
	import pygame
except ImportError:          # pragma: no cover
	pygame = None

from ..gamedata import find_file

SAMPLES = {
	'war': ('WAR.SJH', 8286),
	'drumroll': ('DRUMROLL.SJH', 8286),
	'dramatic': ('DRAMATIC.SJH', 8286),
	'horn': ('HORN.SJH', 5524),
	'ring': ('RING.SJH', 8286),
}

RATE = 22050
VOLUME = 0.45


class Sound:

	def __init__(self, game_dir, enabled=True):
		self.enabled = enabled
		self.ok = False
		self.cache = {}
		self.game_dir = game_dir
		self.channel = None
		if not enabled or pygame is None or os.environ.get('WARLORDS_NOSOUND'):
			return
		try:
			if not pygame.mixer.get_init():
				pygame.mixer.pre_init(RATE, -16, 1, 512)
				pygame.mixer.init(RATE, -16, 1, 512)
			freq, size, chans = pygame.mixer.get_init()
			self.rate, self.size, self.chans = freq, size, chans
			self.ok = True
		except Exception:
			self.ok = False

	# ------------------------------------------------------------------
	def _make(self, mono):
		"""list of floats -1..1 at self.rate -> pygame Sound in the mixer's sample format."""
		v = VOLUME
		vals = [max(-1.0, min(1.0, x * v)) for x in mono]
		if self.chans > 1:
			vals = [x for x in vals for _ in range(self.chans)]
		size = self.size
		if size == -16:
			buf = array('h', [int(x * 32767) for x in vals])
		elif size == 16:
			buf = array('H', [int(x * 32767) + 32768 for x in vals])
		elif size == 32:
			buf = array('f', vals)
		elif size == -8:
			buf = array('b', [int(x * 127) for x in vals])
		else:
			buf = array('B', [int(x * 127) + 128 for x in vals])
		return pygame.mixer.Sound(buffer=buf.tobytes())

	def _load(self, name):
		if name in self.cache:
			return self.cache[name]
		snd = None
		try:
			if name == 'beep':
				n = int(self.rate * 2 / 18.2)
				period = self.rate / 220.0
				snd = self._make([0.35 if (i % period) < period / 2 else -0.35 for i in range(n)])
			else:
				fname, src_rate = SAMPLES[name]
				path = find_file(self.game_dir, fname)
				if path:
					raw = open(path, 'rb').read()[48:]
					if raw and raw[-1] == 0x1a:
						raw = raw[:-1]
					# drop the silent tail so a synchronous play ends with the sound
					last = max((i for i, b in enumerate(raw) if abs(b - 35) > 3), default=len(raw) - 1)
					raw = raw[:min(len(raw), last + src_rate // 20)]
					mean = sum(raw) / float(len(raw))
					x = [(b - mean) / 36.0 for b in raw]
					# linear resampling and a 3 tap box filter (the speaker cone was no better)
					n = int(len(x) * self.rate / src_rate)
					step = src_rate / float(self.rate)
					last_i = len(x) - 1
					y = []
					for i in range(n):
						p = i * step
						j = int(p)
						f = p - j
						a = x[j]
						b = x[j + 1] if j < last_i else a
						y.append(a + (b - a) * f)
					z = [(y[max(i - 1, 0)] + y[i] + y[min(i + 1, n - 1)]) * (1.6 / 3) for i in range(n)]
					snd = self._make(z)
		except Exception:
			snd = None
		self.cache[name] = snd
		return snd

	def play(self, name, wait=False):
		if not (self.ok and self.enabled):
			return 0
		snd = self._load(name)
		if snd is None:
			return 0
		try:
			if name == 'beep':
				snd.play()
			else:
				# the original plays the samples synchronously, one at a time
				if self.channel is not None:
					self.channel.stop()
				self.channel = snd.play()
			return snd.get_length()
		except Exception:
			return 0

	def busy(self):
		return bool(self.ok and self.channel is not None and self.channel.get_busy())

	def stop(self):
		if self.ok:
			try:
				pygame.mixer.stop()
			except Exception:
				pass
