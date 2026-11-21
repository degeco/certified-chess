# Critique of `LOOP.md`: Strategy Programs and What Transfers

*(Evaluates [LOOP.md](file:///home/dege/chess/design/LOOP.md) against [SPEC.md](file:///home/dege/chess/design/SPEC.md) v1.1 and primary sources verified in [recent-methods.md](file:///home/dege/chess/01-survey/recent-methods.md) and [sources.md](file:///home/dege/chess/01-survey/sources.md).)*

---

## 1. Is a Strategy Program Expanded and Checked by Enumeration Sound and Useful?

**Yes—it is completely sound, and it is a high-leverage representation for testing proof compression, subject to three operational caveats:**

1. **Soundness:** Because a strategy program $P(p) \to m$ is treated purely as an untrusted move selector whose expansion emits a flat `#cert v1` file verified by `03-checker`, **soundness is identical to SPEC v1.1**. An illegal move, cycle in `WIN`, or uncovered reply simply causes expansion or `03-checker` to fail.
2. **Usefulness:** Unlike flat FEN certificates, a geometric rule program $P$ can be parameterized independently of board dimensions $(W, H)$ and scored across root ensembles $R$. Measuring **compression = entries / length** directly tests whether human- or LLM-synthesized code captures a closed winning/drawing manifold without memorizing states—adapting the FunSearch / AlphaEvolve paradigm (`Romera-Paredes et al., 2024`; `Novikov et al., 2025`) to game solving.
3. **Three operational caveats:**
   - **Opponent branching still explodes:** $P$ collapses prover branching (OR-nodes) to 1, but expansion must still enumerate **all legal opponent replies** (AND-nodes). On $6\times 6$ or $8\times 8$, even a 300-byte program can reach millions of opponent states and hit the 5-minute / 4 GB RAM cap.
   - **Stateless purity vs. multi-phase subgoals:** Because $P(p)$ is a pure function of position $p$, stateful endgame plans (e.g., remembering which corner or "room" is being shrunk in KRK/KBNK) must be reconstructed deterministically from coordinates (canonical board symmetry normalization prevents oscillating cycles).
   - **All-or-nothing root coverage vs. tactical exceptions:** Simple geometric rules often cover 99% of reachable states but fail on rare tactical traps (e.g., immediate forks or stalemate tricks). Under `LOOP.md`, a single uncovered reply anywhere in the tree zeroes out coverage for that root.

---

## 2. Closest Prior Work

`LOOP.md` sits at the intersection of five research lines:

1. **Endgame Strategies Proven in Proof Assistants (Closest Direct Precedent):** **Bratko (1978)** formulated piece-confinement strategies for KRK in the **AL1** advice language. **Maliković & Janičić (2013)** verified a deterministic Bratko-style KRK strategy on $8\times 8$ via SAT in **URSA**, and **Marić, Janičić & Maliković (2015, CADE-25; 2019, *LMCS* 15(1))** proved its total correctness in **Isabelle/HOL + Z3**, generalizing it to symbolic **$n \times n$ boards ($n \ge 4$)** (`VERIFIED`).
2. **CEGAR Decision-Tree + Residual Synthesis:** **Pavlov (2026, `arXiv:2604.07907`)** runs a label-free **CEGAR loop (`prove_endgame_label_free()`)** that iteratively trains a compact decision tree plus a residual exception table until CQD retrograde violations vanish across all 517 3–6 piece endgames (`VERIFIED`).
3. **Chess Endgame Rule Induction:** **Quinlan (1979/1983, ID3)**, **Shapiro (1983/1987, structured induction on KPK and `kr-vs-kp` / KPa7KR, 3,196 positions)**, and **Bain & Muggleton (1994, ILP on KRK)** induced compact decision trees and logic rules from tablebase oracles, though for static WDL classification rather than closed move certificates.
4. **Evolutionary Program Search:** **FunSearch (2023/2024)** and **AlphaEvolve (2025)** evolve Python code against a deterministic sandbox scorer penalizing length and rewarding validity/coverage—the exact outer loop of `LOOP.md`.
5. **Reactive Synthesis & Inductive Invariants:** Synthesizing $P$ against adversarial inputs is finite-state **reactive synthesis** (Pnueli & Rosner, 1989) via **CEGIS** (Solar-Lezama et al., 2006): `ATLEAST_DRAW` synthesizes an **inductive invariant** (Bradley's IC3/PDR, 2011), while `WIN` synthesizes an invariant plus a decreasing **ranking function**.

---

## 3. What the Symbolic Step in "Honest Limits" Requires—and Which Tools Can Carry It

To check a strategy program $P$ **without enumerating positions** across board sizes $(W, H)$, one must prove a universally quantified 2-ply verification condition over symbolic integer coordinates $(x_i, y_i) \in [0, W) \times [0, H)$:

- **For `ATLEAST_DRAW`:** An **inductive invariant** $I(p, W, H)$ covering the roots such that for every position $p$ satisfying $I$, either $p$ is a prover stalemate or $m = P(p)$ is legal and every legal opponent reply $r$ in $p \cdot m$ satisfies $I(p \cdot m \cdot r, W, H)$.
- **For `WIN`:** Both an invariant $I(p, W, H)$ and a well-founded **ranking function** $\mu(p, W, H) \in \mathbb{N}$ such that every non-mating 2-ply step $p \to p \cdot P(p) \cdot r$ preserves $I$ and strictly decreases $\mu(p \cdot P(p) \cdot r) < \mu(p)$.

**Tools that can carry it:** As demonstrated by **Janičić, Marić & Maliković (2019, *LMCS*)** on $n \times n$ KRK (`VERIFIED`), if $P$, $I$, and $\mu$ avoid nonlinear multiplication (replacing rectangular confinement area $x \cdot y$ with **half-perimeter** $x + y$), all conditions lie in **quantifier-free linear integer arithmetic (`QF_LIA` / Presburger arithmetic)** with symbolic board size $n$:
- **SMT Solvers (`Z3`, `cvc5`):** Decide negated 2-ply `QF_LIA` obligations for all $W, H \ge 4$ in seconds (136s for all 6 symbolic KRK lemmas in Z3) and emit concrete counterexample positions when a branch fails.
- **Proof Assistants (`Lean 4`, `Isabelle/HOL`, `Coq`):** Reconstruct SMT/SAT proofs inside a trusted kernel (Isabelle/HOL + Z3 in 2,202s, or Lean 4 `omega`/`bv_decide` + CakeML `cake_lpr` LRAT checking).

---

## 4. Three Concrete Next Experiments (Ranked by Expected Information per Unit Effort)

1. **Rank 1 — Cross-Board KQK & KRK Strategy Synthesis ($4\times 4$ to $8\times 8$) with Counterexample Feedback:** Run the `LOOP.md` harness on 50-root `KQK` and `KRK` (`WIN w`) ensembles across $4\times 4, 5\times 5, 6\times 6, 8\times 8$, returning both scalar coverage and the **first failing position/reply** (CEGIS feedback). Directly tests Hypothesis H2 using `03-checker`.
2. **Rank 2 — Pure Strategy Program vs. Program + Bounded Residual (`KPK` / `KBNK`):** Compare pure programs $P(p)$ against a hybrid $(P(p), \text{Residual})$ where total length includes explicit residual exception entries (testing Pavlov's 2026 CEGAR decomposition on tactical exceptions).
3. **Rank 3 — Symbolic `QF_LIA` Verification Prototype for the Winning KRK Strategy:** Express the shortest 100%-coverage `KRK` strategy from Experiment 1 in a linear coordinate DSL (`dx`, `dy`, `abs`, half-perimeter `room`) and verify 2-ply closure + rank decrease symbolically for all $W, H \ge 4$ via finite relative-offset case splitting in Python.
