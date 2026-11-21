"""KPK win v2: zero-FP board-parametric geometric classifier + 2-ply minimax + KQK/KRK handover."""

import rules
from lib import kqk, krk


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


def _k_dist(kf, kr, tf, tr, pf, pr):
    df = tf - kf
    dr = tr - kr
    adf = -df if df < 0 else df
    adr = -dr if dr < 0 else dr
    d = adf if adf > adr else adr
    if adf == adr and adf >= 2:
        sf = 1 if df > 0 else -1
        sr = 1 if dr > 0 else -1
        if (pf - kf) * sf == (pr - kr) * sr and 0 < (pf - kf) * sf < adf:
            return d + 1
    return d


def _pawn_runs(w, h, kf, kr, pf, pr, bf, br):
    if bf == pf and br > pr:
        return False
    is8 = w == 8 and h == 8
    rem = (h - 1) - pr
    can_ds = is8 and pr == 1 and not (kf == pf and kr in (2, 3)) and not (bf == pf and br in (2, 3))
    if kf == pf and kr > pr:
        p_steps = rem - (1 if (is8 and pr == 1 and not (bf == pf and br in (2, 3))) else 0) + 1
    else:
        p_steps = rem - (1 if can_ds else 0)
    dk_promo = _dist(bf, br, pf, h - 1)
    if dk_promo > p_steps:
        return True
    if _dist(kf, kr, pf, h - 1) == 1 and not (kf == pf and kr > pr):
        if dk_promo > p_steps - 1:
            start_r = pr + (2 if can_ds else 1)
            for r in range(start_r, h - 1):
                t = r - pr - (1 if can_ds else 0)
                if _dist(bf, br, pf, r) <= t and _dist(kf, kr, pf, r) > 1:
                    return False
            return True
    return False


def _pawn_safe(w, h, kf, kr, pf, pr, bf, br):
    is8 = w == 8 and h == 8
    rem = (h - 1) - pr
    can_ds = is8 and pr == 1 and not (kf == pf and kr in (2, 3)) and not (bf == pf and br in (2, 3))
    dstep = 1 if can_ds else 0
    dk_p = _dist(bf, br, pf, pr)
    dK_p = _dist(kf, kr, pf, pr)
    if dk_p == 1 and dK_p >= 2:
        can_def = False
        if dK_p == 2:
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    nf, nr = kf + df, kr + dr
                    if 0 <= nf < w and 0 <= nr < h and _dist(nf, nr, pf, pr) == 1 and _dist(nf, nr, bf, br) > 1:
                        can_def = True
                        break
                if can_def:
                    break
        if can_def:
            return True
        if bf == pf and br == pr + 1:
            return False
        nr1 = pr + (2 if can_ds else 1)
        if _dist(bf, br, pf, nr1) <= 1 and _dist(kf, kr, pf, nr1) > 1:
            return False
    if dK_p <= dk_p + 1 and dk_p > 1:
        if not (pf == 0 and dk_p <= dK_p):
            return True
    if bf == pf and br > pr:
        return False
    for step in range(1, rem - dstep + 1):
        r = pr + step + dstep
        if r >= h:
            r = h - 1
        if _dist(kf, kr, pf, r) == 1:
            return True
        if _dist(bf, br, pf, r) <= step:
            return False
    return True


def _win_coords_w(w, h, kf, kr, pf, pr, bf, br):
    if pf >= (w + 1) // 2:
        kf, pf, bf = w - 1 - kf, w - 1 - pf, w - 1 - bf
    rem = (h - 1) - pr

    if pf == 0:
        if bf == 0 and br > pr:
            return False
        if bf <= 1 and br >= h - 2:
            return False
        if _pawn_runs(w, h, kf, kr, pf, pr, bf, br):
            trapped = kf == 0 and kr > pr and bf == 2 and br >= kr - 1 and not any(
                0 <= nr < h and _dist(1, nr, bf, br) > 1 for nr in (kr - 1, kr, kr + 1)
            )
            if not trapped:
                return True
        if not _pawn_safe(w, h, kf, kr, pf, pr, bf, br):
            return False
        dK_b7 = _dist(kf, kr, 1, h - 2)
        dk_zone = max(max(0, bf - 1), max(0, (h - 2) - br))
        if kf == 1 and kr >= h - 2:
            return True
        if kf == 0 and kr > pr:
            for nr in (kr - 1, kr, kr + 1):
                if 0 <= nr < h and _dist(1, nr, bf, br) > 1:
                    if nr >= h - 2 and bf >= 3:
                        return True
                    d1 = _dist(1, nr, 1, h - 2)
                    if d1 + 1 < dk_zone and not (bf <= 2 and br <= nr - 1 and pr < nr - 1):
                        return True
                    if d1 + 1 == dk_zone and bf >= 3 and br <= nr:
                        return True
            if kr == pr + 2 and kr < h - 1 and bf == 1 and br == pr and pr + 1 <= h - 2:
                return True
            return False
        if dK_b7 < dk_zone or (dK_b7 == dk_zone and bf >= 3 and br <= kr + 1 and kf <= 2):
            if not (_dist(bf, br, 0, pr) <= _dist(kf, kr, 0, pr) and br <= kr):
                return True
        return False

    if _pawn_runs(w, h, kf, kr, pf, pr, bf, br):
        return True

    if rem == 1:
        if bf == pf and br == h - 1:
            for tf in (pf - 1, pf + 1):
                if _dist(kf, kr, tf, h - 3) == 1:
                    return True
            return False
        if _dist(bf, br, pf, h - 1) > 1 or _dist(kf, kr, pf, h - 1) == 1:
            return True
        for tf, tr in ((pf - 1, h - 2), (pf + 1, h - 2), (pf - 1, h - 1), (pf + 1, h - 1)):
            if _dist(kf, kr, tf, tr) == 1 and _dist(bf, br, tf, tr) > 1:
                if not (_dist(bf, br, pf, pr) == 1 and _dist(tf, tr, pf, pr) > 1):
                    return True
        return False

    if not _pawn_safe(w, h, kf, kr, pf, pr, bf, br):
        return False

    kr_key = pr + 1 if rem <= 3 else pr + 2
    if abs(kf - pf) <= 1 and kr >= kr_key:
        return True

    if rem == 2:
        b_stale = pf == 1 and bf == 0 and br == h - 1
        if kr == pr and abs(kf - pf) == 1:
            if not (bf == kf and br == h - 1) and not (b_stale and kf == 2):
                if not (_dist(bf, br, pf, pr + 1) == 1 and _dist(kf, kr, pf, pr + 1) > 1):
                    return True
        for tf in (pf - 1, pf + 1):
            if b_stale and tf == 2:
                continue
            dK = _k_dist(kf, kr, tf, h - 3, pf, pr)
            if dK == 0:
                continue
            if dK < _dist(bf, br, tf, h - 3) and dK <= _dist(bf, br, pf, h - 2) and _dist(bf, br, tf, h - 1) > dK:
                return True
        for tf in (pf - 1, pf, pf + 1):
            if b_stale and tf == 2 and kf >= 2:
                continue
            dK = _k_dist(kf, kr, tf, h - 2, pf, pr)
            if dK < _dist(bf, br, tf, h - 2) and dK <= _dist(bf, br, pf, h - 1):
                return True
        return False

    dk_D = _dist(bf, br, pf, kr_key + 1) if kr_key + 1 < h else 99
    for tf in (pf - 1, pf, pf + 1):
        dK = _k_dist(kf, kr, tf, kr_key, pf, pr)
        if dK < _dist(bf, br, tf, kr_key) and dK <= dk_D:
            return True

    if kr > pr and abs(kf - pf) <= 1:
        if pr + 1 < kr and not (bf == pf and br == pr + 1):
            if _dist(bf, br, pf, pr + 1) > 1 or _dist(kf, kr, pf, pr + 1) <= 1:
                return True
        if br > kr:
            if not (kf == bf and (br - kr) % 2 == 0):
                if not (abs(kf - bf) % 2 == 0 and (br - kr) % 2 == 0 and br > kr + 2 and kr < kr_key - 1):
                    return True
        elif br <= kr and abs(bf - pf) >= 2:
            return True

    if rem >= 4:
        for tf in (pf - 1, pf, pf + 1):
            dK1 = _k_dist(kf, kr, tf, pr + 1, pf, pr)
            if dK1 < _dist(bf, br, tf, pr + 1) and dK1 < _dist(bf, br, tf, pr + 2) and dK1 < _dist(bf, br, pf, pr + 3):
                if not (bf == tf and br == pr + 3 and dK1 == 0):
                    return True

    return False


def _is_win_w(pos):
    if "Q" in pos.board or "R" in pos.board:
        return True
    if "P" not in pos.board:
        return False
    kf, kr = _sq(pos, "K")
    pf, pr = _sq(pos, "P")
    bf, br = _sq(pos, "k")
    return _win_coords_w(pos.width, pos.height, kf, kr, pf, pr, bf, br)


def _is_win_b(pos):
    reps = rules.legal_transitions(pos)
    if not reps:
        return rules.in_check(pos)
    return all(_is_win_w(rp) for _, rp in reps)


def claims(pos):
    if pos.stm == "b":
        return _is_win_b(pos)
    for m, nxt in rules.legal_transitions(pos):
        if len(m) == 5 and m[4] not in ("q", "r"):
            continue
        if _is_win_b(nxt):
            return True
    return False


def _pot(pos):
    if "Q" in pos.board:
        return (0, 0, 0, 0, 0, 0, 0, 0, 0)
    if "R" in pos.board:
        return (0, 1, 0, 0, 0, 0, 0, 0, 0)
    if "P" not in pos.board:
        return (99, 99, 99, 99, 99, 99, 99, 99, 99)
    w, h = pos.width, pos.height
    kf, kr = _sq(pos, "K")
    pf, pr = _sq(pos, "P")
    bf, br = _sq(pos, "k")
    win_flag = 0 if _win_coords_w(w, h, kf, kr, pf, pr, bf, br) else 1
    rem = (h - 1) - pr
    k_blk = 1 if (kf == pf and kr == pr + 1) else 0
    if pf == 0 or pf == w - 1:
        tf = 1 if pf == 0 else w - 2
        kd = _dist(kf, kr, tf, h - 2)
        k_on_a = 1 if (kf == pf and kr > pr) else 0
        return (1, win_flag, rem, k_on_a, kd, -kr, abs(kf - tf), _dist(kf, kr, pf, pr), 0)
    kr_key = (h - 2) if rem == 1 else (pr + 1 if rem <= 3 else pr + 2)
    on_key = 0 if (abs(kf - pf) <= 1 and kr >= kr_key) else 1
    kd = min(_k_dist(kf, kr, tf, kr_key, pf, pr) for tf in (pf - 1, pf, pf + 1))
    opp = 0 if (br > kr and kf == bf and (br - kr) % 2 == 1) else 1
    return (1, win_flag, rem, on_key, kd, -kr, k_blk, abs(kf - pf), opp)


def move(pos):
    if "Q" in pos.board:
        return kqk.move(pos)
    if "R" in pos.board:
        return krk.move(pos)
    trans = rules.legal_transitions(pos)
    best = None
    for m, nxt in trans:
        if len(m) == 5 and m[4] not in ("q", "r"):
            continue
        reps = rules.legal_transitions(nxt)
        if not reps:
            if rules.in_check(nxt):
                return m
            continue
        worst = max(_pot(rp) for _, rp in reps)
        cand = (worst, len(reps), m)
        if best is None or cand < best:
            best = cand
    return best[2] if best is not None else trans[0][0]
