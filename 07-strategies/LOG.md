# 07-strategies Experiment Log

All scored runs are recorded in [results/scores.tsv](results/scores.tsv). Lengths are reported in both **AST nodes** (`ast.walk` count after removing docstrings; official metric from round 2) and **stripped bytes** (UTF-8 bytes after removing comments, docstrings, and blank lines).

---

## Round 1 (reconstructed from `results/scores.tsv`, `strategies/`, and round-1 log)

### Family: `kk-draw` (100 roots across 4x4..8x8, `ATLEAST_DRAW stm`, limit 2000 B)

- **`strategies/kk_draw_v1.py`** — 17 nodes / 65 B
  - *Idea*: Return the lexicographically first legal move (`rules.legal_moves(pos)[0]`).
  - *Score*: **100/100** (100.0%), 16,126 entries, max rank 0, 248.09 entries/byte, expand 5.31s / verify 3.55s.
  - *Analysis*: Works on every bare-kings position because bare kings cannot be mated; lexicographical first move drifts toward `a1` by chance, giving modest orbits.

- **`strategies/kk_draw_v2.py`** — 203 nodes / 565 B
  - *Idea*: Maximize Chebyshev (then Manhattan) distance from the opponent king.
  - *Score*: **100/100** (100.0%), 88,814 entries, max rank 0, 157.19 entries/byte, expand 32.999s / verify 20.829s.
  - *Analysis*: Worse than v1 in both length and certificate size (5.5x more entries): fleeing the opponent king causes the prover king to visit all four corners across the board rather than staying in one small invariant set.

- **`strategies/kk_draw_v3.py`** — 99 nodes / 309 B
  - *Idea*: Anchor the prover king strictly to the `a1` corner (minimize `f2 + r2`, then `max(f2, r2)`).
  - *Score*: **100/100** (100.0%), 12,215 entries, max rank 0, 39.53 entries/byte, expand 4.567s / verify 2.918s.
  - *Analysis*: Reduces total certificate entries by 24% vs v1 (and 86% vs v2) because the prover king stays confined to `a1` (or adjacent squares when blocked), minimizing the reachable invariant set.

---

### Family: `mini4x4-start` (1 root: `rqkr/pppp/PPPP/RQKR w - -`, `WIN w`, limit 4000 B)

- **`strategies/mini4x4_v1.py`** — 230 nodes / 835 B
  - *Idea*: 1-ply greedy tactical heuristic (mate-in-1, else score checks + captures − reply count).
  - *Score*: **1/1**, 5 entries, max rank **4**, expand 0.003s / verify 0.001s.
  - *Analysis*: Confirms the `01-survey` report of a forced mate in 4 with a 5-entry `mcheck.py`-verified certificate (`results/mini4x4-start.cert`).

- **`strategies/mini4x4_v2.py`** — 350 nodes / 1174 B *(non-compliant with round-2 2-ply limit: calls `_mate_in_1` on ply-2 replies)*
  - *Idea*: Add mate-in-2 check (`_mate_in_1` on replies) and prefer low-value attackers.
  - *Score*: **1/1**, 5 entries, max rank 4. Longer than v1 for the same certificate.

- **`strategies/mini4x4_v3.py`** — 193 nodes / 832 B *(non-compliant with round-2 limit: recursive depth-4 AND-OR search)*
  - *Idea*: Recursive depth-bounded (up to 4 own moves) checking AND-OR search.
  - *Score*: **1/1**, 5 entries, max rank 4. Essentially a miniature solver, which motivated the round-2 lookahead ban.

- **`strategies/mini4x4_v4.py`** — 94 nodes / 314 B *(compliant: 1-ply check + reply count)*
  - *Idea*: Pick the checking move minimizing opponent legal replies (lexicographical tie-break).
  - *Score*: **1/1**, 5 entries, max rank 4, expand 0.003s / verify 0.001s.
  - *Analysis*: Cleanest, shortest proof for `mini4x4-start` (94 nodes / 314 B), confirming the forced mate in 4 without recursion or multi-ply search.

---

### Family: `kqk` (1000 roots: 200 each on 4x4..8x8, `WIN w`, limit 4000 B)

- **`strategies/kqk_v1.py`** — 513 nodes / 1738 B
  - *Idea*: 1-ply greedy queen box-area shrinking (`area < cur_area` without checking, never hanging Q); once `cur_area <= 2`, bring White king closer.
  - *Score*: **669/1000** (66.9%), 5,909 entries, max rank 17, compression 3.40 entries/byte, expand 33.19s / verify 1.42s.
  - *Why it failed*: Cycles (e.g., `4/3Q/1k2/3K w - -`, `1k2/4/4/Q1K1 w - -`, `3k/1Q2/K3/4 w - -`): a 1-ply rule cannot see Black's reply expanding the box back or chasing the queen, and lacks stalemate-cage avoidance and king-unblocking logic.

- **`strategies/kqk_v2.py`** — 1296 nodes / 3480 B *(round-1; uses `_mate1(rp)` 3-4 ply mate-in-2 check)*
  - *Idea*: Add mate-in-2 detection (`len(reps) <= 3`), strict queen box shrink keeping `free_squares >= 2` (avoiding stalemate cages), stalemate-cage escape, and walking White's king strictly closer to the quadrant corner `(cf, cr)`.
  - *Score*: **777/1000** (77.7%), 7,556 entries, max rank 13, compression 2.17 entries/byte, expand 216.25s / verify 1.58s.
  - *Why it failed*: Walking White's king directly toward the corner `(cf, cr)` traps White's king on the same edge as Black's king (blocking the queen's mating line), and 1-ply box shrinking still oscillates when Black steps to a square that changes the queen quadrant.

- **`strategies/kqk_v3.py`** — 1681 nodes / 3976 B *(round-1; uses `_mate1(rp)` 3-4 ply mate-in-2 check)*
  - *Idea*: Change White king's target to a non-edge mating square `(tf, tr)` two files/ranks off the corner; add edge-king unblocking and avoid trapping K on k's edge when shrinking.
  - *Score*: **971/1000** (97.1%), 15,858 entries, max rank 16, compression 3.99 entries/byte, expand 165.74s / verify 3.71s.
  - *Why it failed*: Only 29 failures remained, caused by edge cases where a queen move shrank the box by flipping quadrant/aspect ratio and then bounced back on the next turn (creating cycles), or where K needed to maneuver around Q.

- **`strategies/kqk_v4.py`** — 1741 nodes / 3753 B *(got WORSE: fell from 971/1000 to 556/1000; also note bytes fell via identifier shortening while AST nodes actually grew from 1681 to 1741)*
  - *Idea*: Enforce a strict-subset condition `sub()` on queen box shrinking (`(bw == w or ncf == cf) and (bh == h or ncr == cr) and nbw <= bw and nbh <= bh`), forbid any shrink leaving `K` on `k`'s edge, and add forced-shrink checks when every Black reply satisfies `sub()`.
  - *Score*: **556/1000** (55.6%), 2,510 entries, max rank 11, compression 0.67 entries/byte, expand 127.24s / verify 0.78s.
  - *Why it failed (regression analysis)*: `sub()` was overly restrictive. Whenever Black's king sat aligned with `Q` or shifted sides, `sub()` rejected valid queen box shrinks that changed the quadrant corner or aspect ratio (or momentarily placed `K` on the edge while shrinking). With queen shrinking blocked, White fell through to walking `K` toward `(tf, tr)` while Black stepped back and forth across a quadrant boundary, shifting `(tf, tr)` and producing King-oscillation cycles (e.g., `4/3Q/1k2/3K w - -` cycling between `4/2QK/k3/4` and `2K1/2Q1/4/1k2`).

- **`strategies/kqk_v5.py`** — 754 nodes / 1664 B *(compliant with round-2 2-ply limit)*
  - *Idea*: Abandon ad-hoc case trees completely. Define a single tuple potential `_pot(pos) = (0, k_edge, trap, area, min(bw, bh), kd_c, kd_m, k_bk)` (with `free` squares excluding White king attacks, discovered after a 99/100 quick test caught a 7x7 stalemate-trap bug) and pick the move minimizing `max(_pot(rp) for _, rp in replies)` (pure 2-ply minimax, returning immediate mate-in-1 and skipping stalemate).
  - *Score*: **1000/1000** (100.0%), 19,286 entries, max rank 16, compression 11.59 entries/byte (25.58 entries/node), expand 105.83s / verify 5.08s (re-verified by lead session: 1000/1000, 19,286 entries, max rank 16, expand 97.98s / verify 4.74s).
  - *Why it worked*: Minimax over a single potential automatically handles Black's best escape, prevents queen hanging (missing Q gets penalty `99`), avoids stalemate traps (`trap = 1 if fr < 2`), unblocks K from the edge (`k_edge`), shrinks the queen box (`area`, `min(bw, bh)`), and walks K to the mating square — in less than half the AST nodes of v3/v4.

---

### Family: `krk` (1000 roots: 200 each on 4x4..8x8, `WIN w`, limit 6000 B)

- **`strategies/krk_v1.py`** — 495 nodes / 1536 B
  - *Idea*: 1-ply greedy rook box-shrinking and king approach (avoid hanging rook and stalemate).
  - *Score*: **118/1000** (11.8%), 388 entries, max rank 10, compression 0.25 entries/byte, expand 15.03s / verify 0.11s.
  - *Why it failed*: Without opposition logic or waiting moves, White cannot drive Black's king back once the rook box stops shrinking, so almost all non-trivial roots cycle.

- **`strategies/krk_v2.py`** — 2094 nodes / 5738 B *(round-1; uses `_mate1(rp)`)*
  - *Idea*: Explicit procedural algorithm: emergency rook-hanging escape, direct opposition check push, strict rook cut shrink, corner-pinned waiting move, king walk toward opposition square.
  - *Score*: **367/1000** (36.7%), 2,760 entries, max rank 10, compression 0.48 entries/byte, expand 71.14s / verify 0.71s.
  - *Why it failed*: Only played a waiting move when `k` was pinned in a corner; in mid-board knight's opposition White chased `k` back and forth in cycles, and rook cuts adjacent to `k` got bounced.

- **`strategies/krk_v3.py`** — 2108 nodes / 5392 B *(round-1; uses `_mate1(rp)`)*
  - *Idea*: Generalize the rook waiting move to universal knight's opposition (`kf == tf` and `|kr - br| == 1`), tighten secondary box shrink to avoid bounces, and handle `bw == w-1` cuts.
  - *Score*: **416/1000** (41.6%), 5,688 entries, max rank 18, compression 1.05 entries/byte, expand 260.58s / verify 1.43s.
  - *Why it failed*: Procedural priority rules still interacted poorly in edge cases (king blocked behind rook, rook waiting square attacked by Black's king, switching cut axis between `bw` and `bh` causing cycles).

- **`strategies/krk_v4.py`** — 1388 nodes / 3120 B *(left unscored at end of round 1; compliant 2-ply)*
  - *Idea*: 2-ply minimax over 1D-strip potential plus an explicit knight's-opposition rook waiting-move override.
  - *Status*: To be scored in Round 2 Step 3.

- **`strategies/krk_v5.py`** — 2171 nodes / 4918 B *(left unscored at end of round 1; uses `_m1(rp)` 3-4 ply)*
  - *Idea*: Deterministic 1D-strip cut + opposition push + rook waiting move + far-cut slide.
  - *Status*: To be scored in Round 2 Step 3 (and flagged for round-2 lookahead limit).

- **`strategies/krk_v6.py`** — 1071 nodes / 2338 B *(left unscored at end of round 1; uses `_m1(rp)` 3-4 ply)*
  - *Idea*: 2-ply minimax over `Box-Shrink + King-Defends-Rook` potential plus corner mate-in-2 check.
  - *Status*: To be scored in Round 2 Step 3 (and flagged for round-2 lookahead limit).

---

## Round 2 (in progress)

*(Entries will be appended after each step and experiment.)*
