#pragma once

#include "mchess.hpp"
#include <array>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace tb {

struct MaterialSig {
    // Indexed by [Color][PieceType] where PieceType is PAWN..KING (0..5)
    std::array<std::array<uint8_t, 6>, 2> count{};

    static std::optional<MaterialSig> parse(std::string_view s);
    static MaterialSig from_position(const mchess::Position& pos);

    std::string to_string() const;
    int total_pieces() const;
    int total_pawns() const;

    // Immediate child signatures reachable in 1 capture or 1 promotion (or capture+promo).
    std::vector<MaterialSig> dependencies() const;

    bool operator==(const MaterialSig& o) const { return count == o.count; }
    bool operator!=(const MaterialSig& o) const { return count != o.count; }
    bool operator<(const MaterialSig& o) const;
};

// Enumerate all valid signatures with 2 <= pieces <= max_pieces, sorted topologically
// by (total_pieces, total_pawns, sig).
std::vector<MaterialSig> enumerate_signatures(int max_pieces);

// Parse board dimension string like "4x4" or "5x5".
bool parse_board_size(std::string_view s, int& w, int& h);

} // namespace tb
