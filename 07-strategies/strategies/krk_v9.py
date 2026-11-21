"""krk round 9: pure 2-ply minimax over 2D-box + edge-rank King arrival + corner mate-in-2 potential."""

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
    return (99, 99, 99, 99, 999, 99, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  m_dim = min(bw, bh)
  area = bw * bh
  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0

  if m_dim == 1:
    # Phase 2: Black king is trapped on a 1-wide edge strip!
    # First bring White's King to the mating rank/file (2 away from edge), THEN shrink along the edge!
    if bh == 1:
      tr = cr + 2 * dr
      k_line_d = abs(kr - tr)
      if bw <= 2:
        # In the 2x1 corner cage: force k into the corner (cf, cr) with K on (cf, tr) or (cf+df, tr)
        tf = cf
        in_mate_k = 0 if (kr == tr and kf in (cf, cf + df)) else 1
        bk_c = abs(bf - cf)
        return (0, 0, k_edge, k_line_d, r_hang, bw, in_mate_k, bk_c, abs(kf - tf), 0, cf + cr, 0)
      tf = min(w - 1, max(0, rf - df))
      return (0, 0, k_edge, k_line_d, r_hang, bw, 1, 9, abs(kf - tf), abs(rf - bf), cf + cr, 0)
    else:
      tf = cf + 2 * df
      k_line_d = abs(kf - tf)
      if bh <= 2:
        tr = cr
        in_mate_k = 0 if (kf == tf and kr in (cr, cr + dr)) else 1
        bk_c = abs(br - cr)
        return (0, 0, k_edge, k_line_d, r_hang, bh, in_mate_k, bk_c, abs(kr - tr), 0, cf + cr, 1)
      tr = min(h - 1, max(0, rr - dr))
      return (0, 0, k_edge, k_line_d, r_hang, bh, 1, 9, abs(kr - tr), abs(rr - br), cf + cr, 1)

  # Phase 1: Shrink 2D Rook box (m_dim >= 2) using King-phalanx support behind R
  if bw >= bh and 0 <= rr + dr < h:
    tf, tr = rf - df, rr + dr
  elif 0 <= rf + df < w:
    tf, tr = rf + df, rr - dr
  else:
    tf, tr = rf, rr
  tf = min(w - 1, max(0, tf))
  tr = min(h - 1, max(0, tr))
  kd_c = max(abs(kf - tf), abs(kr - tr))
  kd_m = abs(kf - tf) + abs(kr - tr)
  k_ax = abs(kr - cr) if bh < bw else abs(kf - cf)
  return (0, 1, r_hang, k_edge, area, m_dim, bh, kd_c, kd_m, k_ax, cf + cr, 0)


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
