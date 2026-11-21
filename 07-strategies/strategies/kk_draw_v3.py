"""kk-draw round 3: anchor the prover king to the a1 corner (minimal orbit)."""

import rules


def move(pos):
    best_m = None
    best_key = (999, 999, "")
    for m in rules.legal_moves(pos):
        f2 = ord(m[2]) - ord("a")
        r2 = int(m[3]) - 1
        key = (f2 + r2, max(f2, r2), m)
        if key < best_key:
            best_key = key
            best_m = m
    return best_m
