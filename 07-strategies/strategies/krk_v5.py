"""krk round 5: textbook deterministic 1D-strip cut + opposition push + Rook waiting move."""

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


def move(pos):
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  rf, rr = _f(pos, "R")
  bf, br = _f(pos, "k")
  trans = rules.legal_transitions(pos)

  safe = []
  for m, nxt in trans:
    reps = rules.legal_transitions(nxt)
    chk = rules.in_check(nxt)
    if not reps:
      if chk:
        return m
      continue
    nkf, nkr = _f(nxt, "K")
    nrf, nrr = _f(nxt, "R")
    if max(abs(nrf - bf), abs(nrr - br)) <= 1 and max(abs(nrf - nkf), abs(nrr - nkr)) > 1:
      continue
    safe.append((m, reps, chk, nkf, nkr, nrf, nrr))

  # Rule 0: Fast mate-in-2 on edge when K is close
  on_edge = bf == 0 or bf == w - 1 or br == 0 or br == h - 1
  if on_edge and max(abs(kf - bf), abs(kr - br)) <= 3:
    for m, reps, *_ in safe:
      if len(reps) <= 2 and all(_m1(rp) is not None for _, rp in reps):
        return m

  bw, bh, cf, cr, df, dr = _rbox(w, h, rf, rr, bf, br)
  cur_min = min(bw, bh)
  cut_v = bw <= bh
  rm = [x for x in safe if (x[5], x[6]) != (rf, rr)]
  km = [x for x in safe if (x[3], x[4]) != (kf, kr)]

  # Helper: farthest safe Rook move along current cut line
  def rook_far_on_cut():
    cs = []
    for m, _, chk, _, _, nrf, nrr in rm:
      if chk:
        continue
      if cut_v and nrf == rf:
        cs.append(((abs(nrr - br), -abs(nrr - rr), m), m))
      elif (not cut_v) and nrr == rr:
        cs.append(((abs(nrf - bf), -abs(nrf - rf), m), m))
    return max(cs)[1] if cs else None

  # Rule 1: Emergency Rook safety if currently hanging
  if max(abs(rf - bf), abs(rr - br)) <= 1 and max(abs(rf - kf), abs(rr - kr)) > 1:
    m = rook_far_on_cut()
    if m:
      return m
    cs = []
    for m, _, chk, nkf, nkr, nrf, nrr in safe:
      nbw, nbh, *_ = _rbox(w, h, nrf, nrr, bf, br)
      cs.append(((-min(nbw, nbh), abs(nrf - bf) + abs(nrr - br), m), m))
    if cs:
      return max(cs)[1]

  # Rule 2: Immediate strict reduction of min(bw, bh) via a safe non-checking Rook move!
  # Prefer keeping R at distance >= 2 along the cut line so k cannot bounce R immediately.
  cs = []
  for m, _, chk, nkf, nkr, nrf, nrr in rm:
    if chk:
      continue
    nbw, nbh, *_ = _rbox(w, h, nrf, nrr, bf, br)
    nmin = min(nbw, nbh)
    if nmin < cur_min:
      dist = max(abs(nrf - bf), abs(nrr - br))
      cs.append(((-nmin, 1 if dist >= 2 else 0, abs(nrf - bf) + abs(nrr - br), m), m))
  if cs:
    return max(cs)[1]

  # If cut is too wide (tf off board) or gap exists but R couldn't shrink directly because |rr-br|<=1,
  # slide R to the far end of the board along its current line so it can shrink on the next turn!
  if cut_v:
    tf = bf + 2 * df
    gap = rf != bf + df
    too_wide = not (0 <= tf < w)
    if (gap or too_wide) and abs(rr - br) <= 1:
      m = rook_far_on_cut()
      if m:
        return m
    # Rule 3: Direct opposition push!
    if 0 <= tf < w and kf == tf and kr == br and rf == bf + df:
      pcs = [((abs(nrr - br), m), m) for m, _, chk, _, _, nrf, nrr in rm if chk and nrf == bf]
      if pcs:
        return max(pcs)[1]
      # R too close to k (|rr - br| == 1): move R far along file rf!
      m = rook_far_on_cut()
      if m:
        return m
    # Rule 4: King positioning & Knight-opposition Rook waiting move
    if 0 <= tf < w:
      if kf == tf and abs(kr - br) == 1 and rf == bf + df:
        # Play a safe Rook waiting move on file rf (preferring |nrr - br| >= 2, else defended by K!)
        wcs = []
        for m, _, chk, _, _, nrf, nrr in rm:
          if nrf == rf and not chk:
            far = 1 if abs(nrr - br) >= 2 else 0
            # Prefer toggling to a square with |nrr - br| >= 2, closest to far end
            wcs.append(((far, abs(nrr - br), -abs(nrr - rr), m), m))
        if wcs:
          return max(wcs)[1]
      tr = br
    else:
      tf = min(w - 1, max(0, bf - 2 * df))
      tr = br
  else:
    tr = br + 2 * dr
    gap = rr != br + dr
    too_wide = not (0 <= tr < h)
    if (gap or too_wide) and abs(rf - bf) <= 1:
      m = rook_far_on_cut()
      if m:
        return m
    if 0 <= tr < h and kr == tr and kf == bf and rr == br + dr:
      pcs = [((abs(nrf - bf), m), m) for m, _, chk, _, _, nrf, nrr in rm if chk and nrr == br]
      if pcs:
        return max(pcs)[1]
      m = rook_far_on_cut()
      if m:
        return m
    if 0 <= tr < h:
      if kr == tr and abs(kf - bf) == 1 and rr == br + dr:
        wcs = []
        for m, _, chk, _, _, nrf, nrr in rm:
          if nrr == rr and not chk:
            far = 1 if abs(nrf - bf) >= 2 else 0
            wcs.append(((far, abs(nrf - bf), -abs(nrf - rf), m), m))
        if wcs:
          return max(wcs)[1]
      tf = bf
    else:
      tr = min(h - 1, max(0, br - 2 * dr))
      tf = bf

  # Walk White King strictly closer to (tf, tr)
  cur_kd = (abs(kf - tf) if cut_v else abs(kr - tr), max(abs(kf - tf), abs(kr - tr)), abs(kf - tf) + abs(kr - tr))
  kcs = []
  for m, _, _, nkf, nkr, _, _ in km:
    nkd = (abs(nkf - tf) if cut_v else abs(nkr - tr), max(abs(nkf - tf), abs(nkr - tr)), abs(nkf - tf) + abs(nkr - tr))
    if nkd < cur_kd:
      kcs.append(((-nkd[0], -nkd[1], -nkd[2], m), m))
  if kcs:
    return max(kcs)[1]

  # If K is blocked by R from reaching (tf, tr), step K around R or slide R out of the way along the cut line
  m = rook_far_on_cut()
  if m:
    return m
  if safe:
    return max(((-len(reps), abs(nrf - bf) + abs(nrr - br), m), m) for m, reps, _, _, _, nrf, nrr in safe)[1]
  return trans[0][0]
