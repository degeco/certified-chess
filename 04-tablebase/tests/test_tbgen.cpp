#include "indexer.hpp"
#include "signature.hpp"
#include "tablebase.hpp"
#include "mchess.hpp"

#include <algorithm>
#include <cassert>
#include <filesystem>
#include <iostream>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace {

void check(bool cond, const std::string& msg) {
    if (!cond) {
        std::cerr << "TEST FAILED: " << msg << "\n";
        std::exit(1);
    }
}

void test_signatures() {
    auto kqk = tb::MaterialSig::parse("KQK");
    check(kqk.has_value() && kqk->to_string() == "KQK", "parse KQK");

    auto krkp = tb::MaterialSig::parse("krkp");
    check(krkp.has_value() && krkp->to_string() == "KRKP", "parse krkp");

    auto kprk = tb::MaterialSig::parse("KPRK");
    check(kprk.has_value() && kprk->to_string() == "KRPK", "canonicalize KPRK -> KRPK");

    check(!tb::MaterialSig::parse("KQ").has_value(), "reject single king");
    check(!tb::MaterialSig::parse("KKK").has_value(), "reject three kings");

    auto kpk_deps = tb::MaterialSig::parse("KPK")->dependencies();
    std::set<std::string> dep_strs;
    for (const auto& d : kpk_deps) dep_strs.insert(d.to_string());
    check(dep_strs.count("KK") == 1, "KPK dep KK");
    check(dep_strs.count("KQK") == 1, "KPK dep KQK");
    check(dep_strs.count("KRK") == 1, "KPK dep KRK");
    check(dep_strs.count("KBK") == 1, "KPK dep KBK");
    check(dep_strs.count("KNK") == 1, "KPK dep KNK");
    check(dep_strs.size() == 5, "KPK dep count");

    auto sigs4 = tb::enumerate_signatures(4);
    check(sigs4.size() == 66, "66 total 2-4 piece signatures");
    check(sigs4.front().to_string() == "KK", "first signature is KK");
    std::cout << "[PASS] test_signatures (66 2-4 piece signatures)\n";
}

void test_indexer_bijection(int w, int h, const std::string& sig_str) {
    auto sig = tb::MaterialSig::parse(sig_str);
    check(sig.has_value(), "parse " + sig_str);
    tb::TableIndexer idxr(w, h, *sig);

    uint32_t N = idxr.size();
    uint32_t valid_count = 0;
    for (uint32_t i = 0; i < N; ++i) {
        tb::RawState st;
        idxr.decode_raw(i, st);
        uint32_t re = idxr.encode_raw(st);
        check(re == i, "encode_raw(decode_raw) mismatch at " + sig_str + " idx=" + std::to_string(i));

        mchess::Position pos;
        if (idxr.decode_position(i, pos)) {
            ++valid_count;
            uint32_t re_pos = idxr.encode_position(pos);
            check(re_pos == i, "encode_position mismatch at " + sig_str + " idx=" + std::to_string(i));
            auto reparsed = mchess::Position::from_fen(pos.to_fen());
            check(reparsed.has_value() && reparsed->hash() == pos.hash(),
                  "FEN roundtrip mismatch at " + pos.to_fen());
        }
    }
    std::cout << "[PASS] test_indexer_bijection " << w << "x" << h << " " << sig_str
              << " (index=" << N << ", legal=" << valid_count << ")\n";
}

void test_unmove_matches_forward(int w, int h, const std::string& sig_str) {
    auto sig = tb::MaterialSig::parse(sig_str);
    check(sig.has_value(), "parse " + sig_str);
    tb::TableIndexer idxr(w, h, *sig);
    uint32_t N = idxr.size();

    std::vector<uint8_t> wdl(N, tb::WDL_UNKNOWN);
    std::vector<std::set<uint32_t>> fwd_preds(N);

    mchess::Move moves[mchess::MAX_MOVES];
    for (uint32_t u = 0; u < N; ++u) {
        mchess::Position pos;
        if (!idxr.decode_position(u, pos)) {
            wdl[u] = tb::WDL_ILLEGAL;
            continue;
        }
        int nm = pos.legal_moves(moves);
        for (int i = 0; i < nm; ++i) {
            mchess::Move m = moves[i];
            bool cap_or_promo = (m.promo != mchess::NO_PIECE) ||
                                (pos.piece_at(m.to) != mchess::NO_PIECE) ||
                                (pos.ep_square() != mchess::NO_SQ &&
                                 m.to == pos.ep_square() &&
                                 pos.piece_at(m.from) == mchess::PAWN);
            if (cap_or_promo) continue;
            mchess::Position next = pos.make_move(m);
            uint32_t p = idxr.encode_position(next);
            check(p != UINT32_MAX, "forward quiet move failed encode");
            fwd_preds[p].insert(u);
        }
    }

    size_t total_edges = 0;
    for (uint32_t p = 0; p < N; ++p) {
        if (wdl[p] == tb::WDL_ILLEGAL) continue;
        auto got = tb::collect_quiet_predecessors(idxr, p, wdl);
        std::set<uint32_t> got_set(got.begin(), got.end());
        check(got.size() == got_set.size(), "duplicate predecessor emitted in " + sig_str);
        if (got_set != fwd_preds[p]) {
            mchess::Position ppos;
            idxr.decode_position(p, ppos);
            std::cerr << "Edge mismatch at p=" << p << " (" << ppos.to_fen() << ")\n";
            std::cerr << "  fwd_preds=" << fwd_preds[p].size() << " got=" << got_set.size() << "\n";
            check(false, "unmove != forward in " + sig_str);
        }
        total_edges += got.size();
    }

    std::cout << "[PASS] test_unmove_matches_forward " << w << "x" << h << " " << sig_str
              << " (edges=" << total_edges << ")\n";
}

void test_generate_verify_and_cert() {
    std::string tmp_dir = "build/test_data";
    std::filesystem::remove_all(tmp_dir);
    tb::TableStore store(tmp_dir);

    // Build and verify 3x3 KK, KQK, KPK, KPKP, KQRK and 4x4 KQK, KPK, KRKP
    const std::vector<std::tuple<int, int, std::string>> cases = {
        {3, 3, "KK"},
        {3, 3, "KQK"},
        {3, 3, "KPK"},
        {3, 3, "KPKP"},
        {3, 3, "KQRK"},
        {4, 4, "KQK"},
        {4, 4, "KPK"},
        {4, 4, "KRKP"},
    };

    for (const auto& [w, h, s] : cases) {
        auto sig = tb::MaterialSig::parse(s);
        std::string err;
        check(store.verify(w, h, *sig, &err), err);
        std::cout << "[PASS] verify " << w << "x" << h << " " << s << "\n";
    }

    // Save/load roundtrip check
    {
        auto sig = tb::MaterialSig::parse("KPK");
        const auto& tb1 = store.ensure(4, 4, *sig, true);
        auto tb2 = tb::Tablebase::load(store.db_path(4, 4, *sig));
        check(tb2 != nullptr, "load .tb file");
        check(tb2->wdl == tb1.wdl && tb2->dtm == tb1.dtm, "save/load exact match");
        std::cout << "[PASS] save/load roundtrip 4x4 KPK\n";
    }

    // Export certificates for a WIN position, a LOSS position, and a DRAW position (including stalemate)
    {
        const auto& kqk = store.ensure(4, 4, *tb::MaterialSig::parse("KQK"));
        bool tested_win = false, tested_loss = false, tested_draw = false;
        for (uint32_t i = 0; i < kqk.indexer->size(); ++i) {
            if (kqk.wdl[i] == tb::WDL_ILLEGAL) continue;
            if (!tested_win && kqk.wdl[i] == tb::WDL_WIN && kqk.dtm[i] >= 5) {
                mchess::Position pos;
                check(kqk.indexer->decode_position(i, pos), "decode win");
                std::vector<std::string> certs, claims;
                std::vector<uint32_t> entries;
                std::vector<uint16_t> max_ranks;
                std::string err;
                check(store.export_certificates(pos, certs, claims, entries, max_ranks, &err), err);
                check(certs.size() == 1 && claims[0].rfind("WIN ", 0) == 0 && entries[0] > 0,
                      "WIN cert check");
                tested_win = true;
            }
            if (!tested_loss && kqk.wdl[i] == tb::WDL_LOSS && kqk.dtm[i] >= 4) {
                mchess::Position pos;
                check(kqk.indexer->decode_position(i, pos), "decode loss");
                std::vector<std::string> certs, claims;
                std::vector<uint32_t> entries;
                std::vector<uint16_t> max_ranks;
                std::string err;
                check(store.export_certificates(pos, certs, claims, entries, max_ranks, &err), err);
                check(certs.size() == 1 && claims[0].rfind("WIN ", 0) == 0 && entries[0] > 0,
                      "LOSS->WIN cert check");
                tested_loss = true;
            }
            if (!tested_draw && kqk.wdl[i] == tb::WDL_DRAW) {
                mchess::Position pos;
                check(kqk.indexer->decode_position(i, pos), "decode draw");
                if (pos.has_legal_moves()) {
                    std::vector<std::string> certs, claims;
                    std::vector<uint32_t> entries;
                    std::vector<uint16_t> max_ranks;
                    std::string err;
                    check(store.export_certificates(pos, certs, claims, entries, max_ranks, &err), err);
                    check(certs.size() == 2 && claims[0] == "ATLEAST_DRAW w" &&
                              claims[1] == "ATLEAST_DRAW b",
                          "DRAW cert check");
                    tested_draw = true;
                }
            }
            if (tested_win && tested_loss && tested_draw) break;
        }
        check(tested_win && tested_loss && tested_draw, "tested win/loss/draw cert exports");
        std::cout << "[PASS] cert export WIN/LOSS/DRAW\n";
    }

    std::filesystem::remove_all(tmp_dir);
}

} // namespace

int main() {
    test_signatures();
    test_indexer_bijection(3, 3, "KQRK");
    test_indexer_bijection(3, 3, "KPKP");
    test_indexer_bijection(4, 4, "KQK");
    test_indexer_bijection(4, 4, "KPK");
    test_indexer_bijection(8, 8, "KPK");
    test_indexer_bijection(8, 8, "KRK");

    test_unmove_matches_forward(3, 3, "KK");
    test_unmove_matches_forward(3, 3, "KQK");
    test_unmove_matches_forward(3, 3, "KPK");
    test_unmove_matches_forward(3, 3, "KPKP");
    test_unmove_matches_forward(3, 3, "KQRK");
    test_unmove_matches_forward(4, 4, "KPK");
    test_unmove_matches_forward(8, 8, "KPK");
    test_unmove_matches_forward(8, 8, "KRK");

    test_generate_verify_and_cert();

    std::cout << "ALL TESTS PASSED\n";
    return 0;
}
