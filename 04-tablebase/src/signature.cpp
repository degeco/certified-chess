#include "signature.hpp"
#include <algorithm>
#include <set>

namespace tb {

namespace {

constexpr mchess::PieceType SIG_ORDER[5] = {
    mchess::QUEEN, mchess::ROOK, mchess::BISHOP, mchess::KNIGHT, mchess::PAWN
};

char pt_upper(mchess::PieceType pt) {
    switch (pt) {
        case mchess::QUEEN:  return 'Q';
        case mchess::ROOK:   return 'R';
        case mchess::BISHOP: return 'B';
        case mchess::KNIGHT: return 'N';
        case mchess::PAWN:   return 'P';
        case mchess::KING:   return 'K';
        default:             return '?';
    }
}

std::optional<mchess::PieceType> parse_non_king(char ch) {
    switch (ch) {
        case 'Q': case 'q': return mchess::QUEEN;
        case 'R': case 'r': return mchess::ROOK;
        case 'B': case 'b': return mchess::BISHOP;
        case 'N': case 'n': return mchess::KNIGHT;
        case 'P': case 'p': return mchess::PAWN;
        default: return std::nullopt;
    }
}

} // namespace

std::optional<MaterialSig> MaterialSig::parse(std::string_view s) {
    if (s.size() < 2 || (s[0] != 'K' && s[0] != 'k')) return std::nullopt;

    MaterialSig sig;
    sig.count[mchess::WHITE][mchess::KING] = 1;
    sig.count[mchess::BLACK][mchess::KING] = 1;

    size_t i = 1;
    bool seen_black_k = false;
    while (i < s.size()) {
        char ch = s[i++];
        if (ch == 'K' || ch == 'k') {
            if (seen_black_k) return std::nullopt;
            seen_black_k = true;
            continue;
        }
        auto pt = parse_non_king(ch);
        if (!pt) return std::nullopt;
        mchess::Color c = seen_black_k ? mchess::BLACK : mchess::WHITE;
        if (sig.count[c][*pt] == 63) return std::nullopt;
        ++sig.count[c][*pt];
    }

    if (!seen_black_k) return std::nullopt;
    return sig;
}

MaterialSig MaterialSig::from_position(const mchess::Position& pos) {
    MaterialSig sig;
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            sig.count[c][pt] = static_cast<uint8_t>(
                mchess::popcount(pos.pieces(static_cast<mchess::Color>(c),
                                            static_cast<mchess::PieceType>(pt))));
        }
    }
    return sig;
}

std::string MaterialSig::to_string() const {
    std::string out;
    out.push_back('K');
    for (mchess::PieceType pt : SIG_ORDER) {
        for (uint8_t i = 0; i < count[mchess::WHITE][pt]; ++i) {
            out.push_back(pt_upper(pt));
        }
    }
    out.push_back('K');
    for (mchess::PieceType pt : SIG_ORDER) {
        for (uint8_t i = 0; i < count[mchess::BLACK][pt]; ++i) {
            out.push_back(pt_upper(pt));
        }
    }
    return out;
}

int MaterialSig::total_pieces() const {
    int n = 0;
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) n += count[c][pt];
    }
    return n;
}

int MaterialSig::total_pawns() const {
    return count[mchess::WHITE][mchess::PAWN] + count[mchess::BLACK][mchess::PAWN];
}

bool MaterialSig::operator<(const MaterialSig& o) const {
    int tp1 = total_pieces(), tp2 = o.total_pieces();
    if (tp1 != tp2) return tp1 < tp2;
    int pw1 = total_pawns(), pw2 = o.total_pawns();
    if (pw1 != pw2) return pw1 < pw2;
    return count < o.count;
}

std::vector<MaterialSig> MaterialSig::dependencies() const {
    std::set<MaterialSig> deps;

    // 1. Simple capture of any non-king piece of either color.
    for (int c = 0; c < 2; ++c) {
        for (mchess::PieceType pt : SIG_ORDER) {
            if (count[c][pt] > 0) {
                MaterialSig child = *this;
                --child.count[c][pt];
                deps.insert(child);
            }
        }
    }

    // 2. Promotion (and capture + promotion) for any pawn of either color.
    constexpr mchess::PieceType PROMOS[4] = {
        mchess::QUEEN, mchess::ROOK, mchess::BISHOP, mchess::KNIGHT
    };
    for (int c = 0; c < 2; ++c) {
        if (count[c][mchess::PAWN] == 0) continue;
        int enemy = c ^ 1;
        for (mchess::PieceType pr : PROMOS) {
            // Quiet promotion
            MaterialSig p_child = *this;
            --p_child.count[c][mchess::PAWN];
            ++p_child.count[c][pr];
            deps.insert(p_child);

            // Capture + promotion of any enemy non-king piece
            for (mchess::PieceType cap : SIG_ORDER) {
                if (count[enemy][cap] > 0) {
                    MaterialSig cp_child = p_child;
                    --cp_child.count[enemy][cap];
                    deps.insert(cp_child);
                }
            }
        }
    }

    return std::vector<MaterialSig>(deps.begin(), deps.end());
}

std::vector<MaterialSig> enumerate_signatures(int max_pieces) {
    std::set<MaterialSig> sigs;
    MaterialSig base;
    base.count[mchess::WHITE][mchess::KING] = 1;
    base.count[mchess::BLACK][mchess::KING] = 1;
    sigs.insert(base);

    // Build iteratively up to max_pieces non-king pieces = max_pieces - 2.
    int max_extra = max_pieces - 2;
    for (int k = 0; k < max_extra; ++k) {
        std::vector<MaterialSig> current(sigs.begin(), sigs.end());
        for (const auto& s : current) {
            if (s.total_pieces() != 2 + k) continue;
            for (int c = 0; c < 2; ++c) {
                for (mchess::PieceType pt : SIG_ORDER) {
                    MaterialSig nxt = s;
                    ++nxt.count[c][pt];
                    sigs.insert(nxt);
                }
            }
        }
    }

    return std::vector<MaterialSig>(sigs.begin(), sigs.end());
}

bool parse_board_size(std::string_view s, int& w, int& h) {
    size_t x = s.find('x');
    if (x == std::string_view::npos || x == 0 || x + 1 >= s.size()) return false;
    auto parse_dim = [](std::string_view sv) -> int {
        if (sv.size() != 1) return -1;
        char c = sv[0];
        if (c < '3' || c > '8') return -1;
        return c - '0';
    };
    int tw = parse_dim(s.substr(0, x));
    int th = parse_dim(s.substr(x + 1));
    if (tw < 3 || th < 3) return false;
    w = tw;
    h = th;
    return true;
}

} // namespace tb
