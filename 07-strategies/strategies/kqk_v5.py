"""kqk round 5 (fixed): 2-ply minimax over a single Lyapunov potential (free squares exclude K attacks)."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _box(w, h, qf, qr, bf, br, kf, kr):
  f0, f1, cf, df = (0, qf, 0, 1) if bf < qf else ((qf + 1, w, w - 1, -1) if bf > qf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
  r0, r1, cr, dr = (0, qr, 0, 1) if br < qr else ((qr + 1, h, h - 1, -1) if br > qr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
  fr = sum(
      1
      for f in range(f0, f1)
      for r in range(r0, r1)
      if f != qf and r != qr and abs(f - qf) != abs(r - qr) and max(abs(f - kf), abs(r - kr)) > 1
  )
  return f1 - f0, r1 - r0, fr, cf, cr, df, dr


def _pot(pos):
  if "Q" not in pos.board:
    return (99, 99, 99, 999, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  qf, qr = _f(pos, "Q")
  bf, br = _f(pos, "k")
  bw, bh, fr, cf, cr, df, dr = _box(w, h, qf, qr, bf, br, kf, kr)
  area = bw * bh
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0
  trap = 1 if fr < 2 else 0
  tf, tr = (cf + 2 * df, cr + dr) if bw <= bh else (cf + df, cr + 2 * dr)
  kd_c = max(abs(kf - tf), abs(kr - tr))
  kd_m = abs(kf - tf) + abs(kr - tr)
  k_bk = max(abs(kf - bf), abs(kr - br))
  return (0, k_edge, trap, area, min(bw, bh), kd_c, kd_m, k_bk)


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
