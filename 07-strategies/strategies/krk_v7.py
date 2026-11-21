"""krk round 7: pure 2-ply minimax over 1D-rank-herding Lyapunov potential."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _pot(pos):
  if "R" not in pos.board:
    return (99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")

  if rr > br:
    bh, dr, br_d = rr, 1, br
  elif rr < br:
    bh, dr, br_d = h - 1 - rr, -1, h - 1 - br
  else:
    bh = h
    dr = 1 if br < h // 2 else -1
    br_d = br if dr == 1 else h - 1 - br

  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0
  r_gap = 0 if rr == br + dr else 1
  k_side = 0 if (kr - rr) * dr > 0 else 1
  tr = min(h - 1, max(0, br + 2 * dr))
  k_rank = abs(kr - tr)
  r_far = 0 if abs(rf - bf) >= 2 else 1
  in_opp = 0 if (kf == bf and kr == br + 2 * dr and rr == br + dr and r_far == 0) else 1

  if kf > bf:
    herd, tf = bf, bf + 1
  elif kf < bf:
    herd, tf = w - 1 - bf, bf - 1
  else:
    herd, tf = min(bf, w - 1 - bf), bf
  k_file = abs(kf - tf)
  return (0, r_hang, bh, br_d, r_gap, k_side, k_rank, in_opp, herd, k_file, r_far)


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
