# 07-strategies, round 2

Round 1 was cut off by the 50-minute session limit, so there is no `REPORT.md` and no
`LOG.md`. Read `../AGENTS.md` again (new "Time" section), `../design/LOOP.md` (it changed:
prior work, lessons, round 2 rules) and `TASK.md`. Then continue from the files you left.

## What the lead session found and confirmed

- `strategies/kqk_v5.py`: 1664 bytes, **1000/1000 roots** on 4x4 to 8x8, 19,286 entries,
  maximum rank 16, re-scored by the lead with the same numbers. It is a potential function
  with a two-ply lookahead, and it is shorter than every earlier version.
- `krk`: best scored is v3 at 416/1000. `krk_v4` to `krk_v6` exist but were never scored.
- `mini4x4-start` and `kk-draw` are done.

## Step 0, before anything else

Write `REPORT.md` and `LOG.md` from `results/scores.tsv` and your memory of round 1: one log
entry per program version with the idea, the score, and why it failed or worked. Include the
versions that got worse (`kqk_v4` fell from 971 to 556: say why).

## Rule changes for round 2 (from `LOOP.md`)

1. Report program length in **syntax-tree nodes** (`ast.walk` count after removing
   docstrings) next to bytes. Nodes are the official measure from now on.
2. **Lookahead limit.** A program may look at the positions after its own move and after the
   opponent's replies, as `kqk_v5` does, and no deeper. No recursion, no search loops, no
   memo tables. A program that searches is a solver, and solvers live in `05-solver`. Make
   the harness enforce this as far as it reasonably can and state what it cannot detect.
3. **Exceptions at full price.** A program may contain an explicit table of position to move;
   every node and byte of it counts in the length.

## Step 1: whole-class proofs instead of samples

The checker verifies every entry of a certificate, so one certificate holding the union of
the expansions from many roots proves a win from every position in it. Add
`harness.py expand-all <program> --material KQK --board WxH --out file.cert`: expand from
**every** valid position of that material with White to move, sharing work between roots,
and write a single union certificate. Verify it with `mcheck.py`.

Run it for `kqk_v5` on 4x4, 5x5 and 6x6 (and 7x7, 8x8 in pieces of at most 4 minutes each if
time allows). Report, per board: valid White-to-move positions, entries in the certificate,
positions not covered (list up to five), maximum rank, expansion and checking time. If
entries equal valid positions, the program is a complete proven strategy for that board.

## Step 2: is the potential a ranking function?

For the symbolic step planned next, we need to know whether the potential in `kqk_v5`
decreases along play. Add `harness.py audit-rank`: over the union certificates, for every
entry `p`, the program's move `m` and every reply `r`, compare `_pot(p)` with `_pot(p.m.r)`.
Report how many two-ply steps strictly decrease, stay equal or increase, with up to five
examples of each non-decreasing kind. If it is not a ranking as written, try to find a
variant of the potential that is (keeping full coverage) and report both.

## Step 3: KRK

Score `krk_v4` to `krk_v6`. Then apply what worked for the queen: a single potential with the
two-ply rule. Iterate at least three more times; log each. Target: full coverage on the
1000-root family, then Step 1 and Step 2 for the rook as well.

## Report

Update `REPORT.md` after each step. The table that matters: for `kqk` and `krk`, per board
size: coverage, entries, maximum rank, and the single program length in nodes and bytes.
State plainly whether length had to grow with the board. List under "Tools wanted" anything
that would help the symbolic step.
