"""Random-input smoke test of the pygame UI (headless)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.environ.get('WARLORDS_DATA') or os.path.join(ROOT, '..', 'warlords')
OUT = os.environ.get('WARLORDS_OUT', '.')
import os, sys, random, time, traceback, asyncio
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('WARLORDS_NOSOUND', '1')
import pygame
from warlords.gamedata import GameData
from warlords.ui.game_ui import GameUI, QuitGame, MENUS

class Fuzz:
    def __init__(self, ui, n, seed):
        self.ui = ui; self.n = n; self.r = random.Random(seed); self.count = 0
        self.orig = ui.events
        self.cmds = [it[1] for m in MENUS for it in m[2] if it and it[1] not in ('quit', 'load', 'save', 'about')]
    def __call__(self):
        self.orig()
        self.count += 1
        if self.count > self.n:
            raise QuitGame()
        r = self.r
        k = r.random()
        if k < 0.35:
            x, y = r.randrange(8, 368), r.randrange(5, 165)
            self.ui.scr.mouse = (x, y)
            return [('down', (x, y), 1), ('up', (x, y), 1)]
        if k < 0.45:
            x, y = r.randrange(0, 640), r.randrange(0, 200)
            self.ui.scr.mouse = (x, y)
            return [('down', (x, y), 1), ('up', (x, y), 1)]
        if k < 0.55:
            return [('key', pygame.K_n, 0, 'n')]
        if k < 0.6:
            return [('key', pygame.K_RETURN, 0, '\r')]
        if k < 0.65:
            return [('key', pygame.K_ESCAPE, 0, '')]
        if k < 0.72:
            cmd = r.choice(self.cmds)
            if getattr(self.ui, 'game', None) and hasattr(self.ui, 'end_turn'):
                return [('callback', lambda: self.ui.command(cmd))]
            return []
        if k < 0.75:
            return [('key', pygame.K_e, pygame.KMOD_ALT, 'e')]
        if k < 0.8:
            return [('key', r.choice([pygame.K_KP8, pygame.K_KP2, pygame.K_KP4, pygame.K_KP6]), 0, '')]
        return []

def main(n=4000, seed=1, quick=True):
    data = GameData(DATA)
    ui = GameUI(data, scale=1, seed=seed)
    ui.delay_scale = 0.0
    fz = Fuzz(ui, n, seed)
    ui.events = fz
    t0 = time.time()
    try:
        asyncio.run(ui.run(quick=([1,0,0,1,0,0,0,0], [1,2,3,0,1,2,3,1]) if quick else None))
    finally:
        g = ui.game
        print('events', fz.count, 'turn', g.s.turn if g else None, 'time %.1f' % (time.time()-t0))

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
