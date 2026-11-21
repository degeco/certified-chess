#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace mchess {

enum Color : uint8_t {
    WHITE = 0,
    BLACK = 1
};

inline constexpr Color operator~(Color c) {
    return static_cast<Color>(c ^ 1);
}

enum PieceType : uint8_t {
    PAWN = 0,
    KNIGHT = 1,
    BISHOP = 2,
    ROOK = 3,
    QUEEN = 4,
    KING = 5,
    NO_PIECE = 6
};

enum CastlingRight : uint8_t {
    WK_CASTLE = 1 << 0,
    WQ_CASTLE = 1 << 1,
    BK_CASTLE = 1 << 2,
    BQ_CASTLE = 1 << 3
};

constexpr int NO_SQ = -1;
constexpr int MAX_MOVES = 256;

inline constexpr int make_sq(int file, int rank) {
    return (rank << 3) | file;
}

inline constexpr int sq_file(int sq) {
    return sq & 7;
}

inline constexpr int sq_rank(int sq) {
    return sq >> 3;
}

inline constexpr uint64_t sq_bb(int sq) {
    return 1ULL << sq;
}

inline std::string sq_to_string(int sq) {
    std::string s(2, ' ');
    s[0] = static_cast<char>('a' + sq_file(sq));
    s[1] = static_cast<char>('1' + sq_rank(sq));
    return s;
}

inline int parse_sq(std::string_view sv, int w, int h) {
    if (sv.size() != 2) return NO_SQ;
    int f = sv[0] - 'a';
    int r = sv[1] - '1';
    if (f < 0 || f >= w || r < 0 || r >= h) return NO_SQ;
    return make_sq(f, r);
}

inline char piece_to_char(Color c, PieceType pt) {
    static constexpr char W_CHARS[] = "PNBRQK";
    static constexpr char B_CHARS[] = "pnbrqk";
    if (pt >= NO_PIECE) return '?';
    return (c == WHITE) ? W_CHARS[pt] : B_CHARS[pt];
}

inline char promo_to_char(PieceType pt) {
    switch (pt) {
        case KNIGHT: return 'n';
        case BISHOP: return 'b';
        case ROOK:   return 'r';
        case QUEEN:  return 'q';
        default:     return '\0';
    }
}

struct Move {
    uint8_t from = 0;
    uint8_t to = 0;
    PieceType promo = NO_PIECE;

    bool operator==(const Move& o) const {
        return from == o.from && to == o.to && promo == o.promo;
    }

    bool operator!=(const Move& o) const {
        return !(*this == o);
    }

    std::string to_string() const {
        std::string s;
        s.reserve(5);
        s.push_back(static_cast<char>('a' + sq_file(from)));
        s.push_back(static_cast<char>('1' + sq_rank(from)));
        s.push_back(static_cast<char>('a' + sq_file(to)));
        s.push_back(static_cast<char>('1' + sq_rank(to)));
        if (promo != NO_PIECE) {
            s.push_back(promo_to_char(promo));
        }
        return s;
    }
};

} // namespace mchess
