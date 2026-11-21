# 03-checker: trusted certificate checker (Python, standard library only)

Read `../AGENTS.md` and `../design/SPEC.md` first. Write only inside `03-checker/`.
Do not read `../02-engine/`: the two rule implementations must stay independent.

## Goal

The checker is the only code in this project whose correctness we have to believe. Every
claimed result is accepted or rejected by it. Optimise for being obviously right: small,
plain, no cleverness, no dependencies, easy for a human to audit in one sitting.

## Deliverables

- `rules.py`: the game family of SPEC section 2 on a simple mailbox board. Position parsing
  and canonical printing (SPEC section 3, including the legal-en-passant rule), legal moves,
  apply move, in-check. Aim for a few hundred readable lines.
- `mcheck.py` CLI:
  - `mcheck.py verify <file.cert>` checks a certificate exactly as SPEC section 4 defines.
    Prints `VALID` plus statistics (claim, root, entries, maximum rank, seconds) and exits 0,
    or prints `INVALID`, the first violating entry and the reason, and exits 1.
    Malformed files are `INVALID`, never a crash.
  - `mcheck.py moves "<position>"`: one line per legal move, sorted by move string,
    `<move>\t<resulting canonical position>`.
  - `mcheck.py batch`: reads one position per line on stdin, prints
    `<position>\t<m1>:<pos1>|<m2>:<pos2>|...` with moves sorted, or `<line>\tERROR`.
  - `mcheck.py perft "<position>" <depth>`.
- `AUDIT.md`: a short walk through the code for a human reviewer: which function enforces
  which numbered rule of SPEC section 4, and the soundness argument in your own words.
- `tests/`: runnable with `python3 -m unittest discover -s tests`.

## Tests that must pass

- 8x8 perft, exact values, to the depth Python manages in under a minute each:
  start position 20, 400, 8902, 197281;
  `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -` 48, 2039, 97862;
  `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -` 14, 191, 2812, 43238;
  `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -` 6, 264, 9467;
  `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -` 44, 1486, 62379.
- Mini boards: hand-checked cases for single-step pawns, promotion on a non-8 board, no
  castling, no en passant, pins, check evasion, stalemate, mate on 3x3, 4x4, 5x5.
- Certificates. Write a tiny brute-force solver **inside `tests/` only** (plain minimax or
  retrograde over a small reachable set) to produce real certificates for small positions,
  for example king and queen against king on 4x4 (WIN) and king against king plus a blocked
  position (ATLEAST_DRAW for both sides). Then:
  - every generated certificate verifies as `VALID`;
  - **mutation tests**: each of these single changes must make the checker answer `INVALID`:
    delete one entry that is needed, change a move to another legal move that loses the win,
    change a move to an illegal move, raise a child's rank to equal its parent's, flip the
    claimed side, swap `ATLEAST_DRAW` for `WIN`, duplicate a position, corrupt a position
    string, use a non-canonical position string, give a stalemating move in a WIN
    certificate, omit the root.
  - a WIN certificate containing a cycle of equal ranks is rejected; an ATLEAST_DRAW
    certificate containing a cycle is accepted.

## Out of scope

Speed. Finding proofs. Anything that makes the code harder to audit. If a faster checker is
needed later it will be a separate program validated against this one.
