#!/usr/bin/env python3
"""Verify sampled certificates with 03-checker/mcheck.py and summarize tablebase & H1 results."""

from __future__ import annotations

import csv
import glob
import math
import os
import random
import statistics
import sys
import time
from collections import defaultdict

# Import 03-checker/mcheck.py
CHECKER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "03-checker"))
sys.path.insert(0, CHECKER_DIR)
import mcheck  # type: ignore


def verify_cert_dirs(dirs: list[str], max_per_dir: int | None = None, seed: int = 42) -> None:
    rng = random.Random(seed)
    total_checked = 0
    total_valid = 0
    total_failed = 0
    total_entries = 0
    t0 = time.perf_counter()

    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, "*.cert")))
        if max_per_dir is not None and len(files) > max_per_dir:
            files = rng.sample(files, max_per_dir)
        d_valid = 0
        d_fail = 0
        d_win = 0
        d_draw = 0
        for fp in files:
            res = mcheck.verify_certificate(fp)
            total_checked += 1
            if res.valid:
                total_valid += 1
                d_valid += 1
                total_entries += res.entries
                if res.claim and res.claim.startswith("WIN"):
                    d_win += 1
                else:
                    d_draw += 1
            else:
                total_failed += 1
                d_fail += 1
                print(f"FAIL {fp}: {res.error_entry} -> {res.error_reason}")
        print(
            f"[VERIFY] {d}: checked={len(files)} valid={d_valid} (WIN={d_win}, DRAW={d_draw}) fail={d_fail}"
        )

    dt = time.perf_counter() - t0
    print(
        f"[VERIFY TOTAL] checked={total_checked} valid={total_valid} fail={total_failed} "
        f"total_entries={total_entries} time={dt:.2f}s"
    )
    if total_failed > 0:
        sys.exit(1)


def summarize_tables(tsv_paths: list[str]) -> None:
    print("\n=== TABLEBASE SUMMARY BY BOARD ===")
    for path in tsv_paths:
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        if not rows:
            continue
        board = rows[0]["board"]
        total_idx = sum(int(r["index_size"]) for r in rows)
        total_legal = sum(int(r["legal"]) for r in rows)
        total_wins = sum(int(r["wins"]) for r in rows)
        total_draws = sum(int(r["draws"]) for r in rows)
        total_losses = sum(int(r["losses"]) for r in rows)
        total_mates = sum(int(r["checkmates"]) for r in rows)
        total_stales = sum(int(r["stalemates"]) for r in rows)
        total_bytes = sum(int(r["table_bytes"]) for r in rows)
        total_sec = sum(float(r["gen_sec"]) for r in rows)
        max_w_row = max(rows, key=lambda r: int(r["max_win_dtm"]))
        max_l_row = max(rows, key=lambda r: int(r["max_loss_dtm"]))
        print(
            f"{board}: sigs={len(rows)} index={total_idx:,} legal={total_legal:,} "
            f"W={total_wins:,} ({100*total_wins/total_legal:.2f}%) "
            f"D={total_draws:,} ({100*total_draws/total_legal:.2f}%) "
            f"L={total_losses:,} ({100*total_losses/total_legal:.2f}%) "
            f"mates={total_mates:,} stales={total_stales:,} "
            f"max_win_dtm={max_w_row['max_win_dtm']} ({max_w_row['sig']}: {max_w_row['max_win_fen']}) "
            f"max_loss_dtm={max_l_row['max_loss_dtm']} ({max_l_row['sig']}) "
            f"gen_sec={total_sec:.2f}s bytes={total_bytes:,}"
        )


def summarize_h1(h1_path: str, out_summary_path: str) -> None:
    if not os.path.exists(h1_path):
        return
    # Group by (board, sig, claim_type)
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    max_ranks: dict[tuple[str, str, str], int] = defaultdict(int)
    table_pos: dict[tuple[str, str], int] = {}

    by_board_claim: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)

    with open(h1_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for r in reader:
            board = r["board"]
            sig = r["signature"]
            claim_type = "WIN" if r["claim"].startswith("WIN") else "ATLEAST_DRAW"
            entries = int(r["entries"])
            mr = int(r["max_rank"])
            tpos = int(r["table_positions"])
            groups[(board, sig, claim_type)].append(entries)
            if mr > max_ranks[(board, sig, claim_type)]:
                max_ranks[(board, sig, claim_type)] = mr
            table_pos[(board, sig)] = tpos
            by_board_claim[(board, claim_type)].append((entries, tpos))

    with open(out_summary_path, "w", newline="", encoding="utf-8") as out_fh:
        w = csv.writer(out_fh, delimiter="\t")
        w.writerow(
            [
                "board",
                "signature",
                "claim",
                "samples",
                "table_positions",
                "min_entries",
                "median_entries",
                "mean_entries",
                "max_entries",
                "max_rank",
                "mean_ratio",
            ]
        )
        for (board, sig, ctype) in sorted(groups.keys()):
            vals = sorted(groups[(board, sig, ctype)])
            tpos = table_pos[(board, sig)]
            mn = vals[0]
            med = statistics.median(vals)
            mean = statistics.mean(vals)
            mx = vals[-1]
            mr = max_ranks[(board, sig, ctype)]
            ratio = mean / tpos if tpos > 0 else 0.0
            w.writerow(
                [
                    board,
                    sig,
                    ctype,
                    len(vals),
                    tpos,
                    mn,
                    f"{med:.1f}",
                    f"{mean:.2f}",
                    mx,
                    mr,
                    f"{ratio:.6f}",
                ]
            )

    print("\n=== H1 SUMMARY BY BOARD & CLAIM ===")
    for (board, ctype) in sorted(by_board_claim.keys()):
        pairs = by_board_claim[(board, ctype)]
        ents = [p[0] for p in pairs]
        tposs = [p[1] for p in pairs]
        ratios = [e / t for e, t in pairs if t > 0]
        print(
            f"{board} {ctype}: n={len(ents)} "
            f"entries(min={min(ents)}, med={statistics.median(ents):.1f}, "
            f"mean={statistics.mean(ents):.2f}, max={max(ents)}) "
            f"ratio_to_table(med={statistics.median(ratios):.5f}, mean={statistics.mean(ratios):.5f}, max={max(ratios):.5f})"
        )


def main() -> None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    res_dir = os.path.join(base, "results")

    cert_dirs = [
        os.path.join(res_dir, d)
        for d in ["certs_3x3", "certs_4x4", "certs_4x5", "certs_5x5", "certs_8x8"]
        if os.path.isdir(os.path.join(res_dir, d))
    ]
    if cert_dirs:
        verify_cert_dirs(cert_dirs)

    tables = [
        os.path.join(res_dir, f)
        for f in ["tables_3x3.tsv", "tables_4x4.tsv", "tables_4x5.tsv", "tables_5x5.tsv", "tables_8x8.tsv"]
    ]
    summarize_tables(tables)

    h1_path = os.path.join(res_dir, "h1.tsv")
    summarize_h1(h1_path, os.path.join(res_dir, "h1_summary.tsv"))


if __name__ == "__main__":
    main()
