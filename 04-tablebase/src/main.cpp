#include "indexer.hpp"
#include "signature.hpp"
#include "tablebase.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace {

void print_usage() {
    std::cerr
        << "Usage:\n"
        << "  tbgen build <WxH> <SIG> [--db-dir DIR]\n"
        << "  tbgen build-all <WxH> [--max-pieces N] [--verify] [--db-dir DIR]\n"
        << "  tbgen dump <WxH> <SIG> [--db-dir DIR]\n"
        << "  tbgen verify <WxH> <SIG> [--db-dir DIR]\n"
        << "  tbgen cert \"<FEN>\" [--out-prefix PREFIX] [--db-dir DIR]\n"
        << "  tbgen h1 <WxH> [--max-pieces N | --sig SIG] [--samples N] [--seed S]\n"
        << "           [--out-tsv PATH] [--cert-dir DIR] [--cert-limit N] [--db-dir DIR]\n";
}

void print_stats_header() {
    std::cout << "board\tsig\tindex_size\tlegal\twins\tdraws\tlosses\tcheckmates\tstalemates"
              << "\tmax_win_dtm\tmax_loss_dtm\tgen_sec\ttable_bytes\tmax_win_fen\n";
}

void print_stats_row(const tb::TableStats& st) {
    std::cout << st.width << "x" << st.height << "\t"
              << st.signature << "\t"
              << st.index_size << "\t"
              << st.legal_positions << "\t"
              << st.wins << "\t"
              << st.draws << "\t"
              << st.losses << "\t"
              << st.checkmates << "\t"
              << st.stalemates << "\t"
              << st.max_win_dtm << "\t"
              << st.max_loss_dtm << "\t"
              << std::fixed << std::setprecision(4) << st.gen_seconds << "\t"
              << st.table_bytes << "\t"
              << st.max_win_fen << "\n";
}

bool write_text_file(const std::string& path, const std::string& content) {
    std::filesystem::path p(path);
    if (p.has_parent_path()) {
        std::filesystem::create_directories(p.parent_path());
    }
    std::ofstream os(path, std::ios::binary);
    if (!os) return false;
    os.write(content.data(), static_cast<std::streamsize>(content.size()));
    return static_cast<bool>(os);
}

int cmd_build(int argc, char** argv) {
    if (argc < 4) {
        print_usage();
        return 1;
    }
    int w = 0, h = 0;
    if (!tb::parse_board_size(argv[2], w, h)) {
        std::cerr << "Invalid board size: " << argv[2] << "\n";
        return 1;
    }
    auto sig = tb::MaterialSig::parse(argv[3]);
    if (!sig) {
        std::cerr << "Invalid signature: " << argv[3] << "\n";
        return 1;
    }
    std::string db_dir = "data";
    for (int i = 4; i < argc; ++i) {
        if (std::string(argv[i]) == "--db-dir" && i + 1 < argc) {
            db_dir = argv[++i];
        } else {
            std::cerr << "Unknown arg: " << argv[i] << "\n";
            return 1;
        }
    }

    tb::TableStore store(db_dir);
    const tb::Tablebase& tbl = store.ensure(w, h, *sig, true);
    print_stats_header();
    print_stats_row(tbl.compute_stats());
    return 0;
}

int cmd_build_all(int argc, char** argv) {
    if (argc < 3) {
        print_usage();
        return 1;
    }
    int w = 0, h = 0;
    if (!tb::parse_board_size(argv[2], w, h)) {
        std::cerr << "Invalid board size: " << argv[2] << "\n";
        return 1;
    }
    int max_pieces = 4;
    bool do_verify = false;
    std::string db_dir = "data";
    for (int i = 3; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--max-pieces" && i + 1 < argc) {
            max_pieces = std::stoi(argv[++i]);
        } else if (arg == "--verify") {
            do_verify = true;
        } else if (arg == "--db-dir" && i + 1 < argc) {
            db_dir = argv[++i];
        } else {
            std::cerr << "Unknown arg: " << arg << "\n";
            return 1;
        }
    }

    tb::TableStore store(db_dir);
    auto sigs = tb::enumerate_signatures(max_pieces);
    print_stats_header();
    for (const auto& s : sigs) {
        const tb::Tablebase& tbl = store.ensure(w, h, s, true);
        if (do_verify) {
            std::string err;
            if (!store.verify(w, h, s, &err)) {
                std::cerr << "VERIFY FAILED: " << err << "\n";
                return 1;
            }
        }
        print_stats_row(tbl.compute_stats());
    }
    return 0;
}

int cmd_dump(int argc, char** argv) {
    if (argc < 4) {
        print_usage();
        return 1;
    }
    int w = 0, h = 0;
    if (!tb::parse_board_size(argv[2], w, h)) {
        std::cerr << "Invalid board size: " << argv[2] << "\n";
        return 1;
    }
    auto sig = tb::MaterialSig::parse(argv[3]);
    if (!sig) {
        std::cerr << "Invalid signature: " << argv[3] << "\n";
        return 1;
    }
    std::string db_dir = "data";
    for (int i = 4; i < argc; ++i) {
        if (std::string(argv[i]) == "--db-dir" && i + 1 < argc) {
            db_dir = argv[++i];
        } else {
            std::cerr << "Unknown arg: " << argv[i] << "\n";
            return 1;
        }
    }

    tb::TableStore store(db_dir);
    const tb::Tablebase& tbl = store.ensure(w, h, *sig, true);
    const uint32_t N = tbl.indexer->size();
    std::ios::sync_with_stdio(false);
    for (uint32_t idx = 0; idx < N; ++idx) {
        uint8_t v = tbl.wdl[idx];
        if (v == tb::WDL_ILLEGAL) continue;
        mchess::Position pos;
        if (!tbl.indexer->decode_position(idx, pos)) continue;
        char vc = (v == tb::WDL_WIN) ? 'W' : (v == tb::WDL_LOSS ? 'L' : 'D');
        uint16_t d = (v == tb::WDL_DRAW) ? 0 : tbl.dtm[idx];
        std::cout << pos.to_fen() << "\t" << vc << "\t" << d << "\n";
    }
    return 0;
}

int cmd_verify(int argc, char** argv) {
    if (argc < 4) {
        print_usage();
        return 1;
    }
    int w = 0, h = 0;
    if (!tb::parse_board_size(argv[2], w, h)) {
        std::cerr << "Invalid board size: " << argv[2] << "\n";
        return 1;
    }
    auto sig = tb::MaterialSig::parse(argv[3]);
    if (!sig) {
        std::cerr << "Invalid signature: " << argv[3] << "\n";
        return 1;
    }
    std::string db_dir = "data";
    for (int i = 4; i < argc; ++i) {
        if (std::string(argv[i]) == "--db-dir" && i + 1 < argc) {
            db_dir = argv[++i];
        } else {
            std::cerr << "Unknown arg: " << argv[i] << "\n";
            return 1;
        }
    }

    tb::TableStore store(db_dir);
    std::string err;
    if (!store.verify(w, h, *sig, &err)) {
        std::cerr << "INVALID: " << err << "\n";
        return 1;
    }
    std::cout << "VERIFIED " << w << "x" << h << " " << sig->to_string() << "\n";
    return 0;
}

int cmd_cert(int argc, char** argv) {
    if (argc < 3) {
        print_usage();
        return 1;
    }
    std::string fen = argv[2];
    std::string out_prefix;
    std::string db_dir = "data";
    for (int i = 3; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--out-prefix" && i + 1 < argc) {
            out_prefix = argv[++i];
        } else if (arg == "--db-dir" && i + 1 < argc) {
            db_dir = argv[++i];
        } else {
            std::cerr << "Unknown arg: " << arg << "\n";
            return 1;
        }
    }

    mchess::Position pos;
    std::string err;
    if (!mchess::Position::parse(fen, pos, &err)) {
        std::cerr << "Invalid position: " << err << "\n";
        return 1;
    }

    tb::TableStore store(db_dir);
    std::vector<std::string> certs, claims;
    std::vector<uint32_t> entries;
    std::vector<uint16_t> max_ranks;
    if (!store.export_certificates(pos, certs, claims, entries, max_ranks, &err)) {
        std::cerr << "Export failed: " << err << "\n";
        return 1;
    }

    if (out_prefix.empty()) {
        for (size_t i = 0; i < certs.size(); ++i) {
            if (certs.size() > 1) {
                std::cout << "# === CERTIFICATE " << (i + 1) << " (" << claims[i] << ") ===\n";
            }
            std::cout << certs[i];
        }
    } else {
        if (certs.size() == 1) {
            std::string p = out_prefix + ".cert";
            if (!write_text_file(p, certs[0])) {
                std::cerr << "Failed to write " << p << "\n";
                return 1;
            }
            std::cout << p << "\t" << claims[0] << "\t" << entries[0] << "\t" << max_ranks[0] << "\n";
        } else {
            const char* suffixes[2] = {".w.cert", ".b.cert"};
            for (size_t i = 0; i < certs.size(); ++i) {
                std::string p = out_prefix + suffixes[i];
                if (!write_text_file(p, certs[i])) {
                    std::cerr << "Failed to write " << p << "\n";
                    return 1;
                }
                std::cout << p << "\t" << claims[i] << "\t" << entries[i] << "\t" << max_ranks[i] << "\n";
            }
        }
    }
    return 0;
}

int cmd_h1(int argc, char** argv) {
    if (argc < 3) {
        print_usage();
        return 1;
    }
    int w = 0, h = 0;
    if (!tb::parse_board_size(argv[2], w, h)) {
        std::cerr << "Invalid board size: " << argv[2] << "\n";
        return 1;
    }

    int max_pieces = 4;
    std::string only_sig;
    size_t samples = 200;
    uint64_t seed = 20261121ULL;
    std::string out_tsv = "results/h1.tsv";
    bool append_tsv = false;
    std::string cert_dir;
    size_t cert_limit = 0;
    std::string db_dir = "data";

    for (int i = 3; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--max-pieces" && i + 1 < argc) max_pieces = std::stoi(argv[++i]);
        else if (arg == "--sig" && i + 1 < argc) only_sig = argv[++i];
        else if (arg == "--samples" && i + 1 < argc) samples = std::stoull(argv[++i]);
        else if (arg == "--seed" && i + 1 < argc) seed = std::stoull(argv[++i]);
        else if (arg == "--out-tsv" && i + 1 < argc) out_tsv = argv[++i];
        else if (arg == "--append") append_tsv = true;
        else if (arg == "--cert-dir" && i + 1 < argc) cert_dir = argv[++i];
        else if (arg == "--cert-limit" && i + 1 < argc) cert_limit = std::stoull(argv[++i]);
        else if (arg == "--db-dir" && i + 1 < argc) db_dir = argv[++i];
        else {
            std::cerr << "Unknown arg: " << arg << "\n";
            return 1;
        }
    }

    std::vector<tb::MaterialSig> sigs;
    if (!only_sig.empty()) {
        auto s = tb::MaterialSig::parse(only_sig);
        if (!s) {
            std::cerr << "Invalid signature: " << only_sig << "\n";
            return 1;
        }
        sigs.push_back(*s);
    } else {
        sigs = tb::enumerate_signatures(max_pieces);
    }

    std::filesystem::path tsv_path(out_tsv);
    if (tsv_path.has_parent_path()) {
        std::filesystem::create_directories(tsv_path.parent_path());
    }
    bool write_header = !append_tsv || !std::filesystem::exists(out_tsv);
    std::ofstream tsv(out_tsv, append_tsv ? std::ios::app : std::ios::trunc);
    if (!tsv) {
        std::cerr << "Cannot open output TSV: " << out_tsv << "\n";
        return 1;
    }
    if (write_header) {
        tsv << "board\tsignature\troot\tclaim\tentries\tmax_rank\ttable_positions\n";
    }

    tb::TableStore store(db_dir);
    std::mt19937_64 rng(seed);
    size_t saved_certs = 0;

    for (const auto& s : sigs) {
        const tb::Tablebase& tbl = store.ensure(w, h, s, true);
        const uint32_t N = tbl.indexer->size();

        std::vector<uint32_t> won_indices;
        std::vector<uint32_t> draw_indices;
        uint64_t legal_cnt = 0;

        for (uint32_t idx = 0; idx < N; ++idx) {
            uint8_t v = tbl.wdl[idx];
            if (v == tb::WDL_ILLEGAL) continue;
            ++legal_cnt;
            if (v == tb::WDL_WIN || v == tb::WDL_LOSS) {
                won_indices.push_back(idx);
            } else if (v == tb::WDL_DRAW) {
                draw_indices.push_back(idx);
            }
        }

        auto sample_and_export = [&](std::vector<uint32_t>& pool) {
            if (pool.size() > samples) {
                for (size_t i = 0; i < samples; ++i) {
                    std::uniform_int_distribution<size_t> dist(i, pool.size() - 1);
                    std::swap(pool[i], pool[dist(rng)]);
                }
                pool.resize(samples);
            }
            for (uint32_t idx : pool) {
                mchess::Position root_pos;
                if (!tbl.indexer->decode_position(idx, root_pos)) continue;

                std::vector<std::string> certs, claims;
                std::vector<uint32_t> entries;
                std::vector<uint16_t> max_ranks;
                std::string err;
                if (!store.export_certificates(root_pos, certs, claims, entries, max_ranks, &err)) {
                    std::cerr << "Export error: " << err << "\n";
                    return false;
                }
                std::string root_fen = root_pos.to_fen();
                for (size_t ci = 0; ci < certs.size(); ++ci) {
                    tsv << w << "x" << h << "\t"
                        << s.to_string() << "\t"
                        << root_fen << "\t"
                        << claims[ci] << "\t"
                        << entries[ci] << "\t"
                        << max_ranks[ci] << "\t"
                        << legal_cnt << "\n";

                    if (!cert_dir.empty() && (cert_limit == 0 || saved_certs < cert_limit)) {
                        std::ostringstream fn;
                        fn << cert_dir << "/" << w << "x" << h << "_" << s.to_string()
                           << "_" << saved_certs << ".cert";
                        write_text_file(fn.str(), certs[ci]);
                        ++saved_certs;
                    }
                }
            }
            return true;
        };

        if (!sample_and_export(won_indices)) return 1;
        if (!sample_and_export(draw_indices)) return 1;
    }

    std::cout << "Wrote H1 rows to " << out_tsv;
    if (!cert_dir.empty()) std::cout << " (saved " << saved_certs << " certs to " << cert_dir << ")";
    std::cout << "\n";
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        print_usage();
        return 1;
    }
    std::string cmd = argv[1];
    if (cmd == "build") return cmd_build(argc, argv);
    if (cmd == "build-all") return cmd_build_all(argc, argv);
    if (cmd == "dump") return cmd_dump(argc, argv);
    if (cmd == "verify") return cmd_verify(argc, argv);
    if (cmd == "cert") return cmd_cert(argc, argv);
    if (cmd == "h1") return cmd_h1(argc, argv);

    print_usage();
    return 1;
}
