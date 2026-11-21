#pragma once

#include "common.hpp"
#include <string>
#include <unordered_map>
#include <vector>

namespace msolve {

struct CertEntry {
    Position pos;
    std::string fen;
    Move move;
    uint32_t rank = 0;
};

struct Certificate {
    Claim claim;
    Position root;
    std::string root_fen;
    // Keyed by canonical FEN string for exactness and zero collision risk.
    std::unordered_map<std::string, CertEntry> entries;

    size_t size() const { return entries.size(); }

    uint32_t max_rank() const {
        uint32_t mr = 0;
        for (const auto& kv : entries) {
            if (kv.second.rank > mr) mr = kv.second.rank;
        }
        return mr;
    }

    // Internal strict SPEC v1.1 verification (returns true iff valid).
    bool verify(std::string* err = nullptr) const;

    // Write SPEC v1.1 certificate file.
    bool write_to_file(const std::string& path, std::string* err = nullptr) const;

    // Convert a valid WIN certificate to an ATLEAST_DRAW certificate (same prover, ranks = 0).
    void convert_win_to_draw();

    // Minimise certificate:
    //   1. Drop entries unreachable from root.
    //   2. Iteratively re-select prover moves that merge into existing entries / shrink reachable set.
    //   3. For WIN, recompute exact minimal topological ranks.
    // Populates raw_size, pruned_size, final_size if non-null.
    void minimize(size_t* raw_size = nullptr, size_t* pruned_size = nullptr, size_t* final_size = nullptr);
};

} // namespace msolve
