#include "estimate.hpp"
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

static void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << " <board_name_or_fen> [options]\n"
              << "  --samples <N>   Number of i.i.d. samples (default 1000000)\n"
              << "  --seed <S>      PRNG seed (default 42)\n"
              << "  --exact-check   Also run brute-force exact count (3x3 only)\n";
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

    uint64_t samples = 1000000;
    uint64_t seed = 42;
    bool exact_check = false;
    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--samples" && i + 1 < argc) {
            samples = std::strtoull(argv[++i], nullptr, 10);
        } else if (arg == "--seed" && i + 1 < argc) {
            seed = std::strtoull(argv[++i], nullptr, 10);
        } else if (arg == "--exact-check") {
            exact_check = true;
        } else {
            print_usage(argv[0]);
            return 1;
        }
    }

    complexity::StaticSpaceSampler sampler(spec);
    complexity::EstimateResult res = sampler.run(samples, seed);

    std::cout << "target=" << argv[1]
              << " dims=" << res.width << "x" << res.height
              << " samples=" << res.samples
              << " seed=" << res.seed << "\n";
    std::cout << std::scientific << std::setprecision(6)
              << "U_exact=" << static_cast<double>(res.superset_size)
              << " accepted=" << res.accepted_base
              << " (" << std::fixed << std::setprecision(4)
              << (100.0 * static_cast<double>(res.accepted_base) / static_cast<double>(res.samples))
              << "%)"
              << " mean_F=" << std::setprecision(6) << static_cast<double>(res.mean_F)
              << " se_F=" << static_cast<double>(res.se_F) << "\n";
    std::cout << std::scientific << std::setprecision(6)
              << "estimate=" << static_cast<double>(res.estimate)
              << " se=" << static_cast<double>(res.se_estimate)
              << " ci95=[" << static_cast<double>(res.ci95_low)
              << ", " << static_cast<double>(res.ci95_high) << "]"
              << " rel_ci95_pct=" << std::fixed << std::setprecision(4) << res.rel_ci95_pct << "%"
              << " elapsed_sec=" << std::setprecision(3) << res.elapsed_sec << "\n";

    if (exact_check) {
        auto ex = complexity::brute_force_exact_static_off8(spec);
        std::cout << "exact_U=" << ex.superset_U << " exact_L=" << ex.legal_L
                  << " in_ci95="
                  << ((static_cast<long double>(ex.legal_L) >= res.ci95_low &&
                       static_cast<long double>(ex.legal_L) <= res.ci95_high)
                          ? "true"
                          : "false")
                  << "\n";
    }
    return 0;
}
