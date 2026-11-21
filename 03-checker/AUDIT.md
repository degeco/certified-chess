# Audit Guide for `03-checker` (SPEC v1.2)

This document walks a human reviewer through the trusted certificate checker (`rules.py` and `mcheck.py`), mapping every rule of `design/SPEC.md` (v1.2) sections 2–4 to the exact function that enforces it, and stating the soundness argument directly.

The entire trusted code base is two plain Python standard-library files with no external dependencies:

- `rules.py`: board representation, canonical position parsing/formatting, attack detection, legal move generation, and move execution.
- `mcheck.py`: certificate parser/verifier (`verify_certificate`) and CLI entry points (`verify`, `moves`, `batch`, `perft`).

---

## 1. Trusted Rules (`rules.py`)

A `Position` is an immutable dataclass with a flat mailbox tuple `board` of length `width * height` (`index = rank * width + file`, file `0 = 'a'`, rank `0 = '1'`). Immutability prevents move-undo aliasing bugs.

- **Board & encoding validation (`parse_position`, `format_position`)**:
  - Enforces `3 <= width, height <= 8`, uniform rank lengths, maximal empty-square runs, exactly one `'K'` and one `'k'`, no pawn of either colour (`'P'` or `'p'`) on rank `1` or rank `H`, and that the side *not* to move is not in check (so kings can never be captured).
  - Enforces `castling == "-"` and `ep == "-"` off 8x8.
  - On 8x8, enforces `castling` is a non-empty subset of `"KQkq"` in order (or `"-"`) with each named king and rook standing on its original square (`K`: `K` on `e1` and `R` on `h1`; `Q`: `K` on `e1` and `R` on `a1`; `k`: `k` on `e8` and `r` on `h8`; `q`: `k` on `e8` and `r` on `a8`), with no further normalization.
  - On 8x8, rejects any `ep` square other than `"-"` unless all five SPEC v1.2 conditions hold: rank 6 with White to move (or rank 3 with Black to move), target square empty, double-step origin square behind it (rank 7 or rank 2, same file) empty, enemy pawn in front of it (rank 5 or rank 4), and `_has_legal_ep_capture` confirms at least one legal en-passant capture onto it exists.
  - Accepts optional trailing halfmove/fullmove counters when reading; `format_position` always emits the canonical 4-field string.
- **Attacks & check (`is_square_attacked`, `in_check`)**:
  - Directly checks pawn attack squares, knight/king offsets, and orthogonal/diagonal rays on the `width x height` board.
- **Movement & legality (`_pseudo_legal_moves`, `_apply_board`, `_finish_position`, `legal_moves`, `legal_transitions`, `apply_move`)**:
  - Pawns move one square forward and capture diagonally; reaching the last rank generates all 4 promotions (`q`, `r`, `b`, `n`).
  - Double pawn pushes, en passant, and castling are gated strictly on `pos.is_8x8` (`width == 8 and height == 8`).
  - Castling verifies the castling right, king and rook home squares, empty intervening squares, and that the king's start, transit, and destination squares are not attacked.
  - Every pseudo-legal move is filtered by executing `_apply_board` and requiring `not is_square_attacked(...)` on the mover's own king.
  - `_finish_position` drops castling rights on king move, rook move, or rook capture, and sets `ep` only after an 8x8 pawn double push when `_has_legal_ep_capture` returns `True`.

---

## 2. Mapping SPEC v1.2 Section 4 to `mcheck.py`

All certificate verification happens in `verify_certificate(path)` in `mcheck.py`. A **prover stalemate** is recognized by `_is_prover_stalemate(pos, prover)`: `pos.stm == prover and not in_check(pos) and not legal_moves(pos)`. A position is **covered** in `ATLEAST_DRAW` if it is in `entries` or `_is_prover_stalemate(pos, prover)` holds.

| SPEC v1.2 Section 4 requirement | Enforcing code in `mcheck.py` |
|---|---|
| UTF-8 text; lines end with `\n` only; `\r` anywhere is invalid; missing final `\n` allowed; fields separated by exactly one `\t` | Binary read (`open(path, "rb")`) + strict `.decode("utf-8")`; reject if `text.find("\r") != -1`; strip at most one trailing `\n` and `text.split("\n")`; `line.split("\t")` requiring `len(fields) == 3` |
| Header `#cert v1`, `#claim WIN\|ATLEAST_DRAW w\|b`, `#root <pos>` | `verify_certificate` header block (checking `lines[0]`, `lines[1]`, `lines[2]`) |
| Valid, canonical position strings everywhere (`#root` and every entry) | `_parse_canonical_position` (`parse_position(s)` and `pos.to_fen() == s`) |
| Every entry has the board size of `#root`; no blank lines or comments in body | Body parsing loop (`len(fields) != 3` and `(pos.width, pos.height) != (root_pos.width, root_pos.height)`) |
| Rank is a non-negative decimal integer without sign or leading zeros; `0` in `ATLEAST_DRAW` | `_parse_canonical_rank` and `claim_kind == "ATLEAST_DRAW" and rank != 0` |
| Duplicate position is an error | `if pos_str in entries: return _fail(...)` |
| Root check (prover to move): in `WIN`, root is an entry; in `ATLEAST_DRAW`, root is covered (entry or prover stalemate) | `if root_pos.stm == prover:` branch checking `root_str in entries` or `(claim_kind == "ATLEAST_DRAW" and _is_prover_stalemate(root_pos, prover))` |
| Root check (opponent to move, `WIN`): if no replies, opponent must be in check; otherwise every reply is an entry (no rank bound, no stalemate exemption) | `else:` branch of root check (`if claim_kind == "WIN" and not root_replies: if not in_check(root_pos): ...`, then requiring `reply_str in entries`) |
| Root check (opponent to move, `ATLEAST_DRAW`): every legal reply leads to a covered position (entry or prover stalemate) | `else:` branch of root check allowing `_is_prover_stalemate(reply_pos, prover)` when `claim_kind == "ATLEAST_DRAW"` |
| Verify **every** entry in the file, not only reachable ones | `for pos_str, (pos, move_str, rank, line_no) in entries.items():` iterates over the entire parsed dictionary |
| `WIN` Rule 1 & `ATLEAST_DRAW` Rule 1: prover is to move in `p` and `m` is legal in `p`, `q = p.m` (also prevents a prover stalemate from appearing as an entry) | `if pos.stm != prover: ...` followed by `q_pos = apply_move(pos, move_str)` |
| `WIN` Rule 2: if opponent has no legal move in `q`, opponent must be in check | `if not replies: if not in_check(q_pos): return _fail(...)` |
| `WIN` Rule 3: otherwise, for every legal reply `r`, `q.r` is an entry with rank strictly less than `d` (no stalemate exemption) | `for reply_move, qr_pos in replies:` checking `qr_str in entries` and `child_rank < rank` |
| `ATLEAST_DRAW` Rule 2: for every legal reply `r` in `q`, `q.r` is covered (entry or prover stalemate) | `for reply_move, qr_pos in replies:` checking `qr_str in entries or _is_prover_stalemate(qr_pos, prover)` |

Because `verify_certificate` also rejects malformed UTF-8, unreadable files, and extra fields, any malformed input yields `INVALID` with exit code `1`.

---

## 3. Soundness Argument

Suppose `verify_certificate` returns `VALID` for a file with root position $R$, prover $P$, and finite entry table $E$. Because every position string in $E$ and $R$ equals `pos.to_fen()`, keys in $E$ correspond bijectively to distinct game positions.

### Case 1: `#claim WIN P`

**Claim:** From every position $p \in E$, prover $P$ has a strategy that forces checkmate in finitely many moves (at most $d + 1$ own moves, where $d \ge 0$ is the rank of $p$; and at most $d$ own moves when immediate mates have rank $\ge 1$).

**Proof by strong induction on the non-negative integer rank $d$ of $p \in E$:**
1. By Rule 1, $P$ is to move in $p$, and the entry's move $m$ is legal, producing $q = p.m$.
2. If the opponent has no legal move in $q$, Rule 2 guarantees the opponent is in check, so $P$ has immediately checkmated the opponent.
3. Otherwise, the opponent must play some legal reply $r$, leading to $q.r$. By Rule 3, $q.r \in E$ and $\mathrm{rank}(q.r) < d$. (In particular, if $q.r$ stalemated $P$, $q.r$ would have no legal move and could not satisfy Rule 1 in $E$, so Rule 3 rejects it.) Since ranks are non-negative integers, the induction hypothesis applies to $q.r$, so $P$ forces checkmate from $q.r$ in finitely many moves.

Since no position can decrease in rank below $0$, play cannot cycle or continue forever.

**At the root $R$:**
- If $P$ is to move in $R$, the root check guarantees $R \in E$, so $P$ forces checkmate from $R$.
- If the opponent is to move in $R$, either the opponent has no legal move and is already in check (immediate checkmate for $P$), or every legal reply $r$ leads to $R.r \in E$, from which $P$ forces checkmate.

Therefore, $R$ is a forced win for $P$ under the idealised rules of SPEC section 2.

### Case 2: `#claim ATLEAST_DRAW P`

Let $S_P$ be the set of prover-stalemate positions ($P$ to move, no legal move, not in check), and let the **covered** set be $C = E \cup S_P$.

**Claim:** From every position $p \in C$, prover $P$ has a strategy that never loses (either wins, draws by stalemate, or plays forever, which is a draw under SPEC section 2).

**Proof by invariant:**
Maintain the invariant that whenever it is $P$'s turn to move, the current position $p$ belongs to $C$:
1. If $p \in S_P$, $P$ has no legal move and is not in check, so the game is already drawn by stalemate (not a loss for $P$).
2. Otherwise $p \in E$. By Rule 1, $p$ has a legal move $m$ for $P$, so $P$ is not checkmated at $p$. Let $q = p.m$.
3. If the opponent has no legal move in $q$, the game ends immediately in checkmate (win for $P$) or stalemate (draw)—in either case not a loss for $P$.
4. Otherwise, for whatever legal reply $r$ the opponent chooses, Rule 2 guarantees $q.r \in C = E \cup S_P$ (in particular, $q.r$ cannot be a checkmate against $P$, since a checkmate is neither in $E$ nor in $S_P$), restoring the invariant for $P$'s next turn.

If the game never terminates, infinite play is a draw by SPEC section 2.

**At the root $R$:**
- If $P$ is to move in $R$, the root check guarantees $R \in C$, establishing the invariant at move 0.
- If the opponent is to move in $R$, either the opponent has no legal move (already checkmate or stalemate, not a loss for $P$), or every legal reply $r$ leads to $R.r \in C$, establishing the invariant on $P$'s first turn.

Therefore, $P$ can force at least a draw from $R$. Combining valid `ATLEAST_DRAW w` and `ATLEAST_DRAW b` certificates proves the game value of $R$ is a draw.
