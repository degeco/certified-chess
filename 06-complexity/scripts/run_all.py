#!/usr/bin/env python3
"""Reproducible runner for 06-complexity experiments."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REACH = ROOT / "bin" / "reach"
ESTIMATE = ROOT / "bin" / "estimate"

BOARDS = [
    ("mini4x4", 5_000_000),
    ("mini4x5", 5_000_000),
    ("mini5x5", 5_000_000),
    ("losalamos6x6", 5_000_000),
    ("std6x6", 5_000_000),
    ("std8", 500_000),
]


def run_cmd(cmd):
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["estimate", "reach", "all"], default="estimate")
    ap.add_argument("--board", default="all", help="Board name or 'all'")
    ap.add_argument("--max-mem-mb", type=int, default=3500)
    ap.add_argument("--max-sec", type=int, default=180)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    selected = BOARDS if args.board == "all" else [b for b in BOARDS if b[0] == args.board]
    if not selected:
        print(f"Unknown board: {args.board}", file=sys.stderr)
        sys.exit(1)

    if args.mode in ("estimate", "all"):
        print("=== ESTIMATOR RUNS ===")
        for name, samples in selected:
            run_cmd([str(ESTIMATE), name, "--samples", str(samples), "--seed", str(args.seed)])

    if args.mode in ("reach", "all"):
        print("=== REACHABILITY BFS RUNS ===")
        for name, _ in selected:
            if name == "std6x6":
                continue
            run_cmd([
                str(REACH), name,
                "--max-mem-mb", str(args.max_mem_mb),
                "--max-sec", str(args.max_sec),
            ])


if __name__ == "__main__":
    main()
