# `03-checker` Report

## 1. What was built

All deliverables were implemented inside `/home/dege/chess/03-checker` using only the Python 3.14 standard library, independently of `02-engine/`:

- `rules.py` (614 lines total, 528 non-blank): immutable mailbox board (`3 <= W, H <= 8`), SPEC section 2 movement rules (full FIDE movement on 8x8; mini rules off 8x8), SPEC section 3 position parsing and canonical 4-field formatting (including the legal-en-passant rule and castling-rights tracking with no further normalization), `in_check`, `legal_moves`, `legal_transitions`, `apply_move`, and `perft`.
- `mcheck.py` (322 lines total, 278 non-blank): trusted SPEC section 4 certificate verifier (`verify_certificate`) and CLI supporting `verify`, `moves`, `batch`, and `perft`. Malformed or unreadable files always report `INVALID` and exit `1` without crashing.
- `AUDIT.md`: human reviewer walkthrough mapping each SPEC section 4 rule to its enforcing code in `mcheck.py` and stating the soundness proof for both `WIN` and `ATLEAST_DRAW`.
- `tests/`:
  - `tests/test_perft_8x8.py`: all 5 Chess Programming Wiki 8x8 perft positions, recursion consistency check, en-passant canonicalization (including horizontal/vertical pins and check-resolving ep), and castling edge cases.
  - `tests/test_mini_boards.py`: hand-checked 3x3, 4x4, 4x5, 5x5, and 8x7 cases covering single-step pawns, promotions, no castling/ep off 8x8, pins, check evasions (capture, interposition, double check), stalemate, checkmate, named start positions, and invalid FEN rejection.
  - `tests/mini_solver.py`: tiny brute-force retrograde / fixed-point solver used solely by tests to generate genuine `WIN` and `ATLEAST_DRAW` certificates on small reachable state spaces.
  - `tests/test_certificates.py`: end-to-end verification of generated certificates (KQ vs K, KR vs K, K vs K, sealed 4x5 blocked fortress), all required single-change mutation tests, equal-rank cycle rejection in `WIN` vs cycle acceptance in `ATLEAST_DRAW`, opponent-to-move terminal roots, unreachable invalid entry rejection, malformed-file tests, and CLI subprocess tests.

> **Idealised-game caveat (SPEC section 2):** Values checked by `mcheck.py` are values of the idealised game with no 50/75-move rule, no threefold/fivefold repetition rule, and no insufficient-material adjudication (infinite play is a draw). Under FIDE's 50/75-move rules, some long wins in this idealised game become draws.

---

## 2. How to build and test

No build step is required (pure Python 3 standard library). Exact commands from `/home/dege/chess/03-checker`:

```bash
# Run the full test suite (34 tests)
python3 -m unittest discover -s tests -v

# CLI usage examples
python3 mcheck.py perft "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -" 4
python3 mcheck.py moves "rqkr/pppp/4/PPPP/RQKR w - -"
printf "rqkr/pppp/4/PPPP/RQKR w - -\nbad fen\n" | python3 mcheck.py batch
python3 mcheck.py verify <file.cert>
```

---

## 3. Actual test output

Command: `cd /home/dege/chess/03-checker && python3 -m unittest discover -s tests -v`

```text
test_cli_batch (test_certificates.TestCLI.test_cli_batch) ... ok
test_cli_moves (test_certificates.TestCLI.test_cli_moves) ... ok
test_cli_perft (test_certificates.TestCLI.test_cli_perft) ... ok
test_cli_verify_valid_and_invalid (test_certificates.TestCLI.test_cli_verify_valid_and_invalid) ... ok
test_all_required_mutations_rejected (test_certificates.TestCertificatesAndMutations.test_all_required_mutations_rejected) ... ok
test_cycle_rejected_in_win_and_accepted_in_atleast_draw (test_certificates.TestCertificatesAndMutations.test_cycle_rejected_in_win_and_accepted_in_atleast_draw) ... ok
test_malformed_files_never_crash (test_certificates.TestCertificatesAndMutations.test_malformed_files_never_crash) ... ok
test_opponent_to_move_terminal_roots (test_certificates.TestCertificatesAndMutations.test_opponent_to_move_terminal_roots) ... ok
test_real_draw_certificates_kvk_and_blocked (test_certificates.TestCertificatesAndMutations.test_real_draw_certificates_kvk_and_blocked) ... ok
test_real_kq_vs_k_4x4_win_certificates (test_certificates.TestCertificatesAndMutations.test_real_kq_vs_k_4x4_win_certificates) ... ok
test_unreachable_invalid_entry_is_rejected (test_certificates.TestCertificatesAndMutations.test_unreachable_invalid_entry_is_rejected) ... ok
test_check_evasion_capture_block_and_double_check (test_mini_boards.TestMiniBoards.test_check_evasion_capture_block_and_double_check) ... ok
test_checkmate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_checkmate_on_3x3_4x4_5x5) ... ok
test_named_mini_start_positions_parse_and_roundtrip (test_mini_boards.TestMiniBoards.test_named_mini_start_positions_parse_and_roundtrip) ... ok
test_no_castling_or_ep_off_8x8 (test_mini_boards.TestMiniBoards.test_no_castling_or_ep_off_8x8) ... ok
test_parser_rejects_invalid_positions (test_mini_boards.TestMiniBoards.test_parser_rejects_invalid_positions) ... ok
test_pins_on_mini_boards (test_mini_boards.TestMiniBoards.test_pins_on_mini_boards) ... ok
test_promotion_on_3x3_and_4x4 (test_mini_boards.TestMiniBoards.test_promotion_on_3x3_and_4x4) ... ok
test_single_step_pawns_only_on_mini_boards (test_mini_boards.TestMiniBoards.test_single_step_pawns_only_on_mini_boards) ... ok
test_stalemate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_stalemate_on_3x3_4x4_5x5) ... ok
test_castling_blocked_by_attacked_transit_square_but_not_b1 (test_perft_8x8.Test8x8RulesDetails.test_castling_blocked_by_attacked_transit_square_but_not_b1) ... ok
test_castling_rights_lost_on_rook_capture_and_king_move (test_perft_8x8.Test8x8RulesDetails.test_castling_rights_lost_on_rook_capture_and_king_move) ... ok
test_ep_cleared_under_horizontal_pin (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_under_horizontal_pin) ... ok
test_ep_cleared_when_no_adjacent_pawn (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_when_no_adjacent_pawn) ... ok
test_ep_set_when_it_resolves_check_by_capturing_checker (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_it_resolves_check_by_capturing_checker) ... ok
test_ep_set_when_legal_capture_exists (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_legal_capture_exists) ... ok
test_ep_set_when_only_one_of_two_pawns_is_pinned (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_only_one_of_two_pawns_is_pinned) ... ok
test_trailing_fen_counters_accepted_and_stripped (test_perft_8x8.Test8x8RulesDetails.test_trailing_fen_counters_accepted_and_stripped) ... ok
test_kiwipete_perft (test_perft_8x8.TestPerft8x8.test_kiwipete_perft) ... ok
test_perft_matches_full_apply_recursion (test_perft_8x8.TestPerft8x8.test_perft_matches_full_apply_recursion) ... ok
test_position3_perft (test_perft_8x8.TestPerft8x8.test_position3_perft) ... ok
test_position4_perft (test_perft_8x8.TestPerft8x8.test_position4_perft) ... ok
test_position5_perft (test_perft_8x8.TestPerft8x8.test_position5_perft) ... ok
test_startpos_perft (test_perft_8x8.TestPerft8x8.test_startpos_perft) ... ok

----------------------------------------------------------------------
Ran 34 tests in 5.251s

OK
```

---

## 4. Measured numbers

### 8x8 Perft (Python 3.14.10)

Reproduced by running `python3 mcheck.py perft "<fen>" <depth>` (timed via `rules.perft` loop):

| Position | Depth | Exact Count | Time (s) |
|---|---:|---:|---:|
| Start position | 1 / 2 / 3 / 4 | 20 / 400 / 8,902 / 197,281 | 0.000 / 0.004 / 0.073 / 2.055 |
| Kiwipete (`r3k2r/p1ppqpb1/...`) | 1 / 2 / 3 | 48 / 2,039 / 97,862 | 0.000 / 0.019 / 0.831 |
| Position 3 (`8/2p5/3p4/KP5r/...`) | 1 / 2 / 3 / 4 | 14 / 191 / 2,812 / 43,238 | 0.000 / 0.002 / 0.035 / 0.574 |
| Position 4 (`r3k2r/Pppp1ppp/...`) | 1 / 2 / 3 | 6 / 264 / 9,467 | 0.000 / 0.003 / 0.078 |
| Position 5 (`rnbq1k1r/pp1Pbppp/...`) | 1 / 2 / 3 | 44 / 1,486 / 62,379 | 0.000 / 0.014 / 0.620 |

### Sample generated certificates verified by `mcheck.py`

Reproduced by `tests.mini_solver` + `mcheck.verify_certificate`:

| Position | Claim | Entries | Max Rank | Bytes | Check Time (s) |
|---|---|---:|---:|---:|---:|
| `4/1k2/4/Q2K w - -` (KQ vs K, 4x4) | `WIN w` | 4 | 3 | 147 | 0.0005 |
| `4/1k2/4/R2K w - -` (KR vs K, 4x4) | `WIN w` | 22 | 5 | 613 | 0.0015 |
| `4/1k2/4/Q2K b - -` (KQ vs K, opp to move) | `WIN w` | 5 | 3 | 172 | 0.0005 |
| `k3/4/4/3K w - -` (K vs K, 4x4) | `ATLEAST_DRAW w` | 32 | 0 | 815 | 0.0027 |
| `k3/4/4/3K w - -` (K vs K, 4x4) | `ATLEAST_DRAW b` | 52 | 0 | 1,290 | 0.0044 |
| `k3/p1p1/PpPp/1P1P/3K w - -` (blocked 4x5) | `ATLEAST_DRAW w` | 6 | 0 | 274 | 0.0005 |
| `k3/p1p1/PpPp/1P1P/3K w - -` (blocked 4x5) | `ATLEAST_DRAW b` | 4 | 0 | 204 | 0.0004 |

---

## 5. Known gaps

- **Cross-check with `02-engine` not yet run**: per `TASK.md`, `03-checker` did not inspect `02-engine`. Once both exist, the lead session or a harness should run random positions through `02-engine` and `mcheck.py batch` to cross-verify move-for-move agreement.
- **Pure-Python throughput**: by design (`TASK.md` "Out of scope: Speed"), `mcheck.py` loads all entries into memory and runs pure Python move generation (~10k–20k entries/second depending on board size). Very large certificates (millions of entries) will require a faster secondary checker validated against this one.

---

## 6. Spec issues

Per `AGENTS.md`, we did not deviate from `design/SPEC.md`; we took the conservative reading and record the ambiguities discovered:

1. **`ATLEAST_DRAW` cannot represent prover-stalemate positions.** In SPEC section 4, an `ATLEAST_DRAW` certificate requires every entry `(p, m, 0)` to have a legal move `m` for the prover, and requires every opponent reply `q.r` (and a prover-to-move `#root`) to be an entry. If `q.r` (or `#root`) is a stalemate with the prover to move (0 legal moves, not in check), it is a drawn position in the game, yet no valid entry `(q.r, m, 0)` exists because the prover has no legal move. We encountered this concretely when testing `k3/1p2/1P2/3K w - -`, where Black can force stalemate into `4/1p2/1Pk1/K3 w - -`. Conservative reading implemented: `mcheck.py` enforces SPEC section 4 literally (every `q.r` and prover-to-move `#root` must be an entry with a legal move). A future SPEC revision could exempt prover-stalemate positions in `ATLEAST_DRAW` Rule 2 / Root, or define a sentinel move `-` for stalemate.
2. **Rank domain in `WIN` certificates (`d >= 0` vs `d >= 1`).** SPEC section 4 specifies "an integer rank (`0` in ATLEAST_DRAW certificates)" and states "the prover mates from every entry within `d` own moves", without explicitly stating the minimum allowed rank for `WIN`. Conservative reading implemented: `mcheck.py` accepts canonical non-negative ASCII integers (`d >= 0`, no leading zeros or `+`/`-`), which guarantees well-founded induction and accommodates both 0-based (remaining own moves after `m`) and 1-based / ply-based distance conventions while rejecting negative or non-canonical rank strings.
3. **Position legality edge cases in `parse_position`.** SPEC section 2 requires one king per side, no moving into/staying in check, and mandatory promotion on the last rank, but does not explicitly state whether `parse_position` must reject (a) opponent (non-stm) king in check, or (b) pawns on rank 1 / rank `H`. Conservative reading implemented: `parse_position` rejects non-stm in check (preventing king capture) and rejects unpromoted pawns on their own promotion rank (`P` on rank `H`, `p` on rank `1`), while permitting `P` on rank `1` / `p` on rank `H` (single-step only).
4. **Blank lines, extra comments, and mixed board sizes in certificates.** SPEC section 4 does not mention blank lines, body `#` comments, or entries whose board dimensions differ from `#root`. Conservative reading implemented: all three are rejected as `INVALID`.
5. **Output `<position>` field in `mcheck.py batch`.** When stdin supplies a valid position with trailing FEN halfmove/fullmove counters or a non-legal `ep` square, `mcheck.py batch` outputs the canonical 4-field position string before the tab; on invalid lines it echoes the raw input line followed by `\tERROR`.

---

## Round 2 (SPEC v1.1 update)

### 1. Changes made

- **`mcheck.py`** (now 331 lines total):
  - Added `_is_prover_stalemate(pos, prover)` (`pos.stm == prover and not in_check(pos) and not legal_moves(pos)`).
  - Updated `verify_certificate` so that for `ATLEAST_DRAW` certificates only, a prover-stalemate position counts as **covered** without an entry: at a prover-to-move `#root`, at any opponent reply from `#root`, and at any opponent reply `q.r` from a body entry `(p, m, 0)`.
  - Verified that `WIN` certificates do **not** get the stalemate exemption, that prover checkmate is never covered, and that listing a prover-stalemate position as a body entry is rejected (no legal move).
- **`rules.py`** (now 623 lines total):
  - `parse_position` now rejects any pawn of either colour (`'P'` or `'p'`) on rank `1` or rank `H` (SPEC v1.1 section 3).
  - `parse_position` now enforces that every castling letter in `KQkq` on 8x8 has the corresponding king and rook on their original squares (`K`: `K` on `e1` and `R` on `h1`; `Q`: `K` on `e1` and `R` on `a1`; `k`: `k` on `e8` and `r` on `h8`; `q`: `k` on `e8` and `r` on `a8`).
- **`tests/mini_solver.py`**:
  - Updated `build_atleast_draw_certificate` to compute the greatest fixed point over the SPEC v1.1 covered set (including prover-stalemate positions) and omit prover-stalemate positions from the emitted body entries.
- **`AUDIT.md`**:
  - Updated sections 1–3 to match SPEC v1.1, documenting the rank-1/rank-`H` pawn rule, original-square castling check, `_is_prover_stalemate`, and the covered-set ($C = E \cup S_P$) soundness proof for `ATLEAST_DRAW`.
- **New tests added** (7 new test methods across `tests/test_mini_boards.py`, `tests/test_perft_8x8.py`, and `tests/test_certificates.py`):
  - `test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K`: generates and verifies both `ATLEAST_DRAW w` and `ATLEAST_DRAW b` for `k3/1p2/1P2/3K w - -`, confirming prover-stalemate replies are exercised.
  - `test_v1_1_win_rejects_prover_stalemate_reply`: verifies that a reply stalemating the prover is `VALID` in `ATLEAST_DRAW` and `INVALID` in `WIN` (both from a body entry and from an opponent-to-move root).
  - `test_v1_1_atleast_draw_rejects_prover_checkmate_reply`: verifies that a reply checkmating the prover is `INVALID` in `ATLEAST_DRAW` (both from a body entry and from an opponent-to-move root).
  - `test_v1_1_prover_stalemate_root_empty_body`: verifies that a prover-stalemate root with empty body is `VALID` for `ATLEAST_DRAW` (both sides), `INVALID` for `WIN`, `INVALID` if listed as an entry, and that a prover-checkmate root with empty body is `INVALID` for `ATLEAST_DRAW`.
  - `test_pawns_on_rank_1_or_top_rank_rejected_v1_1` & `test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs`: verifies rejection of `P`/`p` on rank 1 or rank `H` across 3x3, 5x5, and 8x8 in both `parse_position` and `verify_certificate`, plus castling original-square checks, leading-zero/signed ranks (`00`, `01`, `+1`, `-0`), and body comments.
  - `test_castling_requires_king_and_rook_on_original_squares_v1_1`: tests missing/misplaced king or rook for each of `K`, `Q`, `k`, `q`.
- **Round 1 test changes**: none. All 34 round 1 tests pass unchanged.

### 2. Measured numbers (new v1.1 certificates)

Reproduced by `tests.mini_solver.build_atleast_draw_certificate` + `mcheck.verify_certificate`:

| Position | Claim | Entries | Max Rank | Bytes | Check Time (s) |
|---|---|---:|---:|---:|---:|
| `k3/1p2/1P2/3K w - -` | `ATLEAST_DRAW w` | 16 | 0 | 502 | 0.0017 |
| `k3/1p2/1P2/3K w - -` | `ATLEAST_DRAW b` | 14 | 0 | 446 | 0.0014 |

### 3. Full test output (Round 2)

Command: `cd /home/dege/chess/03-checker && python3 -m unittest discover -s tests -v`

```text
test_cli_batch (test_certificates.TestCLI.test_cli_batch) ... ok
test_cli_moves (test_certificates.TestCLI.test_cli_moves) ... ok
test_cli_perft (test_certificates.TestCLI.test_cli_perft) ... ok
test_cli_verify_valid_and_invalid (test_certificates.TestCLI.test_cli_verify_valid_and_invalid) ... ok
test_all_required_mutations_rejected (test_certificates.TestCertificatesAndMutations.test_all_required_mutations_rejected) ... ok
test_cycle_rejected_in_win_and_accepted_in_atleast_draw (test_certificates.TestCertificatesAndMutations.test_cycle_rejected_in_win_and_accepted_in_atleast_draw) ... ok
test_malformed_files_never_crash (test_certificates.TestCertificatesAndMutations.test_malformed_files_never_crash) ... ok
test_opponent_to_move_terminal_roots (test_certificates.TestCertificatesAndMutations.test_opponent_to_move_terminal_roots) ... ok
test_real_draw_certificates_kvk_and_blocked (test_certificates.TestCertificatesAndMutations.test_real_draw_certificates_kvk_and_blocked) ... ok
test_real_kq_vs_k_4x4_win_certificates (test_certificates.TestCertificatesAndMutations.test_real_kq_vs_k_4x4_win_certificates) ... ok
test_unreachable_invalid_entry_is_rejected (test_certificates.TestCertificatesAndMutations.test_unreachable_invalid_entry_is_rejected) ... ok
test_v1_1_atleast_draw_rejects_prover_checkmate_reply (test_certificates.TestCertificatesAndMutations.test_v1_1_atleast_draw_rejects_prover_checkmate_reply) ... ok
test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs (test_certificates.TestCertificatesAndMutations.test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs) ... ok
test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K (test_certificates.TestCertificatesAndMutations.test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K) ... ok
test_v1_1_prover_stalemate_root_empty_body (test_certificates.TestCertificatesAndMutations.test_v1_1_prover_stalemate_root_empty_body) ... ok
test_v1_1_win_rejects_prover_stalemate_reply (test_certificates.TestCertificatesAndMutations.test_v1_1_win_rejects_prover_stalemate_reply) ... ok
test_check_evasion_capture_block_and_double_check (test_mini_boards.TestMiniBoards.test_check_evasion_capture_block_and_double_check) ... ok
test_checkmate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_checkmate_on_3x3_4x4_5x5) ... ok
test_named_mini_start_positions_parse_and_roundtrip (test_mini_boards.TestMiniBoards.test_named_mini_start_positions_parse_and_roundtrip) ... ok
test_no_castling_or_ep_off_8x8 (test_mini_boards.TestMiniBoards.test_no_castling_or_ep_off_8x8) ... ok
test_parser_rejects_invalid_positions (test_mini_boards.TestMiniBoards.test_parser_rejects_invalid_positions) ... ok
test_pawns_on_rank_1_or_top_rank_rejected_v1_1 (test_mini_boards.TestMiniBoards.test_pawns_on_rank_1_or_top_rank_rejected_v1_1) ... ok
test_pins_on_mini_boards (test_mini_boards.TestMiniBoards.test_pins_on_mini_boards) ... ok
test_promotion_on_3x3_and_4x4 (test_mini_boards.TestMiniBoards.test_promotion_on_3x3_and_4x4) ... ok
test_single_step_pawns_only_on_mini_boards (test_mini_boards.TestMiniBoards.test_single_step_pawns_only_on_mini_boards) ... ok
test_stalemate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_stalemate_on_3x3_4x4_5x5) ... ok
test_castling_blocked_by_attacked_transit_square_but_not_b1 (test_perft_8x8.Test8x8RulesDetails.test_castling_blocked_by_attacked_transit_square_but_not_b1) ... ok
test_castling_requires_king_and_rook_on_original_squares_v1_1 (test_perft_8x8.Test8x8RulesDetails.test_castling_requires_king_and_rook_on_original_squares_v1_1) ... ok
test_castling_rights_lost_on_rook_capture_and_king_move (test_perft_8x8.Test8x8RulesDetails.test_castling_rights_lost_on_rook_capture_and_king_move) ... ok
test_ep_cleared_under_horizontal_pin (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_under_horizontal_pin) ... ok
test_ep_cleared_when_no_adjacent_pawn (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_when_no_adjacent_pawn) ... ok
test_ep_set_when_it_resolves_check_by_capturing_checker (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_it_resolves_check_by_capturing_checker) ... ok
test_ep_set_when_legal_capture_exists (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_legal_capture_exists) ... ok
test_ep_set_when_only_one_of_two_pawns_is_pinned (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_only_one_of_two_pawns_is_pinned) ... ok
test_trailing_fen_counters_accepted_and_stripped (test_perft_8x8.Test8x8RulesDetails.test_trailing_fen_counters_accepted_and_stripped) ... ok
test_kiwipete_perft (test_perft_8x8.TestPerft8x8.test_kiwipete_perft) ... ok
test_perft_matches_full_apply_recursion (test_perft_8x8.TestPerft8x8.test_perft_matches_full_apply_recursion) ... ok
test_position3_perft (test_perft_8x8.TestPerft8x8.test_position3_perft) ... ok
test_position4_perft (test_perft_8x8.TestPerft8x8.test_position4_perft) ... ok
test_position5_perft (test_perft_8x8.TestPerft8x8.test_position5_perft) ... ok
test_startpos_perft (test_perft_8x8.TestPerft8x8.test_startpos_perft) ... ok

----------------------------------------------------------------------
Ran 41 tests in 6.331s

OK
```

### 4. Spec issues / open notes (Round 2)

- Round 1 spec issues 1–4 are now resolved by SPEC v1.1.
- **Pseudo-en-passant squares in `parse_position` vs `verify_certificate`**: SPEC v1.1 section 3 states `ep` is "set only if at least one legal en-passant capture exists", while also stating readers accept trailing FEN counters. As in round 1 (and tested by `test_ep_cleared_when_no_adjacent_pawn`), `parse_position` accepts a geometrically valid standard FEN `ep` square (e.g., `e3 0 1` after `1. e4`) and normalizes `ep` to `None` when no legal capture exists, whereas `verify_certificate` requires canonical equality (`pos.to_fen() == pos_str`) and rejects any non-canonical `ep` string in a certificate. If the spec intends `parse_position` itself (e.g., in `mcheck.py moves`/`batch`) to reject non-legal `ep` squares as `ERROR` rather than normalizing them, that should be clarified explicitly in a future spec revision.

---

## Round 3 (SPEC v1.2 update)

### 1. Changes made

- **`mcheck.py`** (now 339 lines total):
  - `verify_certificate` now reads the file in binary mode (`open(path, "rb")`) and decodes strictly as UTF-8 (`decode("utf-8")`), avoiding Python's universal newline translation.
  - Immediately rejects any certificate containing a carriage return (`\r`) anywhere in the file (reporting the 1-based line number of the first `\r`).
  - Strips at most one trailing `\n` (so a missing final `\n` is accepted while a trailing blank line `\n\n` remains `INVALID`) and splits strictly on `\n` (not `splitlines()`).
  - Removed `_strip_newline` from certificate verification (retaining plain line-ending trimming only inside `_cmd_batch` for stdin lines).
- **`rules.py`** (now 638 lines total):
  - `parse_position` now enforces the full SPEC v1.2 section 3 `ep` well-formedness check: when `ep != "-"` on 8x8, it requires rank 6 (White) / rank 3 (Black), empty target square, **empty double-step origin square** on rank 7 (White) / rank 2 (Black), enemy pawn in front on rank 5 / rank 4, **and at least one legal en-passant capture** (`_has_legal_ep_capture`), raising `ValueError` otherwise instead of silently normalizing to `None`.
  - **Additional line-by-line audit fix (`rules.py`)**: `parse_position` previously accepted an empty `castling` field on 8x8 (e.g., `"4k3/8/8/8/8/8/8/4K3 w  -"` where two spaces produced `castling_str == ""`, executing zero iterations of `for ch in castling_str:`). Added an explicit `if not castling_str: raise ValueError("empty castling field")` check.
- **`AUDIT.md`**:
  - Updated to SPEC v1.2, documenting the non-empty castling check, all five `ep` validity conditions in `rules.py`, and binary UTF-8 / `\n`-only / no-`\r` handling in `mcheck.py`.
- **Tests added / updated** (4 new test methods; 1 Round 1 test updated for SPEC v1.2):
  - `tests/test_certificates.py`:
    - `test_v1_2_line_endings_and_carriage_returns`: verifies `\n` with and without final newline (including empty-body root) are `VALID`; `\r\n` (with/without final `\r\n`), bare `\r` as sole line break, bare `\r` inside header/body lines, trailing `\r` at EOF, and trailing blank line `\n\n` are all `INVALID`.
    - `test_v1_2_ep_well_formedness_in_certificates`: verifies valid 1-entry en-passant mate certificates for both White and mirrored Black, and verifies certificates with origin occupied (including `4k3/4p3/8/3Pp3/8/8/8/4K3 w - e6`), target occupied, no enemy pawn in front, wrong rank, and pinned capturing pawn are all `INVALID`.
  - `tests/test_perft_8x8.py`:
    - `test_ep_well_formedness_v1_2`: tests all six `ep` categories for White to move and mirrored for Black to move (origin square occupied, target square occupied, no enemy pawn in front, wrong rank, capturing pawn pinned / absent, and a valid legal `ep` position).
    - `test_empty_castling_field_rejected_v1_2`: tests rejection of `"4k3/8/8/8/8/8/8/4K3 w  -"`.
    - Updated `test_ep_cleared_when_no_adjacent_pawn`: previously (Round 1 / SPEC v1.0) asserted that `parse_position("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")` normalized `e3` to `None`; under SPEC v1.2 section 3 ("every reader rejects anything else: ... and at least one en-passant capture onto it is legal"), it now asserts `ValueError` on `e3` while still asserting that `apply_move(..., "e2e4")` emits `-` and that `"… b KQkq - 0 1"` is accepted and stripped.

### 2. Audit findings against SPEC v1.2

Line-by-line review of SPEC v1.2 sections 2–4 against `rules.py` and `mcheck.py` found four discrepancies, all fixed above:
1. Universal newlines and trailing `\r` stripping in `mcheck.py` (SPEC v1.2 item 5).
2. Missing check that the double-step origin square (rank 7 / rank 2) is empty when `ep != "-"` in `rules.py` (SPEC v1.2 item 6).
3. `parse_position` normalizing an `ep` square with no legal capture to `None` instead of rejecting it (resolved Round 2 open note; now rejected by every reader per SPEC v1.2 section 3).
4. `parse_position` accepting an empty `castling` field on 8x8 caused by a double space (`w  -`).

No remaining discrepancies were found between SPEC v1.2 and `rules.py` / `mcheck.py`.

### 3. Full test output (Round 3)

Command: `cd /home/dege/chess/03-checker && python3 -m unittest discover -s tests -v`

```text
test_cli_batch (test_certificates.TestCLI.test_cli_batch) ... ok
test_cli_moves (test_certificates.TestCLI.test_cli_moves) ... ok
test_cli_perft (test_certificates.TestCLI.test_cli_perft) ... ok
test_cli_verify_valid_and_invalid (test_certificates.TestCLI.test_cli_verify_valid_and_invalid) ... ok
test_all_required_mutations_rejected (test_certificates.TestCertificatesAndMutations.test_all_required_mutations_rejected) ... ok
test_cycle_rejected_in_win_and_accepted_in_atleast_draw (test_certificates.TestCertificatesAndMutations.test_cycle_rejected_in_win_and_accepted_in_atleast_draw) ... ok
test_malformed_files_never_crash (test_certificates.TestCertificatesAndMutations.test_malformed_files_never_crash) ... ok
test_opponent_to_move_terminal_roots (test_certificates.TestCertificatesAndMutations.test_opponent_to_move_terminal_roots) ... ok
test_real_draw_certificates_kvk_and_blocked (test_certificates.TestCertificatesAndMutations.test_real_draw_certificates_kvk_and_blocked) ... ok
test_real_kq_vs_k_4x4_win_certificates (test_certificates.TestCertificatesAndMutations.test_real_kq_vs_k_4x4_win_certificates) ... ok
test_unreachable_invalid_entry_is_rejected (test_certificates.TestCertificatesAndMutations.test_unreachable_invalid_entry_is_rejected) ... ok
test_v1_1_atleast_draw_rejects_prover_checkmate_reply (test_certificates.TestCertificatesAndMutations.test_v1_1_atleast_draw_rejects_prover_checkmate_reply) ... ok
test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs (test_certificates.TestCertificatesAndMutations.test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs) ... ok
test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K (test_certificates.TestCertificatesAndMutations.test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K) ... ok
test_v1_1_prover_stalemate_root_empty_body (test_certificates.TestCertificatesAndMutations.test_v1_1_prover_stalemate_root_empty_body) ... ok
test_v1_1_win_rejects_prover_stalemate_reply (test_certificates.TestCertificatesAndMutations.test_v1_1_win_rejects_prover_stalemate_reply) ... ok
test_v1_2_ep_well_formedness_in_certificates (test_certificates.TestCertificatesAndMutations.test_v1_2_ep_well_formedness_in_certificates) ... ok
test_v1_2_line_endings_and_carriage_returns (test_certificates.TestCertificatesAndMutations.test_v1_2_line_endings_and_carriage_returns) ... ok
test_check_evasion_capture_block_and_double_check (test_mini_boards.TestMiniBoards.test_check_evasion_capture_block_and_double_check) ... ok
test_checkmate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_checkmate_on_3x3_4x4_5x5) ... ok
test_named_mini_start_positions_parse_and_roundtrip (test_mini_boards.TestMiniBoards.test_named_mini_start_positions_parse_and_roundtrip) ... ok
test_no_castling_or_ep_off_8x8 (test_mini_boards.TestMiniBoards.test_no_castling_or_ep_off_8x8) ... ok
test_parser_rejects_invalid_positions (test_mini_boards.TestMiniBoards.test_parser_rejects_invalid_positions) ... ok
test_pawns_on_rank_1_or_top_rank_rejected_v1_1 (test_mini_boards.TestMiniBoards.test_pawns_on_rank_1_or_top_rank_rejected_v1_1) ... ok
test_pins_on_mini_boards (test_mini_boards.TestMiniBoards.test_pins_on_mini_boards) ... ok
test_promotion_on_3x3_and_4x4 (test_mini_boards.TestMiniBoards.test_promotion_on_3x3_and_4x4) ... ok
test_single_step_pawns_only_on_mini_boards (test_mini_boards.TestMiniBoards.test_single_step_pawns_only_on_mini_boards) ... ok
test_stalemate_on_3x3_4x4_5x5 (test_mini_boards.TestMiniBoards.test_stalemate_on_3x3_4x4_5x5) ... ok
test_castling_blocked_by_attacked_transit_square_but_not_b1 (test_perft_8x8.Test8x8RulesDetails.test_castling_blocked_by_attacked_transit_square_but_not_b1) ... ok
test_castling_requires_king_and_rook_on_original_squares_v1_1 (test_perft_8x8.Test8x8RulesDetails.test_castling_requires_king_and_rook_on_original_squares_v1_1) ... ok
test_castling_rights_lost_on_rook_capture_and_king_move (test_perft_8x8.Test8x8RulesDetails.test_castling_rights_lost_on_rook_capture_and_king_move) ... ok
test_empty_castling_field_rejected_v1_2 (test_perft_8x8.Test8x8RulesDetails.test_empty_castling_field_rejected_v1_2) ... ok
test_ep_cleared_under_horizontal_pin (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_under_horizontal_pin) ... ok
test_ep_cleared_when_no_adjacent_pawn (test_perft_8x8.Test8x8RulesDetails.test_ep_cleared_when_no_adjacent_pawn) ... ok
test_ep_set_when_it_resolves_check_by_capturing_checker (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_it_resolves_check_by_capturing_checker) ... ok
test_ep_set_when_legal_capture_exists (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_legal_capture_exists) ... ok
test_ep_set_when_only_one_of_two_pawns_is_pinned (test_perft_8x8.Test8x8RulesDetails.test_ep_set_when_only_one_of_two_pawns_is_pinned) ... ok
test_ep_well_formedness_v1_2 (test_perft_8x8.Test8x8RulesDetails.test_ep_well_formedness_v1_2) ... ok
test_trailing_fen_counters_accepted_and_stripped (test_perft_8x8.Test8x8RulesDetails.test_trailing_fen_counters_accepted_and_stripped) ... ok
test_kiwipete_perft (test_perft_8x8.TestPerft8x8.test_kiwipete_perft) ... ok
test_perft_matches_full_apply_recursion (test_perft_8x8.TestPerft8x8.test_perft_matches_full_apply_recursion) ... ok
test_position3_perft (test_perft_8x8.TestPerft8x8.test_position3_perft) ... ok
test_position4_perft (test_perft_8x8.TestPerft8x8.test_position4_perft) ... ok
test_position5_perft (test_perft_8x8.TestPerft8x8.test_position5_perft) ... ok
test_startpos_perft (test_perft_8x8.TestPerft8x8.test_startpos_perft) ... ok

----------------------------------------------------------------------
Ran 45 tests in 12.344s

OK
```

### 4. Spec issues / open notes (Round 3)

- None. SPEC v1.2 resolved the Round 2 open note regarding `ep` without a legal capture in `parse_position`.
