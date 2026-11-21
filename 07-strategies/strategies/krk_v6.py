"""krk round 6: 2-ply minimax over Box-Shrink + King-Defends-Rook Lyapunov potential + corner mate-in-2."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _rbox(w, h, rf, rr, bf, br):
  f0, f1, cf, df = (0, rf, 0, 1) if bf < rf else ((rf + 1, w, w - 1, -1) if bf > rf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
  r0, r1, cr, dr = (0, rr, 0, 1) if br < rr else ((rr + 1, h, h - 1, -1) if br > rr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
  return f1 - f0, r1 - r0, cf, cr, df, dr


def _m1(pos):
  for m, nxt in rules.legal_transitions(pos):
    if rules.in_check(nxt) and not rules.legal_moves(nxt):
      return m
  return None


def _pot(pos):
  if "R" not in pos.board:
    return (99, 99, 99, 999, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  area = bw * bh
  # Rook is vulnerable on next move if k is adjacent to R and K does not defend R
  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0
  # Avoid trapping K on k's edge when k is pinned to a 1-wide edge strip
  k_edge = 1 if ((bw == 1 and kf == cf) or (bh == 1 and kr == cr)) else 0
  # Ideal King target:
  if bw == 1:
    tf, tr = cf + 2 * df, min(h - 1, max(0, cr + dr))
  elif bh == 1:
    tf, tr = min(w - 1, max(0, cf + df)), cr + 2 * dr
  else:
    # Support square behind R to defend R and its inward shrink square!
    if bw >= bh and 0 <= rr + dr < h:
      tf, tr = rf - df, rr + dr
    elif 0 <= rf + df < w:
      tf, tr = rf + df, rr - dr
    else:
      tf, tr = bf, br
  kd_c = max(abs(kf - tf), abs(kr - tr))
  kd_m = abs(kf - tf) + abs(kr - tr)
  k_bk = max(abs(kf - bf), abs(kr - br))
  # Keep k pushed toward corner
  bk_c = abs(bf - cf) + abs(br - cr)
  return (0, r_hang, k_edge, area, min(bw, bh), kd_c, kd_m, k_bk, bk_c)


def move(pos):
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  bf, br = _f(pos, "k")
  trans = rules.legal_transitions(pos)

  # Fast mate in 1, collect non-stalemate moves with replies
  cands = []
  for m, nxt in trans:
    reps = rules.legal_transitions(nxt)
    if not reps:
      if rules.in_check(nxt):
        return m
      continue
    cands.append((m, nxt, reps))

  # Fast mate in 2 when K is close to k and k is near/on an edge
  if max(abs(kf - bf), abs(kr - br)) <= 3 and (bf <= 1 or bf >= w - 2 or br <= 1 or br >= h - 2):
    for m, nxt, reps in cands:
      if len(reps) <= 3 and all(_m1(rp) is not None for _, rp in reps):
        return m

  best = None
  for m, nxt, reps in cands:
    worst = max(_pot(rp) for _, rp in reps)
    cand = (worst, len(reps), m)
    if best is None or cand < best:
      best = cand
  return best[2] if best is not None else trans[0][0]
