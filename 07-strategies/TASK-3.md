# 07-strategies, round 3: report, then the symbolic step

Round 2 was cut off at 50 minutes again, with `REPORT.md` still a stub. The work itself was
excellent. Read `../AGENTS.md` ("Time"), `../design/LOOP.md` and this file. **Stop
experimenting at minute 35 of your session and spend the rest on the report.**

## What the lead verified from your round 2 files (use these numbers in the report)

- `krk_v21.py` (892 syntax-tree nodes, 2230 bytes) and `kqk_v7.py` (793 nodes, 1747 bytes)
  both score 1000/1000 on their 4x4 to 8x8 families (your `scores.tsv`).
- Whole-class certificates, checked by the lead: on 4x4, 5x5 and 6x6 the union certificate of
  each program contains **every** valid White-to-move position of its material class and is
  `VALID` (both checkers on 4x4 and 5x5, the Go checker `../08-checker2/mcheck2` on 6x6).

  | Program | 4x4 | 5x5 | 6x6 |
  |---|---|---|---|
  | `kqk_v7` | 812 of 812 | 4,976 of 4,976 | 19,360 of 19,360 |
  | `krk_v21` | 1,312 of 1,312 | 7,040 of 7,040 | 25,440 of 25,440 |

- `audit-rank` on 5x5: the `kqk_v7` potential strictly decreases on all 7,748 two-ply steps.
  The `krk_v21` potential does not: 17,852 decrease, 48 equal, 534 increase.
- 7x7 and 8x8 whole-class runs are being done by the lead on a cloud runner; do not run them.

## Step 0 (first 10 minutes): the report

Fill `REPORT.md` and `LOG.md` for rounds 1 and 2: the scoreboard, one log entry per program
version (21 rook versions: idea, score, why it failed), the table above, and a plain answer
to: did program length have to grow with the board? Which ideas mattered most?

## Step 1: potentials an SMT solver can reason about

`z3` 4.16 with Python bindings is now installed (`import z3`). To prove a strategy for all
board sizes at once, without enumeration, everything must be **linear integer arithmetic**
over the piece coordinates and the board size `W`, `H`:

- allowed: `+`, `-`, comparisons, `min`, `max`, `abs`, integer constants, `if`/`else`;
- not allowed: multiplying two variables (`bw * bh`), loops or sums over squares (the `fr`
  count in the queen program), division or modulo by a variable.

Add `harness.py lint-lia <program>` that checks a `_pot` function for this fragment. Then
write `kqk_lia.py`: a potential in the fragment that keeps 1000/1000 coverage, keeps full
whole-class coverage on 4x4 to 6x6, and is a **strict ranking** under `audit-rank` on all
three boards. Length may grow; say by how much.

## Step 2: explicit witness move

The programs choose a move by minimising over all moves, which a solver cannot follow for a
symbolic board. A proof needs a **witness rule**: a second function `hint(pos)` in the same
linear fragment that names one White move directly (which piece, which target square as
linear expressions with case splits), such that after `hint(pos)` every Black reply lands on
a strictly smaller potential, or the move mates. Since the program minimises, it is then at
least as good as the hint. Add `harness.py audit-hint`: over the whole-class positions of 4x4
to 6x6, check that `hint` is legal, never stalemates, and that every reply strictly
decreases the potential. Iterate until there are zero violations.

## Step 3: the proof obligation in z3

Write `smt/kqk.py`: integer variables for the six coordinates and for `W`, `H >= 4`; the
validity of the position; the hint move; all eight Black king replies with their legality
(on the board, not adjacent to the White king, not attacked by the queen along a clear
line, capturing the queen only if it is undefended); and the potential before and after.
Ask z3 for a counterexample: a valid position and a legal reply where the potential does not
strictly decrease and the hint did not mate. `unsat` is the theorem for every board size
`>= 4`. `sat` gives a concrete position: check it against `rules.py`, and fix either the
encoding or the strategy. Also assert and check separately that the potential is bounded
below, so that strict decrease implies termination.

Before trusting `unsat`, test the encoding: for fixed `W = H = 4, 5, 6` the set of positions
z3 accepts as valid must equal the enumerated set, and the encoded reply relation must equal
`rules.legal_transitions` on every one of them. An encoding that disagrees with the rules
proves nothing. Report these agreement counts.

## Report

Update `REPORT.md` after each step. State exactly how far the chain got: linear potential,
hint with zero violations, encoding agreement, z3 verdict. Anything short of `unsat` with a
validated encoding is reported as not proven. List what would be needed for the rook.
