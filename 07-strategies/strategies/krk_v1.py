"""krk round 1: simple rook box-shrinking and king-approach heuristic."""

import rules


def _find(pos, piece):
    idx = pos.board.index(piece)
    return idx % pos.width, idx // pos.width


def _box_area(w, h, rf, rr, bkf, bkr):
    bw = rf if bkf < rf else (w - 1 - rf if bkf > rf else w)
    bh = rr if bkr < rr else (h - 1 - rr if bkr > rr else h)
    return bw * bh


def move(pos):
    w, h = pos.width, pos.height
    wkf, wkr = _find(pos, "K")
    wrf, wrr = _find(pos, "R")
    bkf, bkr = _find(pos, "k")
    cur_area = _box_area(w, h, wrf, wrr, bkf, bkr)

    best_m = None
    best_key = None

    for m, nxt in rules.legal_transitions(pos):
        replies = rules.legal_moves(nxt)
        in_chk = rules.in_check(nxt)
        if not replies:
            if in_chk:
                return m
            continue

        nwkf, nwkr = _find(nxt, "K")
        nwrf, nwrr = _find(nxt, "R")
        r_att = max(abs(nwrf - bkf), abs(nwrr - bkr)) <= 1
        r_def = max(abs(nwrf - nwkf), abs(nwrr - nwkr)) <= 1
        if r_att and not r_def:
            continue

        area = _box_area(w, h, nwrf, nwrr, bkf, bkr)
        k_dist = max(abs(nwkf - bkf), abs(nwkr - bkr))
        edge_dist = min(bkf, w - 1 - bkf, bkr, h - 1 - bkr)

        key = (
            1 if area < cur_area and not in_chk else 0,
            -area,
            -k_dist,
            -edge_dist,
            0 if not in_chk else -1,
            -len(replies),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_m = m

    return best_m if best_m is not None else rules.legal_moves(pos)[0]
