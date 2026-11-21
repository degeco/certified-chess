# SPEC v1.2: certified solving of small-board chess

Changes from earlier versions are listed in section 7. The newest version rules.

## 1. The idea

Full chess is out of reach for direct search. The first experiment therefore asks a question
we can actually measure: **how much smaller is a checkable proof of a game value than the
state space it speaks about, and how does that ratio change as the board grows?**

To measure it rigorously we separate two roles:

- **Solvers are untrusted.** Any search, heuristic, engine or learned model may be used to
  find a result. A solver must emit a **certificate**.
- **The checker is the only trusted part.** It is small, slow, written for clarity, and shares
  no code with the solvers. A claim counts as a result only when the checker accepts it.

Hypothesis H1 (to be tested, not assumed): for the family of boards below, certificate size
grows like a power of the state-space size with exponent clearly below 1.

## 2. The game family

A position is a board of `W` files and `H` ranks, `3 <= W, H <= 8`, with standard chess
pieces. White pawns move toward higher ranks. Exactly one king per side.

The rule set is fixed by the board size:

| Board | Rules |
|---|---|
| 8x8 | Full FIDE movement: pawn double step from ranks 2 and 7, en passant, castling. |
| any other size | "Mini" rules: pawns move one square only, no en passant, no castling. |

Common to both: pieces move as in FIDE chess; a pawn reaching the last rank must promote to
Q, R, B or N; moving into or staying in check is illegal.

### Game value (what "solved" means here)

- Side to move has no legal move and is in check: that side **loses**.
- Side to move has no legal move and is not in check: **draw**.
- Infinite play: **draw**.

There is no 50-move rule, no repetition rule and no insufficient-material adjudication.
Repetition and dead positions are covered by "infinite play is a draw". The 50-move rule is
deliberately left out, as in most game-solving work; under FIDE's 50/75-move rules some long
wins become draws, so values proven here are values of this idealised game. Every report must
keep that caveat visible.

## 3. Encodings

### Position string

`<placement> <stm> <castling> <ep>`: four fields, single spaces.

- `placement`: FEN-style, top rank first, ranks separated by `/`. The number of ranks is `H`,
  each rank describes exactly `W` squares. Letters `PNBRQK` white, `pnbrqk` black, digits for
  runs of empty squares (maximal runs, as in FEN).
- `stm`: `w` or `b`.
- `castling`: subset of `KQkq` in that order, or `-`. Always `-` off 8x8. Rights are lost when
  the king or that rook moves or the rook is captured; no further normalisation.
- `ep`: en-passant target square, or `-`. **Set only if at least one legal en-passant capture
  exists** in the position. Always `-` off 8x8.

A position string is **valid** only if all of these hold; every reader rejects anything else:

- exactly one king per side;
- no pawn of either colour on rank 1 or on rank `H`;
- the side not to move is not in check;
- castling letters only where the king and that rook stand on their original squares;
- an `ep` square other than `-` only on 8x8 and only if all of these hold: it is on rank 6
  with White to move or rank 3 with Black to move; it is empty; the square behind it from
  which the double step started (rank 7 or rank 2, same file) is empty; an enemy pawn stands
  on the square in front of it where the double step ended (rank 5 or rank 4); and at least
  one en-passant capture onto it is legal;
- placement, `stm`, `castling` and `ep` are well formed as described above.

Readers must accept and ignore trailing halfmove/fullmove fields. Writers must emit this
canonical form exactly, because certificates are indexed by this string.

Squares: file letter `a`.. from White's left, rank digit `1`.. from White's side.

### Move string

`<from><to>[promo]`, for example `a2a3`, `b4b5q`. Promotion letter lower case. Castling is the
king's move (`e1g1`).

### Named start positions

| Name | Position |
|---|---|
| `mini4x4` | `rqkr/pppp/PPPP/RQKR w - -` |
| `mini4x5` | `rqkr/pppp/4/PPPP/RQKR w - -` |
| `mini5x5` | `rnbqk/ppppp/5/PPPPP/RNBQK w - -` |
| `std8` | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -` |

These are our definitions. Whether they coincide with historical variants (Silverman,
Gardner) and their published results is for `01-survey` to establish.

## 4. Certificates

A certificate proves a lower bound on what one player, the **prover**, can force from a root.

```
#cert v1
#claim WIN w
#root <position string>
<position>\t<move>\t<rank>
...
```

- `#claim` is `WIN <side>` or `ATLEAST_DRAW <side>`, side `w` or `b`.
- Each body line is an **entry**: a position with the prover to move, the prover's move, and
  a rank. One entry per position; a duplicate position is an error.
- A rank is a non-negative decimal integer without sign or leading zeros. It is `0` in every
  ATLEAST_DRAW entry.
- Every entry position is valid, canonical, and has the board size of the root. The root is
  valid and canonical. No blank lines and no comment lines in the body.
- The file is UTF-8 text. A line ends with a single line feed (`\n`) and nothing else: a
  carriage return anywhere in the file makes the certificate invalid. The line feed after the
  last line may be missing. Fields are separated by exactly one tab.

Write `p.m` for the position after move `m` in `p`.

### Checking a WIN certificate

For every entry `(p, m, d)`:

1. The prover is to move in `p` and `m` is legal in `p`. Let `q = p.m`.
2. If the opponent has no legal move in `q`, the opponent must be in check.
3. Otherwise, for every legal reply `r`, `q.r` is an entry with rank strictly less than `d`.

Root: if the prover is to move, the root is an entry. If the opponent is to move, the root
is treated like `q` in steps 2 and 3 with no rank bound.

Soundness: by induction on rank, the prover mates from every entry within `d` own moves.

### Checking an ATLEAST_DRAW certificate

Call a position a **prover stalemate** if the prover is to move, has no legal move and is not
in check. Such a position is a draw and can have no entry, since an entry needs a legal move.
Call a position **covered** if it is an entry or a prover stalemate.

For every entry `(p, m, 0)`:

1. The prover is to move in `p` and `m` is legal in `p`. Let `q = p.m`.
2. For every legal reply `r` of the opponent in `q`, `q.r` is covered.

Root: if the prover is to move, the root is covered. If the opponent is to move, every legal
reply from the root leads to a covered position.

Soundness: the covered set is an invariant. From a covered position the prover either has a
legal move that keeps play inside the set or the game is already drawn by stalemate, so the
prover is never checkmated; play ends without a prover loss or goes on forever. Cycles are
allowed, which is why no rank is needed.

The stalemate exemption applies to ATLEAST_DRAW only. In a WIN certificate a reply that
stalemates the prover has no entry and the certificate is invalid.

### Combining

- Value of the root is a win for X: one `WIN X` certificate.
- Value of the root is a draw: `ATLEAST_DRAW w` and `ATLEAST_DRAW b`, both valid.

The checker verifies **every** entry in the file, not only those reachable from the root.

## 5. What we measure

For each solved root: number of entries, file size, maximum rank, solver time, checker time,
and the size of the reachable state space where it can be enumerated or estimated.

H1 is judged on **ensembles of roots per board size**, not on single start positions: many
roots sampled per board and material class, WIN and ATLEAST_DRAW reported separately, with
the spread shown and not only the mean. A single start position confounds board size with
opening accidents. `01-survey` reports that `mini4x4` is a forced mate in 4 with a 5-entry
certificate, which says nothing about 4x4 boards in general.

## 6. Folders

| Folder | Purpose | Depends on |
|---|---|---|
| `01-survey` | Source-backed research assessment; challenges this spec | nothing |
| `02-engine` | Fast rules engine in C++ with perft | nothing |
| `03-checker` | Trusted certificate checker in Python, independent rules | nothing |
| `04-tablebase` | Retrograde tablebases with checkable output | 02 |
| `05-solver` | Proof search that emits certificates | 02, 03 |
| `06-complexity` | State-space counts and estimates per board | 02 |
| `07-strategies` | Strategy programs as compressed proofs; the iteration loop of `LOOP.md` | 03 |

`02` and `03` implement the rules twice on purpose. They are compared move for move on random
positions before either is believed: `design/difftest.sh` (random placements, all board
sizes) and `design/walktest.py` (random play on 8x8, covering en passant and castling).

## 7. Changes in v1.1

1. ATLEAST_DRAW: prover-stalemate positions are covered without an entry. v1 could not
   certify a draw reached by stalemating the prover (found by `03-checker`).
2. Validity of position strings is now defined (section 3). v1 left pawns on rank 1 open and
   the two implementations disagreed: `02-engine` rejected them, `03-checker` accepted them.
   Both must reject.
3. Rank domain and certificate file strictness are now explicit (section 4).
4. H1 is measured on ensembles of roots (section 5), following the `01-survey` critique.

### v1.2

Both found by `08-checker2`, the second checker written from this spec alone. In each case
`03-checker` accepted input that `08-checker2` rejected. Neither could make a valid
certificate prove something false, since successor positions are always computed by the
checker itself, but two checkers must not disagree on any file.

5. Line endings and separators of a certificate file are now defined (section 4). The Python
   checker accepted carriage returns.
6. Well-formedness of the `ep` field is now spelled out (section 3). The Python checker
   accepted an `ep` square whose double-step origin square was occupied; `02-engine` and
   `08-checker2` rejected it.

Not changed, by decision: certificates stay flat lists of positions. References from a
certificate into a verified tablebase, and certificates stated over sets of positions, are
the planned next step and get their own spec once the flat baseline has been measured.
