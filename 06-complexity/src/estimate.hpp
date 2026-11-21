#pragma once

#include "common.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <random>
#include <string>
#include <utility>
#include <vector>

namespace complexity {

struct MaterialEntry {
    uint8_t n = 0;
    uint8_t b = 0;
    uint8_t r = 0;
    uint8_t q = 0;
    long double inv_fact = 0.0L;
    long double cum_inv_fact = 0.0L;
};

struct MaterialBucket {
    std::vector<MaterialEntry> entries;
    long double total_inv_fact = 0.0L;
};

struct SamplingBucket {
    int pw = 0;
    int uw = 0;
    int pb = 0;
    int ub = 0;
    int a = 0;
    long double weight = 0.0L;
    long double cum_weight = 0.0L;
};

struct EstimateResult {
    std::string name;
    int width = 0;
    int height = 0;
    bool is_8x8 = false;
    uint64_t samples = 0;
    uint64_t seed = 0;
    long double superset_size = 0.0L;   // |U|
    uint64_t accepted_base = 0;         // samples where F(X) > 0
    long double mean_F = 0.0L;
    long double se_F = 0.0L;
    long double estimate = 0.0L;        // |L_hat|
    long double se_estimate = 0.0L;
    long double ci95_low = 0.0L;
    long double ci95_high = 0.0L;
    double rel_ci95_pct = 0.0;
    double elapsed_sec = 0.0;
};

class StaticSpaceSampler {
public:
    explicit StaticSpaceSampler(const BoardSpec& spec) : spec_(spec) {
        w_ = spec.w;
        h_ = spec.h;
        S_ = w_ * h_;
        S_p_ = w_ * (h_ - 2);

        fact_[0] = 1.0L;
        for (int i = 1; i <= 64; ++i) {
            fact_[i] = fact_[i - 1] * static_cast<long double>(i);
        }

        // Non-adjacent king pairs classified by a = #kings on pawn-eligible ranks [1..h-2].
        for (int kw_idx = 0; kw_idx < S_; ++kw_idx) {
            int kw_r = kw_idx / w_;
            int kw_f = kw_idx % w_;
            int kw_sq = mchess::make_sq(kw_f, kw_r);
            int kw_pr = (kw_r >= 1 && kw_r <= h_ - 2) ? 1 : 0;
            for (int kb_idx = 0; kb_idx < S_; ++kb_idx) {
                if (kw_idx == kb_idx) continue;
                int kb_r = kb_idx / w_;
                int kb_f = kb_idx % w_;
                int kb_sq = mchess::make_sq(kb_f, kb_r);
                if (kings_adjacent(kw_sq, kb_sq)) continue;
                int kb_pr = (kb_r >= 1 && kb_r <= h_ - 2) ? 1 : 0;
                kings_by_a_[kw_pr + kb_pr].push_back({kw_idx, kb_idx});
            }
        }

        build_side_buckets(spec_.white_init, buckets_w_);
        build_side_buckets(spec_.black_init, buckets_b_);

        // Build joint (pw, uw, pb, ub, a) buckets.
        int max_pw = spec_.white_init.p;
        int max_pb = spec_.black_init.p;
        int max_uw = spec_.white_init.non_king_total();
        int max_ub = spec_.black_init.non_king_total();

        long double running = 0.0L;
        for (int pw = 0; pw <= max_pw; ++pw) {
            for (int uw = 0; uw <= max_uw; ++uw) {
                const auto& bw = buckets_w_[pw][uw];
                if (bw.entries.empty()) continue;
                for (int pb = 0; pb <= max_pb; ++pb) {
                    for (int ub = 0; ub <= max_ub; ++ub) {
                        const auto& bb = buckets_b_[pb][ub];
                        if (bb.entries.empty()) continue;
                        if (2 + pw + uw + pb + ub > S_) continue;
                        int S_rem = S_ - 2 - pw - pb;
                        long double piece_ways = fact_[S_rem] / fact_[S_rem - uw - ub];

                        for (int a = 0; a <= 2; ++a) {
                            uint64_t Ka = kings_by_a_[a].size();
                            if (Ka == 0) continue;
                            if (pw + pb > S_p_ - a) continue;
                            long double pawn_ways =
                                fact_[S_p_ - a] /
                                (fact_[pw] * fact_[pb] * fact_[S_p_ - a - pw - pb]);
                            long double w = 2.0L * static_cast<long double>(Ka) * pawn_ways *
                                            piece_ways * bw.total_inv_fact * bb.total_inv_fact;
                            if (w <= 0.0L) continue;
                            running += w;
                            buckets_.push_back({pw, uw, pb, ub, a, w, running});
                        }
                    }
                }
            }
        }
        U_total_ = running;
    }

    long double superset_size() const { return U_total_; }

    EstimateResult run(uint64_t num_samples, uint64_t seed) const {
        using clock = std::chrono::steady_clock;
        auto t0 = clock::now();

        EstimateResult res;
        res.name = spec_.name;
        res.width = w_;
        res.height = h_;
        res.is_8x8 = spec_.is_8x8;
        res.samples = num_samples;
        res.seed = seed;
        res.superset_size = U_total_;

        if (num_samples == 0 || U_total_ <= 0.0L) {
            res.elapsed_sec = std::chrono::duration<double>(clock::now() - t0).count();
            return res;
        }

        std::mt19937_64 rng(seed);
        long double mean = 0.0L;
        long double m2 = 0.0L;
        uint64_t accepted = 0;

        for (uint64_t i = 0; i < num_samples; ++i) {
            long double f_val = sample_once(rng);
            if (f_val > 0.0L) ++accepted;
            long double delta = f_val - mean;
            mean += delta / static_cast<long double>(i + 1);
            long double delta2 = f_val - mean;
            m2 += delta * delta2;
        }

        long double var = (num_samples > 1) ? (m2 / static_cast<long double>(num_samples - 1)) : 0.0L;
        long double se_F = std::sqrt(var / static_cast<long double>(num_samples));
        long double est = U_total_ * mean;
        long double se_est = U_total_ * se_F;
        long double margin = 1.959963984540054L * se_est;

        res.accepted_base = accepted;
        res.mean_F = mean;
        res.se_F = se_F;
        res.estimate = est;
        res.se_estimate = se_est;
        res.ci95_low = (est > margin) ? (est - margin) : 0.0L;
        res.ci95_high = est + margin;
        res.rel_ci95_pct = (est > 0.0L) ? static_cast<double>(100.0L * margin / est) : 0.0;
        res.elapsed_sec = std::chrono::duration<double>(clock::now() - t0).count();
        return res;
    }

private:
    static constexpr int MAX_P = 8;
    static constexpr int MAX_U = 16;

    void build_side_buckets(const MaterialBudget& init,
                            std::array<std::array<MaterialBucket, MAX_U + 1>, MAX_P + 1>& out) {
        for (int p = 0; p <= init.p; ++p) {
            int promo_avail = init.p - p;
            for (int n = 0; n <= init.n + promo_avail; ++n) {
                int ex_n = std::max(0, n - init.n);
                for (int b = 0; b <= init.b + promo_avail - ex_n; ++b) {
                    int ex_b = std::max(0, b - init.b);
                    for (int r = 0; r <= init.r + promo_avail - ex_n - ex_b; ++r) {
                        int ex_r = std::max(0, r - init.r);
                        for (int q = 0; q <= init.q + promo_avail - ex_n - ex_b - ex_r; ++q) {
                            int u = n + b + r + q;
                            if (1 + p + u > S_ - 1) continue;
                            long double inv_f = 1.0L / (fact_[n] * fact_[b] * fact_[r] * fact_[q]);
                            auto& bucket = out[p][u];
                            bucket.total_inv_fact += inv_f;
                            bucket.entries.push_back({static_cast<uint8_t>(n),
                                                      static_cast<uint8_t>(b),
                                                      static_cast<uint8_t>(r),
                                                      static_cast<uint8_t>(q),
                                                      inv_f,
                                                      bucket.total_inv_fact});
                        }
                    }
                }
            }
        }
    }

    static long double uniform_ld(std::mt19937_64& rng, long double upper) {
        std::uniform_real_distribution<long double> dist(0.0L, upper);
        return dist(rng);
    }

    static const MaterialEntry& sample_material(const MaterialBucket& bucket, std::mt19937_64& rng) {
        if (bucket.entries.size() == 1) return bucket.entries[0];
        long double u = uniform_ld(rng, bucket.total_inv_fact);
        auto it = std::lower_bound(
            bucket.entries.begin(), bucket.entries.end(), u,
            [](const MaterialEntry& e, long double val) { return e.cum_inv_fact < val; });
        if (it == bucket.entries.end()) return bucket.entries.back();
        return *it;
    }

    long double sample_once(std::mt19937_64& rng) const {
        long double u = uniform_ld(rng, U_total_);
        auto it = std::lower_bound(
            buckets_.begin(), buckets_.end(), u,
            [](const SamplingBucket& b, long double val) { return b.cum_weight < val; });
        const SamplingBucket& b = (it == buckets_.end()) ? buckets_.back() : *it;

        const MaterialEntry& mw = sample_material(buckets_w_[b.pw][b.uw], rng);
        const MaterialEntry& mb = sample_material(buckets_b_[b.pb][b.ub], rng);

        const auto& kpairs = kings_by_a_[b.a];
        std::uniform_int_distribution<size_t> kdist(0, kpairs.size() - 1);
        auto [kw_idx, kb_idx] = kpairs[kdist(rng)];

        uint8_t codes[64]{};
        codes[kw_idx] = encode_cell(mchess::KING, mchess::WHITE);
        codes[kb_idx] = encode_cell(mchess::KING, mchess::BLACK);

        // Place pawns on remaining pawn-eligible squares (ranks 1 .. h-2).
        if (b.pw + b.pb > 0) {
            int pawn_sqs[64];
            int np = 0;
            for (int r = 1; r <= h_ - 2; ++r) {
                for (int f = 0; f < w_; ++f) {
                    int idx = r * w_ + f;
                    if (codes[idx] == 0) pawn_sqs[np++] = idx;
                }
            }
            int need_p = b.pw + b.pb;
            for (int i = 0; i < need_p; ++i) {
                std::uniform_int_distribution<int> d(i, np - 1);
                std::swap(pawn_sqs[i], pawn_sqs[d(rng)]);
            }
            for (int i = 0; i < b.pw; ++i) {
                codes[pawn_sqs[i]] = encode_cell(mchess::PAWN, mchess::WHITE);
            }
            for (int i = 0; i < b.pb; ++i) {
                codes[pawn_sqs[b.pw + i]] = encode_cell(mchess::PAWN, mchess::BLACK);
            }
        }

        // Place remaining pieces on remaining empty squares.
        int need_u = b.uw + b.ub;
        if (need_u > 0) {
            int rem_sqs[64];
            int nr = 0;
            for (int idx = 0; idx < S_; ++idx) {
                if (codes[idx] == 0) rem_sqs[nr++] = idx;
            }
            for (int i = 0; i < need_u; ++i) {
                std::uniform_int_distribution<int> d(i, nr - 1);
                std::swap(rem_sqs[i], rem_sqs[d(rng)]);
            }
            int pos_i = 0;
            auto place_many = [&](int count, mchess::PieceType pt, mchess::Color c) {
                uint8_t code = encode_cell(pt, c);
                for (int j = 0; j < count; ++j) codes[rem_sqs[pos_i++]] = code;
            };
            place_many(mw.n, mchess::KNIGHT, mchess::WHITE);
            place_many(mw.b, mchess::BISHOP, mchess::WHITE);
            place_many(mw.r, mchess::ROOK, mchess::WHITE);
            place_many(mw.q, mchess::QUEEN, mchess::WHITE);
            place_many(mb.n, mchess::KNIGHT, mchess::BLACK);
            place_many(mb.b, mchess::BISHOP, mchess::BLACK);
            place_many(mb.r, mchess::ROOK, mchess::BLACK);
            place_many(mb.q, mchess::QUEEN, mchess::BLACK);
        }

        mchess::Color stm = (rng() & 1ULL) ? mchess::BLACK : mchess::WHITE;
        return evaluate_position_weight(codes, w_, h_, spec_.is_8x8, stm);
    }

public:
    static long double evaluate_position_weight(const uint8_t* codes, int w, int h, bool is_8x8,
                                                mchess::Color stm) {
        mchess::Position pos;
        std::string base_fen = codes_to_fen(codes, w, h, stm, 0, mchess::NO_SQ);
        if (!mchess::Position::parse(base_fen, pos)) {
            return 0.0L;
        }

        if (!is_8x8) {
            return 1.0L;
        }

        // On 8x8: count exact valid (castling, ep) completions for this (board, stm).
        int castle_bits = 0;
        const uint8_t WK = encode_cell(mchess::KING, mchess::WHITE);
        const uint8_t WR = encode_cell(mchess::ROOK, mchess::WHITE);
        const uint8_t BK = encode_cell(mchess::KING, mchess::BLACK);
        const uint8_t BR = encode_cell(mchess::ROOK, mchess::BLACK);
        if (codes[0 * 8 + 4] == WK && codes[0 * 8 + 7] == WR) ++castle_bits;
        if (codes[0 * 8 + 4] == WK && codes[0 * 8 + 0] == WR) ++castle_bits;
        if (codes[7 * 8 + 4] == BK && codes[7 * 8 + 7] == BR) ++castle_bits;
        if (codes[7 * 8 + 4] == BK && codes[7 * 8 + 0] == BR) ++castle_bits;
        int n_castling = 1 << castle_bits;

        int n_ep = 1; // '-' is always valid
        const uint8_t WP = encode_cell(mchess::PAWN, mchess::WHITE);
        const uint8_t BP = encode_cell(mchess::PAWN, mchess::BLACK);
        if (stm == mchess::WHITE) {
            for (int f = 0; f < 8; ++f) {
                if (codes[5 * 8 + f] == 0 && codes[6 * 8 + f] == 0 && codes[4 * 8 + f] == BP) {
                    bool adj = (f > 0 && codes[4 * 8 + (f - 1)] == WP) ||
                               (f < 7 && codes[4 * 8 + (f + 1)] == WP);
                    if (adj) {
                        int ep_sq = mchess::make_sq(f, 5);
                        mchess::Position tmp;
                        if (mchess::Position::parse(codes_to_fen(codes, 8, 8, stm, 0, ep_sq), tmp) &&
                            tmp.ep_square() == ep_sq) {
                            ++n_ep;
                        }
                    }
                }
            }
        } else {
            for (int f = 0; f < 8; ++f) {
                if (codes[2 * 8 + f] == 0 && codes[1 * 8 + f] == 0 && codes[3 * 8 + f] == WP) {
                    bool adj = (f > 0 && codes[3 * 8 + (f - 1)] == BP) ||
                               (f < 7 && codes[3 * 8 + (f + 1)] == BP);
                    if (adj) {
                        int ep_sq = mchess::make_sq(f, 2);
                        mchess::Position tmp;
                        if (mchess::Position::parse(codes_to_fen(codes, 8, 8, stm, 0, ep_sq), tmp) &&
                            tmp.ep_square() == ep_sq) {
                            ++n_ep;
                        }
                    }
                }
            }
        }

        return static_cast<long double>(n_castling * n_ep);
    }

private:

    BoardSpec spec_;
    int w_ = 0;
    int h_ = 0;
    int S_ = 0;
    int S_p_ = 0;
    long double fact_[65]{};
    std::array<std::vector<std::pair<int, int>>, 3> kings_by_a_;
    std::array<std::array<MaterialBucket, MAX_U + 1>, MAX_P + 1> buckets_w_;
    std::array<std::array<MaterialBucket, MAX_U + 1>, MAX_P + 1> buckets_b_;
    std::vector<SamplingBucket> buckets_;
    long double U_total_ = 0.0L;
};

struct ExactStaticCounts {
    uint64_t superset_U = 0;
    uint64_t legal_L = 0;
};

// Brute-force exact enumerator for small off-8x8 boards (e.g., 3x3) to validate StaticSpaceSampler.
inline ExactStaticCounts brute_force_exact_static_off8(const BoardSpec& spec) {
    ExactStaticCounts out{};
    if (spec.is_8x8 || spec.w * spec.h > 12) return out;
    int w = spec.w;
    int h = spec.h;
    int S = w * h;

    auto valid_side = [](const MaterialBudget& cur, const MaterialBudget& init) {
        if (cur.p > init.p) return false;
        int promo = std::max(0, cur.n - init.n) + std::max(0, cur.b - init.b) +
                    std::max(0, cur.r - init.r) + std::max(0, cur.q - init.q);
        return promo <= (init.p - cur.p);
    };

    uint8_t codes[12]{};
    for (int kw = 0; kw < S; ++kw) {
        int kw_sq = mchess::make_sq(kw % w, kw / w);
        codes[kw] = encode_cell(mchess::KING, mchess::WHITE);
        for (int kb = 0; kb < S; ++kb) {
            if (kb == kw) continue;
            int kb_sq = mchess::make_sq(kb % w, kb / w);
            if (kings_adjacent(kw_sq, kb_sq)) continue;
            codes[kb] = encode_cell(mchess::KING, mchess::BLACK);

            std::vector<int> rem;
            for (int i = 0; i < S; ++i) {
                if (i != kw && i != kb) rem.push_back(i);
            }

            MaterialBudget cw{}, cb{};
            auto dfs = [&](auto& self, size_t idx) -> void {
                if (idx == rem.size()) {
                    out.superset_U += 2;
                    for (int s = 0; s < 2; ++s) {
                        mchess::Color stm = (s == 0) ? mchess::WHITE : mchess::BLACK;
                        mchess::Position pos;
                        if (mchess::Position::parse(codes_to_fen(codes, w, h, stm), pos)) {
                            ++out.legal_L;
                        }
                    }
                    return;
                }
                int sq_idx = rem[idx];
                int r = sq_idx / w;
                bool pawn_rank = (r >= 1 && r <= h - 2);

                // 0: empty
                codes[sq_idx] = 0;
                self(self, idx + 1);

                // White pieces: P, N, B, R, Q
                if (pawn_rank && cw.p + 1 <= spec.white_init.p) {
                    codes[sq_idx] = encode_cell(mchess::PAWN, mchess::WHITE);
                    ++cw.p;
                    if (valid_side(cw, spec.white_init)) self(self, idx + 1);
                    --cw.p;
                }
                auto try_piece = [&](uint8_t code, int& field, const MaterialBudget& cur,
                                     const MaterialBudget& init) {
                    codes[sq_idx] = code;
                    ++field;
                    if (valid_side(cur, init)) self(self, idx + 1);
                    --field;
                };
                try_piece(encode_cell(mchess::KNIGHT, mchess::WHITE), cw.n, cw, spec.white_init);
                try_piece(encode_cell(mchess::BISHOP, mchess::WHITE), cw.b, cw, spec.white_init);
                try_piece(encode_cell(mchess::ROOK, mchess::WHITE), cw.r, cw, spec.white_init);
                try_piece(encode_cell(mchess::QUEEN, mchess::WHITE), cw.q, cw, spec.white_init);

                // Black pieces: p, n, b, r, q
                if (pawn_rank && cb.p + 1 <= spec.black_init.p) {
                    codes[sq_idx] = encode_cell(mchess::PAWN, mchess::BLACK);
                    ++cb.p;
                    if (valid_side(cb, spec.black_init)) self(self, idx + 1);
                    --cb.p;
                }
                try_piece(encode_cell(mchess::KNIGHT, mchess::BLACK), cb.n, cb, spec.black_init);
                try_piece(encode_cell(mchess::BISHOP, mchess::BLACK), cb.b, cb, spec.black_init);
                try_piece(encode_cell(mchess::ROOK, mchess::BLACK), cb.r, cb, spec.black_init);
                try_piece(encode_cell(mchess::QUEEN, mchess::BLACK), cb.q, cb, spec.black_init);

                codes[sq_idx] = 0;
            };
            dfs(dfs, 0);
            codes[kb] = 0;
        }
        codes[kw] = 0;
    }
    return out;
}

} // namespace complexity
