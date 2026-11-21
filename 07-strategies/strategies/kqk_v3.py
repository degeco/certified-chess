"""kqk round 3: fast mate-in-1/2 + strict box shrink + non-edge K mating target + K-unblock."""

import rules


def _find(pos, p):
    i = pos.board.index(p)
    return i % pos.width, i // pos.width


def _q_box(w, h, qf, qr, bf, br):
    f0, f1, cf, df = (0, qf, 0, 1) if bf < qf else ((qf + 1, w, w - 1, -1) if bf > qf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
    r0, r1, cr, dr = (0, qr, 0, 1) if br < qr else ((qr + 1, h, h - 1, -1) if br > qr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
    free = sum(1 for f in range(f0, f1) for r in range(r0, r1) if f != qf and r != qr and abs(f - qf) != abs(r - qr))
    return f1 - f0, r1 - r0, free, cf, cr, df, dr


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

    if max(abs(kf - bf), abs(kr - br)) <= 3:
        for m, reps, chk, nkf, nkr, nqf, nqr in safe:
            if len(reps) <= 3 and all(_mate1(rp) is not None for _, rp in reps):
                return m

    bw, bh, cur_free, cf, cr, df, dr = _q_box(w, h, qf, qr, bf, br)
    cur_area = bw * bh
    tf, tr = (cf + 2 * df, cr + dr) if bw == 1 else ((cf + df, cr + 2 * dr) if bh == 1 else (cf + 2 * df, cr + 2 * dr))

    q_moves = [x for x in safe if (x[5], x[6]) != (qf, qr)]
    k_moves = [x for x in safe if (x[3], x[4]) != (kf, kr)]

    # 1. Strict Q box shrink keeping >= 2 free squares
    cands = []
    for m, reps, chk, nkf, nkr, nqf, nqr in q_moves:
        if chk:
            continue
        nbw, nbh, free, ncf, ncr, _, _ = _q_box(w, h, nqf, nqr, bf, br)
        area = nbw * nbh
        if area < cur_area and free >= 2:
            edge_k = (nbw == 1 and nkf == ncf) or (nbh == 1 and nkr == ncr)
            blk = 1 if (edge_k and max(abs(nqf - nkf), abs(nqr - nkr)) == 1) else 0
            cands.append(((-blk, -area, -free, -abs(nqf - bf) - abs(nqr - br), m), m))
    if cands:
        return max(cands)[1]

    # 2. Escape stalemate cage if cur_free < 2
    if cur_free < 2:
        cands = [((-(nbw * nbh), -free, m), m) for m, _, chk, _, _, nqf, nqr in q_moves if not chk for nbw, nbh, free, *_ in [_q_box(w, h, nqf, nqr, bf, br)] if free >= 2]
        if cands:
            return max(cands)[1]

    # 3. Walk White King strictly closer to non-edge mating target (tf, tr)
    cur_kd = (max(abs(kf - tf), abs(kr - tr)), abs(kf - tf) + abs(kr - tr))
    cands = []
    for m, _, _, nkf, nkr, _, _ in k_moves:
        nkd = (max(abs(nkf - tf), abs(nkr - tr)), abs(nkf - tf) + abs(nkr - tr))
        if nkd < cur_kd:
            cands.append(((-nkd[0], -nkd[1], -max(abs(nkf - bf), abs(nkr - br)), m), m))
    if cands:
        return max(cands)[1]

    # 4. Unblock K if stuck on BK's edge behind Q
    if (bw == 1 and kf == cf) or (bh == 1 and kr == cr):
        cands = [((-abs(nkf - tf) - abs(nkr - tr), m), m) for m, _, _, nkf, nkr, _, _ in k_moves if (bw == 1 and nkf != cf) or (bh == 1 and nkr != cr)]
        if cands:
            return max(cands)[1]
        cands = []
        for m, reps, chk, nkf, nkr, nqf, nqr in q_moves:
            nbw, nbh, free, *_ = _q_box(w, h, nqf, nqr, bf, br)
            same = (bw == 1 and nbw == 1) or (bh == 1 and nbh == 1)
            far = 1 if max(abs(nqf - nkf), abs(nqr - nkr)) > 1 else 0
            cands.append(((1 if (same and not chk and free >= 2 and far) else 0, 1 if (chk and far) else 0, far, -(nbw * nbh), -len(reps), m), m))
        if cands:
            return max(cands)[1]

    if safe:
        return max(((-len(reps), -max(abs(nkf - bf), abs(nkr - br)), 1 if chk else 0, m), m) for m, reps, chk, nkf, nkr, _, _ in safe)[1]
    return trans[0][0]
