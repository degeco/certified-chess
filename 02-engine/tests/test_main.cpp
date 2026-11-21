#include "mchess.hpp"
#include <cassert>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <vector>

using namespace mchess;

namespace {

int g_failures = 0;

void check(bool cond, const char* msg, const char* file, int line) {
    if (!cond) {
        std::cerr << "FAIL [" << file << ":" << line << "]: " << msg << "\n";
        ++g_failures;
    }
}

#define CHECK(cond) check((cond), #cond, __FILE__, __LINE__)

uint64_t naive_perft(const Position& pos, int depth) {
    if (depth == 0) return 1;
    uint64_t total = 0;
    for (const Move& m : pos.legal_moves()) {
        total += naive_perft(pos.make_move(m), depth - 1);
    }
    return total;
}

void verify_hash_tree(const Position& pos, int depth) {
    auto reparsed = Position::from_fen(pos.to_fen());
    CHECK(reparsed.has_value());
    if (reparsed) {
        CHECK(pos == *reparsed);
        CHECK(pos.hash() == reparsed->hash());
    }
    if (depth == 0) return;
    for (const Move& m : pos.legal_moves()) {
        Position next = pos.make_move(m);
        verify_hash_tree(next, depth - 1);
    }
}

void test_8x8_perft() {
    struct PerftCase {
        const char* name;
        const char* fen;
        int max_depth;
        uint64_t expected[6]; // index 1..5
    };

    const PerftCase cases[] = {
        {
            "startpos",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
            5,
            {1, 20, 400, 8902, 197281, 4865609}
        },
        {
            "kiwipete",
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
            4,
            {1, 48, 2039, 97862, 4085603, 0}
        },
        {
            "pos3",
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -",
            5,
            {1, 14, 191, 2812, 43238, 674624}
        },
        {
            "pos4",
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
            4,
            {1, 6, 264, 9467, 422333, 0}
        },
        {
            "pos5",
            "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -",
            4,
            {1, 44, 1486, 62379, 2103487, 0}
        },
        {
            "pos6",
            "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - -",
            4,
            {1, 46, 2079, 89890, 3894594, 0}
        }
    };

    uint64_t total_nodes = 0;
    auto t0 = std::chrono::steady_clock::now();

    for (const auto& tc : cases) {
        auto pos = Position::from_fen(tc.fen);
        CHECK(pos.has_value());
        if (!pos) continue;

        for (int d = 1; d <= tc.max_depth; ++d) {
            uint64_t got = perft(*pos, d);
            total_nodes += got;
            if (got != tc.expected[d]) {
                std::cerr << "Perft mismatch " << tc.name << " d" << d
                          << ": got " << got << ", expected " << tc.expected[d] << "\n";
                ++g_failures;
            }
        }
        // Cross-check naive_perft at d=3
        CHECK(naive_perft(*pos, 3) == tc.expected[3]);
    }

    auto t1 = std::chrono::steady_clock::now();
    double secs = std::chrono::duration<double>(t1 - t0).count();
    std::cout << "8x8 perft suite: " << total_nodes << " nodes in " << secs << " s ("
              << static_cast<uint64_t>(total_nodes / secs) << " nps)\n";
}

void test_mini_boards() {
    // 1. Pawn single step only on 4x4, 4x5, 5x5, and non-8x8 (e.g. 8x7)
    {
        auto p44 = Position::from_fen("rqkr/pppp/PPPP/RQKR w - -");
        CHECK(p44.has_value());
        if (p44) {
            CHECK(p44->width() == 4 && p44->height() == 4);
            CHECK(!p44->is_8x8());
            // White pawns on a2,b2,c2,d2 are blocked by black pawns on a3,b3,c3,d3!
            // Wait: pawns on a2 can capture b3 (1), b2->a3,c3 (2), c2->b3,d3 (2), d2->c3 (1) => 6 pawn captures?
            // Wait: c2->b3 is guarded, etc., and rook/queen/king are blocked. Let's check exact moves!
            // Actually a2xb3 leaves Ra1? No, king is on c1!
            // a2xb3, b2xa3, b2xc3, c2xb3, c2xd3, d2xc3:
            // Wait: b2xa3 doesn't expose c1 king; c2xb3 doesn't expose c1 king (Qd1/Qc4? Black Q is on b4!).
            // Let's check: Black Q is on b4, Black R on a4, d4, Black K on c4.
            // On b4->b3->b2->b1: b2 moves away, leaving White Qb1 blocking? No, Q is on b1!
            // White: Ra1, Qb1, Kc1, Rd1. None of a2, b2, c2, d2 is pinned!
            // Wait: can any pawn push? a3,b3,c3,d3 are occupied by black pawns! So 0 pushes, 6 captures!
            CHECK(p44->legal_moves().size() == 6);
        }

        // Empty board with white pawn on rank 2 of 4x5: single step ONLY (no double step!)
        auto p45 = Position::from_fen("3k/4/4/P3/3K w - -");
        CHECK(p45.has_value());
        if (p45) {
            auto moves = p45->legal_moves();
            bool has_a2a3 = false, has_a2a4 = false;
            for (const auto& m : moves) {
                if (m.to_string() == "a2a3") has_a2a3 = true;
                if (m.to_string() == "a2a4") has_a2a4 = true;
            }
            CHECK(has_a2a3 && !has_a2a4);
        }

        // 8x7 board: still mini rules (no double step, no castling)
        auto p87 = Position::from_fen("4k3/8/8/8/8/PPPPPPPP/R3K2R w - -");
        CHECK(p87.has_value());
        if (p87) {
            CHECK(p87->width() == 8 && p87->height() == 7);
            CHECK(!p87->parse_move("e1g1").has_value());
            CHECK(p87->parse_move("a2a3").has_value());
            CHECK(!p87->parse_move("a2a4").has_value());
        }
    }

    // 2. Promotion on last rank of 3x3, 4x4, 5x5
    {
        // 3x3: white pawn on a2 -> a3 promotes to Q,R,B,N
        auto p33 = Position::from_fen("2k/P2/2K w - -");
        CHECK(p33.has_value());
        if (p33) {
            CHECK(p33->parse_move("a2a3q").has_value());
            CHECK(p33->parse_move("a2a3r").has_value());
            CHECK(p33->parse_move("a2a3b").has_value());
            CHECK(p33->parse_move("a2a3n").has_value());
            CHECK(!p33->parse_move("a2a3").has_value());
            auto next = p33->make_move(*p33->parse_move("a2a3n"));
            CHECK(next.to_fen() == "N1k/3/2K b - -");
        }

        // 4x4: black pawn capture promotion on b2 -> a1q/r/b/n
        auto p44 = Position::from_fen("3k/4/1p2/R2K b - -");
        CHECK(p44.has_value());
        if (p44) {
            CHECK(p44->parse_move("b2a1q").has_value());
            CHECK(p44->parse_move("b2a1r").has_value());
            CHECK(p44->parse_move("b2a1b").has_value());
            CHECK(p44->parse_move("b2a1n").has_value());
            CHECK(p44->parse_move("b2b1q").has_value());
            CHECK(!p44->parse_move("b2a1").has_value());
        }

        // 5x5: white pawn on rank 4 -> rank 5 promotion
        auto p55 = Position::from_fen("4k/2P2/5/5/4K w - -");
        CHECK(p55.has_value());
        if (p55) {
            CHECK(p55->parse_move("c4c5q").has_value());
            CHECK(p55->parse_move("c4c5r").has_value());
            CHECK(p55->parse_move("c4c5b").has_value());
            CHECK(p55->parse_move("c4c5n").has_value());
            CHECK(!p55->parse_move("c4c5").has_value());
        }
    }

    // 3. No castling / no ep off 8x8
    {
        CHECK(!Position::from_fen("4k3/8/8/8/8/8/R3K2R w KQ -").has_value());
        CHECK(!Position::from_fen("8/8/8/3pP3/8/8/K6k w - d6").has_value());
        CHECK(!Position::from_fen("3k/4/4/4/R2K w K -").has_value());
    }

    // 4. Check evasion & double check & pins on 3x3, 4x4, 5x5
    {
        // 3x3 double check: Ka1 checked by ra3 (a-file) and bc3 (diagonal).
        // Rc1 could capture bc3 if single check, but in double check only Ka1->b1 is legal.
        auto dc33 = Position::from_fen("rkb/3/K1R w - -");
        CHECK(dc33.has_value());
        if (dc33) {
            CHECK(dc33->in_check());
            auto moves = dc33->legal_moves();
            CHECK(moves.size() == 1 && moves[0].to_string() == "a1b1");
        }

        // Clean 4x4 double check: White Kd1, White Nd2 (could take Bb3 if single check);
        // Black Kb4, Black Rd4 (checks d1), Black Bb3 (checks d1 via c2).
        auto dc44 = Position::from_fen("1k1r/1b2/3N/3K w - -");
        CHECK(dc44.has_value());
        if (dc44) {
            CHECK(dc44->in_check());
            auto moves = dc44->legal_moves();
            CHECK(moves.size() == 1 && moves[0].to_string() == "d1c1");
        }

        // Pin on 4x4: White Ka1, White Nb2 (pinned by Black Bd4), White Rc2, Black Kb4.
        auto pin44 = Position::from_fen("1k1b/4/1NR1/K3 w - -");
        CHECK(pin44.has_value());
        if (pin44) {
            CHECK(!pin44->in_check());
            auto moves = pin44->legal_moves();
            for (const auto& m : moves) {
                CHECK(m.from != make_sq(1, 1));
            }
        }

        // Pin on 5x5: White Ke1, White Re2 (pinned along e-file by Black Re5), Black Ka5.
        auto pin55 = Position::from_fen("k3r/5/5/4R/4K w - -");
        CHECK(pin55.has_value());
        if (pin55) {
            for (const auto& m : pin55->legal_moves()) {
                if (m.from == make_sq(4, 1)) {
                    CHECK(sq_file(m.to) == 4);
                }
            }
            CHECK(pin55->parse_move("e2e5").has_value());
            CHECK(!pin55->parse_move("e2d2").has_value());
        }
    }

    // 5. Stalemate & Checkmate on 3x3, 4x4, 5x5
    {
        // 3x3 checkmate: White Ka1, Black Qb2, Black Kc2 (protected queen mate)
        auto mate33 = Position::from_fen("3/1qk/K2 w - -");
        CHECK(mate33.has_value());
        if (mate33) {
            CHECK(mate33->in_check());
            CHECK(mate33->is_terminal());
            CHECK(mate33->is_checkmate());
            CHECK(!mate33->is_stalemate());
            CHECK(mate33->status() == GameStatus::CHECKMATE);
        }

        // 3x3 stalemate: White Ka1, Black Qb3, Black Kc2 (a2 attacked by Q&K, b2 attacked by Q&K, b1 attacked by K&Q)
        auto stale33 = Position::from_fen("1q1/2k/K2 w - -");
        CHECK(stale33.has_value());
        if (stale33) {
            CHECK(!stale33->in_check());
            CHECK(stale33->is_terminal());
            CHECK(stale33->is_stalemate());
            CHECK(!stale33->is_checkmate());
            CHECK(stale33->status() == GameStatus::STALEMATE);
        }

        // 4x4 checkmate & stalemate
        auto mate44 = Position::from_fen("4/4/1qk1/K3 w - -");
        CHECK(mate44.has_value() && mate44->is_checkmate());
        auto stale44 = Position::from_fen("4/1q2/2k1/K3 w - -");
        CHECK(stale44.has_value() && stale44->is_stalemate());

        // 5x5 checkmate & stalemate
        auto mate55 = Position::from_fen("5/5/5/1qk2/K4 w - -");
        CHECK(mate55.has_value() && mate55->is_checkmate());
        auto stale55 = Position::from_fen("5/5/1q3/2k2/K4 w - -");
        CHECK(stale55.has_value() && stale55->is_stalemate());
    }
}

void test_canonical_and_ep() {
    const char* canon_fens[] = {
        "rqkr/pppp/PPPP/RQKR w - -",
        "rqkr/pppp/4/PPPP/RQKR w - -",
        "rnbqk/ppppp/5/PPPPP/RNBQK w - -",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "8/8/8/3pP3/8/8/8/K6k w - d6"
    };
    for (const char* fen : canon_fens) {
        auto p = Position::from_fen(fen);
        CHECK(p.has_value());
        if (p) {
            CHECK(p->to_fen() == fen);
        }
    }

    // Trailing halfmove/fullmove ignored
    {
        auto p = Position::from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
        CHECK(p.has_value());
        if (p) {
            CHECK(p->to_fen() == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -");
        }
    }

    // Double step with NO adjacent capturer -> ep is '-'
    {
        auto start = Position::from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -");
        CHECK(start.has_value());
        if (start) {
            auto m = start->parse_move("e2e4");
            CHECK(m.has_value());
            Position after = start->make_move(*m);
            CHECK(after.to_fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -");
            // Reparse with explicit e3 0 1 -> also normalizes to '-'
            auto rep = Position::from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1");
            CHECK(rep.has_value());
            if (rep) {
                CHECK(rep->to_fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -");
                CHECK(rep->hash() == after.hash());
            }
        }
    }

    // Pinned-capturer ep case (horizontal pin along rank 5):
    // Ka5, White pawn e5, Black rook h5; Black pushes d7-d5 -> e5xd6 would expose Ka5 to rh5!
    {
        auto before = Position::from_fen("8/3p4/8/K3P2r/8/8/8/7k b - -");
        CHECK(before.has_value());
        if (before) {
            auto m = before->parse_move("d7d5");
            CHECK(m.has_value());
            Position after = before->make_move(*m);
            CHECK(after.ep_square() == NO_SQ);
            CHECK(after.to_fen() == "8/8/8/K2pP2r/8/8/8/7k w - -");
            CHECK(!after.parse_move("e5d6").has_value());

            auto explicit_ep = Position::from_fen("8/8/8/K2pP2r/8/8/8/7k w - d6");
            CHECK(explicit_ep.has_value());
            if (explicit_ep) {
                CHECK(explicit_ep->ep_square() == NO_SQ);
                CHECK(explicit_ep->to_fen() == "8/8/8/K2pP2r/8/8/8/7k w - -");
                CHECK(explicit_ep->hash() == after.hash());
            }
        }
    }

    // Diagonal pin ep case: Kf3, White pawn e5, Black bishop b7 -> wait: f3-e4-d5-c6-b7!
    // Put White pawn on d5? No, f3-e4-d5-c6-b7: if White pawn is on e4? No, rank 5!
    // Kf4, White pawn e5, Black bishop c7? No: f4-e5-d6-c7-b8!
    // If White pawn is on e5, Black pawn pushes d7-d5, Black bishop on b8 pins e5 to Kf4: e5xd6 is along the pin ray!
    // Wait: moving ALONG the pin ray IS legal! Instead put White pawn on e5 pinned diagonally by Bb8 to Kf4, and Black pushes f7-f5!
    // Then e5xf6 leaves f4-b8 diagonal open!
    {
        auto before = Position::from_fen("1b6/5p2/8/4P3/5K2/8/8/7k b - -");
        CHECK(before.has_value());
        if (before) {
            auto m = before->parse_move("f7f5");
            CHECK(m.has_value());
            Position after = before->make_move(*m);
            CHECK(after.ep_square() == NO_SQ);
            CHECK(after.to_fen() == "1b6/8/8/4Pp2/5K2/8/8/7k w - -");
        }
    }

    // Positive ep case: double step gives check, ep capture captures checking pawn!
    // White Ke4, White pawn c5, Black pawn d7 -> d7-d5+! c5xd6 is legal!
    {
        auto before = Position::from_fen("8/3p4/8/2P5/4K3/8/8/7k b - -");
        CHECK(before.has_value());
        if (before) {
            auto m = before->parse_move("d7d5");
            CHECK(m.has_value());
            Position after = before->make_move(*m);
            CHECK(after.in_check());
            CHECK(after.ep_square() == make_sq(3, 5)); // d6
            CHECK(after.to_fen() == "8/8/8/2Pp4/4K3/8/8/7k w - d6");
            CHECK(after.parse_move("c5d6").has_value());
        }
    }

    // Invalid FEN checks
    CHECK(!Position::from_fen("8/8/8/8/8/8/8/8 w - -").has_value()); // no kings
    CHECK(!Position::from_fen("k7/8/8/8/8/8/8/K6K w - -").has_value()); // 2 white kings
    CHECK(!Position::from_fen("k6P/8/8/8/8/8/8/K7 w - -").has_value()); // pawn on rank 8
    CHECK(!Position::from_fen("k7/8/8/8/8/8/8/K6p w - -").has_value()); // pawn on rank 1
    CHECK(Position::from_fen("k7/8/8/8/8/8/8/K6R w - -").has_value()); // valid: R on h1 does not check k on a8
    CHECK(!Position::from_fen("k6R/8/8/8/8/8/8/K7 w - -").has_value()); // black king in check when white to move
    CHECK(!Position::from_fen("k7/8/8/8/8/8/8/K7 w K -").has_value()); // K without e1/h1
    CHECK(!Position::from_fen("r3k2r/8/8/8/8/8/8/R3K2R w QK -").has_value()); // wrong castling order
    CHECK(!Position::from_fen("44/8/8/8/8/8/8/K6k w - -").has_value()); // adjacent digits
    CHECK(Position::from_fen("2k/3/2K w - -").has_value()); // valid 3x3
    CHECK(!Position::from_fen("k1/K1 w - -").has_value()); // 2x2 too small
    CHECK(Position::from_fen("k2/3/3/K2 w - -").has_value()); // 3x4 valid
}

void test_hashes() {
    // Different dimensions with same lower-left piece placement must differ
    auto p33 = Position::from_fen("k2/3/2K w - -");
    auto p44 = Position::from_fen("4/k3/4/2K1 w - -");
    CHECK(p33.has_value() && p44.has_value());
    if (p33 && p44) {
        CHECK(p33->hash() != p44->hash());
    }

    // Verify make_move hash == reparsed hash across move trees
    const char* fens[] = {
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -",
        "rqkr/pppp/PPPP/RQKR w - -",
        "rqkr/pppp/4/PPPP/RQKR w - -",
        "rnbqk/ppppp/5/PPPPP/RNBQK w - -"
    };
    for (const char* fen : fens) {
        auto p = Position::from_fen(fen);
        CHECK(p.has_value());
        if (p) verify_hash_tree(*p, 2);
    }

    // Also random walks of length 30 on 8x8 and 5x5 checking hash at every step
    std::mt19937_64 rng(42);
    for (int trial = 0; trial < 50; ++trial) {
        Position p = *Position::from_fen(
            (trial % 2 == 0)
            ? "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
            : "rnbqk/ppppp/5/PPPPP/RNBQK w - -"
        );
        for (int step = 0; step < 30; ++step) {
            auto rep = Position::from_fen(p.to_fen());
            CHECK(rep.has_value() && rep->hash() == p.hash() && *rep == p);
            auto moves = p.legal_moves();
            if (moves.empty()) break;
            p = p.make_move(moves[rng() % moves.size()]);
        }
    }
}

void measure_mini_perft() {
    struct MiniCase {
        const char* name;
        const char* fen;
    };
    const MiniCase minis[] = {
        {"mini4x4", "rqkr/pppp/PPPP/RQKR w - -"},
        {"mini4x5", "rqkr/pppp/4/PPPP/RQKR w - -"},
        {"mini5x5", "rnbqk/ppppp/5/PPPPP/RNBQK w - -"}
    };

    for (const auto& mc : minis) {
        auto pos = Position::from_fen(mc.fen);
        CHECK(pos.has_value());
        if (!pos) continue;
        std::cout << mc.name << " (" << mc.fen << "):";
        for (int d = 1; d <= 6; ++d) {
            uint64_t cnt = perft(*pos, d);
            std::cout << " d" << d << "=" << cnt;
            if (d <= 4) {
                CHECK(cnt == naive_perft(*pos, d));
            }
        }
        std::cout << "\n";
    }
}

} // namespace

int main() {
    test_8x8_perft();
    test_mini_boards();
    test_canonical_and_ep();
    test_hashes();
    measure_mini_perft();

    if (g_failures == 0) {
        std::cout << "ALL TESTS PASSED\n";
        return 0;
    } else {
        std::cerr << g_failures << " TEST(S) FAILED\n";
        return 1;
    }
}
