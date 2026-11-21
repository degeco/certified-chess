# Report: `04-tablebase`

Values reported here are for the idealised game in [SPEC.md](file:///home/dege/chess/design/SPEC.md) (infinite play is a draw; no 50/75-move rule or repetition rule).

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
- [scripts/analyze_and_verify.py](file:///home/dege/chess/04-tablebase/scripts/analyze_and_verify.py): verification and summary script for `.cert` directories, [results/tables_3x3.tsv](file:///home/dege/chess/04-tablebase/results/tables_3x3.tsv) .. [results/tables_8x8.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8.tsv), [results/h1.tsv](file:///home/dege/chess/04-tablebase/results/h1.tsv), and [results/h1_summary.tsv](file:///home/dege/chess/04-tablebase/results/h1_summary.tsv).

## How to Build and Test

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

- `3x3`: all 66 signatures verified (exit code 0).
- `4x4`: all 66 signatures verified (exit code 0).
- `4x5`: all 66 signatures verified (exit code 0).
- `5x5`: all 66 signatures verified (exit code 0).
- `8x8`: `VERIFIED 8x8 KQK`, `VERIFIED 8x8 KRK`, `VERIFIED 8x8 KPK` (exit code 0).

## Tablebase Summary

From [results/tables_3x3.tsv](file:///home/dege/chess/04-tablebase/results/tables_3x3.tsv), [results/tables_4x4.tsv](file:///home/dege/chess/04-tablebase/results/tables_4x4.tsv), [results/tables_4x5.tsv](file:///home/dege/chess/04-tablebase/results/tables_4x5.tsv), [results/tables_5x5.tsv](file:///home/dege/chess/04-tablebase/results/tables_5x5.tsv), and [results/tables_8x8.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8.tsv):

| Board | Sigs | Index positions | Legal positions | Wins | Draws | Losses | Max win / loss DTM (plies) | Gen time | Table bytes |
|---|---|---|---|---|---|---|---|---|---|
| `3x3` | 66 | 235,680 | 68,478 | 14,148 (20.66%) | 33,396 (48.77%) | 20,934 (30.57%) | 17 / 18 (`KKBP`) | 0.16 s | 707,040 |
| `4x4` | 66 | 3,596,128 | 1,664,096 | 472,160 (28.37%) | 657,152 (39.49%) | 534,784 (32.14%) | 51 / 52 (`KRKB`) | 3.82 s | 10,788,384 |
| `4x5` | 66 | 9,962,680 | 5,227,644 | 1,554,744 (29.74%) | 1,955,904 (37.41%) | 1,716,996 (32.84%) | 57 / 58 (`KRKB`) | 12.21 s | 29,888,040 |
| `5x5` | 66 | 25,939,680 | 14,931,258 | 4,468,750 (29.93%) | 5,578,212 (37.36%) | 4,884,296 (32.71%) | 61 / 62 (`KRKB`) | 41.08 s | 77,819,040 |
| `8x8` | 3 (`KQK`,`KRK`,`KPK`) | 1,375,123 | 1,099,127 | 444,733 (40.46%) | 154,086 (14.02%) | 500,308 (45.52%) | 55 / 56 (`KPK`) | 3.31 s | 4,125,369 |

## 5x5 H1 Completion

Round 1's interrupted run left 39 complete signatures, 1 partial (`KNKQ` with 200 WIN, 160 `ATLEAST_DRAW`, and 1 truncated line), and 26 missing signatures. In Round 2, the partial `KNKQ` rows and truncated line were removed and `results/h1.tsv` was completed in batches under 4 minutes each with zero duplicates and zero malformed lines (143,808 total rows across all 4 boards):

- **Complete at 200 samples (58 signatures; 200 won roots or all won roots if fewer, and 200 drawn roots = 400 `ATLEAST_DRAW` rows):** `KK`, `KKQ`, `KKR`, `KKB`, `KKN`, `KQK`, `KRK`, `KBK`, `KNK`, `KKP`, `KPK`, `KKQQ`, `KKQR`, `KKRR`, `KKQB`, `KKRB`, `KKBB`, `KKQN`, `KKRN`, `KKBN`, `KKNN`, `KQKQ`, `KQKR`, `KQKB`, `KQKN`, `KQQK`, `KRKQ`, `KRKR`, `KRKB`, `KRKN`, `KQRK`, `KRRK`, `KBKQ`, `KBKR`, `KBKB`, `KBKN` (72 WIN + 400 ATLEAST_DRAW), `KQBK`, `KRBK`, `KBBK`, `KNKQ`, `KQNK`, `KRNK`, `KKQP`, `KKRP`, `KQPK`, `KRPK`, `KKPP`, `KPPK`, `KKBP`, `KKNP`, `KQKP`, `KRKP`, `KPKQ`, `KPKR`, `KBPK`, `KNPK`, `KPKP`, `KNKR`.
- **Complete at 100 samples (3 signatures; to stay under 4 min per command):** `KBNK` (100 WIN, 200 ATLEAST_DRAW), `KNNK` (100 WIN, 200 ATLEAST_DRAW), `KNKB` (all 72 WIN, 200 ATLEAST_DRAW).
- **Complete at 50 samples (5 signatures; to stay under 4 min per command):** `KNKN` (50 WIN, 100 ATLEAST_DRAW), `KBKP` (50 WIN, 100 ATLEAST_DRAW), `KNKP` (50 WIN, 100 ATLEAST_DRAW), `KPKB` (50 WIN, 100 ATLEAST_DRAW), `KPKN` (50 WIN, 100 ATLEAST_DRAW).
- **Partial / Missing:** none (0 partial, 0 missing out of 66).

Reproducing a single-signature batch:

```bash
cd /home/dege/chess/04-tablebase
./bin/tbgen h1 5x5 --sig KNKR --samples 200 --out-tsv results/h1.tsv --append
```

## Certificate Verification (`03-checker/mcheck.py`, SPEC v1.1)

1. **Seeded stratified CLI sample (`random.Random(20261121)`):** 400 certificates (100 per board: 50 `WIN` and 50 `ATLEAST_DRAW` each from `results/certs_{3x3,4x4,4x5}` and `results/certs_5x5` + `results/certs_5x5_extra`) checked via `python3 ../03-checker/mcheck.py verify <file>`:
   - `3x3`: `100/100 VALID` (`50/50 WIN`, `50/50 ATLEAST_DRAW`), `0 INVALID`.
   - `4x4`: `100/100 VALID` (`50/50 WIN`, `50/50 ATLEAST_DRAW`), `0 INVALID`.
   - `4x5`: `100/100 VALID` (`50/50 WIN`, `50/50 ATLEAST_DRAW`), `0 INVALID`.
   - `5x5`: `100/100 VALID` (`50/50 WIN`, `50/50 ATLEAST_DRAW`), `0 INVALID`.
   - **Total:** `400/400 VALID` (`22.79 s`).
2. **Full saved-certificate sweep (`python3 scripts/analyze_and_verify.py` + `certs_5x5_extra`):** all `3,650/3,650` saved certificates (`2,000` `3x3`, `500` `4x4`, `500` `4x5`, `500` `5x5`, `150` `5x5_extra` including `KPKB`, `KNKP`, `KPKN`) returned `VALID`, `0` failed (`150,932` entries in the 3,500-cert sweep in `16.59 s`; `8.15 s` for `certs_5x5_extra`).
3. **8x8 spot check (`mcheck.py verify`):** `8x8 KQK` (`WIN w`, 43 entries), `8x8 KRK` (`WIN w`, 3,922 entries), and `8x8 KPK` (`ATLEAST_DRAW w` 7,311 entries, `ATLEAST_DRAW b` 3,330 entries) all returned `VALID`.

## H1 Summary Table

In [results/h1.tsv](file:///home/dege/chess/04-tablebase/results/h1.tsv), each won/lost root emits 1 `WIN` certificate and each drawn root emits 2 `ATLEAST_DRAW` certificates (`w` and `b`); per-board statistics below aggregate all emitted certificates of each claim kind (with `roots` and `certs` both shown):

| Board | Claim | Roots (Certs) | Entries med | Entries mean | Entries p90 | Entries max | Ratio med | Ratio mean | Ratio p90 | Ratio max |
|---|---|---|---|---|---|---|---|---|---|---|
| `3x3` | `WIN` | 10,666 (10,666) | 1.0 | 2.03 | 5.0 | 22 | 0.001453 | 0.002828 | 0.006410 | 0.049587 |
| `3x3` | `ATLEAST_DRAW` | 10,756 (21,512) | 5.0 | 16.34 | 40.0 | 248 | 0.005000 | 0.019138 | 0.051471 | 0.813559 |
| `4x4` | `WIN` | 11,728 (11,728) | 5.0 | 22.33 | 42.0 | 2,645 | 0.000252 | 0.001174 | 0.002632 | 0.066564 |
| `4x4` | `ATLEAST_DRAW` | 13,200 (26,400) | 87.0 | 1,027.04 | 1,996.1 | 20,687 | 0.004864 | 0.047748 | 0.140893 | 1.642523 |
| `4x5` | `WIN` | 11,808 (11,808) | 10.0 | 65.41 | 107.0 | 6,479 | 0.000144 | 0.001032 | 0.002154 | 0.053999 |
| `4x5` | `ATLEAST_DRAW` | 13,200 (26,400) | 205.0 | 3,708.23 | 9,423.1 | 122,524 | 0.004364 | 0.052198 | 0.202389 | 2.277398 |
| `5x5` | `WIN` | 10,994 (10,994) | 15.0 | 151.22 | 186.0 | 15,199 | 0.000079 | 0.000829 | 0.001666 | 0.044065 |
| `5x5` | `ATLEAST_DRAW` | 12,150 (24,300) | 435.5 | 10,309.94 | 30,728.1 | 377,448 | 0.004488 | 0.052977 | 0.206483 | 2.478645 |

From `3x3` to `5x5`, `WIN` certificate size relative to table size shrinks monotonically across every summary statistic: median ratio drops `18.4x` from `0.001453` (`3x3`) to `0.000079` (`5x5`), mean ratio drops `3.4x` from `0.002828` to `0.000829`, and 90th-percentile ratio drops `3.8x` from `0.006410` to `0.001666`, even as absolute mean `WIN` entries rise `74.5x` (`2.03` to `151.22`). By contrast, `ATLEAST_DRAW` certificates are much larger than `WIN` certificates (`68x` higher mean entries on `5x5`, `10,309.94` vs. `151.22`; `64x` higher mean ratio, `0.052977` vs. `0.000829`) and do not shrink cleanly as a fraction of table size: while median `ATLEAST_DRAW` ratio stays nearly flat (`0.005000` on `3x3` vs. `0.004488` on `5x5`), mean ratio rises from `0.019138` (`3x3`) to `0.047748` (`4x4`), `0.052198` (`4x5`), and `0.052977` (`5x5`), and 90th-percentile ratio rises from `0.051471` (`3x3`) to `0.206483` (`5x5`). Because 8 draw-heavy `5x5` signatures were sampled at 50 or 100 roots rather than 200, equal-signature weighting increases the `5x5` `ATLEAST_DRAW` mean further to `13,539.89` entries (ratio `0.062990`). Note also that `ATLEAST_DRAW` ratios can exceed `1.0` (up to `2.478645` on `5x5`) because pawn-promoting draw certificates include positions from child signatures' tables in addition to the root signature's table.

## Comparisons Against `../01-survey/`

- **8x8 longest mates (`KQK`, `KRK`, `KPK`):** [results/tables_8x8.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8.tsv) gives longest win/loss DTM of `19`/`20` plies for `KQK` (`8/8/8/5k2/8/8/1Q6/K7 w - -`), `31`/`32` plies for `KRK` (`7K/8/8/8/3k4/8/8/R7 w - -`), and `55`/`56` plies for `KPK` (`8/8/8/1k6/8/8/K5P1/8 w - -`). Searching `../01-survey/` found no published longest-mate values for 8x8 `KQK`, `KRK`, or `KPK`, so these values are **unchecked** and **could not be compared**.
- **Pawnless `3x3` totals vs. [small-boards.md](file:///home/dege/chess/01-survey/small-boards.md):** Our 45 pawnless 2–4 piece `3x3` signatures total `56,064` legal positions (`10,512` wins, `28,312` draws, `17,240` losses; `7,808` checkmates, `3,968` stalemates; `44,288` non-terminal; max win/loss DTM `13`/`14` plies). `../01-survey/small-boards.md` reports only Kryukov's **full 2–9 piece** `3x3` database totals (`54,687,564` NULP, `304,545,552` DB positions, max DTM `16` moves / `32` plies) with no 2–4 piece pawnless breakdown, so exact counts **could not be compared** (our 2–4 piece pawnless max DTM of `14` plies is within the 2–9 piece overall max of `32` plies).
- **Pawnless `3x4` totals vs. [small-boards.md](file:///home/dege/chess/01-survey/small-boards.md):** `04-tablebase` did not generate `3x4` tables (it generated `3x3`, `4x4`, `4x5`, `5x5`, and `8x8` `KQK`/`KRK`/`KPK`), and `../01-survey/small-boards.md` reports only Kryukov's **full 2–12 piece** `3x4` totals (`167,303,246,916` NULP across `184,756` ESMs, max DTM `43` moves / `85` plies) with no 2–4 piece pawnless subset. Thus `3x4` totals **could not be compared**.

## Known Gaps

- **Uneven `5x5` sample counts on 8 high-draw signatures:** 58 of 66 signatures used 200 won/drawn samples, 3 (`KBNK`, `KNNK`, `KNKB`) used 100, and 5 (`KNKN`, `KBKP`, `KNKP`, `KPKB`, `KPKN`) used 50 to keep each command under 4 minutes.
- **Certificate `certs_4x4/` and `certs_4x5/` signature breadth:** During Round 1, `--cert-limit 500` filled up on the first two signatures (`KK` and `KKQ`), whereas `certs_3x3/` spans 6 signatures (`KK`..`KQK`) and `certs_5x5/` + `certs_5x5_extra/` span 5 signatures (`KK`, `KKQ`, `KPKB`, `KNKP`, `KPKN`).
- **8x8 castling/EP indexing cutoff:** [src/indexer.cpp](file:///home/dege/chess/04-tablebase/src/indexer.cpp) only enumerates non-zero 8x8 castling/en-passant states when `base_size <= 5,000,000` (sufficient for 2–4 piece 8x8 signatures like `KPK`/`KRK`/`KQK`, not larger 8x8 signatures).
- **No `3x4` tables generated and no 5-piece tables generated:** `4x4`–`5x5` cover 2–4 pieces only; 5-piece signatures on `5x5` exceed single-run RAM/time budget without disk-backed/sharded retrograde or symmetry reduction.
- **Unchecked 8x8 longest-mate values:** `19` (`KQK`), `31` (`KRK`), `55` (`KPK`) are internally verified by `tbgen verify`, and spot-checked certificates pass `mcheck.py`, but no external reference was available in `../01-survey/`.

## Tools Wanted

- A faster compiled (C++/Rust) SPEC v1.1 certificate checker or streaming verifier: `mcheck.py` in Python verifies ~3,500 small certificates in `16.6 s`, which will bottleneck when verifying large `ATLEAST_DRAW` certificates (>100k entries) on `5x5` or 5-piece tables.
- A symmetry-reduced tablebase indexer (color/board reflection) if extending `4x4`/`5x5` to 5 pieces within the 4 GB RAM / 5-minute budget.

## Round 3: 8x8 & 6x6 Piece Ladder Ground Truth

### Engineering & Indexing Updates
- **8x8 `KPKP` en passant indexing ([src/indexer.cpp](file:///home/dege/chess/04-tablebase/src/indexer.cpp)):** Separated castling cutoff (`base_size <= 5,000,000`) from en passant enumeration on `8x8`. When both sides have pawns and `base_size > 5,000,000`, `TableIndexer` pre-filters the pawn pair placement before iterating king/piece squares, enumerating all `87,572` valid en-passant states for `8x8 KPKP` (`17,064,384` base + `87,572` EP = `17,151,956` total indices) in milliseconds. Castling rights remain unindexed for `8x8` tables with `base_size > 5,000,000` (closed under forward moves since castling rights can only be lost).
- **Performance & memory ([src/indexer.cpp](file:///home/dege/chess/04-tablebase/src/indexer.cpp), [src/tablebase.cpp](file:///home/dege/chess/04-tablebase/src/tablebase.cpp)):** Parallelized initialization and `verify` across up to 4 threads, added `select_nth_bit` and stack-buffer FEN formatting with `non_stm_in_check` prefilter, avoided loading grandchild tables during `build`/`verify`, and kept the `MCTBv001` `.tb` disk format unchanged for `05-solver` compatibility.
- **New `tbgen` subcommands ([src/main.cpp](file:///home/dege/chess/04-tablebase/src/main.cpp)):** Added `probe <WxH>`, `sample <WxH> <SIG> --value <W|D|L> --stm <w|b> --n <N> --seed <S>`, and `stats <WxH> <SIG...>`.

### Build Progress (In Progress)
- **`make test`:** All 26 unit tests pass (including `test_8x8_kpkp_ep_indexer`).
- **`6x6` tables:** All 39 ladder-closure signatures (`KK`, 10 3-piece, 28 4-piece + `KNNK`) built and verified via `tbgen build 6x6 ... --verify` in `2m1.4s` ([results/tables_6x6_ladder.tsv](file:///home/dege/chess/04-tablebase/results/tables_6x6_ladder.tsv)).
- **`8x8` Batch 1:** `KK`, 10 3-piece (`KQK`, `KRK`, `KBK`, `KNK`, `KPK`, `KKQ`, `KKR`, `KKB`, `KKN`, `KKP`), `KBBK`, `KNNK` built and verified in `1m1.4s` ([results/tables_8x8_batch1.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch1.tsv)).
- **`8x8` Batch 2:** `KBNK`, `KQKR` built and verified in `1m59.6s` ([results/tables_8x8_batch2.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch2.tsv)).
- **`8x8` Batch 3:** `KRKB`, `KRKN`, `KRKQ` built and verified in `2m46.1s` ([results/tables_8x8_batch3.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch3.tsv)).
- **`8x8` Batch 4:** `KQKQ`, `KQKB`, `KQKN` built and verified in `3m0.2s` ([results/tables_8x8_batch4.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch4.tsv)).
- **`8x8` Batch 5:** `KRKR`, `KBKQ`, `KBKR` built and verified in `3m50.8s` ([results/tables_8x8_batch5.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch5.tsv)).
- **`8x8` Batch 6:** `KBKB`, `KBKN`, `KNKB`, `KNKN` built and verified in `3m47.8s` ([results/tables_8x8_batch6.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch6.tsv)).
- **`8x8` Batch 7:** `KNKQ`, `KNKR` built and verified in `4m31.3s` ([results/tables_8x8_batch7.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch7.tsv)).
- **`8x8` Batch 8:** `KQKP`, `KRKP`, `KBKP` built and verified in `2m47.1s` ([results/tables_8x8_batch8.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch8.tsv)).
- **`8x8` Batch 9:** `KNKP`, `KPKQ`, `KPKR` built and verified in `4m57.3s` ([results/tables_8x8_batch9.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch9.tsv)).
- **`8x8` Batch 10:** `KPKB`, `KPKN` built and verified in `3m48.4s` ([results/tables_8x8_batch10.tsv](file:///home/dege/chess/04-tablebase/results/tables_8x8_batch10.tsv)).
