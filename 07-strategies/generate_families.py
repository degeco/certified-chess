#!/usr/bin/env python3
"""Generate seeded, reproducible root families in families/<name>.json."""

from __future__ import annotations

import json
from pathlib import Path
import random
import sys

BASE_DIR = Path(__file__).resolve().parent
CHECKER_DIR = BASE_DIR.parent / "03-checker"
if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import rules  # noqa: E402

BOARD_SIZES = [(4, 4), (5, 5), (6, 6), (7, 7), (8, 8)]


def _build_fen(width: int, height: int, placements: list[tuple[int, int, str]], stm: str) -> str:
    board = ["."] * (width * height)
    for f, r, piece in placements:
        board[r * width + f] = piece
    pos = rules.Position(
        width=width,
        height=height,
        board=tuple(board),
        stm=stm,
        castling="",
        ep=None,
    )
    return pos.to_fen()


def sample_piece_family(
    pieces: list[str],
    per_board: int,
    stms: list[str],
    seed: int,
) -> list[str]:
    """Sample `per_board` unique valid positions for each board size in BOARD_SIZES."""
    rng = random.Random(seed)
    roots: list[str] = []
    for w, h in BOARD_SIZES:
        squares = [(f, r) for r in range(h) for f in range(w)]
        seen: set[str] = set()
        board_roots: list[str] = []
        idx = 0
        while len(board_roots) < per_board:
            stm = stms[idx % len(stms)]
            chosen = rng.sample(squares, len(pieces))
            fen = _build_fen(
                w,
                h,
                [(f, r, p) for (f, r), p in zip(chosen, pieces)],
                stm,
            )
            if fen in seen:
                continue
            try:
                parsed = rules.parse_position(fen)
            except ValueError:
                continue
            canonical = parsed.to_fen()
            if canonical != fen:
                continue
            seen.add(canonical)
            board_roots.append(canonical)
            idx += 1
        roots.extend(board_roots)
    return roots


def write_family(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    families_dir = BASE_DIR / "families"

    kqk_roots = sample_piece_family(["K", "Q", "k"], per_board=200, stms=["w"], seed=7001)
    write_family(
        families_dir / "kqk.json",
        {
            "name": "kqk",
            "claim": "WIN w",
            "length_limit": 4000,
            "max_entries": 10000,
            "seed": 7001,
            "roots": kqk_roots,
        },
    )

    krk_roots = sample_piece_family(["K", "R", "k"], per_board=200, stms=["w"], seed=7002)
    write_family(
        families_dir / "krk.json",
        {
            "name": "krk",
            "claim": "WIN w",
            "length_limit": 6000,
            "max_entries": 20000,
            "seed": 7002,
            "roots": krk_roots,
        },
    )

    kk_roots = sample_piece_family(["K", "k"], per_board=20, stms=["w", "b"], seed=7003)
    write_family(
        families_dir / "kk-draw.json",
        {
            "name": "kk-draw",
            "claim": "ATLEAST_DRAW stm",
            "length_limit": 2000,
            "max_entries": 5000,
            "seed": 7003,
            "roots": kk_roots,
        },
    )

    write_family(
        families_dir / "mini4x4-start.json",
        {
            "name": "mini4x4-start",
            "claim": "WIN w",
            "length_limit": 4000,
            "max_entries": 5000,
            "roots": ["rqkr/pppp/PPPP/RQKR w - -"],
        },
    )

    print(
        f"Generated families: kqk={len(kqk_roots)}, krk={len(krk_roots)}, "
        f"kk-draw={len(kk_roots)}, mini4x4-start=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
