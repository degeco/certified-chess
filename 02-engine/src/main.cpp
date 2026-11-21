#include "mchess.hpp"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <random>
#include <string>
#include <vector>

namespace {

using namespace mchess;

uint64_t rand_range(std::mt19937_64& rng, uint64_t bound) {
    return rng() % bound;
}

std::string build_raw_fen(const char board[8][8], int w, int h, Color stm, uint8_t castling) {
    std::string s;
    for (int r = h - 1; r >= 0; --r) {
        int empty = 0;
        for (int f = 0; f < w; ++f) {
            char ch = board[r][f];
            if (ch == 0) {
                ++empty;
            } else {
                if (empty > 0) {
                    s.push_back(static_cast<char>('0' + empty));
                    empty = 0;
                }
                s.push_back(ch);
            }
        }
        if (empty > 0) s.push_back(static_cast<char>('0' + empty));
        if (r > 0) s.push_back('/');
    }
    s.push_back(' ');
    s.push_back(stm == WHITE ? 'w' : 'b');
    s.push_back(' ');
    if (castling == 0) {
        s.push_back('-');
    } else {
        if (castling & WK_CASTLE) s.push_back('K');
        if (castling & WQ_CASTLE) s.push_back('Q');
        if (castling & BK_CASTLE) s.push_back('k');
        if (castling & BQ_CASTLE) s.push_back('q');
    }
    s.append(" -");
    return s;
}

Position generate_random_position(int w, int h, std::mt19937_64& rng) {
    static constexpr char W_EXTRA[5] = {'P', 'N', 'B', 'R', 'Q'};
    static constexpr char B_EXTRA[5] = {'p', 'n', 'b', 'r', 'q'};

    while (true) {
        char board[8][8]{};
        uint8_t castling = 0;

        bool castle_setup = (w == 8 && h == 8 && rand_range(rng, 4) == 0);
        if (castle_setup) {
            board[0][4] = 'K';
            board[7][4] = 'k';
            if (rand_range(rng, 2) == 0) { board[0][7] = 'R'; castling |= WK_CASTLE; }
            if (rand_range(rng, 2) == 0) { board[0][0] = 'R'; castling |= WQ_CASTLE; }
            if (rand_range(rng, 2) == 0) { board[7][7] = 'r'; castling |= BK_CASTLE; }
            if (rand_range(rng, 2) == 0) { board[7][0] = 'r'; castling |= BQ_CASTLE; }
            // Add a couple of pawns on ranks 2 and 7 to encourage double steps / ep
            for (int f = 0; f < 8; ++f) {
                if (rand_range(rng, 3) == 0) board[1][f] = 'P';
                if (rand_range(rng, 3) == 0) board[6][f] = 'p';
            }
        } else {
            int wk_f = static_cast<int>(rand_range(rng, w));
            int wk_r = static_cast<int>(rand_range(rng, h));
            int bk_f = static_cast<int>(rand_range(rng, w));
            int bk_r = static_cast<int>(rand_range(rng, h));
            if (std::abs(wk_f - bk_f) <= 1 && std::abs(wk_r - bk_r) <= 1) continue;
            board[wk_r][wk_f] = 'K';
            board[bk_r][bk_f] = 'k';
        }

        std::vector<std::pair<int, int>> empty_sqs;
        empty_sqs.reserve(w * h);
        for (int r = 0; r < h; ++r) {
            for (int f = 0; f < w; ++f) {
                if (board[r][f] == 0) empty_sqs.emplace_back(f, r);
            }
        }

        int max_extra = std::min(static_cast<int>(empty_sqs.size()), (w * h) / 2 + 2);
        int extra = 0;
        if (max_extra > 0) {
            if (rand_range(rng, 3) == 0) {
                extra = static_cast<int>(rand_range(rng, std::min(4, max_extra) + 1));
            } else {
                extra = static_cast<int>(rand_range(rng, max_extra + 1));
            }
        }

        for (int i = 0; i < extra && !empty_sqs.empty(); ++i) {
            size_t idx = static_cast<size_t>(rand_range(rng, empty_sqs.size()));
            auto [f, r] = empty_sqs[idx];
            empty_sqs[idx] = empty_sqs.back();
            empty_sqs.pop_back();

            bool is_white = (rand_range(rng, 2) == 0);
            int p_idx;
            if (r == 0 || r == h - 1) {
                p_idx = 1 + static_cast<int>(rand_range(rng, 4)); // N, B, R, Q
            } else {
                uint64_t roll = rand_range(rng, 10);
                if (roll < 4) p_idx = 0; // P
                else if (roll < 6) p_idx = 1; // N
                else if (roll < 8) p_idx = 2; // B
                else if (roll < 9) p_idx = 3; // R
                else p_idx = 4; // Q
            }
            board[r][f] = is_white ? W_EXTRA[p_idx] : B_EXTRA[p_idx];
        }

        Color stm = (rand_range(rng, 2) == 0) ? WHITE : BLACK;
        std::string fen = build_raw_fen(board, w, h, stm, castling);
        auto opt_pos = Position::from_fen(fen);
        if (!opt_pos) continue;

        Position pos = *opt_pos;
        int plies = static_cast<int>(rand_range(rng, 13));
        Move buf[MAX_MOVES];
        for (int ply = 0; ply < plies; ++ply) {
            int n = pos.legal_moves(buf);
            if (n == 0) break;
            pos = pos.make_move(buf[rand_range(rng, static_cast<uint64_t>(n))]);
        }
        return pos;
    }
}

void print_usage() {
    std::cerr << "Usage:\n"
              << "  mchess perft \"<position>\" <depth>\n"
              << "  mchess divide \"<position>\" <depth>\n"
              << "  mchess moves \"<position>\"\n"
              << "  mchess batch\n"
              << "  mchess random <W> <H> <count> <seed>\n";
}

} // namespace

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    if (argc < 2) {
        print_usage();
        return 1;
    }

    std::string cmd = argv[1];

    if (cmd == "perft") {
        if (argc != 4) { print_usage(); return 1; }
        std::string err;
        Position pos;
        if (!Position::parse(argv[2], pos, &err)) {
            std::cerr << "Invalid position: " << err << '\n';
            return 1;
        }
        int depth = std::atoi(argv[3]);
        if (depth < 0) {
            std::cerr << "Invalid depth\n";
            return 1;
        }
        std::cout << perft(pos, depth) << '\n';
        return 0;
    }

    if (cmd == "divide") {
        if (argc != 4) { print_usage(); return 1; }
        std::string err;
        Position pos;
        if (!Position::parse(argv[2], pos, &err)) {
            std::cerr << "Invalid position: " << err << '\n';
            return 1;
        }
        int depth = std::atoi(argv[3]);
        if (depth < 1) {
            std::cerr << "Depth must be >= 1\n";
            return 1;
        }
        auto res = divide(pos, depth);
        for (const auto& [m, cnt] : res) {
            std::cout << m.to_string() << ' ' << cnt << '\n';
        }
        return 0;
    }

    if (cmd == "moves") {
        if (argc != 3) { print_usage(); return 1; }
        std::string err;
        Position pos;
        if (!Position::parse(argv[2], pos, &err)) {
            std::cerr << "Invalid position: " << err << '\n';
            return 1;
        }
        auto moves = pos.legal_moves();
        std::vector<std::pair<std::string, std::string>> out;
        out.reserve(moves.size());
        for (const auto& m : moves) {
            out.emplace_back(m.to_string(), pos.make_move(m).to_fen());
        }
        std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) {
            return a.first < b.first;
        });
        for (const auto& [ms, fs] : out) {
            std::cout << ms << '\t' << fs << '\n';
        }
        return 0;
    }

    if (cmd == "batch") {
        if (argc != 2) { print_usage(); return 1; }
        std::string line;
        while (std::getline(std::cin, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            Position pos;
            if (!Position::parse(line, pos)) {
                std::cout << line << "\tERROR\n";
                continue;
            }
            auto moves = pos.legal_moves();
            std::vector<std::pair<std::string, std::string>> out;
            out.reserve(moves.size());
            for (const auto& m : moves) {
                out.emplace_back(m.to_string(), pos.make_move(m).to_fen());
            }
            std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) {
                return a.first < b.first;
            });
            std::cout << pos.to_fen() << '\t';
            for (size_t i = 0; i < out.size(); ++i) {
                if (i > 0) std::cout << '|';
                std::cout << out[i].first << ':' << out[i].second;
            }
            std::cout << '\n';
        }
        return 0;
    }

    if (cmd == "random") {
        if (argc != 6) { print_usage(); return 1; }
        int w = std::atoi(argv[2]);
        int h = std::atoi(argv[3]);
        long long count = std::atoll(argv[4]);
        uint64_t seed = std::strtoull(argv[5], nullptr, 10);
        if (w < 3 || w > 8 || h < 3 || h > 8 || count < 0) {
            std::cerr << "Invalid arguments for random\n";
            return 1;
        }
        std::mt19937_64 rng(seed);
        for (long long i = 0; i < count; ++i) {
            std::cout << generate_random_position(w, h, rng).to_fen() << '\n';
        }
        return 0;
    }

    print_usage();
    return 1;
}
