# LADDER v1: the piece ladder on the real board

## Why the axis changes

Solving smaller boards does not transfer: a value for 4x5 says nothing about 8x8. Two things
do transfer. A proof that holds for every board size has 8x8 as a special case. And every
chess game reduces, by captures, to positions with fewer pieces. Chess is a 32-piece endgame
on 8x8; tablebases stop at 7 or 8 pieces and cannot go much further. The only thing that could
carry knowledge up from there is endgame knowledge that compresses into short rules.

So the variable that matters is **piece count on 8x8**, and the question of this ladder is:

> How does the length of the rules needed to play a material class perfectly grow as pieces
> are added?

Slow growth would be the first real evidence that chess might have a compact proof. Fast
growth would be measured evidence that it does not. Either is a result. Small boards remain
what they were good for: testing methods cheaply before spending compute on 8x8.

## What a rung is

A rung is one material class on 8x8, for example KBBK or KRKP. Its ground truth is the
tablebase from `04-tablebase` (win, draw or loss for every position). A solution of a rung is
a pair of strategy programs in the sense of `LOOP.md`:

- `win.py`: `claims(pos)` says whether the program undertakes to win from `pos` for the
  stronger side; `move(pos)` gives its move.
- `hold.py`: `claims(pos)` says whether the program undertakes not to lose from `pos` for the
  side it plays; `move(pos)` gives its move.

`claims` is where the knowledge sits: for king and pawn against king it has to contain the
rule that separates won positions from drawn ones.

### Rules for programs

1. Two-ply lookahead at most, as in `LOOP.md` round 2. No search, no tables of positions.
2. **Lower rungs are free.** When a capture or promotion leaves the class, the program may
   hand over to the accepted program of the class it lands in (`lib/`). Length counts only
   the code written for this rung. This is the measure that matters: knowledge added per
   class, given everything below it.
3. Everything is checked by expansion into flat certificates and both checkers. A claim that
   cannot be certified counts as a failure of the program, never as a result.

### Scores per rung

Against the tablebase, on 8x8, over a stratified random sample of at least 1,000 roots per
value, and over the whole class on 5x5 and 6x6:

- **win recall**: certified wins / truly won positions; **false win claims**: claimed but
  truly not won (these are bugs in `claims`);
- **hold recall**: certified holds / positions where that side truly does not lose; **false
  hold claims** likewise;
- **new length**: syntax-tree nodes of this rung's code, `win.py` and `hold.py` separately;
- **attempts**: how many program versions it took.

A rung is **closed** when both recalls are 100% on the samples and on the whole class for
5x5 and 6x6, with zero false claims.

## The rungs, in order

| Rung | Classes | What makes it a step |
|---|---|---|
| 3a | KQK, KRK | done: one program each, whole class proven on 4x4 to 8x8 |
| 3b | KPK | first class with both wins and draws; first `claims`; first `hold.py`; promotion hands over to KQK |
| 4a | KBBK, KBNK | wins that need coordination of two pieces; KBNK is the classic hard mate |
| 4b | KRKB, KRKN, KQKR | mostly draws for the first two (the defender's `hold.py` is the content); a hard win for the third |
| 4c | KRKP, KQKP, KPKP | pawns on both or one side, promotion races, handing over to three different lower classes |
| 5 | KRPKR and others | to be chosen from what rung 4 teaches |

## What gets reported

One table, updated after every rung: class, pieces, tablebase positions, new length for win
and hold, recalls, attempts, largest certificate. And one curve: new length against piece
count. Rungs that could not be closed stay in the table with the recall reached and the
reason; an unclosed rung is data about the growth rate, and hiding it would bias the curve.
