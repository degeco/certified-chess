# 06-complexity Report: State-Space Counts and Estimates

Note per `design/SPEC.md`: all counts and estimates use `02-engine` rules (idealized chess without 50-move, repetition, or insufficient-material rules; full FIDE movement on `8x8` and mini rules off `8x8`). Differential testing between `02-engine` and `03-checker` is pending per `TASK.md`.

## 1. What Was Built

- [`src/common.hpp`](src/common.hpp): Board specifications (`mini3x3`, `mini3x3_p`, `mini4x4`, `mini4x5`, `mini5x5`, `losalamos6x6`, `std6x6`, `std8`, plus arbitrary FENs) and canonical FEN helpers.
- [`src/reach.hpp`](src/reach.hpp) / [`src/reach.cpp`](src/reach.cpp) -> `bin/reach`: Exact breadth-first reachability enumerator with exact packed keys (`Key16` for `<=31` squares, `Key24` for `<=47` squares, `Key36` for `8x8` including castling/ep), chunked key storage (no reallocation spikes), open-addressing `uint32_t` index hash table, per-depth counts, and clean termination under `--max-mem-mb` (default `3500`, strictly under 4 GB) and `--max-sec` (default `240`).
- [`src/estimate.hpp`](src/estimate.hpp) / [`src/estimate.cpp`](src/estimate.cpp) -> `bin/estimate`: Exact combinatorial superset counter + unbiased i.i.d. sampler (`StaticSpaceSampler`) with Welford variance and 95% confidence intervals, plus a brute-force exact enumerator for small boards (`<=12` squares) to validate the sampler.
- [`src/validate.cpp`](src/validate.cpp) -> `bin/validate`: Validation suite covering key roundtrips, exact BFS depths, brute-force exact vs. estimator validation on `3x3` boards, clean memory-cap stopping, and `8x8` castling/en-passant completion weights.
- [`scripts/run_all.py`](scripts/run_all.py) and [`Makefile`](Makefile): Single-command build, test, and reproducible experiment targets.

## 2. Build and Test

Build all binaries and run the validation suite (assuming `../02-engine/build/libmchess.a` is built):

```sh
make -j4 all && make test
```

Actual `make test` (`./bin/validate`) output:

```text
[PASS] Key16 roundtrip mini4x4
[PASS] Key24 roundtrip 6x6
[PASS] Key36 roundtrip 8x8 with castling and ep
[PASS] reach std8 depth 0..2 == 1, 20, 400
[PASS] reach mini4x4 depth 1 matches legal_moves count
  mini3x3: exact_U=33216 formula_U=33216 exact_L=12616 est=12636.7 ci95=[12586.7, 12686.7]
[PASS] mini3x3 exact |U| matches brute-force enumeration
[PASS] mini3x3 exact |L| inside 95% CI
[PASS] mini3x3_p FEN valid
  mini3x3_p: exact_U=1336664 formula_U=1336664 exact_L=559208 est=558423.5 ci95=[556596.2, 560250.7]
[PASS] mini3x3_p (with pawns & promos) exact |U| matches brute force
[PASS] mini3x3_p exact |L| inside 95% CI
  mini5x5 32MB cap: stop=memory_limit max_complete_depth=6 total=1426063 peak_mb=32.00
[PASS] reach stops cleanly under memory_limit
[PASS] 8x8 F(X) counts 16 castling subsets
[PASS] 8x8 F(X) counts K castling x legal ep = 4
[PASS] 8x8 F(X) rejects pinned pseudo-ep
[PASS] 8x8 F(X) returns 0 when non-stm king in check
ALL TESTS PASSED
```

## 3. Sampling Scheme and Unbiasedness (`estimate`)

For a board $W \times H$ ($S = W \cdot H$, pawn-eligible squares $S_p = W(H-2)$) and initial material budgets $(P_0, N_0, B_0, R_0, Q_0)$ per side, define the superset $\mathcal{U}$ of `(board, stm)` states satisfying:
1. One White King and one Black King on non-adjacent squares, partitioned into exact counts $K_a$ by $a \in \{0,1,2\}$ (number of kings on ranks $1 \dots H-2$).
2. Valid material signatures $m_c = (p_c, n_c, b_c, r_c, q_c)$ with $p_c \le P_{0,c}$ and promotion budget $\sum_{t \in \{N,B,R,Q\}} \max(0, c_t - c_{0,t}) \le P_{0,c} - p_c$, pawns placed only on ranks $1 \dots H-2$, and $2 + p_W + u_W + p_B + u_B \le S$ (where $u_c = n_c+b_c+r_c+q_c$).
3. Side to move $\text{stm} \in \{w, b\}$.

Grouping side material by $(p_c, u_c)$ lets us compute $|\mathcal{U}|$ exactly in $O(P_0^2 U_{\max}^2)$ via multinomial weights:
$$|\mathcal{U}| = \sum_{(p_W, u_W, p_B, u_B, a)} 2\, K_a \binom{S_p - a}{p_W,\, p_B,\, S_p - a - p_W - p_B} \frac{(S-2-p_W-p_B)!}{(S-2-p_W-p_B-u_W-u_B)!} W_W(p_W,u_W) W_B(p_B,u_B),$$
where $W_c(p,u) = \sum_{m_c \in \text{bucket}(p,u)} \frac{1}{n_c! b_c! r_c! q_c!}$. Sampling a bucket proportional to its exact weight, then $(m_W, m_B)$, then $(k_W, k_B)$ uniformly from $K_a$, then pawn and piece squares uniformly without replacement, produces **exact i.i.d. uniform draws** $X_i \sim \text{Uniform}(\mathcal{U})$ (no burn-in or proposal approximation).

For each draw $X_i$, let $F(X_i)$ be the exact number of valid `(castling, ep)` completions accepted by `mchess::Position::parse` (which checks `!in_check(~stm)` plus canonical `castling`/`ep` rules):
- Off `8x8`, $F(X_i) = \mathbb{I}[\neg\text{in\_check}(\sim\text{stm})] \in \{0,1\}$.
- On `8x8`, $F(X_i) = \mathbb{I}[\neg\text{in\_check}(\sim\text{stm})] \cdot 2^{\text{eligible\_castling\_bits}} \cdot (1 + \text{\#legal ep squares})$.

Because every static-legal position projects uniquely onto one `(board, stm)` in $\mathcal{U}$ with $F(X)$ completions, $\hat{L} = |\mathcal{U}| \cdot \frac{1}{N}\sum_{i=1}^N F(X_i)$ is strictly unbiased for $|\mathcal{L}_{\text{static}}|$, with 95% CI $\hat{L} \pm 1.96\, |\mathcal{U}|\, s / \sqrt{N}$.

## 4. Measured Results

### Summary Table

Even `mini4x4` exceeds 3.5 GB before BFS exhaustion (`>162M` reachable positions), so `reach` supplies exact counts up to the completed depth shown and `estimate` supplies static-legal counts across all boards:

| Board | Start FEN / Material | `reach` complete depth (exact cumulative `<= d`) | `reach` total discovered (status) | Static-legal estimate (`95% CI`) | Samples |
|---|---|---|---|---|---|
| `mini4x4` | `rqkr/pppp/PPPP/RQKR w - -` | `d <= 12`: `148,792,856` | `162,267,136` (d=13 partial, `memory_limit` 3500 MB, 168.0s) | `1.3277e+15` (`[1.3256e+15, 1.3298e+15]`, ±0.16%) | 5,000,000 |
| `mini4x5` | `rqkr/pppp/4/PPPP/RQKR w - -` | `d <= 11`: `85,774,732` | `162,267,136` (d=12 partial, `memory_limit` 3500 MB, 164.9s) | `9.4323e+17` (`[9.4170e+17, 9.4477e+17]`, ±0.16%) | 5,000,000 |
| `mini5x5` | `rnbqk/ppppp/5/PPPPP/RNBQK w - -` | `d <= 9`: `76,061,365` | `162,267,136` (d=10 partial, `memory_limit` 3500 MB, 142.2s) | `2.5596e+23` (`[2.5553e+23, 2.5638e+23]`, ±0.17%) | 5,000,000 |
| `losalamos6x6` | `rnqknr/pppppp/6/6/PPPPPP/RNQKNR w - -` | `d <= 8`: `19,398,603` | `91,268,055` (d=9 partial, `memory_limit` 2606 MB, 87.8s) | `3.1753e+31` (`[3.1700e+31, 3.1807e+31]`, ±0.17%) | 5,000,000 |
| `std6x6` | `rnbqkr/pppppp/6/6/PPPPPP/RNBQKR w - -` | — | — | `4.5853e+31` (`[4.5776e+31, 4.5930e+31]`, ±0.17%) | 5,000,000 |
| `std8` | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -` | `d <= 6`: `10,281,862` | `82,513,525` (d=7 partial, `time_limit` 130.1s, 3347 MB) | `9.7445e+48` (`[9.6943e+48, 9.7948e+48]`, ±0.52%) | 500,000 |

Reproducing commands:

```sh
make estimates
make reach-mini4x4
make reach-mini4x5
make reach-mini5x5
make reach-6x6
make reach-std8
```

### Per-Depth `reach` Counts

| Depth | `mini4x4` | `mini4x5` | `mini5x5` | `losalamos6x6` | `std8` |
|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | 1 | 1 | 1 |
| 1 | 6 | 4 | 7 | 10 | 20 |
| 2 | 21 | 18 | 53 | 100 | 400 |
| 3 | 152 | 104 | 428 | 772 | 5,362 |
| 4 | 842 | 579 | 3,231 | 6,072 | 72,013 |
| 5 | 4,506 | 3,667 | 25,175 | 44,276 | 821,016 |
| 6 | 23,095 | 21,728 | 185,994 | 325,526 | 9,383,050 |
| 7 | 118,043 | 125,977 | 1,387,131 | 2,346,262 | 72,231,663 (partial) |
| 8 | 532,910 | 668,211 | 9,671,760 | 16,675,584 | — |
| 9 | 2,371,056 | 3,345,134 | 64,787,585 | 71,869,452 (partial) | — |
| 10 | 9,109,148 | 15,431,328 | 86,205,771 (partial) | — | — |
| 11 | 33,272,936 | 66,177,981 | — | — | — |
| 12 | 103,360,140 | 76,492,404 (partial) | — | — | — |
| 13 | 13,474,280 (partial) | — | — | — | — |

Terminal counts observed over fully expanded depths:
- `mini4x4` (`d <= 11`): `2,253,796` checkmates, `24,402` stalemates.
- `mini4x5` (`d <= 10`): `244,881` checkmates, `367` stalemates.
- `mini5x5` (`d <= 8`): `32,151` checkmates, `0` stalemates.
- `losalamos6x6` (`d <= 7`): `2,532` checkmates, `0` stalemates.
- `std8` (`d <= 5`): `109` checkmates, `0` stalemates.

## 5. Gap Between Static Legality and True Reachability

`estimate` measures $|\mathcal{L}_{\text{static}}|$, which is strictly larger than the true reachable set $|\mathcal{R}|$ from the start position. Key unmodeled reachability obstructions:
1. **Capture-budget vs. pawn promotion / file-passing**: Every start position has opposing pawns on every file. A pawn cannot promote without either capturing onto an open path or an enemy pawn leaving/being captured on that file. Under static rules alone, configurations with 0 or few captures and many promotions dominate: on `8x8`, a Python check of the combinatorial weights shows $U_{\text{approx}} \approx 4.91 \times 10^{49}$ overall versus $2.23 \times 10^{41}$ with zero promotions, and ~75% of $U$ has all 32 pieces on the board (`lt32_pieces = 1.24e+49`)—meaning 0 captures occurred, making any promotion unreachable from `std8`.
2. **Retrograde pawn structure & blocked piece imprisonment**: Pawns on `mini4x4` start face-to-face (`pppp/PPPP`), so moving any pawn requires diagonal captures; static rules allow arbitrary pawn placements on ranks 2–3 regardless of capture count. Likewise, locked pawns can make bishop/rook placements unreachable, and static rules do not check whether a bishop's square color matches starting squares when no promotion occurred.
3. **Impossible checks and `ep` pre-states**: Static rules check `!in_check(~stm)`, not whether `stm` is in an unreachable check (e.g., triple check, impossible double check, or `ep` where the prior double push could not have been legal because `stm`'s king was already in check).
4. **Even on `mini4x4`**, `reach` reaches `1.49e+08` positions by depth 12 (branching ~3.1x/ply at depth 12), while $|\mathcal{L}_{\text{static}}| \approx 1.33 \times 10^{15}$; much of the static space is unreachable due to blocked initial pawns and capture-promotion constraints.

## 6. Known Gaps and Spec Issues

- **Missing `../01-survey/sources.md`**: `TASK.md` requests comparing the `8x8` estimate with the published estimate recorded in `../01-survey/sources.md`, but `../01-survey/sources.md` does not exist yet in the repository, so that comparison is left open until `01-survey` produces it. Note that without capture-vs-promotion / pawn-file-balance constraints, our static-rule `std8` estimate (`9.74e+48`) counts heavy multi-promotion 30–32 piece boards that stricter retrograde-aware chess position bounds exclude.
- **Spec issue (`6x6` start position)**: `design/SPEC.md` defines named start positions for `mini4x4`, `mini4x5`, `mini5x5`, and `std8`, but does not define a `6x6` start position. We reported both `losalamos6x6` (`rnqknr/pppppp/6/6/PPPPPP/RNQKNR w - -`) and `std6x6` (`rnbqkr/pppppp/6/6/PPPPPP/RNBQKR w - -`) for `estimate`, and ran `reach` on `losalamos6x6`.
- **Single-command runtime limit**: Running all five deep `reach` searches sequentially in one process exceeds the 5-minute single-command cap (~693s combined), so `Makefile` exposes one target per `reach` board (`reach-mini4x4`, etc., each `<180s`) alongside `make estimates` (`~49s` total).
