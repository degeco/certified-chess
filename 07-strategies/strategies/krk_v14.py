"""krk round 14: unified 2-ply potential with K on rr+dr (behind R's cut line) in both Phase 1 and Phase 2."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _rbox(w, h, rf, rr, bf, br):
  f0, f1, cf, df = (0, rf, 0, 1) if bf < rf else ((rf + 1, w, w - 1, -1) if bf > rf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
  r0, r1, cr, dr = (0, rr, 0, 1) if br < rr else ((rr + 1, h, h - 1, -1) if br > rr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
  return f1 - f0, r1 - r0, cf, cr, df, dr


def _pot(pos):
  if "R" not in pos.board:
    return (99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0

  # Phase 3 (best): King + Rook 2x1 corner mating cage
  if bw == 2 and (br == 0 or br == h - 1):
    cr_e, dr_e = (0, 1) if br == 0 else (h - 1, -1)
    if kr == cr_e + 2 * dr_e and kf == cf + df and rf == cf + 2 * df and rr != cr_e:
      return (0, 0, 0, r_hang, abs(bf - cf), 0, 0, 0, 0, 0, 0, 0)
  if bh == 2 and (bf == 0 or bf == w - 1):
    cf_e, df_e = (0, 1) if bf == 0 else (w - 1, -1)
    if kf == cf_e + 2 * df_e and kr == cr + dr and rr == cr + 2 * dr and rf != cf_e:
      return (0, 0, 0, r_hang, abs(br - cr), 0, 0, 0, 0, 0, 0, 0)

  m_dim = min(bw, bh)
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0

  # Unified Phase 1 & 2: shrink m_dim all the way to 1, and within each m_dim bring K to rr+dr (behind R),
  # keep R safe, then squeeze the orthogonal box dimension down to 2 (entering corner cage or shrinking m_dim)!
  if bh <= bw:
    tr = min(h - 1, max(0, rr + dr))
    k_line_d = abs(kr - tr)
    k_in_box = 1 if (kr - rr) * dr <= 0 else 0
    tf = cf + df if (bh == 1 and bw <= 2) else min(w - 1, max(0, rf - df))
    k_along = abs(kf - tf)
    bk_along = abs(bf - cf)
    long_d = bw
    axis = 0
  else:
    tf = min(w - 1, max(0, rf + df))
    k_line_d = abs(kf - tf)
    k_in_box = 1 if (kf - rf) * df <= 0 else 0
    tr = cr + dr if (bw == 1 and bh <= 2) else min(h - 1, max(0, rr - dr))
    k_along = abs(kr - tr)
    bk_along = abs(br - cr)
    long_d = bh
    axis = 1

  # When m_dim >= 2 and long_d == 2, K at (cf+df, rr+dr) + R check shrinks m_dim!
  # Prefer smaller m_dim, then K not in box, K on rr+dr, R not hanging, smaller long_d, K at tf, k pushed to corner.
  return (0, 1, k_edge, m_dim, k_in_box, k_line_d, r_hang, long_d, k_along, bk_along, axis, cf + cr)


def move(pos):
  trans = rules.legal_transitions(pos)
  best = None
  for m, nxt in trans:
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
