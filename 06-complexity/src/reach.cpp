#include "reach.hpp"
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

static void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << " <board_name_or_fen> [options]\n"
              << "  --max-mem-mb <N>   Memory cap in MB (default 3500)\n"
              << "  --max-sec <S>      Time cap in seconds (default 240)\n"
              << "  --max-nodes <N>    Max discovered positions\n"
              << "  --max-depth <D>    Max BFS depth\n"
              << "  --quiet            Suppress per-depth lines\n";
}

int main(int argc, char** argv) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    complexity::BoardSpec spec;
    if (!complexity::find_spec(argv[1], spec)) {
        std::cerr << "Invalid board name or FEN: " << argv[1] << "\n";
        return 1;
    }

    complexity::ReachOptions opts;
    bool quiet = false;
    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--max-mem-mb" && i + 1 < argc) {
            opts.max_mem_bytes = std::strtoull(argv[++i], nullptr, 10) * 1024ULL * 1024ULL;
        } else if (arg == "--max-sec" && i + 1 < argc) {
            opts.max_sec = std::strtod(argv[++i], nullptr);
        } else if (arg == "--max-nodes" && i + 1 < argc) {
            opts.max_nodes = std::strtoull(argv[++i], nullptr, 10);
        } else if (arg == "--max-depth" && i + 1 < argc) {
            opts.max_depth = std::atoi(argv[++i]);
        } else if (arg == "--quiet") {
            quiet = true;
        } else {
            print_usage(argv[0]);
            return 1;
        }
    }

    complexity::ReachResult res = complexity::run_reach(spec.start_fen, opts);

    std::cout << "target=" << argv[1]
              << " dims=" << res.width << "x" << res.height
              << " start=\"" << res.start_fen << "\"\n";
    std::cout << "complete=" << (res.complete ? "true" : "false")
              << " stop_reason=" << res.stop_reason
              << " max_complete_depth=" << res.max_complete_depth
              << " total_positions=" << res.total_positions
              << " checkmates=" << res.total_checkmates
              << " stalemates=" << res.total_stalemates
              << " peak_mem_mb=" << std::fixed << std::setprecision(2)
              << (static_cast<double>(res.peak_mem_bytes) / (1024.0 * 1024.0))
              << " elapsed_sec=" << std::setprecision(3) << res.elapsed_sec << "\n";

    if (!quiet) {
        std::cout << "depth\tcount\tcumulative\tcheckmates\tstalemates\tstatus\n";
        for (const auto& d : res.depths) {
            std::cout << d.depth << "\t" << d.count << "\t" << d.cumulative << "\t"
                      << d.checkmates << "\t" << d.stalemates << "\t"
                      << (d.complete ? "complete" : "partial") << "\n";
        }
    }
    return 0;
}
