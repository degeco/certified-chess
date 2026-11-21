#pragma once

#include "common.hpp"
#include "tablebase.hpp"

#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace msolve {

// Read-only in-memory loader and prober for 04-tablebase `.tb` files.
// Never writes to disk.
class TablebaseProbe {
public:
    // Load all existing `.tb` files in `tb_dir` for board (w, h) up to `max_pieces`.
    // Returns true if at least one table was loaded.
    bool load_board(const std::string& tb_dir,
                    int w,
                    int h,
                    int max_pieces = 4,
                    std::string* info = nullptr);

    bool is_loaded() const { return !tables_.empty(); }
    int width() const { return w_; }
    int height() const { return h_; }
    int max_pieces() const { return max_pieces_; }
    size_t table_count() const { return tables_.size(); }
    uint64_t total_bytes() const { return total_bytes_; }

    // Fast O(1) lookup for a position. Returns true iff position is in a loaded table and legal.
    bool probe(const Position& pos,
               tb::WDL& out_wdl,
               uint16_t& out_dtm,
               uint32_t* out_tb_size = nullptr) const;

    // Pick an optimal DTM-decreasing winning move from a WDL_WIN position.
    // Returns false if pos is not WDL_WIN or any successor table is missing.
    bool pick_win_move(const Position& pos, uint16_t p_dtm, Move& out_move) const;

    // Pick a draw-preserving move from a WDL_DRAW position.
    // Prefers immediate opponent stalemate/mate, closure into `preferred_seen` (if non-null),
    // smaller successor tablebase size, fewer opponent replies, and lex move order.
    bool pick_draw_move(const Position& pos,
                        const std::unordered_set<std::string>* preferred_seen,
                        Move& out_move) const;

private:
    static uint64_t pack_sig(const tb::MaterialSig& sig);
    static uint64_t pack_sig_from_pos(const Position& pos);

    int w_ = 0;
    int h_ = 0;
    int max_pieces_ = 0;
    uint64_t total_bytes_ = 0;
    std::unordered_map<uint64_t, std::unique_ptr<tb::Tablebase>> tables_;
};

} // namespace msolve
