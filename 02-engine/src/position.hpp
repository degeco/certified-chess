#pragma once

#include "attacks.hpp"
#include "types.hpp"
#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace mchess {

enum class GameStatus : uint8_t {
    ONGOING = 0,
    CHECKMATE = 1,
    STALEMATE = 2
};

class Position {
public:
    Position() = default;

    static bool parse(std::string_view fen, Position& out, std::string* err = nullptr);
    static std::optional<Position> from_fen(std::string_view fen);

    std::string to_fen() const;

    int width() const { return w_; }
    int height() const { return h_; }
    bool is_8x8() const { return w_ == 8 && h_ == 8; }
    Color side_to_move() const { return stm_; }
    uint8_t castling_rights() const { return castling_; }
    int ep_square() const { return ep_sq_; }
    uint64_t hash() const { return hash_; }
    uint64_t board_mask() const { return board_mask_; }

    PieceType piece_at(int sq, Color* out_color = nullptr) const;
    PieceType piece_at(int file, int rank, Color* out_color = nullptr) const {
        return piece_at(make_sq(file, rank), out_color);
    }

    uint64_t pieces(Color c, PieceType pt) const { return bb_[c][pt]; }
    uint64_t occupancy(Color c) const { return occ_[c]; }
    uint64_t occupancy() const { return occ_[WHITE] | occ_[BLACK]; }
    int king_square(Color c) const { return lsb(bb_[c][KING]); }

    bool is_square_attacked(int sq, Color by_color, uint64_t occ_override) const;
    bool is_square_attacked(int sq, Color by_color) const {
        return is_square_attacked(sq, by_color, occupancy());
    }

    bool in_check(Color c) const {
        return is_square_attacked(king_square(c), ~c);
    }
    bool in_check() const { return in_check(stm_); }

    int legal_moves(Move* out) const;
    std::vector<Move> legal_moves() const;
    bool has_legal_moves() const;

    Position make_move(Move m) const;
    std::optional<Move> parse_move(std::string_view s) const;

    GameStatus status() const;
    bool is_terminal() const { return !has_legal_moves(); }
    bool is_checkmate() const { return status() == GameStatus::CHECKMATE; }
    bool is_stalemate() const { return status() == GameStatus::STALEMATE; }

    bool operator==(const Position& o) const;
    bool operator!=(const Position& o) const { return !(*this == o); }

private:
    uint64_t attackers_to(int sq, Color by_color, uint64_t occ) const;
    bool ep_capture_legal(int from_sq, int ep_target, int cap_pawn_sq, Color us) const;
    void put_piece(int sq, Color c, PieceType pt);
    void remove_piece(int sq, Color c, PieceType pt);
    uint64_t compute_hash() const;

    int w_ = 8;
    int h_ = 8;
    uint64_t board_mask_ = ~0ULL;

    uint64_t bb_[2][6]{};
    uint64_t occ_[2]{};
    std::array<uint8_t, 64> board_{}; // (color << 3) | piece_type, or NO_PIECE

    Color stm_ = WHITE;
    uint8_t castling_ = 0;
    int8_t ep_sq_ = NO_SQ;
    uint64_t hash_ = 0;
};

uint64_t perft(const Position& pos, int depth);
std::vector<std::pair<Move, uint64_t>> divide(const Position& pos, int depth);

} // namespace mchess
