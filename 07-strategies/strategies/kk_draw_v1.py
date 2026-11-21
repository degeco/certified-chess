"""kk-draw round 1: pick the lexicographically first legal move."""

import rules


def move(pos):
    return rules.legal_moves(pos)[0]
