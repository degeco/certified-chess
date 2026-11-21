# 05-solver Report: Certified Proof Search (`msolve`)

> **Rule caveat (`SPEC.md` section 2):** All values and certificates proven here are for the idealised `SPEC v1.1` game (full FIDE movement on `8x8`, mini rules off `8x8`, infinite play = draw; no 50-move rule, no threefold-repetition rule, and no insufficient-material adjudication). Under FIDE 50/75-move rules, long forced mates can become draws.

## 1. What Was Built

Linked directly against `../02-engine/build/libmchess.a` (C++17, zero external dependencies). All files reside inside `05-solver/`:

- [`Makefile`](Makefile): builds `./msolve` and `./build/test_solver`, runs `make test`.
- [`src/common.hpp`](src/common.hpp): claim/status types, limits, packed moves, prover-stalemate helper, fast static material/advancement evaluation, tactical move ordering.
- [`src/certificate.hpp`](src/certificate.hpp), [`src/certificate.cpp`](src/certificate.cpp): `SPEC v1.1` `#cert v1` representation, deterministic writer, strict internal verifier, `WIN -> ATLEAST_DRAW` conversion, and certificate minimiser (reachability pruning + iterative move re-selection/merging + topological rank tightening).
- [`src/dfpn.hpp`](src/dfpn.hpp), [`src/dfpn.cpp`](src/dfpn.cpp): bounded-memory depth-first proof-number search (`df-pn`) for `WIN` claims, plus `solve_draw_via_disproof` for extracting `ATLEAST_DRAW` closed-set certificates from `WIN ~prover` disproof witnesses.
- [`src/draw_solver.hpp`](src/draw_solver.hpp), [`src/draw_solver.cpp`](src/draw_solver.cpp): 3-phase `ATLEAST_DRAW` solver combining bounded `WIN` probes, explicit Closed-Set Invariant Search, and `df-pn` disproof-witness extraction.
- [`src/main.cpp`](src/main.cpp): CLI binary `msolve`:
  - `msolve "<position|name>" --claim <WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b> [--out file.cert] [--max-nodes N] [--max-seconds S] [--tt-mb M] [--no-minimize] [--verbose]`
  - `msolve "<position|name>" --value [--out file.cert | --out-prefix prefix] [--max-nodes N] [--max-seconds S] [--tt-mb M] [--no-minimize]`
  - Exit status: `0` = `PROVED` (or exact value found in `--value`), `1` = `DISPROVED`, `2` = `LIMIT`, `3` = `ERROR`.
- [`tests/test_solver.cpp`](tests/test_solver.cpp) and [`tests/verify_all.py`](tests/verify_all.py): C++ unit tests + end-to-end integration tests verifying every emitted certificate with `../03-checker/mcheck.py`.
- [`certs/`](certs/): verified `#cert v1` certificates from the experiment ladder.

## 2. Algorithmic Design

### 2.1 `WIN` Search (`DfpnSolver`)
- **Bounded 4-way set-associative transposition table (`--tt-mb`, default 256 MB, capped at 3072 MB):** 24 bytes/entry, fixed allocation at startup (no unbounded growth). Slots 0..2 protect solved (`pn==0` or `dn==0`) and high-work entries; slot 3 serves as scratch fallback for unsolved entries. A bounded secondary `proof_moves_` cache preserves winning moves under TT pressure.
- **Heap-backed child arena (`child_arena_`):** avoids putting `ChildInfo[MAX_MOVES]` (~60 KB) on the call stack, preventing stack overflow on deep lines (up to `MAX_DFPN_DEPTH = 240`).
- **DAG overflow & `1+eps` thresholds:** distinguishes finite proof/disproof sums (`MAX_FINITE = 1e9`) from true proved/disproved infinity (`INF = 2e9`) so DAG transposition double-counting cannot falsely trigger root termination; applies `eps = 0.25` threshold scaling to reduce DAG thrashing.
- **GHI-safe cycle handling:** tracks exact active path positions (`path_pos_` + bloom filter) and propagates `min_cycle_depth`. A `pn==0` win never uses cycles and is always safe to store in TT. A `dn==0` disproof is committed permanently to TT only when `min_cycle_depth >= depth` (no dependency on strict ancestors); hitting `MAX_DFPN_DEPTH` returns `min_cycle_depth = -1` and is never treated as a valid disproof.
- **Forcing & material-aware leaf initialization:** checks 1-ply checkmates immediately on checking moves, sets checking AND-node `pn = legal_replies`, and biases non-checking leaf `(pn, dn)` by static material balance (`±400 cp`).
- **Exact proof extraction:** reconstructs the certificate keyed by canonical FEN (`Position::to_fen()`), re-solving any TT-evicted subtree on demand, and runs `Certificate::verify()` before writing.

### 2.2 `ATLEAST_DRAW` Search (`DrawSolver`)
An `ATLEAST_DRAW <prover>` certificate is a finite closed set $S$ of prover-to-move positions with a move $\sigma(p)$ for each $p \in S$ such that every legal opponent reply to $p.\sigma(p)$ lands in $S$ or is a prover stalemate (SPEC v1.1). `DrawSolver` uses three phases:
1. **Quick bounded `WIN` probes (up to 100k nodes / 2s per side):** if `WIN <prover>` is proved, it converts directly to an `ATLEAST_DRAW <prover>` certificate (ranks set to 0); if `WIN <~prover>` is proved, `ATLEAST_DRAW <prover>` is immediately `DISPROVED`.
2. **Closed-Set Invariant Search (`ClosedSetSearch`, up to 25% remaining budget / 4s, memory-bounded `std::deque<OrNode>`):** explicitly grows a candidate closed strategy graph from the root. Prover moves are scored to prefer (a) immediate opponent mate/stalemate, (b) total closure (`new_count == 0`, all opponent replies already in the active set or prover stalemate), and (c) low new-frontier branching combined with exact shallow alpha-beta tactical safety (rejecting forced opponent mates) and periodic mini-`df-pn` refutation checks on dangerous frontier nodes. When a frontier node is disproved, `DISPROVED` propagates upward through parent back-pointers and switches ancestor moves. A periodic shortcut-collapse pass retroactively switches active nodes to moves that close into already-expanded active nodes. This closes small/fortress/endgame draws (e.g., `K vs K`) in milliseconds with tiny closed sets.
3. **`df-pn` Disproof-Witness Extraction (`DfpnSolver::solve_draw_via_disproof`, remaining budget):** exploits finite reachability-safety determinacy (`¬WIN(~prover) <=> ATLEAST_DRAW(prover)`). Runs full `df-pn` on `WIN <~prover>` while recording the defending AND-node disproof moves (`disproof_moves_`). When `WIN <~prover>` is disproved (`dn == 0`, `min_cycle_depth >= 0`), BFS extracts a closed set preferring immediate leaves, moves landing in already-visited entries, and recorded disproof moves, with a re-solve fallback that treats already-committed closed-set positions as safe cycle targets (`safe_cycle_targets_`). On tactical midgame positions like `mini4x5`, this phase proved `ATLEAST_DRAW w` in 5.92 s (6,107 entries, verified `VALID` by `mcheck.py`).

### 2.3 Certificate Minimisation (`Certificate::minimize`)
1. **Pass 1 (Reachability pruning):** BFS from the root under chosen moves; drops all unreachable entries.
2. **Pass 2 (Iterative move re-selection / merging):** for each active entry $p$, scans all other legal moves whose replies stay inside the active set (or prover stalemate for `ATLEAST_DRAW`, and preserving acyclicity for `WIN`). For certificates with `<= 3000` entries, evaluates exact post-switch reachable size; for larger certificates, uses a fast local exclusive-child / out-degree heuristic across up to 3 passes.
3. **Pass 3 (Rank tightening, `WIN` only):** recomputes exact minimal DAG longest-path ranks (`1` for mate-in-1, `1 + max(child_rank)` otherwise).

## 3. Build and Test

Exact build and test command (from `/home/dege/chess/05-solver`):

```sh
make -j4 test
```

Actual `make -j4 test` output:

```text
g++ -O3 -std=c++17 -Wall -Wextra -Wpedantic -I../02-engine/src build/certificate.o build/dfpn.o build/draw_solver.o tests/test_solver.cpp ../02-engine/build/libmchess.a -o build/test_solver
./build/test_solver
[PASS] WIN w on already-checkmated root (0 entries)
[PASS] Test stalemate position is stalemate
[PASS] WIN w on prover stalemate is DISPROVED
[PASS] ATLEAST_DRAW w on prover stalemate is PROVED (0 entries)
[PASS] K vs K 3x3 ATLEAST_DRAW w PROVED
[PASS] K vs K 3x3 ATLEAST_DRAW b PROVED
[PASS] mini4x4 WIN w proved (entries=5, max_rank=4)
[PASS] mini4x4 ATLEAST_DRAW w PROVED
[PASS] mini4x4 ATLEAST_DRAW b DISPROVED
[PASS] 8x8 mate in 2 proved (entries=2, max_rank=2)
[PASS] 8x8 mate in 3 proved (entries=4, max_rank=3)
[PASS] 8x8 mate in 4 proved (entries=5, max_rank=4)
[PASS] 8x8 mate in 5 proved (entries=9, max_rank=5)
[PASS] mini4x4 raw WIN w extracted
[PASS] Synthetic unreachable mate-in-1 valid
[PASS] Bloated certificate with unreachable entry is valid before minimize
[PASS] Minimiser dropped unreachable entry (6 -> 5 -> 5)
ALL C++ UNIT TESTS PASSED
python3 tests/verify_all.py
[PASS] 8x8_mate2: msolve exit 0 (got 0)
[PASS] 8x8_mate2: mcheck VALID (VALID)
[PASS] 8x8_mate2: max_rank=2 <= 2
[PASS] 8x8_mate3_br: msolve exit 0 (got 0)
[PASS] 8x8_mate3_br: mcheck VALID (VALID)
[PASS] 8x8_mate3_br: max_rank=3 <= 3
[PASS] 8x8_mate3_phil: msolve exit 0 (got 0)
[PASS] 8x8_mate3_phil: mcheck VALID (VALID)
[PASS] 8x8_mate3_phil: max_rank=3 <= 3
[PASS] 8x8_mate4_phil: msolve exit 0 (got 0)
[PASS] 8x8_mate4_phil: mcheck VALID (VALID)
[PASS] 8x8_mate4_phil: max_rank=4 <= 4
[PASS] 8x8_mate5_phil: msolve exit 0 (got 0)
[PASS] 8x8_mate5_phil: mcheck VALID (VALID)
[PASS] 8x8_mate5_phil: max_rank=5 <= 5
[PASS] mini4x4_KQ_K: msolve exit 0 (got 0)
[PASS] mini4x4_KQ_K: mcheck VALID (VALID)
[PASS] mini4x4 WIN w proved (rc=0)
[PASS] mini4x4 WIN w mcheck VALID
[PASS] mini4x4 --value == WIN w
[PASS] mini4x4 --value cert mcheck VALID
[PASS] kvk3x3 --value == DRAW
[PASS] kvk3x3 both ATLEAST_DRAW certs mcheck VALID
[PASS] kvk4x4 --value == DRAW
[PASS] kvk4x4 both ATLEAST_DRAW certs mcheck VALID
[PASS] prover-stalemate ATLEAST_DRAW w exit 0
[PASS] prover-stalemate ATLEAST_DRAW w mcheck VALID (0 entries)
[PASS] stalemate_b ATLEAST_DRAW b exit 0
[PASS] stalemate_b ATLEAST_DRAW b mcheck VALID
ALL PYTHON + MCHECK INTEGRATION TESTS PASSED
```

## 4. Experiment Ladder Results

All certificates below were independently verified with `python3 ../03-checker/mcheck.py verify <cert>`.

### Steps 1 & 2: 8x8 Forced Mates, `K vs K` Draw Baseline, and `mini4x4`

| Root / Case | Claim | Solver Status | Entries (raw -> min) | File Bytes | Max Rank | Nodes | Solver (s) | Checker (s) | `mcheck.py` Verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `8x8_mate2`: `3r2k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - -` | `WIN w` | PROVED | 2 -> 2 | 152 | 2 | 3 | 0.0001 | 0.0010 | **VALID** |
| `8x8_mate3`: `4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -` | `WIN w` | PROVED | 4 -> 4 | 225 | 3 | 6 | 0.0002 | 0.0020 | **VALID** |
| `8x8_mate4`: `4r2k/6pp/8/6N1/8/1Q6/6PP/6K1 w - -` | `WIN w` | PROVED | 5 -> 5 | 267 | 4 | 8 | 0.0002 | 0.0015 | **VALID** |
| `8x8_mate5`: `2r3k1/6pp/8/6N1/1Q6/8/5PPP/6K1 w - -` | `WIN w` | PROVED | 9 -> 9 | 450 | 5 | 51 | 0.0007 | 0.0022 | **VALID** |
| `kvk4x4`: `k3/4/4/3K w - -` | `ATLEAST_DRAW w` | PROVED | 17 -> 17 | 464 | 0 | 2,367 | 0.0067 | 0.0023 | **VALID** |
| `kvk4x4`: `k3/4/4/3K w - -` | `ATLEAST_DRAW b` | PROVED | 33 -> 33 | 840 | 0 | 2,702 | 0.0071 | 0.0039 | **VALID** |
| `mini4x4`: `rqkr/pppp/PPPP/RQKR w - -` | `WIN w` | PROVED | 5 -> 5 | 216 | 4 | 16 | 0.0001 | 0.0010 | **VALID** |
| `mini4x4`: `rqkr/pppp/PPPP/RQKR w - -` | `ATLEAST_DRAW w` | PROVED | 5 -> 5 | 225 | 0 | 16 | 0.0020 | 0.0008 | **VALID** |
| `mini4x4`: `rqkr/pppp/PPPP/RQKR w - -` | `ATLEAST_DRAW b` | DISPROVED | — | — | — | 36 | 0.0028 | — | N/A (disproved via `WIN w`) |

- **`mini4x4` value (certified):** **`WIN w`** (forced mate in 4; `certs/mini4x4_win_w.cert`, 5 entries, 216 bytes; note that before adding material-aware PN init, `df-pn` also found the 4-entry `1. c2d3` forced line with 184 bytes, `max_rank=4`, `mcheck.py VALID`).
- **`kvk4x4` value (certified):** **`DRAW`** (`ATLEAST_DRAW w` + `ATLEAST_DRAW b`, both `VALID`).

Reproducing commands:
```sh
./msolve mini4x4 --claim "WIN w" --out certs/mini4x4_win_w.cert --max-seconds 15 --tt-mb 64
python3 ../03-checker/mcheck.py verify certs/mini4x4_win_w.cert
./msolve mini4x4 --value --max-seconds 15 --tt-mb 64
```

### Step 3: `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`)

**Certified lower bound on `mini4x5`:** **`ATLEAST_DRAW w` is PROVED and accepted as `VALID` by `mcheck.py`!** (So `mini4x5` is guaranteed **not** a Black win; its exact value is either `WIN w` or `DRAW` — currently **unproved** as a full game value within the 5-minute single-command limit.)

| Root / Subposition | Claim | Solver Status | Entries (raw -> min) | File Bytes | Max Rank | Nodes | Solver (s) | Checker (s) | `mcheck.py` Verdict |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`) | `ATLEAST_DRAW w` | **PROVED** | **6,211 -> 6,107** | 203,789 | 0 | 1,923,645 | 5.9194 | 0.7726 | **VALID** |
| `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`) | `WIN w` | LIMIT | — | — | — | 4,839,424 | 15.0061 | — | unproved |
| `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`) | `ATLEAST_DRAW b` | LIMIT | — | — | — | 35,043,207 | 120.3296 | — | unproved |
| `1. d3 cxd3` (`rqkr/pp1p/3p/PPP1/RQKR w - -`) | `WIN w` | **PROVED** | **795 -> 733** | 24,599 | 40 | 58,386 | 0.1809 | 0.1210 | **VALID** |
| `1. d3 b3` (`rqkr/p1pp/1p1P/PPP1/RQKR w - -`) | `WIN w` | **PROVED** | **17,556 -> 15,524** | 508,411 | 41 | 3,570,228 | 11.2283 | 2.3856 | **VALID** |
| `1. d3 c3 2. Rd2 b3` (`rqkr/p2p/1ppP/PPPR/RQK1 w - -`) | `WIN w` | **PROVED** | **18,384 -> 15,457** | 478,966 | 57 | 5,638,426 | 17.6500 | 1.8686 | **VALID** |
| `1. c3` (`rqkr/pppp/2P1/PP1P/RQKR b - -`) | `WIN w` | DISPROVED | — | — | — | 254,857 | 0.5698 | — | N/A (disproved via `1... d3`) |
| `1. b3` (`rqkr/pppp/1P2/P1PP/RQKR b - -`) | `WIN w` | DISPROVED | — | — | — | 3,450,790 | 9.0188 | — | N/A (disproved via `1... d3`) |

Key observations on `mini4x5`:
- Minimisation effectiveness on real proofs:
  - `mini4x5 ATLEAST_DRAW w`: `6,211 -> 6,107` entries (`-1.7%`).
  - `1. d3 cxd3 WIN w`: `795 -> 733` entries (`-7.8%`).
  - `1. d3 b3 WIN w`: `17,556 -> 15,524` entries (`-11.6%`).
  - `1. d3 c3 2. Rd2 b3 WIN w`: `18,384 -> 15,457` entries (`-15.9%`).
- Opening structure discovered:
  - `1. c2c3` and `1. b2b3` fail to win for White (`WIN w` disproved via `1... d4d3`).
  - `1. d2d3` is White's critical try (and the move used by our verified `ATLEAST_DRAW w` certificate). Of Black's 4 replies to `1. d2d3`, two (`1... c4d3` and `1... b4b3`) are already proved `WIN w` and accepted by `mcheck.py` (with `max_rank` 40–41).
  - The remaining two replies (`1... a4a3` via `2. b2b3 c4c3 3. d1d2` and `1... c4c3` via `2. d1d2 a4a3 3. b2b3`) transpose to the same blocked-pawn bottleneck position `rqkr/1p1p/pPpP/P1PR/RQK1 b - -` (plus `1. d3 c3 2. Rd2 cxd2 3. Kxd2`, where 2 of 4 replies are proved and `3... Qc4` is at `pn=2`).
  - **Hypothesis (unproved):** `mini4x5` appears close to a `WIN w` via `1. d2d3`, with `1. d3 a3 2. b3 c3 3. Rd2 Ra4` / `3... cxd2` being the decisive bottleneck. Note that `mini4x5`'s `ATLEAST_DRAW w` certificate (6,107 entries) is more than 4 orders of magnitude smaller than the `>1.62e8` reachable positions counted by `06-complexity`.

Reproducing commands:
```sh
./msolve mini4x5 --claim "ATLEAST_DRAW w" --out certs/mini4x5_draw_w.cert --max-seconds 30 --tt-mb 512
python3 ../03-checker/mcheck.py verify certs/mini4x5_draw_w.cert
./msolve "rqkr/pp1p/3p/PPP1/RQKR w - -" --claim "WIN w" --out certs/d3_cxd3.cert --max-seconds 15 --tt-mb 512
./msolve "rqkr/p1pp/1p1P/PPP1/RQKR w - -" --claim "WIN w" --out certs/d3_b3.cert --max-seconds 30 --tt-mb 1024
./msolve "rqkr/p2p/1ppP/PPPR/RQK1 w - -" --claim "WIN w" --out certs/d3_c3_Rd2_b3.cert --max-seconds 20 --tt-mb 512
```

### Step 4: `mini5x5` (`rnbqk/ppppp/5/PPPPP/RNBQK w - -`)

As expected (`06-complexity` estimates `2.56e23` static-legal positions and `>1.62e8` reachable by depth 10), `mini5x5` hits limits on all four claims within 15 s / 512 MB TT. Measured progress (~210k–250k nodes/s):

| Claim | Status | Nodes | Seconds | Root `(pn, dn)` at Cutoff | Best Root Move Snapshot |
|---|---|---:|---:|---|---|
| `WIN w` | LIMIT | 3,710,976 | 15.0038 | `pn=3,393, dn=9,404` | `b1c3` (`pn=3393, dn=612`), `d2d3` (`pn=4202, dn=3112`) |
| `WIN b` | LIMIT | 3,581,952 | 15.0042 | `pn=12,268, dn=2,616` | `e2e3` (`pn=1315, dn=2616`), `d2d3` (`pn=4056, dn=2998`) |
| `ATLEAST_DRAW w` | LIMIT | 3,762,188 | 15.0702 | `pn=11,196, dn=2,543` | `d2d3` (`pn=3185, dn=2543`) |
| `ATLEAST_DRAW b` | LIMIT | 3,122,925 | 15.0651 | `pn=2,715, dn=7,314` | `b2b3` (`pn=2715, dn=995`), `d2d3` (`pn=3343, dn=2362`) |

Reproducing command:
```sh
./msolve mini5x5 --claim "WIN w" --max-seconds 15 --tt-mb 512 --verbose
```

## 5. Known Gaps, Open Questions, Spec Issues, and Tools Wanted

### Known gaps
1. **PN/DN explosion in dense DAGs (`mini4x5` bottleneck):** on deep `mini4x5` subtrees (`>15M` nodes), `dn` sums across transposing siblings saturate `MAX_FINITE = 1e9`, reducing `df-pn` discrimination at AND nodes (e.g., `rqkr/1p1p/pPpP/P1PR/RQK1 b - -` had both `c3d2` and `a5a4` saturate `dn=1e9`). Upgrading TT `pn/dn` to `uint64_t` or applying SNDA (sum-vs-max DAG damping) and integrating `04-tablebase` endgame probes would substantially accelerate solving `mini4x5` completely.
2. **Exact value of `mini4x5` remains open:** `ATLEAST_DRAW w` is certified (`VALID`), while `WIN w` vs `ATLEAST_DRAW b` hit the single-command limit (only the shared `1. d3 a3 2. b3 c3 3. Rd2` / `1. d3 c3 2. Rd2 a3 3. b3` transposition and `1. d3 c3 2. Rd2 cxd2 3. Kxd2` remain open).
3. **Minimiser exact mode threshold:** `Certificate::minimize` uses exact BFS reachability per candidate move up to 3,000 entries and switches to a fast local heuristic above 3,000 entries (giving 1.7%–15.9% reductions on 6k–18k entry proofs); stronger global DAG minimisation (e.g., dominator-tree or minimum hitting-set move selection) could shrink large certificates further.

### Open questions
- Is `mini4x5` (`rqkr/pppp/4/PPPP/RQKR w - -`) a forced `WIN w` via `1. d2d3` (with `max_rank` around 45–60), or does Black hold a draw in `rqkr/1p1p/pPpP/P1PR/RQK1 b - -`?
- How much does probing a `04-tablebase` 4–6 piece endgame tablebase reduce search nodes and certificate size on `mini4x5` (where current `WIN w` subproofs spend 20–40 plies converting won endgames)?

### Spec issues
- None found. `SPEC v1.1` (including the prover-stalemate exemption for `ATLEAST_DRAW`, canonical 4-field position strings, and strict rank formatting) was unambiguous and matched `../02-engine` and `../03-checker/mcheck.py` on all tested positions.

### Tools wanted
- None required for building or running `05-solver`. (For future scaling on `mini4x5` / `mini5x5`, linking against `04-tablebase` once available, or a MaxSAT/ILP solver such as `z3`/`ortools` for optimal post-hoc certificate minimisation, could be useful.)
