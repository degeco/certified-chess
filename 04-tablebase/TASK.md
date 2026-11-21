# 04-tablebase: retrograde tablebases with checkable output (C++17)

Status: ready. `02-engine` is accepted: its tests reproduce and it agrees with `03-checker`
move for move on about 130,000 positions (`../design/difftest.sh`, `../design/walktest.py`).
`03-checker` is being updated to SPEC v1.1 (prover stalemate in ATLEAST_DRAW) while you start;
build the generator first and run certificate verification last. If `mcheck.py` still rejects
a stalemate-covered draw certificate at that point, report it instead of working around it.

Read `../AGENTS.md`, `../design/SPEC.md` and `../02-engine/API.md` first. Link against the
`02-engine` library; do not copy or reimplement the rules. Write only inside `04-tablebase/`.

## Goal

Strongly solve small material classes by retrograde analysis and find out how much of a small
board can be solved completely on this laptop.

## Deliverables

- `tbgen`: for a board size and a material signature (for example `4x4 KQK`, `5x5 KRKP`),
  compute win / draw / loss and distance to mate for every legal position with both sides to
  move. Promotions and captures lead into other signatures, which are built first.
- Table dump: `tbgen dump` writes `<position>\t<W|D|L>\t<dtm plies>` (value for the side to
  move, dtm `0` for draws).
- Certificate export: `tbgen cert "<position>"` writes SPEC section 4 certificates extracted
  from the tables: one `WIN` certificate for a won position, or both `ATLEAST_DRAW`
  certificates for a drawn one. Each must be accepted by `../03-checker/mcheck.py verify`.
- Internal consistency pass, separate from generation: every table value agrees with the
  values of its successors (win: some successor is a loss with dtm one less; loss: all
  successors are wins and the largest dtm is one less; draw: no successor is a loss and at
  least one is a draw, or the position is stalemate).

## Experiments to report

- All 2 to 4 piece signatures on 3x3, 4x4, 4x5, 5x5 as far as time and 4 GB of RAM allow:
  position counts, share of wins / draws / losses, longest mate, generation time, table size.
- 8x8 KQK, KRK, KPK as a sanity check against published longest-mate values (take the
  reference values from `../01-survey/`; if they are not there, report your values as
  unchecked and do not quote references from memory).
- `../01-survey/small-boards.md` lists published 3x3 and 3x4 totals. Those tables allow pawns
  on the first rank, which SPEC v1.1 forbids, so only pawnless signatures are comparable.
  Compare what is comparable and say exactly which numbers were matched.
- H1 ensemble (SPEC section 5): for each board and signature, sample at least 200 roots
  uniformly from the won positions and 200 from the drawn positions (all of them if fewer),
  extract certificates, and report the distribution of certificate entries (min, median,
  mean, max) next to the table size, WIN and ATLEAST_DRAW separately. Write the raw rows to
  `results/h1.tsv`: board, signature, root, claim, entries, max rank, table positions.
  Verify every sampled certificate with `mcheck.py` when the total is small enough, otherwise
  a stated random subset; report how many were verified.

Respect the limits in `../AGENTS.md`: no run over 5 minutes, no more than 4 GB.
