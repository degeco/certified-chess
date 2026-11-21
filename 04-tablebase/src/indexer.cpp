#include "indexer.hpp"
#include <cstring>
#include <stdexcept>

namespace tb {

namespace {

inline int eng_to_dense_sq(int w, int eng_sq) {
    return mchess::sq_rank(eng_sq) * w + mchess::sq_file(eng_sq);
}

inline int dense_to_eng_sq(int w, int dsq) {
    return mchess::make_sq(dsq % w, dsq / w);
}

inline int select_nth_bit(uint64_t bb, int n) {
    uint32_t lo = static_cast<uint32_t>(bb);
    int c = __builtin_popcount(lo);
    int sq = 0;
    if (n >= c) {
        n -= c;
        bb >>= 32;
        sq = 32;
    }
    uint16_t lo16 = static_cast<uint16_t>(bb);
    int c16 = __builtin_popcount(lo16);
    if (n >= c16) {
        n -= c16;
        bb >>= 16;
        sq += 16;
    }
    while (n--) {
        bb &= bb - 1;
    }
    return sq + __builtin_ctzll(bb);
}

bool non_stm_in_check(int w, int h, const RawState& st) {
    const mchess::Color us = st.stm;
    const mchess::Color them = ~us;
    const uint64_t board_mask = mchess::make_board_mask(w, h);
    const int ksq = mchess::lsb(st.bb[them][mchess::KING]);
    const mchess::Tables& tbl = mchess::tables();
    if (tbl.pawn_att[them][ksq] & st.bb[us][mchess::PAWN]) return true;
    if (tbl.knight_att[ksq] & st.bb[us][mchess::KNIGHT]) return true;
    if (tbl.king_att[ksq] & st.bb[us][mchess::KING]) return true;
    uint64_t occ = 0;
    for (int c = 0; c < 2; ++c)
        for (int pt = 0; pt < 6; ++pt)
            occ |= st.bb[c][pt];
    if (mchess::bishop_attacks(ksq, occ, board_mask) &
        (st.bb[us][mchess::BISHOP] | st.bb[us][mchess::QUEEN])) return true;
    if (mchess::rook_attacks(ksq, occ, board_mask) &
        (st.bb[us][mchess::ROOK] | st.bb[us][mchess::QUEEN])) return true;
    return false;
}

} // namespace

TableIndexer::TableIndexer(int w, int h, const MaterialSig& sig)
    : w_(w), h_(h), num_sq_(w * h), sig_(sig) {
    if (w < 3 || w > 8 || h < 3 || h > 8) {
        throw std::invalid_argument("board dimensions out of range 3..8");
    }

    for (int n = 0; n <= 64; ++n) {
        binom_[n][0] = 1;
        for (int k = 1; k <= n; ++k) {
            binom_[n][k] = binom_[n - 1][k - 1] + binom_[n - 1][k];
        }
    }

    all_dense_mask_ = (num_sq_ == 64) ? ~0ULL : ((1ULL << num_sq_) - 1);
    int pawn_hi = w_ * (h_ - 1);
    uint64_t hi_mask = (pawn_hi == 64) ? ~0ULL : ((1ULL << pawn_hi) - 1);
    uint64_t lo_mask = (1ULL << w_) - 1;
    pawn_dense_mask_ = hi_mask & ~lo_mask;

    auto add_group = [&](mchess::Color c, mchess::PieceType pt, bool pawns_only) {
        uint8_t cnt = sig_.count[c][pt];
        if (cnt > 0) {
            groups_.push_back({c, pt, cnt, pawns_only});
        }
    };

    add_group(mchess::WHITE, mchess::PAWN, true);
    add_group(mchess::BLACK, mchess::PAWN, true);
    add_group(mchess::WHITE, mchess::KING, false);
    add_group(mchess::BLACK, mchess::KING, false);
    add_group(mchess::WHITE, mchess::QUEEN, false);
    add_group(mchess::WHITE, mchess::ROOK, false);
    add_group(mchess::WHITE, mchess::BISHOP, false);
    add_group(mchess::WHITE, mchess::KNIGHT, false);
    add_group(mchess::BLACK, mchess::QUEEN, false);
    add_group(mchess::BLACK, mchess::ROOK, false);
    add_group(mchess::BLACK, mchess::BISHOP, false);
    add_group(mchess::BLACK, mchess::KNIGHT, false);

    int total_pawns_placed = 0;
    int total_placed = 0;
    uint64_t prod = 2; // side to move

    int num_pawn_sq = w_ * (h_ - 2);
    group_radix_.resize(groups_.size());
    for (size_t i = 0; i < groups_.size(); ++i) {
        int avail_cnt = groups_[i].pawns_only
                            ? (num_pawn_sq - total_pawns_placed)
                            : (num_sq_ - total_placed);
        if (avail_cnt < groups_[i].count) {
            throw std::runtime_error("too many pieces for board");
        }
        uint64_t ways = binom_[avail_cnt][groups_[i].count];
        group_radix_[i] = static_cast<uint32_t>(ways);
        if (prod > UINT32_MAX / ways) {
            throw std::runtime_error("tablebase index space exceeds 32 bits");
        }
        prod *= ways;
        if (groups_[i].pawns_only) total_pawns_placed += groups_[i].count;
        total_placed += groups_[i].count;
    }

    base_size_ = static_cast<uint32_t>(prod);
    total_size_ = base_size_;

    // On 8x8, enumerate valid non-zero castling / ep states.
    // Castling is enumerated when base_size_ <= 5,000,000; en passant is always enumerated
    // when both sides have pawns (needed e.g. for 8x8 KPKP).
    if (is_8x8()) {
        bool may_castle = (sig_.count[mchess::WHITE][mchess::ROOK] > 0 ||
                           sig_.count[mchess::BLACK][mchess::ROOK] > 0) &&
                          (base_size_ <= 5000000U);
        bool may_ep = (sig_.count[mchess::WHITE][mchess::PAWN] > 0 &&
                       sig_.count[mchess::BLACK][mchess::PAWN] > 0);

        if (may_castle || may_ep) {
            auto has_piece = [](const RawState& st, int f, int r, mchess::Color c, mchess::PieceType pt) {
                int sq = mchess::make_sq(f, r);
                return (st.bb[c][pt] & mchess::sq_bb(sq)) != 0;
            };

            auto check_base_state = [&](uint32_t b, bool do_castle, bool do_ep) {
                RawState st;
                decode_raw(b, st);

                uint8_t max_cast = 0;
                if (do_castle) {
                    if (has_piece(st, 4, 0, mchess::WHITE, mchess::KING)) {
                        if (has_piece(st, 7, 0, mchess::WHITE, mchess::ROOK)) max_cast |= mchess::WK_CASTLE;
                        if (has_piece(st, 0, 0, mchess::WHITE, mchess::ROOK)) max_cast |= mchess::WQ_CASTLE;
                    }
                    if (has_piece(st, 4, 7, mchess::BLACK, mchess::KING)) {
                        if (has_piece(st, 7, 7, mchess::BLACK, mchess::ROOK)) max_cast |= mchess::BK_CASTLE;
                        if (has_piece(st, 0, 7, mchess::BLACK, mchess::ROOK)) max_cast |= mchess::BQ_CASTLE;
                    }
                }

                int8_t cand_eps[9];
                int n_eps = 0;
                cand_eps[n_eps++] = mchess::NO_SQ;
                if (do_ep) {
                    int pawn_rank = (st.stm == mchess::WHITE) ? 4 : 3;
                    int ep_rank = (st.stm == mchess::WHITE) ? 5 : 2;
                    int orig_rank = (st.stm == mchess::WHITE) ? 6 : 1;
                    uint64_t occ = 0;
                    for (int c = 0; c < 2; ++c)
                        for (int pt = 0; pt < 6; ++pt)
                            occ |= st.bb[c][pt];
                    const mchess::Tables& tbl = mchess::tables();
                    for (int f = 0; f < 8; ++f) {
                        int cap_sq = mchess::make_sq(f, pawn_rank);
                        int ep_sq = mchess::make_sq(f, ep_rank);
                        int orig_sq = mchess::make_sq(f, orig_rank);
                        if ((st.bb[~st.stm][mchess::PAWN] & mchess::sq_bb(cap_sq)) &&
                            (st.bb[st.stm][mchess::PAWN] & tbl.pawn_att[~st.stm][ep_sq]) &&
                            !(occ & mchess::sq_bb(ep_sq)) &&
                            !(occ & mchess::sq_bb(orig_sq))) {
                            cand_eps[n_eps++] = static_cast<int8_t>(ep_sq);
                        }
                    }
                }

                if (max_cast == 0 && n_eps == 1) return;
                if (non_stm_in_check(w_, h_, st)) return;

                char buf[128];
                for (uint8_t cm = 0; cm <= max_cast; ++cm) {
                    if ((cm & max_cast) != cm) continue;
                    for (int ei = 0; ei < n_eps; ++ei) {
                        int8_t ep = cand_eps[ei];
                        if (cm == 0 && ep == mchess::NO_SQ) continue;
                        RawState cand = st;
                        cand.castling = cm;
                        cand.ep_sq = ep;
                        int len = raw_to_fen_buf(w_, h_, cand, buf);
                        mchess::Position pos;
                        if (mchess::Position::parse(std::string_view(buf, len), pos) &&
                            pos.castling_rights() == cm &&
                            pos.ep_square() == ep) {
                            uint32_t idx = total_size_++;
                            extra_states_.push_back({b, cm, ep});
                            extra_map_[make_extra_key(b, cm, ep)] = idx;
                        }
                    }
                }
            };

            if (!may_castle && may_ep && base_size_ > 5000000U &&
                groups_.size() >= 2 &&
                groups_[0].pawns_only && groups_[1].pawns_only) {
                // Fast EP enumeration: filter by pawn placement (groups 0 and 1) before iterating kings/pieces.
                uint32_t r0 = group_radix_[0];
                uint32_t r1 = group_radix_[1];
                uint32_t pawn_mod = r0 * r1;
                uint32_t rest_cnt = (base_size_ >> 1) / pawn_mod;

                constexpr uint64_t FILE_A = 0x0101010101010101ULL;
                constexpr uint64_t FILE_H = 0x8080808080808080ULL;
                constexpr uint64_t RANK_4 = 0x00000000FF000000ULL;
                constexpr uint64_t RANK_5 = 0x000000FF00000000ULL;

                for (uint32_t pcode = 0; pcode < pawn_mod; ++pcode) {
                    uint64_t wp_bb = 0;
                    uint64_t bp_bb = 0;
                    uint64_t used = 0;
                    uint32_t tmp_code = pcode;
                    for (int gi = 0; gi < 2; ++gi) {
                        const Group& g = groups_[gi];
                        uint32_t radix = group_radix_[gi];
                        uint64_t rank = tmp_code % radix;
                        tmp_code /= radix;
                        uint64_t avail = pawn_dense_mask_ & ~used;
                        uint64_t placed = 0;
                        if (g.count == 1) {
                            int dsq = select_nth_bit(avail, static_cast<int>(rank));
                            placed = 1ULL << dsq;
                        } else {
                            uint8_t sq_list[64];
                            int m = 0;
                            uint64_t t = avail;
                            while (t) sq_list[m++] = static_cast<uint8_t>(mchess::pop_lsb(t));
                            int x = m - 1;
                            for (int i = g.count; i >= 1; --i) {
                                while (binom_[x][i] > rank) --x;
                                rank -= binom_[x][i];
                                placed |= (1ULL << sq_list[x]);
                                --x;
                            }
                        }
                        used |= placed;
                        if (gi == 0) wp_bb = placed;
                        else bp_bb = placed;
                    }

                    bool has_w_ep = (((((wp_bb & RANK_5) << 1) & ~FILE_A) |
                                      (((wp_bb & RANK_5) >> 1) & ~FILE_H)) & bp_bb) != 0;
                    bool has_b_ep = (((((bp_bb & RANK_4) << 1) & ~FILE_A) |
                                      (((bp_bb & RANK_4) >> 1) & ~FILE_H)) & wp_bb) != 0;
                    if (!has_w_ep && !has_b_ep) continue;

                    for (uint32_t rcode = 0; rcode < rest_cnt; ++rcode) {
                        uint32_t base_code = rcode * pawn_mod + pcode;
                        if (has_w_ep) check_base_state((base_code << 1) | 0U, false, true);
                        if (has_b_ep) check_base_state((base_code << 1) | 1U, false, true);
                    }
                }
            } else {
                for (uint32_t b = 0; b < base_size_; ++b) {
                    check_base_state(b, may_castle, may_ep);
                }
            }
        }
    }
}

void TableIndexer::decode_base_dense(uint32_t base_idx, uint64_t dense_bb[2][6], mchess::Color& stm) const {
    for (int c = 0; c < 2; ++c)
        for (int pt = 0; pt < 6; ++pt)
            dense_bb[c][pt] = 0;

    stm = static_cast<mchess::Color>(base_idx & 1U);
    uint32_t rem_code = base_idx >> 1;

    uint64_t used = 0;
    for (size_t gi = 0; gi < groups_.size(); ++gi) {
        const Group& g = groups_[gi];
        uint32_t radix = group_radix_[gi];
        uint64_t rank = rem_code % radix;
        rem_code /= radix;

        uint64_t avail = (g.pawns_only ? pawn_dense_mask_ : all_dense_mask_) & ~used;
        if (g.count == 1) {
            int dsq = select_nth_bit(avail, static_cast<int>(rank));
            uint64_t bit = 1ULL << dsq;
            dense_bb[g.color][g.pt] |= bit;
            used |= bit;
            continue;
        }

        uint8_t sq_list[64];
        int m = 0;
        uint64_t tmp = avail;
        while (tmp) {
            sq_list[m++] = static_cast<uint8_t>(mchess::pop_lsb(tmp));
        }

        int x = m - 1;
        for (int i = g.count; i >= 1; --i) {
            while (binom_[x][i] > rank) {
                --x;
            }
            rank -= binom_[x][i];
            int dsq = sq_list[x];
            uint64_t bit = 1ULL << dsq;
            dense_bb[g.color][g.pt] |= bit;
            used |= bit;
            --x;
        }
    }
}

uint32_t TableIndexer::encode_base_dense(const uint64_t dense_bb[2][6], mchess::Color stm) const {
    uint64_t used = 0;
    uint32_t code = 0;
    uint32_t mult = 1;

    for (size_t gi = 0; gi < groups_.size(); ++gi) {
        const Group& g = groups_[gi];
        uint64_t avail = (g.pawns_only ? pawn_dense_mask_ : all_dense_mask_) & ~used;
        uint64_t gbb = dense_bb[g.color][g.pt];
        uint64_t rank = 0;
        int k = 1;
        uint64_t tmp = gbb;
        while (tmp) {
            int dsq = mchess::pop_lsb(tmp);
            int rel = mchess::popcount(avail & ((1ULL << dsq) - 1));
            rank += binom_[rel][k++];
        }
        used |= gbb;
        code += static_cast<uint32_t>(rank) * mult;
        mult *= group_radix_[gi];
    }

    return (code << 1) | static_cast<uint32_t>(stm);
}

void TableIndexer::decode_raw(uint32_t idx, RawState& out) const {
    uint32_t b_idx = idx;
    if (idx >= base_size_) {
        const ExtraState& ex = extra_states_[idx - base_size_];
        b_idx = ex.base_idx;
        out.castling = ex.castling;
        out.ep_sq = ex.ep_sq;
    } else {
        out.castling = 0;
        out.ep_sq = mchess::NO_SQ;
    }

    if (w_ == 8) {
        decode_base_dense(b_idx, out.bb, out.stm);
        return;
    }

    for (int c = 0; c < 2; ++c)
        for (int pt = 0; pt < 6; ++pt)
            out.bb[c][pt] = 0;

    uint64_t dense_bb[2][6]{};
    decode_base_dense(b_idx, dense_bb, out.stm);
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            uint64_t b = dense_bb[c][pt];
            while (b) {
                int dsq = mchess::pop_lsb(b);
                out.bb[c][pt] |= mchess::sq_bb(dense_to_eng_sq(w_, dsq));
            }
        }
    }
}

int TableIndexer::raw_to_fen_buf(int w, int h, const RawState& st, char* buf) {
    char board[8][8];
    for (int r = 0; r < h; ++r)
        for (int f = 0; f < w; ++f)
            board[r][f] = '\0';

    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            uint64_t b = st.bb[c][pt];
            char ch = mchess::piece_to_char(static_cast<mchess::Color>(c),
                                            static_cast<mchess::PieceType>(pt));
            while (b) {
                int sq = mchess::pop_lsb(b);
                board[mchess::sq_rank(sq)][mchess::sq_file(sq)] = ch;
            }
        }
    }

    int len = 0;
    for (int r = h - 1; r >= 0; --r) {
        int empty = 0;
        for (int f = 0; f < w; ++f) {
            char ch = board[r][f];
            if (ch == '\0') {
                ++empty;
            } else {
                if (empty > 0) {
                    buf[len++] = static_cast<char>('0' + empty);
                    empty = 0;
                }
                buf[len++] = ch;
            }
        }
        if (empty > 0) buf[len++] = static_cast<char>('0' + empty);
        if (r > 0) buf[len++] = '/';
    }

    buf[len++] = ' ';
    buf[len++] = (st.stm == mchess::WHITE) ? 'w' : 'b';
    buf[len++] = ' ';
    if (st.castling == 0) {
        buf[len++] = '-';
    } else {
        if (st.castling & mchess::WK_CASTLE) buf[len++] = 'K';
        if (st.castling & mchess::WQ_CASTLE) buf[len++] = 'Q';
        if (st.castling & mchess::BK_CASTLE) buf[len++] = 'k';
        if (st.castling & mchess::BQ_CASTLE) buf[len++] = 'q';
    }
    buf[len++] = ' ';
    if (st.ep_sq == mchess::NO_SQ) {
        buf[len++] = '-';
    } else {
        buf[len++] = static_cast<char>('a' + mchess::sq_file(st.ep_sq));
        buf[len++] = static_cast<char>('1' + mchess::sq_rank(st.ep_sq));
    }
    buf[len] = '\0';
    return len;
}

std::string TableIndexer::raw_to_fen(int w, int h, const RawState& st) {
    char buf[128];
    int len = raw_to_fen_buf(w, h, st, buf);
    return std::string(buf, static_cast<size_t>(len));
}

bool TableIndexer::decode_position(uint32_t idx, mchess::Position& out) const {
    RawState st;
    decode_raw(idx, st);
    if (st.castling == 0 && st.ep_sq == mchess::NO_SQ && non_stm_in_check(w_, h_, st)) {
        return false;
    }
    char buf[128];
    int len = raw_to_fen_buf(w_, h_, st, buf);
    return mchess::Position::parse(std::string_view(buf, static_cast<size_t>(len)), out);
}

uint32_t TableIndexer::encode_raw(const RawState& st) const {
    uint32_t b_idx;
    if (w_ == 8) {
        b_idx = encode_base_dense(st.bb, st.stm);
    } else {
        uint64_t dense_bb[2][6]{};
        for (int c = 0; c < 2; ++c) {
            for (int pt = 0; pt < 6; ++pt) {
                uint64_t b = st.bb[c][pt];
                while (b) {
                    int sq = mchess::pop_lsb(b);
                    dense_bb[c][pt] |= (1ULL << eng_to_dense_sq(w_, sq));
                }
            }
        }
        b_idx = encode_base_dense(dense_bb, st.stm);
    }
    if (st.castling == 0 && st.ep_sq == mchess::NO_SQ) {
        return b_idx;
    }
    auto it = extra_map_.find(make_extra_key(b_idx, st.castling, st.ep_sq));
    if (it == extra_map_.end()) return UINT32_MAX;
    return it->second;
}

uint32_t TableIndexer::encode_position(const mchess::Position& pos) const {
    RawState st;
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            st.bb[c][pt] = pos.pieces(static_cast<mchess::Color>(c),
                                      static_cast<mchess::PieceType>(pt));
        }
    }
    st.stm = pos.side_to_move();
    st.castling = pos.castling_rights();
    st.ep_sq = static_cast<int8_t>(pos.ep_square());
    return encode_raw(st);
}

} // namespace tb
