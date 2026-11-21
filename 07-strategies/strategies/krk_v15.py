"""krk round 15: pure 2-ply minimax over 1D-vertical-strip + fixed-left-herd + corner-push potential."""

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

  # Vertical strip only (never flip to horizontal axis!)
  if rr > br:
    bh, dr, cr, br_d = rr, 1, 0, br
  elif rr < br:
    bh, dr, cr, br_d = h - 1 - rr, -1, h - 1, h - 1 - br
  else:
    bh = h
    dr = 1 if br < h // 2 else -1
    cr = 0 if dr == 1 else h - 1
    br_d = br if dr == 1 else h - 1 - br

  # Effective strip height: if k is in a 2-wide left/right corner cage with K on br+2*dr covering escape rank,
  # lifting R along file 2 (or w-3) keeps k confined to br_d + 1 ranks!
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
  # When eff_bh >= h - 1, R must cut from the other side first; otherwise tr = cr + (eff_bh + 1)*dr is on board.
  if eff_bh <= h - 2:
    tr = cr + (eff_bh + 1) * dr
    k_side = 0 if (kr - (cr + eff_bh * dr)) * dr > 0 else 1
  else:
    tr = cr + 2 * dr
    k_side = 1
  k_rank_d = abs(kr - tr)

  # Direct push-ready: on next turn R checks on rank br and strictly shrinks eff_bh (or mates if br == cr)!
  r_far = 0 if abs(rf - bf) >= 2 else 1
  push_ready = 0 if (
      rr == br + dr
      and kr == br + 2 * dr
      and r_far == 0
      and (kf == bf or (bf == 0 and kf == 1) or (bf == w - 1 and kf == w - 2))
  ) else 1

  # Always herd k strictly LEFT toward bf == 0 with K at tf = min(w - 2, bf + 1)!
  # Exception: if k is at w - 1, K at w - 2 is already push_ready when R is far (rf <= w - 3).
  tf = min(w - 2, bf + 1)
  k_file_d = abs(kf - tf)
  r_dist_pen = -abs(rf - bf)

  # Order:
  # 1. eff_bh (primary strip shrink down to 1, then mate!)
  # 2. push_ready (0 => immediate check-shrink / mate next move!)
  # 3. cage (0 => 2-wide corner cage forcing bf -> 0 -> push_ready!)
  # 4. k_side, k_rank_d (bring K onto rank tr = rr + dr!)
  # 5. r_hang (keep R safe)
  # 6. br_d (if k drops below rr-dr, prefer it)
  # 7. bf (herd k strictly left toward 0!)
  # 8. k_file_d (K to bf + 1)
  # 9. r_far, r_dist_pen (keep R far from k along rank rr)
  return (0, eff_bh, push_ready, cage, k_side, k_rank_d, r_hang, br_d, bf, k_file_d, r_far, r_dist_pen)


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
