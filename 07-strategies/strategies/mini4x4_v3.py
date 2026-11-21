"""mini4x4 round 3: depth-bounded checking AND-OR mate search (up to 4 own moves)."""

import rules


def _forced_check_mate(pos, depth):
    """Return a move forcing mate within `depth` own moves using checking moves, or None."""
    transitions = rules.legal_transitions(pos)
    # First check immediate mate in 1
    checks = []
    for m, nxt in transitions:
        if not rules.in_check(nxt):
            continue
        replies = rules.legal_transitions(nxt)
        if not replies:
            return m
        checks.append((len(replies), m, replies))
    if depth <= 1:
        return None
    checks.sort(key=lambda item: item[0])
    for _, m, replies in checks:
        ok = True
        for _, rpos in replies:
            if _forced_check_mate(rpos, depth - 1) is None:
                ok = False
                break
        if ok:
            return m
    return None


def move(pos):
    for d in (1, 2, 3, 4):
        m = _forced_check_mate(pos, d)
        if m is not None:
            return m
    return rules.legal_moves(pos)[0]
