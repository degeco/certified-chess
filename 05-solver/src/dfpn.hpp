#pragma once

#include "certificate.hpp"
#include "common.hpp"
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace msolve {

class DfpnSolver {
public:
    static constexpr uint32_t MAX_FINITE = 1000000000U;
    static constexpr uint32_t INF        = 2000000000U;

    explicit DfpnSolver(size_t tt_mb = 256);

    // Solve WIN <prover> from `root`.
    // If PROVED and `cert_out != nullptr`, extracts (and optionally minimizes) a verified certificate.
    SolveStatus solve_win(const Position& root,
                          Color prover,
                          const SolveLimits& limits,
                          Certificate* cert_out,
                          SolveStats* stats_out = nullptr);

    // Solve ATLEAST_DRAW <defender> by running df-pn on WIN <~defender>:
    //   - If WIN <~defender> is PROVED -> returns DISPROVED.
    //   - If WIN <~defender> is DISPROVED -> extracts & minimizes an ATLEAST_DRAW <defender> certificate.
    SolveStatus solve_draw_via_disproof(const Position& root,
                                        Color defender,
                                        const SolveLimits& limits,
                                        Certificate* cert_out,
                                        SolveStats* stats_out = nullptr);

    // Clear TT and proof/disproof move caches (e.g. when changing prover color).
    void clear();

    uint64_t total_nodes() const { return nodes_; }

private:
    struct TTEntry {
        uint64_t key = 0;       // 0 = empty slot
        uint32_t pn = 0;
        uint32_t dn = 0;
        uint16_t best_move = 0; // packed move (bit 15 = valid)
        uint16_t rank = 0;
        uint32_t work = 0;
    };

    struct TTBucket {
        TTEntry slots[4];
    };

    struct MidResult {
        uint32_t pn = 1;
        uint32_t dn = 1;
        uint16_t best_move = 0;
        uint16_t rank = 0;
        int min_cycle_depth = 1000000;
    };

    struct ChildInfo {
        Move move;
        Position pos;
        uint32_t pn = 1;
        uint32_t dn = 1;
        uint16_t rank = 0;
        int cyc_depth = 1000000;
        int order_score = 0;
    };

    static inline uint64_t norm_key(uint64_t h) { return h ? h : 1ULL; }
    // Saturating addition for proof/disproof numbers: finite sums never become INF!
    static inline uint32_t sat_add(uint32_t a, uint32_t b) {
        if (a >= INF || b >= INF) return INF;
        uint64_t s = static_cast<uint64_t>(a) + static_cast<uint64_t>(b);
        return (s > MAX_FINITE) ? MAX_FINITE : static_cast<uint32_t>(s);
    }
    // Threshold addition: preserves strict > when th < INF and never overflows uint32_t.
    static inline uint32_t thresh_add(uint32_t a, uint32_t b) {
        if (a >= INF || b >= INF) return INF;
        uint64_t s = static_cast<uint64_t>(a) + static_cast<uint64_t>(b);
        return (s >= INF) ? (INF - 1) : static_cast<uint32_t>(s);
    }
    static inline uint32_t sat_sub(uint32_t a, uint32_t b) {
        if (a >= INF) return INF;
        return (a > b) ? (a - b) : 0;
    }

    const TTEntry* tt_lookup(uint64_t hash) const;
    void tt_store(uint64_t hash, uint32_t pn, uint32_t dn,
                  uint16_t best_move, uint16_t rank, uint32_t work);

    bool check_limits();
    int find_on_path(const Position& pos) const;

    MidResult mid(const Position& pos, uint32_t thpn, uint32_t thdn, int depth);

    bool extract_certificate(const Position& root, Certificate& cert);
    bool extract_or(const Position& pos,
                    Certificate& cert,
                    std::unordered_map<std::string, uint32_t>& done_rank,
                    std::unordered_map<std::string, bool>& visiting,
                    uint32_t& out_rank,
                    int depth);
    bool extract_draw_certificate(const Position& root, Color defender, Certificate& cert);

    std::vector<TTBucket> tt_;
    size_t tt_mask_ = 0;

    // Secondary bounded maps preserving winning / disproof moves even under TT pressure.
    std::unordered_map<uint64_t, uint16_t> proof_moves_;
    std::unordered_map<uint64_t, uint16_t> disproof_moves_;
    size_t max_proof_moves_ = 2000000;

    // Optional set of already-committed safe defender positions (exact FENs indexed by hash)
    // used during draw certificate extraction fallback.
    const std::unordered_map<uint64_t, std::vector<Position>>* safe_cycle_targets_ = nullptr;

    Color prover_ = WHITE;
    SolveLimits limits_;
    Timer timer_;
    uint64_t nodes_ = 0;
    bool aborted_ = false;

    // Active recursion path for exact cycle detection.
    std::vector<Position> path_pos_;
    std::vector<uint64_t> path_hash_;
    uint8_t path_bloom_[2048]{};

    // Heap-backed stack arena for child lists (avoids 60KB/frame stack overflow).
    std::vector<ChildInfo> child_arena_;
};

} // namespace msolve
