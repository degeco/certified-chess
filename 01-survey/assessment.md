# Research Assessment: Toward Solving Chess

*(Source status for every claim is tracked in [sources.md](file:///home/dege/chess/01-survey/sources.md); small-board variants and `SPEC.md` start positions are detailed in [small-boards.md](file:///home/dege/chess/01-survey/small-boards.md). Published results, secondary citations, and conjecture are separated explicitly.)*

---

## 1. What Solving Chess Formally Requires

In Victor Allis's taxonomy (Allis, 1994), solving a two-player, zero-sum, finite, perfect-information game has three formal tiers:

1. **Ultra-weak solution:** Prove the game-theoretic value of the start position under perfect play, possibly non-constructively (e.g., strategy stealing in Hex, or Shannon's 1950 observation that chess *with a pass move* cannot lose for White). Yields no playable strategy.
2. **Weak solution:** Prove the initial position's value *and* provide an explicit strategy guaranteeing at least that outcome from the start position with reasonable compute. Checkers, Connect Four (1988), Gardner 5×5, Losing Chess, and 8×8 Othello are weakly solved.
3. **Strong solution:** Provide a strategy yielding optimal play from **every legal position**, even after arbitrary blunders. Nine Men's Morris, Awari, Connect Four (2025 BDD table), 3×3/3×4 chess, and chess endgames up to 7 pieces are strongly solved. (Gévay & Danner, 2016/2026 also define *ultra-strong* solutions that maximize wins against fallible opponents.)

### Rules Ambiguity and FIDE Edge Cases
Chess's value depends on draw rules:
- **Infinite play vs. 50/75-move rules:** Without move-counting draw rules, chess is a finite state graph where infinite play is a draw; `SPEC.md` and most tablebase work (Lomonosov DTM, Kryukov 3×4/4×4) adopt this idealised game. Under FIDE rules, the **50-move claim** (and mandatory **75-move** rule) converts long forced mates—including 7-piece positions up to **549 moves** (`UNVERIFIED` primary) and 8-piece DTC wins of **584 moves** (`UNVERIFIED` primary)—into draws ("cursed wins").
- **Threefold repetition (GHI problem):** Under FIDE repetition rules, a position's value depends on move history, causing the Graph-History Interaction bug when caching transpositions (Kishimoto et al., 2012). Note that an acyclic `WIN` certificate with strictly decreasing rank is automatically immune to repetition draws.

### What Counts as a Checkable Proof
Large searches ($10^{13}$–$10^{18}$ nodes) cannot be audited manually and suffer from software or hardware faults (e.g., Watkins' 2016 Losing Chess proof had a double-*en-passant* bug in five 4-unit tablebases affecting 40 proof positions, fixed in 2019). A credible proof requires **untrusted proof generation decoupled from a small, independent checker**:
- For **weak solutions**, a finite acyclic strategy DAG (`WIN`) or closed invariant strategy graph (`ATLEAST_DRAW`) verified entry-by-entry against independent rules.
- For **strong solutions / tablebases**, independent retrograde re-generation (e.g., Nebe on 3×4 chess), structural verification like Pavlov's (2026) **Capture-Quiet Decomposition (CQD)**—which breaks the "all-draw fixpoint" trap by anchoring captures to verified $(N-1)$-piece submodels—or **machine-checked proofs** in HOL4/Coq/Lean (Hurd, 2005; Marzion, 2023).

---

## 2. Strongest Relevant Methods and Results as of Today

### Size of Standard Chess (Verified)
- **Game-tree complexity:** Shannon (1950) gave a lower bound of **$10^{120}$** variations; Allis (1994) estimated **$10^{123}$** (branching factor $\approx 35$, length $\approx 80$ ply).
- **Legal positions:** Tromp & Österlund (2021–2022) proved an upper bound of **$8.727 \times 10^{45}$** *urpositions* (improving on Allis's $5 \times 10^{52}$ and Chinchalkar's $1.78 \times 10^{46}$) and estimated **$(4.822 \pm 0.028) \times 10^{44}$** legal positions (95% CI, $n=2\times 10^6$). Deciding reachability or helpmate on $n \times n$ chess is **PSPACE-complete** (Brunner et al., 2020); deciding optimal play without polynomial move limits is **EXPTIME-complete** (Fraenkel & Lichtenstein, 1981, secondary; Storer, 1983 for polynomial-$k$ PSPACE-completeness).

### Solved Games Benchmark
- **Connect Four (7×6):** $4.53 \times 10^{12}$ states; 1st-player win via knowledge rules (Allen, Allis 1988) and Tromp's 1995 8-ply DB (`VERIFIED`). Böck (2025) strongly solved 7×6 as an **89.6 GB** BDD lookup table in **47 h** on 1 core (128 GB RAM), matching prior counts (`VERIFIED`).
- **Nine Men's Morris:** $\sim 10^{10}$ states (16× symmetry); draw via retrograde + 18-ply $\alpha\beta$ with separate verifier (Gasser, 1996, `UNVERIFIED` primary). Gévay & Danner (2016/2026) computed extended strong solutions (27B/284B states) and proved Morabaraba is a 1st-player win in 49 moves (`VERIFIED`).
- **Awari (grand slam):** $8.89 \times 10^{11}$ states; strongly solved as draw via parallel retrograde on 144 CPUs, 72 GB RAM, ~51 h (Romein & Bal, 2003, `UNVERIFIED` primary).
- **Checkers (8×8):** $\sim 5 \times 10^{20}$ states; weakly solved as draw via **$3.9 \times 10^{13}$** $\le 10$-piece DB (`VERIFIED` secondary) + PN/$\alpha\beta$ over 18 yrs on 50–200 PCs; ~223K minimal proof tree (Schaeffer et al., 2007, `UNVERIFIED` primary).
- **Hex (8×8–10×10):** 8×8 ($\sim 10^{27}$ $\le$half-full states) all openings solved in <2 weeks (slowest `a7`: 95.6 h) using DFPN + ICE + VCE + decompositions, explicitly *without* an independent verifier (Henderson et al., 2009, `VERIFIED`). 9×9 (hardest 111 days) and one 10×10 opening (63 days) solved via SPDFPN (Pawlewicz & Hayward, 2013, `UNVERIFIED` primary).
- **Losing Chess (8×8):** Weakly solved as White win (`1. e3`) under joint FICS/International rules via modified PN² + 4/6-unit TBs on up to 128 cores; proof graph has **863,301,867 nodes** + 66,187,848 transpositions (~5 GB raw; Watkins, 2016–2020, `VERIFIED`).
- **Othello (8×8):** $\sim 10^{28}$ positions / $10^{58}$ games; weakly solved as draw via modified Edax $\alpha\beta$ splitting at 50 and 36 empty squares (**1.505B** subproblems, **$1.526 \times 10^{18}$** nodes on MN-J cluster with ECC memory; Takizawa, 2023/2024, `VERIFIED`). Code/data are public; no full third-party re-run yet.
- **Gardner 5×5 Minichess:** $\sim 9 \times 10^{18}$ positions; weakly solved as draw under AISE rules via laptop-scale asymmetric human-readable oracles + modified Stockfish mate proofs (Mhalla & Prost, 2013, `VERIFIED`).

### Endgame Tablebases & Verification
- **7-piece status:** Lomonosov 7-piece DTM (~**140 TB**, 2012, `UNVERIFIED` primary); Guo & de Man completed 7-piece **Syzygy** WDL+DTZ in Aug 2018 covering **$4.238 \times 10^{14}$** positions in **16.7 TiB (18.4 TB)** using $\ge 1$ TB RAM over 5 months (>$90K hardware, `VERIFIED` via CPW/Wikipedia).
- **8-piece progress:** Full 8-piece space has **$3.818 \times 10^{16}$** positions (~90× larger), estimated at **~2 PB** Syzygy and 64 TB RAM (`VERIFIED` in CPW/Wikipedia). Partial **Op1** 8-piece DTC (Bourzutschky & Fiekas, Lichess 2025/2026) covers ~$5 \times 10^{14}$ positions (1.3%) in **68.8 TB** (`UNVERIFIED` primary).
- **Structural & Formal Verification:** *Setrograde analysis* (Stone et al., 2024) collapses states into value-equivalent sets, solving 24-card Bridge ($8 \times 10^{14}$ reduced states) in 50 GiB with $10^3\times$ fewer ops (`VERIFIED`). *CQD* (Pavlov, 2026) anchors captures to $(N-1)$-piece submodels, cutting retrograde work by 19% (4-pc) to est. 60–80% (20-pc) and validating all 517 3–6 piece endgames (`VERIFIED`). Hurd (2005/2010) verified 4-piece pawnless TBs in HOL4+BDDs (`VERIFIED` secondary); Marić et al. (2015) verified KRK in Isabelle/HOL+Z3 (`UNVERIFIED` primary); Marzion (2023) built a coinductive TB generator in Coq (`VERIFIED`).

### AI-Assisted Proof Search & Top Engines
- **AI + Formal Kernels:** AlphaGeometry / AG2 (Trinh et al., 2024; Chervonyi et al., 2025) paired symbolic deduction with neural auxiliary constructions (84% on 25 yrs IMO geometry, `VERIFIED`). **AlphaProof** (Hubert et al., 2025/2026) combined a 3B transformer with AlphaZero AND-OR tree search and Test-Time RL inside **Lean**, solving 3/5 non-geometry IMO 2024 problems (80,000 TPU-days RL, `VERIFIED`). Lean's kernel acts as an untrusted-solver referee—the exact analogue of a trusted game certificate checker.
- **Top engines:** Stockfish NNUE and Lc0 score near-100% draws from startpos (forcing biased TCEC books; `UNVERIFIED` exact stats), and 6-man Syzygy adds only **2.7 Elo** to Stockfish 15 NNUE (`VERIFIED` in CPW). Yet engine evals are **heuristics, not proofs**: Mhalla & Prost (2013) found Gardner 5×5 positions where Stockfish gave **+6.00** despite being forced **draws** by blockade (`VERIFIED`).

---

## 3. Main Obstacles and Computational Constraints

1. **The 25-order-of-magnitude gap:** Standard chess ($\sim 4.82 \times 10^{44}$ positions) is **$10^{16}\times$ larger** than Othello ($\sim 10^{28}$) and **$10^{24}\times$ larger** than Checkers ($\sim 5 \times 10^{20}$). Adding one piece multiplies tablebase size ~50–100×; full retrograde beyond ~9–10 pieces is physically infeasible (20-piece space is $\sim 10^{18}$ *per material class*, Pavlov 2026).
2. **Slow convergence and reversible quiet subgraphs:** Unlike sudden-death games (Hex, Connect Four), chess has high mobility, slow material reduction, and deep quiet cycles (Allis, 1994), with forced mates already reaching 549 moves at 7 pieces.
3. **Branching in draw proofs:** Proving `ATLEAST_DRAW` requires covering all non-losing opponent replies for *both* sides. Without **fortress/blockade predicates** or **set-based equivalence classes**, explicit FEN certificates cannot collapse middlegame transpositions.
4. **Verification cost:** Re-running a $10^{18}$-node $\alpha\beta$ search is unaffordable for third parties, while flat move-level certificates would exceed exabyte scale without structural/submodel compression.

---

## 4. Ranked Shortlist of Research Directions

1. **Rank 1 — Set-Based & Structural Proof Compression (Setrograde + CQD + Fortress Invariants):**
   *Why:* Only reasoning over **position sets** (Stone et al., 2024; Pavlov, 2026; Mhalla & Prost's blockade lemmas) can beat raw state-space scaling. In `ATLEAST_DRAW`, a small invariant over an abstract predicate (e.g., locked pawns + king confinement) certifies vast subgraphs at once.
   *Uncertainties:* Chess piece geometry resists uniform rank symmetries like Bridge; finding sound, compactly checkable set abstractions for middlegames is unsolved.
2. **Rank 2 — RL/Neural Guidance inside an Untrusted-Solver / Trusted-Checker Loop (AlphaProof Paradigm):**
   *Why:* Pure PN/$\alpha\beta$ search stalls in high-mobility "wells" (Watkins, 2016). Learned policy/value guidance over AND-OR proof search (df-pn / PN²), checked by a trusted verifier, can find shorter winning/fortress lines without risking soundness.
   *Uncertainties:* High training cost; learned heuristics compress *prover* choices but not *opponent* branching unless paired with dominance/set abstractions.
3. **Rank 3 — Hybrid CQD-Verified Bottom-Up Anchoring + Top-Down Parallel SPDFPN:**
   *Why:* Every large game solve combined bottom-up tablebases with top-down search. Formalizing CQD capture boundaries lets top-down certificates terminate cleanly at verified submodels.
   *Uncertainties:* Bridging ~8-piece tablebases to 32-piece openings still leaves ~24 captures of depth.
4. **Rank 4 — Symbolic BDDs / SAT for Small Boards and Endgames:**
   *Why:* Böck (2025) fit $4.53 \times 10^{12}$ Connect Four states into 89.6 GB BDDs on 1 core, showing symbolic methods can work on consumer RAM for $3\times 4$ or $4\times 4$ chess.
   *Uncertainties:* Naive BDD sizes scale exponentially in board width/height (Edelkamp & Kissmann, 2011), and sliding pieces/promotions create dense transition relations.

---

## 5. Critique of `../design/SPEC.md`

### Is the proposed first experiment sound?
**Mostly sound, with three specification gaps:**
1. **Certificate soundness:** `WIN` enforces strictly decreasing integer rank `d` on a finite entry table, forbidding cycles and ensuring mate; `ATLEAST_DRAW` enforces closure under all opponent replies (vacuously satisfied on mate or stalemate), which is sound under "infinite play is a draw". *Gap:* `SPEC.md` does not explicitly enforce non-negative ranks in `WIN` or verify `#root` legality / entry reachability from `#root` (unreachable entries do not break soundness, but distort size metrics).
2. **8×8 *en passant* edge case:** Setting `ep` iff a *legal* *en passant* capture exists includes horizontal-pin checks where capturing exposes the king on rank 4/5. `02-engine` and `03-checker` must explicitly cross-test this.
3. **FIDE transferability:** `SPEC.md` rightly flags the omitted 50-move rule. Note that **3-fold repetition** does *not* invalidate `WIN` certificates (acyclic ranks), and FIDE draws preserve `ATLEAST_DRAW`.

### Has this experiment already been done?
**Not in this cross-board certificate-scaling form.** Kryukov strongly solved 3×3 ($5.5 \times 10^7$ NULP), 3×4 ($1.67 \times 10^{11}$ NULP), and 2–10 piece 4×4 ($3.68 \times 10^{15}$ total); Mhalla & Prost (2013) weakly solved Gardner 5×5 ($\sim 9 \times 10^{18}$) with compact human oracles; Watkins (2016) emitted an 863M-node Losing Chess proof tree. Yet systematically measuring **certified proof size vs. reachable state space** across board sizes has not been published.

### Is it informative, and what would you change?
**As written, `SPEC.md`'s 4 start positions are too sparse and confounded to test Hypothesis H1 reliably:**
1. **`mini4x4` is degenerate:** Silverman 4×4 (`rqkr/pppp/PPPP/RQKR`) is a forced mate in **4 moves** whose `WIN w` certificate needs only **5 entries** (verified by `verify_survey.py`). Using it as the small-board anchor conflates board-size scaling with an opening trap.
2. **25-order jump to `std8`:** Only `4×4`, `4×5`, and `5×5` are reachable (`std8` at $\sim 4.8 \times 10^{44}$ is out of reach). Fitting a power-law $C \sim S^\alpha$ to 2–3 points—one 4-move mate (`4×4`), one open `4×5`, and one draw (`5×5`)—cannot separate scaling from start-position luck.
3. **Recommended changes:**
   - **Add intermediate boards and position ensembles:** Include `3×3`, `3×4`, `4×6`, `5×6` (QuickChess/Petty), and `6×6` (Los Alamos / Diana), plus **ensembles of random legal start positions** (or N-piece tablebase roots) per board size, analyzing `WIN` and `ATLEAST_DRAW` separately.
   - **Support submodel-anchored / compressed certificates:** Flat ASCII FEN TSVs force `05-solver` to expand trivial endgames and will hit `AGENTS.md`'s 4 GB RAM cap in Python `03-checker` above $\sim 10^7$ entries. Allow CQD-style references to verified smaller-piece tablebases and record both logical entry count and compressed size.
   - **Clarify `mini4x5` and `mini5x5` provenance:** Explicitly note `mini4x5` drops Silverman's 1981 pawn double-step, and `mini5x5` matches AISE/Mhalla–Prost rules rather than Gardner's 1969 rules.
