# 05-solver: proof search that emits certificates (C++17)

Status: ready. `02-engine` and `03-checker` (SPEC v1.1) are accepted and agree move for move on
about 130,000 positions. Note the v1.1 prover-stalemate rule for ATLEAST_DRAW certificates.

Facts from the other folders that shape this task (check them, do not assume them):

- `../01-survey/` reports `mini4x4` is a forced mate in 4 for White. Your solver should find
  it at once; if it does not, something is wrong.
- `../06-complexity/REPORT.md`: the reachable set of even `mini4x4` exceeds 1.6e8 positions,
  so no search here may assume it can store everything it visits. Bound every table.
- `../01-survey/small-boards.md`: `mini5x5` is published as a draw under matching rules;
  `mini4x5` has no published value.

Read `../AGENTS.md`, `../design/SPEC.md` and `../02-engine/API.md` first. Link against the
`02-engine` library. Write only inside `05-solver/`.

## Goal

Weakly solve start positions of small boards and emit certificates the trusted checker
accepts. The solver is untrusted: use any heuristic that helps, as long as the output is a
valid SPEC section 4 certificate.

## Deliverables

- `msolve "<position>" --claim <WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b> --out file.cert`
  with `--max-nodes` and `--max-seconds` limits. Exit status says proved / disproved / limit.
- `msolve "<position>" --value` tries the claims in a sensible order and reports the value.
- Search: start with depth-first proof-number search (df-pn) with a transposition table for
  WIN claims. For ATLEAST_DRAW claims the certificate is a closed set of positions, so a
  search that finds a small closed set (prover moves chosen to revisit known positions,
  repetition treated as success for the prover) is the core problem. Design this yourself and
  explain the choice in `REPORT.md`.
- Certificate minimisation: after a proof is found, shrink it (drop unreachable entries,
  prefer moves that merge into existing entries) and report sizes before and after.

## Experiments to report

A ladder, each step only attempted when the previous one is done:

1. Forced mates on 8x8 (mate in 2 to 5 problems) as a correctness check.
2. `mini4x4` value and certificates.
3. `mini4x5` value and certificates.
4. `mini5x5`: report how far the search gets within the limits. Do not expect to finish.

For every solved root: value, entries, file size, maximum rank, nodes searched, solver
seconds, checker seconds, and the checker's verdict. A result the checker has not accepted is
reported as unproved.
