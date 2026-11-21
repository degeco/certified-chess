#pragma once

#include "types.hpp"
#include <cstdint>

namespace mchess {

enum Dir : int {
    DIR_N  = 0, // +8
    DIR_E  = 1, // +1
    DIR_NE = 2, // +9
    DIR_NW = 3, // +7
    DIR_S  = 4, // -8
    DIR_W  = 5, // -1
    DIR_SE = 6, // -7
    DIR_SW = 7  // -9
};

struct Tables {
    uint64_t knight_att[64]{};
    uint64_t king_att[64]{};
    uint64_t pawn_att[2][64]{};
    uint64_t ray[8][64]{};
    uint64_t between[64][64]{};
    uint64_t line[64][64]{};
    uint8_t castling_mask[64]{};

    uint64_t z_piece[2][6][64]{};
    uint64_t z_stm = 0;
    uint64_t z_castling[16]{};
    uint64_t z_ep[64]{};
    uint64_t z_dims[9][9]{};
};

const Tables& tables();

inline int lsb(uint64_t bb) {
    return __builtin_ctzll(bb);
}

inline int msb(uint64_t bb) {
    return 63 - __builtin_clzll(bb);
}

inline int pop_lsb(uint64_t& bb) {
    int sq = lsb(bb);
    bb &= bb - 1;
    return sq;
}

inline int popcount(uint64_t bb) {
    return __builtin_popcountll(bb);
}

inline uint64_t ray_pos(const Tables& t, int dir, int sq, uint64_t occ, uint64_t board_mask) {
    uint64_t r = t.ray[dir][sq] & board_mask;
    uint64_t b = r & occ;
    if (b) {
        int blocker = lsb(b);
        r ^= (t.ray[dir][blocker] & board_mask);
    }
    return r;
}

inline uint64_t ray_neg(const Tables& t, int dir, int sq, uint64_t occ, uint64_t board_mask) {
    uint64_t r = t.ray[dir][sq] & board_mask;
    uint64_t b = r & occ;
    if (b) {
        int blocker = msb(b);
        r ^= (t.ray[dir][blocker] & board_mask);
    }
    return r;
}

inline uint64_t bishop_attacks(int sq, uint64_t occ, uint64_t board_mask) {
    const Tables& t = tables();
    return ray_pos(t, DIR_NE, sq, occ, board_mask)
         | ray_pos(t, DIR_NW, sq, occ, board_mask)
         | ray_neg(t, DIR_SE, sq, occ, board_mask)
         | ray_neg(t, DIR_SW, sq, occ, board_mask);
}

inline uint64_t rook_attacks(int sq, uint64_t occ, uint64_t board_mask) {
    const Tables& t = tables();
    return ray_pos(t, DIR_N, sq, occ, board_mask)
         | ray_pos(t, DIR_E, sq, occ, board_mask)
         | ray_neg(t, DIR_S, sq, occ, board_mask)
         | ray_neg(t, DIR_W, sq, occ, board_mask);
}

inline uint64_t queen_attacks(int sq, uint64_t occ, uint64_t board_mask) {
    return bishop_attacks(sq, occ, board_mask) | rook_attacks(sq, occ, board_mask);
}

inline uint64_t make_board_mask(int w, int h) {
    uint64_t m = 0;
    for (int r = 0; r < h; ++r) {
        for (int f = 0; f < w; ++f) {
            m |= sq_bb(make_sq(f, r));
        }
    }
    return m;
}

} // namespace mchess
