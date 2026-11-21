#include "tablebase.hpp"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace tb {

namespace {

constexpr char MAGIC[8] = {'M', 'C', 'T', 'B', 'v', '0', '0', '1'};

template <typename Callback>
void for_each_quiet_predecessor(const TableIndexer& indexer,
                                uint32_t p_idx,
                                const std::vector<uint8_t>& wdl,
                                Callback&& cb) {
    RawState p;
    indexer.decode_raw(p_idx, p);

    const int w = indexer.width();
    const int h = indexer.height();
    const bool is_8x8 = indexer.is_8x8();
    const uint64_t board_mask = mchess::make_board_mask(w, h);
    const mchess::Color us = ~p.stm;
    const mchess::Color them = p.stm;
    const mchess::Tables& tbl = mchess::tables();

    uint64_t occ_p = 0;
    for (int c = 0; c < 2; ++c)
        for (int pt = 0; pt < 6; ++pt)
            occ_p |= p.bb[c][pt];

    const int ksq_them = mchess::lsb(p.bb[them][mchess::KING]);

    auto check_and_emit = [&](mchess::PieceType pt, int from, int to, uint8_t u_cast, int8_t u_ep) {
        uint64_t toggle = mchess::sq_bb(from) | mchess::sq_bb(to);
        uint64_t occ_u = (occ_p ^ mchess::sq_bb(to)) | mchess::sq_bb(from);

        uint64_t u_us[6];
        for (int i = 0; i < 6; ++i) u_us[i] = p.bb[us][i];
        u_us[pt] ^= toggle;

        if (tbl.pawn_att[them][ksq_them] & u_us[mchess::PAWN]) return;
        if (tbl.knight_att[ksq_them] & u_us[mchess::KNIGHT]) return;
        if (tbl.king_att[ksq_them] & u_us[mchess::KING]) return;
        if (mchess::bishop_attacks(ksq_them, occ_u, board_mask) &
            (u_us[mchess::BISHOP] | u_us[mchess::QUEEN])) return;
        if (mchess::rook_attacks(ksq_them, occ_u, board_mask) &
            (u_us[mchess::ROOK] | u_us[mchess::QUEEN])) return;

        RawState u;
        for (int i = 0; i < 6; ++i) {
            u.bb[us][i] = u_us[i];
            u.bb[them][i] = p.bb[them][i];
        }
        u.stm = us;
        u.castling = u_cast;
        u.ep_sq = u_ep;

        uint32_t u_idx = indexer.encode_raw(u);
        if (u_idx != UINT32_MAX && wdl[u_idx] != WDL_ILLEGAL) {
            cb(u_idx);
        }
    };

    auto emit_with_ep_and_cast = [&](mchess::PieceType pt, int from, int to, uint8_t extra_cast_bits) {
        // Note: castling combinations where u_cast differs from p.castling.
        uint8_t base_c = p.castling;
        uint8_t diff_bits = extra_cast_bits & ~base_c;

        auto emit_for_cast = [&](uint8_t uc) {
            check_and_emit(pt, from, to, uc, mchess::NO_SQ);
            if (is_8x8 &&
                indexer.signature().count[mchess::WHITE][mchess::PAWN] > 0 &&
                indexer.signature().count[mchess::BLACK][mchess::PAWN] > 0) {
                int ep_rank = (us == mchess::WHITE) ? 5 : 2;
                for (int f = 0; f < 8; ++f) {
                    check_and_emit(pt, from, to, uc, static_cast<int8_t>(mchess::make_sq(f, ep_rank)));
                }
            }
        };

        emit_for_cast(base_c);
        if (diff_bits != 0) {
            for (uint8_t sub = diff_bits; sub > 0; sub = (sub - 1) & diff_bits) {
                emit_for_cast(base_c | sub);
            }
        }
    };

    // If p.ep_sq != NO_SQ, the ONLY quiet move reaching p is a double pawn push by `us`.
    if (p.ep_sq != mchess::NO_SQ) {
        int dir = (us == mchess::WHITE) ? 8 : -8;
        int to = p.ep_sq + dir;
        int from = p.ep_sq - dir;
        if (to >= 0 && to < 64 && from >= 0 && from < 64 &&
            (p.bb[us][mchess::PAWN] & mchess::sq_bb(to)) &&
            !(occ_p & mchess::sq_bb(from)) &&
            !(occ_p & mchess::sq_bb(p.ep_sq))) {
            emit_with_ep_and_cast(mchess::PAWN, from, to, 0);
        }
        return;
    }

    // 1. Non-pawn pieces
    const uint64_t empty = ~occ_p;
    for (int pt_i = mchess::KNIGHT; pt_i <= mchess::KING; ++pt_i) {
        mchess::PieceType pt = static_cast<mchess::PieceType>(pt_i);
        uint64_t pieces = p.bb[us][pt];
        while (pieces) {
            int to = mchess::pop_lsb(pieces);
            uint64_t cand_from = 0;
            switch (pt) {
                case mchess::KNIGHT: cand_from = tbl.knight_att[to] & board_mask & empty; break;
                case mchess::BISHOP: cand_from = mchess::bishop_attacks(to, occ_p, board_mask) & empty; break;
                case mchess::ROOK:   cand_from = mchess::rook_attacks(to, occ_p, board_mask) & empty; break;
                case mchess::QUEEN:  cand_from = mchess::queen_attacks(to, occ_p, board_mask) & empty; break;
                case mchess::KING:   cand_from = tbl.king_att[to] & board_mask & empty; break;
                default: break;
            }
            while (cand_from) {
                int from = mchess::pop_lsb(cand_from);
                uint8_t extra_cast = 0;
                if (is_8x8 && indexer.signature().count[us][mchess::ROOK] > 0) {
                    if (us == mchess::WHITE) {
                        if (pt == mchess::KING && from == mchess::make_sq(4, 0))
                            extra_cast = mchess::WK_CASTLE | mchess::WQ_CASTLE;
                        else if (pt == mchess::ROOK && from == mchess::make_sq(7, 0))
                            extra_cast = mchess::WK_CASTLE;
                        else if (pt == mchess::ROOK && from == mchess::make_sq(0, 0))
                            extra_cast = mchess::WQ_CASTLE;
                    } else {
                        if (pt == mchess::KING && from == mchess::make_sq(4, 7))
                            extra_cast = mchess::BK_CASTLE | mchess::BQ_CASTLE;
                        else if (pt == mchess::ROOK && from == mchess::make_sq(7, 7))
                            extra_cast = mchess::BK_CASTLE;
                        else if (pt == mchess::ROOK && from == mchess::make_sq(0, 7))
                            extra_cast = mchess::BQ_CASTLE;
                    }
                }
                emit_with_ep_and_cast(pt, from, to, extra_cast);
            }
        }
    }

    // 2. Pawns (non-promotion quiet moves)
    {
        int dir = (us == mchess::WHITE) ? 8 : -8;
        uint64_t pawns = p.bb[us][mchess::PAWN];
        while (pawns) {
            int to = mchess::pop_lsb(pawns);
            int from1 = to - dir;
            int r_from1 = mchess::sq_rank(from1);
            if (r_from1 >= 1 && r_from1 <= h - 2 && !(occ_p & mchess::sq_bb(from1))) {
                emit_with_ep_and_cast(mchess::PAWN, from1, to, 0);
            }
            if (is_8x8) {
                int target_rank = (us == mchess::WHITE) ? 3 : 4;
                if (mchess::sq_rank(to) == target_rank) {
                    int mid = to - dir;
                    int from2 = to - 2 * dir;
                    if (!(occ_p & (mchess::sq_bb(mid) | mchess::sq_bb(from2)))) {
                        emit_with_ep_and_cast(mchess::PAWN, from2, to, 0);
                    }
                }
            }
        }
    }

    // 3. Castling unmoves on 8x8
    if (is_8x8 && indexer.signature().count[us][mchess::ROOK] > 0) {
        int rank = (us == mchess::WHITE) ? 0 : 7;
        uint8_t us_k_bit = (us == mchess::WHITE) ? mchess::WK_CASTLE : mchess::BK_CASTLE;
        uint8_t us_q_bit = (us == mchess::WHITE) ? mchess::WQ_CASTLE : mchess::BQ_CASTLE;
        if ((p.castling & (us_k_bit | us_q_bit)) == 0) {
            auto try_uncastle = [&](int k_to_f, int r_to_f, int r_from_f, uint8_t req_bit, uint8_t opt_bit, const char* mv_str) {
                int k_to = mchess::make_sq(k_to_f, rank);
                int r_to = mchess::make_sq(r_to_f, rank);
                int k_from = mchess::make_sq(4, rank);
                int r_from = mchess::make_sq(r_from_f, rank);
                if ((p.bb[us][mchess::KING] & mchess::sq_bb(k_to)) &&
                    (p.bb[us][mchess::ROOK] & mchess::sq_bb(r_to)) &&
                    !(occ_p & (mchess::sq_bb(k_from) | mchess::sq_bb(r_from)))) {
                    uint8_t masks[2] = {
                        static_cast<uint8_t>(p.castling | req_bit),
                        static_cast<uint8_t>(p.castling | req_bit | opt_bit)
                    };
                    for (int mi = 0; mi < 2; ++mi) {
                        if (mi == 1 && masks[1] == masks[0]) continue;
                        RawState u = p;
                        u.stm = us;
                        u.castling = masks[mi];
                        u.ep_sq = mchess::NO_SQ;
                        u.bb[us][mchess::KING] ^= mchess::sq_bb(k_to) | mchess::sq_bb(k_from);
                        u.bb[us][mchess::ROOK] ^= mchess::sq_bb(r_to) | mchess::sq_bb(r_from);
                        uint32_t u_idx = indexer.encode_raw(u);
                        if (u_idx != UINT32_MAX && wdl[u_idx] != WDL_ILLEGAL) {
                            mchess::Position u_pos;
                            if (indexer.decode_position(u_idx, u_pos)) {
                                if (auto mv = u_pos.parse_move(mv_str)) {
                                    (void)mv;
                                    cb(u_idx);
                                }
                            }
                        }
                    }
                }
            };
            if (us == mchess::WHITE) {
                try_uncastle(6, 5, 7, mchess::WK_CASTLE, mchess::WQ_CASTLE, "e1g1");
                try_uncastle(2, 3, 0, mchess::WQ_CASTLE, mchess::WK_CASTLE, "e1c1");
            } else {
                try_uncastle(6, 5, 7, mchess::BK_CASTLE, mchess::BQ_CASTLE, "e8g8");
                try_uncastle(2, 3, 0, mchess::BQ_CASTLE, mchess::BK_CASTLE, "e8c8");
            }
        }
    }
}

bool is_capture_or_promo(const mchess::Position& pos, mchess::Move m) {
    if (m.promo != mchess::NO_PIECE) return true;
    if (pos.piece_at(m.to) != mchess::NO_PIECE) return true;
    if (pos.ep_square() != mchess::NO_SQ &&
        m.to == pos.ep_square() &&
        pos.piece_at(m.from) == mchess::PAWN) {
        return true;
    }
    return false;
}

} // namespace

std::vector<uint32_t> collect_quiet_predecessors(const TableIndexer& indexer,
                                                 uint32_t p_idx,
                                                 const std::vector<uint8_t>& wdl) {
    std::vector<uint32_t> out;
    for_each_quiet_predecessor(indexer, p_idx, wdl, [&](uint32_t u_idx) {
        out.push_back(u_idx);
    });
    return out;
}

TableStats Tablebase::compute_stats() const {
    TableStats st;
    st.width = width;
    st.height = height;
    st.signature = sig.to_string();
    st.index_size = indexer->size();
    st.gen_seconds = gen_seconds;
    st.table_bytes = wdl.size() * sizeof(uint8_t) + dtm.size() * sizeof(uint16_t);

    uint32_t max_w_idx = UINT32_MAX;
    uint32_t max_l_idx = UINT32_MAX;

    for (uint32_t idx = 0; idx < indexer->size(); ++idx) {
        uint8_t w = wdl[idx];
        if (w == WDL_ILLEGAL) continue;
        ++st.legal_positions;
        if (w == WDL_WIN) {
            ++st.wins;
            if (dtm[idx] > st.max_win_dtm || max_w_idx == UINT32_MAX) {
                st.max_win_dtm = dtm[idx];
                max_w_idx = idx;
            }
        } else if (w == WDL_LOSS) {
            ++st.losses;
            if (dtm[idx] == 0) ++st.checkmates;
            if (dtm[idx] > st.max_loss_dtm || max_l_idx == UINT32_MAX) {
                st.max_loss_dtm = dtm[idx];
                max_l_idx = idx;
            }
        } else if (w == WDL_DRAW) {
            ++st.draws;
            mchess::Position pos;
            if (indexer->decode_position(idx, pos) && !pos.has_legal_moves()) {
                ++st.stalemates;
            }
        }
    }

    if (max_w_idx != UINT32_MAX) {
        mchess::Position pos;
        if (indexer->decode_position(max_w_idx, pos)) st.max_win_fen = pos.to_fen();
    }
    if (max_l_idx != UINT32_MAX) {
        mchess::Position pos;
        if (indexer->decode_position(max_l_idx, pos)) st.max_loss_fen = pos.to_fen();
    }
    return st;
}

bool Tablebase::save(const std::string& path) const {
    std::filesystem::path p(path);
    if (p.has_parent_path()) {
        std::filesystem::create_directories(p.parent_path());
    }
    std::ofstream os(path, std::ios::binary);
    if (!os) return false;

    uint8_t w8 = static_cast<uint8_t>(width);
    uint8_t h8 = static_cast<uint8_t>(height);
    uint32_t n = static_cast<uint32_t>(wdl.size());

    os.write(MAGIC, 8);
    os.write(reinterpret_cast<const char*>(&w8), 1);
    os.write(reinterpret_cast<const char*>(&h8), 1);
    os.write(reinterpret_cast<const char*>(sig.count.data()), 12);
    os.write(reinterpret_cast<const char*>(&n), sizeof(n));
    os.write(reinterpret_cast<const char*>(&gen_seconds), sizeof(gen_seconds));
    os.write(reinterpret_cast<const char*>(wdl.data()), n * sizeof(uint8_t));
    os.write(reinterpret_cast<const char*>(dtm.data()), n * sizeof(uint16_t));
    return static_cast<bool>(os);
}

std::unique_ptr<Tablebase> Tablebase::load(const std::string& path) {
    std::ifstream is(path, std::ios::binary);
    if (!is) return nullptr;

    char magic[8];
    if (!is.read(magic, 8) || std::memcmp(magic, MAGIC, 8) != 0) return nullptr;

    uint8_t w8 = 0, h8 = 0;
    MaterialSig sig;
    uint32_t n = 0;
    double gen_s = 0.0;

    if (!is.read(reinterpret_cast<char*>(&w8), 1)) return nullptr;
    if (!is.read(reinterpret_cast<char*>(&h8), 1)) return nullptr;
    if (!is.read(reinterpret_cast<char*>(sig.count.data()), 12)) return nullptr;
    if (!is.read(reinterpret_cast<char*>(&n), sizeof(n))) return nullptr;
    if (!is.read(reinterpret_cast<char*>(&gen_s), sizeof(gen_s))) return nullptr;

    auto tb = std::make_unique<Tablebase>();
    tb->width = w8;
    tb->height = h8;
    tb->sig = sig;
    tb->gen_seconds = gen_s;
    tb->indexer = std::make_unique<TableIndexer>(w8, h8, sig);
    if (tb->indexer->size() != n) return nullptr;

    tb->wdl.resize(n);
    tb->dtm.resize(n);
    if (!is.read(reinterpret_cast<char*>(tb->wdl.data()), n * sizeof(uint8_t))) return nullptr;
    if (!is.read(reinterpret_cast<char*>(tb->dtm.data()), n * sizeof(uint16_t))) return nullptr;
    return tb;
}

std::string TableStore::db_path(int w, int h, const MaterialSig& sig) const {
    std::ostringstream oss;
    oss << db_dir_ << "/" << w << "x" << h << "_" << sig.to_string() << ".tb";
    return oss.str();
}

const Tablebase* TableStore::find(int w, int h, const MaterialSig& sig) const {
    auto it = tables_.find(Key{w, h, sig});
    if (it == tables_.end()) return nullptr;
    return it->second.get();
}

bool TableStore::lookup(const mchess::Position& pos, WDL& out_wdl, uint16_t& out_dtm, int* out_table_id) const {
    MaterialSig sig = MaterialSig::from_position(pos);
    const Tablebase* tb = find(pos.width(), pos.height(), sig);
    if (!tb) return false;
    uint32_t idx = tb->indexer->encode_position(pos);
    if (idx == UINT32_MAX) return false;
    out_wdl = static_cast<WDL>(tb->wdl[idx]);
    out_dtm = tb->dtm[idx];
    if (out_table_id) *out_table_id = tb->id;
    return out_wdl != WDL_ILLEGAL;
}

const Tablebase& TableStore::ensure(int w, int h, const MaterialSig& sig, bool save_to_disk) {
    Key key{w, h, sig};
    auto it = tables_.find(key);
    if (it != tables_.end()) return *it->second;

    // Ensure dependencies first!
    for (const MaterialSig& dep : sig.dependencies()) {
        ensure(w, h, dep, save_to_disk);
    }

    // Check disk cache.
    std::string path = db_path(w, h, sig);
    if (save_to_disk && std::filesystem::exists(path)) {
        if (auto loaded = Tablebase::load(path)) {
            loaded->id = static_cast<int>(by_id_.size());
            by_id_.push_back(loaded.get());
            const Tablebase& ref = *loaded;
            tables_.emplace(key, std::move(loaded));
            return ref;
        }
    }

    // Generate tablebase via retrograde analysis.
    auto t0 = std::chrono::steady_clock::now();

    auto tb = std::make_unique<Tablebase>();
    tb->width = w;
    tb->height = h;
    tb->sig = sig;
    tb->indexer = std::make_unique<TableIndexer>(w, h, sig);
    const uint32_t N = tb->indexer->size();

    tb->wdl.assign(N, WDL_UNKNOWN);
    tb->dtm.assign(N, 0);

    std::vector<uint16_t> rem_children(N, 0);
    std::vector<uint16_t> max_sub_win_dtm(N, 0);
    std::vector<uint8_t> processed(N, 0);
    std::vector<std::vector<uint32_t>> win_buckets(2);
    std::vector<std::vector<uint32_t>> loss_buckets(2);

    // 1. Initialization pass
    mchess::Move moves[mchess::MAX_MOVES];
    for (uint32_t idx = 0; idx < N; ++idx) {
        mchess::Position pos;
        if (!tb->indexer->decode_position(idx, pos)) {
            tb->wdl[idx] = WDL_ILLEGAL;
            continue;
        }
        int nm = pos.legal_moves(moves);
        if (nm == 0) {
            if (pos.in_check()) {
                tb->wdl[idx] = WDL_LOSS;
                tb->dtm[idx] = 0;
                loss_buckets[0].push_back(idx);
            } else {
                tb->wdl[idx] = WDL_DRAW;
                tb->dtm[idx] = 0;
            }
            continue;
        }

        uint16_t rem = static_cast<uint16_t>(nm);
        uint16_t best_win = UINT16_MAX;
        uint16_t max_sub_win = 0;

        for (int i = 0; i < nm; ++i) {
            if (is_capture_or_promo(pos, moves[i])) {
                mchess::Position next = pos.make_move(moves[i]);
                WDL c_wdl = WDL_UNKNOWN;
                uint16_t c_dtm = 0;
                if (!lookup(next, c_wdl, c_dtm)) {
                    throw std::runtime_error("missing child position in dependency table");
                }
                if (c_wdl == WDL_LOSS) {
                    uint16_t cand = static_cast<uint16_t>(c_dtm + 1);
                    if (cand < best_win) best_win = cand;
                } else if (c_wdl == WDL_WIN) {
                    --rem;
                    if (c_dtm > max_sub_win) max_sub_win = c_dtm;
                }
            }
        }

        rem_children[idx] = rem;
        max_sub_win_dtm[idx] = max_sub_win;

        if (best_win < UINT16_MAX) {
            if (win_buckets.size() <= best_win) win_buckets.resize(best_win + 1);
            win_buckets[best_win].push_back(idx);
        } else if (rem == 0) {
            uint16_t l_dtm = static_cast<uint16_t>(max_sub_win + 1);
            tb->wdl[idx] = WDL_LOSS;
            tb->dtm[idx] = l_dtm;
            if (loss_buckets.size() <= l_dtm) loss_buckets.resize(l_dtm + 1);
            loss_buckets[l_dtm].push_back(idx);
        }
    }

    // 2. Retrograde propagation loop
    for (size_t d = 0; d < loss_buckets.size() || d < win_buckets.size(); ++d) {
        if ((d & 1U) == 0) {
            if (d >= loss_buckets.size()) continue;
            for (size_t k = 0; k < loss_buckets[d].size(); ++k) {
                uint32_t p_idx = loss_buckets[d][k];
                uint16_t next_d = static_cast<uint16_t>(d + 1);
                for_each_quiet_predecessor(*tb->indexer, p_idx, tb->wdl, [&](uint32_t u_idx) {
                    if (tb->wdl[u_idx] == WDL_UNKNOWN) {
                        tb->wdl[u_idx] = WDL_WIN;
                        tb->dtm[u_idx] = next_d;
                        if (win_buckets.size() <= next_d) win_buckets.resize(next_d + 1);
                        win_buckets[next_d].push_back(u_idx);
                    }
                });
            }
            std::vector<uint32_t>().swap(loss_buckets[d]);
        } else {
            if (d >= win_buckets.size()) continue;
            for (size_t k = 0; k < win_buckets[d].size(); ++k) {
                uint32_t p_idx = win_buckets[d][k];
                if (processed[p_idx]) continue;
                if (tb->wdl[p_idx] == WDL_UNKNOWN) {
                    tb->wdl[p_idx] = WDL_WIN;
                    tb->dtm[p_idx] = static_cast<uint16_t>(d);
                } else if (tb->wdl[p_idx] != WDL_WIN || tb->dtm[p_idx] != d) {
                    continue;
                }
                processed[p_idx] = 1;
                for_each_quiet_predecessor(*tb->indexer, p_idx, tb->wdl, [&](uint32_t u_idx) {
                    if (tb->wdl[u_idx] == WDL_UNKNOWN) {
                        if (--rem_children[u_idx] == 0) {
                            uint16_t base_max = std::max<uint16_t>(
                                max_sub_win_dtm[u_idx], static_cast<uint16_t>(d));
                            uint16_t next_d = static_cast<uint16_t>(base_max + 1);
                            tb->wdl[u_idx] = WDL_LOSS;
                            tb->dtm[u_idx] = next_d;
                            if (loss_buckets.size() <= next_d) loss_buckets.resize(next_d + 1);
                            loss_buckets[next_d].push_back(u_idx);
                        }
                    }
                });
            }
            std::vector<uint32_t>().swap(win_buckets[d]);
        }
    }

    // 3. Finalize draws
    for (uint32_t idx = 0; idx < N; ++idx) {
        if (tb->wdl[idx] == WDL_UNKNOWN) {
            tb->wdl[idx] = WDL_DRAW;
            tb->dtm[idx] = 0;
        }
    }

    auto t1 = std::chrono::steady_clock::now();
    tb->gen_seconds = std::chrono::duration<double>(t1 - t0).count();

    if (save_to_disk) {
        tb->save(path);
    }

    tb->id = static_cast<int>(by_id_.size());
    by_id_.push_back(tb.get());
    const Tablebase& ref = *tb;
    tables_.emplace(key, std::move(tb));
    return ref;
}

bool TableStore::verify(int w, int h, const MaterialSig& sig, std::string* err) {
    const Tablebase& tb = ensure(w, h, sig);
    const uint32_t N = tb.indexer->size();
    mchess::Move moves[mchess::MAX_MOVES];

    auto fail = [&](uint32_t idx, const std::string& msg) -> bool {
        if (err) {
            std::ostringstream oss;
            oss << w << "x" << h << " " << sig.to_string() << " idx=" << idx << ": " << msg;
            *err = oss.str();
        }
        return false;
    };

    for (uint32_t idx = 0; idx < N; ++idx) {
        mchess::Position pos;
        bool valid = tb.indexer->decode_position(idx, pos);
        uint8_t v = tb.wdl[idx];
        uint16_t d = tb.dtm[idx];

        if (!valid) {
            if (v != WDL_ILLEGAL) return fail(idx, "invalid position not marked ILLEGAL");
            continue;
        }
        if (v == WDL_ILLEGAL) return fail(idx, "valid position marked ILLEGAL");

        int nm = pos.legal_moves(moves);
        if (nm == 0) {
            if (pos.in_check()) {
                if (v != WDL_LOSS || d != 0) return fail(idx, "checkmate must be LOSS dtm=0");
            } else {
                if (v != WDL_DRAW || d != 0) return fail(idx, "stalemate must be DRAW dtm=0");
            }
            continue;
        }

        bool has_draw = false;
        bool has_loss = false;
        bool all_win = true;
        uint16_t min_loss_dtm = UINT16_MAX;
        uint16_t max_win_dtm = 0;

        for (int i = 0; i < nm; ++i) {
            mchess::Position next = pos.make_move(moves[i]);
            WDL cw = WDL_UNKNOWN;
            uint16_t cd = 0;
            if (!lookup(next, cw, cd)) {
                return fail(idx, "missing successor " + next.to_fen());
            }
            if (cw == WDL_LOSS) {
                has_loss = true;
                all_win = false;
                if (cd < min_loss_dtm) min_loss_dtm = cd;
            } else if (cw == WDL_DRAW) {
                has_draw = true;
                all_win = false;
            } else if (cw == WDL_WIN) {
                if (cd > max_win_dtm) max_win_dtm = cd;
            } else {
                return fail(idx, "illegal successor status");
            }
        }

        if (v == WDL_WIN) {
            if (!has_loss || d != min_loss_dtm + 1 || (d & 1U) == 0) {
                return fail(idx, "WIN entry inconsistent with successors");
            }
        } else if (v == WDL_LOSS) {
            if (!all_win || d != max_win_dtm + 1 || (d & 1U) == 1 || d == 0) {
                return fail(idx, "LOSS entry inconsistent with successors");
            }
        } else if (v == WDL_DRAW) {
            if (has_loss || !has_draw || d != 0) {
                return fail(idx, "DRAW entry inconsistent with successors");
            }
        } else {
            return fail(idx, "unknown WDL value");
        }
    }
    return true;
}

bool TableStore::export_certificates(const mchess::Position& root_pos,
                                     std::vector<std::string>& out_certs,
                                     std::vector<std::string>& out_claims,
                                     std::vector<uint32_t>& out_entries,
                                     std::vector<uint16_t>& out_max_ranks,
                                     std::string* err) {
    out_certs.clear();
    out_claims.clear();
    out_entries.clear();
    out_max_ranks.clear();

    MaterialSig root_sig = MaterialSig::from_position(root_pos);
    ensure(root_pos.width(), root_pos.height(), root_sig);

    WDL root_wdl = WDL_UNKNOWN;
    uint16_t root_dtm = 0;
    if (!lookup(root_pos, root_wdl, root_dtm)) {
        if (err) *err = "root position not found in tablebase";
        return false;
    }

    auto make_uid = [&](const mchess::Position& p) -> uint64_t {
        MaterialSig s = MaterialSig::from_position(p);
        const Tablebase* tb = find(p.width(), p.height(), s);
        uint32_t idx = tb->indexer->encode_position(p);
        return (static_cast<uint64_t>(tb->id) << 32) | idx;
    };

    auto pick_win_move = [&](const mchess::Position& p, uint16_t p_dtm) -> mchess::Move {
        mchess::Move moves[mchess::MAX_MOVES];
        int nm = p.legal_moves(moves);
        mchess::Move best{};
        bool found = false;
        int best_replies = INT32_MAX;
        std::string best_str;
        for (int i = 0; i < nm; ++i) {
            mchess::Position q = p.make_move(moves[i]);
            WDL qw = WDL_UNKNOWN;
            uint16_t qd = 0;
            lookup(q, qw, qd);
            if (qw == WDL_LOSS && qd + 1 == p_dtm) {
                mchess::Move rbuf[mchess::MAX_MOVES];
                int nrep = q.legal_moves(rbuf);
                std::string mstr = moves[i].to_string();
                if (!found || nrep < best_replies || (nrep == best_replies && mstr < best_str)) {
                    found = true;
                    best = moves[i];
                    best_replies = nrep;
                    best_str = std::move(mstr);
                }
            }
        }
        return best;
    };

    auto pick_draw_move = [&](const mchess::Position& p) -> mchess::Move {
        mchess::Move moves[mchess::MAX_MOVES];
        int nm = p.legal_moves(moves);
        mchess::Move best{};
        bool found = false;
        uint64_t best_tb_size = UINT64_MAX;
        int best_replies = INT32_MAX;
        std::string best_str;
        for (int i = 0; i < nm; ++i) {
            mchess::Position q = p.make_move(moves[i]);
            WDL qw = WDL_UNKNOWN;
            uint16_t qd = 0;
            int q_tid = -1;
            lookup(q, qw, qd, &q_tid);
            if (qw == WDL_DRAW) {
                uint64_t tb_sz = by_id_[q_tid]->indexer->size();
                mchess::Move rbuf[mchess::MAX_MOVES];
                int nrep = q.legal_moves(rbuf);
                std::string mstr = moves[i].to_string();
                if (!found ||
                    tb_sz < best_tb_size ||
                    (tb_sz == best_tb_size && nrep < best_replies) ||
                    (tb_sz == best_tb_size && nrep == best_replies && mstr < best_str)) {
                    found = true;
                    best = moves[i];
                    best_tb_size = tb_sz;
                    best_replies = nrep;
                    best_str = std::move(mstr);
                }
            }
        }
        return best;
    };

    if (root_wdl == WDL_WIN || root_wdl == WDL_LOSS) {
        mchess::Color prover = (root_wdl == WDL_WIN)
                                   ? root_pos.side_to_move()
                                   : ~root_pos.side_to_move();
        char prover_ch = (prover == mchess::WHITE) ? 'w' : 'b';
        std::string claim = std::string("WIN ") + prover_ch;

        std::ostringstream oss;
        oss << "#cert v1\n#claim " << claim << "\n#root " << root_pos.to_fen() << "\n";

        std::unordered_set<uint64_t> visited;
        std::queue<mchess::Position> q_bfs;
        auto enqueue = [&](const mchess::Position& p) {
            uint64_t uid = make_uid(p);
            if (visited.insert(uid).second) {
                q_bfs.push(p);
            }
        };

        if (root_pos.side_to_move() == prover) {
            enqueue(root_pos);
        } else {
            for (const auto& rm : root_pos.legal_moves()) {
                enqueue(root_pos.make_move(rm));
            }
        }

        uint32_t entries = 0;
        uint16_t max_rank = 0;
        while (!q_bfs.empty()) {
            mchess::Position p = q_bfs.front();
            q_bfs.pop();

            WDL pw = WDL_UNKNOWN;
            uint16_t pd = 0;
            lookup(p, pw, pd);
            if (pw != WDL_WIN || pd == 0) {
                if (err) *err = "internal error: non-win position reached in WIN cert";
                return false;
            }

            mchess::Move mv = pick_win_move(p, pd);
            uint16_t rank = static_cast<uint16_t>((pd + 1) / 2);
            if (rank > max_rank) max_rank = rank;
            oss << p.to_fen() << "\t" << mv.to_string() << "\t" << rank << "\n";
            ++entries;

            mchess::Position q = p.make_move(mv);
            mchess::Move rbuf[mchess::MAX_MOVES];
            int nr = q.legal_moves(rbuf);
            for (int i = 0; i < nr; ++i) {
                enqueue(q.make_move(rbuf[i]));
            }
        }

        out_certs.push_back(oss.str());
        out_claims.push_back(claim);
        out_entries.push_back(entries);
        out_max_ranks.push_back(max_rank);
        return true;
    }

    if (root_wdl == WDL_DRAW) {
        for (int p_i = 0; p_i < 2; ++p_i) {
            mchess::Color prover = static_cast<mchess::Color>(p_i);
            char prover_ch = (prover == mchess::WHITE) ? 'w' : 'b';
            std::string claim = std::string("ATLEAST_DRAW ") + prover_ch;

            std::ostringstream oss;
            oss << "#cert v1\n#claim " << claim << "\n#root " << root_pos.to_fen() << "\n";

            std::unordered_set<uint64_t> visited;
            std::queue<mchess::Position> q_bfs;
            auto enqueue = [&](const mchess::Position& p) {
                uint64_t uid = make_uid(p);
                if (visited.insert(uid).second) {
                    q_bfs.push(p);
                }
            };

            if (root_pos.side_to_move() == prover) {
                enqueue(root_pos);
            } else {
                for (const auto& rm : root_pos.legal_moves()) {
                    enqueue(root_pos.make_move(rm));
                }
            }

            uint32_t entries = 0;
            while (!q_bfs.empty()) {
                mchess::Position p = q_bfs.front();
                q_bfs.pop();

                mchess::Move rbuf[mchess::MAX_MOVES];
                int nm = p.legal_moves(rbuf);
                if (nm == 0) {
                    // Prover stalemate is covered without an entry (SPEC v1.1).
                    if (p.in_check()) {
                        if (err) *err = "internal error: prover checkmated in ATLEAST_DRAW cert";
                        return false;
                    }
                    continue;
                }

                WDL pw = WDL_UNKNOWN;
                uint16_t pd = 0;
                lookup(p, pw, pd);

                mchess::Move mv = (pw == WDL_WIN) ? pick_win_move(p, pd) : pick_draw_move(p);
                oss << p.to_fen() << "\t" << mv.to_string() << "\t0\n";
                ++entries;

                mchess::Position q = p.make_move(mv);
                int nr = q.legal_moves(rbuf);
                for (int i = 0; i < nr; ++i) {
                    enqueue(q.make_move(rbuf[i]));
                }
            }

            out_certs.push_back(oss.str());
            out_claims.push_back(claim);
            out_entries.push_back(entries);
            out_max_ranks.push_back(0);
        }
        return true;
    }

    if (err) *err = "invalid root WDL state";
    return false;
}

} // namespace tb
