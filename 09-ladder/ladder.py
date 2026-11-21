#!/usr/bin/env python3
"""Scoring, validation, union-certificate expansion, and verification harness for 09-ladder.

Usage:
  python3 ladder.py score --class KPK --board 5x5 --all
  python3 ladder.py score --class KPK --board 6x6 --all
  python3 ladder.py score --class KPK --board 8x8 --sample 2000 --seed 1
"""

from __future__ import annotations

import argparse
import ast
import builtins
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
from typing import Callable

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
CHECKER_DIR = REPO_DIR / "03-checker"
MCHECK_PY = CHECKER_DIR / "mcheck.py"
MCHECK2_BIN = REPO_DIR / "08-checker2" / "mcheck2"
TBGEN_BIN = REPO_DIR / "04-tablebase" / "bin" / "tbgen"
DEFAULT_TB_DIR = REPO_DIR / "04-tablebase" / "data"
LOCAL_TB_DIR = BASE_DIR / "tb"
STRAT_DIR = REPO_DIR / "07-strategies"
LIB_DIR = BASE_DIR / "lib"

for p in (str(CHECKER_DIR), str(STRAT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import rules  # noqa: E402
import harness  # noqa: E402

ALLOWED_LIB_MODULES = frozenset({"kqk", "krk"})


@dataclass(frozen=True)
class ProgramStats:
    path: Path
    total_nodes: int
    total_bytes: int
    claims_nodes: int
    move_nodes: int
    move_only_nodes: int


@dataclass(frozen=True)
class CheckerVerdict:
    checker: str
    valid: bool
    entries: int
    max_rank: int
    seconds: float
    detail: str


def _collect_top_level_graph(tree: ast.Module) -> tuple[dict[str, ast.AST], dict[str, set[str]]]:
    """Map each top-level def/assign name to its AST node and referenced top-level names."""
    nodes_by_name: dict[str, ast.AST] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes_by_name[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    nodes_by_name[tgt.id] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            nodes_by_name[stmt.target.id] = stmt

    refs: dict[str, set[str]] = {}
    for name, node in nodes_by_name.items():
        used: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in nodes_by_name and sub.id != name:
                used.add(sub.id)
        refs[name] = used
    return nodes_by_name, refs


def _count_ast_nodes_no_doc(node: ast.AST) -> int:
    """Count AST nodes in a subtree after stripping function docstrings."""
    total = 0
    doc_ids: set[int] = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                sub.body
                and isinstance(sub.body[0], ast.Expr)
                and isinstance(sub.body[0].value, ast.Constant)
                and isinstance(sub.body[0].value.value, str)
            ):
                doc_ids.add(id(sub.body[0]))
                doc_ids.add(id(sub.body[0].value))
    for sub in ast.walk(node):
        if id(sub) not in doc_ids:
            total += 1
    return total


def _reachable_names(root_name: str, refs: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    q = deque([root_name])
    while q:
        u = q.popleft()
        if u in seen or u not in refs:
            continue
        seen.add(u)
        for v in refs[u]:
            if v not in seen:
                q.append(v)
    return seen


def validate_ladder_program(path: Path) -> tuple[str, ProgramStats]:
    """Validate a rung program (claims + move, 2-ply static rules, lower-rung lib imports only)."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise harness.ProgramValidationError(f"cannot read {path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise harness.ProgramValidationError(f"syntax error in {path}: {exc}") from exc

    top_funcs = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for req in ("claims", "move"):
        if req not in top_funcs:
            raise harness.ProgramValidationError(f"{path} must define top-level {req}(pos)")
        fn = top_funcs[req]
        pos_args = len(fn.args.posonlyargs) + len(fn.args.args)
        required_args = pos_args - len(fn.args.defaults)
        if fn.args.vararg is None and (pos_args < 1 or required_args > 1):
            raise harness.ProgramValidationError(f"{req}() must accept a single positional argument")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "rules":
                    continue
                if alias.name in ("lib.kqk", "lib.krk") or alias.name in ALLOWED_LIB_MODULES:
                    continue
                raise harness.ProgramValidationError(
                    f"forbidden import {alias.name!r}: only 'rules' and lower rungs in lib/ allowed"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0:
                raise harness.ProgramValidationError("relative imports forbidden")
            if node.module == "rules":
                for alias in node.names:
                    if alias.name in harness.FORBIDDEN_RULES_ATTRS or alias.name == "*":
                        raise harness.ProgramValidationError(f"forbidden import from rules: {alias.name!r}")
            elif node.module == "lib":
                for alias in node.names:
                    if alias.name not in ALLOWED_LIB_MODULES:
                        raise harness.ProgramValidationError(f"forbidden import from lib: {alias.name!r}")
            else:
                raise harness.ProgramValidationError(
                    f"forbidden import from {node.module!r}: only 'rules' and 'lib' allowed"
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in harness.FORBIDDEN_CALL_NAMES:
                raise harness.ProgramValidationError(f"forbidden builtin call: {node.func.id}")
        elif isinstance(node, ast.Name):
            if node.id in harness.FORBIDDEN_CALL_NAMES or node.id in harness.FORBIDDEN_ATTR_NAMES:
                raise harness.ProgramValidationError(f"forbidden identifier: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in harness.FORBIDDEN_ATTR_NAMES:
                raise harness.ProgramValidationError(f"forbidden attribute access: {node.attr}")
            if node.attr in harness.FORBIDDEN_RULES_ATTRS:
                raise harness.ProgramValidationError(f"forbidden rules attribute: {node.attr}")

    harness._check_lookahead_and_state(tree)

    total_nodes = harness.measure_program_nodes(source)
    total_bytes = harness.measure_program_length(source)

    nodes_by_name, refs = _collect_top_level_graph(tree)
    claims_set = _reachable_names("claims", refs)
    move_set = _reachable_names("move", refs)
    claims_nodes = sum(_count_ast_nodes_no_doc(nodes_by_name[n]) for n in claims_set)
    move_nodes = sum(_count_ast_nodes_no_doc(nodes_by_name[n]) for n in move_set)
    move_only_nodes = sum(_count_ast_nodes_no_doc(nodes_by_name[n]) for n in (move_set - claims_set))

    stats = ProgramStats(
        path=path,
        total_nodes=total_nodes,
        total_bytes=total_bytes,
        claims_nodes=claims_nodes,
        move_nodes=move_nodes,
        move_only_nodes=move_only_nodes,
    )
    return source, stats


class _LowerRungProxy:
    """Guarded proxy for a lower-rung strategy in lib/ (only callable at ply 0 after leaving KPK)."""

    def __init__(
        self,
        name: str,
        move_fn: Callable[[rules.Position], str],
        parent_guard: harness._GuardedRules,
        required_piece: str,
    ) -> None:
        self._name = name
        self._move_fn = move_fn
        self._parent_guard = parent_guard
        self._required_piece = required_piece

    def move(self, pos: rules.Position) -> str:
        ply_map = self._parent_guard._ply
        if ply_map is None or ply_map.get(pos) != 0:
            raise harness.LookaheadLimitError(
                f"lib.{self._name}.move() may only be called at ply 0 (direct handover)"
            )
        if "P" in pos.board or "p" in pos.board or self._required_piece not in pos.board:
            raise harness.LookaheadLimitError(
                f"lib.{self._name}.move() called on non-{self._name.upper()} position"
            )
        return self._move_fn(pos)


class _LibPackageProxy:
    def __init__(self, modules: dict[str, _LowerRungProxy]) -> None:
        for k, v in modules.items():
            setattr(self, k, v)


def load_ladder_program(
    path: Path,
) -> tuple[Callable[[rules.Position], bool], Callable[[rules.Position], str], ProgramStats]:
    """Validate and load a rung program with strict 2-ply lookahead enforcement."""
    source, stats = validate_ladder_program(path)
    guarded = harness._GuardedRules()

    lib_proxies: dict[str, _LowerRungProxy] = {}
    for mod_name, req_piece in (("kqk", "Q"), ("krk", "R")):
        mod_path = LIB_DIR / f"{mod_name}.py"
        if mod_path.is_file():
            _, lib_move_fn, _, _ = harness.load_strategy_namespace(
                mod_path, length_limit=None, enforce_lookahead=True
            )
            lib_proxies[mod_name] = _LowerRungProxy(mod_name, lib_move_fn, guarded, req_piece)
    lib_pkg = _LibPackageProxy(lib_proxies)

    safe_builtins = dict(vars(builtins))

    def _restricted_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if level != 0:
            raise ImportError(f"relative import forbidden: {name!r}")
        if name == "rules":
            return guarded
        if name == "lib":
            return lib_pkg
        if name.startswith("lib."):
            sub = name.split(".", 1)[1]
            if sub in lib_proxies:
                return lib_proxies[sub]
        if name in lib_proxies:
            return lib_proxies[name]
        raise ImportError(f"forbidden import: {name!r}")

    safe_builtins["__import__"] = _restricted_import
    namespace: dict[str, object] = {
        "__builtins__": safe_builtins,
        "__name__": f"ladder_{path.stem}",
        "__file__": str(path.resolve()),
    }
    try:
        exec(compile(source, str(path), "exec"), namespace)
    except Exception as exc:
        raise harness.ProgramValidationError(f"error loading {path}: {exc}") from exc

    raw_claims = namespace.get("claims")
    raw_move = namespace.get("move")
    if not callable(raw_claims) or not callable(raw_move):
        raise harness.ProgramValidationError(f"{path} must expose callable claims() and move()")

    def wrapped_claims(pos: rules.Position) -> bool:
        guarded.begin_call(pos)
        try:
            return bool(raw_claims(pos))
        finally:
            guarded.end_call()

    def wrapped_move(pos: rules.Position) -> str:
        guarded.begin_call(pos)
        try:
            return str(raw_move(pos))
        finally:
            guarded.end_call()

    return wrapped_claims, wrapped_move, stats


def resolve_tb_dir(board: str, sig: str, tb_dir_override: Path | None) -> Path:
    if tb_dir_override is not None:
        return tb_dir_override
    fname = f"{board}_{sig}.tb"
    if (DEFAULT_TB_DIR / fname).is_file():
        return DEFAULT_TB_DIR
    if (LOCAL_TB_DIR / fname).is_file():
        return LOCAL_TB_DIR
    raise FileNotFoundError(
        f"tablebase {fname} not found in {DEFAULT_TB_DIR} or {LOCAL_TB_DIR}"
    )


def load_tablebase_truth(
    board: str, sig: str, tb_dir_override: Path | None = None
) -> list[tuple[str, str, int]]:
    """Return list of (fen, outcome, dtm) where outcome is 'W_WIN', 'DRAW', or 'B_WIN'."""
    tb_dir = resolve_tb_dir(board, sig, tb_dir_override)
    proc = subprocess.run(
        [str(TBGEN_BIN), "dump", board, sig, "--db-dir", str(tb_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    rows: list[tuple[str, str, int]] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        fen, val, dtm_s = line.split("\t")
        stm = fen.split(" ")[1]
        if val == "D":
            outcome = "DRAW"
        elif (stm == "w" and val == "W") or (stm == "b" and val == "L"):
            outcome = "W_WIN"
        else:
            outcome = "B_WIN"
        rows.append((fen, outcome, int(dtm_s)))
    return rows


def select_roots(
    all_rows: list[tuple[str, str, int]],
    sample_n: int | None,
    seed: int,
) -> list[tuple[str, str, int]]:
    """Return all rows or a deterministic stratified sample (equal W_WIN/DRAW, both stms)."""
    if sample_n is None:
        return all_rows
    rng = random.Random(seed)
    buckets: dict[tuple[str, str], list[tuple[str, str, int]]] = {
        ("W_WIN", "w"): [],
        ("W_WIN", "b"): [],
        ("DRAW", "w"): [],
        ("DRAW", "b"): [],
    }
    for row in all_rows:
        stm = row[0].split(" ")[1]
        key = (row[1], stm)
        if key in buckets:
            buckets[key].append(row)

    n_win = sample_n // 2
    n_draw = sample_n - n_win
    targets = {
        ("W_WIN", "w"): n_win // 2,
        ("W_WIN", "b"): n_win - n_win // 2,
        ("DRAW", "w"): n_draw // 2,
        ("DRAW", "b"): n_draw - n_draw // 2,
    }
    selected: list[tuple[str, str, int]] = []
    for key in (("W_WIN", "w"), ("W_WIN", "b"), ("DRAW", "w"), ("DRAW", "b")):
        pool = buckets[key]
        k = min(targets[key], len(pool))
        selected.extend(rng.sample(pool, k))
    return selected


# ---------------------------------------------------------------------------
# Multiprocessing worker state
# ---------------------------------------------------------------------------
_W_CLAIMS: Callable[[rules.Position], bool] | None = None
_W_MOVE: Callable[[rules.Position], str] | None = None


def _init_worker(prog_path: str) -> None:
    global _W_CLAIMS, _W_MOVE
    _W_CLAIMS, _W_MOVE, _ = load_ladder_program(Path(prog_path))


def _eval_claims_batch(fens: list[str]) -> list[tuple[str, bool, str | None]]:
    assert _W_CLAIMS is not None
    out: list[tuple[str, bool, str | None]] = []
    for fen in fens:
        pos = rules.parse_position(fen)
        try:
            val = _W_CLAIMS(pos)
            out.append((fen, val, None))
        except Exception as exc:
            out.append((fen, False, f"{type(exc).__name__}: {exc}"))
    return out


def _eval_win_step_batch(
    fens: list[str],
) -> list[tuple[str, str | None, list[str] | None, str | None, str | None]]:
    assert _W_MOVE is not None
    out: list[tuple[str, str | None, list[str] | None, str | None, str | None]] = []
    for fen in fens:
        pos = rules.parse_position(fen)
        transitions = rules.legal_transitions(pos)
        if not transitions:
            if rules.in_check(pos):
                out.append((fen, None, None, "checkmated", "prover is checkmated"))
            else:
                out.append((fen, None, None, "stalemate", "prover stalemated in WIN"))
            continue
        trans_dict = dict(transitions)
        try:
            m = _W_MOVE(pos)
        except Exception as exc:
            out.append((fen, None, None, "program_error", f"{type(exc).__name__}: {exc}"))
            continue
        q_pos = trans_dict.get(m)
        if q_pos is None:
            out.append((fen, None, None, "illegal_move", f"illegal move {m!r}"))
            continue
        replies = rules.legal_transitions(q_pos)
        if not replies:
            if not rules.in_check(q_pos):
                out.append((fen, m, None, "stalemate", f"move {m} stalemates opponent"))
            else:
                out.append((fen, m, [], None, None))
            continue
        children = sorted({rpos.to_fen() for _, rpos in replies})
        out.append((fen, m, children, None, None))
    return out


def _eval_hold_step_batch(
    fens: list[str],
) -> list[tuple[str, str | None, list[str] | None, str | None, str | None]]:
    assert _W_MOVE is not None
    out: list[tuple[str, str | None, list[str] | None, str | None, str | None]] = []
    for fen in fens:
        pos = rules.parse_position(fen)
        transitions = rules.legal_transitions(pos)
        if not transitions:
            if rules.in_check(pos):
                out.append((fen, None, None, "checkmated", "prover is checkmated"))
            else:
                # Prover stalemate: covered without an entry (SPEC v1.1)
                out.append((fen, None, [], "prover_stalemate", None))
            continue
        trans_dict = dict(transitions)
        try:
            m = _W_MOVE(pos)
        except Exception as exc:
            out.append((fen, None, None, "program_error", f"{type(exc).__name__}: {exc}"))
            continue
        q_pos = trans_dict.get(m)
        if q_pos is None:
            out.append((fen, None, None, "illegal_move", f"illegal move {m!r}"))
            continue
        replies = rules.legal_transitions(q_pos)
        children = sorted({rpos.to_fen() for _, rpos in replies})
        out.append((fen, m, children, None, None))
    return out


def _run_batches(
    pool: ProcessPoolExecutor | None,
    fn: Callable,
    items: list[str],
    workers: int,
) -> list:
    if not items:
        return []
    if pool is None or len(items) < 256:
        return fn(items)
    chunk = max(64, min(1000, (len(items) + workers * 4 - 1) // (workers * 4)))
    batches = [items[i : i + chunk] for i in range(0, len(items), chunk)]
    out: list = []
    for res in pool.map(fn, batches):
        out.extend(res)
    return out


def verify_cert(cert_path: Path, checker_mode: str) -> list[CheckerVerdict]:
    verdicts: list[CheckerVerdict] = []
    runners: list[tuple[str, list[str]]] = []
    if checker_mode in ("mcheck2", "both"):
        runners.append(("mcheck2", [str(MCHECK2_BIN), "verify", str(cert_path)]))
    if checker_mode in ("mcheck", "both"):
        runners.append(("mcheck.py", [sys.executable, str(MCHECK_PY), "verify", str(cert_path)]))

    for label, cmd in runners:
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        elapsed = time.perf_counter() - t0
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if proc.returncode == 0 and lines and lines[0] == "VALID":
            parsed: dict[str, str] = {}
            for ln in lines[1:]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    parsed[k.strip()] = v.strip()
            verdicts.append(
                CheckerVerdict(
                    checker=label,
                    valid=True,
                    entries=int(parsed.get("entries", "0")),
                    max_rank=int(parsed.get("max_rank", "0")),
                    seconds=float(parsed.get("seconds", f"{elapsed:.4f}")),
                    detail="VALID",
                )
            )
        else:
            detail = "; ".join(lines) if lines else proc.stderr.strip()
            verdicts.append(
                CheckerVerdict(
                    checker=label,
                    valid=False,
                    entries=0,
                    max_rank=0,
                    seconds=elapsed,
                    detail=detail or f"exit {proc.returncode}",
                )
            )
    return verdicts


def _write_union_cert(
    out_path: Path,
    claim: str,
    root_fen: str,
    entries: dict[str, tuple[str, int]],
    order: list[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("#cert v1\n")
        fh.write(f"#claim {claim}\n")
        fh.write(f"#root {root_fen}\n")
        for fen in order:
            m, rk = entries[fen]
            fh.write(f"{fen}\t{m}\t{rk}\n")


def evaluate_win(
    prog_path: Path,
    roots: list[tuple[str, str, int]],
    *,
    checker_mode: str,
    jobs: int,
    max_entries: int,
    claims_only: bool,
    cert_out: Path | None,
) -> dict[str, object]:
    t0 = time.perf_counter()
    claims_fn, move_fn, stats = load_ladder_program(prog_path)
    global _W_CLAIMS, _W_MOVE
    _W_CLAIMS, _W_MOVE = claims_fn, move_fn

    workers = max(1, min(4, jobs))
    fens = [r[0] for r in roots]
    outcome_map = {r[0]: r[1] for r in roots}

    pool: ProcessPoolExecutor | None = None
    if workers > 1 and len(fens) >= 256:
        pool = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(str(prog_path.resolve()),),
        )

    try:
        claim_rows = _run_batches(pool, _eval_claims_batch, fens, workers)
        true_wins = [f for f, o, _ in roots if o == "W_WIN"]
        false_claims: list[str] = []
        missed_claims: list[str] = []
        claim_errors: list[tuple[str, str]] = []
        claimed_true_wins: list[str] = []

        for fen, val, err in claim_rows:
            if err is not None:
                claim_errors.append((fen, err))
            is_true_win = outcome_map[fen] == "W_WIN"
            if val and not is_true_win:
                false_claims.append(fen)
            elif not val and is_true_win:
                missed_claims.append(fen)
            elif val and is_true_win:
                claimed_true_wins.append(fen)

        claims_sec = time.perf_counter() - t0
        if claims_only or not claimed_true_wins:
            return {
                "stats": stats,
                "true_total": len(true_wins),
                "claimed_true": len(claimed_true_wins),
                "certified": 0,
                "recall": 0.0 if not claims_only else (len(claimed_true_wins) / len(true_wins) if true_wins else 1.0),
                "claims_recall": len(claimed_true_wins) / len(true_wins) if true_wins else 1.0,
                "false_claims": false_claims,
                "missed_claims": missed_claims,
                "claim_errors": claim_errors,
                "cert_entries": 0,
                "cert_bytes": 0,
                "max_rank": 0,
                "verdicts": [],
                "uncertified_claimed": [],
                "direct_failures": {},
                "claims_seconds": claims_sec,
                "expand_seconds": 0.0,
            }

        # Collect starting wtm positions for all claimed true wins
        t_exp0 = time.perf_counter()
        btm_replies_map: dict[str, list[str]] = {}
        btm_mate_roots: set[str] = set()
        frontier_set: set[str] = set()

        for fen in claimed_true_wins:
            pos = rules.parse_position(fen)
            if pos.stm == "w":
                frontier_set.add(fen)
            else:
                reps = rules.legal_transitions(pos)
                if not reps:
                    if rules.in_check(pos):
                        btm_mate_roots.add(fen)
                    else:
                        btm_replies_map[fen] = []
                else:
                    c_list = sorted({rp.to_fen() for _, rp in reps})
                    btm_replies_map[fen] = c_list
                    frontier_set.update(c_list)

        # Wavefront BFS expansion
        visited: set[str] = set()
        chosen_move: dict[str, str] = {}
        children_map: dict[str, list[str]] = {}
        direct_failures: dict[str, tuple[str, str]] = {}
        frontier = sorted(frontier_set)
        truncated = False

        while frontier:
            remaining_budget = max_entries - len(visited)
            if remaining_budget <= 0:
                truncated = True
                break
            if len(frontier) > remaining_budget:
                frontier = frontier[:remaining_budget]
                truncated = True
            for f in frontier:
                visited.add(f)

            rows = _run_batches(pool, _eval_win_step_batch, frontier, workers)
            next_frontier: set[str] = set()
            for fen, m, children, fk, fr in rows:
                if fk is not None or children is None or m is None:
                    direct_failures[fen] = (fk or "unknown", fr or "")
                    continue
                chosen_move[fen] = m
                children_map[fen] = children
                for c in children:
                    if c not in visited:
                        next_frontier.add(c)
            frontier = sorted(next_frontier)

        # Reverse topological peeling (Kahn's algorithm) from mate-in-1 nodes
        remaining: dict[str, int] = {}
        parents: dict[str, list[str]] = {}
        max_child_rank: dict[str, int] = {}
        ranks: dict[str, int] = {}
        q: deque[str] = deque()

        for fen, children in children_map.items():
            if not children:
                ranks[fen] = 1
                q.append(fen)
                continue
            # All children must have been expanded and have no direct failure
            if any(c not in children_map for c in children):
                continue
            remaining[fen] = len(children)
            max_child_rank[fen] = 0
            for c in children:
                parents.setdefault(c, []).append(fen)

        while q:
            c = q.popleft()
            cr = ranks[c]
            for u in parents.get(c, ()):
                if cr > max_child_rank[u]:
                    max_child_rank[u] = cr
                remaining[u] -= 1
                if remaining[u] == 0:
                    ranks[u] = 1 + max_child_rank[u]
                    q.append(u)

        certified_wtm = {f: (chosen_move[f], ranks[f]) for f in ranks}
        expand_sec = time.perf_counter() - t_exp0

        verdicts: list[CheckerVerdict] = []
        cert_bytes = 0
        max_rank = max(ranks.values(), default=0)

        if certified_wtm:
            root_fen = max(certified_wtm.keys(), key=lambda f: (certified_wtm[f][1], f))
            order = sorted(certified_wtm.keys(), key=lambda f: (certified_wtm[f][1], f))
            tmp_file = None
            if cert_out is not None:
                cpath = cert_out
            else:
                fd, tmp_name = tempfile.mkstemp(prefix="ladder_win_", suffix=".cert")
                os.close(fd)
                cpath = Path(tmp_name)
                tmp_file = cpath
            try:
                _write_union_cert(cpath, "WIN w", root_fen, certified_wtm, order)
                cert_bytes = cpath.stat().st_size
                verdicts = verify_cert(cpath, checker_mode)
            finally:
                if tmp_file is not None:
                    tmp_file.unlink(missing_ok=True)

        all_valid = bool(verdicts) and all(v.valid for v in verdicts)
        certified_roots: list[str] = []
        uncertified_claimed: list[str] = []

        for fen in claimed_true_wins:
            stm = fen.split(" ")[1]
            if stm == "w":
                ok = all_valid and fen in certified_wtm
            else:
                if fen in btm_mate_roots:
                    ok = True
                else:
                    reps = btm_replies_map.get(fen, [])
                    ok = all_valid and bool(reps) and all(c in certified_wtm for c in reps)
            if ok:
                certified_roots.append(fen)
            else:
                uncertified_claimed.append(fen)

        return {
            "stats": stats,
            "true_total": len(true_wins),
            "claimed_true": len(claimed_true_wins),
            "certified": len(certified_roots),
            "recall": len(certified_roots) / len(true_wins) if true_wins else 1.0,
            "claims_recall": len(claimed_true_wins) / len(true_wins) if true_wins else 1.0,
            "false_claims": false_claims,
            "missed_claims": missed_claims,
            "claim_errors": claim_errors,
            "cert_entries": len(certified_wtm),
            "cert_bytes": cert_bytes,
            "max_rank": max_rank,
            "verdicts": verdicts,
            "uncertified_claimed": uncertified_claimed,
            "direct_failures": direct_failures,
            "visited_total": len(visited),
            "truncated": truncated,
            "claims_seconds": claims_sec,
            "expand_seconds": expand_sec,
        }
    finally:
        if pool is not None:
            pool.shutdown(wait=True)


def evaluate_hold(
    prog_path: Path,
    roots: list[tuple[str, str, int]],
    *,
    checker_mode: str,
    jobs: int,
    max_entries: int,
    claims_only: bool,
    cert_out: Path | None,
) -> dict[str, object]:
    t0 = time.perf_counter()
    claims_fn, move_fn, stats = load_ladder_program(prog_path)
    global _W_CLAIMS, _W_MOVE
    _W_CLAIMS, _W_MOVE = claims_fn, move_fn

    workers = max(1, min(4, jobs))
    fens = [r[0] for r in roots]
    outcome_map = {r[0]: r[1] for r in roots}

    pool: ProcessPoolExecutor | None = None
    if workers > 1 and len(fens) >= 256:
        pool = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(str(prog_path.resolve()),),
        )

    try:
        claim_rows = _run_batches(pool, _eval_claims_batch, fens, workers)
        true_draws = [f for f, o, _ in roots if o == "DRAW"]
        false_claims: list[str] = []
        missed_claims: list[str] = []
        claim_errors: list[tuple[str, str]] = []
        claimed_true_draws: list[str] = []

        for fen, val, err in claim_rows:
            if err is not None:
                claim_errors.append((fen, err))
            is_true_draw = outcome_map[fen] == "DRAW"
            if val and not is_true_draw:
                false_claims.append(fen)
            elif not val and is_true_draw:
                missed_claims.append(fen)
            elif val and is_true_draw:
                claimed_true_draws.append(fen)

        claims_sec = time.perf_counter() - t0
        if claims_only or not claimed_true_draws:
            return {
                "stats": stats,
                "true_total": len(true_draws),
                "claimed_true": len(claimed_true_draws),
                "certified": 0,
                "recall": 0.0 if not claims_only else (len(claimed_true_draws) / len(true_draws) if true_draws else 1.0),
                "claims_recall": len(claimed_true_draws) / len(true_draws) if true_draws else 1.0,
                "false_claims": false_claims,
                "missed_claims": missed_claims,
                "claim_errors": claim_errors,
                "cert_entries": 0,
                "cert_bytes": 0,
                "max_rank": 0,
                "verdicts": [],
                "uncertified_claimed": [],
                "direct_failures": {},
                "claims_seconds": claims_sec,
                "expand_seconds": 0.0,
            }

        # Collect starting btm positions for all claimed true draws
        t_exp0 = time.perf_counter()
        wtm_replies_map: dict[str, list[str]] = {}
        frontier_set: set[str] = set()

        for fen in claimed_true_draws:
            pos = rules.parse_position(fen)
            if pos.stm == "b":
                frontier_set.add(fen)
            else:
                reps = rules.legal_transitions(pos)
                c_list = sorted({rp.to_fen() for _, rp in reps})
                wtm_replies_map[fen] = c_list
                frontier_set.update(c_list)

        visited: set[str] = set()
        chosen_move: dict[str, str] = {}
        children_map: dict[str, list[str]] = {}
        stalemates: set[str] = set()
        direct_failures: dict[str, tuple[str, str]] = {}
        frontier = sorted(frontier_set)
        truncated = False

        while frontier:
            remaining_budget = max_entries - len(visited)
            if remaining_budget <= 0:
                truncated = True
                break
            if len(frontier) > remaining_budget:
                frontier = frontier[:remaining_budget]
                truncated = True
            for f in frontier:
                visited.add(f)

            rows = _run_batches(pool, _eval_hold_step_batch, frontier, workers)
            next_frontier: set[str] = set()
            for fen, m, children, fk, fr in rows:
                if fk == "prover_stalemate":
                    stalemates.add(fen)
                    continue
                if fk is not None or children is None or m is None:
                    direct_failures[fen] = (fk or "unknown", fr or "")
                    continue
                chosen_move[fen] = m
                children_map[fen] = children
                for c in children:
                    if c not in visited:
                        next_frontier.add(c)
            frontier = sorted(next_frontier)

        # Co-inductive reverse-failure pruning: greatest fixed point of valid ATLEAST_DRAW b entries
        bad: set[str] = set(direct_failures.keys())
        parents: dict[str, list[str]] = {}
        q: deque[str] = deque()

        for fen, children in children_map.items():
            for c in children:
                if c not in chosen_move and c not in stalemates:
                    # Unexpanded or directly failed child -> fen is bad
                    if fen not in bad:
                        bad.add(fen)
                        q.append(fen)
                elif c in chosen_move:
                    parents.setdefault(c, []).append(fen)

        while q:
            c = q.popleft()
            for u in parents.get(c, ()):
                if u not in bad:
                    bad.add(u)
                    q.append(u)

        certified_btm = {f: (chosen_move[f], 0) for f in chosen_move if f not in bad}
        covered_btm = set(certified_btm.keys()) | stalemates
        expand_sec = time.perf_counter() - t_exp0

        verdicts: list[CheckerVerdict] = []
        cert_bytes = 0

        if certified_btm:
            order = sorted(certified_btm.keys())
            root_fen = order[0]
            tmp_file = None
            if cert_out is not None:
                cpath = cert_out
            else:
                fd, tmp_name = tempfile.mkstemp(prefix="ladder_hold_", suffix=".cert")
                os.close(fd)
                cpath = Path(tmp_name)
                tmp_file = cpath
            try:
                _write_union_cert(cpath, "ATLEAST_DRAW b", root_fen, certified_btm, order)
                cert_bytes = cpath.stat().st_size
                verdicts = verify_cert(cpath, checker_mode)
            finally:
                if tmp_file is not None:
                    tmp_file.unlink(missing_ok=True)

        all_valid = (not certified_btm) or (bool(verdicts) and all(v.valid for v in verdicts))
        certified_roots: list[str] = []
        uncertified_claimed: list[str] = []

        for fen in claimed_true_draws:
            stm = fen.split(" ")[1]
            if stm == "b":
                ok = all_valid and fen in covered_btm
            else:
                reps = wtm_replies_map.get(fen, [])
                ok = all_valid and all(c in covered_btm for c in reps)
            if ok:
                certified_roots.append(fen)
            else:
                uncertified_claimed.append(fen)

        return {
            "stats": stats,
            "true_total": len(true_draws),
            "claimed_true": len(claimed_true_draws),
            "certified": len(certified_roots),
            "recall": len(certified_roots) / len(true_draws) if true_draws else 1.0,
            "claims_recall": len(claimed_true_draws) / len(true_draws) if true_draws else 1.0,
            "false_claims": false_claims,
            "missed_claims": missed_claims,
            "claim_errors": claim_errors,
            "cert_entries": len(certified_btm),
            "cert_bytes": cert_bytes,
            "stalemates": len(stalemates),
            "max_rank": 0,
            "verdicts": verdicts,
            "uncertified_claimed": uncertified_claimed,
            "direct_failures": direct_failures,
            "visited_total": len(visited),
            "truncated": truncated,
            "claims_seconds": claims_sec,
            "expand_seconds": expand_sec,
        }
    finally:
        if pool is not None:
            pool.shutdown(wait=True)


def _print_side_report(label: str, res: dict[str, object], show_failures: int) -> None:
    st: ProgramStats = res["stats"]  # type: ignore[assignment]
    verdicts: list[CheckerVerdict] = res["verdicts"]  # type: ignore[assignment]
    verdict_str = (
        ", ".join(f"{v.checker}:{'VALID' if v.valid else 'INVALID'}({v.seconds:.2f}s)" for v in verdicts)
        if verdicts
        else "skipped"
    )
    print(f"=== {label} ({st.path}) ===")
    print(
        f"  Length     : {st.total_nodes} AST nodes ({st.total_bytes} B) "
        f"[claims: {st.claims_nodes} nodes, move: {st.move_nodes} nodes, move-only: {st.move_only_nodes} nodes]"
    )
    print(
        f"  Claims     : {res['claimed_true']}/{res['true_total']} "
        f"({100.0 * float(res['claims_recall']):.2f}%) | "
        f"false claims: {len(res['false_claims'])} | missed: {len(res['missed_claims'])}"  # type: ignore[arg-type]
    )
    print(
        f"  Certified  : {res['certified']}/{res['true_total']} "
        f"({100.0 * float(res['recall']):.2f}%) | "
        f"uncertified claimed: {len(res['uncertified_claimed'])}"  # type: ignore[arg-type]
    )
    print(
        f"  Union cert : {res['cert_entries']} entries, {res['cert_bytes']} B, "
        f"max_rank={res['max_rank']}, checker=[{verdict_str}]"
    )
    print(
        f"  Timing     : claims={float(res['claims_seconds']):.2f}s, "
        f"expand={float(res['expand_seconds']):.2f}s"
    )
    if show_failures > 0:
        fc: list[str] = res["false_claims"]  # type: ignore[assignment]
        mc: list[str] = res["missed_claims"]  # type: ignore[assignment]
        uc: list[str] = res["uncertified_claimed"]  # type: ignore[assignment]
        df: dict[str, tuple[str, str]] = res["direct_failures"]  # type: ignore[assignment]
        if fc:
            print(f"  Sample false claims ({len(fc)} total):")
            for f in fc[:show_failures]:
                print(f"    FALSE: {f}")
        if mc:
            print(f"  Sample missed claims ({len(mc)} total):")
            for f in mc[:show_failures]:
                print(f"    MISS : {f}")
        if uc:
            print(f"  Sample uncertified claimed roots ({len(uc)} total):")
            for f in uc[:show_failures]:
                print(f"    UNCERT: {f}")
        if df:
            print(f"  Sample direct expansion failures ({len(df)} total):")
            for f, (fk, fr) in list(df.items())[:show_failures]:
                print(f"    FAIL ({fk}): {f} -- {fr}")


def cmd_score(args: argparse.Namespace) -> int:
    sig = args.cls.upper()
    if sig != "KPK":
        raise SystemExit(f"unsupported class {sig!r} (only KPK implemented)")

    win_path = Path(args.win) if args.win else BASE_DIR / "kpk" / "win.py"
    hold_path = Path(args.hold) if args.hold else BASE_DIR / "kpk" / "hold.py"
    tb_dir = Path(args.tb_dir) if args.tb_dir else None

    all_rows = load_tablebase_truth(args.board, sig, tb_dir)
    if args.all:
        roots = all_rows
        mode_desc = f"ALL ({len(roots)} positions)"
    else:
        n = args.sample if args.sample is not None else 2000
        roots = select_roots(all_rows, n, args.seed)
        mode_desc = f"SAMPLE N={len(roots)} seed={args.seed} (of {len(all_rows)})"

    n_w = sum(1 for _, o, _ in roots if o == "W_WIN")
    n_d = sum(1 for _, o, _ in roots if o == "DRAW")
    print(f"Scoring {sig} on {args.board} [{mode_desc}]: {n_w} W_WIN, {n_d} DRAW")

    cert_dir = Path(args.cert_dir) if args.cert_dir else None
    win_cert = cert_dir / f"{args.board}_{sig}_win.cert" if cert_dir else None
    hold_cert = cert_dir / f"{args.board}_{sig}_hold.cert" if cert_dir else None

    win_res = evaluate_win(
        win_path,
        roots,
        checker_mode=args.checker,
        jobs=args.jobs,
        max_entries=args.max_entries,
        claims_only=args.claims_only,
        cert_out=win_cert,
    )
    hold_res = evaluate_hold(
        hold_path,
        roots,
        checker_mode=args.checker,
        jobs=args.jobs,
        max_entries=args.max_entries,
        claims_only=args.claims_only,
        cert_out=hold_cert,
    )

    _print_side_report("WIN  (White)", win_res, args.show_failures)
    _print_side_report("HOLD (Black)", hold_res, args.show_failures)

    if args.json:
        out_json = Path(args.json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "class": sig,
            "board": args.board,
            "mode": "all" if args.all else "sample",
            "sample": None if args.all else len(roots),
            "seed": None if args.all else args.seed,
            "total_tb": len(all_rows),
            "eval_roots": len(roots),
            "win": {
                "nodes": win_res["stats"].total_nodes,
                "bytes": win_res["stats"].total_bytes,
                "claims_nodes": win_res["stats"].claims_nodes,
                "move_nodes": win_res["stats"].move_nodes,
                "move_only_nodes": win_res["stats"].move_only_nodes,
                "true_total": win_res["true_total"],
                "claimed_true": win_res["claimed_true"],
                "certified": win_res["certified"],
                "recall": win_res["recall"],
                "false_claims": len(win_res["false_claims"]),
                "missed_claims": len(win_res["missed_claims"]),
                "cert_entries": win_res["cert_entries"],
                "cert_bytes": win_res["cert_bytes"],
                "max_rank": win_res["max_rank"],
                "verdicts": [v.__dict__ for v in win_res["verdicts"]],
                "claims_seconds": win_res["claims_seconds"],
                "expand_seconds": win_res["expand_seconds"],
            },
            "hold": {
                "nodes": hold_res["stats"].total_nodes,
                "bytes": hold_res["stats"].total_bytes,
                "claims_nodes": hold_res["stats"].claims_nodes,
                "move_nodes": hold_res["stats"].move_nodes,
                "move_only_nodes": hold_res["stats"].move_only_nodes,
                "true_total": hold_res["true_total"],
                "claimed_true": hold_res["claimed_true"],
                "certified": hold_res["certified"],
                "recall": hold_res["recall"],
                "false_claims": len(hold_res["false_claims"]),
                "missed_claims": len(hold_res["missed_claims"]),
                "cert_entries": hold_res["cert_entries"],
                "cert_bytes": hold_res["cert_bytes"],
                "max_rank": hold_res["max_rank"],
                "verdicts": [v.__dict__ for v in hold_res["verdicts"]],
                "claims_seconds": hold_res["claims_seconds"],
                "expand_seconds": hold_res["expand_seconds"],
            },
        }
        out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="09-ladder KPK scoring harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("score", help="Score win.py and hold.py against tablebase truth")
    sc.add_argument("--class", dest="cls", required=True, help="Material class (e.g. KPK)")
    sc.add_argument("--board", required=True, help="Board size WxH (e.g. 5x5, 6x6, 8x8)")
    grp = sc.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true", help="Evaluate every position in the class")
    grp.add_argument("--sample", type=int, default=None, help="Stratified random sample size")
    sc.add_argument("--seed", type=int, default=1, help="RNG seed for --sample")
    sc.add_argument("--win", default=None, help="Path to win.py (default: kpk/win.py)")
    sc.add_argument("--hold", default=None, help="Path to hold.py (default: kpk/hold.py)")
    sc.add_argument(
        "--checker",
        choices=("mcheck2", "mcheck", "both"),
        default="mcheck2",
        help="Independent checker(s) to verify emitted union certificates",
    )
    sc.add_argument("--jobs", type=int, default=4, help="Parallel worker count (max 4)")
    sc.add_argument("--tb-dir", default=None, help="Override tablebase directory")
    sc.add_argument("--cert-dir", default=None, help="Directory to keep emitted certificates")
    sc.add_argument("--max-entries", type=int, default=500000, help="Max union expansion entries")
    sc.add_argument("--show-failures", type=int, default=10, help="Number of sample failures to print")
    sc.add_argument("--claims-only", action="store_true", help="Check claims() only (no certificate expansion)")
    sc.add_argument("--json", default=None, help="Optional JSON summary output path")
    sc.set_defaults(func=cmd_score)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
