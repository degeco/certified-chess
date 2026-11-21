"""krk round 20: pure 2-ply 1D-vertical-strip (ignore bf while K approaches tr; R flees far to give K tempo)."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _pot(pos):
  if "R" not in pos.board:
    return (99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")

  if rr > br:
    bh, dr, cr, br_d = rr, 1, 0, br
  elif rr < br:
    bh, dr, cr, br_d = h - 1 - rr, -1, h - 1, h - 1 - br
  else:
    bh = h
    dr = 1 if br < h // 2 else -1
    cr = 0 if dr == 1 else h - 1
    br_d = br if dr == 1 else h - 1 - br

  eff_bh = bh
  cage = 1
  if kr == br + 2 * dr and (rr - br) * dr > 0:
    if bf <= 1 and kf == 1 and rf == 2:
      eff_bh = min(bh, br_d + 1)
      cage = 0
    elif bf >= w - 2 and kf == w - 2 and rf == w - 3:
      eff_bh = min(bh, br_d + 1)
      cage = 0

  r_hang = 1 if (max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1) else 0
  if eff_bh <= h - 2:
    tr = cr + (eff_bh + 1) * dr
    k_side = 0 if (kr - (cr + eff_bh * dr)) * dr > 0 else 1
  else:
    # Strip too tall (eff_bh >= h - 1): R needs to flip to the other side of k; bring K toward R's flip rank.
    tr = br - dr
    k_side = 1
  k_rank_d = abs(kr - tr)
  k_blocks_r = 1 if (k_side == 1 and ((rf < kf < bf) or (bf < kf < rf))) else 0

  r_far = 0 if abs(rf - bf) >= 2 else 1
  push_ready = 0 if (
      r_far == 0
      and (
          (eff_bh < h and br_d < eff_bh - 1)
          or (
              rr == br + dr
              and kr == br + 2 * dr
              and (kf == bf or (bf == 0 and kf == 1) or (bf == w - 1 and kf == w - 2))
          )
      )
  ) else 1

  tf = min(w - 2, bf + 1)
  k_file_d = abs(kf - tf)
  r_dist_pen = -abs(rf - bf)

  # Only herd bf once K is on the opposition rank tr! While K is walking to tr, keep R far so k can't chase R.
  if k_side == 0 and k_rank_d == 0:
    return (0, eff_bh, push_ready, cage, 0, 0, 0, bf, k_file_d, r_hang, r_far, r_dist_pen)
  return (0, eff_bh, push_ready, cage, k_side, k_rank_d, k_blocks_r, r_hang, r_far, r_dist_pen, k_file_d, 0)


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
