"""kqk round 4: strict-subset Q box shrink (non-check + forced-shrink check) + non-edge K target."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _ch(a, b, c, d):
  return max(abs(a - c), abs(b - d))


def _mh(a, b, c, d):
  return abs(a - c) + abs(b - d)


def _box(w, h, qf, qr, bf, br):
  f0, f1, cf, df = (0, qf, 0, 1) if bf < qf else ((qf + 1, w, w - 1, -1) if bf > qf else ((0, w, 0, 1) if bf < w // 2 else (0, w, w - 1, -1)))
  r0, r1, cr, dr = (0, qr, 0, 1) if br < qr else ((qr + 1, h, h - 1, -1) if br > qr else ((0, h, 0, 1) if br < h // 2 else (0, h, h - 1, -1)))
  fr = sum(1 for f in range(f0, f1) for r in range(r0, r1) if f != qf and r != qr and abs(f - qf) != abs(r - qr))
  return f1 - f0, r1 - r0, fr, cf, cr, df, dr


def _m1(pos):
  for m, nxt in rules.legal_transitions(pos):
    if rules.in_check(nxt) and not rules.legal_moves(nxt):
      return m
  return None


def move(pos):
  w, h = pos.width, pos.height
  kf, kr = _f(pos, "K")
  qf, qr = _f(pos, "Q")
  bf, br = _f(pos, "k")
  tr_all = rules.legal_transitions(pos)
  safe = []
  for m, nxt in tr_all:
    reps = rules.legal_transitions(nxt)
    chk = rules.in_check(nxt)
    if not reps:
      if chk:
        return m
      continue
    nkf, nkr = _f(nxt, "K")
    nqf, nqr = _f(nxt, "Q")
    if _ch(nqf, nqr, bf, br) <= 1 and _ch(nqf, nqr, nkf, nkr) > 1:
      continue
    safe.append((m, reps, chk, nkf, nkr, nqf, nqr))

  if _ch(kf, kr, bf, br) <= 3:
    for m, reps, *_ in safe:
      if len(reps) <= 3 and all(_m1(rp) is not None for _, rp in reps):
        return m

  bw, bh, cfr, cf, cr, df, dr = _box(w, h, qf, qr, bf, br)
  ca = bw * bh
  tf, tr = (cf + 2 * df, cr + dr) if bw == 1 else ((cf + df, cr + 2 * dr) if bh == 1 else (cf + 2 * df, cr + 2 * dr))
  qm = [x for x in safe if (x[5], x[6]) != (qf, qr)]
  km = [x for x in safe if (x[3], x[4]) != (kf, kr)]

  def sub(nqf, nqr, rbf, rbr, nkf, nkr):
    nbw, nbh, fr, ncf, ncr, _, _ = _box(w, h, nqf, nqr, rbf, rbr)
    a = nbw * nbh
    if (bw == w or ncf == cf) and (bh == h or ncr == cr) and nbw <= bw and nbh <= bh and a < ca and fr >= 2:
      if not ((nbw == 1 and nkf == ncf) or (nbh == 1 and nkr == ncr)):
        return a, fr
    return None

  cs = []
  for m, reps, chk, nkf, nkr, nqf, nqr in qm:
    d = _mh(nqf, nqr, bf, br)
    if not chk:
      r = sub(nqf, nqr, bf, br, nkf, nkr)
      if r:
        cs.append(((1, -r[0], -r[1], -d, m), m))
    else:
      vs = [sub(nqf, nqr, *_f(rp, "k"), nkf, nkr) for _, rp in reps]
      if all(vs):
        cs.append(((0, -max(v[0] for v in vs), -len(reps), -d, m), m))
  if cs:
    return max(cs)[1]

  if cfr < 2:
    cs = [((-(nbw * nbh), -fr, m), m) for m, _, chk, _, _, nqf, nqr in qm if not chk for nbw, nbh, fr, *_ in [_box(w, h, nqf, nqr, bf, br)] if fr >= 2]
    if cs:
      return max(cs)[1]

  ck = (_ch(kf, kr, tf, tr), _mh(kf, kr, tf, tr))
  cs = [((-nk[0], -nk[1], -_ch(nkf, nkr, bf, br), m), m) for m, _, _, nkf, nkr, _, _ in km for nk in [(_ch(nkf, nkr, tf, tr), _mh(nkf, nkr, tf, tr))] if nk < ck]
  if cs:
    return max(cs)[1]

  if (bw == 1 and kf == cf) or (bh == 1 and kr == cr):
    cs = [((-_mh(nkf, nkr, tf, tr), m), m) for m, _, _, nkf, nkr, _, _ in km if (bw == 1 and nkf != cf) or (bh == 1 and nkr != cr)]
    if cs:
      return max(cs)[1]
    cs = []
    for m, reps, chk, nkf, nkr, nqf, nqr in qm:
      nbw, nbh, fr, *_ = _box(w, h, nqf, nqr, bf, br)
      same = (bw == 1 and nbw == 1) or (bh == 1 and nbh == 1)
      far = 1 if _ch(nqf, nqr, nkf, nkr) > 1 else 0
      cs.append(((1 if (same and not chk and fr >= 2 and far) else 0, 1 if (chk and far) else 0, far, -(nbw * nbh), -len(reps), m), m))
    if cs:
      return max(cs)[1]

  if safe:
    return max(((-len(reps), -_ch(nkf, nkr, bf, br), 1 if chk else 0, m), m) for m, reps, chk, nkf, nkr, _, _ in safe)[1]
  return tr_all[0][0]
