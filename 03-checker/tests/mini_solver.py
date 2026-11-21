"""Tiny brute-force retrograde solver for test certificate generation ONLY.

Lives inside tests/ as required by TASK.md. Used only to produce real WIN and
ATLEAST_DRAW certificates for small reachable state spaces so mcheck.py can be
tested on genuine proofs and single-change mutations of them.
"""

from __future__ import annotations

from collections import deque

from rules import Position, in_check, legal_transitions, parse_position


def solve_small(
    root_fen: str, max_states: int = 50000
) -> tuple[str, dict[str, str], dict[str, int], dict[str, str]]:
    """Enumerate reachable states from root_fen and solve by retrograde analysis.

    Returns (root_outcome_for_root_stm, outcomes, dtm_plies, best_move), where:
      - outcomes[fen] in {"WIN", "LOSS", "DRAW"} from the side-to-move's perspective.
      - dtm_plies[fen] is exact plies to mate for WIN/LOSS states (0 at checkmate).
      - best_move[fen] is a winning move (for WIN) or drawing move (for DRAW).
    """
    root_pos = parse_position(root_fen)
    root_key = root_pos.to_fen()

    positions: dict[str, Position] = {root_key: root_pos}
    edges: dict[str, list[tuple[str, str]]] = {}
    rev_edges: dict[str, list[tuple[str, str]]] = {root_key: []}

    bfs: deque[str] = deque([root_key])
    while bfs:
        key = bfs.popleft()
        pos = positions[key]
        trans = legal_transitions(pos)
        out_list: list[tuple[str, str]] = []
        for move_str, next_pos in trans:
            nkey = next_pos.to_fen()
            out_list.append((move_str, nkey))
            if nkey not in positions:
                if len(positions) >= max_states:
                    raise RuntimeError(f"state space exceeded {max_states}")
                positions[nkey] = next_pos
                rev_edges[nkey] = []
                bfs.append(nkey)
            rev_edges[nkey].append((key, move_str))
        edges[key] = out_list

    outcomes: dict[str, str] = {}
    dtm_plies: dict[str, int] = {}
    best_move: dict[str, str] = {}
    remaining: dict[str, int] = {k: len(v) for k, v in edges.items()}

    queue: deque[str] = deque()
    for key, out_list in edges.items():
        if not out_list and in_check(positions[key]):
            outcomes[key] = "LOSS"
            dtm_plies[key] = 0
            queue.append(key)

    while queue:
        child = queue.popleft()
        child_outcome = outcomes[child]
        child_ply = dtm_plies[child]

        for parent, move_str in rev_edges[child]:
            if parent in outcomes:
                continue
            if child_outcome == "LOSS":
                outcomes[parent] = "WIN"
                dtm_plies[parent] = child_ply + 1
                best_move[parent] = move_str
                queue.append(parent)
            else:
                remaining[parent] -= 1
                if remaining[parent] == 0:
                    outcomes[parent] = "LOSS"
                    dtm_plies[parent] = child_ply + 1
                    queue.append(parent)

    for key, out_list in edges.items():
        if key not in outcomes:
            outcomes[key] = "DRAW"
            for move_str, nkey in out_list:
                if outcomes.get(nkey, "DRAW") == "DRAW":
                    best_move[key] = move_str
                    break

    return outcomes[root_key], outcomes, dtm_plies, best_move


def build_win_certificate(root_fen: str, prover: str, max_states: int = 50000) -> str:
    """Build a SPEC v1 WIN certificate for `prover` from `root_fen`."""
    root_pos = parse_position(root_fen)
    root_key = root_pos.to_fen()
    _, outcomes, dtm_plies, best_move = solve_small(root_key, max_states=max_states)

    # Check root is actually a win for prover.
    root_is_prover = root_pos.stm == prover
    if root_is_prover and outcomes[root_key] != "WIN":
        raise ValueError(f"root is {outcomes[root_key]} for prover {prover}, not WIN")
    if not root_is_prover and outcomes[root_key] != "LOSS":
        raise ValueError(f"root is {outcomes[root_key]} for opponent, not WIN for {prover}")

    # Collect entries reachable under the prover's winning strategy.
    entries: dict[str, tuple[str, int]] = {}
    visited_opp: set[str] = set()
    stack: list[Position] = [root_pos]

    while stack:
        pos = stack.pop()
        key = pos.to_fen()
        if pos.stm == prover:
            if key in entries:
                continue
            move_str = best_move[key]
            # Convert odd ply distance (1, 3, 5, ...) to own-move rank (1, 2, 3, ...).
            rank = (dtm_plies[key] + 1) // 2
            entries[key] = (move_str, rank)
            for m, nxt in legal_transitions(pos):
                if m == move_str:
                    stack.append(nxt)
                    break
        else:
            if key in visited_opp:
                continue
            visited_opp.add(key)
            for _, nxt in legal_transitions(pos):
                stack.append(nxt)

    lines = [
        "#cert v1",
        f"#claim WIN {prover}",
        f"#root {root_key}",
    ]
    for key in sorted(entries):
        move_str, rank = entries[key]
        lines.append(f"{key}\t{move_str}\t{rank}")
    return "\n".join(lines) + "\n"


def build_atleast_draw_certificate(
    root_fen: str, prover: str, max_states: int = 50000
) -> str:
    """Build a SPEC v1.1 ATLEAST_DRAW certificate for `prover` from `root_fen`.

    Computes the maximal covered set C of prover-to-move positions: each position
    in C is either a prover stalemate (0 legal moves, not in check, covered
    without an entry) or has a legal move keeping all opponent replies inside C.
    """
    root_pos = parse_position(root_fen)
    root_key = root_pos.to_fen()

    positions: dict[str, Position] = {root_key: root_pos}
    edges: dict[str, list[tuple[str, str]]] = {}
    bfs: deque[str] = deque([root_key])
    while bfs:
        key = bfs.popleft()
        trans = legal_transitions(positions[key])
        edges[key] = [(m, nxt.to_fen()) for m, nxt in trans]
        for _, nxt in trans:
            nkey = nxt.to_fen()
            if nkey not in positions:
                if len(positions) >= max_states:
                    raise RuntimeError(f"state space exceeded {max_states}")
                positions[nkey] = nxt
                bfs.append(nkey)

    prover_stalemates: set[str] = {
        k
        for k, p in positions.items()
        if p.stm == prover and len(edges[k]) == 0 and not in_check(p)
    }

    # Greatest fixed point: covered prover states (prover stalemates or states with a safe move).
    covered: set[str] = {
        k
        for k, p in positions.items()
        if p.stm == prover and (len(edges[k]) > 0 or not in_check(p))
    }
    safe_move: dict[str, str] = {}
    while True:
        new_covered: set[str] = set(prover_stalemates)
        new_move: dict[str, str] = {}
        for k in covered:
            if k in prover_stalemates:
                continue
            for move_str, q_key in edges[k]:
                if all(r_key in covered for _, r_key in edges[q_key]):
                    new_covered.add(k)
                    new_move[k] = move_str
                    break
        if len(new_covered) == len(covered):
            safe_move = new_move
            break
        covered = new_covered

    if root_pos.stm == prover:
        if root_key not in covered:
            raise ValueError(f"no SPEC v1.1 ATLEAST_DRAW strategy for {prover} from {root_key}")
    else:
        if not all(r_key in covered for _, r_key in edges[root_key]):
            raise ValueError(f"no SPEC v1.1 ATLEAST_DRAW strategy for {prover} from {root_key}")

    entries: dict[str, str] = {}
    visited_opp: set[str] = set()
    stack: list[str] = [root_key]
    while stack:
        key = stack.pop()
        if positions[key].stm == prover:
            if key in prover_stalemates or key in entries:
                continue
            move_str = safe_move[key]
            entries[key] = move_str
            for m, q_key in edges[key]:
                if m == move_str:
                    stack.append(q_key)
                    break
        else:
            if key in visited_opp:
                continue
            visited_opp.add(key)
            for _, r_key in edges[key]:
                stack.append(r_key)

    lines = [
        "#cert v1",
        f"#claim ATLEAST_DRAW {prover}",
        f"#root {root_key}",
    ]
    for key in sorted(entries):
        lines.append(f"{key}\t{entries[key]}\t0")
    return "\n".join(lines) + "\n"
