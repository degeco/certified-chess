# 08-checker2: second certificate checker (Go, standard library only)

Written from `design/SPEC.md` v1.1 only. No source from 02/03/04/05/07 was read. `mchess` and
`mcheck.py` were only run as black boxes, to compare outputs and to learn the `moves`/`batch`/`verify`
output formats.

Caveat that must stay visible: the game is the idealised one of the SPEC (no 50-move rule, no
repetition rule), so everything here is about that game.

## What was built

| File | Purpose |
|---|---|
| `rules.go` | Board, move generation, check detection, castling, en passant, position parsing and validity (SPEC section 3), canonical writer, perft |
| `cert.go` | Certificate parsing and checking (SPEC section 4), WIN and ATLEAST_DRAW, entries verified on 4 goroutines |
| `main.go` | CLI: `verify`, `moves`, `batch`, `perft` (same interface as `mcheck.py`) |
| `rules_test.go` | `go test`: exact perft numbers, one test per validity rejection rule, ep and castling successor tests |
| `blackbox.sh` | `mcheck2 batch` against `mchess batch` on `mchess random W H 3000 1` for 8 board sizes |
| `compare.sh` | Runs both checkers on every `*.cert` under a directory (optional seeded sample), prints agreements and every disagreement |
| `mutate.py` | Mutation comparison, 35 kinds of mutation (`--with-crlf` adds a 36th, see Disagreements) |
| `edge.sh`, `edge/` | 21 hand-made certificates (mate, stalemate, rank 0/1, wrong claim side, duplicate, extra fields, ...) |
| `speed.py` | Entries per second of both checkers on the same files |
| `logs/` | Raw output of every run quoted below |

Build and test (commands exactly as run; the whole of `make test` takes about 7 minutes because the
Python checker is slow, so it was run in pieces, each under 5 minutes):

```
cd /home/dege/chess/08-checker2
make                                     # builds ./mcheck2
make unit                                # go test: perft + validity + successors
make blackbox                            # ./blackbox.sh
make edge                                # ./edge.sh
./compare.sh ../05-solver/certs
./compare.sh ../04-tablebase/results 2000 1
python3 mutate.py 200 1                  # = make mutate
python3 mutate.py 200 1 --with-crlf      # includes the known CRLF disagreement
python3 speed.py
```

## Test results

### Unit tests (`logs/unit.txt`)
```
--- PASS: TestPerft8x8 (2.13s)
--- PASS: TestValidity (0.00s)
--- PASS: TestEPAndCastlingSuccessors (0.00s)
ok  	mcheck2	2.137s
```
`TestPerft8x8` is the exact list of TASK.md: all 6 positions, all depths (start position 20, 400, 8902,
197281, 4865609 included). `TestValidity` has a rejection test for each rule: no/two kings, pawn on
rank 1 and on rank H (both colours), opponent in check (both side-to-move values), castling off 8x8,
castling without king / rook / wrong colour rook / wrong order / duplicates / empty field, ep off 8x8,
ep without a legal capture, ep on the wrong rank, ep with a pinned capturing pawn, malformed
fields, non-maximal empty runs, ragged ranks, too narrow/too many ranks, bad characters, extra spaces,
bad trailing fields. Also checks that a double step sets the ep field only when a legal capture exists
and that capturing a rook removes the castling right.

### Black-box move comparison against `02-engine/bin/mchess` (`logs/blackbox.txt`)
```
3x3  OK   3000 positions
3x4  OK   3000 positions
4x4  OK   3000 positions
4x5  OK   3000 positions
5x5  OK   3000 positions
5x6  OK   3000 positions
6x6  OK   3000 positions
8x8  OK   3000 positions
```
`batch` output is byte-identical to `mchess batch` (seed 1). Not compared: behaviour on invalid input lines
(both print `<line>\tERROR`, seen on one example only).

### Verdicts on existing certificates
```
compared 12 of 12 certs under ../05-solver/certs: agree=12 (VALID=12 INVALID=0) disagree=0
compared 2000 of 3500 certs under ../04-tablebase/results: agree=2000 (VALID=2000 INVALID=0) disagree=0
```
(2000 is a seeded sample, `shuf` with seed 1.) All existing certificates are VALID, so they say nothing
about agreement on INVALID verdicts; the mutants do.

Note: the first run of `compare.sh` printed 405 "disagreements" (go rc=141). That was a bug in the
script (`| head -1` killed the writer with SIGPIPE), not in the checkers. The script now captures the whole
output first. The numbers above are from the fixed script.

### Mutated certificates (`logs/mutate.txt`, `logs/mutate_crlf.txt`)
200 valid source certificates (seeded sample of 04-tablebase and 05-solver, `python3 mutate.py 200 1`).
35 mutation kinds, 6197 mutants: both checkers give the same verdict (first line and exit code) on **all
6197**. Reordering and reversing the body: all 400 such mutants stay VALID in both checkers.

| kind | n | both VALID | both INVALID | disagree |
|---|---|---|---|---|
| all_ranks_zero | 200 | 173 | 27 | 0 |
| bad_move_text | 200 | 0 | 200 | 0 |
| blank_body / blank_end / blank_header | 200 each | 0 | 200 each | 0 |
| change_move (to another legal move) | 161 | 50 | 111 | 0 |
| comment | 200 | 0 | 200 | 0 |
| corrupt_entry | 200 | 14 | 186 | 0 |
| corrupt_root | 200 | 28 | 172 | 0 |
| drop_last_line / drop_line | 200 each | 0 | 200 each | 0 |
| dup_line / dup_line_other_move | 200 / 158 | 0 | all | 0 |
| empty / truncate | 200 each | 0 | 200 each | 0 |
| extra_field / missing_field / spaces_for_tabs / trailing_ws | 200 each | 0 | 200 each | 0 |
| header_variants | 200 | 0 | 200 | 0 |
| no_final_newline | 200 | 200 | 0 | 0 |
| rank_bad_format | 200 | 0 | 200 | 0 |
| rank_down / rank_zero | 27 each | 7 | 20 | 0 |
| rank_up | 200 | 11 | 189 | 0 |
| reorder / reverse | 200 each | 200 | 0 | 0 |
| root_flip_stm | 200 | 49 | 151 | 0 |
| root_other_entry / root_successor | 200 each | 200 | 0 | 0 |
| swap_kind / swap_side | 200 each | 0 | 200 each | 0 |
| swap_ranks | 24 | 0 | 24 | 0 |
| swap_two_moves | 200 | 8 | 192 | 0 |

With `--with-crlf` (6397 mutants) there are **200 disagreements, all of kind `crlf`**, see below.

### Hand-made edge certificates (`logs/edge.txt`, `./edge.sh`)
`edge certs: 21 compared, all agree`. Covers: root stalemated or mated with the opponent to move,
for WIN and ATLEAST_DRAW of both sides (WIN with a stalemated root is INVALID, ATLEAST_DRAW is VALID,
ATLEAST_DRAW for the mated prover is INVALID); mate-in-1 with rank 0 and rank 1; ATLEAST_DRAW with rank 1
(INVALID); wrong claim side; wrong move; duplicate; promotion letter in upper case; trailing fields in
root or entry position (INVALID); entry with other board size; missing root entry; no final newline.

## Disagreements and analysis

**Open: CRLF files.** `03-checker` accepts a certificate whose lines end in `\r\n` (and even a file
with bare `\r` as the only line break); `mcheck2` rejects it. Cause (my reading, the Python source was
not read): the Python checker opens the file in text mode with universal newlines. I keep my reading,
which the SPEC supports: a line is terminated by `\n`, so `\r` stays in the last field of the line and then
the rank is not "a non-negative decimal integer without sign or leading zeros", and in the header
`#cert v1\r` is not `#cert v1`. Also "Writers must emit this canonical form exactly". Those 200 mutants
(one per source certificate) are the only remaining disagreement. Since a failing test must not be
hidden, `make mutate` excludes kind `crlf` explicitly and `--with-crlf` runs it and exits 1.
Other line-break characters (form feed, NEL U+0085, U+2028) and trailing space: both reject
(`/tmp` probes, checked once, not in the test suite).

No other disagreement was found. Neither checker is shown wrong by the comparisons: both use
independently derived rules and agree on move generation, validity and all verdicts above.

## Things in the SPEC that are ambiguous (my reading in brackets)

1. **Final newline and line endings of a certificate file** are not specified. [Only `\n` terminates a
   line; a missing newline after the last line is accepted, because the SPEC never requires it; `\r` is not
   a line break.] My first version rejected a missing final newline; `03-checker` accepts it, nothing in
   the SPEC supports rejection, so I changed it.
2. **Validity of `ep`.** Section 3 says "`ep` well formed as described above" and that it is "set only if at
   least one legal en-passant capture exists". [A reader rejects an `ep` field for which there is no legal
   capture. In addition I require that the pawn that "just moved" stands on the square behind the target and
   that the square it came from (rank 7 for White to move, rank 2 for Black to move) is empty, because
   otherwise no double step can have produced the position.] The extra condition is stricter than the SPEC
   text. No comparison exercised it (hypothesis: the `mchess random` positions never have such an `ep`
   field); it can be removed if the lead decides otherwise.
3. **Trailing halfmove/fullmove fields.** [Accepted only as exactly two further decimal-digit fields (so 4
   or 6 fields in total) in `moves`, `batch`, `perft`. In a certificate, positions must have exactly 4
   fields, because entries and root must be canonical.]
4. **"Rights are lost when the king or that rook moves or the rook is captured".** [Implemented as: any
   move from or to a1, e1, h1, a8, e8, h8 clears the rights tied to that square. This is equivalent in valid
   positions because a right can only exist while king and rook stand there.]
5. **Mini rules on non-square boards such as 8x5 or 5x8.** The SPEC says "any other size" is mini, so the
   double step, ep and castling exist only when both dimensions are exactly 8. [Followed literally.]
6. **ATLEAST_DRAW root, opponent to move, opponent has no legal reply.** Vacuously valid by the SPEC (the
   opponent is mated or stalemated, the prover is not in danger). [Accepted.] For WIN the same root is valid
   only if the opponent is in check.
7. **Ranks.** No upper limit is given. [Compared as strings of digits (length, then lexicographic) so any
   length works, no overflow; rank strings longer than 1000 digits are rejected as a practical limit.]
8. **Entry position order / "first violating entry".** The SPEC gives no order. [The checker reports the first
   failing entry in file order; parse errors (anything wrong with the form of the file) are reported before
   rule violations.] Verdicts do not depend on this.

## Speed (same files, `logs/speed.txt`)

Measured with other agents' jobs running on the same 4 cores (load average 11.3 at start), so the wall
times are noisy; CPU time of the child processes is the more reliable column. Includes process start-up.

| Set | Checker | entries | CPU s | wall s | entries / CPU s | entries / wall s |
|---|---|---|---|---|---|---|
| 3 large solver certs (37088 entries) | python | 37088 | 9.01 | 11.79 | 4118 | 3146 |
| | go, 4 threads | 37088 | 0.47 | 0.71 | 78660 | 52162 |
| | go, GOMAXPROCS=1 | 37088 | 0.47 | 0.53 | 79353 | 69986 |
| 300 small 5x5 tablebase certs (31742 entries) | python | 31742 | 30.48 | 32.13 | 1042 | 988 |
| | go, 4 threads | 31742 | 0.96 | 1.23 | 33132 | 25899 |
| | go, GOMAXPROCS=1 | 31742 | 0.85 | 1.24 | 37148 | 25599 |

About 19x (large files) and 32x (small files, one process start per file) on CPU time. Single-threaded Go is
as fast as 4 threads on these files, so the goroutines buy nothing at this size; they are kept for larger
certificates (not measured). 8x8 perft: start position depth 5 and Kiwipete depth 4 run in about 1 s each
(`./mcheck2 perft ... 4`, 0.99 s wall for Kiwipete depth 4, a single measurement, machine load not recorded).

## Known gaps

- `make test` was never run as one command (about 7 minutes); each of its parts was run and passed as
  listed above, apart from the CRLF kind that is excluded from `make mutate` on purpose.
- All 3512 existing certificates are VALID; INVALID agreement rests on mutants and the 21 edge certificates.
  The mutants were produced with `mchess moves` for "another legal move".
- The ep origin-square rule (ambiguity 2) is untested by differential testing; a random position with a
  non-canonical `ep` field would reveal a difference between the checkers.
- No cross-check against positions with invalid placement from `batch` beyond the unit tests and the
  mutants (`corrupt_entry`, `corrupt_root`).

## Tools wanted

None.
