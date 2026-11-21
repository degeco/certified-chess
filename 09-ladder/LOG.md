# 09-ladder Experiment Log (Rung 3b: KPK)

All program lengths are measured in **AST nodes** (`ast.walk` after removing docstrings, via `../07-strategies/harness.py:measure_program_nodes`) and **stripped bytes**, counting only the rung code (`kpk/win.py` or `kpk/hold.py`, excluding lower rungs in `lib/`). Every certified recall is backed by a flat union certificate verified `VALID` by `../08-checker2/mcheck2` (and `../03-checker/mcheck.py` where noted).

---

## v1 — Textbook Baseline (Key Squares + Rule of the Square + Simple Rook Pawn)

- **`kpk/win.py` v1**: 953 AST nodes (2,641 B) [claims: 590 nodes, move-only: 358 nodes]
  - *Idea*: 0-ply `_is_win_w` (rule of the square, key squares 1 rank ahead for `rem <= 3` and 2 ranks ahead for `rem >= 4`, simple `kf == 1 and kr >= h - 2` rook-pawn check) wrapped in 2-ply `claims`; 2-ply minimax `move` handing over to `lib/kqk.py` on promotion.
- **`kpk/hold.py` v1**: 775 AST nodes (2,221 B) [claims: 487 nodes, move-only: 285 nodes]
  - *Idea*: 0-ply `_is_hold_b` (undefended pawn capture, rook-pawn corner rule, Black king in front of pawn while White king off key square) wrapped in 2-ply `claims`; 2-ply invariant-preserving `move` anchoring `k` to `a1` in bare `KK`.
- **5x5 `--all` (12,224 positions: 7,666 W_WIN, 4,558 DRAW; both `mcheck2` & `mcheck.py` VALID)**:
  - WIN: claims 6,926/7,666 (90.35%), **false claims 91**, **certified 6,793/7,666 (88.61%)**, union cert 6,371 entries (max rank 18).
  - HOLD: claims 3,724/4,558 (81.70%), **false claims 246**, **certified 1,793/4,558 (39.34%)**, union cert 1,798 entries (max rank 0).
- **Failure analysis**:
  1. `hold.py` v1 had a tuple-index bug (`best[2]` returned `-br` instead of `m = best[3]`), causing 1,396 illegal-move failures in expansion.
  2. `win.py` v1 had 91 false claims where `K` sat on a key square while `k` immediately captured the undefended pawn (`1K3/5/5/kP3/5 w - -`), and 740 missed wins (rook pawn shoulderings, king races to key squares, opposition).
  3. `hold.py` v1 missed 834 draws (rook pawn trapping `K` on file a, distant opposition, pawn-race draws) and had 246 false draw claims (rook pawn where White shoulders Black out or outruns Black).
