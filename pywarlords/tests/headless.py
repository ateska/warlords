
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.environ.get('WARLORDS_DATA') or os.path.join(ROOT, '..', 'warlords')
OUT = os.environ.get('WARLORDS_OUT', '.')
import sys, time
from warlords.gamedata import GameData
from warlords.engine import Game
from warlords.ai import AI
from warlords.ui_base import UIBase

class Auto(UIBase):
    def __init__(self, turns):
        super().__init__(); self.turns = turns
    def status(self, t):
        if 'declares' in t or 'truce' in t: print('   ', t)
    def human_turn(self, game, p):
        return 'end'
    def game_over(self, game, lines):
        print('GAME OVER', lines)

def main(turns=30, seed=1, levels=(3,)*8):
    data = GameData(DATA)
    ui = Auto(turns)
    g = Game(data, ui, seed=seed)
    g.ai = AI(g)
    g.new_game([0]*8, list(levels))
    t0 = time.time()
    s = g.s
    # custom loop to stop after n turns
    while s.turn <= turns and not g.quit:
        for p in range(8):
            s.players[p].report_allowed = s.players[p].report_done = 0
        for p in range(8):
            if s.alive[p] and not s.human[p]:
                tp = time.time()
                g.ai_turn(p)
        g.end_of_round()
        nh = sum(1 for a in s.live_armies())
        print('turn %3d  %.1fs armies %4d cities %s gold %s' % (s.turn, time.time()-t0, nh, s.ncities, [pl.gold for pl in s.players]))
        s.turn += 1
    return g

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
