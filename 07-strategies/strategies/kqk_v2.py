"""kqk round 2: mate-in-1/2 + strict Queen box shrinking (free_squares >= 2) + fixed-corner King approach."""

import rules


def _find(pos, piece):
    i = pos.board.index(piece)
    return i % pos.width, i // pos.width


def _q_box(w, h, qf, qr, bf, br):
    if bf < qf:
        f0, f1, cf = 0, qf, 0
    elif bf > qf:
        f0, f1, cf = qf + 1, w, w - 1
    else:
        f0, f1, cf = 0, w, 0 if bf < w // 2 else w - 1
    if br < qr:
        r0, r1, cr = 0, qr, 0
    elif br > qr:
        r0, r1, cr = qr + 1, h, h - 1
    else:
        r0, r1, cr = 0, h, 0 if br < h // 2 else h - 1
    area = (f1 - f0) * (r1 - r0)
    free = 0
    for f in range(f0, f1):
        for r in range(r0, r1):
            if f != qf and r != qr and abs(f - qf) != abs(r - qr):
                free += 1
    return area, free, cf, cr


def _mate1(pos):
    for m, nxt in rules.legal_transitions(pos):
        if rules.in_check(nxt) and not rules.legal_moves(nxt):
            return m
    return None


def move(pos):
    w, h = pos.width, pos.height
    kf, kr = _find(pos, "K")
    qf, qr = _find(pos, "Q")
    bf, br = _find(pos, "k")
    trans = rules.legal_transitions(pos)

    safe = []
    for m, nxt in trans:
        reps = rules.legal_transitions(nxt)
        chk = rules.in_check(nxt)
        if not reps:
            if chk:
                return m
            continue
        nkf, nkr = _find(nxt, "K")
        nqf, nqr = _find(nxt, "Q")
        if max(abs(nqf - bf), abs(nqr - br)) <= 1 and max(abs(nqf - nkf), abs(nqr - nkr)) > 1:
            continue
        safe.append((m, reps, chk, nkf, nkr, nqf, nqr))

    # Fast mate in 2 when Black has few replies
    for m, reps, chk, nkf, nkr, nqf, nqr in safe:
        if len(reps) <= 3 and all(_mate1(rp) is not None for _, rp in reps):
            return m

    cur_area, cur_free, cf, cr = _q_box(w, h, qf, qr, bf, br)

    # Strict Queen box shrink keeping >= 2 free squares in BK's quadrant
    best_q = None
    for m, reps, chk, nkf, nkr, nqf, nqr in safe:
        if (nqf, nqr) == (qf, qr) or chk:
            continue
        area, free, _, _ = _q_box(w, h, nqf, nqr, bf, br)
        if area < cur_area and free >= 2:
            key = (-area, -free, -abs(nqf - bf) - abs(nqr - br), m)
            if best_q is None or key > best_q[0]:
                best_q = (key, m)
    if best_q is not None:
        return best_q[1]

    # Escape stalemate trap if cur_free < 2
    if cur_free < 2:
        best_fix = None
        for m, reps, chk, nkf, nkr, nqf, nqr in safe:
            if (nqf, nqr) == (qf, qr) or chk:
                continue
            area, free, _, _ = _q_box(w, h, nqf, nqr, bf, br)
            if free >= 2:
                key = (-area, -free, m)
                if best_fix is None or key > best_fix[0]:
                    best_fix = (key, m)
        if best_fix is not None:
            return best_fix[1]

    # Walk White King strictly closer to the fixed quadrant corner (cf, cr)
    cur_k = (max(abs(kf - cf), abs(kr - cr)), abs(kf - cf) + abs(kr - cr))
    best_k = None
    for m, reps, chk, nkf, nkr, nqf, nqr in safe:
        if (nkf, nkr) == (kf, kr):
            continue
        nk = (max(abs(nkf - cf), abs(nkr - cr)), abs(nkf - cf) + abs(nkr - cr))
        if nk < cur_k:
            key = (-nk[0], -nk[1], -max(abs(nkf - bf), abs(nkr - br)), m)
            if best_k is None or key > best_k[0]:
                best_k = (key, m)
    if best_k is not None:
        return best_k[1]

    # Fallback: minimize replies then King distance to BK
    best_fb = None
    for m, reps, chk, nkf, nkr, nqf, nqr in safe:
        area, _, _, _ = _q_box(w, h, nqf, nqr, bf, br)
        kd = max(abs(nkf - bf), abs(nkr - br))
        key = (-len(reps), -kd, -area, 1 if chk else 0, m)
        if best_fb is None or key > best_fb[0]:
            best_fb = (key, m)
    return best_fb[1] if best_fb is not None else trans[0][0]
