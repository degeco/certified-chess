# 02-engine: fast rules engine (C++17)

Read `../AGENTS.md` and `../design/SPEC.md` first. Write only inside `02-engine/`.
Do not read `../03-checker/`: the two rule implementations must stay independent.

## Goal

A correct, reasonably fast implementation of the game family in SPEC section 2, as a library
the solver, tablebase and complexity work will link against, plus a small CLI.

## Deliverables

- `src/` library: position type for boards from 3x3 to 8x8, parsing and canonical printing of
  position strings (SPEC section 3, including the legal-en-passant rule for the `ep` field),
  legal move generation, make move, in-check, terminal detection (checkmate / stalemate),
  a 64-bit position hash.
- `Makefile`: `make` builds `bin/mchess`, `make test` runs every test. Flags `-O2 -std=c++17
  -Wall -Wextra`, no external dependencies.
- CLI `bin/mchess`:
  - `mchess perft "<position>" <depth>` prints the node count.
  - `mchess divide "<position>" <depth>` prints `move count` per root move, sorted by move.
  - `mchess moves "<position>"` prints one line per legal move, sorted by move string:
    `<move>\t<resulting canonical position>`.
  - `mchess batch` reads one position per line on stdin and for each prints
    `<position>\t<m1>:<pos1>|<m2>:<pos2>|...` with moves sorted; an illegal or unparsable
    input line prints `<line>\tERROR`.
  - `mchess random <W> <H> <count> <seed>` prints `count` positions reached by random legal
    play from random legal piece placements on a WxH board, deterministic in the seed.
    These feed the differential test against the checker.
- `API.md`: one page on how other C++ code uses the library.

## Tests that must pass

8x8 perft, exact values:

| Position | d1 | d2 | d3 | d4 | d5 |
|---|---|---|---|---|---|
| `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -` | 20 | 400 | 8902 | 197281 | 4865609 |
| `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -` | 48 | 2039 | 97862 | 4085603 | |
| `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -` | 14 | 191 | 2812 | 43238 | 674624 |
| `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -` | 6 | 264 | 9467 | 422333 | |
| `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -` | 44 | 1486 | 62379 | 2103487 | |
| `r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - -` | 46 | 2079 | 89890 | 3894594 | |

Also required:

- Mini boards: hand-checked unit tests for pawn single step only, promotion on the last rank
  of a non-8 board, no castling, no en passant, check evasion, pins, stalemate and mate on
  3x3, 4x4 and 5x5.
- Canonical form: parse then print is the identity on canonical strings; the `ep` field is
  `-` when the double step allows no legal capture (include a pinned-capturer case).
- Hash: equal positions give equal hashes; make-move hash equals hash of the reparsed result.
- Record perft d1 to d6 for `mini4x4`, `mini4x5`, `mini5x5` in `REPORT.md`. No reference
  values exist for these; they will be cross-checked against `03-checker` later.

## Out of scope

Search, evaluation, tablebases. Keep the code simple enough to audit; correctness first,
speed second. Report perft speed (nodes per second) in `REPORT.md`.
