# `02-engine` C++17 Library API

A small, dependency-free C++17 rules engine for chess on boards from `3x3` to `8x8` (full FIDE rules on `8x8`, mini rules off `8x8`; no 50-move, repetition, or insufficient-material rules).

## Building & Linking

Build the static library and CLI from `02-engine/`:

```sh
make -j4
```

Link your C++17 code against `build/libmchess.a` with `-I<repo>/02-engine/src`:

```sh
g++ -O2 -std=c++17 -I../02-engine/src my_tool.cpp ../02-engine/build/libmchess.a -o my_tool
```

Include the umbrella header:

```cpp
#include "mchess.hpp"
using namespace mchess;
```

No global initialization call is required; attack and Zobrist tables initialize automatically on first use.

## Core Types (`src/types.hpp`)

- `Color`: `WHITE = 0`, `BLACK = 1`, `~c` flips color.
- `PieceType`: `PAWN`, `KNIGHT`, `BISHOP`, `ROOK`, `QUEEN`, `KING`, `NO_PIECE`.
- `CastlingRight`: `WK_CASTLE`, `WQ_CASTLE`, `BK_CASTLE`, `BQ_CASTLE`.
- Squares: `0..63` encoded as `(rank << 3) | file` (`0 <= file < width`, `0 <= rank < height`). Helpers: `make_sq(f, r)`, `sq_file(sq)`, `sq_rank(sq)`, `sq_to_string(sq)`, `parse_sq(sv, w, h)`. `NO_SQ = -1`.
- `Move`: `{ uint8_t from; uint8_t to; PieceType promo; }` (`promo == NO_PIECE` for non-promotions). `m.to_string()` formats `<from><to>[promo]`. `MAX_MOVES = 256`.
- `GameStatus`: `ONGOING`, `CHECKMATE`, `STALEMATE`.

## `Position` (`src/position.hpp`)

### Parsing & Canonical Formatting
- `Position::from_fen(std::string_view fen)` -> `std::optional<Position>`
- `Position::parse(std::string_view fen, Position& out, std::string* err = nullptr)` -> `bool`
  - Accepts 4-field canonical strings (`<placement> <stm> <castling> <ep>`) and 5/6-field FENs with trailing halfmove/fullmove counters (ignored).
  - Canonicalizes `ep` to `-` if no legal en passant capture exists.
  - Rejects invalid dimensions, missing/extra kings, pawns on first/last rank, opponent in check, or castling/ep off `8x8`.
- `pos.to_fen()` -> `std::string` (canonical 4-field position string).

### Board State & Hashing
- `pos.width()`, `pos.height()`, `pos.is_8x8()`
- `pos.side_to_move()`, `pos.castling_rights()`, `pos.ep_square()`
- `pos.piece_at(sq, Color* out_color = nullptr)`, `pos.piece_at(file, rank, Color* out_color = nullptr)`
- `pos.pieces(Color c, PieceType pt)`, `pos.occupancy(Color c)`, `pos.occupancy()`, `pos.board_mask()`, `pos.king_square(Color c)`
- `pos.hash()` -> `uint64_t` (64-bit Zobrist hash including board dimensions, pieces, side to move, castling rights, and canonical `ep` square).

### Rules, Legal Moves & Transitions
- `pos.is_square_attacked(int sq, Color by_color)`
- `pos.in_check()`, `pos.in_check(Color c)`
- `pos.legal_moves(Move* out)` -> `int` (writes into caller buffer of size `MAX_MOVES`, zero heap allocation)
- `pos.legal_moves()` -> `std::vector<Move>`
- `pos.has_legal_moves()` -> `bool`
- `pos.status()`, `pos.is_terminal()`, `pos.is_checkmate()`, `pos.is_stalemate()`
- `pos.parse_move(std::string_view s)` -> `std::optional<Move>` (parses `<from><to>[promo]` and verifies legality in `pos`)
- `pos.make_move(Move m)` -> `Position` (returns new `Position` by value; `m` must be legal in `pos`; incrementally updates Zobrist hash and canonical `ep`)

### Perft Helpers
- `perft(const Position& pos, int depth)` -> `uint64_t`
- `divide(const Position& pos, int depth)` -> `std::vector<std::pair<Move, uint64_t>>` (sorted by move string)

## Minimal Example

```cpp
#include "mchess.hpp"
#include <iostream>

int main() {
    auto pos = mchess::Position::from_fen("rqkr/pppp/PPPP/RQKR w - -");
    if (!pos) return 1;

    mchess::Move buf[mchess::MAX_MOVES];
    int n = pos->legal_moves(buf);
    for (int i = 0; i < n; ++i) {
        mchess::Position next = pos->make_move(buf[i]);
        std::cout << buf[i].to_string() << "\t" << next.to_fen()
                  << "\t" << next.hash() << "\n";
    }
}
```
