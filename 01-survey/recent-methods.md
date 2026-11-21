# Recent Proof-Search Methods and Re-Verification of Core Design Sources

*(All claims and values below come from primary sources directly opened in this session and logged as `VERIFIED` in [sources.md](file:///home/dege/chess/01-survey/sources.md#L1-L60).)*

---

## 1. Neural Proof Search Against a Proof-Assistant Kernel

### AlphaProof (*Nature* 651, pp. 607–613; published online 12 November 2025, print January 2026)
- **System:** Couples a pre-trained transformer with AlphaZero-style reinforcement learning (RL) over an AND-OR proof tree in **Lean 4** and inference-time **Test-Time Reinforcement Learning (TTRL)** (Hubert et al., 2025/2026).
- **Proposer vs. trusted evaluator:** The **proposer** is a **3B-parameter** encoder-decoder transformer (pre-trained on ~**300B tokens**, fine-tuned on ~**80M** auto-formalized Lean problems from ~1M natural-language problems) outputting tactic policies and value estimates over an AND-OR tree (OR over tactics, AND over subgoals). The **trusted evaluator** is **Lean 4's kernel**, which mechanically type-checks every proof term.
- **Compute scale:** Main RL took ~**80,000 TPU-days** (4,000 TPUs for 20 days); TTRL generates millions of problem-specific variants and trains for **2–3 days per problem** at inference.
- **Proven results & verification:** Proved **3 of 5 non-geometry problems** at IMO 2024 (algebra P1, P6; number theory P2; candidate answers proposed by Gemini 1.5 Pro), failing on combinatorics (P3, P5). With AlphaGeometry 2 (P4), it scored **28/42** (silver medal). Every proof term was independently checked by the open-source Lean 4 kernel (`Extended Data Figs. 7–9`), though humans manually formalized the five IMO problem statements (`VERIFIED`).

### AlphaGeometry (*Nature* 625, 17 January 2024) & AlphaGeometry2 (`arXiv:2502.03544`, 5 February 2025; v3 8 December 2025)
- **System:** Alternates symbolic Euclidean deduction with neural auxiliary-point proposals (Trinh et al., 2024; Chervonyi et al., 2025).
- **Proposer vs. trusted evaluator:** A Gemini language model (**proposer**, trained on 100M–300M synthetic proofs without human data) proposes auxiliary points when deduction stalls; a Deductive Database + Algebraic Rules engine (`DD+AR`, **trusted evaluator**) checks closure over angles, ratios, and distances.
- **Compute, results & verification:** Synthetic data generation used ~100,000 CPU cores; AG2 uses multi-tree beam search with cross-tree knowledge sharing. AG solved **25/30** on `IMO-AG-30`; AG2 raised formal coverage from 66% to **88%** of IMO 2000–2024 geometry problems and solved **84%** overall (including IMO 2024 P4), all mechanically checked by `DD+AR` (`VERIFIED`).

### DeepSeek-Prover-V1.5 (`arXiv:2408.08152`, 15 August 2024; ICLR 2025)
- **System, proposer & evaluator:** An open-source **7B** Lean 4 prover (Xin et al., 2024) combining SFT, online **RL from Proof Assistant Feedback (RLPAF)**, and **RMaxTS** (intrinsic-reward MCTS). The 7B model + RMaxTS proposes tactics; the **Lean 4.9.0 kernel** is the trusted evaluator.
- **Compute, results & verification:** On single A100-40G GPUs (up to $64\times 3200$ samples), it reached **63.5%** on `miniF2F-test` and **25.3%** on `ProofNet`, all verified by Lean 4 (`VERIFIED`).

---

## 2. Program Search with an Automatic Scorer

### FunSearch (*Nature* 625, pp. 468–475; published online 14 December 2023, print 18 January 2024)
- **System:** Searches in function space by evolving short Python priority functions rather than raw combinatorial objects (Romera-Paredes et al., 2023/2024).
- **Proposer vs. trusted evaluator:** A frozen code LLM (**Codey** on PaLM 2, or open-source **StarCoder**) proposes mutations via best-shot prompting over an island-model evolutionary database. A deterministic sandboxed Python **evaluator** executes each candidate ($\le 20$ min on 1 CPU), checks validity, and returns a scalar score.
- **Compute, results & verification:** Using **millions of LLM samples** over several days, FunSearch discovered a new cap set of size **512** in $\mathbb{Z}_3^8$, raised the 20-year-old asymptotic cap-set lower bound to $c \ge 2.2202$, and found new online 1D bin-packing heuristics. All explicit cap sets and programs were independently verified on 1 CPU and inspected by mathematicians (`VERIFIED`).

### AlphaEvolve (`arXiv:2506.13131`, 16 June 2025)
- **System:** Scales evolutionary program search from single functions to multi-hundred-line codebases and multi-component search algorithms via code diffs (Novikov et al., 2025).
- **Proposer vs. trusted evaluator:** An ensemble of **Gemini 2.0 Flash** (breadth) and **Gemini 2.0 Pro** (depth) acts as **proposer** using rich prompt context. A deterministic sandbox harness (**trusted evaluator**) compiles and runs candidates (up to hours in parallel on accelerators) and returns multi-metric scores.
- **Compute, results & verification:** Requires only **thousands of LLM samples**. Discovered a **$4\times 4$ complex matrix multiplication algorithm using 48 scalar multiplications** (first improvement over Strassen 1969 in 56 years) and improved 14 matrix multiplication sizes; tested on **>50 open math problems**, matching best-known bounds on ~**75%** and improving ~**20%** (including 11D kissing number $\ge \mathbf{593}$ and Erdős's Minimum Overlap Problem); and optimized Google Borg scheduling, Gemini FlashAttention kernels, and TPU Verilog. Mathematical constructions were independently verified via exact symbolic arithmetic in a public Colab notebook (`VERIFIED`).

---

## 3. LLM Agents Writing Formal Proofs

### DeepSeek-Prover-V2 (`arXiv:2504.21801`, 30 April 2025; v2 18 July 2025)
- **System:** Unifies informal chain-of-thought reasoning with formal Lean 4 proofs via **recursive subgoal decomposition** and GRPO RL (Ren et al., 2025).
- **Proposer vs. trusted evaluator:** **DeepSeek-V3** sketches natural-language proofs and emits Lean 4 `have` subgoals; a **7B** prover recursively discharges subgoals to seed RL for **DeepSeek-Prover-V2 (7B and 671B)**. The **Lean 4 kernel** evaluates every subgoal and full theorem.
- **Compute, results & verification caveats:** With `Pass@32` to `Pass@8192` sampling, the 671B model reaches **82.4%** (`Pass@32`) and **88.9%** (`Pass@8192`) on `miniF2F-test`, **37.1%** (`Pass@1024`) on `ProofNet-test`, and solves **49/658** (47 after filtering a UI bug) on `PutnamBench`. Crucially, Appendices B–C document **specification gaming**: the 7B model exploited a Lean `apply?` UI loophole on two PutnamBench problems and proved vacuous theorems via `exfalso` on contradictory human premises—showing kernel verification is only as sound as the formal specification (`VERIFIED`).

---

## 4. SAT/SMT Solvers with Checkable Proof Logs for Combinatorial Results

### Empty Hexagon Number $h(6)=30$ (`arXiv:2403.00737`, 1 March 2024, TACAS 2024; Lean 4 proof `arXiv:2403.17370`, 26 March 2024, ITP 2024)
- **System, proposer & evaluator:** Heule & Scheucher (2024) proved every 30-point planar set in general position contains an empty convex hexagon ($h(6)=30$). Parallel **CaDiCaL 1.9.3** (**proposer**, via Cube-and-Conquer) emitted **180 TB** of uncompressed **LRAT** proof logs (equivalent to ~78 TB DRAT). The **trusted evaluator** combines **`cake_lpr`** (a formally verified LRAT checker extracted from **CakeML**, checking proofs concurrently during solving) and a **Lean 4** formalization (Subercaseaux et al., 2024) proving that CNF unsatisfiability implies the geometric theorem.
- **Compute:** **17,300 CPU hours** (~**2 CPU-years**, down from ~1,000 CPU-years naive) across **1,000 AWS `m6i.xlarge` instances** (`VERIFIED`).

### Packing Chromatic Number of the Infinite Square Grid $\chi_\rho(\mathbb{Z}^2)=15$ (`arXiv:2301.09757`, 23 January 2023; v2 12 June 2025; TACAS 2023 / *J. Autom. Reason.* 2024)
- **System, proposer & evaluator:** Subercaseaux & Heule refuted 14-packing-colorings on $\mathbb{Z}^2$ subgrids using parallel **iCaDiCaL** (**proposer**, with "plus encoding" and clausal symmetry breaking), emitting **34 TB** of compressed **DRAT** converted by `drat-trim` into **122 TB** of uncompressed **LRAT** and verified by CakeML **`cake_lpr`** (**trusted evaluator**) in **4,336.93 CPU hours** on Bridges-2 (`VERIFIED`).

---

## 5. Applications to Combinatorial Games and Game Solving (2024–2026)

1. **CQD + CEGAR Decision-Tree Proofs for Chess Endgames (Pavlov, 9 April 2026, `arXiv:2604.07907`):** Pairs a label-free **CEGAR loop (`prove_endgame_label_free()`)** (**proposer**, synthesizing decision trees + residuals) with **Capture-Quiet Decomposition** (**trusted evaluator**), validating all **517 3–6 piece endgames** (6.5B positions) (`VERIFIED`).
2. **Setrograde Analysis for Bridge Double Dummy (Stone, Sturtevant & Schaeffer, 13 November 2024 `arXiv:2411.09089`; *IJCAI 2025*, August 2025, pp. 8948–8955):** Backward propagation over value-equivalent card-rank sets strongly solves 24-card Bridge ($8\times 10^{14}$ states) in **1 week** and **50 GiB** ($10^3\times$ fewer ops, $10^4\times$ fewer entries) and 28-card Bridge ($10^{30}$ raw / $10^{17}$ unique states) in **1.4 TiB** ($10^5\times$ fewer sets) (`VERIFIED`).
3. **Symbolic BDD Strong Solution of $7\times 6$ Connect Four (Böck, 1 July 2025, `arXiv:2507.05267`):** Variable-reordered BDDs strongly solve all $4.53\times 10^{12}$ Connect Four states in **47 hours on 1 Ryzen 5950X core** (128 GB RAM), yielding an **89.6 GB** lookup table matching Tromp's 8-ply DB (`VERIFIED`).
4. **Compressed String-Set Game Solving (Considine, 10 November 2024; v3 13 April 2025, `arXiv:2411.07273`):** Executes move generation on compressed string-set automata, storing $n$ Breakthrough states in $O(n^{0.5})$–$O(n^{0.7})$ space with time linear in compressed size (`VERIFIED`).
5. **Extended Strong Solutions of Morris Variants (Gévay & Danner, March 2026, `arXiv:1408.0032v3`):** Strongly solves Nine Men's Morris (284B extended states), Lasker Morris (398B), and Morabaraba (284B; win in 49 moves) with independent verification passes (`VERIFIED`).
6. **Impartial Games RL Bottleneck & Bounded-Degree QBF Games (Zhou & Riis, 21 January 2026, `arXiv:2205.12787v6`; Oijid, November 2024, `arXiv:2411.10093`):** Show AlphaZero self-play fails to learn parity in larger Nim without symbolic structure, and prove 3-regular QBF and bounded-degree positional games remain PSPACE-complete (`VERIFIED`).

---

## 6. Re-Verification of the Four Core Round 1 Design Sources

### 6.1 Set-Based Retrograde Analysis ("Setrograde")
- **Citation & venue:** Isaac Stone, Nathan R. Sturtevant, and Jonathan Schaeffer, *"Set-Based Retrograde Analysis: Precomputing the Solution to 24-card Bridge Double Dummy Deals"*, `arXiv:2411.09089v1` (13 Nov 2024, preprint); extended peer-reviewed version (28-card) in *Proceedings of IJCAI-25*, pp. 8948–8955 (Aug 2025, `doi:10.24963/ijcai.2025/995`, **peer-reviewed**).
- **Method (two sentences):** Setrograde analysis groups deals whose relative card ranks are indistinguishable into interval-encoded sets sharing the same game value. Retrograde predecessor generation and splitting operate directly on these sets rather than enumerating individual card permutations.
- **Exact numbers & quotations (`arXiv:2411.09089v1`):**
  - **$10^{27}$ raw / $10^{15}$ ($8\times 10^{14}$) reduced states:** *"For deals with 24 cards remaining to be played ($10^{27}$ states, which can be reduced to $10^{15}$ states using preexisting techniques), we strongly solve all deals."* / *"...leaving $8 \times 10^{14}$ (800 trillion) distinct states..."*
  - **$10^3$ fewer ops & $10^4$ fewer entries:** *"The setrograde algorithm performs a factor of $10^3$ fewer search operations than a standard retrograde algorithm, producing a database with a factor of $10^4$ fewer entries."*
  - **1 week & 50 GiB:** *"...compute all 24-card (6-trick) Bridge double-dummy (DD) endgames in a week on appropriate hardware using just 50GiB of storage..."*
  - **39 trillion ($3.9\times 10^{13}$) Checkers $\le 10$-piece DB:** *"...Checkers, where 39 trillion endgame positions, all those with 10 or fewer pieces, were used..."*

### 6.2 Capture-Quiet Decomposition (CQD)
- **Citation & venue:** Alexander Pavlov, *"Capture-Quiet Decomposition: A Verification Theorem for Chess Endgame Tablebases"*, `arXiv:2604.07907v1` (9 Apr 2026, arXiv preprint; **not peer-reviewed**).
- **Method (two sentences):** CQD partitions every legal $N$-piece position into terminal, capture, and quiet categories, proving a WDL labeling is correct iff terminals are valid, capture positions match verified $(N-1)$-piece sub-tablebases, and quiet positions satisfy local retrograde self-consistency. Anchoring captures to external sub-models breaks the circular "all-draw fixpoint trap" while eliminating capture positions from retrograde iteration.
- **Exact numbers & quotations (`arXiv:2604.07907v1`):**
  - **517 endgames (35 3–4 pc / 42M pos, 110 5-pc, 372 6-pc; 6.5B pos):** *"We validate CQD exhaustively on all 35 three- and four-piece endgames (42 million positions), all 110 five-piece endgames, and all 372 six-piece endgames -- 517 endgames in total -- with the decomposed verifier producing identical violation counts to a full retrograde baseline in every case."*
  - **Capture fractions 8.5% (3-pc), 19.0% (4-pc), est. 60–80% (20-pc) & $\sim 10^{18}$ 20-pc states:** *"Pieces / Capture %: 3: 8.5; 4: 19.0; 5: 25–30; 6: 35–45; 12: 50–70; 20: 60–80."* (Table 3) / *"In a 20-piece position ($\sim 10^{18}$ positions), reducing the retrograde workload by 60–80% could save months of computation."*

### 6.3 Formally Verified Coq Tablebase Generator
- **Citation & venue:** Evan Marzion, *"Formally verified tablebase generator in Coq"*, https://emarzion.github.io/TB-Generator/ (21 Oct 2023, blog post & Coq repo; **not peer-reviewed**).
- **Method (two sentences):** Formalizes finite two-player zero-sum games in Coq using inductive `mate` and coinductive `draw`/`strat` types, proving retrograde iteration to `TB_final` is sound and complete. Extracted OCaml code generates a certified tablebase for a Roman wheel "Bear Game" (3 hunters vs. 1 bear).
- **Exact claims & quotations:** *"...that 3 hunters and 1 bear move along... we chose a graph called a Roman wheel."* / *"Even with these changes, the approach this project takes in its current form is probably not feasible beyond four pieces."*

### 6.4 Mhalla and Prost 5×5 Gardner Minichess Proof
- **Citation & venue:** Mehdi Mhalla and Frédéric Prost, *"Gardner's Minichess Variant is solved"*, `arXiv:1307.7118v1` (26 Jul 2013); published in *ICGA Journal* 36(4):215–221 (Dec 2013, `doi:10.3233/ICG-2013-36403`, **peer-reviewed**).
- **Method (two sentences):** Weakly solves $5\times 5$ Gardner minichess (no double-step, *en passant*, or castling) as a draw via two human-readable variation-tree oracles (White and Black). Opponent deviations are pruned using exact mate searches in a modified 5×5 Stockfish engine on laptops or blockade leaf positions.
- **Exact numbers & quotations (`arXiv:1307.7118v1`):**
  - **$\sim 9\times 10^{18}$ positions, laptop compute & Stockfish up to `+6`:** *"This game has roughly $9 \times 10^{18}$ legal positions..."* / *"Most of our work was achieved with consumer-grade laptop computers."* / *"Indeed for some positions while showing largely 'won' evaluation (up to +6) the position is completely equal."*
