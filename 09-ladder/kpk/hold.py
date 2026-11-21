"""KPK hold v2: zero-FP board-parametric draw classifier + 2-ply invariant move + KK corner anchor."""

import rules


def _sq(pos, ch):
    i = pos.board.index(ch)
    return i % pos.width, i // pos.width


def _dist(f1, r1, f2, r2):
    df = f1 - f2
    if df < 0:
        df = -df
    dr = r1 - r2
    if dr < 0:
        dr = -dr
    return df if df > dr else dr


def _hold_coords_b(w, h, kf, kr, pf, pr, bf, br):
    if pf >= (w + 1) // 2:
        kf, pf, bf = w - 1 - kf, w - 1 - pf, w - 1 - bf
    is8 = w == 8 and h == 8
    rem = (h - 1) - pr
    can_ds = is8 and pr == 1 and not (kf == pf and kr in (2, 3)) and not (bf == pf and br in (2, 3))
    dstep = 1 if can_ds else 0

    # Immediate capture of undefended pawn
    if _dist(bf, br, pf, pr) == 1 and _dist(kf, kr, pf, pr) > 1:
        return True

    p_steps = rem - dstep + (1 if (kf == pf and kr > pr) else 0)
    dk_promo = _dist(bf, br, pf, h - 1)

    # Rook pawn
    if pf == 0:
        if bf == 0 and br > pr:
            return True
        if bf <= 1 and br >= h - 2:
            return True
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                nf, nr = bf + df, br + dr
                if not (0 <= nf < w and 0 <= nr < h):
                    continue
                if _dist(nf, nr, kf, kr) <= 1:
                    continue
                if nr == pr + 1 and nf == 1:
                    continue
                if (nf == 0 and nr > pr) or (nf <= 1 and nr >= h - 2):
                    return True
        if kf == 0 and kr > pr and bf == 2 and br >= kr and (kr >= h - 2 or br >= h - 2):
            return True
        dk_zone = max(max(0, bf - 1), max(0, (h - 2) - br))
        dK_b7 = _dist(kf, kr, 1, h - 2)
        if dk_zone <= p_steps and dk_promo <= p_steps + 1:
            if dk_zone < dK_b7 or (dk_zone == dK_b7 and br > kr + 1):
                if not (rem == 1 and bf == 2 and br == h - 1 and kr >= h - 3 and kf <= 2):
                    return True
        if _dist(bf, br, 0, pr) + 1 < _dist(kf, kr, 0, pr) and dk_promo <= p_steps:
            if not (kf == 0 and kr > pr and bf >= 2 and br == pr):
                if pr == h - 2 or _dist(bf, br, 0, pr + 1 + dstep) <= 1:
                    if _dist(kf, kr, 0, pr + 1 + dstep) > 1:
                        return True
        return False

    # Non-rook pawn: 7th rank
    if rem == 1:
        if bf == pf and br == h - 1:
            if (kf == pf and kr == h - 3) or _dist(kf, kr, pf, pr) > 1:
                return True
        if _dist(bf, br, pf, h - 1) == 1 and _dist(kf, kr, pf, h - 1) > 1:
            if _dist(kf, kr, pf, pr) > 2:
                return True
        return False

    kr_key = pr + 1 if rem <= 3 else pr + 2
    dk_p = _dist(bf, br, pf, pr)
    dK_p = _dist(kf, kr, pf, pr)
    if dk_p + 1 < dK_p and dk_promo <= p_steps:
        if _dist(bf, br, pf, pr + 1 + dstep) <= 1 and _dist(kf, kr, pf, pr + 1 + dstep) > 1:
            return True

    # 6th rank
    if rem == 2:
        if abs(kf - pf) <= 1 and kr >= h - 2:
            return False
        if bf == pf and br >= h - 2 and kr < pr:
            return True
        if kr < pr - 1 and min(_dist(bf, br, pf, h - 2), _dist(bf, br, pf, h - 1)) <= 1:
            return True
        if kr == pr and abs(kf - pf) == 1 and _dist(bf, br, kf, h - 1) == 1:
            return True
        if kr < pr and dk_promo <= p_steps:
            dK_side = min(_dist(kf, kr, pf - 1, h - 3), _dist(kf, kr, pf + 1, h - 3))
            if _dist(bf, br, pf, h - 2) < dK_side:
                return True
        return False

    # Ranks <= 5th (rem >= 3)
    if abs(kf - pf) <= 1 and kr >= kr_key:
        return False

    if bf == pf and br > pr and kr <= pr:
        if br <= kr_key + 1 or dk_promo <= p_steps:
            return True

    if kr == kr_key - 1 and abs(kf - pf) <= 1:
        has_tempo = pr + 1 < kr
        if not has_tempo:
            if kr + 2 < h and _dist(bf, br, kf, kr + 2) == 1 and not (kr + 2 == pr + 1 and abs(kf - pf) == 1):
                return True

    if kr <= pr and dk_promo <= p_steps:
        dk_blk = min(_dist(bf, br, pf, pr + 1), _dist(bf, br, pf, kr_key))
        if kr_key + 1 < h:
            dk_blk = min(dk_blk, _dist(bf, br, pf, kr_key + 1))
        dK_min = min(_dist(kf, kr, tf, kr_key) for tf in (pf - 1, pf, pf + 1))
        if dk_blk < dK_min:
            if rem == 3 or dk_blk < min(_dist(kf, kr, tf, pr + 1) for tf in (pf - 1, pf, pf + 1)):
                return True
            if rem >= 4 and _dist(bf, br, pf, pr + 2) < min(_dist(kf, kr, tf, pr + 1) for tf in (pf - 1, pf, pf + 1)):
                return True

    if kr <= pr and abs(bf - pf) == 1 and pr <= br <= kr_key + 1 and dk_promo <= p_steps:
        for nr in range(pr + 1, min(h, kr_key + 2)):
            if _dist(bf, br, pf, nr) == 1 and _dist(kf, kr, pf, nr) > 1:
                if rem == 3 or _dist(kf, kr, pf, pr + 1) >= 2:
                    return True

    return False


def _is_hold_b(pos):
    if "P" not in pos.board:
        if "Q" in pos.board or "R" in pos.board:
            # Draw in KQK/KRK only if Black can capture Q/R immediately (checked via coordinates)
            qch = "Q" if "Q" in pos.board else "R"
            qf, qr = _sq(pos, qch)
            kf, kr = _sq(pos, "K")
            bf, br = _sq(pos, "k")
            return _dist(bf, br, qf, qr) == 1 and _dist(kf, kr, qf, qr) > 1
        return True
    kf, kr = _sq(pos, "K")
    pf, pr = _sq(pos, "P")
    bf, br = _sq(pos, "k")
    return _hold_coords_b(pos.width, pos.height, kf, kr, pf, pr, bf, br)


def _is_hold_w(pos):
    reps = rules.legal_transitions(pos)
    return all(_is_hold_b(rp) for _, rp in reps)


def claims(pos):
    if pos.stm == "w":
        return _is_hold_w(pos)
    trans = rules.legal_transitions(pos)
    if not trans:
        return not rules.in_check(pos)
    return any(_is_hold_w(nxt) for _, nxt in trans)


def move(pos):
    trans = rules.legal_transitions(pos)
    # Bare KK (or KBK/KNK): capture minor piece if possible, else anchor k to a1
    if "P" not in pos.board and "Q" not in pos.board and "R" not in pos.board:
        for m, nxt in trans:
            if nxt.board.count(".") > pos.board.count("."):
                return m
        best = None
        for m, nxt in trans:
            bf, br = _sq(nxt, "k")
            cand = (bf + br, max(bf, br), m)
            if best is None or cand < best:
                best = cand
        return best[2]
    # Immediately capture any hanging piece (P, Q, R)
    for m, nxt in trans:
        if nxt.board.count(".") > pos.board.count("."):
            return m
    pf, pr = _sq(pos, "P") if "P" in pos.board else (0, 0)
    w, h = pos.width, pos.height
    is_rook = pf == 0 or pf == w - 1
    best = None
    for m, nxt in trans:
        reps = rules.legal_transitions(nxt)
        # Never allow White a safe Q/R promotion or checkmate
        safe_promo = 0
        hold_ok = 0
        for _, rp in reps:
            if not _is_hold_b(rp):
                hold_ok = 1
                if "Q" in rp.board or "R" in rp.board:
                    safe_promo = 1
        bf, br = _sq(nxt, "k")
        if is_rook:
            t_dist = _dist(bf, br, pf, h - 1)
        else:
            tr = min(h - 1, pr + 2)
            t_dist = _dist(bf, br, pf, tr)
        cand = (hold_ok, safe_promo, abs(bf - pf), t_dist, -br, m)
        if best is None or cand < best:
            best = cand
    return best[5]
