# 07-strategies Report

*Caveat (SPEC section 2)*: All game values proven here hold for the idealised game without the 50-move rule, repetition rule, or insufficient-material adjudication (infinite play is a draw). All flat-certificate claims rest solely on independent verification by `../03-checker/mcheck.py` (and `../08-checker2/mcheck2` where noted).

## 1. Rounds 1 & 2 Summary and Scoreboard

All lengths are reported in **AST nodes** (`ast.walk` count after removing docstrings; official Round 2 metric) and **stripped bytes** (UTF-8 bytes after stripping comments, docstrings, and blank lines). Full per-version notes (all 7 `kqk` versions and all 21 `krk` versions) are in [LOG.md](LOG.md).

### Family Ensemble Scoreboard (`results/scores.tsv`)

| Family | Program | Nodes | Bytes | Coverage | Entries | Max Rank | Entries/Node | Expand (s) | Verify (s) | 2-ply OK? |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| `kk-draw` | [kk_draw_v1.py](strategies/kk_draw_v1.py) | 17 | 65 | 100/100 (100%) | 16,126 | 0 | 948.59 | 5.31 | 3.55 | Yes |
| `kk-draw` | [kk_draw_v2.py](strategies/kk_draw_v2.py) | 203 | 565 | 100/100 (100%) | 88,814 | 0 | 437.51 | 33.00 | 20.83 | Yes |
| `kk-draw` | [kk_draw_v3.py](strategies/kk_draw_v3.py) | 99 | 309 | 100/100 (100%) | 12,215 | 0 | 123.38 | 4.57 | 2.92 | Yes |
| `mini4x4-start` | [mini4x4_v1.py](strategies/mini4x4_v1.py) | 230 | 835 | 1/1 (100%) | 5 | 4 | 0.02 | 0.003 | 0.001 | Yes |
| `mini4x4-start` | [mini4x4_v2.py](strategies/mini4x4_v2.py) | 350 | 1174 | 1/1 (100%) | 5 | 4 | 0.01 | 0.008 | 0.001 | No (ply-2 `_mate_in_1`) |
| `mini4x4-start` | [mini4x4_v3.py](strategies/mini4x4_v3.py) | 193 | 832 | 1/1 (100%) | 5 | 4 | 0.03 | 0.010 | 0.001 | No (recursion) |
| `mini4x4-start` | [mini4x4_v4.py](strategies/mini4x4_v4.py) | 94 | 314 | 1/1 (100%) | 5 | 4 | 0.05 | 0.003 | 0.001 | Yes |
| `kqk` | [kqk_v1.py](strategies/kqk_v1.py) | 513 | 1738 | 669/1000 (66.9%) | 5,909 | 17 | 11.52 | 33.19 | 1.42 | Yes |
| `kqk` | [kqk_v2.py](strategies/kqk_v2.py) | 1296 | 3480 | 777/1000 (77.7%) | 7,556 | 13 | 5.83 | 216.25 | 1.58 | No (ply-2 `_mate1`) |
| `kqk` | [kqk_v3.py](strategies/kqk_v3.py) | 1681 | 3976 | 971/1000 (97.1%) | 15,858 | 16 | 9.43 | 165.74 | 3.71 | No (ply-2 `_mate1`) |
| `kqk` | [kqk_v4.py](strategies/kqk_v4.py) | 1741 | 3753 | 556/1000 (55.6%) | 2,510 | 11 | 1.44 | 127.24 | 0.78 | No (ply-2 `_mate1`) |
| `kqk` | [kqk_v5.py](strategies/kqk_v5.py) | 754 | 1664 | 1000/1000 (100%) | 19,286 | 16 | 25.58 | 97.98 | 4.74 | Yes |
| `kqk` | **[kqk_v7.py](strategies/kqk_v7.py)** | **793** | **1747** | **1000/1000 (100%)** | **19,571** | **17** | **24.68** | 75.06 | 3.16 | **Yes** |
| `krk` | [krk_v1.py](strategies/krk_v1.py) | 495 | 1536 | 118/1000 (11.8%) | 388 | 10 | 0.78 | 15.03 | 0.11 | Yes |
| `krk` | [krk_v2.py](strategies/krk_v2.py) | 2094 | 5738 | 367/1000 (36.7%) | 2,760 | 10 | 1.32 | 71.14 | 0.71 | No (ply-2 `_mate1`) |
| `krk` | [krk_v3.py](strategies/krk_v3.py) | 2108 | 5392 | 416/1000 (41.6%) | 5,688 | 18 | 2.70 | 260.58 | 1.43 | No (ply-2 `_mate1`) |
| `krk` | [krk_v4.py](strategies/krk_v4.py) | 1388 | 3120 | 295/1000 (29.5%) | 3,713 | 18 | 2.68 | 76.13 | 1.16 | Yes |
| `krk` | [krk_v5.py](strategies/krk_v5.py) | 2171 | 4918 | 693/1000 (69.3%) | 139,863 | 36 | 64.42 | 1517.98 | 39.86 | No (ply-2 `_m1`) |
| `krk` | [krk_v6.py](strategies/krk_v6.py) | 1071 | 2338 | 448/1000 (44.8%) | 8,254 | 12 | 7.71 | 149.11 | 1.69 | No (ply-2 `_m1`) |
| `krk` | **[krk_v21.py](strategies/krk_v21.py)** | **892** | **2230** | **1000/1000 (100%)** | **433,400** | **68** | **485.87** | 1233.87 | 72.49 | **Yes** |

### Whole-Class Union Certificates (4x4, 5x5, 6x6)

Both `kqk_v7.py` and `krk_v21.py` cover **every** valid White-to-move position of their material class on 4x4, 5x5, and 6x6, verified `VALID` by both checkers (`03-checker/mcheck.py` and `08-checker2/mcheck2` on 4x4 and 5x5; `08-checker2/mcheck2` on 6x6; 7x7 and 8x8 runs are handled by the lead):

| Program | Nodes / Bytes | 4x4 | 5x5 | 6x6 |
|---|---:|---|---|---|
| `kqk_v7` | 793 / 1,747 B | 812 of 812 (max rank 6) | 4,976 of 4,976 (max rank 10) | 19,360 of 19,360 (max rank 13) |
| `krk_v21` | 892 / 2,230 B | 1,312 of 1,312 (max rank 17) | 7,040 of 7,040 (max rank 26) | 25,440 of 25,440 (max rank 43) |

### Potential Ranking Audit (`audit-rank`, Round 2 Programs)

| Program | Board | Entries | Mate-in-1 | 2-ply Steps | Decrease | Equal | Increase | Strict? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `kqk_v7` | 4x4 | 812 | 184 | 940 | 940 (100%) | 0 | 0 | **Yes** |
| `kqk_v7` | 5x5 | 4,976 | 464 | 7,748 | 7,748 (100%) | 0 | 0 | **Yes** |
| `kqk_v7` | 6x6 | 19,360 | 920 | 35,184 | 35,184 (100%) | 0 | 0 | **Yes** |
| `krk_v21` | 4x4 | 1,312 | 120 | 2,306 | 2,150 (93.2%) | 21 | 135 | No |
| `krk_v21` | 5x5 | 7,040 | 288 | 18,434 | 17,852 (96.8%) | 48 | 534 | No |
| `krk_v21` | 6x6 | 25,440 | 560 | 80,112 | 78,406 (97.9%) | 82 | 1,624 | No |

### Answers to Round 2 Questions

- **Did program length have to grow with the board?**
  **No.** A single board-size-parametric program of fixed length covers every board size from 4x4 through 8x8 (confirmed 1000/1000 across 4x4..8x8 ensembles and 100% of all valid positions on 4x4, 5x5, and 6x6): **793 AST nodes (1,747 B)** for KQK (`kqk_v7.py`) and **892 AST nodes (2,230 B)** for KRK (`krk_v21.py`). While the flat union certificate grows roughly like `O((W*H)^3)` (from 812 to 19,360 for KQK and 1,312 to 25,440 for KRK across 4x4→6x6), the strategy program stays constant size. This supports Hypothesis H2 for 3-piece winning endgames.
- **Which ideas mattered most?**
  1. **2-ply minimax over a single lexicographic potential** (replacing procedural case trees): cut KQK program size by >50% (1,741 → 754 nodes) while jumping from 97.1% to 100%, and cut KRK from 2,171 nodes (69.3%, illegal 3-ply) to 892 nodes (100%, legal 2-ply). Evaluating `max(_pot(rp))` over all Black replies automatically avoids hanging the Q/R, stalemates, and tactical bounces without hand-coding tactical checks.
  2. **Single-axis 1D vertical strip for KRK** (abandoning 2D box shrinking in `krk_v15..v21`): 2D boxes suffered incurable axis-flipping cycles on 5x5 and 6x6 whenever Black crossed the Rook's file/rank. Fixing one herding axis (vertical strip `eff_bh` + left-herding `bf -> 0`) eliminated axis flips completely.
  3. **Phase separation on King arrival & corner cage in KRK**: only herding `bf` once `K` reaches the opposition rank `tr` (while keeping `R` safe and far during `K`'s approach), adding the 2-wide corner mating cage (`eff_bh = min(bh, br_d + 1)`), and fixing `tr = h // 2` when `eff_bh >= h - 1` closed the final ~0.3% edge cases.
  4. **Eliminating non-monotonic tie-breaks in KQK**: targeting `Q`'s square `(qf, qr)` until `bw == 1` or `bh == 1`, plus deterministic axis tie-breaking (`bh`, `k_ax`, `cf + cr`), turned `kqk_v5` into a 100%-complete strict ranking (`kqk_v7`).

---

## 2. Round 3: Symbolic Step (LIA Potential, Witness Rule, Z3 Proof)

*(Updated after each step below.)*
