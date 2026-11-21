"""mini4x4 round 1: greedy tactical heuristic (mate-in-1, else checking capture, else check, else capture)."""

import rules


def _piece_val(ch):
    u = ch.upper()
    if u == "Q":
        return 9
    if u == "R":
        return 5
    if u == "B" or u == "N":
        return 3
    if u == "P":
        return 1
    return 0


def move(pos):
    best_m = None
    best_score = -10**9
    for m, nxt in rules.legal_transitions(pos):
        replies = rules.legal_moves(nxt)
        in_chk = rules.in_check(nxt)
        if not replies and in_chk:
            return m
        f2, r2 = ord(m[2]) - ord("a"), int(m[3]) - 1
        captured = pos.at(f2, r2)
        cap_val = _piece_val(captured)
        score = 0
        if in_chk:
            score += 100
        if cap_val > 0:
            score += 20 * cap_val
        score -= len(replies) * 3
        if score > best_score:
            best_score = score
            best_m = m
    return best_m
