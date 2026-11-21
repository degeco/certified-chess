"""kqk_lia: pure LIA potential _pot and explicit LIA witness rule hint(pos) for KQK (W, H >= 4)."""

import rules


def _f(p, c):
  i = p.board.index(c)
  return i % p.width, i // p.width


def _sfree(n, qs, qp, kn, kp):
  lq = max(0, qp - 1) if qs == 1 else max(0, n - 1)
  hq = min(n - 1, qp + 1) if qs == 1 else n - 1
  qc = max(0, hq - lq + 1)
  if kn == 0:
    return n - qc
  lk = max(0, kp - 1)
  hk = min(n - 1, kp + 1)
  kc = max(0, hk - lk + 1)
  ov = max(0, min(hq, hk) - max(lq, lk) + 1)
  return n - qc - kc + ov


def _far(f, r, kf, kr):
  return 1 if max(abs(f - kf), abs(r - kr)) > 1 else 0


def _norm(w, h, kf, kr, qf, qr, bf, br):
  fh = 1 if (bf > qf or (bf == qf and bf >= w // 2)) else 0
  fv = 1 if (br > qr or (br == qr and br >= h // 2)) else 0
  nkf = w - 1 - kf if fh == 1 else kf
  nkr = h - 1 - kr if fv == 1 else kr
  nqf = w - 1 - qf if fh == 1 else qf
  nqr = h - 1 - qr if fv == 1 else qr
  nbf = w - 1 - bf if fh == 1 else bf
  nbr = h - 1 - br if fv == 1 else br
  vb = nkf == nqf and nkr < nqr and nbf == nqf - 1 and (nkr >= nbr + 2 or (nkr == nbr + 1 and nbr >= 1))
  hb = nkr == nqr and nkf < nqf and nbr == nqr - 1 and (nkf >= nbf + 2 or (nkf == nbf + 1 and nbf >= 1))
  bw = nqf if (nbf < nqf and not vb) else w
  bh = nqr if (nbr < nqr and not hb) else h
  return fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh


def _pot_lia(w, h, kf, kr, qf, qr, bf, br):
  fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh = _norm(w, h, kf, kr, qf, qr, bf, br)
  ke = 1 if ((bw == 1 and nkf == 0) or (bh == 1 and nkr == 0)) else 0
  if bw == 1:
    trp = 1 if _sfree(bh, 1 if nbr == nqr else 0, nqr, 1 if nkf <= 1 else 0, nkr) < 2 else 0
  elif bh == 1:
    trp = 1 if _sfree(bw, 1 if nbf == nqf else 0, nqf, 1 if nkr <= 1 else 0, nkf) < 2 else 0
  elif bw == 2 and bh == 2:
    trp = 1 if (_far(0, 1, nkf, nkr) + _far(1, 0, nkf, nkr)) < 2 else 0
  elif bw == 2 and bh == 3:
    trp = 1 if (_far(0, 0, nkf, nkr) + _far(1, 0, nkf, nkr) + _far(0, 2, nkf, nkr) + _far(1, 1, nkf, nkr)) < 2 else 0
  elif bw == 3 and bh == 2:
    trp = 1 if (_far(0, 0, nkf, nkr) + _far(0, 1, nkf, nkr) + _far(2, 0, nkf, nkr) + _far(1, 1, nkf, nkr)) < 2 else 0
  elif bw == 2 and bh >= 4:
    trp = 1 if (nbr >= bh - 2 and max(abs(nkf - 1), abs(nkr - (bh - 2))) <= 1 and not (nkf == 2 and nkr >= bh - 2)) else 0
  elif bh == 2 and bw >= 4:
    trp = 1 if (nbf >= bw - 2 and max(abs(nkr - 1), abs(nkf - (bw - 2))) <= 1 and not (nkr == 2 and nkf >= bw - 2)) else 0
  else:
    trp = 0
  tf = 2 if bw == 1 else (nqf - 1 if bh == 1 else nqf)
  tr = nqr - 1 if bw == 1 else (2 if bh == 1 else nqr)
  kc = max(abs(nkf - tf), abs(nkr - tr))
  km = abs(nkf - tf) + abs(nkr - tr)
  ka = nkr if bh < bw else nkf
  cc = (w - 1 if fh == 1 else 0) + (h - 1 if fv == 1 else 0)
  return (0, trp, bw + bh, min(bw, bh), ke, bh, kc, km, ka, cc)


def _pot(pos):
  if "Q" not in pos.board:
    return (99, 99, 99, 99, 99, 99, 99, 99, 99, 99)
  kf, kr = _f(pos, "K")
  qf, qr = _f(pos, "Q")
  bf, br = _f(pos, "k")
  return _pot_lia(pos.width, pos.height, kf, kr, qf, qr, bf, br)


def _btwn(f1, r1, mf, mr, f2, r2):
  if f1 == f2 and mf == f1 and ((r1 < mr and mr < r2) or (r2 < mr and mr < r1)):
    return 1
  if r1 == r2 and mr == r1 and ((f1 < mf and mf < f2) or (f2 < mf and mf < f1)):
    return 1
  if f2 - f1 == r2 - r1 and mf - f1 == mr - r1 and ((f1 < mf and mf < f2) or (f2 < mf and mf < f1)):
    return 1
  if f2 - f1 == r1 - r2 and mf - f1 == r1 - mr and ((f1 < mf and mf < f2) or (f2 < mf and mf < f1)):
    return 1
  return 0


def _qatk(qf, qr, tf, tr, kf, kr):
  if (qf == tf and qr == tr) or not (qf == tf or qr == tr or abs(qf - tf) == abs(qr - tr)):
    return 0
  return 0 if _btwn(qf, qr, kf, kr, tf, tr) == 1 else 1


def _rep(w, h, kf, kr, qf, qr, bf, br, df, dr, p0):
  nf, nr = bf + df, br + dr
  if nf < 0 or nf >= w or nr < 0 or nr >= h or max(abs(nf - kf), abs(nr - kr)) < 2:
    return 0, 1
  if nf == qf and nr == qr:
    return 1, 0
  if _qatk(qf, qr, nf, nr, kf, kr) == 1:
    return 0, 1
  return 1, (1 if _pot_lia(w, h, kf, kr, qf, qr, nf, nr) < p0 else 0)


def _good(w, h, kf, kr, qf, qr, bf, br, p0, ik, tf, tr):
  if tf < 0 or tf >= w or tr < 0 or tr >= h:
    return 0
  if ik == 1:
    if max(abs(tf - kf), abs(tr - kr)) != 1 or (tf == qf and tr == qr) or max(abs(tf - bf), abs(tr - br)) < 2:
      return 0
    k1, r1, q1, s1 = tf, tr, qf, qr
  else:
    if (tf == qf and tr == qr) or (tf == kf and tr == kr) or (tf == bf and tr == br):
      return 0
    if not (tf == qf or tr == qr or abs(tf - qf) == abs(tr - qr)):
      return 0
    if _btwn(qf, qr, kf, kr, tf, tr) == 1 or _btwn(qf, qr, bf, br, tf, tr) == 1:
      return 0
    k1, r1, q1, s1 = kf, kr, tf, tr
  l0, d0 = _rep(w, h, k1, r1, q1, s1, bf, br, -1, -1, p0)
  l1, d1 = _rep(w, h, k1, r1, q1, s1, bf, br, -1, 0, p0)
  l2, d2 = _rep(w, h, k1, r1, q1, s1, bf, br, -1, 1, p0)
  l3, d3 = _rep(w, h, k1, r1, q1, s1, bf, br, 0, -1, p0)
  l4, d4 = _rep(w, h, k1, r1, q1, s1, bf, br, 0, 1, p0)
  l5, d5 = _rep(w, h, k1, r1, q1, s1, bf, br, 1, -1, p0)
  l6, d6 = _rep(w, h, k1, r1, q1, s1, bf, br, 1, 0, p0)
  l7, d7 = _rep(w, h, k1, r1, q1, s1, bf, br, 1, 1, p0)
  any_r = l0 + l1 + l2 + l3 + l4 + l5 + l6 + l7
  if any_r == 0:
    return _qatk(q1, s1, bf, br, k1, r1)
  return 1 if (d0 + d1 + d2 + d3 + d4 + d5 + d6 + d7) == 8 else 0


def _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, ik, ntf, ntr):
  tf = w - 1 - ntf if fh == 1 else ntf
  tr = h - 1 - ntr if fv == 1 else ntr
  if _good(w, h, kf, kr, qf, qr, bf, br, p0, ik, tf, tr) == 1:
    return 1, (kf if ik == 1 else qf), (kr if ik == 1 else qr), tf, tr
  return 0, 0, 0, 0, 0


def _try_k(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, nkf, nkr):
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf + 1, nkr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf - 1, nkr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf, nkr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf, nkr - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf + 1, nkr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf - 1, nkr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 1, nkf + 1, nkr - 1)
  if ok == 1: return a, b, c, d
  return kf, kr, (w - 1 - (nkf - 1) if fh == 1 else nkf - 1), (h - 1 - (nkr - 1) if fv == 1 else nkr - 1)


def _hint_lia(w, h, kf, kr, qf, qr, bf, br):
  p0 = _pot_lia(w, h, kf, kr, qf, qr, bf, br)
  fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh = _norm(w, h, kf, kr, qf, qr, bf, br)
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf - 1, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, nqr - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf - 1, nqr - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf - 1, nqr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf + 1, nqr - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, nbr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nbf, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 0, nbr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nbf, 0)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, 3)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 3, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 2, 2)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, nbr - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nbf - 1, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nbf + 2, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, nbr + 2)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nbf + 1, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, nbr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, h - 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, w - 1, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, 2)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 2, 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf + 1, nqr)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, nqf, nqr + 1)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 2, 3)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 3, 2)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 1, 4)
  if ok == 1: return a, b, c, d
  ok, a, b, c, d = _try(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, 0, 4, 1)
  if ok == 1: return a, b, c, d
  return _try_k(w, h, kf, kr, qf, qr, bf, br, p0, fh, fv, nkf, nkr)


def hint(pos):
  kf, kr = _f(pos, "K")
  qf, qr = _f(pos, "Q")
  bf, br = _f(pos, "k")
  sf, sr, tf, tr = _hint_lia(pos.width, pos.height, kf, kr, qf, qr, bf, br)
  return rules.square_name(sf, sr) + rules.square_name(tf, tr)


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
