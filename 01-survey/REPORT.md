# Report: `01-survey`

## What Was Built

- [assessment.md](file:///home/dege/chess/01-survey/assessment.md) — Source-backed research assessment (2,066 tokens, within the ~2,500-word limit) covering formal solving criteria, current methods/results, computational obstacles, a ranked shortlist of research directions, and a critique of [SPEC.md](file:///home/dege/chess/design/SPEC.md).
- [sources.md](file:///home/dege/chess/01-survey/sources.md) — 53-row claim ledger tracking exact values, authors/years/URLs/DOIs, source types, access date (`2026-11-21`), `VERIFIED` / `UNVERIFIED` status, and a Round 2 re-verification section.
- [small-boards.md](file:///home/dege/chess/01-survey/small-boards.md) — Literature survey for 3×3, 3×4, 4×4, 4×5, 5×5, 5×6, and 6×6 chess variants, mapping `mini4x4`, `mini4x5`, and `mini5x5` to historical variants and flagging rule differences.
- [recent-methods.md](file:///home/dege/chess/01-survey/recent-methods.md) — Round 2 survey (~2,000 words) of recent proof-search and program-search method families plus direct re-verification and verbatim quotations for the four core Round 1 design sources.
- [transfer.md](file:///home/dege/chess/01-survey/transfer.md) — Round 2 critique (~800 words) of [LOOP.md](file:///home/dege/chess/design/LOOP.md), covering soundness/usefulness of enumerated strategy programs, closest prior work, requirements and tools for the symbolic verification step, and three ranked next experiments.
- [novelty-4x5.md](file:///home/dege/chess/01-survey/novelty-4x5.md) — Round 3 prior-art investigation (4,339 words) of the certified `mini4x5` draw (`rqkr/pppp/4/PPPP/RQKR w - -`), including a 12-category search log, a 7-implementation rule comparison matrix with an executable Ply-3 divergence proof, a formal novelty verdict, and target publication venues.
- [verify_survey.py](file:///home/dege/chess/01-survey/verify_survey.py) — Python 3.14 standard-library verification suite testing all Round 1, Round 2, and Round 3 deliverables, `mini4x4` `#cert v1` verification, `mini4x5` main-line and Ply-3 rule-divergence verification, and `LOOP.md` strategy-program expansion on a 4-root 4×4 `KQK` ensemble.

## How to Build and Test

No build step is required (Python 3.14 standard library only). Run:

```bash
python3 /home/dege/chess/01-survey/verify_survey.py
```

## Actual Test Output

```text
PASS assessment.md word count: 2066 <= 2500; all 5 sections present.
PASS recent-methods.md word count: 2082 (~2000 target); all 5 method families and 4 re-verified sources present.
PASS transfer.md word count: 976 (~800 target); all 4 critique sections present.
PASS novelty-4x5.md verified: 4339 words; all 4 sections and all required search/rule/venue items present.
PASS sources.md schema valid: 53 claims (40 VERIFIED, 13 UNVERIFIED) + Round 2 re-verification section.
PASS all file:// links resolve to existing files.
PASS mini4x4 WIN w certificate verified: 5 entries, max rank 4.
PASS mini4x5 mainline (1. d3 c3 2. Rd2 a3 3. b3 Ra4 -> 1qkr/rp1p/pPpP/P1PR/RQK1 w - -) and ply-3 double-step / ply-4 en-passant rule divergence verified.
PASS LOOP.md KQK strategy expansion verified across 4 roots: 7 total certificate entries.
```

## Measured Numbers

- `assessment.md`: 2,066 whitespace-delimited tokens.
- `recent-methods.md`: 2,082 whitespace-delimited tokens.
- `transfer.md`: 976 whitespace-delimited tokens.
- `novelty-4x5.md`: 4,339 whitespace-delimited tokens.
- `sources.md`: 53 claims total — 40 `VERIFIED` (directly opened and read), 13 `UNVERIFIED` (paywalled, timed out, 403/404, or seen only in secondary citations / search summaries).
- `mini4x4` (`rqkr/pppp/PPPP/RQKR w - -` under `SPEC.md` mini rules): proved `WIN w` in 4 moves (`1. a2b3 b4b3 2. c2b3 c4b3 3. b2a3 b3c4 4. b1a2#`, or `2... c4b4 3. b2c3#`), with a 5-entry certificate of max rank 4.
- `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`): main defensive line `1. d3 c3 2. Rd2 a3 3. b3 Ra4` verified legal under `SPEC.md` rules (reaching `1qkr/rp1p/pPpP/P1PR/RQK1 w - -`); legal move sets of `SPEC.md` `mini4x5` and Silverman (1981) / Hammersborg & Strümke (2022/2023) rules verified to diverge at **Ply 3** (after `1. d2d3 c4d3`, White has `2. c2c4` and Black has `2... b4c3` *en passant* at Ply 4 under double-step rules, both illegal under `SPEC.md`).
- `LOOP.md` 4×4 `KQK` prototype strategy program in `verify_survey.py`: 100% coverage across 4 roots, producing 7 total `#cert v1` entries verified by `verify_win_cert()`.

## Known Gaps / Unverified Items (Round 1)

The following items could not be verified directly from their primary sources during Round 1 (marked `UNVERIFIED` in [sources.md](file:///home/dege/chess/01-survey/sources.md)):

1. **Schaeffer et al. (2007), *Checkers Is Solved* (`Science`, paywalled):** Total state space ($\sim 5 \times 10^{20}$), ops ($10^{14}$), 18-year duration, and 50–200 PCs came from Wikipedia; minimal proof-tree size (223,178 positions) came only from search summaries; the $\le 10$-piece DB size ($3.9 \times 10^{13}$) was verified via Stone et al. (2024).
2. **Romein & Bal (2003), *Awari* (`IEEE Computer`, paywalled):** State count ($889,063,398,406$), 144 CPUs, 72 GB RAM, ~51 h, and verification method were not directly opened.
3. **Gasser (1995/1996), *Solving Nine Men's Morris*:** MSRI PDF timed out; state count ($\sim 10^{10}$) and separate verifier came from Gévay & Danner (2016/2026) and Wikipedia.
4. **Pawlewicz & Hayward (2013), *SPDFPN* (404 on UAlberta):** 9×9 (111 days) and 10×10 (63 days) Hex solve times came only from search summaries.
5. **Fraenkel & Lichtenstein (1981) & Storer (1983) (paywalled):** EXPTIME-completeness and polynomial-$k$ PSPACE-completeness were verified via Brunner et al. (2020) secondary citations, not the 1981/1983 originals.
6. **Chinchalkar (1996) upper bound ($\sim 1.78 \times 10^{46}$):** Verified only as cited by Tromp (2022).
7. **7-piece Lomonosov DTM (~140 TB, max 549 moves) & 8-piece Op1 (68.8 TB, ~5×10^14 pos, DTC-584):** Lichess blog returned HTTP 403; figures come from Wikipedia / Chess Programming Wiki.
8. **Sayle (2023), *Los Alamos Game 2* (`ICGA Journal`, paywalled):** $\sim 4 \times 10^{29}$ positions and 21-move Black win after `1. d3 c4` come from Wikipedia.
9. **Mhalla & Prost Mallett 5×5 result:** Not present in `arXiv:1307.7118`; reported via Wikipedia.
10. **TCEC / Stockfish draw rates from startpos:** Exact season-level percentages were not opened from primary TCEC logs.

## Spec Issues (for [SPEC.md](file:///home/dege/chess/design/SPEC.md))

1. **Degenerate and too-sparse H1 benchmark (addressed in SPEC v1.1 Section 5):** `mini4x4` is a 4-move mate (5-entry `WIN w` certificate); SPEC v1.1 now measures H1 on ensembles of roots per board size.
2. **Variant rule differences:** `mini4x5` disables Silverman's 1981 pawn double-step (`mini4x5` != Silverman 4×5); `mini5x5` matches AISE / Mhalla–Prost rules rather than Gardner's original 1969 rules (which had double-step, *en passant*, and castling).
3. **Rank bounds in `#cert v1` (addressed in SPEC v1.1 Section 4):** SPEC v1.1 now explicitly specifies non-negative decimal integer ranks (`0` in `ATLEAST_DRAW`) and prover-stalemate coverage.
4. **Flat TSV memory scaling:** Storing raw FENs per entry will strain `AGENTS.md`'s 4 GB RAM cap in Python `03-checker` beyond $\sim 10^7$ entries; CQD-style submodel anchoring and [LOOP.md](file:///home/dege/chess/design/LOOP.md) strategy programs address proof representation compression.
5. **8×8 *en passant* legality edge case:** Canonical `ep` requires testing horizontal pins along ranks 4/5; `02-engine` and `03-checker` should explicitly cross-test this.

---

## Round 2

### What Was Re-Verified and Built in Round 2

1. **New primary sources opened and verified (`VERIFIED` in [sources.md](file:///home/dege/chess/01-survey/sources.md)):**
   - **Neural proof search against a kernel:** AlphaProof (Hubert et al., *Nature* 651:607–613, published online 12 Nov 2025 / print Jan 2026), AlphaGeometry (Trinh et al., *Nature* 625:476–482, 17 Jan 2024), AlphaGeometry2 (Chervonyi et al., `arXiv:2502.03544v3`, 5 Feb / 8 Dec 2025), and DeepSeek-Prover-V1.5 (Xin et al., `arXiv:2408.08152v1`, 15 Aug 2024; ICLR 2025).
   - **Program search with an automatic scorer:** FunSearch (Romera-Paredes et al., *Nature* 625:468–475, 14 Dec 2023 / 18 Jan 2024) and AlphaEvolve (Novikov et al., `arXiv:2506.13131v1`, 16 Jun 2025).
   - **LLM agents writing formal proofs:** DeepSeek-Prover-V2 (Ren et al., `arXiv:2504.21801v2`, 30 Apr / 18 Jul 2025), including its documented `apply?` UI and `exfalso` specification-gaming cases on `PutnamBench`.
   - **SAT/SMT with checkable proof logs:** Empty Hexagon Number $h(6)=30$ (Heule & Scheucher, `arXiv:2403.00737v1`, 1 Mar 2024, TACAS 2024) + its Lean 4 CNF-reduction formalization (Subercaseaux et al., `arXiv:2403.17370v1`, 26 Mar 2024, ITP 2024), and Packing Chromatic Number $\chi_\rho(\mathbb{Z}^2)=15$ (Subercaseaux & Heule, `arXiv:2301.09757v2`, 23 Jan 2023 / 12 Jun 2025, TACAS 2023 / *J. Autom. Reason.* 2024).
   - **Combinatorial games (2024–2026) & formal endgame strategies:** Pavlov (9 Apr 2026, `arXiv:2604.07907v1`), Stone et al. (*IJCAI 2025*, Aug 2025, `doi:10.24963/ijcai.2025/995`), Böck (1 Jul 2025, `arXiv:2507.05267v1`), Considine (10 Nov 2024 / 13 Apr 2025, `arXiv:2411.07273v3`), Gévay & Danner (Mar 2026, `arXiv:1408.0032v3`), Zhou & Riis (21 Jan 2026, `arXiv:2205.12787v6`), Oijid (Nov 2024, `arXiv:2411.10093`), and Janičić, Marić & Maliković (2019, *LMCS* 15(1):34:1–34:37, upgrading Round 1's Isabelle/HOL + Z3 KRK strategy entry from `UNVERIFIED` to `VERIFIED`).
2. **Re-verification of the four core Round 1 design sources (Section 6 of [recent-methods.md](file:///home/dege/chess/01-survey/recent-methods.md#L76-L125)):**
   - All four sources (`arXiv:2411.09089v1` + *IJCAI 2025* `0995.pdf`; `arXiv:2604.07907v1`; `https://emarzion.github.io/TB-Generator/`; `arXiv:1307.7118v1`) were re-opened directly and every quoted number was verified against verbatim quotes.
   - **Refinements/corrections recorded in [sources.md](file:///home/dege/chess/01-survey/sources.md):**
     - Added the peer-reviewed **IJCAI 2025** venue and 28-card result (`10^30` -> `10^17` states, `1.4 TiB`, `10^5` fewer sets) to Stone, Sturtevant & Schaeffer (row 35).
     - Clarified in Pavlov (2026, row 38) that the 517-endgame validation verifies exact equality of violation counts (`v_total == full_v`) between decomposed CQD and full retrograde verification on CEGAR-trained decision-tree + residual models (where 4-piece `KBNvK` had 121,188 tree-depth violations matched by both verifiers, while all 110 5-piece and 372 6-piece models converged to 0 violations).
     - Added the peer-reviewed *ICGA Journal* 36(4):215–221 (Dec 2013) citation to Mhalla & Prost (2013, row 28) and refined Round 1's `+6.00` phrasing to the paper's exact text `(up to +6)`.

### What Could Not Be Verified from Primary Sources in Round 2

1. **Paywalled *ICGA Journal* 36(4) typeset PDF of Mhalla & Prost (2013):** The bibliographic metadata and DOI (`10.3233/ICG-2013-36403`, pp. 215–221) were verified, while all full-text quotations were read from the open-access `arXiv:1307.7118v1` PDF.
2. **Paywalled 1979–1994 chess endgame induction originals (Quinlan 1979/1983, Shapiro 1987 book *Structured Induction in Expert Systems*, Bain & Muggleton 1994):** Cited in [transfer.md](file:///home/dege/chess/01-survey/transfer.md) as historical context via open secondary descriptions and the UCI `kr-vs-kp` dataset documentation (3,196 positions, 36 attributes); Bratko (1978) and Maliković & Janičić (2013) were verified through the opened full text of Janičić, Marić & Maliković (2019, *LMCS*).
3. **Remaining 13 `UNVERIFIED` rows in [sources.md](file:///home/dege/chess/01-survey/sources.md):** The paywalled Round 1 primary sources listed under "Known Gaps / Unverified Items (Round 1)" above remain marked `UNVERIFIED` (note that row 37, Marić et al. on Isabelle/HOL + Z3 KRK, was upgraded to `VERIFIED` in Round 2 after opening the 2019 *LMCS* journal PDF).

---

## Round 3

### 1. Novelty of the Certified `mini4x5` Draw ([novelty-4x5.md](file:///home/dege/chess/01-survey/novelty-4x5.md))

- **Verdict:** **Published under different rules only** (with **no published proof or database under any rules**, and **no prior result found under matching `SPEC.md` rules**).
- **Key Findings:**
  1. **Original Silverman 1981 source (Pritchard/Beasley *CECV* 2nd ed. 2007, Sec. 13.2, p. 113):** Poses 4×5 (`rqkr/pppp/4/PPPP/RQKR w`) *with a two-square pawn advance permitted if the file is clear* as an open problem (*"asks: what is White's best strategy?"*).
  2. **Only prior value claim for `rqkr/pppp/4/PPPP/RQKR` (Hammersborg & Strümke, Nov 2022 `arXiv:2211.05500v1`; Jul 2023 *IFAC-PapersOnLine* 56(2):9050–9055):** States in one sentence (Sec. 2.1) that *"By building the full search tree, we have found that optimal play results in a draw for the Silverman 4x5 variants."* Direct inspection of their repository (`https://github.com/patrik-ha/explainable-minichess`, `minichess/chess/fastchess.py` & `fastchess_utils.py`) proves three game-theoretic rule mismatches against `SPEC.md` `mini4x5`: **(i) pawn double-step is enabled** (`pawn_moves_double`), **(ii) *en passant* is enabled**, and **(iii) games are adjudicated as a draw after 20 plies (`ply_count_without_adv > 20`, i.e. 10.5 moves) without a pawn move or capture**—a severe horizon cutoff that truncates any >10-move quiet endgame win into a draw. The two game trees diverge at **Ply 3** (`1. d2d3 c4d3 2. c2c4`), and Hammersborg & Strümke published no solver code, proof, node count, opening line, or database.
  3. **Other 4×5 claim (Fairy-Stockfish `variants.ini` PR #290, 2021 / GreenChess `4x5-chess`):** Labels `[4x5chess:gardner]` as `# --> Solved draw` without a proof, but for a **different starting array and material set** (`rnbk/pppp/4/PPPP/RNBK w - - 0 1`, no Queens, one Rook per side).

### 2. Primary-Source Status of the 20 November 2026 Riemann Hypothesis Claim

Directly opened primary sources: Levent Alpöge's 4-page untitled note ([`https://alpo.ge/remark.pdf`](https://alpo.ge/remark.pdf), 20 Nov 2026), Andrew Sutherland's MIT verification page ([`https://math.mit.edu/~drew/grh/`](https://math.mit.edu/~drew/grh/), updated `2026-11-21 12:55 UTC`, checks run with Claude Code), and [`https://lean4.dev/proofs/riemann-hypothesis-claim`](https://lean4.dev/proofs/riemann-hypothesis-claim).

- **How the Proof Was Produced (`alpo.ge/remark.pdf`):**
  - **Scope & Timeline:** Formalizes not only `RiemannHypothesis` (using Mathlib's `Mathlib/NumberTheory/LSeries/RiemannZeta.lean` definition), but **full GRH for all Dirichlet $L$-functions** (`LFunction_eq_zero_re` and `LFunction_ne_zero_of_half_lt_re` for every modulus $N \ge 1$ and character $\chi \pmod N$, primitive or not). Produced over a 6-week collaboration (`10/6/26`–`11/16/26`) between Alpöge and Claude, released as a 14-part archive (`lean.tar.gz.part01`..`14`, `239,275,554` bytes, `sha256: 9631b4f0…`) containing `175,187` Lean files (`17.4M` lines, `~819,000` theorems/lemmas) pinned to Lean `v4.33.1` (`819816b2`) and Mathlib `v4.33.1` (`0df444a3`).
  - **Division of Labor & Mathematical Mechanism:** Alpöge set up an analogy to Stepanov's function-field determinant method combined with a Fourier-analytic Guinand–Weil / iterated-Parseval sign test on a "path" quadric ($x_1 x_2 + \dots + x_{k-1} x_k$). Claude supplied the core technical leap and automorphic machinery: mimicking divisor multiplicity over $\mathbb{Z}$ for a von Mangoldt sum of length $X$ by **chaining $m \asymp \sqrt{X}$ iterated theta lifts** $U(X_0) \to \dots \to U(X_m)$ between totally definite unitary groups ($\pi \mapsto \pi \boxplus \mu_j[t]$, `11/15/26`), bounding lift norms/divisibility via Chowla–Selberg, Weyl, Siegel mass, Rallis seesaw Bessel periods, a relative trace formula (via a 6-fold cover of $\mathrm{GL}_5$), gluing an integral structure across Hecke characters, an Iwasawa tower via Behrend, and proving a "significant weakening of Vandiver" for unkilled $H^1(\mathcal{O}_E[1/\ell], \mathbb{Q}_\ell/\mathbb{Z}_\ell(-e))$ classes (`11/15/26`–`11/16/26`).
  - **Author's Explicit Caveat (Footnote 4):** Alpöge notes that his 20-step timeline paraphrases a Claude-generated "slop" summary of areas where Claude—not Alpöge—is the expert and "might make zero sense," deferring entirely to the Lean code.
- **How It Was Checked & Primary-Source Corrections (`math.mit.edu/~drew/grh/` as of `2026-11-21 12:55 UTC`):**
  - **Completed & Passed Checks:** (1) All `175,187` modules compile with 0 errors (`16:43:21 UTC` on 20 Nov) and pass `leanchecker` kernel replay (`~18:17 UTC`). (2) Byte-for-byte match of `8,322` Mathlib and `378` dependency `.olean` files against official cache; `#print axioms` on the 5 headline theorems in `Main.lean` shows only `propext`, `Classical.choice`, and `Quot.sound` (`15` `Init` axioms total; zero `sorry`, `admit`, custom `axiom`, or `native_decide`). (3) Full 61.57 GB (`61,570,595,788`-byte) `lean4export v4.33.0` proof export (`solution.ndjson`, `1,468,418` declarations, `sha256: 5ea74b91…`) is accepted by two independent kernels: **`nanoda`** (Rust kernel, `exit 0` in `27m 42s` on 80 threads, ~100 GB RAM) and **`con-leche` master (`cd2eceab`)** (`exit 0` in `3m 15s` on 64 threads, ~50 GB RAM), with `con-leche --compare` (`5dc36dc1`) confirming all 5 challenge theorems (`51,692` challenge declarations, `350.86 MB`). (4) **`lean4lean` (`67f63b0c`, built with Lean `v4.33.1`)** accepted all `175,187` compiled `.olean` modules (`175,182` at default settings; **5 modules hit `lean4lean`'s default deterministic step limit on `decide +kernel` computations and passed after raising the limit**).
  - **Nuances & Unfinished Checks Omitted in Press Summaries:** (1) Older `con-leche` / `con-ron` binaries bundled with Lean `v4.36.0` exited with code 2 (not a proof rejection: they lacked support for one reflexive inductive type in the proof, which `con-leche` master supports). (2) **Two kernel runs are still in progress:** single-threaded replay of `solution.ndjson` through the **Lean default kernel** and **Lean paranoid kernel**, and the end-to-end **`lake comparator` (Lean `v4.36.0`)** kernel phase. (3) **Unsandboxed build caveat:** Sutherland notes the cloud build ran *without a sandbox* by invoking `lean` directly per file rather than `lake build` (`98,219` of `175,187` `.olean` files embed `/home/ubuntu/grh/src/lean/src/…` in linter messages), and the `sha256` of `solution.ndjson` has not yet been compared against an export from a sandboxed `lake build`.
