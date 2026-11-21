"""krk round 2: Rook box-shrinking + King opposition & edge-mate algorithm."""

import rules


def _find(pos, p):
    i = pos.board.index(p)
    return i % pos.width, i // pos.width


def _r_box(w, h, rf, rr, bf, br):
    if bf < rf:
        f0, f1, cf, df = 0, rf, 0, 1
    elif bf > rf:
        f0, f1, cf, df = rf + 1, w, w - 1, -1
    else:
        f0, f1 = 0, w
        cf, df = (0, 1) if bf < w // 2 else (w - 1, -1)
    if br < rr:
        r0, r1, cr, dr = 0, rr, 0, 1
    elif br > rr:
        r0, r1, cr, dr = rr + 1, h, h - 1, -1
    else:
        r0, r1 = 0, h
        cr, dr = (0, 1) if br < h // 2 else (h - 1, -1)
    return f1 - f0, r1 - r0, cf, cr, df, dr


def _mate1(pos):
    for m, nxt in rules.legal_transitions(pos):
        if rules.in_check(nxt) and not rules.legal_moves(nxt):
            return m
    return None


def move(pos):
    w, h = pos.width, pos.height
    kf, kr = _find(pos, "K")
    rf, rr = _find(pos, "R")
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
        nrf, nrr = _find(nxt, "R")
        # Rook must not be hanging (attacked by k and not defended by K)
        if max(abs(nrf - bf), abs(nrr - br)) <= 1 and max(abs(nrf - nkf), abs(nrr - nkr)) > 1:
            continue
        safe.append((m, reps, chk, nkf, nkr, nrf, nrr))

    # Fast mate in 2 when K is close to k and k is on an edge
    on_edge = bf == 0 or bf == w - 1 or br == 0 or br == h - 1
    if on_edge and max(abs(kf - bf), abs(kr - br)) <= 3:
        for m, reps, chk, nkf, nkr, nrf, nrr in safe:
            if len(reps) <= 2 and all(_mate1(rp) is not None for _, rp in reps):
                return m

    bw, bh, cf, cr, df, dr = _r_box(w, h, rf, rr, bf, br)
    cur_min = min(bw, bh)
    cur_area = bw * bh

    # 1. Emergency: if R is currently hanging, defend with K (if keeps cut) or flee R along tighter cut
    r_hanging = max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1
    if r_hanging:
        best_s = None
        for m, reps, chk, nkf, nkr, nrf, nrr in safe:
            nbw, nbh, _, _, _, _ = _r_box(w, h, nrf, nrr, bf, br)
            nmin = min(nbw, nbh)
            k_moved = 1 if (nkf, nkr) != (kf, kr) else 0
            r_dist = abs(nrf - bf) + abs(nrr - br)
            key = (1 if nmin <= cur_min else 0, k_moved, -nmin, -(nbw * nbh), r_dist, m)
            if best_s is None or key > best_s[0]:
                best_s = (key, m)
        if best_s is not None:
            return best_s[1]

    # 2. If in direct opposition along the tighter cut axis, give rank/file check to push k back!
    cut_vert = bw <= bh  # True => cutting files (k on cf side of rf), push horizontally
    if cut_vert:
        # K at (bf + 2*df, br) and R on file rf == bf + df (safe distance from br) -> check on file bf!
        if kf == bf + 2 * df and kr == br and rf == bf + df:
            for m, reps, chk, nkf, nkr, nrf, nrr in safe:
                if (nrf, nrr) != (rf, rr) and chk and nrf == bf:
                    return m
    else:
        if kr == br + 2 * dr and kf == bf and rr == br + dr:
            for m, reps, chk, nkf, nkr, nrf, nrr in safe:
                if (nrf, nrr) != (rf, rr) and chk and nrr == br:
                    return m

    # 3. Strict Rook cut shrink (never worsen min(bw, bh); shrink tighter cut first, else shrink area)
    # Only move R to a square at distance >= 2 from k (or defended by K) so k can't bounce R immediately.
    best_r = None
    for m, reps, chk, nkf, nkr, nrf, nrr in safe:
        if (nrf, nrr) == (rf, rr) or chk:
            continue
        nbw, nbh, _, _, _, _ = _r_box(w, h, nrf, nrr, bf, br)
        nmin = min(nbw, nbh)
        narea = nbw * nbh
        if nmin < cur_min or (nmin == cur_min and narea < cur_area and (cur_min > 1)):
            # Prefer moving to safe non-adjacent square (unless defended by K)
            adj = 1 if max(abs(nrf - bf), abs(nrr - br)) <= 1 else 0
            key = (-nmin, -adj, -narea, abs(nrf - bf) + abs(nrr - br), m)
            if best_r is None or key > best_r[0]:
                best_r = (key, m)
    if best_r is not None:
        return best_r[1]

    # 4. Walk White King to the exact opposition square behind the Rook's cut line
    if cut_vert:
        tf = min(w - 1, max(0, bf + 2 * df))
        tr = br
        # If K is on the SAME side of rf as k (blocked), still head to tf
        # If already on file tf and 1 rank off (|kr - br| == 1), check whether to chase or wait
        if kf == tf and abs(kr - br) == 1:
            # If k is pinned on the corner rank away from K, play a Rook waiting move on file rf!
            away_r = br + (br - kr)
            if not (0 <= away_r < h):
                best_w = None
                for m, reps, chk, nkf, nkr, nrf, nrr in safe:
                    if nrf == rf and nrr != rr and not chk:
                        dist = abs(nrr - br)
                        key = (1 if dist >= 2 else 0, -abs(nrr - rr), m)
                        if best_w is None or key > best_w[0]:
                            best_w = (key, m)
                if best_w is not None:
                    return best_w[1]
    else:
        tf = bf
        tr = min(h - 1, max(0, br + 2 * dr))
        if kr == tr and abs(kf - bf) == 1:
            away_f = bf + (bf - kf)
            if not (0 <= away_f < w):
                best_w = None
                for m, reps, chk, nkf, nkr, nrf, nrr in safe:
                    if nrr == rr and nrf != rf and not chk:
                        dist = abs(nrf - bf)
                        key = (1 if dist >= 2 else 0, -abs(nrf - rf), m)
                        if best_w is None or key > best_w[0]:
                            best_w = (key, m)
                if best_w is not None:
                    return best_w[1]

    cur_kd = (max(abs(kf - tf), abs(kr - tr)), abs(kf - tf) + abs(kr - tr))
    best_k = None
    for m, reps, chk, nkf, nkr, nrf, nrr in safe:
        if (nkf, nkr) == (kf, kr):
            continue
        nkd = (max(abs(nkf - tf), abs(nkr - tr)), abs(nkf - tf) + abs(nkr - tr))
        if nkd < cur_kd:
            key = (-nkd[0], -nkd[1], m)
            if best_k is None or key > best_k[0]:
                best_k = (key, m)
    if best_k is not None:
        return best_k[1]

    # 5. If K is already at (tf, tr) or blocked by R, slide R along the cut line to clear/reposition
    best_fb = None
    for m, reps, chk, nkf, nkr, nrf, nrr in safe:
        nbw, nbh, _, _, _, _ = _r_box(w, h, nrf, nrr, bf, br)
        same_cut = (cut_vert and nrf == rf) or ((not cut_vert) and nrr == rr)
        r_far = abs(nrf - bf) + abs(nrr - br)
        key = (1 if (same_cut and not chk) else 0, -min(nbw, nbh), r_far, -len(reps), m)
        if best_fb is None or key > best_fb[0]:
            best_fb = (key, m)
    return best_fb[1] if best_fb is not None else trans[0][0]
