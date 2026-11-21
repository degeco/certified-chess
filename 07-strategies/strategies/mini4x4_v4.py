"""mini4x4 round 4: minimal checking-move strategy (prefer mate-in-1, else check minimizing replies)."""

import rules


def move(pos):
    best = None
    for m, nxt in rules.legal_transitions(pos):
        if rules.in_check(nxt):
            n = len(rules.legal_moves(nxt))
            if best is None or (n, m) < best:
                best = (n, m)
    return best[1] if best is not None else rules.legal_moves(pos)[0]
