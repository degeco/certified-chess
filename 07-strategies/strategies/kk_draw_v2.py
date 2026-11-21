"""kk-draw round 2: maximize Chebyshev distance from the opponent king."""

import rules


def _find(pos, piece):
    idx = pos.board.index(piece)
    return idx % pos.width, idx // pos.width


def move(pos):
    opp_k = "k" if pos.stm == "w" else "K"
    of, or_ = _find(pos, opp_k)
    best_m = None
    best_key = (-1, -1, "")
    for m in rules.legal_moves(pos):
        f2 = ord(m[2]) - ord("a")
        r2 = int(m[3]) - 1
        cheb = max(abs(f2 - of), abs(r2 - or_))
        manh = abs(f2 - of) + abs(r2 - or_)
        key = (cheb, manh, m)
        if key > best_key:
            best_key = key
            best_m = m
    return best_m
