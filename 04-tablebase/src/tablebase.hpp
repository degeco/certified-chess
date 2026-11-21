#pragma once

#include "indexer.hpp"
#include "signature.hpp"
#include "mchess.hpp"
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace tb {

enum WDL : uint8_t {
    WDL_UNKNOWN = 0,
    WDL_WIN     = 1,
    WDL_LOSS    = 2,
    WDL_DRAW    = 3,
    WDL_ILLEGAL = 4
};

struct TableStats {
    int width = 0;
    int height = 0;
    std::string signature;
    uint64_t index_size = 0;
    uint64_t legal_positions = 0;
    uint64_t wins = 0;
    uint64_t draws = 0;
    uint64_t losses = 0;
    uint64_t checkmates = 0;
    uint64_t stalemates = 0;
    uint16_t max_win_dtm = 0;
    uint16_t max_loss_dtm = 0;
    std::string max_win_fen;
    std::string max_loss_fen;
    double gen_seconds = 0.0;
    uint64_t table_bytes = 0;
};

struct Tablebase {
    int id = -1;
    int width = 0;
    int height = 0;
    MaterialSig sig;
    std::unique_ptr<TableIndexer> indexer;
    std::vector<uint8_t> wdl;
    std::vector<uint16_t> dtm;
    double gen_seconds = 0.0;

    TableStats compute_stats() const;
    bool save(const std::string& path) const;
    static std::unique_ptr<Tablebase> load(const std::string& path);
};

class TableStore {
public:
    explicit TableStore(std::string db_dir = "data") : db_dir_(std::move(db_dir)) {}

    // Ensure signature (and transitive or direct dependencies) for (w, h) are loaded or generated.
    const Tablebase& ensure(int w, int h, const MaterialSig& sig,
                            bool save_to_disk = true,
                            bool load_deps_if_cached = true);

    const Tablebase* find(int w, int h, const MaterialSig& sig) const;

    // Look up a position (automatically ensuring its tablebase if needed? No, lookup assumes built).
    bool lookup(const mchess::Position& pos, WDL& out_wdl, uint16_t& out_dtm, int* out_table_id = nullptr) const;

    // Separate verification pass using forward 02-engine moves.
    bool verify(int w, int h, const MaterialSig& sig, std::string* err = nullptr);

    // Export certificate(s) for root_pos.
    // For WIN/LOSS: populates certs = { win_cert }.
    // For DRAW: populates certs = { atleast_draw_w, atleast_draw_b }.
    bool export_certificates(const mchess::Position& root_pos,
                             std::vector<std::string>& out_certs,
                             std::vector<std::string>& out_claims,
                             std::vector<uint32_t>& out_entries,
                             std::vector<uint16_t>& out_max_ranks,
                             std::string* err = nullptr);

    std::string db_path(int w, int h, const MaterialSig& sig) const;

private:
    struct Key {
        int w;
        int h;
        MaterialSig sig;
        bool operator<(const Key& o) const {
            if (w != o.w) return w < o.w;
            if (h != o.h) return h < o.h;
            return sig < o.sig;
        }
    };

    std::string db_dir_;
    std::map<Key, std::unique_ptr<Tablebase>> tables_;
    std::vector<const Tablebase*> by_id_;
};

// Expose predecessor enumeration for unit testing (unmove == forward).
std::vector<uint32_t> collect_quiet_predecessors(const TableIndexer& indexer,
                                                 uint32_t p_idx,
                                                 const std::vector<uint8_t>& wdl);

} // namespace tb
