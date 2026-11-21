"""kqk round 1: simple greedy knight-opposition / box-shrinking heuristic with king approach."""

import rules


def _find(pos, piece):
    idx = pos.board.index(piece)
    return idx % pos.width, idx // pos.width


def _box_area(w, h, qf, qr, bkf, bkr):
    bw = qf if bkf < qf else (w - 1 - qf if bkf > qf else w)
    bh = qr if bkr < qr else (h - 1 - qr if bkr > qr else h)
    return bw * bh


def move(pos):
    w, h = pos.width, pos.height
    wkf, wkr = _find(pos, "K")
    wqf, wqr = _find(pos, "Q")
    bkf, bkr = _find(pos, "k")
    cur_area = _box_area(w, h, wqf, wqr, bkf, bkr)

    best_m = None
    best_key = None

    for m, nxt in rules.legal_transitions(pos):
        replies = rules.legal_moves(nxt)
        in_chk = rules.in_check(nxt)
        if not replies:
            if in_chk:
                return m
            continue  # avoid stalemate

        nwkf, nwkr = _find(nxt, "K")
        nwqf, nwqr = _find(nxt, "Q")

        # Never hang the queen: check if BK attacks Q and WK does not defend Q
        q_attacked = max(abs(nwqf - bkf), abs(nwqr - bkr)) <= 1
        q_defended = max(abs(nwqf - nwkf), abs(nwqr - nwkr)) <= 1
        if q_attacked and not q_defended:
            continue

        area = _box_area(w, h, nwqf, nwqr, bkf, bkr)
        k_dist = max(abs(nwkf - bkf), abs(nwkr - bkr))
        moved_q = (nwqf, nwqr) != (wqf, wqr)

        # Prefer shrinking box area without checking; once small, bring king closer.
        if cur_area > 2:
            key = (
                1 if area < cur_area and not in_chk else 0,
                -area,
                -k_dist,
                0 if not in_chk else -1,
                -len(replies),
            )
        else:
            key = (
                1 if not moved_q else 0,
                -k_dist,
                -area,
                -len(replies),
            )
        if best_key is None or key > best_key:
            best_key = key
            best_m = m

    return best_m if best_m is not None else rules.legal_moves(pos)[0]
