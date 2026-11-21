#include "tb_probe.hpp"

#include <climits>
#include <filesystem>
#include <sstream>

namespace msolve {

uint64_t TablebaseProbe::pack_sig(const tb::MaterialSig& sig) {
    uint64_t k = 0;
    int shift = 0;
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            k |= (static_cast<uint64_t>(sig.count[c][pt] & 0xF) << shift);
            shift += 4;
        }
    }
    return k;
}

uint64_t TablebaseProbe::pack_sig_from_pos(const Position& pos) {
    uint64_t k = 0;
    int shift = 0;
    for (int c = 0; c < 2; ++c) {
        Color col = static_cast<Color>(c);
        for (int pt = 0; pt < 6; ++pt) {
            uint64_t cnt = static_cast<uint64_t>(__builtin_popcountll(pos.pieces(col, static_cast<PieceType>(pt))));
            k |= ((cnt & 0xFULL) << shift);
            shift += 4;
        }
    }
    return k;
}

bool TablebaseProbe::load_board(const std::string& tb_dir,
                                int w,
                                int h,
                                int max_pieces,
                                std::string* info) {
    tables_.clear();
    w_ = w;
    h_ = h;
    max_pieces_ = 0;
    total_bytes_ = 0;

    if (tb_dir.empty() || !std::filesystem::exists(tb_dir)) {
        if (info) *info = "tb_dir not found: " + tb_dir;
        return false;
    }

    auto sigs = tb::enumerate_signatures(max_pieces);
    for (const auto& sig : sigs) {
        std::ostringstream oss;
        oss << tb_dir << "/" << w << "x" << h << "_" << sig.to_string() << ".tb";
        std::string path = oss.str();
        if (!std::filesystem::exists(path)) continue;
        auto loaded = tb::Tablebase::load(path);
        if (!loaded) continue;
        if (loaded->width != w || loaded->height != h) continue;
        int tp = sig.total_pieces();
        if (tp > max_pieces_) max_pieces_ = tp;
        total_bytes_ += loaded->wdl.size() * sizeof(uint8_t) + loaded->dtm.size() * sizeof(uint16_t);
        tables_.emplace(pack_sig(sig), std::move(loaded));
    }

    if (info) {
        std::ostringstream oss;
        oss << "loaded " << tables_.size() << " tables for " << w << "x" << h
            << " (max_pieces=" << max_pieces_
            << ", bytes=" << total_bytes_ << ")";
        *info = oss.str();
    }
    return !tables_.empty();
}

bool TablebaseProbe::probe(const Position& pos,
                           tb::WDL& out_wdl,
                           uint16_t& out_dtm,
                           uint32_t* out_tb_size) const {
    if (tables_.empty() || pos.width() != w_ || pos.height() != h_) return false;
    int n_pieces = __builtin_popcountll(pos.occupancy());
    if (n_pieces > max_pieces_) return false;

    uint64_t skey = pack_sig_from_pos(pos);
    auto it = tables_.find(skey);
    if (it == tables_.end()) return false;

    const tb::Tablebase* tbl = it->second.get();
    uint32_t idx = tbl->indexer->encode_position(pos);
    if (idx == UINT32_MAX) return false;

    uint8_t w = tbl->wdl[idx];
    if (w == tb::WDL_ILLEGAL || w == tb::WDL_UNKNOWN) return false;

    out_wdl = static_cast<tb::WDL>(w);
    out_dtm = tbl->dtm[idx];
    if (out_tb_size) *out_tb_size = tbl->indexer->size();
    return true;
}

bool TablebaseProbe::pick_win_move(const Position& pos, uint16_t p_dtm, Move& out_move) const {
    if (p_dtm == 0) return false;
    Move moves[MAX_MOVES];
    Move rbuf[MAX_MOVES];
    int nm = pos.legal_moves(moves);

    bool found = false;
    Move best{};
    int best_replies = INT_MAX;
    std::string best_str;

    for (int i = 0; i < nm; ++i) {
        Position q = pos.make_move(moves[i]);
        tb::WDL qw = tb::WDL_UNKNOWN;
        uint16_t qd = 0;
        if (!probe(q, qw, qd)) continue;
        if (qw == tb::WDL_LOSS && qd + 1 == p_dtm) {
            int nr = q.legal_moves(rbuf);
            std::string mstr = moves[i].to_string();
            if (!found || nr < best_replies || (nr == best_replies && mstr < best_str)) {
                found = true;
                best = moves[i];
                best_replies = nr;
                best_str = std::move(mstr);
            }
        }
    }

    if (!found) return false;
    out_move = best;
    return true;
}

bool TablebaseProbe::pick_draw_move(const Position& pos,
                                    const std::unordered_set<std::string>* preferred_seen,
                                    Move& out_move) const {
    Move moves[MAX_MOVES];
    Move rbuf[MAX_MOVES];
    int nm = pos.legal_moves(moves);

    bool found = false;
    Move best{};
    int best_tier = INT_MAX; // 0 = 0 replies, 1 = all replies in preferred_seen, 2 = normal TB draw
    uint32_t best_tb_size = UINT32_MAX;
    int best_replies = INT_MAX;
    std::string best_str;

    for (int i = 0; i < nm; ++i) {
        Position q = pos.make_move(moves[i]);
        tb::WDL qw = tb::WDL_UNKNOWN;
        uint16_t qd = 0;
        uint32_t q_tb_sz = 0;
        if (!probe(q, qw, qd, &q_tb_sz)) continue;
        if (qw != tb::WDL_DRAW) continue;

        int nr = q.legal_moves(rbuf);
        int tier = 2;
        if (nr == 0) {
            tier = 0;
        } else if (preferred_seen != nullptr) {
            bool all_in = true;
            for (int j = 0; j < nr; ++j) {
                Position qr = q.make_move(rbuf[j]);
                if (!qr.has_legal_moves()) {
                    if (qr.in_check()) {
                        all_in = false;
                        break;
                    }
                    continue;
                }
                if (preferred_seen->find(qr.to_fen()) == preferred_seen->end()) {
                    all_in = false;
                    break;
                }
            }
            if (all_in) tier = 1;
        }

        std::string mstr = moves[i].to_string();
        bool better = false;
        if (!found) {
            better = true;
        } else if (tier != best_tier) {
            better = (tier < best_tier);
        } else if (q_tb_sz != best_tb_size) {
            better = (q_tb_sz < best_tb_size);
        } else if (nr != best_replies) {
            better = (nr < best_replies);
        } else {
            better = (mstr < best_str);
        }

        if (better) {
            found = true;
            best = moves[i];
            best_tier = tier;
            best_tb_size = q_tb_sz;
            best_replies = nr;
            best_str = std::move(mstr);
        }
    }

    if (!found) return false;
    out_move = best;
    return true;
}

} // namespace msolve
