#pragma once

#include "signature.hpp"
#include "mchess.hpp"
#include <array>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace tb {

struct RawState {
    uint64_t bb[2][6]{}; // 02-engine bitboards (sq = (r << 3) | f)
    mchess::Color stm = mchess::WHITE;
    uint8_t castling = 0;
    int8_t ep_sq = mchess::NO_SQ;
};

struct ExtraState {
    uint32_t base_idx = 0;
    uint8_t castling = 0;
    int8_t ep_sq = mchess::NO_SQ;
};

class TableIndexer {
public:
    TableIndexer(int w, int h, const MaterialSig& sig);

    int width() const { return w_; }
    int height() const { return h_; }
    bool is_8x8() const { return w_ == 8 && h_ == 8; }
    const MaterialSig& signature() const { return sig_; }

    uint32_t size() const { return total_size_; }
    uint32_t base_size() const { return base_size_; }

    // Decode index into raw bitboards + metadata (always succeeds for idx < size()).
    void decode_raw(uint32_t idx, RawState& out) const;

    // Decode index into a validated mchess::Position. Returns false if illegal
    // (e.g., opponent king in check).
    bool decode_position(uint32_t idx, mchess::Position& out) const;

    // Encode raw state or Position. Returns UINT32_MAX if not found / invalid.
    uint32_t encode_raw(const RawState& st) const;
    uint32_t encode_position(const mchess::Position& pos) const;

    // Square coordinate helpers between dense [0, w*h) and engine (r<<3)|f.
    int to_dense(int eng_sq) const {
        return mchess::sq_rank(eng_sq) * w_ + mchess::sq_file(eng_sq);
    }
    int to_engine(int dense_sq) const {
        return mchess::make_sq(dense_sq % w_, dense_sq / w_);
    }

    static std::string raw_to_fen(int w, int h, const RawState& st);
    static int raw_to_fen_buf(int w, int h, const RawState& st, char* buf);

private:
    struct Group {
        mchess::Color color;
        mchess::PieceType pt;
        uint8_t count;
        bool pawns_only;
    };

    uint32_t encode_base_dense(const uint64_t dense_bb[2][6], mchess::Color stm) const;
    void decode_base_dense(uint32_t base_idx, uint64_t dense_bb[2][6], mchess::Color& stm) const;

    static uint64_t make_extra_key(uint32_t base_idx, uint8_t castling, int8_t ep_sq) {
        return (uint64_t(base_idx) << 11) | (uint64_t(castling & 0xF) << 7) | uint64_t(ep_sq + 1);
    }

    int w_ = 0;
    int h_ = 0;
    int num_sq_ = 0;
    uint64_t all_dense_mask_ = 0;
    uint64_t pawn_dense_mask_ = 0;
    MaterialSig sig_;

    std::vector<Group> groups_;
    std::vector<uint32_t> group_radix_;
    uint32_t base_size_ = 0;
    uint32_t total_size_ = 0;

    std::vector<ExtraState> extra_states_;
    std::unordered_map<uint64_t, uint32_t> extra_map_;

    uint64_t binom_[65][65]{};
};

} // namespace tb
