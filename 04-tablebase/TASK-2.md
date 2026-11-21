# 04-tablebase, round 2: finish and report

Round 1 was cut off by the 50-minute session limit while waiting on a 22-minute run of
`tbgen h1 5x5`, so no `REPORT.md` was written. The code and most results are there. Read
`../AGENTS.md` again (it has a new "Time" section) and `TASK.md`, then finish. Do not rebuild
or rerun what already exists unless a check fails.

## State found by the lead session

- `results/tables_{3x3,4x4,4x5,5x5}.tsv`: 66 signatures each. `results/tables_8x8.tsv`: KQK,
  KRK, KPK with longest wins of 19, 31 and 55 plies.
- `results/h1.tsv`: 131,146 rows. 3x3, 4x4 and 4x5 look complete; 5x5 stopped at 22,633 rows.
- No `REPORT.md`. No record of how many certificates `mcheck.py` verified.

## Do, in this order, writing each result into `REPORT.md` as you go

1. Write `REPORT.md` now with what round 1 built and how to build and test it.
2. Run `make test` and the internal consistency pass on every table; record the output.
3. Finish the 5x5 part of `results/h1.tsv` in pieces of at most 4 minutes each, one signature
   or a few per command, with fewer samples if needed (state the number used). List which
   5x5 signatures are complete, partial or missing. Do not duplicate rows already present.
4. Verification count: run `../03-checker/mcheck.py verify` (now SPEC v1.1) on a seeded random
   sample of at least 300 certificates spread over all four boards and both claim kinds.
   Report how many were `VALID`. Any `INVALID` is the most important finding of the round:
   give the file and the checker's reason and stop to analyse it.
5. The H1 summary table: per board and claim kind (WIN, ATLEAST_DRAW), over all sampled
   roots: number of roots, median, mean, 90th percentile and maximum of certificate entries,
   and the same for entries divided by table positions. Then one paragraph, plain: how does
   certificate size relative to table size change from 3x3 to 5x5, and how do draws compare
   with wins? Give numbers, not adjectives. If the data do not support a conclusion, say so.
6. The comparisons asked for in `TASK.md`: 8x8 longest mates against `../01-survey/` if the
   values are there, pawnless 3x3 and 3x4 totals against `../01-survey/small-boards.md` where
   comparable. Say exactly which numbers matched, which did not, and which could not be
   compared.

Keep every command under 5 minutes. Finish with the "Known gaps" and "Tools wanted" sections.
