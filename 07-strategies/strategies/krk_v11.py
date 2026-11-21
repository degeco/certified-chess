"""krk round 11: pure 2-ply minimax with m_dim-first + area-before-r_hang + corner mating cage."""

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
  area = bw * bh
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0

  if m_dim == 1:
    # Phase 2: Black king trapped on a 1-wide edge strip.
    if bh == 1:
      tr = cr + 2 * dr
      k_line_d = abs(kr - tr)
      tf = cf + df if bw <= 2 else min(w - 1, max(0, rf - df))
      return (0, 1, k_edge, k_line_d, bw, r_hang, abs(kf - tf), abs(bf - cf), cf + cr, 0, 0, 0)
    else:
      tf = cf + 2 * df
      k_line_d = abs(kf - tf)
      tr = cr + dr if bh <= 2 else min(h - 1, max(0, rr - dr))
      return (0, 1, k_edge, k_line_d, bh, r_hang, abs(kr - tr), abs(br - cr), cf + cr, 1, 0, 0)

  # Phase 1: Shrink 2D Rook box (m_dim >= 2)
  # Put area BEFORE r_hang so R never flees and expands the box while K walks in.
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
  # When K is in direct opposition across R's cut line with R adjacent to k, prefer sliding R off-file/rank
  k_ax = abs(kr - cr) if bh < bw else abs(kf - cf)
  # Distance of k from box corner breaks ties when K is already at (tf, tr)
  bk_c = abs(bf - cf) + abs(br - cr)
  return (0, 2, k_edge, area, m_dim, bh, r_hang, kd_c, kd_m, bk_c, k_ax, cf + cr)


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
