#pragma once

#include "certificate.hpp"
#include "common.hpp"
#include "dfpn.hpp"
#include "tb_probe.hpp"

namespace msolve {

// Solver for ATLEAST_DRAW <prover> claims.
// Combines:
//   1. Tablebase shortcut when root is in a loaded tablebase.
//   2. Quick bounded WIN <prover> / WIN <~prover> df-pn probes.
//   3. Closed-set invariant search for small/fortress draws.
//   4. Full-budget df-pn disproof witness extraction (with tablebase probing & splicing).
class DrawSolver {
public:
    explicit DrawSolver(const TablebaseProbe* tb = nullptr) : tb_probe_(tb) {}

    void set_tablebase(const TablebaseProbe* tb) { tb_probe_ = tb; }

    SolveStatus solve_atleast_draw(const Position& root,
                                   Color prover,
                                   const SolveLimits& limits,
                                   Certificate* cert_out,
                                   SolveStats* stats_out = nullptr);

private:
    const TablebaseProbe* tb_probe_ = nullptr;
};

} // namespace msolve
