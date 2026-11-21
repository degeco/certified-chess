"""krk round 8: pure 2-ply minimax over 2D-box + King-phalanx potential (no Black-king distance terms)."""

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
    return (99, 99, 99, 999, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  area = bw * bh
  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0

  # Phalanx target for K: always outside k's box so k cannot block K!
  if bw == 1 and bh <= 2:
    tf, tr = cf + 2 * df, cr + dr
  elif bh == 1 and bw <= 2:
    tf, tr = cf + df, cr + 2 * dr
  elif bh == 1:
    tf, tr = rf - df, cr + 2 * dr
  elif bw == 1:
    tf, tr = cf + 2 * df, rr - dr
  elif bw >= bh and 0 <= rr + dr < h:
    tf, tr = rf - df, rr + dr
  elif 0 <= rf + df < w:
    tf, tr = rf + df, rr - dr
  else:
    tf, tr = rf, rr

  tf = min(w - 1, max(0, tf))
  tr = min(h - 1, max(0, tr))
  kd_c = max(abs(kf - tf), abs(kr - tr))
  kd_m = abs(kf - tf) + abs(kr - tr)
  # Break distance ties around R toward the box corner, and break bw/bh symmetry deterministically
  k_ax = abs(kr - cr) if bh < bw else abs(kf - cf)
  return (0, r_hang, k_edge, area, min(bw, bh), bh, kd_c, kd_m, k_ax, cf + cr)


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
