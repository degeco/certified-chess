#pragma once

#include "certificate.hpp"
#include "common.hpp"
#include "tb_probe.hpp"
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace msolve {

class DfpnSolver {
public:
    static constexpr uint64_t MAX_FINITE = (1ULL << 60);
    static constexpr uint64_t INF        = (1ULL << 62);

    explicit DfpnSolver(size_t tt_mb = 256, const TablebaseProbe* tb = nullptr);

    void set_tablebase(const TablebaseProbe* tb) { tb_probe_ = tb; }

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
    uint64_t tb_hits() const { return tb_hits_; }

private:
    struct TTEntry {
        uint64_t key = 0;       // 0 = empty slot
        uint64_t pn = 0;
        uint64_t dn = 0;
        uint32_t pn_sig = 0;    // 32-bit signature of critical PN node (SNDA)
        uint32_t dn_sig = 0;    // 32-bit signature of critical DN node (SNDA)
        uint16_t best_move = 0; // packed move (bit 15 = valid)
        uint16_t rank = 0;
        uint32_t work = 0;
    };

    struct TTBucket {
        TTEntry slots[4];
    };

    struct MidResult {
        uint64_t pn = 1;
        uint64_t dn = 1;
        uint32_t pn_sig = 0;
        uint32_t dn_sig = 0;
        uint16_t best_move = 0;
        uint16_t rank = 0;
        int min_cycle_depth = 1000000;
    };

    struct ChildInfo {
        Move move;
        Position pos;
        uint64_t pn = 1;
        uint64_t dn = 1;
        uint32_t pn_sig = 0;
        uint32_t dn_sig = 0;
        uint16_t rank = 0;
        int cyc_depth = 1000000;
        int order_score = 0;
    };

    static inline uint64_t norm_key(uint64_t h) { return h ? h : 1ULL; }
    static inline uint32_t hash_sig(uint64_t h) {
        uint32_t s = static_cast<uint32_t>(h ^ (h >> 32));
        return s ? s : 1U;
    }

    // Saturating addition for proof/disproof numbers: finite sums never become INF.
    static inline uint64_t sat_add(uint64_t a, uint64_t b) {
        if (a >= INF || b >= INF) return INF;
        if (a > MAX_FINITE - b) return MAX_FINITE;
        return a + b;
    }

    // Threshold addition: preserves strict > when th < INF and never overflows uint64_t.
    static inline uint64_t thresh_add(uint64_t a, uint64_t b) {
        if (a >= INF || b >= INF) return INF;
        if (a >= INF - 1 - b) return INF - 1;
        return a + b;
    }

    static inline uint64_t sat_sub(uint64_t a, uint64_t b) {
        if (a >= INF) return INF;
        return (a > b) ? (a - b) : 0;
    }

    // Exact floor integer square root for uint64_t.
    static uint64_t isqrt64(uint64_t n);

    // DAG-aware aggregation and exact threshold inversion.
    uint64_t dag_aggregate(uint64_t sum, uint64_t max_v, uint32_t k_pos) const;
    uint64_t dag_child_threshold(uint64_t th,
                                 uint64_t best_v,
                                 uint64_t max_other,
                                 uint64_t sum_other,
                                 uint32_t k_pos_other) const;

    const TTEntry* tt_lookup(uint64_t hash) const;
    void tt_store(uint64_t hash, uint64_t pn, uint64_t dn,
                  uint32_t pn_sig, uint32_t dn_sig,
                  uint16_t best_move, uint16_t rank, uint32_t work);

    bool check_limits();
    int find_on_path(const Position& pos) const;

    // Probe tablebase from `prover_`'s WIN perspective. Returns true on hit.
    bool probe_tb_for_win(const Position& pos, uint64_t& out_pn, uint64_t& out_dn, uint16_t& out_rank);

    MidResult mid(const Position& pos, uint64_t thpn, uint64_t thdn, int depth);

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

    const TablebaseProbe* tb_probe_ = nullptr;

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
    uint64_t tb_hits_ = 0;
    bool aborted_ = false;

    // Active recursion path for exact cycle detection.
    std::vector<Position> path_pos_;
    std::vector<uint64_t> path_hash_;
    uint8_t path_bloom_[2048]{};

    // Heap-backed stack arena for child lists (avoids 60KB/frame stack overflow).
    std::vector<ChildInfo> child_arena_;
};

} // namespace msolve
