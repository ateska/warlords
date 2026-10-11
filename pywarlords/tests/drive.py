"""Drive the pygame UI with a scripted list of events (headless) and take screenshots."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.environ.get('WARLORDS_DATA') or os.path.join(ROOT, '..', 'warlords')
OUT = os.environ.get('WARLORDS_OUT', '.')
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('WARLORDS_NOSOUND', '1')
import asyncio
import pygame
from warlords.gamedata import GameData
from warlords.ui import game_ui
from warlords.ui.game_ui import GameUI, QuitGame

class Driver:
    def __init__(self, ui, script, prefix='d'):
        self.ui = ui; self.script = list(script); self.prefix = prefix; self.idle = 0
        self.orig_events = ui.events
    def __call__(self):
        self.ui.events_orig = self.orig_events
        self.orig_events()  # keep pygame happy
        if not self.script:
            raise QuitGame()
        item = self.script.pop(0)
        kind = item[0]
        if kind == 'shot':
            self.ui.scr.present()
            big = pygame.transform.scale(self.ui.scr.surface, (640, 400))
            # draw cursor
            c = self.ui.scr._cursors.get(self.ui.scr.cursor)
            if c:
                img, hot = c
                tmp = self.ui.scr.surface.copy(); tmp.blit(img, (self.ui.scr.mouse[0]-hot[0], self.ui.scr.mouse[1]-hot[1]))
                big = pygame.transform.scale(tmp, (640, 400))
            pygame.image.save(big, os.path.join(OUT, '%s_%s.png' % (self.prefix, item[1])))
            return []
        if kind == 'click':
            x, y = item[1], item[2]; b = item[3] if len(item) > 3 else 1
            self.ui.scr.mouse = (x, y)
            self.script.insert(0, ('raw', [('up', (x, y), b)]))
            return [('motion', (x, y), (0, 0, 0)), ('down', (x, y), b)]
        if kind == 'move':
            self.ui.scr.mouse = (item[1], item[2])
            return [('motion', (item[1], item[2]), (0, 0, 0))]
        if kind == 'raw':
            return item[1]
        if kind == 'key':
            k = item[1]; mod = item[2] if len(item) > 2 else 0; uni = item[3] if len(item) > 3 else ''
            return [('key', k, mod, uni)]
        if kind == 'idle':
            n = item[1]
            if n > 1:
                self.script.insert(0, ('idle', n - 1))
            return []
        if kind == 'call':
            r = item[1](self.ui)
            if asyncio.iscoroutine(r):
                return [('callback', lambda: r)]
            return []
        return []

def run(script, prefix='d', setup=None, quick=None, load=None, seed=5):
    data = GameData(DATA)
    ui = GameUI(data, scale=1, seed=seed)
    ui.delay_scale = 0.0
    drv = Driver(ui, script, prefix)
    ui.events = drv
    if setup: setup(ui)
    asyncio.run(ui.run(load_path=load, quick=quick))
    return ui

if __name__ == '__main__':
    pass
