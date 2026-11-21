# 07-strategies Report

*Caveat (SPEC section 2)*: All game values proven here hold for the idealised game without the 50-move rule, repetition rule, or insufficient-material adjudication (infinite play is a draw). All claims rest solely on independent verification by `../03-checker/mcheck.py`.

## Status

Round 2 in progress. Step 0 baseline reconstructed from Round 1 outputs (`results/scores.tsv` and `strategies/`). Steps 1–3 (harness round-2 rules, whole-class `expand-all` proofs, potential ranking audit `audit-rank`, and `krk` iteration) will be added incrementally below as each completes.

## Round 1 Scoreboard Baseline

All lengths shown in **AST nodes** (`ast.walk` count after removing docstrings, official Round 2 metric) and **stripped bytes**. Full per-version notes are in [LOG.md](LOG.md).

| Family | Program | Nodes | Bytes | Coverage | Entries | Max Rank | Entries/Node | Expand (s) | Verify (s) | R2 2-ply OK? |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| `kk-draw` | [kk_draw_v1.py](strategies/kk_draw_v1.py) | 17 | 65 | 100/100 (100%) | 16,126 | 0 | 948.59 | 5.31 | 3.55 | Yes |
| `kk-draw` | [kk_draw_v2.py](strategies/kk_draw_v2.py) | 203 | 565 | 100/100 (100%) | 88,814 | 0 | 437.51 | 33.00 | 20.83 | Yes |
| `kk-draw` | [kk_draw_v3.py](strategies/kk_draw_v3.py) | 99 | 309 | 100/100 (100%) | 12,215 | 0 | 123.38 | 4.57 | 2.92 | Yes |
| `mini4x4-start` | [mini4x4_v1.py](strategies/mini4x4_v1.py) | 230 | 835 | 1/1 (100%) | 5 | 4 | 0.02 | 0.003 | 0.001 | Yes |
| `mini4x4-start` | [mini4x4_v2.py](strategies/mini4x4_v2.py) | 350 | 1174 | 1/1 (100%) | 5 | 4 | 0.01 | 0.008 | 0.001 | No (`_mate_in_1(rp)`) |
| `mini4x4-start` | [mini4x4_v3.py](strategies/mini4x4_v3.py) | 193 | 832 | 1/1 (100%) | 5 | 4 | 0.03 | 0.010 | 0.001 | No (recursion) |
| `mini4x4-start` | [mini4x4_v4.py](strategies/mini4x4_v4.py) | 94 | 314 | 1/1 (100%) | 5 | 4 | 0.05 | 0.003 | 0.001 | Yes |
| `kqk` | [kqk_v1.py](strategies/kqk_v1.py) | 513 | 1738 | 669/1000 (66.9%) | 5,909 | 17 | 11.52 | 33.19 | 1.42 | Yes |
| `kqk` | [kqk_v2.py](strategies/kqk_v2.py) | 1296 | 3480 | 777/1000 (77.7%) | 7,556 | 13 | 5.83 | 216.25 | 1.58 | No (`_mate1(rp)`) |
| `kqk` | [kqk_v3.py](strategies/kqk_v3.py) | 1681 | 3976 | 971/1000 (97.1%) | 15,858 | 16 | 9.43 | 165.74 | 3.71 | No (`_mate1(rp)`) |
| `kqk` | [kqk_v4.py](strategies/kqk_v4.py) | 1741 | 3753 | 556/1000 (55.6%) | 2,510 | 11 | 1.44 | 127.24 | 0.78 | No (`_mate1(rp)`) |
| `kqk` | [kqk_v5.py](strategies/kqk_v5.py) | **754** | **1664** | **1000/1000 (100%)** | **19,286** | **16** | **25.58** | 97.98 | 4.74 | **Yes** |
| `krk` | [krk_v1.py](strategies/krk_v1.py) | 495 | 1536 | 118/1000 (11.8%) | 388 | 10 | 0.78 | 15.03 | 0.11 | Yes |
| `krk` | [krk_v2.py](strategies/krk_v2.py) | 2094 | 5738 | 367/1000 (36.7%) | 2,760 | 10 | 1.32 | 71.14 | 0.71 | No (`_mate1(rp)`) |
| `krk` | [krk_v3.py](strategies/krk_v3.py) | 2108 | 5392 | 416/1000 (41.6%) | 5,688 | 18 | 2.70 | 260.58 | 1.43 | No (`_mate1(rp)`) |

Note on `mini4x4-start`: Confirmed forced mate in 4 with a 5-entry certificate ([results/mini4x4-start.cert](results/mini4x4-start.cert)), verified `VALID` by `mcheck.py`.

## Round 2 Results

*(Populated step-by-step below.)*
