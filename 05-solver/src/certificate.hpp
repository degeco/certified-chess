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

    // Internal strict SPEC v1.2 verification (returns true iff valid).
    bool verify(std::string* err = nullptr) const;

    // Load a SPEC v1.2 `#cert v1` file with strict format validation.
    static bool load_from_file(const std::string& path, Certificate& out, std::string* err = nullptr);

    // Write SPEC v1.2 certificate file.
    bool write_to_file(const std::string& path, std::string* err = nullptr) const;

    // Recompute exact minimal DAG ranks for a WIN certificate. Returns false if a cycle exists.
    bool recompute_win_ranks(std::string* err = nullptr);

    // Merge multiple verified sub-certificates and optional connecting moves into one flat certificate.
    // For WIN claims, duplicate FENs across sub_certs keep the smaller-rank entry (preserving acyclicity).
    // For ATLEAST_DRAW claims, both ATLEAST_DRAW <prover> and WIN <prover> sub_certs are accepted.
    static bool merge(const Position& root,
                      const Claim& claim,
                      const std::vector<Certificate>& sub_certs,
                      const std::vector<std::pair<Position, Move>>& connecting_moves,
                      Certificate& out,
                      bool minimize = true,
                      size_t* raw_size = nullptr,
                      size_t* pruned_size = nullptr,
                      size_t* final_size = nullptr,
                      std::string* err = nullptr);

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
