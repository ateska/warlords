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

try:
	import numpy as np
	import pygame
except ImportError:          # pragma: no cover
	np = None
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
			self.rate, self.chans = freq, chans
			self.ok = True
		except Exception:
			self.ok = False

	# ------------------------------------------------------------------
	def _make(self, mono):
		"""float array -1..1 at self.rate -> pygame Sound."""
		a = np.clip(mono * VOLUME, -1, 1)
		a = (a * 32767).astype(np.int16)
		if self.chans > 1:
			a = np.repeat(a[:, None], self.chans, axis=1)
		return pygame.sndarray.make_sound(np.ascontiguousarray(a))

	def _load(self, name):
		if name in self.cache:
			return self.cache[name]
		snd = None
		try:
			if name == 'beep':
				n = int(self.rate * 2 / 18.2)
				t = np.arange(n) / self.rate
				wave = np.where((t * 220.0) % 1.0 < 0.5, 0.35, -0.35)
				snd = self._make(wave)
			else:
				fname, src_rate = SAMPLES[name]
				path = find_file(self.game_dir, fname)
				if path:
					raw = np.frombuffer(open(path, 'rb').read(), np.uint8)[48:]
					if len(raw) and raw[-1] == 0x1a:
						raw = raw[:-1]
					# drop the silent tail so a synchronous play ends with the sound
					loud = np.nonzero(np.abs(raw.astype(np.int16) - 35) > 3)[0]
					if len(loud):
						raw = raw[:min(len(raw), loud[-1] + src_rate // 20)]
					x = (raw.astype(np.float32) - 35.0) / 36.0
					x -= x.mean()
					# resample (linear) and a gentle low pass, like the speaker cone
					n = int(len(x) * self.rate / src_rate)
					y = np.interp(np.arange(n) * (src_rate / self.rate), np.arange(len(x)), x)
					k = np.ones(3, np.float32) / 3
					y = np.convolve(y, k, mode='same')
					snd = self._make(y * 1.6)
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
