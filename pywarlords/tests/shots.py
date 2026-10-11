"""Render screens headlessly and save PNGs for visual checks."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.environ.get('WARLORDS_DATA') or os.path.join(ROOT, '..', 'warlords')
OUT = os.environ.get('WARLORDS_OUT', '.')
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
os.environ.setdefault('WARLORDS_NOSOUND', '1')
from warlords.gamedata import GameData
from warlords.engine import Game
from warlords.ai import AI
from warlords.ui.game_ui import GameUI

def save(ui, name):
    surf = ui.scr.surface.copy()
    if ui.scr.cursor:
        c = ui.scr._cursors.get(ui.scr.cursor)
    big = pygame.transform.scale(surf, (640, 400))
    pygame.image.save(big, os.path.join(OUT, 'py_%s.png' % name))

data = GameData(DATA)
ui = GameUI(data, scale=1)
g = Game(data, ui, seed=3); g.ai = AI(g); ui.game = g
from warlords.gamedata import find_file
g.s.load(find_file(DATA, 'WAR1.SAV')); g.recompute_totals_all()
s = g.s
g.center_view(s.view_x + 4, s.view_y + 4)
ui.draw_main(); save(ui, 'main')
# select army at Zhoran (31) area like in DOSBox: the army at the castle
g.select_stack(31, 61, False) if s.armies_at(31,61) else None
ui.draw_main(); save(ui, 'sel')
ui.draw_main(); ui.draw_menu((150, 30)); ui._menu_sel = 3; ui.draw_menu((230, 30)); save(ui, 'menu')
