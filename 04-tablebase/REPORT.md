# Report: `04-tablebase`

## What Was Built (Round 1)

Retrograde endgame tablebase generator, verifier, and SPEC v1.1 certificate exporter in C++17, linked against `../02-engine/build/libmchess.a`:

- [Makefile](file:///home/dege/chess/04-tablebase/Makefile): builds `bin/tbgen` and `build/test_tbgen` with `g++ -O2 -std=c++17 -Wall -Wextra -pthread`.
- [src/signature.hpp](file:///home/dege/chess/04-tablebase/src/signature.hpp), [src/signature.cpp](file:///home/dege/chess/04-tablebase/src/signature.cpp): `MaterialSig` parsing, canonicalization (e.g. `KPRK` -> `KRPK`), dependency enumeration (captures, promotions, capture-promotions), and topological enumeration (`enumerate_signatures(4)` yields 66 2–4 piece signatures).
- [src/indexer.hpp](file:///home/dege/chess/04-tablebase/src/indexer.hpp), [src/indexer.cpp](file:///home/dege/chess/04-tablebase/src/indexer.cpp): combinatorial `TableIndexer` mapping `(board, piece placement, side to move, castling, ep)` bijectively to `uint32_t` indices (restricting pawns to ranks `2..H-1`, and indexing valid 8x8 castling/en-passant states when `base_size <= 5,000,000`).
- [src/tablebase.hpp](file:///home/dege/chess/04-tablebase/src/tablebase.hpp), [src/tablebase.cpp](file:///home/dege/chess/04-tablebase/src/tablebase.cpp):
  - `TableStore::ensure`: recursive dependency build, `.tb` binary disk cache (`MCTBv001`), retrograde WDL/DTM solver using quiet unmove generation (`for_each_quiet_predecessor`) and forward capture/promotion lookup into child tables.
  - `TableStore::verify`: independent forward-move consistency pass checking every legal and illegal index against `02-engine` `legal_moves()`.
  - `TableStore::export_certificates`: BFS extraction of `#cert v1` `WIN <side>` certificates (for `WIN`/`LOSS` roots) and paired `ATLEAST_DRAW w` + `ATLEAST_DRAW b` certificates (for `DRAW` roots, omitting prover-stalemate entries per SPEC v1.1).
- [src/main.cpp](file:///home/dege/chess/04-tablebase/src/main.cpp): CLI subcommands `build`, `build-all`, `dump`, `verify`, `cert`, `h1`.
- [tests/test_tbgen.cpp](file:///home/dege/chess/04-tablebase/tests/test_tbgen.cpp): unit tests for signature parsing/dependencies, indexer bijections, quiet unmove vs. forward move equality, table generation/verification, `.tb` save/load roundtrip, and certificate export.
- [scripts/analyze_and_verify.py](file:///home/dege/chess/04-tablebase/scripts/analyze_and_verify.py): script to run `../03-checker/mcheck.py` on sampled `.cert` files and summarize `tables_*.tsv` and `h1.tsv`.

### Existing Round 1 Artifacts in `results/` and `data/`

- `results/tables_{3x3,4x4,4x5,5x5}.tsv`: 66 signatures each (2–4 pieces).
- `results/tables_8x8.tsv`: `KQK`, `KRK`, `KPK`.
- `results/h1.tsv`: interrupted during `5x5` `KNKQ` in Round 1 (131,146 complete rows + 1 truncated trailing line).
- `results/certs_{3x3,4x4,4x5,5x5}/`: sampled `.cert` files saved during Round 1.

## How to Build and Test

Build `02-engine` (if not already built) and `04-tablebase`:

```bash
make -C /home/dege/chess/02-engine
make -C /home/dege/chess/04-tablebase all
make -C /home/dege/chess/04-tablebase test
```

Run the independent forward-consistency check on all generated tables:

```bash
cd /home/dege/chess/04-tablebase
for b in 3x3 4x4 4x5 5x5; do ./bin/tbgen build-all $b --max-pieces 4 --verify; done
./bin/tbgen verify 8x8 KQK && ./bin/tbgen verify 8x8 KRK && ./bin/tbgen verify 8x8 KPK
```

## Actual Test Output

`make test` (all 25 checks passed):

```text
./build/test_tbgen
[PASS] test_signatures (66 2-4 piece signatures)
[PASS] test_indexer_bijection 3x3 KQRK (index=6048, legal=1480)
[PASS] test_indexer_bijection 3x3 KPKP (index=504, legal=236)
[PASS] test_indexer_bijection 4x4 KQK (index=6720, legal=2996)
[PASS] test_indexer_bijection 4x4 KPK (index=3360, legal=2112)
[PASS] test_indexer_bijection 8x8 KPK (index=374976, legal=331352)
[PASS] test_indexer_bijection 8x8 KRK (index=500179, legal=399323)
[PASS] test_unmove_matches_forward 3x3 KK (edges=112)
[PASS] test_unmove_matches_forward 3x3 KQK (edges=368)
[PASS] test_unmove_matches_forward 3x3 KPK (edges=202)
[PASS] test_unmove_matches_forward 3x3 KPKP (edges=248)
[PASS] test_unmove_matches_forward 3x3 KQRK (edges=1168)
[PASS] test_unmove_matches_forward 4x4 KPK (edges=7202)
[PASS] test_unmove_matches_forward 8x8 KPK (edges=2125630)
[PASS] test_unmove_matches_forward 8x8 KRK (edges=4449145)
[PASS] verify 3x3 KK
[PASS] verify 3x3 KQK
[PASS] verify 3x3 KPK
[PASS] verify 3x3 KPKP
[PASS] verify 3x3 KQRK
[PASS] verify 4x4 KQK
[PASS] verify 4x4 KPK
[PASS] verify 4x4 KRKP
[PASS] save/load roundtrip 4x4 KPK
[PASS] cert export WIN/LOSS/DRAW
ALL TESTS PASSED
```

Internal consistency pass (`tbgen build-all <board> --max-pieces 4 --verify` and `tbgen verify 8x8 <SIG>`):

- `3x3`: all 66 signatures verified (exit code 0, 67 TSV lines including header).
- `4x4`: all 66 signatures verified (exit code 0, 67 TSV lines including header).
- `4x5`: all 66 signatures verified (exit code 0, 67 TSV lines including header).
- `5x5`: all 66 signatures verified (exit code 0, 67 TSV lines including header).
- `8x8`: `VERIFIED 8x8 KQK`, `VERIFIED 8x8 KRK`, `VERIFIED 8x8 KPK` (exit code 0).

## 5x5 H1 Coverage Status (Before Round 2 Completion)

Inspecting the Round 1 `results/h1.tsv` (131,146 complete rows + 1 truncated trailing line `5x5\tKNKQ\t`):

- **Complete (39 signatures, 200 won roots or all won roots if fewer, and 200 drawn roots = 400 `ATLEAST_DRAW` rows):** `KK`, `KKQ`, `KKR`, `KKB`, `KKN`, `KQK`, `KRK`, `KBK`, `KNK`, `KKP`, `KPK`, `KKQQ`, `KKQR`, `KKRR`, `KKQB`, `KKRB`, `KKBB`, `KKQN`, `KKRN`, `KKBN`, `KKNN`, `KQKQ`, `KQKR`, `KQKB`, `KQKN`, `KQQK`, `KRKQ`, `KRKR`, `KRKB`, `KRKN`, `KQRK`, `KRRK`, `KBKQ`, `KBKR`, `KBKB`, `KBKN` (72 WIN + 400 ATLEAST_DRAW), `KQBK`, `KRBK`, `KBBK`.
- **Partial (1 signature):** `KNKQ` (200 WIN rows, 160 `ATLEAST_DRAW` rows = 80 drawn roots, plus 1 truncated line).
- **Missing (26 signatures):** `KNKR`, `KNKB`, `KNKN`, `KQNK`, `KRNK`, `KBNK`, `KNNK`, `KKQP`, `KKRP`, `KKBP`, `KKNP`, `KQKP`, `KRKP`, `KBKP`, `KNKP`, `KPKQ`, `KPKR`, `KPKB`, `KPKN`, `KQPK`, `KRPK`, `KBPK`, `KNPK`, `KKPP`, `KPKP`, `KPPK`.

