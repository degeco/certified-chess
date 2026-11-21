#!/usr/bin/env python3
"""Verification checks for 01-survey Round 1 and Round 2 deliverables."""

import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))


def check_assessment_word_count():
    path = os.path.join(ROOT, "assessment.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    words = re.findall(r"\S+", text)
    required_sections = [
        "## 1. What Solving Chess Formally Requires",
        "## 2. Strongest Relevant Methods and Results as of Today",
        "## 3. Main Obstacles and Computational Constraints",
        "## 4. Ranked Shortlist of Research Directions",
        "## 5. Critique of `../design/SPEC.md`",
    ]
    for sec in required_sections:
        assert sec in text, f"Missing required section: {sec}"
    assert len(words) <= 2500, f"assessment.md exceeds 2500 words: {len(words)}"
    print(f"PASS assessment.md word count: {len(words)} <= 2500; all 5 sections present.")


def check_recent_methods():
    path = os.path.join(ROOT, "recent-methods.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    words = re.findall(r"\S+", text)
    required_sections = [
        "## 1. Neural Proof Search Against a Proof-Assistant Kernel",
        "## 2. Program Search with an Automatic Scorer",
        "## 3. LLM Agents Writing Formal Proofs",
        "## 4. SAT/SMT Solvers with Checkable Proof Logs for Combinatorial Results",
        "## 5. Applications to Combinatorial Games and Game Solving (2024–2026)",
        "## 6. Re-Verification of the Four Core Round 1 Design Sources",
        "### 6.1 Set-Based Retrograde Analysis",
        "### 6.2 Capture-Quiet Decomposition (CQD)",
        "### 6.3 Formally Verified Coq Tablebase Generator",
        "### 6.4 Mhalla and Prost 5×5 Gardner Minichess Proof",
    ]
    for sec in required_sections:
        assert sec in text, f"Missing required section in recent-methods.md: {sec}"
    assert 1600 <= len(words) <= 2300, f"recent-methods.md word count out of ~2000 target: {len(words)}"
    print(
        f"PASS recent-methods.md word count: {len(words)} (~2000 target); "
        "all 5 method families and 4 re-verified sources present."
    )


def check_transfer():
    path = os.path.join(ROOT, "transfer.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    words = re.findall(r"\S+", text)
    required_sections = [
        "## 1. Is a Strategy Program Expanded and Checked by Enumeration Sound and Useful?",
        "## 2. Closest Prior Work",
        "## 3. What the Symbolic Step in \"Honest Limits\" Requires—and Which Tools Can Carry It",
        "## 4. Three Concrete Next Experiments (Ranked by Expected Information per Unit Effort)",
    ]
    for sec in required_sections:
        assert sec in text, f"Missing required section in transfer.md: {sec}"
    assert 650 <= len(words) <= 1050, f"transfer.md word count out of ~800 target: {len(words)}"
    print(f"PASS transfer.md word count: {len(words)} (~800 target); all 4 critique sections present.")


def check_sources_table():
    path = os.path.join(ROOT, "sources.md")
    with open(path, "r", encoding="utf-8") as f:
        full_text = f.read()
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    table_rows = [l for l in lines if l.startswith("|")]
    assert len(table_rows) >= 20, f"Too few rows in sources.md: {len(table_rows)}"
    header = [c.strip() for c in table_rows[0].strip("|").split("|")]
    assert header == [
        "Claim",
        "Value",
        "Source",
        "Source Type",
        "Date Accessed",
        "Status",
    ], f"Unexpected header: {header}"
    verified_count = 0
    unverified_count = 0
    for idx, row in enumerate(table_rows[2:], start=1):
        cols = [c.strip() for c in row.strip("|").split("|")]
        assert len(cols) == 6, f"Row {idx} does not have 6 columns: {row}"
        assert all(cols), f"Row {idx} has empty cell: {row}"
        assert cols[4] == "2026-11-21", f"Row {idx} unexpected date: {cols[4]}"
        assert cols[5] in ("VERIFIED", "UNVERIFIED"), f"Row {idx} bad status: {cols[5]}"
        if cols[5] == "VERIFIED":
            verified_count += 1
        else:
            unverified_count += 1
    assert "## Round 2 Re-Verification of Core Design Sources" in full_text
    print(
        f"PASS sources.md schema valid: {verified_count + unverified_count} claims "
        f"({verified_count} VERIFIED, {unverified_count} UNVERIFIED) + Round 2 re-verification section."
    )


def check_links():
    for fn in ("assessment.md", "small-boards.md", "sources.md", "recent-methods.md", "transfer.md"):
        p = os.path.join(ROOT, fn)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        for target in re.findall(r"\(file:///([^)#]+)", text):
            full = "/" + target
            assert os.path.exists(full), f"Broken file link in {fn}: {full}"
    print("PASS all file:// links resolve to existing files.")


# --- Independent SPEC.md 4x4 mini-rules engine, #cert v1 checker & LOOP.md expander ---

FILES = "abcd"


def parse_fen_4x4(fen):
    placement, stm, castling, ep = fen.split(" ")
    assert castling == "-" and ep == "-"
    ranks = placement.split("/")
    assert len(ranks) == 4
    board = {}
    for r_idx, rank_str in enumerate(ranks):
        y = 3 - r_idx
        x = 0
        for ch in rank_str:
            if ch.isdigit():
                x += int(ch)
            else:
                board[(x, y)] = ch
                x += 1
        assert x == 4
    return board, stm


def to_fen_4x4(board, stm):
    ranks = []
    for y in range(3, -1, -1):
        empty = 0
        s = ""
        for x in range(4):
            p = board.get((x, y))
            if p is None:
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += p
        if empty:
            s += str(empty)
        ranks.append(s)
    return f"{'/'.join(ranks)} {stm} - -"


def pseudo_moves(board, stm):
    white = stm == "w"
    moves = []
    for (x, y), p in board.items():
        if p.isupper() != white:
            continue
        pt = p.upper()
        if pt == "P":
            dy = 1 if white else -1
            ny = y + dy
            if 0 <= ny < 4:
                if (x, ny) not in board:
                    promos = ["q", "r", "b", "n"] if ny in (0, 3) else [""]
                    for pr in promos:
                        moves.append(((x, y), (x, ny), pr))
                for dx in (-1, 1):
                    nx = x + dx
                    if 0 <= nx < 4 and (nx, ny) in board and board[(nx, ny)].isupper() != white:
                        promos = ["q", "r", "b", "n"] if ny in (0, 3) else [""]
                        for pr in promos:
                            moves.append(((x, y), (nx, ny), pr))
        elif pt == "K":
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 4 and 0 <= ny < 4:
                        if (nx, ny) not in board or board[(nx, ny)].isupper() != white:
                            moves.append(((x, y), (nx, ny), ""))
        elif pt in ("R", "B", "Q"):
            dirs = []
            if pt in ("R", "Q"):
                dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]
            if pt in ("B", "Q"):
                dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                while 0 <= nx < 4 and 0 <= ny < 4:
                    if (nx, ny) not in board:
                        moves.append(((x, y), (nx, ny), ""))
                    else:
                        if board[(nx, ny)].isupper() != white:
                            moves.append(((x, y), (nx, ny), ""))
                        break
                    nx += dx
                    ny += dy
        elif pt == "N":
            for dx, dy in [
                (1, 2), (2, 1), (-1, 2), (-2, 1),
                (1, -2), (2, -1), (-1, -2), (-2, -1),
            ]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < 4 and 0 <= ny < 4:
                    if (nx, ny) not in board or board[(nx, ny)].isupper() != white:
                        moves.append(((x, y), (nx, ny), ""))
    return moves


def apply_move(board, stm, m):
    nb = dict(board)
    (x1, y1), (x2, y2), pr = m
    piece = nb.pop((x1, y1))
    if pr:
        piece = pr.upper() if stm == "w" else pr.lower()
    nb[(x2, y2)] = piece
    return nb, ("b" if stm == "w" else "w")


def in_check(board, stm):
    king = "K" if stm == "w" else "k"
    kp = next(pos for pos, pc in board.items() if pc == king)
    opp = "b" if stm == "w" else "w"
    return any(m[1] == kp for m in pseudo_moves(board, opp))


def legal_moves(board, stm):
    res = {}
    for m in pseudo_moves(board, stm):
        nb, nstm = apply_move(board, stm, m)
        if not in_check(nb, stm):
            s = f"{FILES[m[0][0]]}{m[0][1]+1}{FILES[m[1][0]]}{m[1][1]+1}{m[2]}"
            res[s] = (nb, nstm)
    return res


def verify_win_cert(root, cert):
    assert root in cert
    for p, (m, d) in cert.items():
        assert isinstance(d, int) and d >= 0
        bp, sp = parse_fen_4x4(p)
        assert sp == "w"
        lmp = legal_moves(bp, sp)
        assert m in lmp, f"Illegal move {m} in {p}"
        bq, sq = lmp[m]
        lmq = legal_moves(bq, sq)
        if not lmq:
            assert in_check(bq, sq), f"Stalemate, not checkmate after {p} -> {m}"
        else:
            for r, (br, sr) in lmq.items():
                qr = to_fen_4x4(br, sr)
                assert qr in cert, f"Missing entry for {qr}"
                assert cert[qr][1] < d, f"Rank did not decrease at {qr}"


def check_mini4x4_cert():
    root = "rqkr/pppp/PPPP/RQKR w - -"
    b0, s0 = parse_fen_4x4(root)
    b1, s1 = legal_moves(b0, s0)["a2b3"]
    b2, s2 = legal_moves(b1, s1)["b4b3"]
    fen2 = to_fen_4x4(b2, s2)
    b3, s3 = legal_moves(b2, s2)["c2b3"]
    lm3 = legal_moves(b3, s3)

    b4a, s4a = lm3["c4b3"]
    fen4a = to_fen_4x4(b4a, s4a)
    b5a, s5a = legal_moves(b4a, s4a)["b2a3"]
    b6a, s6a = legal_moves(b5a, s5a)["b3c4"]
    fen6a = to_fen_4x4(b6a, s6a)

    b4b, s4b = lm3["c4b4"]
    fen4b = to_fen_4x4(b4b, s4b)

    cert = {
        root: ("a2b3", 4),
        fen2: ("c2b3", 3),
        fen4a: ("b2a3", 2),
        fen6a: ("b1a2", 1),
        fen4b: ("b2c3", 1),
    }
    verify_win_cert(root, cert)
    print(f"PASS mini4x4 WIN w certificate verified: {len(cert)} entries, max rank 4.")


def check_loop_strategy_expansion():
    """Verify LOOP.md expansion & rank synthesis on a pure 4x4 KQK strategy program."""

    def kqk_strategy(fen):
        board, stm = parse_fen_4x4(fen)
        lm = legal_moves(board, stm)
        wk = next(pos for pos, pc in board.items() if pc == "K")
        wq = next(pos for pos, pc in board.items() if pc == "Q")
        bk = next(pos for pos, pc in board.items() if pc == "k")
        best_move = None
        best_score = None
        for m, (nb, nstm) in sorted(lm.items()):
            opp_lm = legal_moves(nb, nstm)
            if not opp_lm:
                if in_check(nb, nstm):
                    return m  # immediate checkmate
                continue  # never stalemate
            nwk = next(pos for pos, pc in nb.items() if pc == "K")
            nwq = next(pos for pos, pc in nb.items() if pc == "Q")
            # Queen safe if adjacent to WK or not adjacent to BK
            q_adj_bk = max(abs(nwq[0] - bk[0]), abs(nwq[1] - bk[1])) <= 1
            q_adj_wk = max(abs(nwq[0] - nwk[0]), abs(nwq[1] - nwk[1])) <= 1
            if q_adj_bk and not q_adj_wk:
                continue
            chk = 1 if in_check(nb, nstm) else 0
            k_dist = abs(nwk[0] - bk[0]) + abs(nwk[1] - bk[1])
            q_dist = abs(nwq[0] - bk[0]) + abs(nwq[1] - bk[1])
            score = (-len(opp_lm), chk, -k_dist, -q_dist)
            if best_score is None or score > best_score:
                best_score = score
                best_move = m
        return best_move

    roots = [
        "3k/4/1K2/Q3 w - -",
        "2k1/4/2K1/3Q w - -",
        "k3/4/2K1/1Q2 w - -",
        "1k2/4/1K2/2Q1 w - -",
    ]
    total_entries = 0
    for r in roots:
        # Expand strategy graph and compute exact topological WIN ranks
        moves_chosen = {}
        children = {}
        visiting = set()

        def expand(p):
            if p in moves_chosen:
                return True
            if p in visiting:
                return False  # cycle
            visiting.add(p)
            m = kqk_strategy(p)
            if not m:
                return False
            bp, sp = parse_fen_4x4(p)
            bq, sq = legal_moves(bp, sp)[m]
            lmq = legal_moves(bq, sq)
            if not lmq:
                if not in_check(bq, sq):
                    return False
                moves_chosen[p] = m
                children[p] = []
                visiting.remove(p)
                return True
            ch = []
            for _, (br, sr) in sorted(lmq.items()):
                qr = to_fen_4x4(br, sr)
                if not expand(qr):
                    return False
                ch.append(qr)
            moves_chosen[p] = m
            children[p] = ch
            visiting.remove(p)
            return True

        assert expand(r), f"LOOP.md strategy expansion failed on {r}"
        ranks = {}

        def get_rank(p):
            if p not in ranks:
                ranks[p] = 1 + max((get_rank(c) for c in children[p]), default=0)
            return ranks[p]

        for p in moves_chosen:
            get_rank(p)
        cert = {p: (moves_chosen[p], ranks[p]) for p in moves_chosen}
        verify_win_cert(r, cert)
        total_entries += len(cert)

    print(
        f"PASS LOOP.md KQK strategy expansion verified across {len(roots)} roots: "
        f"{total_entries} total certificate entries."
    )


if __name__ == "__main__":
    check_assessment_word_count()
    check_recent_methods()
    check_transfer()
    check_sources_table()
    check_links()
    check_mini4x4_cert()
    check_loop_strategy_expansion()
