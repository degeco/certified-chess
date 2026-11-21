#pragma once

#include "mchess.hpp"
#include <array>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace complexity {

struct MaterialBudget {
    int p = 0;
    int n = 0;
    int b = 0;
    int r = 0;
    int q = 0;

    int non_king_total() const { return p + n + b + r + q; }
};

struct BoardSpec {
    std::string name;
    int w = 0;
    int h = 0;
    bool is_8x8 = false;
    std::string start_fen;
    MaterialBudget white_init;
    MaterialBudget black_init;
};

inline MaterialBudget budget_from_position(const mchess::Position& pos, mchess::Color c) {
    MaterialBudget mb;
    mb.p = mchess::popcount(pos.pieces(c, mchess::PAWN));
    mb.n = mchess::popcount(pos.pieces(c, mchess::KNIGHT));
    mb.b = mchess::popcount(pos.pieces(c, mchess::BISHOP));
    mb.r = mchess::popcount(pos.pieces(c, mchess::ROOK));
    mb.q = mchess::popcount(pos.pieces(c, mchess::QUEEN));
    return mb;
}

inline BoardSpec make_spec_from_fen(const std::string& name, const std::string& fen) {
    auto pos = mchess::Position::from_fen(fen);
    BoardSpec s;
    s.name = name;
    s.start_fen = fen;
    if (pos) {
        s.w = pos->width();
        s.h = pos->height();
        s.is_8x8 = pos->is_8x8();
        s.white_init = budget_from_position(*pos, mchess::WHITE);
        s.black_init = budget_from_position(*pos, mchess::BLACK);
    }
    return s;
}

inline std::vector<BoardSpec> builtin_specs() {
    return {
        make_spec_from_fen("mini3x3", "rkr/3/RKR w - -"),
        make_spec_from_fen("mini3x3_p", "k1r/P1p/R1K w - -"),
        make_spec_from_fen("mini4x4", "rqkr/pppp/PPPP/RQKR w - -"),
        make_spec_from_fen("mini4x5", "rqkr/pppp/4/PPPP/RQKR w - -"),
        make_spec_from_fen("mini5x5", "rnbqk/ppppp/5/PPPPP/RNBQK w - -"),
        make_spec_from_fen("losalamos6x6", "rnqknr/pppppp/6/6/PPPPPP/RNQKNR w - -"),
        make_spec_from_fen("std6x6", "rnbqkr/pppppp/6/6/PPPPPP/RNBQKR w - -"),
        make_spec_from_fen("std8", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"),
    };
}

inline bool find_spec(const std::string& name_or_fen, BoardSpec& out) {
    for (const auto& s : builtin_specs()) {
        if (s.name == name_or_fen) {
            out = s;
            return true;
        }
    }
    auto pos = mchess::Position::from_fen(name_or_fen);
    if (!pos) return false;
    out = make_spec_from_fen("custom", name_or_fen);
    return true;
}

inline uint8_t encode_cell(mchess::PieceType pt, mchess::Color c) {
    if (pt == mchess::NO_PIECE) return 0;
    return static_cast<uint8_t>(1 + static_cast<int>(c) * 6 + static_cast<int>(pt));
}

inline char cell_to_fen_char(uint8_t code) {
    static constexpr char kMap[] = ".PNBRQKpnbrqk";
    return kMap[code];
}

// Formats a canonical 4-field FEN from dense board codes [0..w*h-1] (row-major r*w + f).
inline std::string codes_to_fen(const uint8_t* codes, int w, int h, mchess::Color stm,
                                uint8_t castling = 0, int ep_sq = mchess::NO_SQ) {
    std::string s;
    s.reserve(96);
    for (int r = h - 1; r >= 0; --r) {
        int empty = 0;
        for (int f = 0; f < w; ++f) {
            uint8_t code = codes[r * w + f];
            if (code == 0) {
                ++empty;
            } else {
                if (empty > 0) {
                    s.push_back(static_cast<char>('0' + empty));
                    empty = 0;
                }
                s.push_back(cell_to_fen_char(code));
            }
        }
        if (empty > 0) s.push_back(static_cast<char>('0' + empty));
        if (r > 0) s.push_back('/');
    }
    s.push_back(' ');
    s.push_back(stm == mchess::WHITE ? 'w' : 'b');
    s.push_back(' ');
    if (castling == 0) {
        s.push_back('-');
    } else {
        if (castling & mchess::WK_CASTLE) s.push_back('K');
        if (castling & mchess::WQ_CASTLE) s.push_back('Q');
        if (castling & mchess::BK_CASTLE) s.push_back('k');
        if (castling & mchess::BQ_CASTLE) s.push_back('q');
    }
    s.push_back(' ');
    if (ep_sq == mchess::NO_SQ) {
        s.push_back('-');
    } else {
        s += mchess::sq_to_string(ep_sq);
    }
    return s;
}

inline uint64_t splitmix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

inline bool kings_adjacent(int sq1, int sq2) {
    int df = mchess::sq_file(sq1) - mchess::sq_file(sq2);
    int dr = mchess::sq_rank(sq1) - mchess::sq_rank(sq2);
    return (df >= -1 && df <= 1 && dr >= -1 && dr <= 1);
}

} // namespace complexity
