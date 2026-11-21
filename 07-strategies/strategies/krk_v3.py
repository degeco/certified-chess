"""krk round 3: strict-monotonic Rook cut + universal Knight-opposition Rook waiting move."""

import rules


def _find(pos, p):
    i = pos.board.index(p)
    return i % pos.width, i // pos.width


def _r_box(w, h, rf, rr, bf, br):
    f0, f1, cf, df = (0, rf, 0, 1) if bf < rf else ((rf + 1, w, w - 1, -1) if bf > rf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
    r0, r1, cr, dr = (0, rr, 0, 1) if br < rr else ((rr + 1, h, h - 1, -1) if br > rr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
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
        if max(abs(nrf - bf), abs(nrr - br)) <= 1 and max(abs(nrf - nkf), abs(nrr - nkr)) > 1:
            continue
        safe.append((m, reps, chk, nkf, nkr, nrf, nrr))

    on_edge = bf == 0 or bf == w - 1 or br == 0 or br == h - 1
    if on_edge and max(abs(kf - bf), abs(kr - br)) <= 3:
        for m, reps, chk, nkf, nkr, nrf, nrr in safe:
            if len(reps) <= 2 and all(_mate1(rp) is not None for _, rp in reps):
                return m

    bw, bh, cf, cr, df, dr = _r_box(w, h, rf, rr, bf, br)
    cur_min = min(bw, bh)
    cur_area = bw * bh
    cut_vert = bw <= bh

    # 1. Emergency: R currently attacked by k and undefended
    r_hanging = max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1
    if r_hanging:
        cands = []
        for m, reps, chk, nkf, nkr, nrf, nrr in safe:
            nbw, nbh, ncf, ncr, _, _ = _r_box(w, h, nrf, nrr, bf, br)
            nmin = min(nbw, nbh)
            k_moved = 1 if (nkf, nkr) != (kf, kr) else 0
            keep_cut = 1 if ((cut_vert and nrf == rf) or ((not cut_vert) and nrr == rr)) else 0
            r_far = abs(nrf - bf) + abs(nrr - br)
            cands.append(((1 if nmin <= cur_min else 0, keep_cut, k_moved, -nmin, r_far, -(nbw * nbh), m), m))
        if cands:
            return max(cands)[1]

    # 2. Direct opposition push: K at (bf + 2*df, br) with R on file rf == bf + df -> check on file bf!
    if cut_vert and kf == bf + 2 * df and kr == br and rf == bf + df:
        cands = [((abs(nrr - br), m), m) for m, _, chk, _, _, nrf, nrr in safe if chk and nrf == bf]
        if cands:
            return max(cands)[1]
    if (not cut_vert) and kr == br + 2 * dr and kf == bf and rr == br + dr:
        cands = [((abs(nrf - bf), m), m) for m, _, chk, _, _, nrf, nrr in safe if chk and nrr == br]
        if cands:
            return max(cands)[1]

    # 3. Strict Rook cut shrink:
    #    - Strictly decrease min(bw, bh) (may flip quadrant if needed to escape bw >= w-1)
    #    - Wait: NEVER leave R adjacent to k without K defending (already filtered by safe)
    #    - Only shrink secondary dimension if same quadrant AND min > 1 AND far from k (avoid bounce!)
    cands = []
    for m, reps, chk, nkf, nkr, nrf, nrr in safe:
        if (nrf, nrr) == (rf, rr) or chk:
            continue
        nbw, nbh, ncf, ncr, _, _ = _r_box(w, h, nrf, nrr, bf, br)
        nmin = min(nbw, nbh)
        narea = nbw * nbh
        dist_rk = max(abs(nrf - bf), abs(nrr - br))
        if nmin < cur_min:
            # Prefer non-adjacent safe cut (or defended) with smallest nmin
            cands.append(((2, -nmin, 1 if dist_rk >= 2 else 0, -narea, abs(nrf - bf) + abs(nrr - br), m), m))
        elif nmin == cur_min and cur_min > 1 and (ncf, ncr) == (cf, cr) and nbw <= bw and nbh <= bh and narea < cur_area and dist_rk >= 2:
            cands.append(((1, -nmin, 1, -narea, abs(nrf - bf) + abs(nrr - br), m), m))
    if cands:
        return max(cands)[1]

    # 4. Opposition & Knight-Opposition Rook Waiting Move!
    if cut_vert:
        tf = bf + 2 * df
        tr = br
        if 0 <= tf < w:
            # If K is on opposition file tf and |kr - br| == 1 (Knight's opposition), play Rook waiting move on file rf!
            if kf == tf and abs(kr - br) == 1 and rf == bf + df:
                w_cands = []
                for m, _, chk, _, _, nrf, nrr in safe:
                    if nrf == rf and nrr != rr and not chk:
                        # Prefer a safe waiting square on file rf (especially far from k, or toggling 1 step)
                        far = 1 if abs(nrr - br) >= 2 else 0
                        w_cands.append(((far, -abs(nrr - rr), abs(nrr - br), m), m))
                if w_cands:
                    return max(w_cands)[1]
        else:
            # tf is off board (bw == w-1): reposition R to a safe rank far from k so next move flips cut!
            tf = min(w - 1, max(0, bf - 2 * df))
    else:
        tf = bf
        tr = br + 2 * dr
        if 0 <= tr < h:
            if kr == tr and abs(kf - bf) == 1 and rr == br + dr:
                w_cands = []
                for m, _, chk, _, _, nrf, nrr in safe:
                    if nrr == rr and nrf != rf and not chk:
                        far = 1 if abs(nrf - bf) >= 2 else 0
                        w_cands.append(((far, -abs(nrf - rf), abs(nrf - bf), m), m))
                if w_cands:
                    return max(w_cands)[1]
        else:
            tr = min(h - 1, max(0, br - 2 * dr))

    # 5. Walk White King strictly closer to (tf, tr)
    cur_kd = (max(abs(kf - tf), abs(kr - tr)), abs(kf - tf) + abs(kr - tr))
    k_cands = []
    for m, _, _, nkf, nkr, _, _ in safe:
        if (nkf, nkr) == (kf, kr):
            continue
        nkd = (max(abs(nkf - tf), abs(nkr - tr)), abs(nkf - tf) + abs(nkr - tr))
        if nkd < cur_kd:
            # If K is at tf and |kr - br| >= 2, stepping straight along file tf is best
            k_cands.append(((-nkd[0], -nkd[1], m), m))
    if k_cands:
        return max(k_cands)[1]

    # 6. Fallback: keep tighter cut and slide R far from k (unblocks K or prepares push)
    fb = []
    for m, reps, chk, nkf, nkr, nrf, nrr in safe:
        nbw, nbh, _, _, _, _ = _r_box(w, h, nrf, nrr, bf, br)
        same = (cut_vert and nrf == rf) or ((not cut_vert) and nrr == rr)
        r_far = abs(nrf - bf) + abs(nrr - br)
        fb.append(((1 if (same and not chk) else 0, -min(nbw, nbh), r_far, -len(reps), m), m))
    return max(fb)[1] if fb else trans[0][0]
