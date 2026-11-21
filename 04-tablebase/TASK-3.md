# 04-tablebase, round 3: ground truth for the piece ladder

Rounds 1 and 2 are accepted. The project now climbs by piece count on 8x8: read
`../design/LADDER.md`. Your tables are the ground truth every rung is scored against. Read
`../AGENTS.md` ("Time": stop new work at minute 35, keep `REPORT.md` current).

## Deliverables

1. **8x8 four-piece tables** for the ladder classes and everything they can reach by capture
   or promotion: KBBK, KBNK, KRKB, KRKN, KQKR, KRKP, KQKP, KPKP, and their children (for
   example KPKP promotes into KQKP, KRKP, KBKP, KNKP; captures lead into three-piece
   classes). Build in batches, each command under 5 minutes; if a single signature cannot be
   built within the limits, say which and why, and what would be needed.
   The round 2 report notes that castling and en-passant states are only indexed for small
   bases. Castling rights do not matter for the ladder (roots are sampled without them), but
   en passant does matter for KPKP on 8x8: state clearly what is and is not covered, and
   verify the tables with `tbgen verify`.
2. **6x6 tables** for the same classes (mini rules), for whole-class checks.
3. **`tbgen probe <WxH>`**: reads position strings from stdin, one per line, prints
   `<position>\t<W|D|L>\t<dtm plies>` for the side to move (`?` if the position is not in a
   built table). This is how other folders label positions. It must be fast enough for a
   million positions.
4. **`tbgen sample <WxH> <SIG> --value <W|D|L> --stm <w|b> --n <N> --seed <S>`**: uniform
   random sample without replacement of positions of that signature with that value for the
   side to move; prints `<position>\t<value>\t<dtm>`. No castling rights, `ep` `-`.
5. **`results/ladder.tsv`**: for every class above on 6x6 and 8x8, by side to move: number of
   valid positions, wins, draws, losses, longest win in plies with an example position.
6. Sanity checks against known facts, each stated with the number you measured: KBBK and
   KBNK are won for the stronger side from almost all positions (give the exact shares and
   the longest mates); KNNK has no forced mate except trivial cases. Take any published
   reference values from `../01-survey/` only; otherwise mark yours as unchecked.

## Constraints

Disk: keep the total of `data/` under 12 GB; report the size. RAM under 4 GB per command.
Do not change the format of existing tables that `../05-solver` reads (it loads the 4x5
tables); if a format change is unavoidable, keep the old reader working and say so.

## Report

Append "Round 3" to `REPORT.md` early and update it after each batch: which tables exist,
their sizes and build times, the `probe` and `sample` usage, the sanity numbers, known gaps.
