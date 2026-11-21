"""krk round 4: 2-ply minimax over 1D-strip Lyapunov potential + exact Knight-opposition waiting move."""

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
    return (99, 99, 99, 99, 99, 99, 99, 99)
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  # Focus strictly on the tighter 1D cut!
  if bw <= bh:
    strip = bw
    k_edge = bf if df == 1 else w - 1 - bf
    tf = bf + 2 * df
    in_b = 0 <= tf < w
    if not in_b:
      # Strip too wide (> w-2); flip will reduce strip on next step
      tf = min(w - 1, max(0, bf - 2 * df))
    # Target rank: push k toward rank 0 (keep K at br+1, or br-1 if br == h-1)
    tr = br + 1 if br < h - 1 else h - 2
    opp = 0 if (in_b and kf == tf and kr == br and rf == bf + df) else 1
    k_file_d = abs(kf - tf)
    k_rank_d = abs(kr - tr)
    # Distance of k to bottom edge (0), unless br == h-1 where K sits below
    k_corner = br
    r_cut_gap = abs(rf - (bf + df))
    r_safe = 0 if (abs(rr - br) >= 2 or max(abs(rf - kf), abs(rr - kr)) <= 1) else 1
  else:
    strip = bh
    k_edge = br if dr == 1 else h - 1 - br
    tr = br + 2 * dr
    in_b = 0 <= tr < h
    if not in_b:
      tr = min(h - 1, max(0, br - 2 * dr))
    tf = bf + 1 if bf < w - 1 else w - 2
    opp = 0 if (in_b and kr == tr and kf == bf and rr == br + dr) else 1
    k_file_d = abs(kr - tr)
    k_rank_d = abs(kf - tf)
    k_corner = bf
    r_cut_gap = abs(rr - (br + dr))
    r_safe = 0 if (abs(rf - bf) >= 2 or max(abs(rf - kf), abs(rr - kr)) <= 1) else 1

  return (0, strip, k_edge, opp, r_cut_gap, k_file_d, k_corner, k_rank_d, r_safe)


def move(pos):
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  trans = rules.legal_transitions(pos)

  # Evaluate 2-ply minimax over _pot
  best = None
  safe_wait = []
  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  cut_v = bw <= bh

  for m, nxt in trans:
    reps = rules.legal_transitions(nxt)
    chk = rules.in_check(nxt)
    if not reps:
      if chk:
        return m
      continue
    worst = max(_pot(rp) for _, rp in reps)
    if worst[0] == 99:
      continue
    cand = (worst, len(reps), m)
    if best is None or cand < best:
      best = cand

    # Collect safe Rook waiting moves on the cutting line
    nrf, nrr = _f(nxt, "R")
    if (nrf, nrr) != (rf, rr) and not chk:
      if (cut_v and nrf == rf) or ((not cut_v) and nrr == rr):
        safe_wait.append((worst, abs(nrf - bf) + abs(nrr - br), m))

  # If in exact Knight's opposition on the cut line (kf==tf, kr==tr) and waiting move keeps strip, wait!
  if cut_v:
    tf = bf + 2 * df
    tr = br + 1 if br < h - 1 else h - 2
    if 0 <= tf < w and kf == tf and kr == tr and rf == bf + df and safe_wait:
      # Pick waiting move minimizing worst potential, preferring Rook far from k
      wbest = min(safe_wait, key=lambda x: (x[0][:4], -x[1], x[2]))
      if wbest[0][1] <= bw:
        return wbest[2]
  else:
    tr = br + 2 * dr
    tf = bf + 1 if bf < w - 1 else w - 2
    if 0 <= tr < h and kr == tr and kf == tf and rr == br + dr and safe_wait:
      wbest = min(safe_wait, key=lambda x: (x[0][:4], -x[1], x[2]))
      if wbest[0][1] <= bh:
        return wbest[2]

  return best[2] if best is not None else trans[0][0]
