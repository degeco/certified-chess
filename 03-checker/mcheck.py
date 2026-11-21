#!/usr/bin/env python3
"""Trusted certificate checker and CLI for small-board and 8x8 chess (SPEC v1.1)."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import time

from rules import (
    Position,
    apply_move,
    in_check,
    legal_moves,
    legal_transitions,
    parse_position,
    perft,
)


@dataclass(frozen=True)
class VerifyResult:
    valid: bool
    claim: str | None = None
    root: str | None = None
    entries: int = 0
    max_rank: int = 0
    seconds: float = 0.0
    error_entry: str | None = None
    error_reason: str | None = None


def _fail(entry: str, reason: str, t0: float) -> VerifyResult:
    return VerifyResult(
        valid=False,
        seconds=time.perf_counter() - t0,
        error_entry=entry,
        error_reason=reason,
    )


def _strip_newline(line: str) -> str:
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _parse_canonical_rank(rank_str: str) -> int:
    """Parse a canonical non-negative ASCII integer (no leading zeros, signs, or spaces)."""
    if rank_str == "0":
        return 0
    if (
        not rank_str
        or not rank_str.isascii()
        or not rank_str.isdigit()
        or rank_str.startswith("0")
    ):
        raise ValueError(f"invalid rank {rank_str!r}")
    return int(rank_str)


def _parse_canonical_position(pos_str: str) -> Position:
    pos = parse_position(pos_str)
    canonical = pos.to_fen()
    if canonical != pos_str:
        raise ValueError(f"non-canonical position string (expected {canonical!r})")
    return pos


def _is_prover_stalemate(pos: Position, prover: str) -> bool:
    """Return True if `prover` is to move in `pos`, has no legal move, and is not in check."""
    return pos.stm == prover and not in_check(pos) and not legal_moves(pos)


def verify_certificate(path: str) -> VerifyResult:
    """Verify a certificate file strictly according to SPEC section 4."""
    t0 = time.perf_counter()

    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = [_strip_newline(raw) for raw in fh]
    except (OSError, UnicodeDecodeError) as exc:
        return _fail("file", f"cannot read certificate: {exc}", t0)

    # Header: 3 mandatory lines.
    if len(lines) < 3:
        return _fail("header", "certificate must have at least 3 header lines", t0)

    if lines[0] != "#cert v1":
        return _fail("line 1", f"expected '#cert v1', got {lines[0]!r}", t0)

    claim_line = lines[1]
    if claim_line not in (
        "#claim WIN w",
        "#claim WIN b",
        "#claim ATLEAST_DRAW w",
        "#claim ATLEAST_DRAW b",
    ):
        return _fail("line 2", f"invalid #claim header: {claim_line!r}", t0)
    _, claim_kind, prover = claim_line.split(" ")
    claim_text = f"{claim_kind} {prover}"

    root_line = lines[2]
    if not root_line.startswith("#root "):
        return _fail("line 3", f"expected '#root <position>', got {root_line!r}", t0)
    root_str = root_line[6:]
    try:
        root_pos = _parse_canonical_position(root_str)
    except ValueError as exc:
        return _fail(f"line 3 (#root {root_str})", str(exc), t0)

    # Body: parse every entry, rejecting duplicates, malformed lines, and non-canonical strings.
    entries: dict[str, tuple[Position, str, int, int]] = {}
    for line_no, line in enumerate(lines[3:], start=4):
        fields = line.split("\t")
        if len(fields) != 3:
            return _fail(
                f"line {line_no}",
                f"expected 3 tab-separated fields, got {len(fields)}",
                t0,
            )
        pos_str, move_str, rank_str = fields
        try:
            pos = _parse_canonical_position(pos_str)
        except ValueError as exc:
            return _fail(f"line {line_no} ({pos_str})", str(exc), t0)

        if (pos.width, pos.height) != (root_pos.width, root_pos.height):
            return _fail(
                f"line {line_no} ({pos_str})",
                f"board size {pos.width}x{pos.height} does not match root {root_pos.width}x{root_pos.height}",
                t0,
            )

        if pos_str in entries:
            return _fail(f"line {line_no} ({pos_str})", "duplicate position entry", t0)

        try:
            rank = _parse_canonical_rank(rank_str)
        except ValueError as exc:
            return _fail(f"line {line_no} ({pos_str})", str(exc), t0)

        if claim_kind == "ATLEAST_DRAW" and rank != 0:
            return _fail(
                f"line {line_no} ({pos_str})",
                f"ATLEAST_DRAW entry must have rank 0, got {rank}",
                t0,
            )

        entries[pos_str] = (pos, move_str, rank, line_no)

    # Check root condition (SPEC v1.1 section 4).
    if root_pos.stm == prover:
        if root_str not in entries:
            if not (claim_kind == "ATLEAST_DRAW" and _is_prover_stalemate(root_pos, prover)):
                return _fail(f"root ({root_str})", "root position missing from entries", t0)
    else:
        root_replies = legal_transitions(root_pos)
        if claim_kind == "WIN" and not root_replies:
            if not in_check(root_pos):
                return _fail(
                    f"root ({root_str})",
                    "opponent has no legal moves at root and is not in check (stalemate)",
                    t0,
                )
        for reply_move, reply_pos in root_replies:
            reply_str = reply_pos.to_fen()
            if reply_str not in entries:
                if not (claim_kind == "ATLEAST_DRAW" and _is_prover_stalemate(reply_pos, prover)):
                    return _fail(
                        f"root ({root_str})",
                        f"missing entry for opponent reply {reply_move} -> {reply_str}",
                        t0,
                    )

    # Check every entry in file order (SPEC section 4).
    for pos_str, (pos, move_str, rank, line_no) in entries.items():
        tag = f"line {line_no} ({pos_str})"

        # Rule 1: prover is to move in p, and m is legal in p.
        if pos.stm != prover:
            return _fail(tag, f"side to move is {pos.stm!r}, expected prover {prover!r}", t0)
        try:
            q_pos = apply_move(pos, move_str)
        except ValueError as exc:
            return _fail(tag, f"illegal move {move_str!r}: {exc}", t0)

        replies = legal_transitions(q_pos)

        if claim_kind == "WIN":
            # Rule 2: if opponent has no legal move in q, opponent must be in check.
            if not replies:
                if not in_check(q_pos):
                    return _fail(
                        tag,
                        f"move {move_str} leads to stalemate (not checkmate) in WIN certificate",
                        t0,
                    )
            else:
                # Rule 3: every legal reply r leads to an entry with rank strictly less than d.
                for reply_move, qr_pos in replies:
                    qr_str = qr_pos.to_fen()
                    child = entries.get(qr_str)
                    if child is None:
                        return _fail(
                            tag,
                            f"after {move_str}, missing entry for opponent reply {reply_move} -> {qr_str}",
                            t0,
                        )
                    child_rank = child[2]
                    if not (child_rank < rank):
                        return _fail(
                            tag,
                            f"after {move_str} {reply_move} -> {qr_str}, child rank {child_rank} is not < parent rank {rank}",
                            t0,
                        )
        else:
            # ATLEAST_DRAW Rule 2: every legal reply r leads to a covered position
            # (an entry or a prover stalemate).
            for reply_move, qr_pos in replies:
                qr_str = qr_pos.to_fen()
                if qr_str not in entries and not _is_prover_stalemate(qr_pos, prover):
                    return _fail(
                        tag,
                        f"after {move_str}, reply {reply_move} -> {qr_str} is not covered (missing entry and not prover stalemate)",
                        t0,
                    )

    max_rank = max((entry[2] for entry in entries.values()), default=0)
    return VerifyResult(
        valid=True,
        claim=claim_text,
        root=root_str,
        entries=len(entries),
        max_rank=max_rank,
        seconds=time.perf_counter() - t0,
    )


def _cmd_verify(args: list[str]) -> int:
    if len(args) != 1:
        print("INVALID\nentry: cli\nreason: usage: mcheck.py verify <file.cert>")
        return 1
    res = verify_certificate(args[0])
    if res.valid:
        print("VALID")
        print(f"claim: {res.claim}")
        print(f"root: {res.root}")
        print(f"entries: {res.entries}")
        print(f"max_rank: {res.max_rank}")
        print(f"seconds: {res.seconds:.4f}")
        return 0
    print("INVALID")
    print(f"entry: {res.error_entry}")
    print(f"reason: {res.error_reason}")
    return 1


def _cmd_moves(args: list[str]) -> int:
    if len(args) != 1:
        print("usage: mcheck.py moves \"<position>\"", file=sys.stderr)
        return 1
    try:
        pos = parse_position(args[0])
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for move_str, next_pos in legal_transitions(pos):
        print(f"{move_str}\t{next_pos.to_fen()}")
    return 0


def _cmd_batch(args: list[str]) -> int:
    if args:
        print("usage: mcheck.py batch", file=sys.stderr)
        return 1
    for raw_line in sys.stdin:
        line = _strip_newline(raw_line)
        try:
            pos = parse_position(line)
        except ValueError:
            print(f"{line}\tERROR")
            continue
        pairs = "|".join(
            f"{move_str}:{next_pos.to_fen()}" for move_str, next_pos in legal_transitions(pos)
        )
        print(f"{pos.to_fen()}\t{pairs}")
    return 0


def _cmd_perft(args: list[str]) -> int:
    if len(args) != 2:
        print("usage: mcheck.py perft \"<position>\" <depth>", file=sys.stderr)
        return 1
    try:
        pos = parse_position(args[0])
        depth = int(args[1])
        if depth < 0:
            raise ValueError("depth must be non-negative")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(perft(pos, depth))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: mcheck.py <verify|moves|batch|perft> ...",
            file=sys.stderr,
        )
        return 1
    cmd, rest = args[0], args[1:]
    if cmd == "verify":
        return _cmd_verify(rest)
    if cmd == "moves":
        return _cmd_moves(rest)
    if cmd == "batch":
        return _cmd_batch(rest)
    if cmd == "perft":
        return _cmd_perft(rest)
    print(f"unknown command: {cmd!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
