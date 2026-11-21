#!/usr/bin/env python3
"""Z3 symbolic proof of KQK winning strategy (kqk_lia) for all board sizes W >= 4, H >= 4.

Encodes:
- Position validity (matching ../03-checker/rules.py)
- White move legality (K and Q)
- All 8 Black king replies and their legality (including capturing undefended Q)
- Pure-LIA potential `_pot_lia` and lower-bound check
- Pure-LIA witness rule `hint` (explicit finite symbolic candidate list)

Usage:
  python3 smt/kqk.py --validate-encoding [--boards 4 5 6] [--jobs 4]
  python3 smt/kqk.py --prove [--quadrants 00 10 01 11] [--jobs 4] [--timeout 30]
  python3 smt/kqk.py --all
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import sys
import time
import z3

BASE_DIR = Path(__file__).resolve().parent.parent
CHECKER_DIR = BASE_DIR.parent / "03-checker"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import rules  # noqa: E402
import harness  # noqa: E402

KING_DIRS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


# ---------------------------------------------------------------------------
# Z3 LIA arithmetic & chess rules encoding
# ---------------------------------------------------------------------------


def z_abs(x: z3.ArithRef) -> z3.ArithRef:
    return z3.If(x >= 0, x, -x)


def z_min(a: z3.ArithRef, b: z3.ArithRef) -> z3.ArithRef:
    return z3.If(a <= b, a, b)


def z_max(a: z3.ArithRef, b: z3.ArithRef) -> z3.ArithRef:
    return z3.If(a >= b, a, b)


def z_cheb(f1: z3.ArithRef, r1: z3.ArithRef, f2: z3.ArithRef, r2: z3.ArithRef) -> z3.ArithRef:
    return z_max(z_abs(f1 - f2), z_abs(r1 - r2))


def z_between_1d(a: z3.ArithRef, mid: z3.ArithRef, b: z3.ArithRef) -> z3.BoolRef:
    return z3.Or(z3.And(a < mid, mid < b), z3.And(b < mid, mid < a))


def z_strictly_between_line(
    f1: z3.ArithRef,
    r1: z3.ArithRef,
    mf: z3.ArithRef,
    mr: z3.ArithRef,
    f2: z3.ArithRef,
    r2: z3.ArithRef,
) -> z3.BoolRef:
    same_file = z3.And(f1 == f2, mf == f1, z_between_1d(r1, mr, r2))
    same_rank = z3.And(r1 == r2, mr == r1, z_between_1d(f1, mf, f2))
    diag_pos = z3.And(f2 - f1 == r2 - r1, mf - f1 == mr - r1, z_between_1d(f1, mf, f2))
    diag_neg = z3.And(f2 - f1 == r1 - r2, mf - f1 == r1 - mr, z_between_1d(f1, mf, f2))
    return z3.Or(same_file, same_rank, diag_pos, diag_neg)


def z_queen_attacks(
    qf: z3.ArithRef,
    qr: z3.ArithRef,
    tf: z3.ArithRef,
    tr: z3.ArithRef,
    bf_blk: z3.ArithRef,
    br_blk: z3.ArithRef,
) -> z3.BoolRef:
    on_line = z3.And(
        z3.Or(qf != tf, qr != tr),
        z3.Or(qf == tf, qr == tr, z_abs(qf - tf) == z_abs(qr - tr)),
    )
    blocked = z_strictly_between_line(qf, qr, bf_blk, br_blk, tf, tr)
    return z3.And(on_line, z3.Not(blocked))


def z_on_board(w: z3.ArithRef, h: z3.ArithRef, f: z3.ArithRef, r: z3.ArithRef) -> z3.BoolRef:
    return z3.And(f >= 0, f < w, r >= 0, r < h)


def z_valid_wtm(
    w: z3.ArithRef,
    h: z3.ArithRef,
    kf: z3.ArithRef,
    kr: z3.ArithRef,
    qf: z3.ArithRef,
    qr: z3.ArithRef,
    bf: z3.ArithRef,
    br: z3.ArithRef,
) -> z3.BoolRef:
    """SPEC v1.2 validity for a White-to-move KQK position."""
    return z3.And(
        z_on_board(w, h, kf, kr),
        z_on_board(w, h, qf, qr),
        z_on_board(w, h, bf, br),
        z3.Or(kf != qf, kr != qr),
        z3.Or(kf != bf, kr != br),
        z3.Or(qf != bf, qr != br),
        z_cheb(kf, kr, bf, br) >= 2,
        z3.Not(z_queen_attacks(qf, qr, bf, br, kf, kr)),
    )


def z_legal_white_move(
    w: z3.ArithRef,
    h: z3.ArithRef,
    kf: z3.ArithRef,
    kr: z3.ArithRef,
    qf: z3.ArithRef,
    qr: z3.ArithRef,
    bf: z3.ArithRef,
    br: z3.ArithRef,
    is_k: int | z3.ArithRef,
    tf: z3.ArithRef,
    tr: z3.ArithRef,
) -> z3.BoolRef:
    k_ok = z3.And(
        z_on_board(w, h, tf, tr),
        z_cheb(kf, kr, tf, tr) == 1,
        z3.Or(tf != qf, tr != qr),
        z_cheb(tf, tr, bf, br) >= 2,
    )
    q_ok = z3.And(
        z_on_board(w, h, tf, tr),
        z3.Or(tf != qf, tr != qr),
        z3.Or(tf != kf, tr != kr),
        z3.Or(tf != bf, tr != br),
        z3.Or(tf == qf, tr == qr, z_abs(tf - qf) == z_abs(tr - qr)),
        z3.Not(z_strictly_between_line(qf, qr, kf, kr, tf, tr)),
        z3.Not(z_strictly_between_line(qf, qr, bf, br, tf, tr)),
    )
    if isinstance(is_k, int):
        return k_ok if is_k == 1 else q_ok
    return z3.If(is_k == 1, k_ok, q_ok)


def z_legal_black_reply(
    w: z3.ArithRef,
    h: z3.ArithRef,
    kf: z3.ArithRef,
    kr: z3.ArithRef,
    qf: z3.ArithRef,
    qr: z3.ArithRef,
    bf: z3.ArithRef,
    br: z3.ArithRef,
    df: int,
    dr: int,
) -> z3.BoolRef:
    nbf = bf + df
    nbr = br + dr
    captures_q = z3.And(nbf == qf, nbr == qr)
    return z3.And(
        z_on_board(w, h, nbf, nbr),
        z_cheb(nbf, nbr, kf, kr) >= 2,
        z3.Or(captures_q, z3.Not(z_queen_attacks(qf, qr, nbf, nbr, kf, kr))),
    )


def z_lex_lt(a: tuple[z3.ArithRef, ...], b: tuple[z3.ArithRef, ...]) -> z3.BoolRef:
    assert len(a) == len(b)
    res = z3.BoolVal(False)
    for ai, bi in reversed(list(zip(a, b))):
        res = z3.Or(ai < bi, z3.And(ai == bi, res))
    return res


# ---------------------------------------------------------------------------
# Z3 encoding of _pot_lia (exact mirror of strategies/kqk_lia.py)
# ---------------------------------------------------------------------------


def z_sfree(n, q_same, q_pos, k_near, k_pos):
    lo_q = z3.If(q_same == 1, z_max(0, q_pos - 1), z_max(0, n - 1))
    hi_q = z3.If(q_same == 1, z_min(n - 1, q_pos + 1), z_min(n - 1, n - 1))
    q_cnt = z_max(0, hi_q - lo_q + 1)
    lo_k = z_max(0, k_pos - 1)
    hi_k = z_min(n - 1, k_pos + 1)
    k_cnt = z_max(0, hi_k - lo_k + 1)
    ov = z_max(0, z_min(hi_q, hi_k) - z_max(lo_q, lo_k) + 1)
    return z3.If(k_near == 0, n - q_cnt, n - q_cnt - k_cnt + ov)


def z_far(f, r, kf, kr):
    return z3.If(z_cheb(f, r, kf, kr) > 1, 1, 0)


def z_norm_box(w, h, kf, kr, qf, qr, bf, br):
    fh = z3.If(z3.Or(bf > qf, z3.And(bf == qf, bf >= w / 2)), 1, 0)
    fv = z3.If(z3.Or(br > qr, z3.And(br == qr, br >= h / 2)), 1, 0)
    nkf = z3.If(fh == 1, w - 1 - kf, kf)
    nkr = z3.If(fv == 1, h - 1 - kr, kr)
    nqf = z3.If(fh == 1, w - 1 - qf, qf)
    nqr = z3.If(fv == 1, h - 1 - qr, qr)
    nbf = z3.If(fh == 1, w - 1 - bf, bf)
    nbr = z3.If(fv == 1, h - 1 - br, br)
    v_brk = z3.And(nkf == nqf, nkr < nqr, nbf == nqf - 1, z3.Or(nkr >= nbr + 2, z3.And(nkr == nbr + 1, nbr >= 1)))
    h_brk = z3.And(nkr == nqr, nkf < nqf, nbr == nqr - 1, z3.Or(nkf >= nbf + 2, z3.And(nkf == nbf + 1, nbf >= 1)))
    bw = z3.If(z3.And(nbf < nqf, z3.Not(v_brk)), nqf, w)
    bh = z3.If(z3.And(nbr < nqr, z3.Not(h_brk)), nqr, h)
    return fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh


def z_pot_lia(w, h, kf, kr, qf, qr, bf, br):
    fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh = z_norm_box(w, h, kf, kr, qf, qr, bf, br)
    k_edge = z3.If(z3.Or(z3.And(bw == 1, nkf == 0), z3.And(bh == 1, nkr == 0)), 1, 0)
    fr_bw1 = z_sfree(bh, z3.If(nbr == nqr, 1, 0), nqr, z3.If(nkf <= 1, 1, 0), nkr)
    fr_bh1 = z_sfree(bw, z3.If(nbf == nqf, 1, 0), nqf, z3.If(nkr <= 1, 1, 0), nkf)
    fr_22 = z_far(0, 1, nkf, nkr) + z_far(1, 0, nkf, nkr)
    fr_23 = z_far(0, 0, nkf, nkr) + z_far(1, 0, nkf, nkr) + z_far(0, 2, nkf, nkr) + z_far(1, 1, nkf, nkr)
    fr_32 = z_far(0, 0, nkf, nkr) + z_far(0, 1, nkf, nkr) + z_far(2, 0, nkf, nkr) + z_far(1, 1, nkf, nkr)
    trap_2g = z3.If(
        z3.And(nbr >= bh - 2, z_cheb(1, bh - 2, nkf, nkr) <= 1, z3.Not(z3.And(nkf == 2, nkr >= bh - 2))),
        1, 0,
    )
    trap_g2 = z3.If(
        z3.And(nbf >= bw - 2, z_cheb(bw - 2, 1, nkf, nkr) <= 1, z3.Not(z3.And(nkr == 2, nkf >= bw - 2))),
        1, 0,
    )
    trap = z3.If(
        bw == 1, z3.If(fr_bw1 < 2, 1, 0),
        z3.If(
            bh == 1, z3.If(fr_bh1 < 2, 1, 0),
            z3.If(
                z3.And(bw == 2, bh == 2), z3.If(fr_22 < 2, 1, 0),
                z3.If(
                    z3.And(bw == 2, bh == 3), z3.If(fr_23 < 2, 1, 0),
                    z3.If(
                        z3.And(bw == 3, bh == 2), z3.If(fr_32 < 2, 1, 0),
                        z3.If(
                            z3.And(bw == 2, bh >= 4), trap_2g,
                            z3.If(z3.And(bh == 2, bw >= 4), trap_g2, 0),
                        ),
                    ),
                ),
            ),
        ),
    )
    tf = z3.If(bw == 1, 2, z3.If(bh == 1, nqf - 1, nqf))
    tr = z3.If(bw == 1, nqr - 1, z3.If(bh == 1, 2, nqr))
    kd_c = z_cheb(nkf, nkr, tf, tr)
    kd_m = z_abs(nkf - tf) + z_abs(nkr - tr)
    k_ax = z3.If(bh < bw, nkr, nkf)
    cf_cr = z3.If(fh == 1, w - 1, 0) + z3.If(fv == 1, h - 1, 0)
    return (z3.IntVal(0), trap, bw + bh, z_min(bw, bh), k_edge, bh, kd_c, kd_m, k_ax, cf_cr)


def z_good_move(w, h, kf, kr, qf, qr, bf, br, pot0, is_k, tf, tr):
    leg_w = z_legal_white_move(w, h, kf, kr, qf, qr, bf, br, is_k, tf, tr)
    kf1 = tf if is_k == 1 else kf
    kr1 = tr if is_k == 1 else kr
    qf1 = qf if is_k == 1 else tf
    qr1 = qr if is_k == 1 else tr
    in_chk = z_queen_attacks(qf1, qr1, bf, br, kf1, kr1)
    rep_leg = []
    rep_dec = []
    for df, dr in KING_DIRS:
        rl = z_legal_black_reply(w, h, kf1, kr1, qf1, qr1, bf, br, df, dr)
        rep_leg.append(rl)
        nbf, nbr = bf + df, br + dr
        cap_q = z3.And(nbf == qf1, nbr == qr1)
        pot1 = z_pot_lia(w, h, kf1, kr1, qf1, qr1, nbf, nbr)
        dec = z3.And(z3.Not(cap_q), z_lex_lt(pot1, pot0))
        rep_dec.append(z3.Implies(rl, dec))
    any_rep = z3.Or(*rep_leg)
    mate = z3.And(in_chk, z3.Not(any_rep))
    progress = z3.And(any_rep, *rep_dec)
    return z3.And(leg_w, z3.Or(mate, progress))


# ---------------------------------------------------------------------------
# Fast parallel encoding validation on 4x4, 5x5, 6x6
# ---------------------------------------------------------------------------


def _validate_encoding_chunk(args: tuple[int, list[int]]) -> tuple[int, int, int, int, int]:
    sz, ki_list = args
    n_sq = sz * sz
    W, H = z3.IntVal(sz), z3.IntVal(sz)
    kf, kr, qf, qr, bf, br = z3.Ints("kf kr qf qr bf br")
    v_var = z3.Bool("v")
    r_vars = [z3.Bool(f"r{i}") for i in range(8)]
    s = z3.Solver()
    s.add(v_var == z_valid_wtm(W, H, kf, kr, qf, qr, bf, br))
    for i, (df, dr) in enumerate(KING_DIRS):
        s.add(r_vars[i] == z_legal_black_reply(W, H, kf, kr, qf, qr, bf, br, df, dr))

    checked_states = 0
    valid_count = 0
    valid_mis = 0
    reply_mis = 0
    reply_dirs = 0

    for ki in ki_list:
        kfv, krv = ki % sz, ki // sz
        for bi in range(n_sq):
            if bi == ki:
                continue
            bfv, brv = bi % sz, bi // sz
            if max(abs(kfv - bfv), abs(krv - brv)) <= 1:
                continue
            for qi in range(n_sq):
                if qi == ki or qi == bi:
                    continue
                qfv, qrv = qi % sz, qi // sz
                board = ["."] * n_sq
                board[ki] = "K"
                board[qi] = "Q"
                board[bi] = "k"
                bt = tuple(board)
                in_check_b = rules.is_square_attacked(bt, sz, sz, bfv, brv, "w")
                rules_valid = not in_check_b
                if rules_valid:
                    valid_count += 1

                btm = rules.Position(sz, sz, bt, "b", "", None)
                rules_targets = set()
                for m_str, _ in rules.legal_transitions(btm):
                    tf, tr = rules.parse_square(m_str[2:4], sz, sz)
                    rules_targets.add((tf - bfv, tr - brv))
                r_expected = [(d in rules_targets) for d in KING_DIRS]

                assumps = [
                    kf == kfv, kr == krv, qf == qfv, qr == qrv, bf == bfv, br == brv,
                    v_var if rules_valid else z3.Not(v_var),
                ]
                for i, exp in enumerate(r_expected):
                    assumps.append(r_vars[i] if exp else z3.Not(r_vars[i]))

                if s.check(*assumps) != z3.sat:
                    # Find which component disagreed
                    if s.check(kf == kfv, kr == krv, qf == qfv, qr == qrv, bf == bfv, br == brv,
                               v_var if rules_valid else z3.Not(v_var)) != z3.sat:
                        valid_mis += 1
                    else:
                        reply_mis += 1
                checked_states += 1
                reply_dirs += 8

    return checked_states, valid_count, valid_mis, reply_dirs, reply_mis


def validate_encoding(boards: tuple[int, ...] = (4, 5, 6), jobs: int = 4) -> bool:
    """Prove exact agreement between Z3 encoding and rules.py on 4x4, 5x5, 6x6."""
    all_ok = True
    for sz in boards:
        t0 = time.perf_counter()
        # First prove in Z3 that z_valid_wtm rejects out-of-bounds, overlapping pieces, and adjacent kings.
        kf, kr, qf, qr, bf, br = z3.Ints("kf kr qf qr bf br")
        s_basic = z3.Solver()
        s_basic.add(z_valid_wtm(z3.IntVal(sz), z3.IntVal(sz), kf, kr, qf, qr, bf, br))
        s_basic.add(
            z3.Not(
                z3.And(
                    0 <= kf, kf < sz, 0 <= kr, kr < sz,
                    0 <= qf, qf < sz, 0 <= qr, qr < sz,
                    0 <= bf, bf < sz, 0 <= br, br < sz,
                    z3.Or(kf != qf, kr != qr),
                    z3.Or(kf != bf, kr != br),
                    z3.Or(qf != bf, qr != br),
                    z_cheb(kf, kr, bf, br) >= 2,
                )
            )
        )
        assert s_basic.check() == z3.unsat, "z_valid_wtm accepted invalid basic constraint"

        n_sq = sz * sz
        workers = max(1, min(4, jobs))
        chunks = [(sz, [ki for ki in range(n_sq) if ki % workers == w_i]) for w_i in range(workers)]
        checked = valid_cnt = valid_mis = reply_dirs = reply_mis = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for c, vc, vm, rd, rm in pool.map(_validate_encoding_chunk, chunks):
                checked += c
                valid_cnt += vc
                valid_mis += vm
                reply_dirs += rd
                reply_mis += rm

        enum_count = len(harness.enumerate_valid_positions("KQK", sz, sz))
        ok_sz = (valid_cnt == enum_count and valid_mis == 0 and reply_mis == 0)
        if not ok_sz:
            all_ok = False
        dt = time.perf_counter() - t0
        print(
            f"ENCODING {sz}x{sz}: valid_z3==rules={valid_cnt}/{enum_count} "
            f"(checked_states={checked}, valid_mismatches={valid_mis}) | "
            f"reply_dir_checks={reply_dirs} (reply_mismatches={reply_mis}) "
            f"| ok={ok_sz} [{dt:.2f}s]"
        )
    return all_ok


# ---------------------------------------------------------------------------
# Symbolic Z3 proof obligations for all W >= 4, H >= 4
# ---------------------------------------------------------------------------

CASE_NAMES = (
    "bw==1,bh<=3",
    "bw==1,bh>=4",
    "bh==1,bw in 2..3",
    "bh==1,bw>=4",
    "bw==2,bh==2",
    "bw==2,bh==3",
    "bw==2,bh>=4",
    "bh==2,bw==3",
    "bh==2,bw>=4",
    "bw>=3,bh>=3,gap",
    "bw>=3,bh>=3,bf_adj",
    "bw>=3,bh>=3,br_adj",
    "bw==w or bh==h",
)


def _case_cond_and_cands(cname: str, w, h, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh):
    k_moves = [(1, nkf + df, nkr + dr) for df, dr in KING_DIRS]
    if cname == "bw==1,bh<=3":
        return z3.And(bw == 1, bh <= 3), [(0, nqf, nqr - 1), (0, 1, nbr), (0, 0, nbr), (0, 1, 3), (0, 2, 2), (0, 1, h - 1), (0, 3, 1), (0, nqf, 1)] + k_moves
    if cname == "bw==1,bh>=4":
        return z3.And(bw == 1, bh >= 4), [(0, nqf, nqr - 1), (0, 1, nbr), (0, 0, nbr), (0, 1, 3), (0, 2, 2), (0, 1, h - 1), (0, 3, 1), (0, nqf, 1)] + k_moves
    if cname == "bh==1,bw in 2..3":
        return z3.And(bh == 1, bw >= 2, bw <= 3), [(0, nqf - 1, nqr), (0, nbf, 1), (0, nbf, 0), (0, 3, 1), (0, 2, 2), (0, w - 1, 1), (0, 1, 3), (0, 1, nqr)] + k_moves
    if cname == "bh==1,bw>=4":
        return z3.And(bh == 1, bw >= 4), [(0, nqf - 1, nqr), (0, nbf, 1), (0, nbf, 0), (0, 3, 1), (0, 2, 2), (0, w - 1, 1), (0, 1, 3), (0, 1, nqr)] + k_moves
    if cname == "bw==2,bh==2":
        return z3.And(bw == 2, bh == 2), [(0, 1, 3), (0, 3, 1), (0, 1, 2), (0, 2, 1), (0, 1, 1), (0, 2, 3), (0, 3, 2)] + k_moves
    if cname == "bw==2,bh==3":
        return z3.And(bw == 2, bh == 3), [(0, 1, 3), (0, 1, 4), (0, 2, 2), (0, 3, 1), (0, 3, 2), (0, 1, nbr), (0, 2, 1)] + k_moves
    if cname == "bw==2,bh>=4":
        return z3.And(bw == 2, bh >= 4, bh < h), [(0, 1, nqr), (0, 1, nqr + 1), (0, 2, nqr - 1), (0, 2, nbr + 1), (0, 2, nbr + 2), (0, 2, nbr - 1), (0, 1, nbr), (0, 2, 2)] + k_moves
    if cname == "bh==2,bw==3":
        return z3.And(bh == 2, bw == 3), [(0, 3, 1), (0, 4, 1), (0, 2, 2), (0, 1, 3), (0, 2, 3), (0, nbf, 1), (0, 1, 2)] + k_moves
    if cname == "bh==2,bw>=4":
        return z3.And(bh == 2, bw >= 4, bw < w), [(0, nqf, 1), (0, nqf + 1, 1), (0, nqf - 1, 2), (0, nbf + 1, 2), (0, nbf + 2, 2), (0, nbf - 1, 2), (0, nbf, 1), (0, 2, 2)] + k_moves
    if cname == "bw>=3,bh>=3,gap":
        return z3.And(bw >= 3, bh >= 3, bw < w, bh < h, nbf <= nqf - 2, nbr <= nqr - 2), [(0, nqf - 1, nqr), (0, nqf, nqr - 1), (0, nqf - 1, nqr - 1)] + k_moves
    if cname == "bw>=3,bh>=3,bf_adj":
        return z3.And(bw >= 3, bh >= 3, bw < w, bh < h, nbf == nqf - 1), [(0, nqf, nqr - 1), (0, nqf - 1, nqr - 1), (0, nqf + 1, nqr - 1), (0, nbf - 1, nqr), (0, nqf, nbr + 2)] + k_moves
    if cname == "bw>=3,bh>=3,br_adj":
        return z3.And(bw >= 3, bh >= 3, bw < w, bh < h, nbr == nqr - 1), [(0, nqf - 1, nqr), (0, nqf - 1, nqr - 1), (0, nqf - 1, nqr + 1), (0, nqf, nbr - 1), (0, nbf + 2, nqr)] + k_moves
    if cname == "bw==w or bh==h":
        return z3.Or(bw == w, bh == h), [(0, nqf - 1, nqr), (0, nqf, nqr - 1), (0, nqf + 1, nqr), (0, nqf, nqr + 1), (0, nbf + 1, nqr), (0, nqf, nbr + 1), (0, nbf + 2, nqr), (0, nqf, nbr + 2), (0, 2, 2), (0, 1, 3), (0, 3, 1)] + k_moves
    raise ValueError(cname)


def _prove_one_task(args: tuple[str, str, int]) -> tuple[str, str, str, float, dict[str, int] | None]:
    quad, cname, timeout_ms = args
    fh_val = int(quad[0])
    fv_val = int(quad[1])
    t0 = time.perf_counter()
    w, h, kf, kr, qf, qr, bf, br = z3.Ints("w h kf kr qf qr bf br")
    fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh = z_norm_box(w, h, kf, kr, qf, qr, bf, br)
    cond, norm_cands = _case_cond_and_cands(cname, w, h, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh)
    pot0 = z_pot_lia(w, h, kf, kr, qf, qr, bf, br)

    s = z3.Solver()
    s.set("timeout", timeout_ms)
    s.add(w >= 4, h >= 4)
    s.add(z_valid_wtm(w, h, kf, kr, qf, qr, bf, br))
    s.add(fh == fh_val, fv == fv_val)
    s.add(cond)

    for is_k, ntf, ntr in norm_cands:
        tf = (w - 1 - ntf) if fh_val == 1 else ntf
        tr = (h - 1 - ntr) if fv_val == 1 else ntr
        s.add(z3.Not(z_good_move(w, h, kf, kr, qf, qr, bf, br, pot0, is_k, tf, tr)))

    res = s.check()
    dt = time.perf_counter() - t0
    model_dict = None
    if res == z3.sat:
        m = s.model()
        model_dict = {str(v): m[v].as_long() for v in (w, h, kf, kr, qf, qr, bf, br)}
    return quad, cname, str(res), dt, model_dict


def prove_all(
    quadrants: tuple[str, ...] = ("00", "10", "01", "11"),
    jobs: int = 4,
    timeout_sec: int = 30,
    only: list[str] | None = None,
) -> bool:
    t_start = time.perf_counter()
    w, h, kf, kr, qf, qr, bf, br = z3.Ints("w h kf kr qf qr bf br")

    # 1. Check potential lower bound (>= 0 on every coordinate)
    t0 = time.perf_counter()
    s_lb = z3.Solver()
    s_lb.add(w >= 4, h >= 4, z_valid_wtm(w, h, kf, kr, qf, qr, bf, br))
    pot = z_pot_lia(w, h, kf, kr, qf, qr, bf, br)
    s_lb.add(z3.Or(*[c < 0 for c in pot]))
    res_lb = s_lb.check()
    print(f"LOWER_BOUND (>= 0 on all 10 coords): {res_lb} [{time.perf_counter()-t0:.2f}s]")

    # 2. Check case partition exhaustiveness
    t0 = time.perf_counter()
    fh, fv, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh = z_norm_box(w, h, kf, kr, qf, qr, bf, br)
    s_ex = z3.Solver()
    s_ex.add(w >= 4, h >= 4, z_valid_wtm(w, h, kf, kr, qf, qr, bf, br))
    conds = [_case_cond_and_cands(cn, w, h, nkf, nkr, nqf, nqr, nbf, nbr, bw, bh)[0] for cn in CASE_NAMES]
    s_ex.add(z3.Not(z3.Or(*conds)))
    res_ex = s_ex.check()
    print(f"PARTITION_EXHAUSTIVE ({len(CASE_NAMES)} cases):     {res_ex} [{time.perf_counter()-t0:.2f}s]")

    # 3. Check all (quadrant, case) tasks
    if only:
        tasks = []
        for spec in only:
            q, cn = spec.split(":", 1)
            tasks.append((q, cn, timeout_sec * 1000))
    else:
        tasks = [(q, cn, timeout_sec * 1000) for q in quadrants for cn in CASE_NAMES]
    all_unsat = (res_lb == z3.unsat and res_ex == z3.unsat)
    workers = max(1, min(4, jobs))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for quad, cname, res_str, dt, mdict in pool.map(_prove_one_task, tasks):
            if res_str != "unsat":
                all_unsat = False
            extra = f" -> {mdict}" if mdict else ""
            print(f"  Q={quad} CASE {cname:16s}: {res_str:7s} ({dt:.2f}s){extra}", flush=True)

    label = f"{len(tasks)} selected tasks" if only else f"{len(quadrants)} quadrants"
    print(f"OVERALL VERDICT ({label}): {'PROVEN_UNSAT' if all_unsat else 'NOT_PROVEN'} [{time.perf_counter()-t_start:.2f}s]")
    return all_unsat


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KQK Z3 encoding and run symbolic proofs.")
    parser.add_argument("--validate-encoding", action="store_true")
    parser.add_argument("--prove", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--boards", type=int, nargs="+", default=[4, 5, 6])
    parser.add_argument("--quadrants", nargs="+", default=["00", "10", "01", "11"])
    parser.add_argument("--only", nargs="+", default=None, help="Run specific Q:CASE tasks")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    ok = True
    if args.validate_encoding or args.all:
        ok = validate_encoding(tuple(args.boards), jobs=args.jobs) and ok
    if args.prove or args.all:
        ok = prove_all(tuple(args.quadrants), jobs=args.jobs, timeout_sec=args.timeout, only=args.only) and ok
    if not (args.validate_encoding or args.prove or args.all):
        parser.print_help()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
