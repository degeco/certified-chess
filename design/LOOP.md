# LOOP v1: propose, verify, score, repeat

## Why

Recent AI-assisted mathematics works by one pattern: an untrusted proposer generates many
candidates, a trusted evaluator accepts or rejects each one mechanically, and the survivors
seed the next round. Proof search against a proof-assistant kernel and program search against
an automatic scorer are both instances. `01-survey` is asked to document the current state of
these methods from primary sources; this file fixes how we use the pattern here.

Our trusted evaluator already exists: `03-checker`. What was missing is a kind of candidate
worth iterating on. Flat certificates are found by search and cannot be improved by thought.
**Strategy programs can.**

## Strategy programs

A strategy program is a small pure function that, given a position with the prover to move,
returns the prover's move. Together with a root and a claim it *is* a proof, in compressed
form:

1. Expand: starting from the root, follow the program at prover positions and all legal
   replies at opponent positions, collecting every prover position reached.
2. The collected positions with the program's moves form a flat SPEC section 4 certificate
   (ranks for WIN claims are computed from the expansion; a cycle means the claim fails).
3. `03-checker` verifies the flat certificate.

Nothing about the program is trusted. A wrong program simply produces a certificate the
checker rejects, or an expansion that never closes. Soundness rests on the checker alone.

One program can be run on many roots and on many board sizes. A program that mates with king
and queen on every board from 4x4 to 8x8 is a single short text standing for millions of
certificate entries, and it is the first kind of object in this project that does not grow
with the board.

## What we measure

For a program `P`, a claim, and a set of roots `R` (an ensemble, as in SPEC section 5):

- **coverage**: share of roots in `R` whose expansion closes and whose certificate is `VALID`;
- **length**: size of the program in bytes after stripping comments and blank lines;
- **entries**: total flat certificate entries over the covered roots;
- **compression** = entries / length.

Hypothesis H2 (to be tested): for natural families of positions there are programs whose
length stays bounded while board size and entries grow. If H2 fails for simple endgames, it
fails for chess. If it holds, the question becomes how far up the piece count it survives.

## The loop

Each round an agent gets a target family, the current best program and its failures, and the
scoreboard. It proposes new programs; the harness scores them; only checker-verified numbers
enter the scoreboard. A round ends with a written entry in `07-strategies/LOG.md`: what was
tried, what the scores were, what failed and why. Failed ideas are kept.

A program may not embed a table of positions: it must be written from rules and geometry. The
harness enforces a length limit per family, and length is part of the score, so memorising
is both forbidden and unprofitable.

## Prior work (from `01-survey/transfer.md`, round 2)

This loop is not new in its parts, and the reports must say so:

- A king-and-rook strategy has already been proven correct for every `n x n` board with
  `n >= 4`, in Isabelle/HOL with Z3, by keeping strategy, invariant and ranking inside linear
  integer arithmetic (Marić, Janičić, Maliković; reported as verified by the survey). The
  symbolic step below is therefore known to be possible for that endgame.
- Induction of compact rules for endgames from tablebases is decades old, and a 2026 preprint
  (Pavlov) reports decision trees plus exception tables for all 3 to 6 piece endgames.
- Program search against an automatic scorer is the FunSearch and AlphaEvolve pattern.

What is open, and what this project can measure: whether proposing strategy, invariant and
ranking can be automated by agents, how program length behaves across endgames and board
sizes (H2), and how far up the piece count the approach survives.

## Planned for round 2 (do not apply in round 1)

1. **Exceptions at full price.** A program may carry an explicit exception table, with every
   byte of it counted in the length. This tests whether a short rule plus a few tactical
   exceptions beats a longer pure rule.
2. **Symbolic check.** For the best program of a family, state an invariant and a ranking in
   linear integer arithmetic over piece coordinates and board size, and discharge the two-ply
   closure conditions with an SMT solver, for all board sizes at once.

## Lessons taken from the large formal proofs of autumn 2026

Read from press reports and two arXiv papers on 2026-11-21; the Riemann-hypothesis claim of
20 November was machine-checked but not yet accepted by mathematicians at that date.

1. **Toy model first.** The reported workflow settled the approach on a simplified model before
   the real problem. Our small boards play that role; a method is not moved to a larger board
   before it is clean on the smaller one.
2. **Several independent checkers.** That proof was replayed by more than one kernel
   implementation. We have one checker. A second, written in another language by another
   model, comparing verdicts on every certificate, is cheap and is the next trust step.
3. **The statement is the residual risk.** A checker cannot tell whether what was proven is
   what was meant. For us the statement is the rules: two independent rule implementations,
   perft against published counts, and the idealised-game caveat on every result.
4. **Agents are good at local, checkable feedback and weak at choosing definitions**
   (Ilin and Nugent, arXiv 2606.13925). So the designer fixes definitions: families, scoring,
   the language invariants are written in. Agents fill in against the checker.
5. **A gate is only as good as its target** (same paper). Program length in bytes can be gamed
   by short names and dense formatting. From round 2 length is counted in syntax-tree nodes.
6. **Generated proofs are unreadable; compression is separate work.** The readable account
   came afterwards and from people. Finding a proof and shrinking it are scored separately.

## Honest limits

- Checking a strategy program by expansion still costs time proportional to the entries. This
  loop compresses the *description* of a proof, not yet the *work* of checking it. Checking
  without enumeration needs a symbolic step (proving that a program's invariant is closed
  under all moves for every board size at once). That is the round after this one and it only
  makes sense for programs this loop has shown to exist.
- Results hold for the idealised game of SPEC section 2 (no 50-move rule).
