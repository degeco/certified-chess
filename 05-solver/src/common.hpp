#pragma once

#include "mchess.hpp"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <string>
#include <string_view>

namespace msolve {

using namespace mchess;

enum class ClaimKind : uint8_t {
    WIN = 0,
    ATLEAST_DRAW = 1
};

struct Claim {
    ClaimKind kind = ClaimKind::WIN;
    Color prover = WHITE;

    std::string to_string() const {
        std::string s = (kind == ClaimKind::WIN) ? "WIN " : "ATLEAST_DRAW ";
        s.push_back(prover == WHITE ? 'w' : 'b');
        return s;
    }
};

enum class SolveStatus : uint8_t {
    PROVED = 0,
    DISPROVED = 1,
    LIMIT = 2,
    ERROR = 3
};

inline const char* status_to_string(SolveStatus st) {
    switch (st) {
        case SolveStatus::PROVED:    return "PROVED";
        case SolveStatus::DISPROVED: return "DISPROVED";
        case SolveStatus::LIMIT:     return "LIMIT";
        case SolveStatus::ERROR:     return "ERROR";
    }
    return "UNKNOWN";
}

struct SolveLimits {
    uint64_t max_nodes = 20000000ULL;
    double max_seconds = 60.0;
    size_t tt_mb = 256;
    bool minimize = true;
    bool verbose = false;
};

struct SolveStats {
    uint64_t nodes = 0;
    double seconds = 0.0;
    size_t raw_entries = 0;
    size_t pruned_entries = 0;
    size_t min_entries = 0;
    uint32_t max_rank = 0;
    std::string note;
};

class Timer {
public:
    Timer() : t0_(std::chrono::steady_clock::now()) {}
    double elapsed() const {
        auto now = std::chrono::steady_clock::now();
        return std::chrono::duration<double>(now - t0_).count();
    }
private:
    std::chrono::steady_clock::time_point t0_;
};

inline uint16_t pack_move(Move m) {
    uint16_t promo_bits = (m.promo == NO_PIECE) ? 0 : static_cast<uint16_t>(m.promo);
    return static_cast<uint16_t>(
        (static_cast<uint16_t>(m.from & 63)) |
        (static_cast<uint16_t>(m.to & 63) << 6) |
        (promo_bits << 12) |
        (1U << 15)
    );
}

inline Move unpack_move(uint16_t packed) {
    Move m;
    m.from = static_cast<uint8_t>(packed & 63);
    m.to = static_cast<uint8_t>((packed >> 6) & 63);
    uint8_t p = static_cast<uint8_t>((packed >> 12) & 7);
    m.promo = (p == 0) ? NO_PIECE : static_cast<PieceType>(p);
    return m;
}

inline bool is_prover_stalemate(const Position& pos, Color prover) {
    return pos.side_to_move() == prover && !pos.in_check() && !pos.has_legal_moves();
}

inline int piece_value(PieceType pt) {
    switch (pt) {
        case PAWN:   return 100;
        case KNIGHT: return 320;
        case BISHOP: return 330;
        case ROOK:   return 500;
        case QUEEN:  return 900;
        default:     return 0;
    }
}

// Fast heuristic evaluation from `prover`'s perspective (centipawns).
inline int eval_position(const Position& pos, Color prover) {
    auto pop = [](uint64_t b) -> int { return __builtin_popcountll(b); };
    int score = 0;
    Color opp = ~prover;
    score += 100 * (pop(pos.pieces(prover, PAWN))   - pop(pos.pieces(opp, PAWN)));
    score += 320 * (pop(pos.pieces(prover, KNIGHT)) - pop(pos.pieces(opp, KNIGHT)));
    score += 330 * (pop(pos.pieces(prover, BISHOP)) - pop(pos.pieces(opp, BISHOP)));
    score += 500 * (pop(pos.pieces(prover, ROOK))   - pop(pos.pieces(opp, ROOK)));
    score += 900 * (pop(pos.pieces(prover, QUEEN))  - pop(pos.pieces(opp, QUEEN)));

    // Pawn advancement bonus (scaled to board height)
    int h = pos.height();
    uint64_t wp = pos.pieces(WHITE, PAWN);
    int w_adv = 0;
    while (wp) {
        int sq = __builtin_ctzll(wp);
        wp &= wp - 1;
        int r = sq_rank(sq);
        w_adv += (r * 20) / std::max(1, h - 2);
    }
    uint64_t bp = pos.pieces(BLACK, PAWN);
    int b_adv = 0;
    while (bp) {
        int sq = __builtin_ctzll(bp);
        bp &= bp - 1;
        int r = (h - 1) - sq_rank(sq);
        b_adv += (r * 20) / std::max(1, h - 2);
    }
    score += (prover == WHITE) ? (w_adv - b_adv) : (b_adv - w_adv);

    // Small check bonus/penalty
    if (pos.in_check()) {
        score += (pos.side_to_move() == prover) ? -35 : 35;
    }
    return score;
}

// Move ordering score for tactical priority (higher = search earlier).
inline int move_order_score(const Position& pos, Move m) {
    int s = 0;
    Color cap_c = WHITE;
    PieceType cap = pos.piece_at(m.to, &cap_c);
    if (cap != NO_PIECE) {
        PieceType mover = pos.piece_at(m.from);
        s += 10 * piece_value(cap) - piece_value(mover) + 1000;
    }
    if (m.promo != NO_PIECE) {
        s += 800 + piece_value(m.promo);
    }
    return s;
}

} // namespace msolve
