#include "certificate.hpp"
#include "common.hpp"
#include "dfpn.hpp"
#include "draw_solver.hpp"

#include <cstdlib>
#include <filesystem>
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

void print_usage(const char* prog) {
    std::cerr
        << "Usage:\n"
        << "  " << prog << " \"<position|name>\" --claim <WIN w|WIN b|ATLEAST_DRAW w|ATLEAST_DRAW b> [options]\n"
        << "  " << prog << " \"<position|name>\" --value [options]\n"
        << "\nOptions:\n"
        << "  --out <file.cert>        Write certificate to file (WIN or single ATLEAST_DRAW)\n"
        << "  --out-prefix <prefix>    In --value mode, write <prefix>_win_w.cert / <prefix>_draw_w.cert etc.\n"
        << "  --max-nodes <N>          Node limit (default: 20000000)\n"
        << "  --max-seconds <S>        Time limit in seconds (default: 60)\n"
        << "  --tt-mb <MB>             Memory budget in MB for TT/tables (default: 256, max: 3072)\n"
        << "  --no-minimize            Skip certificate minimisation\n"
        << "  --verbose                Extra progress output\n"
        << "\nNamed positions: mini4x4, mini4x5, mini5x5, std8\n"
        << "\nExit codes:\n"
        << "  0 = PROVED (or exact value determined in --value mode)\n"
        << "  1 = DISPROVED\n"
        << "  2 = LIMIT (unknown within node/time/memory budget)\n"
        << "  3 = ERROR\n";
}

void print_claim_report(const Claim& claim,
                        const std::string& root_fen,
                        SolveStatus status,
                        const SolveStats& st,
                        const std::string& out_path) {
    std::cout << "status: " << status_to_string(status) << "\n";
    std::cout << "claim: " << claim.to_string() << "\n";
    std::cout << "root: " << root_fen << "\n";
    std::cout << "nodes: " << st.nodes << "\n";
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
                     const std::string& out_path) {
    Certificate cert;
    SolveStats st;
    SolveStatus status = SolveStatus::ERROR;

    if (claim.kind == ClaimKind::WIN) {
        DfpnSolver solver(limits.tt_mb);
        status = solver.solve_win(root, claim.prover, limits, &cert, &st);
    } else {
        DrawSolver solver;
        status = solver.solve_atleast_draw(root, claim.prover, limits, &cert, &st);
    }

    if (status == SolveStatus::PROVED && !out_path.empty()) {
        std::string werr;
        if (!cert.write_to_file(out_path, &werr)) {
            std::cerr << "ERROR: " << werr << "\n";
            return 3;
        }
    }

    print_claim_report(claim, root.to_fen(), status, st, out_path);
    return static_cast<int>(status);
}

int run_value_mode(const Position& root,
                   const SolveLimits& limits,
                   const std::string& out_path,
                   const std::string& out_prefix) {
    Timer total_timer;
    uint64_t total_nodes = 0;

    auto rem_limits = [&](double frac_time, uint64_t frac_nodes) -> SolveLimits {
        SolveLimits sub = limits;
        double rem_t = std::max(0.01, limits.max_seconds - total_timer.elapsed());
        uint64_t rem_n = (limits.max_nodes > total_nodes) ? (limits.max_nodes - total_nodes) : 1ULL;
        sub.max_seconds = std::min(rem_t, std::max(0.05, limits.max_seconds * frac_time));
        sub.max_nodes = std::min(rem_n, std::max<uint64_t>(1000ULL, frac_nodes));
        return sub;
    };

    // Decide initial WIN probe order: start with side to move (or side ahead in static eval).
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

    // Phase 1: Quick WIN probes (15% budget each)
    DfpnSolver win_solver(limits.tt_mb);
    for (Color c : {first, second}) {
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        win_solver.clear();
        SolveLimits sub = rem_limits(0.20, limits.max_nodes / 5);
        Certificate cert;
        SolveStats st;
        SolveStatus rs = win_solver.solve_win(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
        if (rs == SolveStatus::PROVED) {
            return finish_win(c, cert, st);
        }
        if (rs == SolveStatus::DISPROVED) {
            disproved_win[c] = true;
        }
    }

    // Phase 2: Try ATLEAST_DRAW for both sides (30% budget each)
    bool proved_draw[2] = {false, false};
    Certificate draw_cert[2];
    SolveStats draw_st[2];
    DrawSolver draw_solver;

    for (Color c : {WHITE, BLACK}) {
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        SolveLimits sub = rem_limits(0.30, limits.max_nodes / 3);
        SolveStats st;
        Certificate cert;
        SolveStatus rs = draw_solver.solve_atleast_draw(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
        if (rs == SolveStatus::PROVED) {
            proved_draw[c] = true;
            draw_cert[c] = std::move(cert);
            draw_st[c] = st;
        } else if (rs == SolveStatus::DISPROVED) {
            // ATLEAST_DRAW c disproved => opponent (~c) wins! Prove & emit WIN ~c!
            Color opp = ~c;
            win_solver.clear();
            SolveLimits wsub = rem_limits(1.0, limits.max_nodes);
            Certificate wcert;
            SolveStats wst;
            SolveStatus wrs = win_solver.solve_win(root, opp, wsub, &wcert, &wst);
            total_nodes += wst.nodes;
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

    // Phase 3: Spend remaining budget on deeper WIN search for sides not yet disproved/drawn.
    for (Color c : {first, second}) {
        if (disproved_win[c] || proved_draw[~c]) continue;
        if (total_timer.elapsed() >= limits.max_seconds || total_nodes >= limits.max_nodes) break;
        win_solver.clear();
        SolveLimits sub = rem_limits(0.50, limits.max_nodes / 2);
        Certificate cert;
        SolveStats st;
        SolveStatus rs = win_solver.solve_win(root, c, sub, &cert, &st);
        total_nodes += st.nodes;
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

} // namespace

int main(int argc, char** argv) {
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
            if (i >= argc) {
                std::cerr << "ERROR: --claim requires an argument\n";
                return 3;
            }
            std::string first_tok = argv[i++];
            auto sp = first_tok.find(' ');
            if (sp != std::string::npos) {
                std::string k = first_tok.substr(0, sp);
                std::string s = first_tok.substr(sp + 1);
                if (!parse_claim_str(k, s, claim)) {
                    std::cerr << "ERROR: invalid --claim '" << first_tok << "'\n";
                    return 3;
                }
            } else {
                if (i >= argc) {
                    std::cerr << "ERROR: --claim requires side (w or b)\n";
                    return 3;
                }
                std::string second_tok = argv[i++];
                if (!parse_claim_str(first_tok, second_tok, claim)) {
                    std::cerr << "ERROR: invalid --claim '" << first_tok << " " << second_tok << "'\n";
                    return 3;
                }
            }
            has_claim = true;
        } else if (arg == "--value") {
            value_mode = true;
        } else if (arg == "--out") {
            if (i >= argc) {
                std::cerr << "ERROR: --out requires a file path\n";
                return 3;
            }
            out_path = argv[i++];
        } else if (arg == "--out-prefix") {
            if (i >= argc) {
                std::cerr << "ERROR: --out-prefix requires a prefix\n";
                return 3;
            }
            out_prefix = argv[i++];
        } else if (arg == "--max-nodes") {
            if (i >= argc) {
                std::cerr << "ERROR: --max-nodes requires a number\n";
                return 3;
            }
            limits.max_nodes = std::strtoull(argv[i++], nullptr, 10);
        } else if (arg == "--max-seconds") {
            if (i >= argc) {
                std::cerr << "ERROR: --max-seconds requires a number\n";
                return 3;
            }
            limits.max_seconds = std::strtod(argv[i++], nullptr);
        } else if (arg == "--tt-mb") {
            if (i >= argc) {
                std::cerr << "ERROR: --tt-mb requires a number\n";
                return 3;
            }
            limits.tt_mb = static_cast<size_t>(std::strtoull(argv[i++], nullptr, 10));
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

    if (has_claim) {
        return run_single_claim(root, claim, limits, out_path);
    } else {
        return run_value_mode(root, limits, out_path, out_prefix);
    }
}
