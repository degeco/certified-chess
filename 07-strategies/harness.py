#!/usr/bin/env python3
"""Strategy-program expansion, validation, scoring, whole-class union, and rank-audit harness.

Implements SPEC v1.1 and LOOP v1 (round 2 rules):
- Program length measured in AST nodes (ast.walk count after removing docstrings) and stripped bytes.
- 2-ply lookahead limit (own move + opponent replies; no recursion, no while loops, no memo tables),
  enforced both statically (AST) and dynamically (runtime guarded `rules` proxy).
- Explicit position-to-move exception tables allowed at full price (counted in nodes and bytes).
- Whole-class expansion (`expand-all`) emitting a single mcheck-verified union certificate.
- Potential ranking audit (`audit-rank`) over union certificates.
"""

from __future__ import annotations

import argparse
import ast
import builtins
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tokenize
from typing import Callable

BASE_DIR = Path(__file__).resolve().parent
CHECKER_DIR = BASE_DIR.parent / "03-checker"
MCHECK_PATH = CHECKER_DIR / "mcheck.py"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import rules  # noqa: E402

VALID_CLAIMS = frozenset({"WIN w", "WIN b", "ATLEAST_DRAW w", "ATLEAST_DRAW b"})
FORBIDDEN_CALL_NAMES = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "breakpoint",
        "input",
        "globals",
        "locals",
        "vars",
        "setattr",
        "delattr",
        "getattr",
        "type",
        "object",
        "super",
    }
)
FORBIDDEN_ATTR_NAMES = frozenset(
    {
        "__builtins__",
        "__import__",
        "__subclasses__",
        "__globals__",
        "__loader__",
        "__spec__",
        "__doc__",
        "__code__",
        "__dict__",
        "__closure__",
        "__defaults__",
        "__kwdefaults__",
        "__class__",
    }
)
FORBIDDEN_RULES_ATTRS = frozenset(
    {
        "perft",
        "Position",
        "_pseudo_legal_moves",
        "_apply_board",
        "_finish_position",
        "_has_legal_ep_capture",
    }
)
MUTATING_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "pop",
        "popitem",
        "remove",
        "clear",
        "update",
        "setdefault",
        "add",
        "discard",
        "sort",
        "reverse",
    }
)

MATERIAL_SPECS: dict[str, tuple[str, ...]] = {
    "KQK": ("K", "Q", "k"),
    "KRK": ("K", "R", "k"),
    "KK": ("K", "k"),
}


class ProgramValidationError(ValueError):
    """Raised when a strategy program violates harness static constraints."""


class LookaheadLimitError(RuntimeError):
    """Raised at runtime when a strategy program exceeds the 2-ply lookahead limit."""


@dataclass(frozen=True)
class ExpandResult:
    ok: bool
    claim: str
    root: str
    entries: dict[str, tuple[str, int]]  # pos_str -> (move_str, rank)
    entry_order: tuple[str, ...]
    max_rank: int
    seconds: float
    failure_kind: str | None = None
    failure_pos: str | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class RootScoreResult:
    root: str
    board_size: str
    claim: str
    ok: bool
    entries: int
    max_rank: int
    expand_seconds: float
    verify_seconds: float
    failure_kind: str | None = None
    failure_pos: str | None = None
    failure_reason: str | None = None


def _collect_docstring_nodes(tree: ast.AST) -> set[int]:
    """Return id() set of ast.Constant nodes that serve as docstrings."""
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                doc_ids.add(id(node.body[0].value))
    return doc_ids


def _byte_col_to_char_col(line: str, byte_col: int) -> int:
    return len(line.encode("utf-8")[:byte_col].decode("utf-8"))


def measure_program_length(source: str) -> int:
    """Return program length in UTF-8 bytes after stripping comments, docstrings, and blank lines."""
    tree = ast.parse(source)
    doc_ids = _collect_docstring_nodes(tree)
    lines = source.splitlines()
    keep = [[True] * len(line) for line in lines]

    def mask_span(srow: int, scol: int, erow: int, ecol: int) -> None:
        for row in range(srow, erow + 1):
            idx = row - 1
            if not (0 <= idx < len(keep)):
                continue
            start_c = scol if row == srow else 0
            end_c = ecol if row == erow else len(keep[idx])
            for c in range(max(0, start_c), min(len(keep[idx]), end_c)):
                keep[idx][c] = False

    for node in ast.walk(tree):
        if id(node) in doc_ids:
            assert (
                node.lineno is not None
                and node.end_lineno is not None
                and node.col_offset is not None
                and node.end_col_offset is not None
            )
            scol = _byte_col_to_char_col(lines[node.lineno - 1], node.col_offset)
            ecol = _byte_col_to_char_col(lines[node.end_lineno - 1], node.end_col_offset)
            mask_span(node.lineno, scol, node.end_lineno, ecol)

    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            srow, scol = tok.start
            erow, ecol = tok.end
            mask_span(srow, scol, erow, ecol)

    out_lines: list[str] = []
    for line, mask in zip(lines, keep):
        cleaned = "".join(ch for ch, k in zip(line, mask) if k).rstrip()
        if cleaned:
            out_lines.append(cleaned)

    if not out_lines:
        return 0
    return len(("\n".join(out_lines) + "\n").encode("utf-8"))


def measure_program_nodes(source: str) -> int:
    """Return AST node count (`ast.walk`) after removing docstrings (official round-2 metric)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body.pop(0)
    return sum(1 for _ in ast.walk(tree))


def _is_pure_literal_expr(node: ast.AST) -> bool:
    """Return True if `node` is a pure literal/constant expression (for read-only tables)."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _is_pure_literal_expr(node.operand)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_pure_literal_expr(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (k is not None and _is_pure_literal_expr(k) and _is_pure_literal_expr(v))
            for k, v in zip(node.keys, node.values)
        )
    return False


def _root_name(node: ast.AST) -> str | None:
    """Extract the base ast.Name identifier of a chained subscript/attribute target."""
    cur = node
    while isinstance(cur, (ast.Subscript, ast.Attribute)):
        cur = cur.value
    return cur.id if isinstance(cur, ast.Name) else None


def _check_no_recursion(tree: ast.Module) -> None:
    """Reject direct or mutual recursion among defined functions (conservative by function name)."""
    defined: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.setdefault(node.name, []).append(node)

    edges: dict[str, set[str]] = {name: set() for name in defined}
    for name, fn_nodes in defined.items():
        for fn in fn_nodes:
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name) and sub.func.id in defined:
                        edges[name].add(sub.func.id)

    color: dict[str, int] = {name: 0 for name in defined}  # 0=unvisited, 1=visiting, 2=done

    def dfs(u: str, path: list[str]) -> None:
        color[u] = 1
        for v in edges[u]:
            if color[v] == 1:
                cycle = " -> ".join(path[path.index(v) :] + [v])
                raise ProgramValidationError(f"recursion forbidden (cycle: {cycle})")
            if color[v] == 0:
                dfs(v, path + [v])
        color[u] = 2

    for name in sorted(defined):
        if color[name] == 0:
            dfs(name, [name])


def _check_lookahead_and_state(tree: ast.Module) -> None:
    """Static checks for round-2 rule 2: no recursion, no while loops, no memo tables/mutable globals."""
    _check_no_recursion(tree)

    # Collect top-level assigned variable names and verify module body has no sneaky closures/calls.
    module_vars: set[str] = set()
    defined_funcs: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_funcs.add(stmt.name)
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue  # module docstring
        if isinstance(stmt, ast.Assign):
            if not _is_pure_literal_expr(stmt.value):
                raise ProgramValidationError(
                    "module-level assignments must be pure constant/literal tables (no calls/closures)"
                )
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    module_vars.add(tgt.id)
                else:
                    raise ProgramValidationError("module-level assignment must bind a simple name")
            continue
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.value is not None and not _is_pure_literal_expr(stmt.value):
                raise ProgramValidationError(
                    "module-level annotated assignments must be pure constant/literal tables"
                )
            module_vars.add(stmt.target.id)
            continue
        raise ProgramValidationError(
            f"disallowed top-level statement {type(stmt).__name__}: only imports, literal tables, and defs allowed"
        )

    protected_names = module_vars | defined_funcs

    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            raise ProgramValidationError("while loops are forbidden (no search loops)")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ProgramValidationError("global/nonlocal statements are forbidden (no memo tables)")
        if isinstance(node, ast.ClassDef):
            raise ProgramValidationError("class definitions are forbidden in strategy programs")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Forbid mutable default arguments (classic memo table idiom).
            for default in list(node.args.defaults) + [
                d for d in node.args.kw_defaults if d is not None
            ]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    raise ProgramValidationError(
                        f"mutable default argument forbidden in {node.name}() (no memo tables)"
                    )
                if isinstance(default, ast.Call):
                    raise ProgramValidationError(
                        f"call expression in default argument forbidden in {node.name}()"
                    )
            # Inside function body, forbid mutating module-level tables or function attributes.
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for tgt in sub.targets:
                        if isinstance(tgt, (ast.Subscript, ast.Attribute)):
                            rname = _root_name(tgt)
                            if rname in protected_names:
                                raise ProgramValidationError(
                                    f"mutating module/function object {rname!r} is forbidden (no memo tables)"
                                )
                elif isinstance(sub, (ast.AugAssign, ast.AnnAssign)):
                    tgt = sub.target
                    if isinstance(tgt, (ast.Subscript, ast.Attribute)):
                        rname = _root_name(tgt)
                        if rname in protected_names:
                            raise ProgramValidationError(
                                f"mutating module/function object {rname!r} is forbidden (no memo tables)"
                            )
                elif isinstance(sub, ast.Delete):
                    for tgt in sub.targets:
                        rname = _root_name(tgt)
                        if rname in protected_names:
                            raise ProgramValidationError(
                                f"deleting from module object {rname!r} is forbidden"
                            )
                elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    if sub.func.attr in MUTATING_METHODS:
                        rname = _root_name(sub.func.value)
                        if rname in protected_names:
                            raise ProgramValidationError(
                                f"calling mutating method .{sub.func.attr}() on {rname!r} is forbidden (no memo tables)"
                            )


def validate_program(
    path: Path,
    length_limit: int | None = None,
    *,
    node_limit: int | None = None,
    enforce_lookahead: bool = True,
) -> tuple[str, int, int]:
    """Validate a strategy program file and return (source, stripped_bytes, ast_nodes)."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProgramValidationError(f"cannot read program {path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ProgramValidationError(f"syntax error: {exc}") from exc

    move_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "move"
    ]
    if not move_defs:
        raise ProgramValidationError("program must define a top-level function move(pos)")
    move_fn = move_defs[-1]
    pos_args = len(move_fn.args.posonlyargs) + len(move_fn.args.args)
    required_args = pos_args - len(move_fn.args.defaults)
    if move_fn.args.vararg is None and (pos_args < 1 or required_args > 1):
        raise ProgramValidationError("move() must accept a single positional argument (pos)")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "rules":
                    raise ProgramValidationError(
                        f"forbidden import {alias.name!r}: only 'rules' may be imported"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module != "rules":
                raise ProgramValidationError(
                    f"forbidden import from {node.module!r}: only 'rules' may be imported"
                )
            if enforce_lookahead:
                for alias in node.names:
                    if alias.name in FORBIDDEN_RULES_ATTRS or alias.name == "*":
                        raise ProgramValidationError(
                            f"forbidden import from rules: {alias.name!r}"
                        )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                raise ProgramValidationError(f"forbidden builtin call: {node.func.id}")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_CALL_NAMES or node.id in FORBIDDEN_ATTR_NAMES:
                raise ProgramValidationError(f"forbidden identifier: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTR_NAMES:
                raise ProgramValidationError(f"forbidden attribute access: {node.attr}")
            if enforce_lookahead and node.attr in FORBIDDEN_RULES_ATTRS:
                raise ProgramValidationError(
                    f"forbidden rules helper/attribute: {node.attr}"
                )

    if enforce_lookahead:
        _check_lookahead_and_state(tree)

    length_bytes = measure_program_length(source)
    length_nodes = measure_program_nodes(source)
    if length_limit is not None and length_bytes > length_limit:
        raise ProgramValidationError(
            f"program length {length_bytes} bytes exceeds family limit {length_limit} bytes"
        )
    if node_limit is not None and length_nodes > node_limit:
        raise ProgramValidationError(
            f"program length {length_nodes} AST nodes exceeds limit {node_limit} nodes"
        )

    return source, length_bytes, length_nodes


class _GuardedRules:
    """Runtime proxy around `rules` enforcing the 2-ply lookahead limit per move(pos) call.

    Ply 0: root `pos` passed to move(pos).
    Ply 1: positions after prover's move (`legal_transitions(pos)` / `apply_move(pos, m)`).
    Ply 2: positions after opponent's reply (`legal_transitions(nxt)` / `apply_move(nxt, r)`).
    Calling move generation or `apply_move` on a ply-2 or untracked Position raises LookaheadLimitError.
    """

    WHITE_PIECES = rules.WHITE_PIECES
    BLACK_PIECES = rules.BLACK_PIECES
    ALL_PIECES = rules.ALL_PIECES
    PROMO_PIECES = rules.PROMO_PIECES
    KNIGHT_OFFSETS = rules.KNIGHT_OFFSETS
    KING_OFFSETS = rules.KING_OFFSETS
    ORTHO_DIRS = rules.ORTHO_DIRS
    DIAG_DIRS = rules.DIAG_DIRS
    ALL_DIRS = rules.ALL_DIRS

    opponent = staticmethod(rules.opponent)
    piece_color = staticmethod(rules.piece_color)
    square_name = staticmethod(rules.square_name)
    parse_square = staticmethod(rules.parse_square)
    is_square_attacked = staticmethod(rules.is_square_attacked)
    in_check = staticmethod(rules.in_check)
    format_position = staticmethod(rules.format_position)
    parse_position = staticmethod(rules.parse_position)

    def __init__(self) -> None:
        self._ply: dict[rules.Position, int] | None = None

    def begin_call(self, root_pos: rules.Position) -> None:
        self._ply = {root_pos: 0}

    def end_call(self) -> None:
        self._ply = None

    def _require_ply(self, pos: rules.Position, fn_name: str) -> int:
        if self._ply is None:
            raise LookaheadLimitError(f"{fn_name}() called outside move()")
        d = self._ply.get(pos)
        if d is None:
            raise LookaheadLimitError(
                f"{fn_name}() called on untracked/synthesized Position (ply unknown)"
            )
        if d >= 2:
            raise LookaheadLimitError(
                f"lookahead limit exceeded: {fn_name}() called at ply {d} (max allowed is ply 0..1)"
            )
        return d

    def legal_transitions(self, pos: rules.Position) -> list[tuple[str, rules.Position]]:
        d = self._require_ply(pos, "legal_transitions")
        res = rules.legal_transitions(pos)
        assert self._ply is not None
        nxt_d = d + 1
        for _, nxt in res:
            prev = self._ply.get(nxt)
            if prev is None or nxt_d < prev:
                self._ply[nxt] = nxt_d
        return res

    def legal_moves(self, pos: rules.Position) -> list[str]:
        self._require_ply(pos, "legal_moves")
        return rules.legal_moves(pos)

    def apply_move(self, pos: rules.Position, move_str: str) -> rules.Position:
        d = self._require_ply(pos, "apply_move")
        nxt = rules.apply_move(pos, move_str)
        assert self._ply is not None
        nxt_d = d + 1
        prev = self._ply.get(nxt)
        if prev is None or nxt_d < prev:
            self._ply[nxt] = nxt_d
        return nxt

    def perft(self, *args: object, **kwargs: object) -> int:
        raise LookaheadLimitError("rules.perft() is forbidden by the lookahead limit")


def load_strategy_namespace(
    path: Path,
    length_limit: int | None = None,
    *,
    enforce_lookahead: bool = True,
) -> tuple[dict[str, object], Callable[[rules.Position], str], int, int]:
    """Validate and load a strategy program, returning (namespace, move_fn, bytes, nodes)."""
    source, length_bytes, length_nodes = validate_program(
        path, length_limit=length_limit, enforce_lookahead=enforce_lookahead
    )
    guarded = _GuardedRules() if enforce_lookahead else None

    safe_builtins = dict(vars(builtins))
    if guarded is not None:
        def _restricted_import(
            name: str,
            globals_: object = None,
            locals_: object = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name != "rules" or level != 0:
                raise ImportError(f"forbidden import: {name!r}")
            return guarded

        safe_builtins["__import__"] = _restricted_import

    namespace: dict[str, object] = {
        "__builtins__": safe_builtins,
        "__name__": f"strategy_{path.stem}",
        "__file__": str(path.resolve()),
    }
    try:
        exec(compile(source, str(path), "exec"), namespace)
    except Exception as exc:
        raise ProgramValidationError(f"error loading program: {exc}") from exc

    raw_move = namespace.get("move")
    if not callable(raw_move):
        raise ProgramValidationError("loaded program has no callable move()")

    if guarded is None:
        return namespace, raw_move, length_bytes, length_nodes  # type: ignore[return-value]

    def wrapped_move(pos: rules.Position) -> str:
        guarded.begin_call(pos)
        try:
            return raw_move(pos)  # type: ignore[no-any-return]
        finally:
            guarded.end_call()

    return namespace, wrapped_move, length_bytes, length_nodes


def load_strategy(
    path: Path,
    length_limit: int | None = None,
    *,
    enforce_lookahead: bool = True,
) -> tuple[Callable[[rules.Position], str], int]:
    """Validate and load a strategy program, returning (move_fn, stripped_length_bytes)."""
    _, move_fn, length_bytes, _ = load_strategy_namespace(
        path, length_limit=length_limit, enforce_lookahead=enforce_lookahead
    )
    return move_fn, length_bytes


def expand_strategy(
    move_fn: Callable[[rules.Position], str],
    claim: str,
    root_str: str,
    max_entries: int = 20000,
) -> ExpandResult:
    """Expand `move_fn` from `root_str` under `claim` into a SPEC section 4 certificate."""
    t0 = time.perf_counter()

    def fail(kind: str, pos: str, reason: str) -> ExpandResult:
        return ExpandResult(
            ok=False,
            claim=claim,
            root=root_str,
            entries={},
            entry_order=(),
            max_rank=0,
            seconds=time.perf_counter() - t0,
            failure_kind=kind,
            failure_pos=pos,
            failure_reason=reason,
        )

    if claim not in VALID_CLAIMS:
        return fail("invalid_claim", root_str, f"unsupported claim: {claim!r}")
    if max_entries < 0:
        return fail("invalid_arg", root_str, f"max_entries must be >= 0, got {max_entries}")

    try:
        root_pos = rules.parse_position(root_str)
    except ValueError as exc:
        return fail("invalid_root", root_str, str(exc))
    if root_pos.to_fen() != root_str:
        return fail(
            "invalid_root",
            root_str,
            f"non-canonical root string (expected {root_pos.to_fen()!r})",
        )

    claim_kind, prover = claim.split(" ")

    start_nodes: list[tuple[str, rules.Position]] = []
    if root_pos.stm == prover:
        start_nodes.append((root_str, root_pos))
    else:
        root_replies = rules.legal_transitions(root_pos)
        if not root_replies:
            if claim_kind == "WIN" and not rules.in_check(root_pos):
                return fail(
                    "stalemate",
                    root_str,
                    "opponent has no legal move at root and is not in check (stalemate)",
                )
            return ExpandResult(
                ok=True,
                claim=claim,
                root=root_str,
                entries={},
                entry_order=(),
                max_rank=0,
                seconds=time.perf_counter() - t0,
            )
        for _, reply_pos in root_replies:
            start_nodes.append((reply_pos.to_fen(), reply_pos))

    if claim_kind == "WIN":
        return _expand_win(move_fn, claim, root_str, start_nodes, max_entries, t0)
    return _expand_atleast_draw(move_fn, claim, root_str, start_nodes, max_entries, t0)


def _expand_win(
    move_fn: Callable[[rules.Position], str],
    claim: str,
    root_str: str,
    start_nodes: list[tuple[str, rules.Position]],
    max_entries: int,
    t0: float,
) -> ExpandResult:
    """Iterative DFS expansion for WIN claims with cycle detection and longest-path ranks."""

    def fail(kind: str, pos: str, reason: str) -> ExpandResult:
        return ExpandResult(
            ok=False,
            claim=claim,
            root=root_str,
            entries={},
            entry_order=(),
            max_rank=0,
            seconds=time.perf_counter() - t0,
            failure_kind=kind,
            failure_pos=pos,
            failure_reason=reason,
        )

    state: dict[str, int] = {}
    chosen_move: dict[str, str] = {}
    children_map: dict[str, list[str]] = {}
    ranks: dict[str, int] = {}
    entry_order: list[str] = []
    stack: list[list[object]] = []

    def enter_node(pos_str: str, pos: rules.Position) -> ExpandResult | None:
        if len(chosen_move) >= max_entries:
            return fail(
                "entry_limit",
                pos_str,
                f"expansion exceeded max_entries={max_entries}",
            )
        transitions = rules.legal_transitions(pos)
        if not transitions:
            if rules.in_check(pos):
                return fail("checkmated", pos_str, "prover is checkmated")
            return fail(
                "stalemate", pos_str, "prover has no legal moves (stalemate) in WIN claim"
            )
        trans_dict = dict(transitions)
        try:
            move_str = move_fn(pos)
        except LookaheadLimitError as exc:
            return fail("lookahead_limit", pos_str, str(exc))
        except Exception as exc:
            return fail("program_error", pos_str, f"move() raised {type(exc).__name__}: {exc}")
        if not isinstance(move_str, str) or not move_str:
            return fail("missing_move", pos_str, f"move() returned invalid/missing move: {move_str!r}")
        q_pos = trans_dict.get(move_str)
        if q_pos is None:
            return fail("illegal_move", pos_str, f"move() returned illegal move {move_str!r}")

        replies = rules.legal_transitions(q_pos)
        if not replies:
            if not rules.in_check(q_pos):
                return fail(
                    "stalemate",
                    pos_str,
                    f"move {move_str} leads to opponent stalemate",
                )
            chosen_move[pos_str] = move_str
            entry_order.append(pos_str)
            children_map[pos_str] = []
            ranks[pos_str] = 1
            state[pos_str] = 2
            return None

        child_list: list[tuple[str, rules.Position]] = []
        seen_children: set[str] = set()
        for _, rpos in replies:
            r_str = rpos.to_fen()
            if r_str not in seen_children:
                seen_children.add(r_str)
                child_list.append((r_str, rpos))

        chosen_move[pos_str] = move_str
        entry_order.append(pos_str)
        children_map[pos_str] = [cs for cs, _ in child_list]
        state[pos_str] = 1
        stack.append([pos_str, child_list, 0])
        return None

    for start_str, start_pos in start_nodes:
        if state.get(start_str) == 2:
            continue
        err = enter_node(start_str, start_pos)
        if err is not None:
            return err
        while stack:
            frame = stack[-1]
            u_str: str = frame[0]  # type: ignore[assignment]
            child_list: list[tuple[str, rules.Position]] = frame[1]  # type: ignore[assignment]
            idx: int = frame[2]  # type: ignore[assignment]
            if idx < len(child_list):
                frame[2] = idx + 1
                c_str, c_pos = child_list[idx]
                st = state.get(c_str, 0)
                if st == 1:
                    return fail(
                        "cycle",
                        c_str,
                        f"cycle detected: {u_str} ({chosen_move[u_str]}) reaches active ancestor {c_str}",
                    )
                if st == 0:
                    err = enter_node(c_str, c_pos)
                    if err is not None:
                        return err
            else:
                ranks[u_str] = 1 + max(ranks[c] for c in children_map[u_str])
                state[u_str] = 2
                stack.pop()

    entries = {p: (chosen_move[p], ranks[p]) for p in entry_order}
    max_rank = max(ranks.values(), default=0)
    return ExpandResult(
        ok=True,
        claim=claim,
        root=root_str,
        entries=entries,
        entry_order=tuple(entry_order),
        max_rank=max_rank,
        seconds=time.perf_counter() - t0,
    )


def _expand_atleast_draw(
    move_fn: Callable[[rules.Position], str],
    claim: str,
    root_str: str,
    start_nodes: list[tuple[str, rules.Position]],
    max_entries: int,
    t0: float,
) -> ExpandResult:
    """BFS expansion for ATLEAST_DRAW claims applying the SPEC v1.1 prover-stalemate rule."""

    def fail(kind: str, pos: str, reason: str) -> ExpandResult:
        return ExpandResult(
            ok=False,
            claim=claim,
            root=root_str,
            entries={},
            entry_order=(),
            max_rank=0,
            seconds=time.perf_counter() - t0,
            failure_kind=kind,
            failure_pos=pos,
            failure_reason=reason,
        )

    visited: set[str] = set()
    chosen_move: dict[str, str] = {}
    entry_order: list[str] = []
    queue: deque[tuple[str, rules.Position]] = deque(start_nodes)

    while queue:
        pos_str, pos = queue.popleft()
        if pos_str in visited:
            continue
        visited.add(pos_str)

        transitions = rules.legal_transitions(pos)
        if not transitions:
            if rules.in_check(pos):
                return fail("checkmated", pos_str, "prover is checkmated in ATLEAST_DRAW claim")
            continue

        if len(chosen_move) >= max_entries:
            return fail(
                "entry_limit",
                pos_str,
                f"expansion exceeded max_entries={max_entries}",
            )

        trans_dict = dict(transitions)
        try:
            move_str = move_fn(pos)
        except LookaheadLimitError as exc:
            return fail("lookahead_limit", pos_str, str(exc))
        except Exception as exc:
            return fail("program_error", pos_str, f"move() raised {type(exc).__name__}: {exc}")
        if not isinstance(move_str, str) or not move_str:
            return fail("missing_move", pos_str, f"move() returned invalid/missing move: {move_str!r}")
        q_pos = trans_dict.get(move_str)
        if q_pos is None:
            return fail("illegal_move", pos_str, f"move() returned illegal move {move_str!r}")

        chosen_move[pos_str] = move_str
        entry_order.append(pos_str)

        for _, rpos in rules.legal_transitions(q_pos):
            r_str = rpos.to_fen()
            if r_str not in visited:
                queue.append((r_str, rpos))

    entries = {p: (chosen_move[p], 0) for p in entry_order}
    return ExpandResult(
        ok=True,
        claim=claim,
        root=root_str,
        entries=entries,
        entry_order=tuple(entry_order),
        max_rank=0,
        seconds=time.perf_counter() - t0,
    )


def write_certificate(result: ExpandResult, out_path: Path) -> None:
    """Write a SPEC section 4 certificate file from a successful ExpandResult."""
    if not result.ok:
        raise ValueError("cannot write certificate from a failed expansion")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#cert v1",
        f"#claim {result.claim}",
        f"#root {result.root}",
    ]
    for pos_str in result.entry_order:
        move_str, rank = result.entries[pos_str]
        lines.append(f"{pos_str}\t{move_str}\t{rank}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_with_mcheck(cert_path: Path) -> tuple[bool, int, int, float, str]:
    """Invoke ../03-checker/mcheck.py verify <cert_path> and parse its output."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(MCHECK_PATH), "verify", str(cert_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - t0
    stdout_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode == 0 and stdout_lines and stdout_lines[0] == "VALID":
        parsed: dict[str, str] = {}
        for line in stdout_lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                parsed[k.strip()] = v.strip()
        entries = int(parsed.get("entries", "0"))
        max_rank = int(parsed.get("max_rank", "0"))
        sec = float(parsed.get("seconds", str(elapsed)))
        return True, entries, max_rank, sec, "VALID"
    err_detail = "; ".join(stdout_lines) if stdout_lines else proc.stderr.strip()
    return False, 0, 0, elapsed, err_detail or f"mcheck exited with {proc.returncode}"


def _resolve_root_claim(family_claim: str, root_str: str) -> str:
    if family_claim in VALID_CLAIMS:
        return family_claim
    if family_claim in ("ATLEAST_DRAW stm", "ATLEAST_DRAW"):
        pos = rules.parse_position(root_str)
        return f"ATLEAST_DRAW {pos.stm}"
    if family_claim in ("WIN stm", "WIN"):
        pos = rules.parse_position(root_str)
        return f"WIN {pos.stm}"
    raise ValueError(f"unsupported family claim: {family_claim!r}")


# Worker state for ProcessPoolExecutor
_WORKER_MOVE_FN: Callable[[rules.Position], str] | None = None
_WORKER_POT_FN: Callable[[rules.Position], object] | None = None


def _init_worker(program_path_str: str, enforce_lookahead: bool) -> None:
    global _WORKER_MOVE_FN
    _WORKER_MOVE_FN, _ = load_strategy(
        Path(program_path_str), length_limit=None, enforce_lookahead=enforce_lookahead
    )


def _init_audit_worker(program_path_str: str, fn_name: str) -> None:
    global _WORKER_POT_FN
    ns, _, _, _ = load_strategy_namespace(
        Path(program_path_str), length_limit=None, enforce_lookahead=False
    )
    fn = ns.get(fn_name)
    if not callable(fn):
        raise ValueError(f"program {program_path_str} has no callable {fn_name}()")
    _WORKER_POT_FN = fn  # type: ignore[assignment]


def _score_one_root(args: tuple[str, str, int, str]) -> RootScoreResult:
    root_str, family_claim, max_entries, tmp_dir = args
    assert _WORKER_MOVE_FN is not None
    pos = rules.parse_position(root_str)
    board_size = f"{pos.width}x{pos.height}"
    claim = _resolve_root_claim(family_claim, root_str)

    exp = expand_strategy(_WORKER_MOVE_FN, claim, root_str, max_entries=max_entries)
    if not exp.ok:
        return RootScoreResult(
            root=root_str,
            board_size=board_size,
            claim=claim,
            ok=False,
            entries=0,
            max_rank=0,
            expand_seconds=exp.seconds,
            verify_seconds=0.0,
            failure_kind=exp.failure_kind,
            failure_pos=exp.failure_pos,
            failure_reason=exp.failure_reason,
        )

    fd, tmp_name = tempfile.mkstemp(prefix="cert_", suffix=".cert", dir=tmp_dir)
    os.close(fd)
    cert_path = Path(tmp_name)
    try:
        write_certificate(exp, cert_path)
        valid, m_entries, m_max_rank, verify_sec, detail = verify_with_mcheck(cert_path)
        if not valid:
            return RootScoreResult(
                root=root_str,
                board_size=board_size,
                claim=claim,
                ok=False,
                entries=0,
                max_rank=0,
                expand_seconds=exp.seconds,
                verify_seconds=verify_sec,
                failure_kind="checker_rejected",
                failure_pos=root_str,
                failure_reason=detail,
            )
        return RootScoreResult(
            root=root_str,
            board_size=board_size,
            claim=claim,
            ok=True,
            entries=m_entries,
            max_rank=m_max_rank,
            expand_seconds=exp.seconds,
            verify_seconds=verify_sec,
        )
    finally:
        try:
            cert_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_family(name: str, families_dir: Path | None = None) -> dict[str, object]:
    fdir = families_dir if families_dir is not None else BASE_DIR / "families"
    path = fdir / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"family file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("claim", "length_limit", "roots"):
        if key not in data:
            raise ValueError(f"family {path} missing required field {key!r}")
    return data


def score_program(
    program_path: Path,
    family_name: str,
    *,
    families_dir: Path | None = None,
    scores_path: Path | None = None,
    max_entries_override: int | None = None,
    jobs: int = 4,
    record: bool = True,
    enforce_lookahead: bool = True,
) -> dict[str, object]:
    """Validate, expand, and mcheck-verify `program_path` on all roots in `family_name`."""
    family = load_family(family_name, families_dir=families_dir)
    family_claim = str(family["claim"])
    length_limit = int(family["length_limit"])  # type: ignore[arg-type]
    max_entries = (
        max_entries_override
        if max_entries_override is not None
        else int(family.get("max_entries", 20000))  # type: ignore[arg-type]
    )
    roots: list[str] = list(family["roots"])  # type: ignore[arg-type]

    _, move_fn, length, nodes = load_strategy_namespace(
        program_path, length_limit=length_limit, enforce_lookahead=enforce_lookahead
    )

    workers = max(1, min(4, jobs, len(roots) if roots else 1))
    results: list[RootScoreResult] = []
    with tempfile.TemporaryDirectory(prefix="harness_certs_") as tmp_dir:
        tasks = [(r, family_claim, max_entries, tmp_dir) for r in roots]
        if workers == 1:
            global _WORKER_MOVE_FN
            _WORKER_MOVE_FN = move_fn
            for task in tasks:
                results.append(_score_one_root(task))
        else:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_worker,
                initargs=(str(program_path.resolve()), enforce_lookahead),
            ) as pool:
                for res in pool.map(_score_one_root, tasks):
                    results.append(res)

    total = len(results)
    covered = sum(1 for r in results if r.ok)
    coverage = (covered / total) if total else 0.0
    total_entries = sum(r.entries for r in results if r.ok)
    max_rank = max((r.max_rank for r in results if r.ok), default=0)
    compression = (total_entries / length) if length > 0 else 0.0
    entries_per_node = (total_entries / nodes) if nodes > 0 else 0.0
    expand_sec = sum(r.expand_seconds for r in results)
    verify_sec = sum(r.verify_seconds for r in results)
    failures = [r for r in results if not r.ok]

    by_board: dict[str, dict[str, object]] = {}
    for r in results:
        b = by_board.setdefault(
            r.board_size,
            {
                "covered": 0,
                "total": 0,
                "entries": 0,
                "max_rank": 0,
                "expand_seconds": 0.0,
                "verify_seconds": 0.0,
            },
        )
        b["total"] = int(b["total"]) + 1  # type: ignore[arg-type]
        b["expand_seconds"] = float(b["expand_seconds"]) + r.expand_seconds  # type: ignore[arg-type]
        b["verify_seconds"] = float(b["verify_seconds"]) + r.verify_seconds  # type: ignore[arg-type]
        if r.ok:
            b["covered"] = int(b["covered"]) + 1  # type: ignore[arg-type]
            b["entries"] = int(b["entries"]) + r.entries  # type: ignore[arg-type]
            b["max_rank"] = max(int(b["max_rank"]), r.max_rank)  # type: ignore[arg-type]

    summary: dict[str, object] = {
        "family": family_name,
        "program": str(program_path),
        "length": length,
        "nodes": nodes,
        "length_limit": length_limit,
        "covered": covered,
        "total": total,
        "coverage": coverage,
        "entries": total_entries,
        "max_rank": max_rank,
        "compression": compression,
        "entries_per_node": entries_per_node,
        "expand_seconds": expand_sec,
        "verify_seconds": verify_sec,
        "by_board": by_board,
        "failures": failures,
    }

    if record:
        out_tsv = scores_path if scores_path is not None else BASE_DIR / "results" / "scores.tsv"
        out_tsv.parent.mkdir(parents=True, exist_ok=True)
        write_header = not out_tsv.exists() or out_tsv.stat().st_size == 0
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            prog_label = str(program_path.resolve().relative_to(BASE_DIR))
        except ValueError:
            prog_label = str(program_path)
        if not enforce_lookahead:
            prog_label = f"{prog_label}[legacy]"
        row = "\t".join(
            [
                ts,
                family_name,
                prog_label,
                str(nodes),
                str(length),
                str(covered),
                str(total),
                f"{coverage:.4f}",
                str(total_entries),
                str(max_rank),
                f"{compression:.2f}",
                f"{expand_sec:.3f}",
                f"{verify_sec:.3f}",
            ]
        )
        with out_tsv.open("a", encoding="utf-8") as fh:
            if write_header:
                fh.write(
                    "timestamp\tfamily\tprogram\tnodes\tlength\tcovered\ttotal\tcoverage\t"
                    "entries\tmax_rank\tcompression\texpand_sec\tverify_sec\n"
                )
            fh.write(row + "\n")

    return summary


# ---------------------------------------------------------------------------
# Whole-class enumeration & union certificate expansion (Step 1: expand-all)
# ---------------------------------------------------------------------------


def parse_board_size(text: str) -> tuple[int, int]:
    parts = text.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"invalid board size {text!r}, expected WxH")
    w, h = int(parts[0]), int(parts[1])
    if not (3 <= w <= 8 and 3 <= h <= 8):
        raise ValueError(f"board dimensions must be in 3..8, got {w}x{h}")
    return w, h


def enumerate_valid_positions(material: str, width: int, height: int) -> list[str]:
    """Enumerate every canonical valid White-to-move position of `material` on `width x height`.

    Uses `castling="-"` and `ep="-"` (matching `generate_families.py`).
    Validates opponent king safety via `rules.is_square_attacked`.
    """
    mat = material.upper()
    if mat not in MATERIAL_SPECS:
        raise ValueError(
            f"unsupported material {material!r}; supported: {', '.join(sorted(MATERIAL_SPECS))}"
        )
    pieces = MATERIAL_SPECS[mat]
    n_sq = width * height
    fens: list[str] = []

    if len(pieces) == 2:
        # KK
        for ki in range(n_sq):
            kf, kr = ki % width, ki // width
            for bi in range(n_sq):
                if bi == ki:
                    continue
                bf, br = bi % width, bi // width
                if max(abs(kf - bf), abs(kr - br)) <= 1:
                    continue
                board = ["."] * n_sq
                board[ki] = "K"
                board[bi] = "k"
                pos = rules.Position(width, height, tuple(board), "w", "", None)
                fens.append(pos.to_fen())
        return fens

    # 3-piece: ("K", piece, "k")
    mid_piece = pieces[1]
    for ki in range(n_sq):
        kf, kr = ki % width, ki // width
        for bi in range(n_sq):
            if bi == ki:
                continue
            bf, br = bi % width, bi // width
            if max(abs(kf - bf), abs(kr - br)) <= 1:
                continue
            for pi in range(n_sq):
                if pi == ki or pi == bi:
                    continue
                board = ["."] * n_sq
                board[ki] = "K"
                board[pi] = mid_piece
                board[bi] = "k"
                bt = tuple(board)
                # Side not to move ('k') must not be in check.
                if rules.is_square_attacked(bt, width, height, bf, br, "w"):
                    continue
                pos = rules.Position(width, height, bt, "w", "", None)
                fens.append(pos.to_fen())
    return fens


def _eval_position_batch(
    fens: list[str],
) -> list[tuple[str, str | None, list[str] | None, str | None, str | None]]:
    """Worker function: evaluate move_fn on a batch of White-to-move positions.

    Returns tuples of (fen, move_str, children_fens, fail_kind, fail_reason).
    If fail_kind is None and children_fens == [], the position is immediate mate-in-1.
    """
    assert _WORKER_MOVE_FN is not None
    out: list[tuple[str, str | None, list[str] | None, str | None, str | None]] = []
    for fen in fens:
        pos = rules.parse_position(fen)
        transitions = rules.legal_transitions(pos)
        if not transitions:
            if rules.in_check(pos):
                out.append((fen, None, None, "checkmated", "prover is checkmated"))
            else:
                out.append((fen, None, None, "stalemate", "prover has no legal moves"))
            continue
        trans_dict = dict(transitions)
        try:
            move_str = _WORKER_MOVE_FN(pos)
        except LookaheadLimitError as exc:
            out.append((fen, None, None, "lookahead_limit", str(exc)))
            continue
        except Exception as exc:
            out.append((fen, None, None, "program_error", f"{type(exc).__name__}: {exc}"))
            continue
        if not isinstance(move_str, str) or not move_str:
            out.append((fen, None, None, "missing_move", f"invalid/missing move: {move_str!r}"))
            continue
        q_pos = trans_dict.get(move_str)
        if q_pos is None:
            out.append((fen, None, None, "illegal_move", f"illegal move {move_str!r}"))
            continue
        replies = rules.legal_transitions(q_pos)
        if not replies:
            if not rules.in_check(q_pos):
                out.append(
                    (fen, move_str, None, "stalemate", f"move {move_str} leads to opponent stalemate")
                )
            else:
                out.append((fen, move_str, [], None, None))
            continue
        children = sorted({rpos.to_fen() for _, rpos in replies})
        out.append((fen, move_str, children, None, None))
    return out


def solve_union_graph(
    valid_fens: list[str],
    eval_rows: list[tuple[str, str | None, list[str] | None, str | None, str | None]],
) -> tuple[dict[str, tuple[str, int]], list[str], dict[str, tuple[str, str]]]:
    """Run reverse topological peeling (Kahn's algorithm) from mate-in-1 nodes.

    Returns:
      entries: dict fen -> (move_str, rank) for every provably winning node in the closed union
      uncovered: list of valid_fens not in `entries`
      direct_failures: dict fen -> (fail_kind, fail_reason) for nodes that directly failed
    """
    valid_set = set(valid_fens)
    chosen_move: dict[str, str] = {}
    remaining: dict[str, int] = {}
    parents: dict[str, list[str]] = {}
    direct_failures: dict[str, tuple[str, str]] = {}
    queue: deque[str] = deque()
    ranks: dict[str, int] = {}
    max_child_rank: dict[str, int] = {}

    for fen, move_str, children, fail_kind, fail_reason in eval_rows:
        if fail_kind is not None or children is None or move_str is None:
            direct_failures[fen] = (fail_kind or "unknown", fail_reason or "")
            continue
        chosen_move[fen] = move_str
        if not children:
            ranks[fen] = 1
            queue.append(fen)
            continue
        # If any reply leaves the material class (e.g. Black captures Q/R -> bare Kk),
        # this node cannot close inside a WIN w certificate.
        out_of_class = [c for c in children if c not in valid_set]
        if out_of_class:
            direct_failures[fen] = (
                "piece_captured",
                f"move {move_str} allows material loss to {out_of_class[0]}",
            )
            continue
        remaining[fen] = len(children)
        max_child_rank[fen] = 0
        for c in children:
            parents.setdefault(c, []).append(fen)

    while queue:
        c = queue.popleft()
        cr = ranks[c]
        for u in parents.get(c, ()):
            if cr > max_child_rank[u]:
                max_child_rank[u] = cr
            remaining[u] -= 1
            if remaining[u] == 0:
                ranks[u] = 1 + max_child_rank[u]
                queue.append(u)

    entries = {fen: (chosen_move[fen], ranks[fen]) for fen in valid_fens if fen in ranks}
    uncovered = [fen for fen in valid_fens if fen not in ranks]
    return entries, uncovered, direct_failures


def expand_all_class(
    program_path: Path,
    material: str,
    width: int,
    height: int,
    out_path: Path | None,
    *,
    jobs: int = 4,
    enforce_lookahead: bool = True,
    shard: tuple[int, int] | None = None,
    shard_out: Path | None = None,
    merge_shards: list[Path] | None = None,
    verify: bool = True,
) -> dict[str, object]:
    """Expand a strategy program across EVERY valid White-to-move position of (material, WxH)."""
    t0 = time.perf_counter()
    _, move_fn, length_bytes, length_nodes = load_strategy_namespace(
        program_path, length_limit=None, enforce_lookahead=enforce_lookahead
    )
    valid_fens = enumerate_valid_positions(material, width, height)
    total_valid = len(valid_fens)

    if merge_shards:
        eval_rows: list[tuple[str, str | None, list[str] | None, str | None, str | None]] = []
        seen_fens: set[str] = set()
        for sp in merge_shards:
            data = json.loads(sp.read_text(encoding="utf-8"))
            for row in data["rows"]:
                fen = row[0]
                if fen not in seen_fens:
                    seen_fens.add(fen)
                    eval_rows.append((row[0], row[1], row[2], row[3], row[4]))
        if len(seen_fens) != total_valid:
            raise ValueError(
                f"merged shards cover {len(seen_fens)} positions, expected {total_valid}"
            )
    else:
        if shard is not None:
            s_idx, s_tot = shard
            if not (0 <= s_idx < s_tot):
                raise ValueError(f"invalid shard {s_idx}/{s_tot}")
            target_fens = [f for i, f in enumerate(valid_fens) if i % s_tot == s_idx]
        else:
            target_fens = valid_fens

        workers = max(1, min(4, jobs))
        chunk_size = max(1, min(500, (len(target_fens) + workers * 8 - 1) // (workers * 8)))
        batches = [
            target_fens[i : i + chunk_size] for i in range(0, len(target_fens), chunk_size)
        ]
        eval_rows = []
        if workers == 1:
            global _WORKER_MOVE_FN
            _WORKER_MOVE_FN = move_fn
            for batch in batches:
                eval_rows.extend(_eval_position_batch(batch))
        else:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_worker,
                initargs=(str(program_path.resolve()), enforce_lookahead),
            ) as pool:
                for res_batch in pool.map(_eval_position_batch, batches):
                    eval_rows.extend(res_batch)

        if shard is not None:
            elapsed = time.perf_counter() - t0
            if shard_out is None:
                raise ValueError("--shard requires --shard-out <path.json>")
            shard_out.parent.mkdir(parents=True, exist_ok=True)
            shard_out.write_text(
                json.dumps(
                    {
                        "material": material.upper(),
                        "board": f"{width}x{height}",
                        "shard": [shard[0], shard[1]],
                        "program": str(program_path),
                        "seconds": elapsed,
                        "rows": eval_rows,
                    }
                ),
                encoding="utf-8",
            )
            return {
                "mode": "shard",
                "shard": f"{shard[0]}/{shard[1]}",
                "evaluated": len(eval_rows),
                "total_valid": total_valid,
                "seconds": elapsed,
                "shard_out": str(shard_out),
            }

    entries, uncovered, direct_failures = solve_union_graph(valid_fens, eval_rows)
    expand_sec = time.perf_counter() - t0

    # Classify up to 5 uncovered positions with concrete failure details
    uncovered_details: list[tuple[str, str, str]] = []
    for fen in uncovered[:5]:
        if fen in direct_failures:
            fk, fr = direct_failures[fen]
            uncovered_details.append((fen, fk, fr))
        else:
            exp_single = expand_strategy(move_fn, "WIN w", fen, max_entries=5000)
            uncovered_details.append(
                (
                    fen,
                    exp_single.failure_kind or "unclosed",
                    exp_single.failure_reason or "reaches cycle or failing branch",
                )
            )

    max_rank = max((r for _, r in entries.values()), default=0)
    verify_ok: bool | None = None
    verify_sec = 0.0
    verify_detail = "skipped"
    verified_entries = 0
    verified_max_rank = 0

    if out_path is not None and entries:
        # Pick a covered position with maximum rank as #root (all entries are checked by mcheck).
        root_fen = max(entries.keys(), key=lambda f: (entries[f][1], f))
        order = tuple(sorted(entries.keys(), key=lambda f: (entries[f][1], f)))
        exp_union = ExpandResult(
            ok=True,
            claim="WIN w",
            root=root_fen,
            entries=entries,
            entry_order=order,
            max_rank=max_rank,
            seconds=expand_sec,
        )
        write_certificate(exp_union, out_path)
        if verify:
            verify_ok, verified_entries, verified_max_rank, verify_sec, verify_detail = (
                verify_with_mcheck(out_path)
            )

    return {
        "mode": "full",
        "material": material.upper(),
        "board": f"{width}x{height}",
        "program": str(program_path),
        "nodes": length_nodes,
        "bytes": length_bytes,
        "valid_positions": total_valid,
        "entries": len(entries),
        "uncovered_count": len(uncovered),
        "uncovered_sample": uncovered_details,
        "complete": len(entries) == total_valid and (verify_ok is not False),
        "max_rank": max_rank,
        "expand_seconds": expand_sec,
        "verify_ok": verify_ok,
        "verified_entries": verified_entries,
        "verified_max_rank": verified_max_rank,
        "verify_seconds": verify_sec,
        "verify_detail": verify_detail,
        "out": str(out_path) if out_path is not None else None,
    }


# ---------------------------------------------------------------------------
# Potential ranking audit (Step 2: audit-rank)
# ---------------------------------------------------------------------------


def _audit_entry_batch(
    lines: list[str],
) -> tuple[int, int, int, int, int, list[tuple[object, ...]], list[tuple[object, ...]]]:
    assert _WORKER_POT_FN is not None
    entries_n = 0
    mate1_n = 0
    dec_n = 0
    eq_n = 0
    inc_n = 0
    eq_samples: list[tuple[object, ...]] = []
    inc_samples: list[tuple[object, ...]] = []

    for line in lines:
        p_str, m_str, _ = line.split("\t")
        entries_n += 1
        pos = rules.parse_position(p_str)
        pot_p = _WORKER_POT_FN(pos)
        q_pos = rules.apply_move(pos, m_str)
        replies = rules.legal_transitions(q_pos)
        if not replies:
            mate1_n += 1
            continue
        for r_move, r_pos in replies:
            pot_r = _WORKER_POT_FN(r_pos)
            if pot_r < pot_p:  # type: ignore[operator]
                dec_n += 1
            elif pot_r == pot_p:
                eq_n += 1
                if len(eq_samples) < 5:
                    eq_samples.append((p_str, m_str, r_move, r_pos.to_fen(), repr(pot_p), repr(pot_r)))
            else:
                inc_n += 1
                if len(inc_samples) < 5:
                    inc_samples.append((p_str, m_str, r_move, r_pos.to_fen(), repr(pot_p), repr(pot_r)))

    return entries_n, mate1_n, dec_n, eq_n, inc_n, eq_samples, inc_samples


def audit_rank(
    program_path: Path,
    cert_path: Path,
    *,
    fn_name: str = "_pot",
    jobs: int = 4,
) -> dict[str, object]:
    """Compare `fn_name(p)` with `fn_name(p.m.r)` for every entry (p, m) and reply r in `cert_path`."""
    t0 = time.perf_counter()
    ns, _, length_bytes, length_nodes = load_strategy_namespace(
        program_path, length_limit=None, enforce_lookahead=False
    )
    pot_fn = ns.get(fn_name)
    if not callable(pot_fn):
        raise ValueError(f"program {program_path} has no callable {fn_name}()")

    raw_lines = cert_path.read_text(encoding="utf-8").splitlines()
    if len(raw_lines) < 3 or raw_lines[0] != "#cert v1":
        raise ValueError(f"invalid certificate header in {cert_path}")
    body_lines = [ln for ln in raw_lines[3:] if ln]

    workers = max(1, min(4, jobs))
    chunk_size = max(1, min(1000, (len(body_lines) + workers * 4 - 1) // (workers * 4)))
    batches = [body_lines[i : i + chunk_size] for i in range(0, len(body_lines), chunk_size)]

    entries_n = mate1_n = dec_n = eq_n = inc_n = 0
    eq_samples: list[tuple[object, ...]] = []
    inc_samples: list[tuple[object, ...]] = []

    if workers == 1 or len(batches) <= 1:
        global _WORKER_POT_FN
        _WORKER_POT_FN = pot_fn  # type: ignore[assignment]
        for batch in batches:
            e, m1, d, eq, inc, eqs, incs = _audit_entry_batch(batch)
            entries_n += e
            mate1_n += m1
            dec_n += d
            eq_n += eq
            inc_n += inc
            for s in eqs:
                if len(eq_samples) < 5:
                    eq_samples.append(s)
            for s in incs:
                if len(inc_samples) < 5:
                    inc_samples.append(s)
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_audit_worker,
            initargs=(str(program_path.resolve()), fn_name),
        ) as pool:
            for e, m1, d, eq, inc, eqs, incs in pool.map(_audit_entry_batch, batches):
                entries_n += e
                mate1_n += m1
                dec_n += d
                eq_n += eq
                inc_n += inc
                for s in eqs:
                    if len(eq_samples) < 5:
                        eq_samples.append(s)
                for s in incs:
                    if len(inc_samples) < 5:
                        inc_samples.append(s)

    total_steps = dec_n + eq_n + inc_n
    return {
        "program": str(program_path),
        "cert": str(cert_path),
        "fn": fn_name,
        "nodes": length_nodes,
        "bytes": length_bytes,
        "entries": entries_n,
        "mate1_entries": mate1_n,
        "total_steps": total_steps,
        "decrease": dec_n,
        "equal": eq_n,
        "increase": inc_n,
        "strict_ranking": (eq_n == 0 and inc_n == 0),
        "equal_examples": eq_samples,
        "increase_examples": inc_samples,
        "seconds": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------
# LIA fragment linter (Round 3 Step 1: lint-lia)
# ---------------------------------------------------------------------------

LIA_ALLOWED_BUILTINS = frozenset({"min", "max", "abs", "int"})


def _is_int_const_expr(node: ast.AST) -> bool:
    """Return True if `node` is a constant integer expression (no variables)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _is_int_const_expr(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)):
        return _is_int_const_expr(node.left) and _is_int_const_expr(node.right)
    return False


def _eval_int_const(node: ast.AST) -> int | None:
    if not _is_int_const_expr(node):
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp):
        v = _eval_int_const(node.operand)
        if v is None:
            return None
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp):
        lv = _eval_int_const(node.left)
        rv = _eval_int_const(node.right)
        if lv is None or rv is None:
            return None
        if isinstance(node.op, ast.Add):
            return lv + rv
        if isinstance(node.op, ast.Sub):
            return lv - rv
        if isinstance(node.op, ast.Mult):
            return lv * rv
        if rv == 0:
            return None
        if isinstance(node.op, ast.FloorDiv):
            return lv // rv
        if isinstance(node.op, ast.Mod):
            return lv % rv
    return None


def _is_board_index_call(node: ast.AST) -> bool:
    """Match `<pos>.board.index(<single-piece-str>)` for coordinate extraction."""
    if not isinstance(node, ast.Call):
        return False
    if not (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "index"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "board"
        and isinstance(node.func.value.value, ast.Name)
    ):
        return False
    if len(node.args) != 1 or node.keywords:
        return False
    arg = node.args[0]
    return isinstance(arg, ast.Constant) and isinstance(arg.value, str) and len(arg.value) == 1


def _is_board_width_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "width"
        and isinstance(node.value, ast.Name)
    )


def _is_pos_board_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "board"
        and isinstance(node.value, ast.Name)
    )


def _is_square_name_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "square_name"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "rules"
        and len(node.args) == 2
        and not node.keywords
    )


def lint_lia(
    program_path: Path,
    *,
    fn_name: str = "_pot",
    allow_move_formatting: bool = False,
) -> dict[str, object]:
    """Check that `fn_name` (and any local helpers it calls) stays inside Linear Integer Arithmetic.

    Allowed: +, -, comparisons, min, max, abs, integer constants, constant-scaled multiplication,
    floor-div/mod by a non-zero integer constant, if/else, tuples, and piece-coordinate extraction
    from `pos` (`pos.width`, `pos.height`, `pos.board.index(c)` with `i % pos.width`, `i // pos.width`,
    and `<piece> in pos.board`).
    Forbidden: variable*variable, loops, comprehensions/generators, division/mod by variables,
    float division, powers, bitwise ops, lookup tables, or rules move-generation calls.
    """
    source = program_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(program_path))

    func_defs: dict[str, ast.FunctionDef] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            func_defs[stmt.name] = stmt

    if fn_name not in func_defs:
        return {
            "ok": False,
            "program": str(program_path),
            "fn": fn_name,
            "checked_functions": [],
            "violations": [f"function {fn_name!r} not found at module top level"],
        }

    violations: list[str] = []
    checked: list[str] = []
    visited: set[str] = set()

    def add_err(fn: str, node: ast.AST, msg: str) -> None:
        ln = getattr(node, "lineno", "?")
        violations.append(f"{fn}:{ln}: {msg}")

    def check_fn(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        checked.append(name)
        fn = func_defs[name]

        # Track variables bound directly to `<pos>.board.index(...)` (for 1D -> (f, r) unpack only).
        board_idx_vars: set[str] = set()
        # Allow string-typed piece param in a tiny coordinate helper like `def _f(p, c): i = p.board.index(c)`.
        param_names = {a.arg for a in fn.args.args}

        def is_coord_index_call(node: ast.AST) -> bool:
            if _is_board_index_call(node):
                return True
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "index"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "board"
                and isinstance(node.func.value.value, ast.Name)
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in param_names
            ):
                return True
            return False

        def check_expr(node: ast.AST) -> None:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, bool)):
                    return
                if isinstance(node.value, str) and len(node.value) == 1:
                    return
                add_err(name, node, f"non-integer constant {node.value!r} not allowed in LIA")
                return
            if isinstance(node, ast.Name):
                return
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.attr in ("width", "height", "board"):
                    return
                add_err(name, node, f"attribute access .{node.attr} not allowed in LIA")
                return
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
                    check_expr(node.operand)
                    return
                add_err(name, node, f"unary operator {type(node.op).__name__} not allowed in LIA")
                return
            if isinstance(node, ast.BoolOp):
                for v in node.values:
                    check_expr(v)
                return
            if isinstance(node, ast.Compare):
                check_expr(node.left)
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                        check_expr(comp)
                    elif isinstance(op, (ast.In, ast.NotIn)):
                        if not (
                            isinstance(node.left, ast.Constant)
                            and isinstance(node.left.value, str)
                            and _is_pos_board_attr(comp)
                        ):
                            add_err(name, node, "'in'/'not in' only allowed for piece presence in pos.board")
                    else:
                        add_err(name, node, f"comparison {type(op).__name__} not allowed in LIA")
                return
            if isinstance(node, ast.IfExp):
                check_expr(node.test)
                check_expr(node.body)
                check_expr(node.orelse)
                return
            if isinstance(node, ast.Tuple):
                for elt in node.elts:
                    check_expr(elt)
                return
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, (ast.Add, ast.Sub)):
                    check_expr(node.left)
                    check_expr(node.right)
                    return
                if isinstance(node.op, ast.Mult):
                    if _is_int_const_expr(node.left) or _is_int_const_expr(node.right):
                        check_expr(node.left)
                        check_expr(node.right)
                        return
                    add_err(
                        name,
                        node,
                        f"non-linear multiplication of two variables: {ast.unparse(node)}",
                    )
                    return
                if isinstance(node.op, (ast.FloorDiv, ast.Mod)):
                    # Allow constant non-zero divisor (Presburger/LIA definable)
                    rv = _eval_int_const(node.right)
                    if rv is not None and rv != 0:
                        check_expr(node.left)
                        return
                    # Allow coordinate unpacking `i % p.width` / `i // p.width`
                    if (
                        isinstance(node.left, ast.Name)
                        and node.left.id in board_idx_vars
                        and _is_board_width_attr(node.right)
                    ):
                        return
                    add_err(
                        name,
                        node,
                        f"division/modulo by non-constant expression: {ast.unparse(node)}",
                    )
                    return
                add_err(name, node, f"operator {type(node.op).__name__} not allowed in LIA ({ast.unparse(node)})")
                return
            if isinstance(node, ast.Call):
                if is_coord_index_call(node):
                    return
                if allow_move_formatting and _is_square_name_call(node):
                    for a in node.args:
                        check_expr(a)
                    return
                if isinstance(node.func, ast.Name):
                    cname = node.func.id
                    if cname in LIA_ALLOWED_BUILTINS:
                        if node.keywords:
                            add_err(name, node, f"keyword args not allowed in {cname}()")
                        for a in node.args:
                            check_expr(a)
                        return
                    if cname in func_defs:
                        if node.keywords:
                            add_err(name, node, f"keyword args not allowed in {cname}()")
                        for a in node.args:
                            check_expr(a)
                        check_fn(cname)
                        return
                add_err(name, node, f"disallowed call in LIA: {ast.unparse(node)}")
                return
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                add_err(name, node, f"comprehension/generator not allowed in LIA: {ast.unparse(node)}")
                return
            add_err(name, node, f"disallowed expression {type(node).__name__} in LIA: {ast.unparse(node)}")

        def check_target(tgt: ast.AST) -> None:
            if isinstance(tgt, ast.Name):
                return
            if isinstance(tgt, ast.Tuple):
                for elt in tgt.elts:
                    check_target(elt)
                return
            add_err(name, tgt, f"disallowed assignment target {type(tgt).__name__} in LIA")

        def check_stmts(stmts: list[ast.stmt]) -> None:
            for idx, stmt in enumerate(stmts):
                if (
                    idx == 0
                    and isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    continue  # docstring
                if isinstance(stmt, ast.Assign):
                    if len(stmt.targets) != 1:
                        add_err(name, stmt, "chained assignment not allowed in LIA")
                        continue
                    tgt = stmt.targets[0]
                    check_target(tgt)
                    if isinstance(tgt, ast.Name) and is_coord_index_call(stmt.value):
                        board_idx_vars.add(tgt.id)
                        continue
                    check_expr(stmt.value)
                    continue
                if isinstance(stmt, ast.AugAssign):
                    if not isinstance(stmt.op, (ast.Add, ast.Sub)):
                        add_err(name, stmt, f"augmented assign {type(stmt.op).__name__} not allowed in LIA")
                    check_target(stmt.target)
                    check_expr(stmt.value)
                    continue
                if isinstance(stmt, ast.If):
                    check_expr(stmt.test)
                    check_stmts(stmt.body)
                    check_stmts(stmt.orelse)
                    continue
                if isinstance(stmt, ast.Return):
                    if stmt.value is not None:
                        check_expr(stmt.value)
                    continue
                if isinstance(stmt, ast.Pass):
                    continue
                if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                    add_err(name, stmt, f"loop ({type(stmt).__name__}) not allowed in LIA")
                    continue
                add_err(name, stmt, f"disallowed statement {type(stmt).__name__} in LIA")

        check_stmts(fn.body)

    check_fn(fn_name)
    return {
        "ok": len(violations) == 0,
        "program": str(program_path),
        "fn": fn_name,
        "checked_functions": checked,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# Witness-move audit (Round 3 Step 2: audit-hint)
# ---------------------------------------------------------------------------

_WORKER_HINT_FN: Callable[[rules.Position], str] | None = None


def _init_hint_worker(program_path_str: str, pot_fn_name: str, hint_fn_name: str) -> None:
    global _WORKER_POT_FN, _WORKER_HINT_FN
    ns, _, _, _ = load_strategy_namespace(
        Path(program_path_str), length_limit=None, enforce_lookahead=False
    )
    pfn = ns.get(pot_fn_name)
    hfn = ns.get(hint_fn_name)
    if not callable(pfn):
        raise ValueError(f"program {program_path_str} has no callable {pot_fn_name}()")
    if not callable(hfn):
        raise ValueError(f"program {program_path_str} has no callable {hint_fn_name}()")
    _WORKER_POT_FN = pfn  # type: ignore[assignment]
    _WORKER_HINT_FN = hfn  # type: ignore[assignment]


def _audit_hint_batch(
    fens: list[str],
) -> tuple[int, int, int, int, int, int, int, int, list[tuple[str, ...]]]:
    assert _WORKER_POT_FN is not None and _WORKER_HINT_FN is not None
    total = 0
    mate1 = 0
    illegal = 0
    stalemate = 0
    dec_n = 0
    eq_n = 0
    inc_n = 0
    cap_n = 0
    samples: list[tuple[str, ...]] = []

    for fen in fens:
        total += 1
        pos = rules.parse_position(fen)
        trans = rules.legal_transitions(pos)
        trans_dict = dict(trans)
        try:
            m_str = _WORKER_HINT_FN(pos)
        except Exception as exc:
            illegal += 1
            if len(samples) < 10:
                samples.append(("error", fen, "", "", f"{type(exc).__name__}: {exc}"))
            continue
        if not isinstance(m_str, str) or m_str not in trans_dict:
            illegal += 1
            if len(samples) < 10:
                samples.append(("illegal", fen, repr(m_str), "", "not a legal move"))
            continue
        q_pos = trans_dict[m_str]
        replies = rules.legal_transitions(q_pos)
        if not replies:
            if rules.in_check(q_pos):
                mate1 += 1
            else:
                stalemate += 1
                if len(samples) < 10:
                    samples.append(("stalemate", fen, m_str, "", "leads to stalemate"))
            continue

        pot_p = _WORKER_POT_FN(pos)
        orig_pieces = sum(1 for c in pos.board if c != ".")
        for r_move, r_pos in replies:
            if sum(1 for c in r_pos.board if c != ".") < orig_pieces:
                cap_n += 1
            pot_r = _WORKER_POT_FN(r_pos)
            if pot_r < pot_p:  # type: ignore[operator]
                dec_n += 1
            elif pot_r == pot_p:
                eq_n += 1
                if len(samples) < 10:
                    samples.append(
                        ("equal", fen, m_str, r_move, f"{r_pos.to_fen()} | {pot_p!r} == {pot_r!r}")
                    )
            else:
                inc_n += 1
                if len(samples) < 10:
                    samples.append(
                        ("increase", fen, m_str, r_move, f"{r_pos.to_fen()} | {pot_p!r} -> {pot_r!r}")
                    )
    return total, mate1, illegal, stalemate, dec_n, eq_n, inc_n, cap_n, samples


def audit_hint(
    program_path: Path,
    material: str,
    width: int,
    height: int,
    *,
    pot_fn_name: str = "_pot",
    hint_fn_name: str = "hint",
    jobs: int = 4,
) -> dict[str, object]:
    """Audit `hint(pos)` over every valid White-to-move position of (material, WxH)."""
    t0 = time.perf_counter()
    ns, _, length_bytes, length_nodes = load_strategy_namespace(
        program_path, length_limit=None, enforce_lookahead=False
    )
    pot_fn = ns.get(pot_fn_name)
    hint_fn = ns.get(hint_fn_name)
    if not callable(pot_fn):
        raise ValueError(f"program {program_path} has no callable {pot_fn_name}()")
    if not callable(hint_fn):
        raise ValueError(f"program {program_path} has no callable {hint_fn_name}()")

    valid_fens = enumerate_valid_positions(material, width, height)
    workers = max(1, min(4, jobs))
    chunk_size = max(1, min(500, (len(valid_fens) + workers * 4 - 1) // (workers * 4)))
    batches = [valid_fens[i : i + chunk_size] for i in range(0, len(valid_fens), chunk_size)]

    total = mate1 = illegal = stalemate = dec_n = eq_n = inc_n = cap_n = 0
    samples: list[tuple[str, ...]] = []

    if workers == 1 or len(batches) <= 1:
        global _WORKER_POT_FN, _WORKER_HINT_FN
        _WORKER_POT_FN = pot_fn  # type: ignore[assignment]
        _WORKER_HINT_FN = hint_fn  # type: ignore[assignment]
        for b in batches:
            t, m1, il, sm, d, eq, inc, cap, smp = _audit_hint_batch(b)
            total += t
            mate1 += m1
            illegal += il
            stalemate += sm
            dec_n += d
            eq_n += eq
            inc_n += inc
            cap_n += cap
            for s in smp:
                if len(samples) < 10:
                    samples.append(s)
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_hint_worker,
            initargs=(str(program_path.resolve()), pot_fn_name, hint_fn_name),
        ) as pool:
            for t, m1, il, sm, d, eq, inc, cap, smp in pool.map(_audit_hint_batch, batches):
                total += t
                mate1 += m1
                illegal += il
                stalemate += sm
                dec_n += d
                eq_n += eq
                inc_n += inc
                cap_n += cap
                for s in smp:
                    if len(samples) < 10:
                        samples.append(s)

    violations = illegal + stalemate + eq_n + inc_n
    return {
        "program": str(program_path),
        "material": material.upper(),
        "board": f"{width}x{height}",
        "nodes": length_nodes,
        "bytes": length_bytes,
        "valid_positions": total,
        "mate1": mate1,
        "illegal": illegal,
        "stalemate": stalemate,
        "piece_captured": cap_n,
        "total_steps": dec_n + eq_n + inc_n,
        "decrease": dec_n,
        "equal": eq_n,
        "increase": inc_n,
        "violations": violations,
        "ok": violations == 0,
        "samples": samples,
        "seconds": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def _cmd_expand(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    out_path = Path(args.out)
    enforce = not args.allow_legacy_lookahead
    try:
        _, move_fn, length, nodes = load_strategy_namespace(
            prog_path, length_limit=args.max_length, enforce_lookahead=enforce
        )
    except ProgramValidationError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2

    res = expand_strategy(move_fn, args.claim, args.root, max_entries=args.max_entries)
    if not res.ok:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        print("FAILED")
        print(f"kind: {res.failure_kind}")
        print(f"position: {res.failure_pos}")
        print(f"reason: {res.failure_reason}")
        print(f"seconds: {res.seconds:.4f}")
        return 1

    write_certificate(res, out_path)
    print("EXPANDED")
    print(f"claim: {res.claim}")
    print(f"root: {res.root}")
    print(f"entries: {len(res.entries)}")
    print(f"max_rank: {res.max_rank}")
    print(f"program_nodes: {nodes}")
    print(f"program_length: {length}")
    print(f"out: {out_path}")
    print(f"seconds: {res.seconds:.4f}")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    enforce = not args.allow_legacy_lookahead
    try:
        summary = score_program(
            prog_path,
            args.family,
            max_entries_override=args.max_entries,
            jobs=args.jobs,
            record=not args.no_record,
            enforce_lookahead=enforce,
        )
    except (ProgramValidationError, FileNotFoundError, ValueError) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2

    print(f"family: {summary['family']}")
    print(f"program: {summary['program']}" + (" [legacy lookahead]" if not enforce else ""))
    print(f"coverage: {summary['covered']}/{summary['total']} ({summary['coverage'] * 100:.2f}%)")
    print(
        f"length: {summary['nodes']} AST nodes, {summary['length']} bytes "
        f"(byte limit {summary['length_limit']})"
    )
    print(f"entries: {summary['entries']}")
    print(f"max_rank: {summary['max_rank']}")
    print(
        f"compression: {summary['entries_per_node']:.2f} entries/node, "
        f"{summary['compression']:.2f} entries/byte"
    )
    print(
        f"time: expand={summary['expand_seconds']:.2f}s (cpu-sum), "
        f"verify={summary['verify_seconds']:.2f}s (cpu-sum)"
    )

    by_board: dict[str, dict[str, object]] = summary["by_board"]  # type: ignore[assignment]
    if len(by_board) > 1:
        print("by_board:")
        for board in sorted(by_board.keys()):
            b = by_board[board]
            cov = int(b["covered"])  # type: ignore[arg-type]
            tot = int(b["total"])  # type: ignore[arg-type]
            ent = int(b["entries"])  # type: ignore[arg-type]
            mr = int(b["max_rank"])  # type: ignore[arg-type]
            es = float(b["expand_seconds"])  # type: ignore[arg-type]
            vs = float(b["verify_seconds"])  # type: ignore[arg-type]
            print(
                f"  {board}: {cov}/{tot} ({cov / tot * 100:.1f}%) "
                f"entries={ent} max_rank={mr} expand={es:.2f}s verify={vs:.2f}s"
            )

    failures: list[RootScoreResult] = summary["failures"]  # type: ignore[assignment]
    if failures:
        print(f"failures (showing up to 5 of {len(failures)}):")
        for f in failures[:5]:
            print(
                f"  root={f.root!r} | kind={f.failure_kind} | pos={f.failure_pos!r} | {f.failure_reason}"
            )
    return 0


def _cmd_expand_all(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    enforce = not args.allow_legacy_lookahead
    try:
        w, h = parse_board_size(args.board)
        shard_tuple = None
        if args.shard:
            a, b = args.shard.split("/")
            shard_tuple = (int(a), int(b))
        merge_paths = [Path(p) for p in args.merge_shards] if args.merge_shards else None
        out_path = Path(args.out) if args.out else None
        shard_out = Path(args.shard_out) if args.shard_out else None
        res = expand_all_class(
            prog_path,
            args.material,
            w,
            h,
            out_path,
            jobs=args.jobs,
            enforce_lookahead=enforce,
            shard=shard_tuple,
            shard_out=shard_out,
            merge_shards=merge_paths,
            verify=not args.no_verify,
        )
    except (ProgramValidationError, FileNotFoundError, ValueError) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2

    if res["mode"] == "shard":
        print(
            f"SHARD {res['shard']}: evaluated={res['evaluated']}/{res['total_valid']} "
            f"seconds={res['seconds']:.2f}s out={res['shard_out']}"
        )
        return 0

    print(f"material: {res['material']} board: {res['board']}")
    print(f"program: {res['program']} ({res['nodes']} AST nodes, {res['bytes']} bytes)")
    print(
        f"valid_positions: {res['valid_positions']} | entries: {res['entries']} "
        f"| uncovered: {res['uncovered_count']}"
    )
    print(f"complete: {res['complete']}")
    print(f"max_rank: {res['max_rank']}")
    print(f"expand_seconds: {res['expand_seconds']:.2f}s")
    if res["out"] is not None:
        print(f"out: {res['out']}")
        print(
            f"mcheck: {res['verify_detail']} (entries={res['verified_entries']}, "
            f"max_rank={res['verified_max_rank']}, seconds={res['verify_seconds']:.2f}s)"
        )
    uncovered_sample = res["uncovered_sample"]
    if uncovered_sample:
        print(f"uncovered (showing up to 5 of {res['uncovered_count']}):")
        for fen, fk, fr in uncovered_sample:  # type: ignore[union-attr]
            print(f"  {fen!r} | {fk} | {fr}")
    if res["verify_ok"] is False:
        return 1
    return 0


def _cmd_audit_rank(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    cert_path = Path(args.cert)
    try:
        res = audit_rank(prog_path, cert_path, fn_name=args.fn, jobs=args.jobs)
    except (ProgramValidationError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    tot = int(res["total_steps"])  # type: ignore[arg-type]
    dec = int(res["decrease"])  # type: ignore[arg-type]
    eq = int(res["equal"])  # type: ignore[arg-type]
    inc = int(res["increase"])  # type: ignore[arg-type]
    pct = (lambda n: (100.0 * n / tot) if tot else 0.0)
    print(f"program: {res['program']} ({res['nodes']} AST nodes, {res['bytes']} bytes) fn={res['fn']}")
    print(f"cert: {res['cert']} (entries={res['entries']}, mate1={res['mate1_entries']})")
    print(
        f"two_ply_steps: {tot} | decrease={dec} ({pct(dec):.2f}%) | "
        f"equal={eq} ({pct(eq):.2f}%) | increase={inc} ({pct(inc):.2f}%)"
    )
    print(f"strict_ranking: {res['strict_ranking']} | seconds: {res['seconds']:.2f}s")
    if res["equal_examples"]:
        print("equal examples (up to 5):")
        for p, m, r, rp, pp, pr in res["equal_examples"]:  # type: ignore[union-attr]
            print(f"  {p} --({m} {r})--> {rp} | pot {pp} == {pr}")
    if res["increase_examples"]:
        print("increase examples (up to 5):")
        for p, m, r, rp, pp, pr in res["increase_examples"]:  # type: ignore[union-attr]
            print(f"  {p} --({m} {r})--> {rp} | pot {pp} -> {pr}")
    return 0


def _cmd_lint_lia(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    try:
        allow_fmt = args.allow_move_formatting or (args.fn == "hint")
        res = lint_lia(prog_path, fn_name=args.fn, allow_move_formatting=allow_fmt)
    except (OSError, SyntaxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if res["ok"]:
        print(f"LIA_OK: {res['program']} fn={res['fn']} (checked: {', '.join(res['checked_functions'])})")  # type: ignore[arg-type]
        return 0
    print(f"LIA_REJECTED: {res['program']} fn={res['fn']}")
    for v in res["violations"]:  # type: ignore[union-attr]
        print(f"  - {v}")
    return 1


def _cmd_audit_hint(args: argparse.Namespace) -> int:
    prog_path = Path(args.program)
    try:
        w, h = parse_board_size(args.board)
        res = audit_hint(
            prog_path,
            args.material,
            w,
            h,
            pot_fn_name=args.pot_fn,
            hint_fn_name=args.hint_fn,
            jobs=args.jobs,
        )
    except (ProgramValidationError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"program: {res['program']} ({res['nodes']} AST nodes, {res['bytes']} bytes)")
    print(f"material: {res['material']} board: {res['board']} valid_positions: {res['valid_positions']}")
    print(
        f"mate1={res['mate1']} | illegal={res['illegal']} | stalemate={res['stalemate']} "
        f"| piece_captured={res['piece_captured']}"
    )
    print(
        f"two_ply_steps={res['total_steps']} | decrease={res['decrease']} "
        f"| equal={res['equal']} | increase={res['increase']}"
    )
    print(f"violations={res['violations']} | ok={res['ok']} | seconds={res['seconds']:.2f}s")
    samples = res["samples"]
    if samples:
        print(f"violation samples (up to 10):")
        for kind, fen, m, r, detail in samples:  # type: ignore[union-attr]
            print(f"  [{kind}] {fen} --({m} {r})--> {detail}")
    return 0 if res["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expand, score, union-prove, lint-LIA, and audit chess strategy programs."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("expand", help="Expand a strategy program into a certificate.")
    p_exp.add_argument("program", help="Path to strategy .py file")
    p_exp.add_argument("--claim", required=True, help="WIN w | WIN b | ATLEAST_DRAW w | ATLEAST_DRAW b")
    p_exp.add_argument("--root", required=True, help="Canonical SPEC position string")
    p_exp.add_argument("--out", required=True, help="Output certificate file path")
    p_exp.add_argument("--max-entries", type=int, default=20000, help="Maximum certificate entries")
    p_exp.add_argument("--max-length", type=int, default=None, help="Optional stripped byte length limit")
    p_exp.add_argument(
        "--allow-legacy-lookahead",
        action="store_true",
        help="Disable round-2 2-ply lookahead check (for benchmarking round-1 programs only)",
    )

    p_score = sub.add_parser("score", help="Score a strategy program on a family.")
    p_score.add_argument("program", help="Path to strategy .py file")
    p_score.add_argument("--family", required=True, help="Family name in families/<name>.json")
    p_score.add_argument("--max-entries", type=int, default=None, help="Override family max_entries")
    p_score.add_argument("--jobs", type=int, default=4, help="Parallel worker count (1..4)")
    p_score.add_argument("--no-record", action="store_true", help="Do not append to results/scores.tsv")
    p_score.add_argument(
        "--allow-legacy-lookahead",
        action="store_true",
        help="Disable round-2 2-ply lookahead check (for benchmarking round-1 programs only)",
    )

    p_all = sub.add_parser(
        "expand-all",
        help="Expand from every valid White-to-move position of a material class on WxH.",
    )
    p_all.add_argument("program", help="Path to strategy .py file")
    p_all.add_argument("--material", required=True, help="Material class, e.g. KQK or KRK")
    p_all.add_argument("--board", required=True, help="Board size WxH, e.g. 4x4")
    p_all.add_argument("--out", default=None, help="Output union certificate file path")
    p_all.add_argument("--jobs", type=int, default=4, help="Parallel worker count (1..4)")
    p_all.add_argument("--shard", default=None, help="Optional shard I/N (0-indexed) for split runs")
    p_all.add_argument("--shard-out", default=None, help="JSON output path when --shard is set")
    p_all.add_argument(
        "--merge-shards",
        nargs="+",
        default=None,
        help="Merge precomputed shard JSON files into the union certificate",
    )
    p_all.add_argument("--no-verify", action="store_true", help="Skip mcheck.py verification")
    p_all.add_argument(
        "--allow-legacy-lookahead",
        action="store_true",
        help="Disable round-2 2-ply lookahead check",
    )

    p_aud = sub.add_parser(
        "audit-rank",
        help="Audit whether a program's potential function strictly decreases along 2-ply steps.",
    )
    p_aud.add_argument("program", help="Path to strategy .py file")
    p_aud.add_argument("--cert", required=True, help="Path to certificate file")
    p_aud.add_argument("--fn", default="_pot", help="Potential function name in program (default: _pot)")
    p_aud.add_argument("--jobs", type=int, default=4, help="Parallel worker count (1..4)")

    p_lia = sub.add_parser(
        "lint-lia",
        help="Check that a program's potential (or witness) function stays inside Linear Integer Arithmetic.",
    )
    p_lia.add_argument("program", help="Path to strategy .py file")
    p_lia.add_argument("--fn", default="_pot", help="Function name to check (default: _pot)")
    p_lia.add_argument(
        "--allow-move-formatting",
        action="store_true",
        help="Allow rules.square_name() for formatting move strings (auto-enabled for --fn hint)",
    )

    p_hint = sub.add_parser(
        "audit-hint",
        help="Audit an explicit witness rule hint(pos) over every valid position of (material, board).",
    )
    p_hint.add_argument("program", help="Path to strategy .py file")
    p_hint.add_argument("--material", required=True, help="Material class, e.g. KQK")
    p_hint.add_argument("--board", required=True, help="Board size WxH, e.g. 4x4")
    p_hint.add_argument("--pot-fn", default="_pot", help="Potential function name (default: _pot)")
    p_hint.add_argument("--hint-fn", default="hint", help="Witness function name (default: hint)")
    p_hint.add_argument("--jobs", type=int, default=4, help="Parallel worker count (1..4)")

    args = parser.parse_args(argv)
    if args.cmd == "expand":
        return _cmd_expand(args)
    if args.cmd == "score":
        return _cmd_score(args)
    if args.cmd == "expand-all":
        return _cmd_expand_all(args)
    if args.cmd == "audit-rank":
        return _cmd_audit_rank(args)
    if args.cmd == "lint-lia":
        return _cmd_lint_lia(args)
    if args.cmd == "audit-hint":
        return _cmd_audit_hint(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
