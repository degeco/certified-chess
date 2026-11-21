# 08-checker2: second, independent certificate checker (Go, standard library only)

Read `../AGENTS.md` and `../design/SPEC.md` (v1.1) first. Write only inside `08-checker2/`.

## Goal

Every result in this project rests on one checker, `03-checker`. A second checker, written
from the spec alone in another language, lets us compare verdicts on every certificate. A
disagreement between the two is a bug in one of them or a hole in the spec, and finding it
is the purpose of this folder. It also removes the speed limit of the Python checker.

## Independence rules

- Implement the rules and the checking from `../design/SPEC.md` only.
- Do **not** read any source code in `../02-engine/`, `../03-checker/`, `../04-tablebase/`,
  `../05-solver/`, `../07-strategies/`. You may read their certificate files (`*.cert`).
- You may **run** `../02-engine/bin/mchess` and `python3 ../03-checker/mcheck.py` as black
  boxes to compare outputs. You may not copy their behaviour where it contradicts the spec:
  if they disagree with your reading of the spec, keep your reading and report it.

## Deliverables

- `mcheck2` (built by `make`, tested by `make test`), same interface as the first checker:
  - `mcheck2 verify <file.cert>` prints `VALID` or `INVALID` on the first line, then
    `claim:`, `root:`, `entries:`, `max_rank:`, `seconds:` lines when valid, or the first
    violating entry and the reason when invalid. Exit 0 for valid, 1 for invalid. Never
    crash on malformed input.
  - `mcheck2 moves "<position>"`: one line per legal move, sorted, `<move>\t<position>`.
  - `mcheck2 batch`: one position per stdin line, prints
    `<position>\t<m1>:<pos1>|<m2>:<pos2>|...` sorted by move, or `<line>\tERROR`.
  - `mcheck2 perft "<position>" <depth>`.
- `compare.sh`: runs both checkers on every `*.cert` under a directory and prints the number
  of agreements and each disagreement with both verdicts.

## Tests that must pass

- 8x8 perft, exact: start position 20, 400, 8902, 197281, 4865609;
  `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -` 48, 2039, 97862, 4085603;
  `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -` 14, 191, 2812, 43238, 674624;
  `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -` 6, 264, 9467, 422333;
  `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -` 44, 1486, 62379, 2103487;
  `r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - -` 46, 2079, 89890, 3894594.
- Position validity exactly as SPEC section 3, with a test for each rejection rule.
- Black-box move comparison: for each of 3x3, 3x4, 4x4, 4x5, 5x5, 5x6, 6x6, 8x8, take
  `mchess random <W> <H> 3000 <seed>` and require identical `batch` output from `mcheck2` and
  `mchess`.
- Verdict comparison on existing certificates: all `*.cert` under `../04-tablebase/results/`
  and `../05-solver/certs/` (a seeded sample of 2000 if there are more), both checkers.
- Verdict comparison on mutated certificates: from 200 valid certificates make at least ten
  kinds of single mutation each (drop a line, change a move to another legal move, change a
  rank, swap the claim kind, swap the claimed side, duplicate a line, corrupt a position,
  change the root, add a blank line, reorder lines). Both checkers must give the same
  verdict on every mutant. Reordering lines must not change the verdict.

## Report

`REPORT.md`: the test output, the comparison counts, every disagreement with your analysis
of which side the spec supports, anything in the spec you found ambiguous, and verification
speed in entries per second next to the Python checker's on the same files.
