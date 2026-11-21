# 06-complexity: state-space size per board

Status: ready. `02-engine` passes its own tests (reproduced by the designer); the differential test against `03-checker` is still pending, so a rules fix may require rerunning your experiments. Keep every experiment rerunnable with one command.

Read `../AGENTS.md`, `../design/SPEC.md` and `../02-engine/API.md` first. Link against the
`02-engine` library. Write only inside `06-complexity/`.

## Goal

Supply the denominator for hypothesis H1: how many positions each board has. Without it,
certificate sizes mean nothing.

## Deliverables

- `reach`: exact count of positions reachable from a start position by breadth-first search
  with a visited set, for as long as it fits in 4 GB; per-depth counts; stops cleanly at the
  limit and reports the depth reached.
- `estimate`: for boards where exact counting fails, an unbiased sampling estimate of the
  number of legal positions with a confidence interval. Describe the sampling scheme and why
  it is unbiased; "legal" here means reachable-looking by static rules (kings not adjacent,
  side not to move not in check, pawn counts and ranks possible), and the gap between that
  and true reachability must be stated, not ignored.
- A table in `REPORT.md` for `mini4x4`, `mini4x5`, `mini5x5` and 6x6, with exact counts where
  possible and estimates elsewhere, plus the same method applied to 8x8 at reduced sample
  size and compared with the published estimate recorded in `../01-survey/sources.md`.

Validate the estimator on a board small enough to count exactly before trusting it anywhere
else.
