#include "attacks.hpp"
#include <cstdlib>

namespace mchess {

namespace {

uint64_t splitmix64(uint64_t& state) {
    uint64_t z = (state += 0x9e3779b97f4a7c15ULL);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

Tables build_tables() {
    Tables t;

    static constexpr int df[8] = { 0, 1,  1, -1,  0, -1,  1, -1};
    static constexpr int dr[8] = { 1, 0,  1,  1, -1,  0, -1, -1};

    static constexpr int kdf[8] = {-2, -2, -1, -1,  1,  1,  2,  2};
    static constexpr int kdr[8] = {-1,  1, -2,  2, -2,  2, -1,  1};

    for (int sq = 0; sq < 64; ++sq) {
        int f = sq_file(sq);
        int r = sq_rank(sq);

        // Knight attacks
        for (int i = 0; i < 8; ++i) {
            int nf = f + kdf[i];
            int nr = r + kdr[i];
            if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
                t.knight_att[sq] |= sq_bb(make_sq(nf, nr));
            }
        }

        // King attacks and rays
        for (int d = 0; d < 8; ++d) {
            int nf = f + df[d];
            int nr = r + dr[d];
            if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
                t.king_att[sq] |= sq_bb(make_sq(nf, nr));
            }
            while (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
                t.ray[d][sq] |= sq_bb(make_sq(nf, nr));
                nf += df[d];
                nr += dr[d];
            }
        }

        // Pawn attacks
        if (r + 1 < 8) {
            if (f - 1 >= 0) t.pawn_att[WHITE][sq] |= sq_bb(make_sq(f - 1, r + 1));
            if (f + 1 < 8)  t.pawn_att[WHITE][sq] |= sq_bb(make_sq(f + 1, r + 1));
        }
        if (r - 1 >= 0) {
            if (f - 1 >= 0) t.pawn_att[BLACK][sq] |= sq_bb(make_sq(f - 1, r - 1));
            if (f + 1 < 8)  t.pawn_att[BLACK][sq] |= sq_bb(make_sq(f + 1, r - 1));
        }

        t.castling_mask[sq] = WK_CASTLE | WQ_CASTLE | BK_CASTLE | BQ_CASTLE;
    }

    t.castling_mask[make_sq(0, 0)] &= ~WQ_CASTLE;
    t.castling_mask[make_sq(4, 0)] &= ~(WK_CASTLE | WQ_CASTLE);
    t.castling_mask[make_sq(7, 0)] &= ~WK_CASTLE;
    t.castling_mask[make_sq(0, 7)] &= ~BQ_CASTLE;
    t.castling_mask[make_sq(4, 7)] &= ~(BK_CASTLE | BQ_CASTLE);
    t.castling_mask[make_sq(7, 7)] &= ~BK_CASTLE;

    // Between and line tables
    for (int s1 = 0; s1 < 64; ++s1) {
        for (int s2 = 0; s2 < 64; ++s2) {
            if (s1 == s2) continue;
            int f1 = sq_file(s1), r1 = sq_rank(s1);
            int f2 = sq_file(s2), r2 = sq_rank(s2);
            int df_val = f2 - f1;
            int dr_val = r2 - r1;

            int step_f = (df_val > 0) ? 1 : (df_val < 0 ? -1 : 0);
            int step_r = (dr_val > 0) ? 1 : (dr_val < 0 ? -1 : 0);

            bool ortho = (df_val == 0 || dr_val == 0);
            bool diag  = (std::abs(df_val) == std::abs(dr_val));
            if (!ortho && !diag) continue;

            // Between (exclusive)
            int cf = f1 + step_f;
            int cr = r1 + step_r;
            while (cf != f2 || cr != r2) {
                t.between[s1][s2] |= sq_bb(make_sq(cf, cr));
                cf += step_f;
                cr += step_r;
            }

            // Full line
            uint64_t l = sq_bb(s1) | sq_bb(s2);
            for (int dir_sign : {-1, 1}) {
                cf = f1 + dir_sign * step_f;
                cr = r1 + dir_sign * step_r;
                while (cf >= 0 && cf < 8 && cr >= 0 && cr < 8) {
                    l |= sq_bb(make_sq(cf, cr));
                    cf += dir_sign * step_f;
                    cr += dir_sign * step_r;
                }
            }
            t.line[s1][s2] = l;
        }
    }

    // Zobrist keys (fixed deterministic seed)
    uint64_t seed = 0x517cc1b727220a95ULL;
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            for (int sq = 0; sq < 64; ++sq) {
                t.z_piece[c][pt][sq] = splitmix64(seed);
            }
        }
    }
    t.z_stm = splitmix64(seed);
    for (int i = 0; i < 16; ++i) {
        t.z_castling[i] = (i == 0) ? 0ULL : splitmix64(seed);
    }
    for (int sq = 0; sq < 64; ++sq) {
        t.z_ep[sq] = splitmix64(seed);
    }
    for (int w = 0; w <= 8; ++w) {
        for (int h = 0; h <= 8; ++h) {
            t.z_dims[w][h] = splitmix64(seed);
        }
    }

    return t;
}

} // namespace

const Tables& tables() {
    static const Tables t = build_tables();
    return t;
}

} // namespace mchess
