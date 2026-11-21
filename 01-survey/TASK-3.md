# 01-survey, round 3: is the `mini4x5` result new?

You may use the network. Write only inside `01-survey/`. Read `../AGENTS.md` ("Time": stop
searching at minute 35 and write).

## The result to check

`../05-solver` produced, and both independent checkers accepted, certificates showing that
this position is a **draw**:

```
rqkr/pppp/4/PPPP/RQKR w - -      (4 files, 5 ranks)
```

under these rules: pawns move one square only (no double step), no en passant, no castling,
promotion to Q, R, B or N on the last rank, stalemate is a draw, no 50-move rule, infinite
play is a draw. Proof size: 6,107 positions for White's half, 249,051 for Black's half.
Main line of the defence: against `1. d3` Black plays `1... c3`, and after
`2. Rd2 a3 3. b3` the move `3... Ra4`.

Round 1 found no published solution, but that was one pass among many topics. Before anyone
calls this new, try hard to find it already done.

## Deliverable: `novelty-4x5.md`

1. **Search log.** Every query and site tried, with what it returned. Cover at least: the
   original Silverman 4x5 sources and later descriptions; chess variant sites and their
   comment threads; Kirill Kryukov's small-board pages and forum; computer-chess forums;
   the ICGA Journal and Computers and Games proceedings; arXiv; code repositories that
   mention solving 4x5 or "Silverman" chess; student theses and course projects; pages in
   languages other than English if they turn up.
2. **Rule comparison.** For every source that states a value or a solution for a 4x5 game
   with this starting position: the exact rules it used (double step? en passant? castling?
   promotion choices? draw rules?), its claimed value, how it was obtained, and whether a
   proof or database is available. A result under other rules does not settle ours; say what
   it does and does not imply.
3. **Verdict**, one of: already published under matching rules (cite it); published under
   different rules only; no prior result found. State how confident the verdict is and what
   would still need checking. "No prior result found" is a statement about your search, not
   about the world; word it that way.
4. **Where it would belong.** If nothing is found: which venues have published results of
   this size (give two or three concrete examples of comparable small-game solutions and
   where they appeared), and what such a note is expected to contain.

Also, briefly, in `REPORT.md` under "Round 3": the current status of the Riemann hypothesis
claim of 20 November 2026 from primary sources (the author's own note and any verification
page), limited to how the proof was produced and checked. Half a page at most; the lead has
press coverage already and wants only what the primary sources add or correct.
