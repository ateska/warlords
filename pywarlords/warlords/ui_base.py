"""Interface between the rules engine and a front-end.

The engine is written like the original program: sequential code that calls
modal dialogs and waits for the answer. A front-end implements these hooks
(the pygame UI runs a nested event loop inside each call). The defaults here
answer automatically, which is what a headless game (tests, AI-only runs)
needs.
"""


class UIBase:

	headless = True

	def __init__(self):
		self.log = []

	# --- messages / pictures -------------------------------------------
	async def message(self, text, wait=True):
		"""Modal message in the bottom bar (FUN_1312_2016)."""
		self.log.append(text)

	async def status(self, text):
		"""Non modal status line (e.g. 'Lord Bane is moving!')."""
		self.log.append(text)

	async def picture(self, name, lines=()):
		"""Full screen picture: 'raze', 'beg', 'head', 'war'..."""
		for ln in lines:
			self.log.append(ln)

	# --- questions -----------------------------------------------------
	async def ask(self, lines, buttons, default=0):
		"""Generic modal dialog, returns the index of the chosen button."""
		self.log.append(" / ".join(lines))
		return default

	async def hero_offer(self, city_name, price, gold):
		return price + 0 <= gold

	async def name_hero(self, default):
		return default

	async def production_report(self, text, city=None):
		"""'<unit> - Produced!' / 'Keep producing these?'. Returns 'yes', 'no' or 'end'."""
		self.log.append(text)
		return 'yes'

	async def city_production(self, game, city, captured=False):
		"""Open the city production dialog (turn 1 / city captured)."""
		pass

	async def choose(self, title, options):
		"""Choose one entry from a list; returns index or None."""
		return 0 if options else None

	# --- turn control --------------------------------------------------
	async def human_turn(self, game, player):
		"""Run the interactive turn of a human player. Return when the player ends the turn.
		May return 'quit' to stop the game."""
		return 'end'

	async def ai_turn_start(self, game, player):
		await self.status("%s %s moving!" % (game.clan_name(player), "is" if player in (4, 7) else "are"))

	def ai_turn_end(self, game, player):
		pass

	def show_moves(self, game, player):
		"""True if the moves of this computer player should be drawn (Observe)."""
		return False

	async def army_moved(self, game, armies, x0, y0, x1, y1):
		pass

	async def battle(self, game, info, caption=None):
		"""Show a battle; info is a combat.Battle with the full round log."""
		pass

	async def play_sound(self, name, sync=True, fallback_ms=0):
		"""Digitised sound: 'war', 'drumroll', 'dramatic', 'horn'."""
		pass

	def beep(self):
		pass

	def refresh(self, game):
		pass

	async def game_over(self, game, lines):
		for ln in lines:
			self.log.append(ln)
