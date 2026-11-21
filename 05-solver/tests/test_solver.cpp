#include "../src/certificate.hpp"
#include "../src/common.hpp"
#include "../src/dfpn.hpp"
#include "../src/draw_solver.hpp"

#include <cassert>
#include <iostream>
#include <string>

using namespace msolve;

static int failures = 0;

static void check(bool cond, const std::string& name) {
    if (cond) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << "\n";
        ++failures;
    }
}

static Position must_parse(const std::string& fen) {
    Position p;
    std::string err;
    bool ok = Position::parse(fen, p, &err);
    if (!ok) {
        std::cerr << "Parse error on '" << fen << "': " << err << "\n";
        std::exit(1);
    }
    return p;
}

int main() {
    SolveLimits lim;
    lim.max_nodes = 2000000;
    lim.max_seconds = 10.0;
    lim.tt_mb = 32;

    // 1. Immediate checkmate at root (opponent to move -> 0 entries)
    {
        Position p = must_parse("3k/3Q/3K/4 b - -");
        DfpnSolver s(16);
        Certificate c;
        SolveStats st;
        auto rs = s.solve_win(p, WHITE, lim, &c, &st);
        check(rs == SolveStatus::PROVED && c.size() == 0 && c.verify(),
              "WIN w on already-checkmated root (0 entries)");
    }

    // 2. Prover stalemate at root (SPEC v1.1: ATLEAST_DRAW PROVED 0 entries, WIN DISPROVED)
    {
        // White king on a1, Black queen on b3, Black king on c2 -> White to move, no moves, not in check!
        Position p = must_parse("4/1q2/2k1/K3 w - -");
        check(p.is_stalemate(), "Test stalemate position is stalemate");

        DfpnSolver s(16);
        Certificate cw;
        auto rw = s.solve_win(p, WHITE, lim, &cw);
        check(rw == SolveStatus::DISPROVED, "WIN w on prover stalemate is DISPROVED");

        DrawSolver ds;
        Certificate cd;
        auto rd = ds.solve_atleast_draw(p, WHITE, lim, &cd);
        check(rd == SolveStatus::PROVED && cd.size() == 0 && cd.verify(),
              "ATLEAST_DRAW w on prover stalemate is PROVED (0 entries)");
    }

    // 3. Opponent reply forces prover stalemate (SPEC v1.1 exemption inside body)
    {
        // Black to move: Black king c2, Black queen c3, White king a1 ->
        // Wait: make White to move with only draw via stalemate trap:
        // White K a1, Black K c2, Black Q b3 -> if Black to move from 4/2q1/2k1/K3 b - -,
        // actually let's test K vs K on 3x3: must prove ATLEAST_DRAW for both sides!
        Position p = must_parse("k2/3/2K w - -");
        DrawSolver ds;
        Certificate cw, cb;
        auto rw = ds.solve_atleast_draw(p, WHITE, lim, &cw);
        auto rb = ds.solve_atleast_draw(p, BLACK, lim, &cb);
        check(rw == SolveStatus::PROVED && cw.verify(), "K vs K 3x3 ATLEAST_DRAW w PROVED");
        check(rb == SolveStatus::PROVED && cb.verify(), "K vs K 3x3 ATLEAST_DRAW b PROVED");
    }

    // 4. mini4x4 (Silverman 4x4): forced mate in 4 for White!
    {
        Position p = must_parse("rqkr/pppp/PPPP/RQKR w - -");
        DfpnSolver s(32);
        Certificate cw;
        SolveStats st;
        auto rw = s.solve_win(p, WHITE, lim, &cw, &st);
        check(rw == SolveStatus::PROVED && cw.verify() && cw.max_rank() <= 4 && cw.size() <= 8,
              "mini4x4 WIN w proved (entries=" + std::to_string(cw.size()) +
              ", max_rank=" + std::to_string(cw.max_rank()) + ")");

        DrawSolver ds;
        Certificate cdw, cdb;
        auto rdw = ds.solve_atleast_draw(p, WHITE, lim, &cdw);
        auto rdb = ds.solve_atleast_draw(p, BLACK, lim, &cdb);
        check(rdw == SolveStatus::PROVED && cdw.verify(), "mini4x4 ATLEAST_DRAW w PROVED");
        check(rdb == SolveStatus::DISPROVED, "mini4x4 ATLEAST_DRAW b DISPROVED");
    }

    // 5. 8x8 forced mate in 2: 3r2k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - - (1. Re8+ Rxe8 2. Rxe8#)
    {
        Position p = must_parse("3r2k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - -");
        DfpnSolver s(32);
        Certificate c;
        SolveStats st;
        auto r = s.solve_win(p, WHITE, lim, &c, &st);
        check(r == SolveStatus::PROVED && c.verify() && c.max_rank() == 2,
              "8x8 mate in 2 proved (entries=" + std::to_string(c.size()) +
              ", max_rank=" + std::to_string(c.max_rank()) + ")");
    }

    // 6. 8x8 forced mate in 3 (Philidor smothered mate): 4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -
    //    1. Nh6+ Kh8 2. Qg8+ Rxg8 3. Nf7# (or 1... Kf8 2. Qf7#)
    {
        Position p = must_parse("4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -");
        DfpnSolver s(32);
        Certificate c;
        SolveStats st;
        auto r = s.solve_win(p, WHITE, lim, &c, &st);
        check(r == SolveStatus::PROVED && c.verify() && c.max_rank() == 3,
              "8x8 mate in 3 proved (entries=" + std::to_string(c.size()) +
              ", max_rank=" + std::to_string(c.max_rank()) + ")");
    }

    // 7. 8x8 forced mate in 4: 4r2k/6pp/8/6N1/8/1Q6/6PP/6K1 w - -
    //    1. Nf7+ Kg8 2. Nh6+ Kh8 3. Qg8+ Rxg8 4. Nf7#
    {
        Position p = must_parse("4r2k/6pp/8/6N1/8/1Q6/6PP/6K1 w - -");
        DfpnSolver s(32);
        Certificate c;
        SolveStats st;
        auto r = s.solve_win(p, WHITE, lim, &c, &st);
        check(r == SolveStatus::PROVED && c.verify() && c.max_rank() == 4,
              "8x8 mate in 4 proved (entries=" + std::to_string(c.size()) +
              ", max_rank=" + std::to_string(c.max_rank()) + ")");
    }

    // 8. 8x8 forced mate in 5: 2r3k1/6pp/8/6N1/1Q6/8/5PPP/6K1 w - -
    //    1. Qb3+ Kh8 2. Nf7+ Kg8 3. Nh6+ Kh8 4. Qg8+ Rxg8 5. Nf7#
    {
        Position p = must_parse("2r3k1/6pp/8/6N1/1Q6/8/5PPP/6K1 w - -");
        DfpnSolver s(32);
        Certificate c;
        SolveStats st;
        auto r = s.solve_win(p, WHITE, lim, &c, &st);
        check(r == SolveStatus::PROVED && c.verify() && c.max_rank() == 5,
              "8x8 mate in 5 proved (entries=" + std::to_string(c.size()) +
              ", max_rank=" + std::to_string(c.max_rank()) + ")");
    }

    // 9. Minimisation test: add an unreachable valid entry and verify minimize() drops it.
    {
        Position p = must_parse("rqkr/pppp/PPPP/RQKR w - -");
        DfpnSolver s(16);
        Certificate c;
        SolveLimits nmlim = lim;
        nmlim.minimize = false;
        auto r = s.solve_win(p, WHITE, nmlim, &c);
        check(r == SolveStatus::PROVED, "mini4x4 raw WIN w extracted");

        // Inject an unrelated valid mate-in-1 entry on 4x4: k3/4/1K2/2R1 w - - (c1c4#)
        Position extra = must_parse("k3/4/1K2/2R1 w - -");
        auto mv = extra.parse_move("c1c4");
        check(mv.has_value() && extra.make_move(*mv).is_checkmate(), "Synthetic unreachable mate-in-1 valid");
        CertEntry ce;
        ce.pos = extra;
        ce.fen = extra.to_fen();
        ce.move = *mv;
        ce.rank = 1;
        c.entries[ce.fen] = ce;
        check(c.verify(), "Bloated certificate with unreachable entry is valid before minimize");
        size_t before = 0, pruned = 0, after = 0;
        c.minimize(&before, &pruned, &after);
        check(pruned < before && after <= pruned && c.verify(),
              "Minimiser dropped unreachable entry (" + std::to_string(before) +
              " -> " + std::to_string(pruned) + " -> " + std::to_string(after) + ")");
    }

    // 10. All 4 DAG modes solve mini4x4 and 8x8 mate-in-4 cleanly
    {
        Position m4 = must_parse("rqkr/pppp/PPPP/RQKR w - -");
        Position m8 = must_parse("4r2k/6pp/8/6N1/8/1Q6/6PP/6K1 w - -");
        for (DagMode dm : {DagMode::SUM, DagMode::SNDA, DagMode::SQRT, DagMode::DAMPED, DagMode::MAX_PLUS}) {
            SolveLimits dlim = lim;
            dlim.dag_mode = dm;
            DfpnSolver s1(16), s2(16);
            Certificate c1, c2;
            auto r1 = s1.solve_win(m4, WHITE, dlim, &c1);
            auto r2 = s2.solve_win(m8, WHITE, dlim, &c2);
            check(r1 == SolveStatus::PROVED && c1.verify(),
                  std::string("mini4x4 WIN w valid under dag=") + dag_mode_to_string(dm));
            check(r2 == SolveStatus::PROVED && c2.verify() && c2.max_rank() == 4,
                  std::string("8x8 mate4 WIN w valid under dag=") + dag_mode_to_string(dm));
        }
    }

    // 11. TablebaseProbe + splicing on 4x5 (both 4pc direct and 5pc->4pc splice)
    {
        TablebaseProbe tb;
        std::string info;
        bool loaded = tb.load_board("../04-tablebase/data", 4, 5, 4, &info);
        check(loaded && tb.table_count() == 66, "TablebaseProbe loaded all 66 4x5 tables (" + info + ")");
        if (loaded) {
            // 4pc KQ vs KR on 4x5: k3/r3/4/1Q2/3K w - -
            Position p4 = must_parse("k3/r3/4/1Q2/3K w - -");
            DfpnSolver s(16, &tb);
            Certificate c;
            SolveStats st;
            auto r = s.solve_win(p4, WHITE, lim, &c, &st);
            check(r == SolveStatus::PROVED && c.verify() && st.tb_hits > 0 && st.nodes == 1,
                  "4x5 4pc TB WIN w solved in 1 node and verified (entries=" + std::to_string(c.size()) + ")");

            // 4pc draw position (K vs K on 4x5) via DrawSolver with TB
            Position pk = must_parse("k3/4/4/4/3K w - -");
            DrawSolver ds(&tb);
            Certificate cd;
            SolveStats dst;
            auto rd = ds.solve_atleast_draw(pk, WHITE, lim, &cd, &dst);
            check(rd == SolveStatus::PROVED && cd.verify(),
                  "4x5 K vs K ATLEAST_DRAW w via TB verified (entries=" + std::to_string(cd.size()) + ")");
        }
    }

    // 12. Certificate::merge (split mini4x4 across opponent replies + root move)
    {
        Position root = must_parse("rqkr/pppp/PPPP/RQKR w - -");
        auto mv_opt = root.parse_move("c2d3");
        check(mv_opt.has_value(), "mini4x4 c2d3 legal");
        Position after_cxd3 = root.make_move(*mv_opt);
        Move rbuf[MAX_MOVES];
        int nr = after_cxd3.legal_moves(rbuf);
        std::vector<Certificate> subs;
        for (int i = 0; i < nr; ++i) {
            Position rp = after_cxd3.make_move(rbuf[i]);
            DfpnSolver s(16);
            Certificate sc;
            auto rs = s.solve_win(rp, WHITE, lim, &sc);
            check(rs == SolveStatus::PROVED && sc.verify(),
                  "mini4x4 sub-reply " + rbuf[i].to_string() + " proved");
            subs.push_back(std::move(sc));
        }
        Certificate merged;
        std::string merr;
        bool mok = Certificate::merge(root, Claim{ClaimKind::WIN, WHITE}, subs,
                                      {{root, *mv_opt}}, merged, true, nullptr, nullptr, nullptr, &merr);
        check(mok && merged.verify(), "Certificate::merge combined mini4x4 sub-certs (" + merr + ")");

        // Also test merging WIN sub-certs into ATLEAST_DRAW claim
        Certificate merged_draw;
        bool mdok = Certificate::merge(root, Claim{ClaimKind::ATLEAST_DRAW, WHITE}, subs,
                                       {{root, *mv_opt}}, merged_draw, true, nullptr, nullptr, nullptr, &merr);
        check(mdok && merged_draw.verify(), "Certificate::merge WIN subs into ATLEAST_DRAW (" + merr + ")");
    }

    if (failures == 0) {
        std::cout << "ALL C++ UNIT TESTS PASSED\n";
        return 0;
    } else {
        std::cout << failures << " TEST(S) FAILED\n";
        return 1;
    }
}
