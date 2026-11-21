# 09-ladder: rung 3b, king and pawn against king

Read `../AGENTS.md` ("Time": stop experimenting at minute 35 and write), `../design/SPEC.md`
(v1.2), `../design/LOOP.md` and above all `../design/LADDER.md`. Write only inside
`09-ladder/`. You may read everything in `../07-strategies/` and import its `harness.py` and
`../03-checker/rules.py`; do not modify them. Python standard library only (`z3` is installed
but not needed in this round).

## Setting up

- `lib/kqk.py` and `lib/krk.py`: copies of `../07-strategies/strategies/kqk_v7.py` and
  `krk_v21.py`, the accepted programs of the rungs below. They are proven for every valid
  White-to-move position on 4x4 to 8x8.
- Ground truth: `../04-tablebase/bin/tbgen dump <WxH> KPK` prints every position of the class
  with its value for the side to move and its distance to mate. Tables for 3x3 to 5x5 and 8x8
  exist in `../04-tablebase/data`. Build 6x6 into your own folder with
  `tbgen build 6x6 KPK --db-dir <your dir>` (and its children the same way if needed).
- Remember the rules: on 8x8 a pawn may advance two squares from its second rank; on every
  other board it moves one square only (SPEC section 2). One program must handle both.

## The rung

KPK is the first class where the value depends on the position. White (king and pawn) wins
some positions and only draws others; Black (bare king) never wins.

1. `kpk/win.py` with `claims(pos)` and `move(pos)` for White. When the pawn promotes, hand
   over to `lib/kqk.py` (promotion to a queen is always enough here; the certificate
   continues through KQK positions). Under-promotion is not needed.
2. `kpk/hold.py` with `claims(pos)` and `move(pos)` for Black: the positions where Black
   draws, and how. When Black captures the pawn the game is king against king, where any
   legal move holds.
3. `ladder.py score --class KPK --board <WxH> [--sample N --seed S | --all]`: runs both
   programs against the tablebase truth as `LADDER.md` defines: win recall, false win claims,
   hold recall, false hold claims, new length in syntax-tree nodes, certificate sizes. Every
   counted success is a certificate accepted by `../03-checker/mcheck.py` or, for speed,
   `../08-checker2/mcheck2` (build it with `make -C ../08-checker2`; do not read its
   source); say which checker was used for which run. Use union certificates as
   `07-strategies` does, so a whole board is one expansion.
   Roots may have either side to move.
4. Iterate. Start from the simplest honest idea, look at the failing positions, improve.
   Log every version in `LOG.md` with its scores and the reason for the change. The target
   is a closed rung: 100% on 2,000-root samples on 8x8 (1,000 won, 1,000 drawn, both sides
   to move) and on every position of 5x5 and 6x6, zero false claims.

## What the lead wants to learn

- How long is `claims` when it is right? This is the first measurement of "knowledge that
  classifies" as opposed to "knowledge that executes".
- How does the new length of this rung compare with `lib/kqk.py` (793 nodes) and
  `lib/krk.py` (892 nodes)?
- Is the drawing side cheap or expensive to describe? Earlier measurements on flat
  certificates found draw proofs far larger than win proofs.
- Does the same program work on 5x5, 6x6 and 8x8, or does the double step force a split?

## Report

`REPORT.md`: the `LADDER.md` score table for KPK on each board, the lengths, the number of
attempts, what the final `claims` rule says in two or three plain sentences, and the failing
positions if the rung is not closed. Unclosed is an acceptable outcome if it is reported
exactly.
