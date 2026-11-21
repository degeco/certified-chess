#include "certificate.hpp"
#include "common.hpp"
#include "dfpn.hpp"
#include "draw_solver.hpp"
#include "tb_probe.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

namespace {

using namespace msolve;

std::string resolve_named_position(const std::string& s) {
    if (s == "mini4x4") return "rqkr/pppp/PPPP/RQKR w - -";
    if (s == "mini4x5") return "rqkr/pppp/4/PPPP/RQKR w - -";
    if (s == "mini5x5") return "rnbqk/ppppp/5/PPPPP/RNBQK w - -";
    if (s == "std8")    return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -";
    return s;
}

bool parse_claim_str(const std::string& kind_s, const std::string& side_s, Claim& out) {
    if (kind_s == "WIN") {
        out.kind = ClaimKind::WIN;
    } else if (kind_s == "ATLEAST_DRAW") {
        out.kind = ClaimKind::ATLEAST_DRAW;
    } else {
        return false;
    }
    if (side_s == "w") {
        out.prover = WHITE;
    } else if (side_s == "b") {
        out.prover = BLACK;
    } else {
        return false;
    }
    return true;
}

bool parse_claim_args(int argc, char** argv, int& i, Claim& claim) {
    if (i >= argc) {
        std::cerr << "ERROR: --claim requires an argument\n";
        return false;
    }
    std::string first_tok = argv[i++];
    auto sp = first_tok.find(' ');
    if (sp != std::string::npos) {
        std::string k = first_tok.substr(0, sp);
        std::string s = first_tok.substr(sp + 1);
        if (!parse_claim_str(k, s, claim)) {
            std::cerr << "ERROR: invalid --claim '" << first_tok << "'\n";
            return false;
        }
    } else {
        if (i >= argc) {
            std::cerr << "ERROR: --claim requires side (w or b)\n";
            return false;
        }
        std::string second_tok = argv[i++];
        if (!parse_claim_str(first_tok, second_tok, claim)) {
            std::cerr << "ERROR: invalid --claim '" << first_tok << " " << second_tok << "'\n";
            return false;
        }
    }
    return true;
}

void print_usage(const char* prog) {
    std::cerr
        << "Usage:\n"
        << "  " << prog << " \"<position|name>\" --claim <WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b> [options]\n"
        << "  " << prog << " \"<position|name>\" --value [options]\n"
        << "  " << prog << " merge --root \"<position|name>\" --claim <...> [merge options] <cert1> [<cert2> ...]\n"
        << "\nSolve options:\n"
        << "  --out <file.cert>        Write certificate to file (WIN or single ATLEAST_DRAW)\n"
        << "  --out-prefix <prefix>    In --value mode, write <prefix>_win_w.cert / <prefix>_draw_w.cert etc.\n"
        << "  --max-nodes <N>          Node limit (default: 20000000)\n"
        << "  --max-seconds <S>        Time limit in seconds (default: 60)\n"
        << "  --tt-mb <MB>             Memory budget in MB for TT/tables (default: 256, max: 3072)\n"
        << "  --dag-mode <mode>        DAG aggregation: snda (default), sum, sqrt, damped, max\n"
        << "  --tb-dir <dir>           Directory of 04-tablebase .tb files (default: auto ../04-tablebase/data)\n"
        << "  --no-tb                  Disable endgame tablebase probing\n"
        << "  --no-minimize            Skip certificate minimisation\n"
        << "  --verbose                Extra progress output\n"
        << "\nMerge options:\n"
        << "  --root \"<pos|name>\"      Root position for merged certificate\n"
        << "  --claim <...>            Claim for merged certificate (WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b)\n"
        << "  --root-move <move>       Shorthand for --move \"<root>=<move>\"\n"
        << "  --move \"<pos|name>=<mv>\" Add connecting move for prover position (repeatable)\n"
        << "  --moves-file <file>      File with '<fen>\\t<move>' lines for connecting moves\n"
        << "  --out <file.cert>        Output merged certificate path\n"
        << "  --no-minimize            Skip certificate minimisation\n"
        << "\nNamed positions: mini4x4, mini4x5, mini5x5, std8\n"
        << "\nExit codes:\n"
        << "  0 = PROVED / merged valid (or exact value determined in --value mode)\n"
        << "  1 = DISPROVED\n"
        << "  2 = LIMIT (unknown within node/time/memory budget)\n"
        << "  3 = ERROR\n";
}

std::string find_default_tb_dir(const char* argv0) {
    namespace fs = std::filesystem;
    std::vector<fs::path> candidates;
    candidates.emplace_back("../04-tablebase/data");
    candidates.emplace_back("04-tablebase/data");
    if (argv0 && argv0[0] != '\0') {
        std::error_code ec;
        fs::path exe = fs::weakly_canonical(fs::path(argv0), ec);
        if (!ec && exe.has_parent_path()) {
            candidates.push_back(exe.parent_path() / ".." / "04-tablebase" / "data");
        }
    }
    for (const auto& p : candidates) {
        std::error_code ec;
        if (fs::exists(p, ec) && fs::is_directory(p, ec)) {
            return p.string();
        }
    }
    return {};
}

void maybe_load_tb(const Position& root, const SolveLimits& limits, const char* argv0, TablebaseProbe& tb) {
    if (!limits.use_tb) return;
    std::string dir = limits.tb_dir.empty() ? find_default_tb_dir(argv0) : limits.tb_dir;
    if (dir.empty()) return;
    std::string info;
    if (tb.load_board(dir, root.width(), root.height(), 4, &info) && limits.verbose) {
        std::cerr << "[tb] " << info << "\n";
    }
}

void print_claim_report(const Claim& claim,
                        const std::string& root_fen,
                        SolveStatus status,
                        const SolveStats& st,
                        const std::string& out_path,
                        size_t tb_tables) {
    std::cout << "status: " << status_to_string(status) << "\n";
    std::cout << "claim: " << claim.to_string() << "\n";
    std::cout << "root: " << root_fen << "\n";
    std::cout << "nodes: " << st.nodes << "\n";
    if (tb_tables > 0) {
        std::cout << "tb_tables: " << tb_tables << "\n";
        std::cout << "tb_hits: " << st.tb_hits << "\n";
    }
    std::cout << std::fixed << std::setprecision(4) << "seconds: " << st.seconds << "\n";
    if (status == SolveStatus::PROVED) {
        std::cout << "entries_raw: " << st.raw_entries << "\n";
        std::cout << "entries_pruned: " << st.pruned_entries << "\n";
        std::cout << "entries: " << st.min_entries << "\n";
        std::cout << "max_rank: " << st.max_rank << "\n";
        if (!out_path.empty()) {
            std::error_code ec;
            auto fsz = std::filesystem::file_size(out_path, ec);
            if (!ec) {
                std::cout << "file_bytes: " << fsz << "\n";
            }
            std::cout << "cert: " << out_path << "\n";
        }
    }
    if (!st.note.empty()) {
        std::cout << "note: " << st.note << "\n";
    }
}

int run_single_claim(const Position& root,
                     const Claim& claim,
                     const SolveLimits& limits,
                     const std::string& out_path,
                     const TablebaseProbe* tb) {
    Certificate cert;
    SolveStats st;
    SolveStatus status = SolveStatus::ERROR;

    if (claim.kind == ClaimKind::WIN) {
        DfpnSolver solver(limits.tt_mb, tb);
        status = solver.solve_win(root, claim.prover, limits, &cert, &st);
    } else {
        DrawSolver solver(tb);
        status = solver.solve_atleast_draw(root, claim.prover, limits, &cert, &st);
    }

    if (status == SolveStatus::PROVED && !out_path.empty()) {
        std::string werr;
        if (!cert.write_to_file(out_path, &werr)) {
            std::cerr << "ERROR: " << werr << "\n";
            return 3;
        }
    }

    print_claim_report(claim, root.to_fen(), status, st, out_path, tb ? tb->table_count() : 0);
    return static_cast<int>(status);
}

int run_value_mode(const Position& root,
                   const SolveLimits& limits,
                   const std::string& out_path,
                   const std::string& out_prefix,
                   const TablebaseProbe* tb) {
    Timer total_timer;
    uint64_t total_nodes = 0;
    uint64_t total_tb_hits = 0;

    auto rem_limits = [&](double frac_time, uint64_t frac_nodes) -> SolveLimits {
        SolveLimits sub = limits;
        double rem_t = std::max(0.01, limits.max_seconds - total_timer.elapsed());
        uint64_t rem_n = (limits.max_nodes > total_nodes) ? (limits.max_nodes - total_nodes) : 1ULL;
        sub.max_seconds = std::min(rem_t, std::max(0.05, limits.max_seconds * frac_time));
        sub.max_nodes = std::min(rem_n, std::max<uint64_t>(1000ULL, frac_nodes));
        return sub;
    };

    int ev_w = eval_position(root, WHITE);
    Color first = root.side_to_move();
    if (ev_w >= 250) first = WHITE;
    else if (ev_w <= -250) first = BLACK;
    Color second = ~first;

    bool disproved_win[2] = {false, false};

    auto finish_win = [&](Color winner, const Certificate& cert, const SolveStats& st) -> int {
        std::string path = out_path;
        if (path.empty() && !out_prefix.empty()) {
            path = out_prefix + (winner == WHITE ? "_win_w.cert" : "_win_b.cert");
        }
        if (!path.empty()) {
            std::string werr;
            if (!cert.write_to_file(path, &werr)) {
                std::cerr << "ERROR: " << werr << "\n";
                return 3;
            }
        }
        std::cout << "value: WIN " << (winner == WHITE ? 'w' : 'b') << "\n";
        std::cout << "root: " << root.to_fen() << "\n";
        std::cout << "nodes: " << total_nodes << "\n";
        if (tb && tb->is_loaded()) {
            std::cout << "tb_tables: " << tb->table_count() << "\n";
            std::cout << "tb_hits: " << total_tb_hits << "\n";
        }
        std::cout << std::fixed << std::setprecision(4) << "seconds: " << total_timer.elapsed() << "\n";
        std::cout << "entries_raw: " << st.raw_entries << "\n";
        std::cout << "entries_pruned: " << st.pruned_entries << "\n";
        std::cout << "entries: " << st.min_entries << "\n";
        std::cout << "max_rank: " << st.max_rank << "\n";
        if (!path.empty()) {
            std::error_code ec;
            auto fsz = std::filesystem::file_size(path, ec);
            if (!ec) std::cout << "file_bytes: " << fsz << "\n";
            std::cout << "cert: " << path << "\n";
        }
        return 0;
    };

    DfpnSolver win_solver(limits.tt_mb, tb);
    for (Color c : {first, second}) {
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        win_solver.clear();
        SolveLimits sub = rem_limits(0.20, limits.max_nodes / 5);
        Certificate cert;
        SolveStats st;
        SolveStatus rs = win_solver.solve_win(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
        total_tb_hits += st.tb_hits;
        if (rs == SolveStatus::PROVED) {
            return finish_win(c, cert, st);
        }
        if (rs == SolveStatus::DISPROVED) {
            disproved_win[c] = true;
        }
    }

    bool proved_draw[2] = {false, false};
    Certificate draw_cert[2];
    SolveStats draw_st[2];
    DrawSolver draw_solver(tb);

    for (Color c : {WHITE, BLACK}) {
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        SolveLimits sub = rem_limits(0.30, limits.max_nodes / 3);
        SolveStats st;
        Certificate cert;
        SolveStatus rs = draw_solver.solve_atleast_draw(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
        total_tb_hits += st.tb_hits;
        if (rs == SolveStatus::PROVED) {
            proved_draw[c] = true;
            draw_cert[c] = std::move(cert);
            draw_st[c] = st;
        } else if (rs == SolveStatus::DISPROVED) {
            Color opp = ~c;
            win_solver.clear();
            SolveLimits wsub = rem_limits(1.0, limits.max_nodes);
            Certificate wcert;
            SolveStats wst;
            SolveStatus wrs = win_solver.solve_win(root, opp, wsub, &wcert, &wst);
            total_nodes += wst.nodes;
            total_tb_hits += wst.tb_hits;
            if (wrs == SolveStatus::PROVED) {
                return finish_win(opp, wcert, wst);
            }
        }
    }

    if (proved_draw[WHITE] && proved_draw[BLACK]) {
        std::string pw, pb;
        if (!out_prefix.empty()) {
            pw = out_prefix + "_draw_w.cert";
            pb = out_prefix + "_draw_b.cert";
            std::string werr;
            if (!draw_cert[WHITE].write_to_file(pw, &werr) ||
                !draw_cert[BLACK].write_to_file(pb, &werr)) {
                std::cerr << "ERROR: " << werr << "\n";
                return 3;
            }
        }
        std::cout << "value: DRAW\n";
        std::cout << "root: " << root.to_fen() << "\n";
        std::cout << "nodes: " << total_nodes << "\n";
        if (tb && tb->is_loaded()) {
            std::cout << "tb_tables: " << tb->table_count() << "\n";
            std::cout << "tb_hits: " << total_tb_hits << "\n";
        }
        std::cout << std::fixed << std::setprecision(4) << "seconds: " << total_timer.elapsed() << "\n";
        std::cout << "draw_w_entries_raw: " << draw_st[WHITE].raw_entries << "\n";
        std::cout << "draw_w_entries: " << draw_st[WHITE].min_entries << "\n";
        std::cout << "draw_b_entries_raw: " << draw_st[BLACK].raw_entries << "\n";
        std::cout << "draw_b_entries: " << draw_st[BLACK].min_entries << "\n";
        if (!pw.empty()) {
            std::cout << "cert_w: " << pw << "\n";
            std::cout << "cert_b: " << pb << "\n";
        }
        return 0;
    }

    for (Color c : {first, second}) {
        if (disproved_win[c] || proved_draw[~c]) continue;
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        win_solver.clear();
        SolveLimits sub = rem_limits(0.50, limits.max_nodes / 2);
        Certificate cert;
        SolveStats st;
        SolveStatus rs = win_solver.solve_win(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
        total_tb_hits += st.tb_hits;
        if (rs == SolveStatus::PROVED) {
            return finish_win(c, cert, st);
        }
    }

    std::cout << "value: UNKNOWN\n";
    std::cout << "root: " << root.to_fen() << "\n";
    std::cout << "nodes: " << total_nodes << "\n";
    std::cout << std::fixed << std::setprecision(4) << "seconds: " << total_timer.elapsed() << "\n";
    if (proved_draw[WHITE]) {
        std::cout << "partial_bound: ATLEAST_DRAW w (entries=" << draw_st[WHITE].min_entries << ")\n";
        if (!out_prefix.empty()) {
            std::string pw = out_prefix + "_draw_w.cert";
            std::string werr;
            if (draw_cert[WHITE].write_to_file(pw, &werr)) {
                std::cout << "cert_w: " << pw << "\n";
            }
        }
    }
    if (proved_draw[BLACK]) {
        std::cout << "partial_bound: ATLEAST_DRAW b (entries=" << draw_st[BLACK].min_entries << ")\n";
        if (!out_prefix.empty()) {
            std::string pb = out_prefix + "_draw_b.cert";
            std::string werr;
            if (draw_cert[BLACK].write_to_file(pb, &werr)) {
                std::cout << "cert_b: " << pb << "\n";
            }
        }
    }
    return 2;
}

int run_merge_mode(int argc, char** argv) {
    Timer timer;
    std::string root_arg;
    bool has_claim = false;
    Claim claim;
    std::string root_move_str;
    std::vector<std::string> move_specs;
    std::vector<std::string> moves_files;
    std::vector<std::string> cert_paths;
    std::string out_path;
    bool do_minimize = true;

    int i = 2;
    while (i < argc) {
        std::string arg = argv[i++];
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--root") {
            if (i >= argc) { std::cerr << "ERROR: --root requires an argument\n"; return 3; }
            root_arg = argv[i++];
        } else if (arg == "--claim") {
            if (!parse_claim_args(argc, argv, i, claim)) return 3;
            has_claim = true;
        } else if (arg == "--root-move") {
            if (i >= argc) { std::cerr << "ERROR: --root-move requires an argument\n"; return 3; }
            root_move_str = argv[i++];
        } else if (arg == "--move") {
            if (i >= argc) { std::cerr << "ERROR: --move requires '<pos>=<move>'\n"; return 3; }
            move_specs.push_back(argv[i++]);
        } else if (arg == "--moves-file") {
            if (i >= argc) { std::cerr << "ERROR: --moves-file requires a path\n"; return 3; }
            moves_files.push_back(argv[i++]);
        } else if (arg == "--out") {
            if (i >= argc) { std::cerr << "ERROR: --out requires a path\n"; return 3; }
            out_path = argv[i++];
        } else if (arg == "--no-minimize") {
            do_minimize = false;
        } else if (!arg.empty() && arg[0] != '-') {
            cert_paths.push_back(arg);
        } else {
            std::cerr << "ERROR: unknown merge argument: " << arg << "\n";
            return 3;
        }
    }

    if (root_arg.empty() || !has_claim) {
        std::cerr << "ERROR: merge requires --root and --claim\n";
        return 3;
    }

    Position root;
    std::string perr;
    if (!Position::parse(resolve_named_position(root_arg), root, &perr)) {
        std::cerr << "ERROR: invalid --root '" << root_arg << "': " << perr << "\n";
        return 3;
    }

    // Parse connecting moves
    std::vector<std::pair<Position, Move>> connecting;
    auto add_move_pair = [&](const std::string& pos_str, const std::string& mv_str) -> bool {
        Position p;
        std::string err;
        if (!Position::parse(resolve_named_position(pos_str), p, &err)) {
            std::cerr << "ERROR: invalid connecting position '" << pos_str << "': " << err << "\n";
            return false;
        }
        auto mv = p.parse_move(mv_str);
        if (!mv) {
            std::cerr << "ERROR: illegal connecting move '" << mv_str << "' at '" << p.to_fen() << "'\n";
            return false;
        }
        connecting.emplace_back(p, *mv);
        return true;
    };

    if (!root_move_str.empty()) {
        if (!add_move_pair(root.to_fen(), root_move_str)) return 3;
    }

    for (const std::string& spec : move_specs) {
        auto eq = spec.find('=');
        if (eq == std::string::npos) {
            std::cerr << "ERROR: --move expects '<pos>=<move>', got '" << spec << "'\n";
            return 3;
        }
        if (!add_move_pair(spec.substr(0, eq), spec.substr(eq + 1))) return 3;
    }

    for (const std::string& mf : moves_files) {
        std::ifstream in(mf);
        if (!in) {
            std::cerr << "ERROR: cannot open moves file '" << mf << "'\n";
            return 3;
        }
        std::string line;
        while (std::getline(in, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty() || line[0] == '#') continue;
            auto tab = line.find('\t');
            if (tab == std::string::npos) {
                auto eq = line.find('=');
                if (eq == std::string::npos) {
                    std::cerr << "ERROR: bad line in " << mf << ": '" << line << "'\n";
                    return 3;
                }
                if (!add_move_pair(line.substr(0, eq), line.substr(eq + 1))) return 3;
            } else {
                if (!add_move_pair(line.substr(0, tab), line.substr(tab + 1))) return 3;
            }
        }
    }

    // Load all input sub-certificates
    std::vector<Certificate> sub_certs;
    sub_certs.reserve(cert_paths.size());
    for (const std::string& path : cert_paths) {
        Certificate sc;
        std::string lerr;
        if (!Certificate::load_from_file(path, sc, &lerr)) {
            std::cerr << "ERROR: failed loading certificate " << lerr << "\n";
            return 3;
        }
        sub_certs.push_back(std::move(sc));
    }

    Certificate merged;
    size_t raw_sz = 0, pruned_sz = 0, final_sz = 0;
    std::string merr;
    if (!Certificate::merge(root, claim, sub_certs, connecting, merged,
                            do_minimize, &raw_sz, &pruned_sz, &final_sz, &merr)) {
        std::cerr << "ERROR: merge failed: " << merr << "\n";
        return 3;
    }

    if (!out_path.empty()) {
        std::string werr;
        if (!merged.write_to_file(out_path, &werr)) {
            std::cerr << "ERROR: " << werr << "\n";
            return 3;
        }
    }

    std::cout << "status: MERGED_VALID\n";
    std::cout << "claim: " << claim.to_string() << "\n";
    std::cout << "root: " << merged.root_fen << "\n";
    std::cout << "inputs: " << sub_certs.size() << "\n";
    std::cout << "connecting_moves: " << connecting.size() << "\n";
    std::cout << "entries_raw: " << raw_sz << "\n";
    std::cout << "entries_pruned: " << pruned_sz << "\n";
    std::cout << "entries: " << final_sz << "\n";
    std::cout << "max_rank: " << merged.max_rank() << "\n";
    std::cout << std::fixed << std::setprecision(4) << "seconds: " << timer.elapsed() << "\n";
    if (!out_path.empty()) {
        std::error_code ec;
        auto fsz = std::filesystem::file_size(out_path, ec);
        if (!ec) std::cout << "file_bytes: " << fsz << "\n";
        std::cout << "cert: " << out_path << "\n";
    }
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 3;
    }
    if (std::string(argv[1]) == "-h" || std::string(argv[1]) == "--help") {
        print_usage(argv[0]);
        return 0;
    }
    if (std::string(argv[1]) == "merge") {
        return run_merge_mode(argc, argv);
    }
    if (argc < 3) {
        print_usage(argv[0]);
        return 3;
    }

    std::string pos_arg;
    bool has_claim = false;
    bool value_mode = false;
    Claim claim;
    SolveLimits limits;
    std::string out_path;
    std::string out_prefix;

    int i = 1;
    if (argv[1][0] != '-') {
        pos_arg = argv[1];
        i = 2;
    }

    while (i < argc) {
        std::string arg = argv[i++];
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--claim") {
            if (!parse_claim_args(argc, argv, i, claim)) return 3;
            has_claim = true;
        } else if (arg == "--value") {
            value_mode = true;
        } else if (arg == "--out") {
            if (i >= argc) { std::cerr << "ERROR: --out requires a file path\n"; return 3; }
            out_path = argv[i++];
        } else if (arg == "--out-prefix") {
            if (i >= argc) { std::cerr << "ERROR: --out-prefix requires a prefix\n"; return 3; }
            out_prefix = argv[i++];
        } else if (arg == "--max-nodes") {
            if (i >= argc) { std::cerr << "ERROR: --max-nodes requires a number\n"; return 3; }
            limits.max_nodes = std::strtoull(argv[i++], nullptr, 10);
        } else if (arg == "--max-seconds") {
            if (i >= argc) { std::cerr << "ERROR: --max-seconds requires a number\n"; return 3; }
            limits.max_seconds = std::strtod(argv[i++], nullptr);
        } else if (arg == "--tt-mb") {
            if (i >= argc) { std::cerr << "ERROR: --tt-mb requires a number\n"; return 3; }
            limits.tt_mb = static_cast<size_t>(std::strtoull(argv[i++], nullptr, 10));
        } else if (arg == "--dag-mode") {
            if (i >= argc) { std::cerr << "ERROR: --dag-mode requires sum|sqrt|damped|max\n"; return 3; }
            std::string dm = argv[i++];
            if (!parse_dag_mode(dm, limits.dag_mode)) {
                std::cerr << "ERROR: invalid --dag-mode '" << dm << "'\n";
                return 3;
            }
        } else if (arg == "--tb-dir") {
            if (i >= argc) { std::cerr << "ERROR: --tb-dir requires a directory path\n"; return 3; }
            limits.tb_dir = argv[i++];
            limits.use_tb = true;
        } else if (arg == "--no-tb") {
            limits.use_tb = false;
        } else if (arg == "--no-minimize") {
            limits.minimize = false;
        } else if (arg == "--verbose") {
            limits.verbose = true;
        } else if (pos_arg.empty() && arg[0] != '-') {
            pos_arg = arg;
        } else {
            std::cerr << "ERROR: unknown argument: " << arg << "\n";
            return 3;
        }
    }

    if (pos_arg.empty()) {
        std::cerr << "ERROR: missing position argument\n";
        return 3;
    }
    if (has_claim == value_mode) {
        std::cerr << "ERROR: specify exactly one of --claim or --value\n";
        return 3;
    }

    std::string fen = resolve_named_position(pos_arg);
    Position root;
    std::string perr;
    if (!Position::parse(fen, root, &perr)) {
        std::cerr << "ERROR: invalid position '" << pos_arg << "': " << perr << "\n";
        return 3;
    }

    TablebaseProbe tb;
    maybe_load_tb(root, limits, argv[0], tb);
    const TablebaseProbe* tb_ptr = tb.is_loaded() ? &tb : nullptr;

    if (has_claim) {
        return run_single_claim(root, claim, limits, out_path, tb_ptr);
    } else {
        return run_value_mode(root, limits, out_path, out_prefix, tb_ptr);
    }
}
