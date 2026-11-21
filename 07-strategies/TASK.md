# 07-strategies: strategy programs as compressed proofs

Read `../AGENTS.md`, `../design/SPEC.md` (v1.1) and `../design/LOOP.md` first. Write only
inside `07-strategies/`. You may import `../03-checker/rules.py` and call
`../03-checker/mcheck.py`; do not modify them. Python standard library only.

## Part A: harness

- `harness.py expand <program.py> --claim "<WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b>"
  --root "<position>" --out file.cert [--max-entries N]`
  expands a strategy program as `LOOP.md` describes and writes a SPEC section 4 certificate.
  For WIN claims compute ranks from the expansion (longest distance to mate); report a cycle,
  a stalemate, an illegal or missing move, or the entry limit as a failure with the offending
  position. For ATLEAST_DRAW apply the prover-stalemate rule of SPEC v1.1.
- `harness.py score <program.py> --family <name>` runs the program on every root of a family,
  verifies each certificate with `mcheck.py verify`, and prints coverage, program length
  (bytes after stripping comments, docstrings and blank lines), total entries, compression,
  and up to five failing roots with the reason. It appends one row to `results/scores.tsv`.
- A strategy program is a Python file defining `move(pos) -> str`, where `pos` is a
  `rules.Position` with the prover to move. It may import only `rules`. The harness rejects
  programs that are longer than the family's limit, that import anything else, or that contain
  position strings or large literal tables.
- Families live in `families/<name>.json`: claim, length limit, and the list of roots.
  Generate the root lists with a script that is kept in the folder, seeded and rerunnable.
- Tests: `python3 -m unittest discover -s tests`. They must include a deliberately wrong
  program for each failure kind, and show that a program which is wrong on one root cannot
  get a `VALID` certificate for that root.

## Part B: first families and first programs

Write the programs yourself; this is the research part. Start simple and iterate.

1. `kqk`: White king and queen against the bare king, White to move, claim `WIN w`. Roots:
   200 random valid positions on each of 4x4, 5x5, 6x6, 7x7, 8x8. Length limit 4000 bytes.
   Goal: **one** program with full coverage on all five board sizes.
2. `krk`: the same with a rook. Length limit 6000 bytes.
3. `kk-draw`: bare kings, claim `ATLEAST_DRAW` for the side to move, as a harness sanity check.
4. `mini4x4-start`: root `rqkr/pppp/PPPP/RQKR w - -`, claim `WIN w`. `../01-survey/` reports a
   forced mate in 4; confirm or refute it through the checker.

Iterate on each family at least three times: look at the failing roots, change the idea, and
rescore. Record every round in `LOG.md`, including the ones that got worse.

## What to report

In `REPORT.md`: the scoreboard, and for `kqk` and `krk` a table by board size with coverage,
entries and maximum rank, next to the single program length. State plainly whether program
length had to grow with the board. That is the first evidence for or against hypothesis H2.
Also report how expansion time grows, since `LOOP.md` names it as the open limit.
