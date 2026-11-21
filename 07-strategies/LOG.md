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

## Round 2 (2-ply lookahead limit, AST-node length metric, whole-class union proofs, `audit-rank`)

Whole-class reference totals for White-to-move valid positions:
- **KQK**: 4x4 = **812**, 5x5 = **4,976**, 6x6 = **19,360**.
- **KRK**: 4x4 = **1,312**, 5x5 = **7,040**, 6x6 = **25,440**.

### Family: `kqk` (Round 2 refinement)

- **`strategies/kqk_v5.py`** — 754 nodes / 1,664 B *(compliant 2-ply)*
  - *Whole-class score*: 4x4 = **804/812** (8 uncovered, max rank 5), 5x5 = **4,964/4,976** (12 uncovered, max rank 8), 6x6 = **19,280/19,360** (80 uncovered, max rank 12). On 5x5 covered positions, `audit-rank` is strict (7,588/7,588 decrease).
  - *Why it missed a few whole-class positions*: On rare positions where the Black king stands between `K` and the mating square `(tf, tr)` (or symmetric `bw == bh` ties), `kqk_v5` entered short oscillations because `K` aimed at the corner mating square rather than `Q`'s square and did not break `bw == bh` symmetry deterministically.

- **`strategies/kqk_v6.py`** — 762 nodes / 1,686 B *(compliant 2-ply)*
  - *Idea*: When `bw > 1` and `bh > 1`, target `Q`'s square `(qf, qr)` instead of the corner so `k` cannot block `K`; break `bw` vs `bh` symmetry deterministically via `(area, min(bw, bh), bh, kd_c, kd_m, cf + cr)`.
  - *Whole-class score*: 4x4 = **812/812** (100%, max rank 7), 5x5 = **4,976/4,976** (100%, max rank 10).
  - *Why v7 was still needed*: Distance-1 ties around `Q` could still stall `audit-rank` monotonicity when `K` stepped around `Q` without moving onto `k`'s side along the shorter axis.

- **`strategies/kqk_v7.py`** — 793 nodes / 1,747 B *(compliant 2-ply)*
  - *Idea*: Add `k_ax` (distance from `K` to `k`'s edge along the shorter box axis) to break distance-1 ties around `Q`: `(0, k_edge, trap, area, min(bw, bh), bh, kd_c, kd_m, k_ax, cf + cr)`.
  - *Score*: **1000/1000** on `kqk` family (19,571 entries, max rank 17, 11.20 entries/B, 24.68 entries/node). Whole-class: **812/812** on 4x4 (max rank 6), **4,976/4,976** on 5x5 (max rank 10), **19,360/19,360** on 6x6 (max rank 13), all `VALID` (both checkers on 4x4/5x5; `mcheck2` on 6x6).
  - *`audit-rank`*: **Strict ranking on all three boards** — 4x4: 940/940 decrease; 5x5: 7,748/7,748 decrease; 6x6: 35,184/35,184 decrease (0 equal, 0 increase).

---

### Family: `krk` (Round 2: versions 4–21)

- **`strategies/krk_v4.py`** — 1,388 nodes / 3,120 B *(compliant 2-ply)*
  - *Idea*: 2-ply minimax over 1D-strip potential plus an explicit knight's-opposition rook waiting-move override.
  - *Score*: **295/1000** on `krk` (3,713 entries, max rank 18).
  - *Why it failed*: The hard-coded waiting-move override conflicted with the minimax potential (sometimes playing a waiting move into a worse strip or hanging the rook), causing cycles whenever `k` stepped sideways instead of retreating.

- **`strategies/krk_v5.py`** — 2,171 nodes / 4,918 B *(non-compliant legacy: ply-2 `_m1(rp)`)*
  - *Idea*: Procedural textbook 1D-strip cut + opposition push + rook waiting move + far-cut slide.
  - *Score*: **693/1000** on `krk` under `--allow-legacy-lookahead` (139,863 entries, max rank 36).
  - *Why it failed*: Violated the round-2 2-ply rule and still cycled on ~31% of roots in corner/king-behind-rook/cut-axis transition edge cases.

- **`strategies/krk_v6.py`** — 1,071 nodes / 2,338 B *(non-compliant legacy: ply-2 `_m1(rp)`)*
  - *Idea*: 2-ply minimax over `Box-Shrink + King-Defends-Rook` potential plus corner mate-in-2 check.
  - *Score*: **448/1000** on `krk` under `--allow-legacy-lookahead` (8,254 entries, max rank 12).
  - *Why it failed*: Violated the 2-ply rule and still lacked a clean mechanism to break knight's opposition without oscillating.

- **`strategies/krk_v7.py`** — 651 nodes / 1,496 B *(compliant 2-ply)*
  - *Idea*: Pure 2-ply minimax over a 1D-rank-herding tuple `(0, r_hang, bh, br_d, r_gap, k_side, k_rank, in_opp, herd, k_file, r_far)`.
  - *Whole-class score*: 4x4 = **590/1,312** (45.0%, max rank 7), 5x5 = **1,388/7,040** (19.7%, max rank 9).
  - *Why it failed*: Placing `r_hang` ahead of `bh` and including `br_d` / `r_gap` let Black's king attack the rook or bounce back and forth along the cut rank without allowing a tempo-gaining rook slide.

- **`strategies/krk_v8.py`** — 926 nodes / 1,928 B *(compliant 2-ply)*
  - *Idea*: Switch to a 2D-box + King-phalanx potential `(0, r_hang, k_edge, area, min(bw, bh), bh, kd_c, kd_m, k_ax, cf + cr)` modeled directly on `kqk_v7` (dropping Black-king distance terms).
  - *Whole-class score*: 4x4 = **368/1,312** (28.0%), 5x5 = **1,316/7,040** (18.7%), 6x6 = **1,850/25,440** (7.3%).
  - *Why it failed*: Unlike a Queen, a Rook cannot cut diagonally or deliver solo box shrinks; once `k` reached the edge (`min(bw, bh) == 1`), the 2D potential had no opposition/edge-squeeze mechanism to force mate.

- **`strategies/krk_v9.py`** — 1,153 nodes / 2,607 B *(compliant 2-ply)*
  - *Idea*: Split the 2D-box potential into Phase 1 (`m_dim >= 2`) and Phase 2 (`m_dim == 1`, edge-rank King arrival + corner mate-in-2 bonus `in_mate_k`).
  - *Whole-class score*: 4x4 = **444/1,312** (33.8%), 5x5 = **1,788/7,040** (25.4%), 6x6 = **2,508/25,440** (9.9%).
  - *Why it failed*: Still got stuck in Phase 1 box-shrink cycles (Black harassed the rook along the box boundary) and Phase 2 edge-squeeze ties.

- **`strategies/krk_v10.py`** — 1,247 nodes / 2,693 B *(compliant 2-ply)*
  - *Idea*: Add an explicit Phase 3 King+Rook 2x1 corner mating cage (when `bw == 2` on edge rank or `bh == 2` on edge file) and tighten Phase 2 edge squeeze with tie-breakers (`abs(bf - cf)` / `abs(br - cr)`).
  - *Whole-class score*: 4x4 = **1,312/1,312** (**100%**, max rank 10), 5x5 = **6,880/7,040** (97.7%, max rank 15), 6x6 = **12,708/25,440** (50.0%, max rank 14).
  - *Why it failed on 5x5/6x6*: On larger boards, Phase 1 (`area` + King-phalanx) cycled when Black attacked the rook during box transitions, and switching between horizontal and vertical cut axes created axis-flipping cycles.

- **`strategies/krk_v11.py`** — 1,271 nodes / 2,733 B *(compliant 2-ply)*
  - *Idea*: Reorder Phase 1/2 to prioritize `area` before `r_hang` (so White accepts temporary rook threats if a shrink is forced) and add `bk_c` tie-break.
  - *Whole-class score*: 4x4 = **1,312/1,312** (100%, max rank 9), 5x5 = **5,496/7,040** (78.1%), 6x6 = **10,284/25,440** (40.4%).
  - *Why it failed*: Regression vs v10: deprioritizing `r_hang` caused White to step into rook-harassment loops where `k` chased `R` back and forth across a shrink line.

- **`strategies/krk_v12.py`** — 1,199 nodes / 2,617 B *(compliant 2-ply)*
  - *Idea*: Restore `r_hang` in Phase 2, refine King-defense of the exact shrink square in Phase 1, and drop `bk_c`.
  - *Whole-class score*: 4x4 = **1,312/1,312** (100%, max rank 10), 5x5 = **6,820/7,040** (96.9%), 6x6 = **18,588/25,440** (73.1%, max rank 18).
  - *Why it failed*: Major gain on 6x6 (+5,880 positions over v10), but 2D box axis flips between `bw` and `bh` still produced cycles in the middle of the 6x6 board.

- **`strategies/krk_v13.py`** — 1,194 nodes / 2,673 B *(compliant 2-ply)*
  - *Idea*: In Phase 1, prioritize `m_dim` -> `axis` -> `k_line_d` -> `r_hang` -> `area` to commit to shrinking the shorter dimension first.
  - *Whole-class score*: 4x4 = **1,312/1,312** (100%, max rank 9), 5x5 = **6,180/7,040** (87.8%), 6x6 = **13,744/25,440** (54.0%).
  - *Why it failed*: Regression vs v12: locking `axis` inside a 2D box still allowed `k` to jump across `R`'s file/rank and invert `m_dim` / `axis`.

- **`strategies/krk_v14.py`** — 1,092 nodes / 2,457 B *(compliant 2-ply)*
  - *Idea*: Unify Phase 1 and Phase 2 so `K` always targets `rr + dr` (behind `R`'s cut line), merging the two phases into one tuple.
  - *Whole-class score*: 4x4 = **1,224/1,312** (93.3%), 5x5 = **5,608/7,040** (79.7%), 6x6 = **11,976/25,440** (47.1%).
  - *Why it failed*: Unifying within a 2D box still allowed horizontal/vertical axis flips, and lost 4x4 completeness because `k_in_box` occasionally blocked a 1-rank shrink.

- **`strategies/krk_v15.py`** — 794 nodes / 1,885 B *(compliant 2-ply)*
  - *Idea*: **Major architectural pivot** — abandon 2D boxes completely and return to a pure **1D vertical strip** (`eff_bh` with corner-cage reduction, `push_ready` for opposition check-shrink, and fixed left-herding `bf -> 0` with `K` at `tf = min(w-2, bf+1)`). Never flip to horizontal cuts, eliminating all axis-flipping cycles.
  - *Whole-class score*: 4x4 = **890/1,312** (67.8%), 5x5 = **3,186/7,040** (45.3%), 6x6 = **7,640/25,440** (30.0%).
  - *Why it failed*: Three specific bugs: (1) `K` walking behind `R` could block `R` from sliding past `K`; (2) `push_ready` didn't recognize when `k` already retreated (`br_d < eff_bh - 1`); (3) `br_d` in the tuple blocked waiting moves.

- **`strategies/krk_v16.py`** — 830 nodes / 1,981 B *(compliant 2-ply)*
  - *Idea*: Add `k_blocks_r` penalty (when `K` lies horizontally between `R` and `k` on the wrong side) and place `r_far` before `bf`.
  - *Whole-class score*: 4x4 = **772/1,312** (58.8%), 5x5 = **2,544/7,040** (36.1%), 6x6 = **7,448/25,440** (29.3%).
  - *Why it failed*: Putting `r_far` ahead of `bf` prevented White from herding `k` left when `R` was close, and `push_ready` still missed free retreats.

- **`strategies/krk_v17.py`** — 852 nodes / 2,097 B *(compliant 2-ply)*
  - *Idea*: Extend `push_ready` to fire whenever `r_far == 0` AND `eff_bh < h and br_d < eff_bh - 1` (i.e. `k` stepped away from the cut rank so `R` can immediately tighten the strip next move), and move `r_far` back behind `k_file_d`.
  - *Whole-class score*: 4x4 = **1,312/1,312** (**100%**, max rank 18), 5x5 = **6,726/7,040** (95.5%, max rank 22), 6x6 = **16,766/25,440** (65.9%, max rank 28).
  - *Why it failed on 5x5/6x6*: Huge jump (+4,182 on 5x5, +9,318 on 6x6), but keeping `br_d` in the tuple still prevented necessary Rook waiting moves along the cut rank.

- **`strategies/krk_v18.py`** — 849 nodes / 2,087 B *(compliant 2-ply)*
  - *Idea*: Remove the redundant `br_d` term from the tuple so `R` can freely make tempo/waiting moves without fearing `k` stepping closer to the cut rank.
  - *Whole-class score*: 4x4 = **1,312/1,312** (100%, max rank 18), 5x5 = **6,904/7,040** (98.1%, max rank 24), 6x6 = **17,334/25,440** (68.1%, max rank 29).
  - *Why it failed on 5x5/6x6*: With `r_hang` ahead of `bf`, Black could chase `R` back and forth along the cut rank and undo left-herding progress.

- **`strategies/krk_v19.py`** — 849 nodes / 2,087 B *(compliant 2-ply)*
  - *Idea*: Move `bf` and `k_file_d` ahead of `r_hang` so White prioritizes herding `k` left even when `k` threatens `R` (since 2-ply minimax already sees `R` capture as penalty `99`).
  - *Whole-class score*: 4x4 = **1,290/1,312** (98.3%), 5x5 = **6,693/7,040** (95.1%), 6x6 = **24,546/25,440** (**96.5%**, max rank 43).
  - *Why it failed*: Massive jump on 6x6 (+7,212 positions!), but herding `bf` while `K` was still approaching the opposition rank `tr` let `k` chase `R` before `K` arrived.

- **`strategies/krk_v20.py`** — 881 nodes / 2,209 B *(compliant 2-ply)*
  - *Idea*: Split the return tuple on `k_side == 0 and k_rank_d == 0`: only herd `bf` once `K` has reached the opposition rank `tr`; while `K` is approaching `tr`, keep `R` safe and far (`r_hang, r_far, r_dist_pen`) so `k` cannot harass `R`. For `eff_bh >= h - 1`, set `tr = br - dr`.
  - *Whole-class score*: 4x4 = **1,308/1,312** (99.7%, only 4 uncovered), 5x5 = **7,040/7,040** (**100%**, max rank 28), 6x6 = **25,392/25,440** (99.8%, only 48 uncovered).
  - *Why it missed the last 4 on 4x4 and 48 on 6x6*: Two tiny edge cases: (1) `k_blocks_r` fired even when `K` was far from `R`'s rank, interfering with `K`'s approach; (2) `tr = br - dr` when `eff_bh >= h - 1` moved with `k`, causing a rare oscillation on `eff_bh >= h - 1` positions.

- **`strategies/krk_v21.py`** — 892 nodes / 2,230 B *(compliant 2-ply)*
  - *Idea*: Restrict `k_blocks_r` to `abs(kr - rr) <= 1` (put `r_hang` before `k_blocks_r`), and use a constant center target `tr = h // 2` when `eff_bh >= h - 1` so `k` cannot shift `K`'s target rank.
  - *Score*: **1000/1000** on `krk` family (433,400 entries, max rank 68, 194.35 entries/B, 485.87 entries/node). Whole-class: **1,312/1,312** on 4x4 (max rank 17), **7,040/7,040** on 5x5 (max rank 26), **25,440/25,440** on 6x6 (max rank 43), all `VALID` (both checkers on 4x4/5x5; `mcheck2` on 6x6).
  - *`audit-rank`*: **Not a strict ranking** — 4x4: 2,150 dec / 21 eq / 135 inc (2,306 steps); 5x5: 17,852 dec / 48 eq / 534 inc (18,434 steps); 6x6: 78,406 dec / 82 eq / 1,624 inc (80,112 steps). The program still closes globally without cycles because non-decreasing steps enter configurations (such as rook fleeing or tempo waiting) that strictly decrease 1–2 moves later, but `_pot` itself is not yet a Lyapunov certificate.

---

## Round 3 (LIA potential, witness rule, and Z3 proof for all `W >= 4, H >= 4`)

### Step 1: LIA Linter (`harness.py lint-lia`) and `strategies/kqk_lia.py` (v1)

- Implemented `harness.py lint-lia <program> [--fn _pot]` checking AST compliance with Linear Integer Arithmetic (rejecting `var * var`, loops/comprehensions/`sum`, division/modulo by variables, and `rules` move generation; allowing `+`, `-`, comparisons, `min`, `max`, `abs`, constant-scaled multiplication, floor-div/mod by a non-zero integer constant, `if`/`else`, tuples, and board-index coordinate extraction).
- Confirmed rejection of Round 2 programs: `kqk_v7.py` fails on `bw * bh` and `sum(1 for f in range(...) ...)`; `krk_v21.py` fails on `(rr - br) * dr`, `(eff_bh + 1) * dr`, and `(kr - (cr + eff_bh * dr)) * dr`.
- **v1 (`strategies/kqk_lia.py`, `_pot` + `move` only, 1,165 AST nodes / 2,774 B)**:
  - *Idea*: Replace `area = bw * bh` with half-perimeter `bw + bh` (with `(bw + bh, min(bw, bh))`), and replace the `fr` loop with closed-form LIA interval arithmetic (`_sfree` for 1-wide strips; constant-offset `_far` checks for 2x2, 2x3, 3x2 boxes).
  - *Results*: `lint-lia` `LIA_OK`; `kqk` 1000-root score **1000/1000** (19,798 entries, max rank 17, 16.99 entries/node); whole-class **812/812** on 4x4 (`mcheck` VALID, 940/940 strict), **4,976/4,976** on 5x5 (`mcheck` VALID, 7,740/7,740 strict), **19,360/19,360** on 6x6 (`mcheck2` VALID, 34,904/34,904 strict).

### Steps 2 & 3: Witness Rule (`hint`), `audit-hint`, and Z3 Counterexample-Guided Refinement (`smt/kqk.py`)

- Implemented `harness.py audit-hint <program> --material <M> --board <WxH>` verifying over every valid position that `hint` is legal, never stalemates, and either mates in 1 or strictly decreases `_pot` on every legal Black reply.
- Built `smt/kqk.py` encoding SPEC v1.2 position validity, White move legality, all 8 Black king replies (including capturing an undefended Queen), `_pot_lia`, and an explicit finite list of symbolic LIA candidate moves (no board loops).
- **Counterexamples discovered by Z3 for arbitrary `W >= 4, H >= 4` (all invisible on 4x4..6x6 and 1000-root 4x4..8x8)**:
  1. `w=10, h=4, K=(1,2), Q=(5,1), k=(3,0)`: With `bh == 1` and constant King target `(1, 2)`, `K` stalled at `(1, 2)` while `Q` at `(5, 1)` could neither shrink to `(4, 1)` (undefended) nor flip without expanding `bw` from `5` to `7`. **Fix**: change King target on 1-wide strips from constant `(2, 1)`/`(1, 2)` to `(2, nqr - 1)`/`(nqf - 1, 2)` (still independent of `k`'s reply, so `K` walks beside `Q` to support the shrink/mate on arbitrarily wide boards).
  2. `w=8, h=26, K=(5,10), Q=(6,10), k=(0,9)`: `K` stood on `Q`'s rank `10` blocking `Q`'s horizontal cut, so `k` could step onto rank `10`, yet `_pot_lia` treated `bh = 10` as already sealed. **Fix**: add `v_brk` and `h_brk` (when `K` breaks `Q`'s seal adjacent to `k`, treat that box dimension as unsealed `w` or `h`).
  3. `w=12, h=11, K=(0,2), Q=(2,5), k=(0,4)` and transpose `w=17, h=14, K=(5,0), Q=(8,2), k=(7,0)`: needed 1-square diagonal Queen moves `(nqf - 1, nqr + 1)` and `(nqf + 1, nqr - 1)` keeping `bw + bh` constant while dropping `min(bw, bh)` from `2` to `1`.
  4. `w=16, h=10, K=(5,9), Q=(9,9), k=(7,8)`: needed edge-flip Queen moves `(nqf, nbr - 1)` and `(nbf - 1, nqr)` when `k` is near the far board edge.
  5. `w=12, h=4, K=(2,0), Q=(5,2), k=(4,0)`: `k_edge` ahead of `bw + bh` blocked `Q -> (6, 1)` from dropping `min(bw, bh)` from `2` to `1` whenever `K` happened to sit on rank `0`, leaving no decreasing move because `K -> (2, 1)` stalemated. **Fix**: order `k_edge` immediately after `(bw + bh, min(bw, bh))`.
  6. `w=34, h=15, K=(16,5), Q=(17,6), k=(0,5)`: `v_brk`/`h_brk` must require `nbf == nqf - 1` (resp. `nbr == nqr - 1`), otherwise a distant `K` on file `nqf` falsely unsealed a box `k` could not reach.
  7. `w=5, h=17, K=(0,3), Q=(2,6), k=(0,5)` and transpose `w=21, h=4, K=(6,0), Q=(9,2), k=(8,0)`: a genuine stalemate-trap pattern on `2 x bh` (`bh >= 4`) strips where `K` near `(1, bh - 2)` traps `k` at `(0, bh - 1)` against `Q = (2, bh)`. **Fix**: add `trap_2g` / `trap_g2` (scoped to `nbr >= bh - 2` / `nbf >= bw - 2`, which Z3 confirmed is invariant under Black replies after fixing counterexamples `w=24, h=28` and `w=8, h=4`).
- **Final `strategies/kqk_lia.py`** (1,477 AST nodes / 3,520 B for `_pot` + `move`; 5,309 AST nodes / 10,800 B including LIA `hint` + witness verifier):
  - `lint-lia` `LIA_OK` on both `_pot` and `hint`.
  - `audit-hint`: **0 violations** on 4x4 (812 pos, 1,216 steps), 5x5 (4,976 pos, 10,946 steps), and 6x6 (19,360 pos, 56,364 steps).
  - Whole-class `expand-all` + `audit-rank`: **812/812** on 4x4 (920/920 strict, `mcheck` VALID), **4,976/4,976** on 5x5 (7,620/7,620 strict, `mcheck` VALID), **19,360/19,360** on 6x6 (34,396/34,396 strict, `mcheck2` VALID).
  - Z3 encoding validation on 4x4, 5x5, 6x6: **0 mismatches** across 48,032 states and 384,256 Black-reply direction checks.
  - Z3 symbolic proof for all `W >= 4, H >= 4`: lower bound `unsat` (0.37s), 13-case partition exhaustiveness `unsat` (0.03s), and **all 52/52 `(quadrant, case)` obligations across all 4 quadrants (`00`, `10`, `01`, `11`) returned `unsat` (`PROVEN_UNSAT`)** — quadrant `00`: 13/13 `unsat` (77.23s); quadrants `10, 01, 11`: 35/39 `unsat` at 55s cap + remaining 4/4 `unsat` at 150s cap (85.09s). Zero `sat`, zero `unknown`.
