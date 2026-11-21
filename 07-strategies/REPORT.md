# 07-strategies Report

*Caveat (SPEC section 2)*: All game values proven here hold for the idealised game without the 50-move rule, repetition rule, or insufficient-material adjudication (infinite play is a draw). Flat-certificate claims rest on independent verification by `../03-checker/mcheck.py` and `../08-checker2/mcheck2`; symbolic all-board-size claims rest on Z3 4.16.0 (`smt/kqk.py`) with the encoding validated against `../03-checker/rules.py` on 4x4, 5x5, and 6x6.

---

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
| `kqk` | **[kqk_lia.py](strategies/kqk_lia.py)** *(Step 1, `_pot`+`move`)* | **1165** | **2774** | **1000/1000 (100%)** | **19,798** | **17** | **16.99** | 53.10 | 2.48 | **Yes** |
| `krk` | [krk_v1.py](strategies/krk_v1.py) | 495 | 1536 | 118/1000 (11.8%) | 388 | 10 | 0.78 | 15.03 | 0.11 | Yes |
| `krk` | [krk_v2.py](strategies/krk_v2.py) | 2094 | 5738 | 367/1000 (36.7%) | 2,760 | 10 | 1.32 | 71.14 | 0.71 | No (ply-2 `_mate1`) |
| `krk` | [krk_v3.py](strategies/krk_v3.py) | 2108 | 5392 | 416/1000 (41.6%) | 5,688 | 18 | 2.70 | 260.58 | 1.43 | No (ply-2 `_mate1`) |
| `krk` | [krk_v4.py](strategies/krk_v4.py) | 1388 | 3120 | 295/1000 (29.5%) | 3,713 | 18 | 2.68 | 76.13 | 1.16 | Yes |
| `krk` | [krk_v5.py](strategies/krk_v5.py) | 2171 | 4918 | 693/1000 (69.3%) | 139,863 | 36 | 64.42 | 1517.98 | 39.86 | No (ply-2 `_m1`) |
| `krk` | [krk_v6.py](strategies/krk_v6.py) | 1071 | 2338 | 448/1000 (44.8%) | 8,254 | 12 | 7.71 | 149.11 | 1.69 | No (ply-2 `_m1`) |
| `krk` | **[krk_v21.py](strategies/krk_v21.py)** | **892** | **2230** | **1000/1000 (100%)** | **433,400** | **68** | **485.87** | 1233.87 | 72.49 | **Yes** |

### Whole-Class Union Certificates (4x4, 5x5, 6x6)

All three winning programs cover **every** valid White-to-move position of their material class on 4x4, 5x5, and 6x6, verified `VALID` (both checkers `03-checker/mcheck.py` and `08-checker2/mcheck2` on 4x4/5x5; `08-checker2/mcheck2` on 6x6; 7x7 and 8x8 runs are handled by the lead):

| Program | Nodes / Bytes | 4x4 | 5x5 | 6x6 |
|---|---:|---|---|---|
| `kqk_v7` | 793 / 1,747 B | 812 of 812 (max rank 6) | 4,976 of 4,976 (max rank 10) | 19,360 of 19,360 (max rank 13) |
| `kqk_lia` (final) | 1,477 / 3,520 B (`_pot`+`move`); 5,309 / 10,800 B (+`hint`) | 812 of 812 (max rank 6) | 4,976 of 4,976 (max rank 10) | 19,360 of 19,360 (max rank 12) |
| `krk_v21` | 892 / 2,230 B | 1,312 of 1,312 (max rank 17) | 7,040 of 7,040 (max rank 26) | 25,440 of 25,440 (max rank 43) |

### Potential Ranking Audit (`audit-rank`)

| Program | Board | Entries | Mate-in-1 | 2-ply Steps | Decrease | Equal | Increase | Strict? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `kqk_v7` | 4x4 | 812 | 184 | 940 | 940 (100%) | 0 | 0 | **Yes** |
| `kqk_v7` | 5x5 | 4,976 | 464 | 7,748 | 7,748 (100%) | 0 | 0 | **Yes** |
| `kqk_v7` | 6x6 | 19,360 | 920 | 35,184 | 35,184 (100%) | 0 | 0 | **Yes** |
| `kqk_lia` (final) | 4x4 | 812 | 184 | 920 | 920 (100%) | 0 | 0 | **Yes** |
| `kqk_lia` (final) | 5x5 | 4,976 | 464 | 7,620 | 7,620 (100%) | 0 | 0 | **Yes** |
| `kqk_lia` (final) | 6x6 | 19,360 | 920 | 34,396 | 34,396 (100%) | 0 | 0 | **Yes** |
| `krk_v21` | 4x4 | 1,312 | 120 | 2,306 | 2,150 (93.2%) | 21 | 135 | No |
| `krk_v21` | 5x5 | 7,040 | 288 | 18,434 | 17,852 (96.8%) | 48 | 534 | No |
| `krk_v21` | 6x6 | 25,440 | 560 | 80,112 | 78,406 (97.9%) | 82 | 1,624 | No |

### Answers to Round 2 Questions

- **Did program length have to grow with the board?**
  **No.** A single board-size-parametric program of fixed length covers every board size from 4x4 through 8x8 (confirmed 1000/1000 on 4x4..8x8 ensembles and 100% of all valid positions on 4x4, 5x5, and 6x6): **793 AST nodes (1,747 B)** for KQK (`kqk_v7.py`) and **892 AST nodes (2,230 B)** for KRK (`krk_v21.py`). While flat certificates grow like `O((W*H)^3)`, program length stays constant, supporting Hypothesis H2 for 3-piece winning endgames. In Round 3, `kqk_lia.py` + `smt/kqk.py` goes further and proves winning termination for **every** `W >= 4, H >= 4` simultaneously.
- **Which ideas mattered most?**
  1. **2-ply minimax over a single lexicographic potential** (replacing procedural case trees): halved KQK AST size (1,741 → 754 nodes) while jumping from 97.1% to 100%, and cut KRK from 2,171 nodes (69.3%, illegal 3-ply) to 892 nodes (100%, legal 2-ply).
  2. **Single-axis 1D vertical strip for KRK** (`krk_v15..v21`): abandoning 2D boxes eliminated axis-flipping cycles between horizontal and vertical rook cuts on 5x5 and 6x6.
  3. **Phase separation on King arrival & corner cage in KRK**: herding `bf` only after `K` reaches the opposition rank `tr` (while keeping `R` safe/far during `K`'s approach), recognizing 2-wide corner mating cages (`eff_bh = min(bh, br_d + 1)`), and using a constant center rank `tr = h // 2` when `eff_bh >= h - 1` closed the last 0.3% of positions.
  4. **Reply-independent King targets & deterministic tie-breaking in KQK**: targeting `Q`'s square `(qf, qr)` (and `(2, nqr - 1)`/`(nqf - 1, 2)` on 1-wide strips, discovered by Z3 in Round 3) ensured `K`'s approach strictly decreases regardless of Black's reply.

---

## 2. Round 3: Symbolic Step (LIA Potential, Witness Rule, Z3 Proof)

### Chain Status Summary

Every link in the symbolic proof chain for **KQK on all boards `W >= 4, H >= 4`** completed and passed:

1. **LIA linter (`harness.py lint-lia`)**: Implemented & unit-tested. Rejects `kqk_v7.py` and `krk_v21.py`; accepts `strategies/kqk_lia.py` for both `_pot` and `hint` (`LIA_OK`).
2. **LIA potential (`strategies/kqk_lia.py`)**: Replaces `bw * bh` with `bw + bh` and the square-counting `fr` loop with closed-form LIA interval/offset formulas.
   - Length growth vs `kqk_v7.py` (793 nodes / 1,747 B):
     - Step 1 LIA `_pot` + `move` (scored 1000/1000 on `kqk`): **1,165 nodes / 2,774 B** (+372 nodes / +1,027 B, +46.9% nodes).
     - Z3-hardened final `_pot` + `move` subset: **1,477 nodes / 3,520 B** (+684 nodes / +1,773 B, +86.3% nodes; still under the 4,000 B `kqk` limit).
     - Full final `strategies/kqk_lia.py` (including pure-LIA `hint` + 8-reply witness evaluator): **5,309 nodes / 10,800 B**.
   - 100% whole-class `VALID` and **100% strict ranking** on 4x4, 5x5, and 6x6 (table above).
3. **Explicit LIA witness rule (`hint`) & `harness.py audit-hint`**: **ZERO violations** across all 25,148 valid positions on 4x4, 5x5, and 6x6:

| Board | Valid Positions | Mate-in-1 | Illegal | Stalemate | Q Captured | 2-ply Steps | Decrease | Equal | Increase | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4x4 | 812 | 100 | 0 | 0 | 0 | 1,216 | 1,216 (100%) | 0 | 0 | **0** |
| 5x5 | 4,976 | 132 | 0 | 0 | 0 | 10,946 | 10,946 (100%) | 0 | 0 | **0** |
| 6x6 | 19,360 | 152 | 0 | 0 | 0 | 56,364 | 56,364 (100%) | 0 | 0 | **0** |

4. **Z3 encoding validation (`smt/kqk.py --validate-encoding`)**: Verified exact agreement between the Z3 formulas (`z_valid_wtm`, all 8 `z_legal_black_reply` directions) and `../03-checker/rules.py` on every distinct non-adjacent-king placement of 4x4, 5x5, and 6x6 (plus Z3 `unsat` check that `z_valid_wtm` rejects all out-of-bounds, overlapping, and adjacent-king placements, and exact 812/812 match of `z_pot_lia == kqk_lia._pot_lia` and `z_legal_white_move` on 4x4):

| Board | Valid Z3 == Rules | States Checked | Valid Mismatches | Reply Direction Checks | Reply Mismatches | Time (s) |
|---|---:|---:|---:|---:|---:|---:|
| 4x4 | 812 / 812 | 2,184 | **0** | 17,472 | **0** | 1.70 |
| 5x5 | 4,976 / 4,976 | 10,488 | **0** | 83,904 | **0** | 10.39 |
| 6x6 | 19,360 / 19,360 | 35,360 | **0** | 282,880 | **0** | 32.10 |

5. **Z3 symbolic proof verdict (`smt/kqk.py --prove`) — `PROVEN_UNSAT` for all `W >= 4, H >= 4`**:
   - **Lower bound** (`Valid(s) /\ any(_pot_lia(s)[i] < 0)`): **`unsat`** (0.37s) — every component of the 10-tuple potential is `>= 0`, so lexicographic strict decrease implies termination on every `W >= 4, H >= 4`.
   - **Partition exhaustiveness** (`Valid(s) /\ not (or of 13 cases)`): **`unsat`** (0.03s).
   - **Main step theorem** (`Valid(s) /\ quadrant(fh, fv) /\ case_c /\ AND_i not Good(s, M_i(s))` over all 4 quadrants `00, 10, 01, 11` and all 13 cases = **52 obligations**, with NO assumed symmetry):
     - Quadrant `00`: **13/13 `unsat`** (77.23s total, 4 cores).
     - Quadrants `10, 01, 11`: **35/39 `unsat`** at 55s timeout (382.94s), and the remaining **4/4 `unsat`** at 150s timeout (`10:bh==2,bw==3` 84.45s, `01:bw==2,bh==3` 75.14s, `11:bw==2,bh>=4` 49.98s, `11:bh==2,bw==3` 50.59s; 85.09s total).
     - **Total across all 4 quadrants: 52/52 `unsat` (`PROVEN_UNSAT`), 0 `sat`, 0 `unknown`.**
   - Because `kqk_lia.move(pos)` returns mate-in-1 when available and otherwise minimizes `max_r _pot(p.m.r)` over all non-stalemating legal moves, proving `hint` strictly decreases `_pot` (or mates) simultaneously proves that both `hint` and 2-ply minimax `move` win from **every** valid White-to-move KQK position on **every** board `W >= 4, H >= 4`.

### Bugs Caught Only by Z3 (Invisible on 4x4..6x6 and 1000-Root 4x4..8x8)

Counterexample-guided refinement against Z3 uncovered four real bugs in the Round-2/Step-1 potential that passed 100% of all 25,148 positions on 4x4..6x6 and 1000/1000 roots on 4x4..8x8:
1. **`w=10, h=4, K=(1,2), Q=(5,1), k=(3,0)`**: constant King target `(1, 2)` stalled on wide 1-rank strips (`bw >= 5`); fixed to `(2, nqr - 1)` / `(nqf - 1, 2)`.
2. **`w=8, h=26, K=(5,10), Q=(6,10), k=(0,9)`**: `K` blocking `Q`'s rank/file seal adjacent to `k` allowed `k` to escape a supposedly sealed box; fixed via `v_brk` / `h_brk`.
3. **`w=12, h=4, K=(2,0), Q=(5,2), k=(4,0)`**: placing `k_edge` ahead of `(bw + bh, min(bw, bh))` prevented `Q` from shrinking `min(bw, bh)` from 2 to 1 when `K` sat on the edge while `K` stepping off stalemated; fixed by placing `k_edge` immediately after `min(bw, bh)`.
4. **`w=5, h=17, K=(0,3), Q=(2,6), k=(0,5)`** (and transpose `21x4`): a `2 x bh` (`bh >= 4`) stalemate trap where `K` near `(1, bh - 2)` traps `k` at `(0, bh - 1)` against `Q = (2, bh)`; fixed by adding `trap_2g` / `trap_g2` scoped to `nbr >= bh - 2` / `nbf >= bw - 2`.

---

## 3. What Would Be Needed for the Rook (`KRK`)

`krk_v21.py` already wins 100% of valid positions on 4x4, 5x5, and 6x6 and 1000/1000 on `krk`, and has no `bw * bh` or square loops. Four concrete steps are needed to lift it to a Z3 proof for all `W >= 4, H >= 4`:

1. **Remove variable-by-variable sign products (trivial LIA rewrite)**: `lint-lia` flags only 3 expressions in `krk_v21.py` (`(rr - br) * dr`, `(eff_bh + 1) * dr`, `(kr - (cr + eff_bh * dr)) * dr`). Normalizing `kr, rr, br` via vertical reflection `fv` (as done in `kqk_lia.py`) eliminates `dr` completely and passes `lint-lia`.
2. **Turn `_pot` into a strict 2-ply ranking (the real mathematical work)**: `krk_v21.py` has 534 increases and 48 ties on 5x5 (1,624 increases / 82 ties on 6x6) because:
   - *Rook fleeing & tempo waiting*: when `k` approaches `R` on the cut rank, `R` slides to the opposite side (temporarily keeping `eff_bh` and `bf` equal or increasing `r_dist_pen`), and when `K` is in knight's opposition `R` plays a 1-square waiting move along the cut rank. A strict LIA ranking must explicitly encode **opposition parity / tempo state** (e.g., direct opposition vs knight's opposition vs waiting-move phase, as in Marić–Janičić–Maliković's Isabelle/Z3 proof) and a **rook-side indicator** (left vs right of `k`, or safe-flee phase) so every rook flee and waiting move strictly lowers the phase/sub-rank.
   - *King-behind-rook unblocking*: `k_blocks_r` currently has local dips when `K` steps sideways to pass `R`.
3. **Explicit LIA witness rule `hint(pos)` for KRK**: Much smaller than KQK's candidate set once the potential is strict — on a 1D vertical strip, `hint` needs only ~8–10 symbolic Rook moves (check-push to `(rf, br)`, cut to `(rf, br + 1)`, flee to `(0, rr)` or `(w - 1, rr)`, waiting move `(rf ± 1, rr)`, corner-cage lift `(2, rr)` / `(w - 3, rr)`) plus the 8 King moves.
4. **Z3 encoding for KRK (`smt/krk.py`)**: Simpler than KQK (rook attacks only along files and ranks, no diagonals!), with the same `validate_encoding` check against `rules.py` on 4x4, 5x5, and 6x6 before trusting `unsat`.

---

## 4. Exact Reproduction Commands & Test Output

All commands run from `/home/dege/chess/07-strategies`:

```bash
# Unit tests (22 tests: harness, lookahead guard, expand-all, audit-rank, lint-lia, audit-hint)
python3 -m unittest discover -s tests -v

# LIA linter (rejects Round 2 programs, accepts kqk_lia _pot and hint)
python3 harness.py lint-lia strategies/kqk_v7.py
python3 harness.py lint-lia strategies/krk_v21.py
python3 harness.py lint-lia strategies/kqk_lia.py --fn _pot
python3 harness.py lint-lia strategies/kqk_lia.py --fn hint

# Witness audit across every valid position of 4x4, 5x5, 6x6 (0 violations on all three)
python3 harness.py audit-hint strategies/kqk_lia.py --material KQK --board 4x4 --jobs 4
python3 harness.py audit-hint strategies/kqk_lia.py --material KQK --board 5x5 --jobs 4
python3 harness.py audit-hint strategies/kqk_lia.py --material KQK --board 6x6 --jobs 4

# Whole-class union certificates + independent checker + strict audit-rank
python3 harness.py expand-all strategies/kqk_lia.py --material KQK --board 4x4 --out results/kqk_lia_4x4.cert --jobs 4
python3 harness.py audit-rank strategies/kqk_lia.py --cert results/kqk_lia_4x4.cert --jobs 4
python3 harness.py expand-all strategies/kqk_lia.py --material KQK --board 5x5 --out results/kqk_lia_5x5.cert --jobs 4
python3 harness.py audit-rank strategies/kqk_lia.py --cert results/kqk_lia_5x5.cert --jobs 4
python3 harness.py expand-all strategies/kqk_lia.py --material KQK --board 6x6 --out results/kqk_lia_6x6.cert --no-verify --jobs 4
../08-checker2/mcheck2 verify results/kqk_lia_6x6.cert
python3 harness.py audit-rank strategies/kqk_lia.py --cert results/kqk_lia_6x6.cert --jobs 4

# Z3 encoding validation against rules.py on 4x4, 5x5, 6x6 (0 mismatches)
python3 smt/kqk.py --validate-encoding --boards 4 5 6 --jobs 4

# Z3 symbolic proof for all W >= 4, H >= 4 (split by quadrant to stay well under 5 min/command)
python3 smt/kqk.py --prove --quadrants 00 --jobs 4 --timeout 90
python3 smt/kqk.py --prove --quadrants 10 --jobs 4 --timeout 120
python3 smt/kqk.py --prove --quadrants 01 --jobs 4 --timeout 120
python3 smt/kqk.py --prove --quadrants 11 --jobs 4 --timeout 120
```

Actual test output (`python3 -m unittest discover -s tests`): `Ran 22 tests in 1.125s — OK`.

---

## 5. Known Gaps, Spec Issues, and Open Questions

- **Spec issues**: None encountered in SPEC v1.2.
- **Byte-limit interaction with `hint`**: Adding `hint(pos)` (and its pure-LIA 8-reply evaluator) inside [strategies/kqk_lia.py](strategies/kqk_lia.py) raises the combined file size to 10,800 B, above the 4,000 B limit in `families/kqk.json` designed for `move`-only strategy programs. The `_pot` + `move` subset alone is 3,520 B (1,477 AST nodes), and Step 1 `kqk_lia.py` (`_pot` + `move`, 2,774 B) passed `harness.py score --family kqk` with 1000/1000. Open question for the lead: should `hint` live in a separate companion file or be excluded from the `move` family byte limit?
- **Python-to-Z3 correspondence**: `smt/kqk.py` mirrors `_pot_lia` and the candidate move list of `strategies/kqk_lia.py` by hand (verified for exact equality on all 812 positions of 4x4 with 0 mismatches, and `kqk_lia._hint_lia` tests a superset of every candidate in `smt/kqk.py`). Automatically compiling a single Python LIA AST into Z3 expressions would remove this small manual-translation trust boundary.
- **No tools installed**: Used only preinstalled Python 3.14 stdlib and Z3 4.16.0. No additional tools requested.
