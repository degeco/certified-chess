#!/usr/bin/env python3
"""Differential test on 8x8 game play: random walks from castling- and en-passant-rich
positions, compared move for move between 03-checker (Python) and 02-engine (C++).

Usage: design/walktest.py [walks per root, default 300] [seed, default 1]
The random placements used by difftest.sh almost never produce en-passant squares;
this test exists to cover them.
"""
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "03-checker"))
import rules  # noqa: E402

ROOTS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -",
    "4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - -",  # pawns only: many en-passant chances
    "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq -",
]


def main():
    walks = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    expected = {}
    for root in ROOTS:
        for _ in range(walks):
            pos = rules.parse_position(root)
            for _ in range(60):
                key = rules.format_position(pos)
                trans = sorted((m, rules.format_position(p)) for m, p in rules.legal_transitions(pos))
                expected[key] = "|".join(f"{m}:{p}" for m, p in trans)
                if not trans:
                    break
                pos = rules.apply_move(pos, rng.choice(trans)[0])
    keys = sorted(expected)
    out = subprocess.run(
        [os.path.join(ROOT, "02-engine", "bin", "mchess"), "batch"],
        input="\n".join(keys) + "\n", capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    bad = 0
    for key, line in zip(keys, out):
        if line != f"{key}\t{expected[key]}":
            bad += 1
            if bad <= 3:
                print("MISMATCH", key, "\n  engine :", line, "\n  checker:", expected[key])
    ep = sum(1 for k in keys if k.split()[3] != "-")
    castle = sum(1 for k in keys if k.split()[2] != "-")
    promo = sum(expected[k].count("q:") for k in keys)
    print(f"positions={len(keys)} with_ep={ep} with_castling={castle} "
          f"queen_promotions={promo} engine_lines={len(out)} mismatches={bad}")
    sys.exit(1 if bad or len(out) != len(keys) else 0)


if __name__ == "__main__":
    main()
