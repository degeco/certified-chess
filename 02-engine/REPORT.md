# `02-engine` Report

> **Rules caveat (SPEC §2):** This engine implements the idealised game without the 50-move rule, threefold-repetition rule, or insufficient-material adjudication. Under FIDE 50/75-move rules some long wins become draws; any game values proved using this engine apply to the idealised game.

## What Was Built

- Library in `src/` (C++17, zero external dependencies, bitboard + 64-bit Zobrist hash):
  - `src/types.hpp`: `Color`, `PieceType`, `CastlingRight`, `Move`, square helpers (`3x3` to `8x8`).
  - `src/attacks.hpp`, `src/attacks.cpp`: precomputed attack rays, between/line masks, castling masks, and deterministic Zobrist keys (including board dimensions `W x H`).
  - `src/position.hpp`, `src/position.cpp`: `Position` parsing/canonical formatting (with legal-en-passant canonicalization), direct legal move generation, `make_move`, `in_check`, `status` (`ONGOING`/`CHECKMATE`/`STALEMATE`), `perft`, and `divide`.
  - `src/mchess.hpp`: umbrella header.
- CLI in `src/main.cpp` building `bin/mchess` with subcommands:
  - `perft "<position>" <depth>`
  - `divide "<position>" <depth>`
  - `moves "<position>"`
  - `batch`
  - `random <W> <H> <count> <seed>`
- `Makefile`: builds `build/libmchess.a`, `bin/mchess`, and `build/test_mchess` with `-O2 -std=c++17 -Wall -Wextra` (zero warnings).
- `tests/test_main.cpp`: 8x8 perft suite, mini-board unit tests (`3x3`, `4x4`, `4x5`, `5x5`, `8x7`), canonical FEN & pinned-`ep` tests, invalid-FEN rejection, and Zobrist hash consistency checks.
- `API.md`: one-page usage guide for downstream C++ consumers.

## How to Build and Test

```sh
cd /home/dege/chess/02-engine
make clean && make -j4 && make test
```

Additional CLI checks run:

```sh
./bin/mchess perft "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -" 3
./bin/mchess divide "rqkr/pppp/PPPP/RQKR w - -" 2
./bin/mchess moves "rqkr/pppp/PPPP/RQKR w - -"
printf "rqkr/pppp/PPPP/RQKR w - -\n3/1qk/K2 w - -\ninvalid fen\n" | ./bin/mchess batch
diff -u <(./bin/mchess random 8 8 200 777) <(./bin/mchess random 8 8 200 777)
./bin/mchess random 4 4 200 777 | ./bin/mchess batch | grep -c ERROR || true
time ./bin/mchess perft "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -" 6
```

## Actual Test Output

```
g++ -O2 -std=c++17 -Wall -Wextra -Isrc tests/test_main.cpp build/libmchess.a -o build/test_mchess
./build/test_mchess
8x8 perft suite: 16564718 nodes in 0.271791 s (60946576 nps)
mini4x4 (rqkr/pppp/PPPP/RQKR w - -): d1=6 d2=21 d3=157 d4=1005 d5=6856 d6=46987
mini4x5 (rqkr/pppp/4/PPPP/RQKR w - -): d1=4 d2=18 d3=116 d4=733 d5=5794 d6=45618
mini5x5 (rnbqk/ppppp/5/PPPPP/RNBQK w - -): d1=7 d2=53 d3=506 d4=4775 d5=52512 d6=572874
ALL TESTS PASSED
```

## Measured Numbers

- **8x8 perft suite** (all 6 positions in `TASK.md` matched exact reference counts; `perft` uses depth-1 bulk counting, cross-checked against `naive_perft` without bulk counting at `d3`):
  - Total: `16,564,718` nodes in `0.271791 s` (**60.95M nps**).
  - `std8` `d6`: `119,060,324` nodes in `2.202 s` real (`2.191 s` user, **54.1M nps**).
- **Mini-board perft (`d1` to `d6`)**:

| Name | Position | d1 | d2 | d3 | d4 | d5 | d6 |
|---|---|---:|---:|---:|---:|---:|---:|
| `mini4x4` | `rqkr/pppp/PPPP/RQKR w - -` | 6 | 21 | 157 | 1005 | 6856 | 46987 |
| `mini4x5` | `rqkr/pppp/4/PPPP/RQKR w - -` | 4 | 18 | 116 | 733 | 5794 | 45618 |
| `mini5x5` | `rnbqk/ppppp/5/PPPPP/RNBQK w - -` | 7 | 53 | 506 | 4775 | 52512 | 572874 |

- **Random + batch smoke check**: `diff` on two `random 8 8 200 777` runs returned exit code 0 (deterministic); `random 4 4 200 777 | batch` reported `0` `ERROR` lines.

## Known Gaps

- Differential testing against `03-checker` has not been run yet (by task isolation, `03-checker` was not read). The `mini4x4`, `mini4x5`, and `mini5x5` perft counts above await cross-checking against `03-checker`.

## Spec Issues

- **Trailing FEN fields & whitespace (`SPEC.md` §3):** Spec states readers must accept and ignore trailing halfmove/fullmove fields. Conservatively, `Position::parse` accepts 4, 5, or 6 single-space-separated fields where fields 5–6 (if present) contain only ASCII digits, and rejects >6 fields, non-digit trailing fields, or extra spaces.
- **Castling & placement consistency (`SPEC.md` §3):** Spec states castling rights are lost when king/rook moves or rook is captured, with "no further normalisation". Conservatively, `Position::parse` rejects FENs claiming `K`/`Q`/`k`/`q` if the corresponding king (`e1`/`e8`) or rook (`h1`/`a1`/`h8`/`a8`) is absent, and rejects out-of-order castling letters or adjacent digits (e.g. `44`) in placement.
- **En passant input validation (`SPEC.md` §3):** When an input FEN specifies a non-`-` `ep` square on 8x8, `Position::parse` rejects structurally impossible `ep` squares (wrong rank for `stm`, occupied target or behind-pawn square, or missing enemy pawn) and canonicalizes structurally valid `ep` squares to `-` when no legal en passant capture exists.
- **`mchess batch` output prefix (`TASK.md`):** On valid input lines (including 5/6-field FENs or non-canonical `ep`), `batch` prints the canonical `pos.to_fen()` before `\t`; unparsable/illegal lines print `<line>\tERROR`.
