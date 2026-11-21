"""mini4x4 round 2: 2-ply mate check + prefer pawn checking captures (lowest attacker value)."""

import rules


def _val(ch):
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


def _mate_in_1(pos):
    for m, nxt in rules.legal_transitions(pos):
        if rules.in_check(nxt) and not rules.legal_moves(nxt):
            return m
    return None


def move(pos):
    m1 = _mate_in_1(pos)
    if m1 is not None:
        return m1
    best_m = None
    best_score = -10**9
    for m, nxt in rules.legal_transitions(pos):
        replies = rules.legal_transitions(nxt)
        in_chk = rules.in_check(nxt)
        if not replies:
            if in_chk:
                return m
            continue
        if all(_mate_in_1(rpos) is not None for _, rpos in replies):
            return m
        f1, r1 = ord(m[0]) - ord("a"), int(m[1]) - 1
        f2, r2 = ord(m[2]) - ord("a"), int(m[3]) - 1
        att = _val(pos.at(f1, r1))
        cap = _val(pos.at(f2, r2))
        score = (200 if in_chk else 0) + cap * 30 - att * 10 - len(replies) * 15
        if score > best_score:
            best_score = score
            best_m = m
    return best_m
