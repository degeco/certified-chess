#pragma once

#include "certificate.hpp"
#include "common.hpp"
#include "dfpn.hpp"

namespace msolve {

// Solver for ATLEAST_DRAW <prover> claims.
// Combines:
//   1. Quick bounded WIN <prover> / WIN <~prover> df-pn probes.
//   2. Closed-set invariant search: grows a candidate strategy graph from root,
//      scoring prover moves by closure into already-active positions, low opponent
//      branching, and alpha-beta tactical safety, with mini-dfpn refutation checks
//      and full backtracking when a branch is disproved.
class DrawSolver {
public:
    SolveStatus solve_atleast_draw(const Position& root,
                                   Color prover,
                                   const SolveLimits& limits,
                                   Certificate* cert_out,
                                   SolveStats* stats_out = nullptr);
};

} // namespace msolve
