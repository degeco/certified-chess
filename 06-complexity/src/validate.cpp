#include "estimate.hpp"
#include "reach.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

static int failures = 0;

static void check(bool cond, const std::string& name) {
    if (cond) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << "\n";
        ++failures;
    }
}

int main() {
    // 1. PackedKey roundtrip on mini4x4, mini5x5, 6x6, and 8x8 (with castling & ep)
    {
        auto p4 = mchess::Position::from_fen("rqkr/pppp/PPPP/RQKR w - -").value();
        auto k4 = complexity::pack_position<complexity::Key16>(p4);
        mchess::Position u4;
        check(complexity::unpack_position(k4, 4, 4, u4) && u4 == p4, "Key16 roundtrip mini4x4");

        auto p6 = mchess::Position::from_fen("rnqknr/pppppp/6/6/PPPPPP/RNQKNR b - -").value();
        auto k6 = complexity::pack_position<complexity::Key24>(p6);
        mchess::Position u6;
        check(complexity::unpack_position(k6, 6, 6, u6) && u6 == p6, "Key24 roundtrip 6x6");

        auto p8 = mchess::Position::from_fen(
                      "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6")
                      .value();
        auto k8 = complexity::pack_position<complexity::Key36>(p8);
        mchess::Position u8;
        check(complexity::unpack_position(k8, 8, 8, u8) && u8 == p8 &&
                  u8.castling_rights() == p8.castling_rights() &&
                  u8.ep_square() == p8.ep_square(),
              "Key36 roundtrip 8x8 with castling and ep");
    }

    // 2. Reachability depth-1 & depth-2 counts match perft/unique children on std8 and mini4x4
    {
        complexity::ReachOptions opts;
        opts.max_depth = 2;
        auto r8 = complexity::run_reach("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", opts);
        // From std8: depth 0 = 1, depth 1 = 20, depth 2 = 400 (no transpositions at ply 2)
        check(r8.depths.size() == 3 && r8.depths[0].count == 1 && r8.depths[1].count == 20 &&
                  r8.depths[2].count == 400 && r8.total_positions == 421,
              "reach std8 depth 0..2 == 1, 20, 400");

        auto r4 = complexity::run_reach("rqkr/pppp/PPPP/RQKR w - -", opts);
        // Check depth 1 count matches legal_moves().size() from mini4x4
        auto p4 = mchess::Position::from_fen("rqkr/pppp/PPPP/RQKR w - -").value();
        uint64_t d1 = p4.legal_moves().size();
        check(r4.depths.size() == 3 && r4.depths[0].count == 1 && r4.depths[1].count == d1,
              "reach mini4x4 depth 1 matches legal_moves count");
    }

    // 3. Exact brute-force validation of StaticSpaceSampler on 3x3 boards
    {
        auto spec1 = complexity::make_spec_from_fen("mini3x3", "rkr/3/RKR w - -");
        auto ex1 = complexity::brute_force_exact_static_off8(spec1);
        complexity::StaticSpaceSampler s1(spec1);
        uint64_t U1 = static_cast<uint64_t>(std::llround(s1.superset_size()));
        auto est1 = s1.run(400000, 12345);
        std::cout << "  mini3x3: exact_U=" << ex1.superset_U << " formula_U=" << U1
                  << " exact_L=" << ex1.legal_L
                  << " est=" << std::fixed << std::setprecision(1) << static_cast<double>(est1.estimate)
                  << " ci95=[" << static_cast<double>(est1.ci95_low) << ", "
                  << static_cast<double>(est1.ci95_high) << "]\n";
        check(U1 == ex1.superset_U, "mini3x3 exact |U| matches brute-force enumeration");
        check(static_cast<long double>(ex1.legal_L) >= est1.ci95_low &&
                  static_cast<long double>(ex1.legal_L) <= est1.ci95_high,
              "mini3x3 exact |L| inside 95% CI");

        auto spec2 = complexity::make_spec_from_fen("mini3x3_p", "k1r/P1p/R1K w - -");
        check(spec2.w == 3 && spec2.h == 3 && spec2.white_init.p == 1,
              "mini3x3_p FEN valid");
        auto ex2 = complexity::brute_force_exact_static_off8(spec2);
        complexity::StaticSpaceSampler s2(spec2);
        uint64_t U2 = static_cast<uint64_t>(std::llround(s2.superset_size()));
        auto est2 = s2.run(500000, 54321);
        std::cout << "  mini3x3_p: exact_U=" << ex2.superset_U << " formula_U=" << U2
                  << " exact_L=" << ex2.legal_L
                  << " est=" << std::fixed << std::setprecision(1) << static_cast<double>(est2.estimate)
                  << " ci95=[" << static_cast<double>(est2.ci95_low) << ", "
                  << static_cast<double>(est2.ci95_high) << "]\n";
        check(U2 == ex2.superset_U, "mini3x3_p (with pawns & promos) exact |U| matches brute force");
        check(static_cast<long double>(ex2.legal_L) >= est2.ci95_low &&
                  static_cast<long double>(ex2.legal_L) <= est2.ci95_high,
              "mini3x3_p exact |L| inside 95% CI");
    }

    // 4. Clean memory-limit stop test for reach
    {
        complexity::ReachOptions opts;
        opts.max_mem_bytes = 32ULL * 1024ULL * 1024ULL; // 32 MB tiny cap
        auto r5 = complexity::run_reach("rnbqk/ppppp/5/PPPPP/RNBQK w - -", opts);
        std::cout << "  mini5x5 32MB cap: stop=" << r5.stop_reason
                  << " max_complete_depth=" << r5.max_complete_depth
                  << " total=" << r5.total_positions
                  << " peak_mb=" << std::fixed << std::setprecision(2)
                  << (static_cast<double>(r5.peak_mem_bytes) / (1024.0 * 1024.0)) << "\n";
        check(!r5.complete && r5.stop_reason == "memory_limit" &&
                  r5.peak_mem_bytes <= opts.max_mem_bytes,
              "reach stops cleanly under memory_limit");
    }

    // 5. 8x8 completion multiplier F(X) tests (castling, legal ep, pinned ep, opponent in check)
    {
        auto to_codes = [](const mchess::Position& pos, uint8_t* codes) {
            std::memset(codes, 0, 64);
            for (int r = 0; r < 8; ++r) {
                for (int f = 0; f < 8; ++f) {
                    mchess::Color c = mchess::WHITE;
                    mchess::PieceType pt = pos.piece_at(mchess::make_sq(f, r), &c);
                    codes[r * 8 + f] = complexity::encode_cell(pt, c);
                }
            }
        };

        uint8_t codes[64];
        // KQkq start-like position -> 16 castling * 1 ep = 16
        auto p_cast = mchess::Position::from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq -").value();
        to_codes(p_cast, codes);
        check(complexity::StaticSpaceSampler::evaluate_position_weight(
                  codes, 8, 8, true, mchess::WHITE) == 16.0L,
              "8x8 F(X) counts 16 castling subsets");

        // K castling (2) + legal ep on d6 (2) -> 4
        auto p_ep = mchess::Position::from_fen("4k3/8/8/3pP3/8/8/8/4K2R w K -").value();
        to_codes(p_ep, codes);
        check(complexity::StaticSpaceSampler::evaluate_position_weight(
                  codes, 8, 8, true, mchess::WHITE) == 4.0L,
              "8x8 F(X) counts K castling x legal ep = 4");

        // Horizontal pin makes ep illegal: Ka5, pawns d5/e5, black rook h5 -> ep must NOT count
        auto p_pin = mchess::Position::from_fen("4k3/8/8/K2pP2r/8/8/8/8 w - -").value();
        to_codes(p_pin, codes);
        check(complexity::StaticSpaceSampler::evaluate_position_weight(
                  codes, 8, 8, true, mchess::WHITE) == 1.0L,
              "8x8 F(X) rejects pinned pseudo-ep");

        // Opponent king in check -> 0 (White Rook on h8 checks Black King on e8, stm = WHITE)
        auto p_chk = mchess::Position::from_fen("4k2R/8/8/8/8/8/8/4K3 b - -").value();
        to_codes(p_chk, codes);
        check(complexity::StaticSpaceSampler::evaluate_position_weight(
                  codes, 8, 8, true, mchess::WHITE) == 0.0L,
              "8x8 F(X) returns 0 when non-stm king in check");
    }

    std::cout << (failures == 0 ? "ALL TESTS PASSED\n" : "TESTS FAILED\n");
    return failures == 0 ? 0 : 1;
}
