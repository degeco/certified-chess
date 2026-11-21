# Small-Board Chess Variants and `SPEC.md` Start Positions

This document surveys published results on chess boards smaller than 8×8 and compares them directly against the rules and start positions defined in [SPEC.md](file:///home/dege/chess/design/SPEC.md). Under `SPEC.md`, any board other than 8×8 uses **"mini" rules**: pawns move one square forward (no double-step), no *en passant*, no castling, mandatory promotion to Q/R/B/N on the last rank, and no 50-move or repetition rule (infinite play is a draw). A published game value transfers to our setting **only if both the board setup and the rules match**.

---

## 1. Direct Comparison of `SPEC.md` Start Positions

| `SPEC.md` Name | FEN (`<placement> w - -`) | Historical Variant | Rules Match? | Published Value & Status | Proof Size / Compute |
|---|---|---|---|---|---|
| `mini4x4` | `rqkr/pppp/PPPP/RQKR w - -` | **Silverman 4×4** (David Silverman, 1981) | **Yes.** Neither variant has double pawn push, *en passant*, or castling (only 4 ranks exist). | **White wins in 4 moves** (`1. axb3+ Qxb3 2. cxb3+ Kb4 3. bxc3#` or `2... Kxb3 3. bxa3+ Kc4 4. Qa2#`). Independently verified under `SPEC.md` rules by `verify_survey.py`. | **5 entries** in `#cert v1` `WIN w` (max rank 4); solved in <0.05 s on 1 CPU core. |
| `mini4x5` | `rqkr/pppp/4/PPPP/RQKR w - -` | **Silverman 4×5** (David Silverman, 1981) | **NO — Rule Mismatch.** Silverman (1981, in Pritchard *CECV* 2007 p. 113) allows **pawn double-step** if the file is clear; Hammersborg & Strümke (2022/2023, `arXiv:2211.05500v1`) allow **pawn double-step**, ***en passant***, and a **20-ply no-progress draw cutoff**. `SPEC.md` forbids pawn double-step, *en passant*, castling, and 50/10-move cutoffs. | **Draw under `SPEC.md` rules (newly certified in this project by `../05-solver` and verified by `../03-checker` & `../08-checker2`).** Under different rules (double-step + *en passant* + 20-ply draw cutoff), Hammersborg & Strümke (2022/2023) state a draw in 1 sentence without a published proof or database (see [novelty-4x5.md](file:///home/dege/chess/01-survey/novelty-4x5.md)). | **`6,107` entries** (`ATLEAST_DRAW w`) + **`249,051` entries** (`ATLEAST_DRAW b`) in `#cert v1`; main defence `1. d3 c3 2. Rd2 a3 3. b3 Ra4`. |
| `mini5x5` | `rnbqk/ppppp/5/PPPPP/RNBQK w - -` | **Gardner's Minichess** (Martin Gardner, 1969; **AISE rules**) | **Partial — Matches AISE, differs from Gardner 1969.** Gardner (1969) originally allowed pawn double-step, *en passant*, and castling. Later **AISE** (Italian Heterodox Chess Association) dropped pawn double-step, *en passant*, and castling. **Mhalla & Prost (2013)** solved the **AISE ruleset**, which **matches `SPEC.md` mini rules** (note: Mhalla & Prost do not state whether 50-move/repetition differ, though their oracle explicitly uses repetition/fortress draws). | **Draw** (weakly solved under AISE rules by Mhalla & Prost, 2013). Correspondence statistics under AISE: 40% White win, 32% draw, 28% Black win. | Human-readable proof tree (~12 pages of variations in `arXiv:1307.7118`) + modified Stockfish mate searches up to 60 moves; computed on consumer laptops. |

---

## 2. Survey by Board Size

### 3×3 Chess
- **Setup & Rules:** No canonical starting position. Kirill Kryukov (2004, updated 2024) strongly solved all legal placements, including pawns on the first rank, with no castling, no double-step, and no *en passant*. Aloril (2001) earlier solved the smaller subset forbidding pawns on the 1st rank (link now dead; cited by Kryukov and Wikipedia).
- **Counts & Values:** **54,687,564** unique legal positions (NULP, accounting for symmetries); **304,545,552** positions in Kryukov's unreduced database (330 MB, 1 byte/position): 104,863,672 checkmates (>1/3), 3,576,856 stalemates (1.2%), 78,022,680 wins (39.8% of non-terminal), 69,391,160 losses (35.4%), 48,691,184 non-stalemate draws (24.8%).
- **Depth:** Longest forced checkmate is **16 moves** (32 plies).

### 3×4 Chess
- **Setup & Rules:** No canonical starting position; no castling, no double pawn step, no *en passant*; pawns allowed on the 1st rank; no 50-move rule (Kryukov, 2009–2025).
- **Counts & Values:** **167,303,246,916** unique legal white-to-move positions across 184,756 ESMs (endgame+side-to-move classes), 2–12 pieces. Of non-check positions with legal moves (41.8B), 59.97% win, 27.76% lose, 12.27% draw.
- **Depth & Storage:** Longest DTM is **43 moves** (85 plies); longest DTC is **26 moves**. Compressed full 3–12 piece DB is **50.6 GB (DTM)** / **18.4 GB (DTC)** (or **11.8 GB / 3.8 GB** shrunk).
- **Compute & Verification:** Built in ~10 days on a 4-core AMD Phenom II X4 905e with 8 GB RAM; verified by self-consistency (`-verify`), double reconstruction, Lutz Nebe's independent build (identical stats), and Marc Bourzutschky's max-DTM comparison up to 6 pieces (excluding 5v1).

### 4×4 Chess
- **General Strong Solution (Kryukov, 2011–2025):** Same no-castling / no-double-step / no-50-move rules, pawns allowed on 1st rank. Total NULP (2–16 pieces across 981,010 non-empty endgames / 1,960,934 ESMs): **3,677,542,994,054,888** ($\approx 3.68 \times 10^{15}$). All **2–10 piece** endgames are strongly solved (DTM and WDL; DTX/DTZ to 9 pieces; DTC to 8 pieces), covering up to ~4.60 trillion 10-piece positions. Longest mate found so far is **73 moves** (e.g., `b1p1/N1Pk/PBb1/BK2 w`, 9 pieces).
- **Silverman 4×4 (`rqkr/pppp/PPPP/RQKR`):** White wins in 4 moves (`1. axb3+`). Silverman's anti-first-move variant (Black chooses which White pawn moves first) loses even faster for White (`b2` -> `1. bxa3 b2+ 2. Qxb2 Qxb2#`).
- **ProstoTak 4×4 (`nqkr/pppp/PPPP/NQKR`):** Proposed in 2011; solved as a White mate in 4 moves (`1. cxd3+ Rxd3 2. Qxd3+ Kxd3 3. dxc3+ Kc4 4. Rd8#`, cited by Kryukov).

### 4×5 Chess
- **Silverman 4×5 (`rqkr/pppp/4/PPPP/RQKR`):** Proposed by Silverman (1981; Pritchard *CECV* 2nd ed. 2007, Section 13.2, p. 113) by inserting an empty rank and permitting a two-square pawn advance if the file is clear. Under `SPEC.md` mini rules (no double-step, no *en passant*, no castling, no 50-move rule), `../05-solver` produced—and both independent checkers (`../03-checker` and `../08-checker2`) accepted—`#cert v1` certificates proving that `mini4x5` is a **draw** (`6,107` positions for White's half, `249,051` for Black's half; main defensive line `1. d3 c3 2. Rd2 a3 3. b3 Ra4`). Under different rules (double-step enabled, *en passant* enabled, and a 20-ply no-progress draw cutoff in `fastchess.py`), Hammersborg & Strümke (2022/2023, `arXiv:2211.05500v1`, *IFAC-PapersOnLine* 56(2):9050–9055) state in one sentence that optimal play is a draw, without publishing a proof, opening line, or database. Full search log and rule comparison: [novelty-4x5.md](file:///home/dege/chess/01-survey/novelty-4x5.md).
- **Gardner-style 4×5 (`rnbk/pppp/4/PPPP/RNBK`):** Default 4×5 setup on GreenChess (`https://greenchess.net/rules.php?v=4x5-chess`, no double-step, no castling) and implemented in Fairy-Stockfish `variants.ini` as `[4x5chess:gardner]` (PR #290, 2021) with an unarchived comment `# --> Solved draw`.
- **Microchess (Dan Glimne, 1997):** Different material (`rbnk/p3/4/3P/RBNK`, 1 pawn per side, no queen), no double-step, castling allowed; no published solution found.

### 5×5 Chess
- **Gardner's Minichess (`rnbqk/ppppp/5/PPPPP/RNBQK`):** State space estimated at **$\sim 9 \times 10^{18}$** legal positions (Mhalla & Prost, 2013). Weakly solved as a **draw** under AISE rules (matching `SPEC.md` mini rules) via two asymmetric oracles (one for White, one for Black), where non-mainline deviations end in Stockfish-verified forced mates (up to 60 moves) or human-evident blocked/fortress draws.
- **Other 5×5 setups:** Baby chess (mirrored Black back rank, Gardner 1989) and Jacobs–Meirovitz do not have published complete proofs in `arXiv:1307.7118`. Wikipedia reports that Mhalla & Prost proved **Mallett 5×5** (2 knights vs 2 bishops) is a forced White win in 25 moves when White has knights, and drawn when White has bishops (`UNVERIFIED` from primary source).

### 5×6 and 6×6 Chess
- **5×6 variants** (Petty 1930, QuickChess 1991, Chess Attack 2008, MinitChess 2010): no complete game-theoretic solutions found.
- **Los Alamos 6×6** (`rnqknr/pppppp/6/6/PPPPPP/RNQKNR`, no bishops, no pawn double-step, no castling, no bishop promotion): estimated **$\sim 4 \times 10^{29}$** positions, branching factor ~22 (Wikipedia citing Sayle 2023, `UNVERIFIED` from primary journal). Standard Game 1 remains unsolved. **Game 2** (White starts without a queen; after `1. d3`) was reported solved by Roger Sayle (*ICGA Journal*, Nov 2023) as a **Black win in at most 21 moves (41 ply)** after `1... c4` (`UNVERIFIED` from primary journal).
