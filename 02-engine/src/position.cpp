#include "position.hpp"
#include <algorithm>
#include <cctype>
#include <cstdlib>

namespace mchess {

namespace {

constexpr uint8_t EMPTY_CELL = 0xFF;

bool is_digits(std::string_view sv) {
    if (sv.empty()) return false;
    for (char ch : sv) {
        if (ch < '0' || ch > '9') return false;
    }
    return true;
}

int parse_piece_char(char ch, Color& out_c, PieceType& out_pt) {
    switch (ch) {
        case 'P': out_c = WHITE; out_pt = PAWN; return 0;
        case 'N': out_c = WHITE; out_pt = KNIGHT; return 0;
        case 'B': out_c = WHITE; out_pt = BISHOP; return 0;
        case 'R': out_c = WHITE; out_pt = ROOK; return 0;
        case 'Q': out_c = WHITE; out_pt = QUEEN; return 0;
        case 'K': out_c = WHITE; out_pt = KING; return 0;
        case 'p': out_c = BLACK; out_pt = PAWN; return 0;
        case 'n': out_c = BLACK; out_pt = KNIGHT; return 0;
        case 'b': out_c = BLACK; out_pt = BISHOP; return 0;
        case 'r': out_c = BLACK; out_pt = ROOK; return 0;
        case 'q': out_c = BLACK; out_pt = QUEEN; return 0;
        case 'k': out_c = BLACK; out_pt = KING; return 0;
        default: return -1;
    }
}

inline void emit_pawn_move(Move*& it, int from, int to, int promo_rank) {
    if (sq_rank(to) == promo_rank) {
        *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), QUEEN};
        *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), ROOK};
        *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), BISHOP};
        *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), KNIGHT};
    } else {
        *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), NO_PIECE};
    }
}

} // namespace

PieceType Position::piece_at(int sq, Color* out_color) const {
    uint8_t cell = board_[sq];
    if (cell == EMPTY_CELL) return NO_PIECE;
    if (out_color) *out_color = static_cast<Color>(cell >> 3);
    return static_cast<PieceType>(cell & 7);
}

void Position::put_piece(int sq, Color c, PieceType pt) {
    uint64_t b = sq_bb(sq);
    bb_[c][pt] |= b;
    occ_[c] |= b;
    board_[sq] = static_cast<uint8_t>((c << 3) | pt);
    hash_ ^= tables().z_piece[c][pt][sq];
}

void Position::remove_piece(int sq, Color c, PieceType pt) {
    uint64_t b = sq_bb(sq);
    bb_[c][pt] ^= b;
    occ_[c] ^= b;
    board_[sq] = EMPTY_CELL;
    hash_ ^= tables().z_piece[c][pt][sq];
}

uint64_t Position::compute_hash() const {
    const Tables& t = tables();
    uint64_t h = t.z_dims[w_][h_];
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            uint64_t b = bb_[c][pt];
            while (b) {
                int sq = pop_lsb(b);
                h ^= t.z_piece[c][pt][sq];
            }
        }
    }
    if (stm_ == BLACK) h ^= t.z_stm;
    h ^= t.z_castling[castling_];
    if (ep_sq_ != NO_SQ) h ^= t.z_ep[ep_sq_];
    return h;
}

uint64_t Position::attackers_to(int sq, Color by_color, uint64_t occ) const {
    const Tables& t = tables();
    uint64_t att = 0;
    att |= t.pawn_att[~by_color][sq] & bb_[by_color][PAWN];
    att |= t.knight_att[sq] & bb_[by_color][KNIGHT];
    att |= t.king_att[sq] & bb_[by_color][KING];
    att |= bishop_attacks(sq, occ, board_mask_) & (bb_[by_color][BISHOP] | bb_[by_color][QUEEN]);
    att |= rook_attacks(sq, occ, board_mask_) & (bb_[by_color][ROOK] | bb_[by_color][QUEEN]);
    return att;
}

bool Position::is_square_attacked(int sq, Color by_color, uint64_t occ_override) const {
    const Tables& t = tables();
    if (t.pawn_att[~by_color][sq] & bb_[by_color][PAWN]) return true;
    if (t.knight_att[sq] & bb_[by_color][KNIGHT]) return true;
    if (t.king_att[sq] & bb_[by_color][KING]) return true;
    if (bishop_attacks(sq, occ_override, board_mask_) & (bb_[by_color][BISHOP] | bb_[by_color][QUEEN])) return true;
    if (rook_attacks(sq, occ_override, board_mask_) & (bb_[by_color][ROOK] | bb_[by_color][QUEEN])) return true;
    return false;
}

bool Position::ep_capture_legal(int from_sq, int ep_target, int cap_pawn_sq, Color us) const {
    const Tables& t = tables();
    Color them = ~us;
    int ksq = king_square(us);
    uint64_t occ_all = occupancy();
    uint64_t new_occ = (occ_all ^ sq_bb(from_sq) ^ sq_bb(cap_pawn_sq)) | sq_bb(ep_target);
    uint64_t not_cap = ~sq_bb(cap_pawn_sq);

    if (t.pawn_att[us][ksq] & bb_[them][PAWN] & not_cap) return false;
    if (t.knight_att[ksq] & bb_[them][KNIGHT]) return false;
    if (t.king_att[ksq] & bb_[them][KING]) return false;
    if (bishop_attacks(ksq, new_occ, board_mask_) & (bb_[them][BISHOP] | bb_[them][QUEEN])) return false;
    if (rook_attacks(ksq, new_occ, board_mask_) & (bb_[them][ROOK] | bb_[them][QUEEN])) return false;
    return true;
}

bool Position::parse(std::string_view fen, Position& out, std::string* err) {
    auto fail = [&](const char* msg) -> bool {
        if (err) *err = msg;
        return false;
    };

    // Split into fields separated by single ASCII spaces.
    std::string_view fields[6];
    int nf = 0;
    size_t pos = 0;
    while (pos < fen.size()) {
        size_t sp = fen.find(' ', pos);
        if (sp == std::string_view::npos) {
            if (nf >= 6) return fail("too many fields");
            fields[nf++] = fen.substr(pos);
            break;
        }
        if (sp == pos) return fail("empty field / extra space");
        if (nf >= 6) return fail("too many fields");
        fields[nf++] = fen.substr(pos, sp - pos);
        pos = sp + 1;
        if (pos == fen.size()) return fail("trailing space");
    }

    if (nf < 4) return fail("fewer than 4 fields");
    if (nf >= 5 && !is_digits(fields[4])) return fail("invalid halfmove clock");
    if (nf >= 6 && !is_digits(fields[5])) return fail("invalid fullmove number");

    Position p;
    p.board_.fill(EMPTY_CELL);

    // 1. Placement
    std::string_view placement = fields[0];
    if (placement.empty()) return fail("empty placement");

    std::string_view rank_strs[8];
    int h = 0;
    size_t rpos = 0;
    while (true) {
        size_t sl = placement.find('/', rpos);
        if (h >= 8) return fail("too many ranks");
        if (sl == std::string_view::npos) {
            rank_strs[h++] = placement.substr(rpos);
            break;
        }
        rank_strs[h++] = placement.substr(rpos, sl - rpos);
        rpos = sl + 1;
    }

    if (h < 3 || h > 8) return fail("height out of range 3..8");
    p.h_ = h;

    int w = -1;
    int king_count[2] = {0, 0};

    for (int i = 0; i < h; ++i) {
        int rank = h - 1 - i;
        std::string_view rs = rank_strs[i];
        if (rs.empty()) return fail("empty rank");
        int file = 0;
        bool prev_digit = false;
        for (char ch : rs) {
            if (ch >= '1' && ch <= '8') {
                if (prev_digit) return fail("adjacent digits in rank");
                file += (ch - '0');
                if (file > 8) return fail("rank wider than 8");
                prev_digit = true;
            } else {
                prev_digit = false;
                Color c = WHITE;
                PieceType pt = NO_PIECE;
                if (parse_piece_char(ch, c, pt) != 0) return fail("invalid piece char");
                if (file >= 8) return fail("rank wider than 8");
                if (pt == PAWN && (rank == 0 || rank == h - 1)) {
                    return fail("pawn on first or last rank");
                }
                if (pt == KING) ++king_count[c];
                p.put_piece(make_sq(file, rank), c, pt);
                ++file;
            }
        }
        if (w == -1) {
            if (file < 3 || file > 8) return fail("width out of range 3..8");
            w = file;
        } else if (file != w) {
            return fail("inconsistent rank width");
        }
    }
    p.w_ = w;
    p.board_mask_ = make_board_mask(w, h);

    if (king_count[WHITE] != 1 || king_count[BLACK] != 1) {
        return fail("must have exactly one king per side");
    }

    // 2. Side to move
    if (fields[1] == "w") p.stm_ = WHITE;
    else if (fields[1] == "b") p.stm_ = BLACK;
    else return fail("invalid side to move");

    // 3. Castling
    std::string_view cast = fields[2];
    if (cast.empty()) return fail("empty castling field");
    if (cast != "-") {
        if (!p.is_8x8()) return fail("castling not allowed off 8x8");
        int order = -1;
        for (char ch : cast) {
            int idx = -1;
            uint8_t bit = 0;
            if (ch == 'K') { idx = 0; bit = WK_CASTLE; }
            else if (ch == 'Q') { idx = 1; bit = WQ_CASTLE; }
            else if (ch == 'k') { idx = 2; bit = BK_CASTLE; }
            else if (ch == 'q') { idx = 3; bit = BQ_CASTLE; }
            else return fail("invalid castling char");
            if (idx <= order) return fail("castling chars out of order or duplicate");
            order = idx;
            p.castling_ |= bit;
        }
        auto has = [&](int f, int r, Color c, PieceType pt) {
            Color pc = WHITE;
            return p.piece_at(make_sq(f, r), &pc) == pt && pc == c;
        };
        if ((p.castling_ & WK_CASTLE) && !(has(4, 0, WHITE, KING) && has(7, 0, WHITE, ROOK)))
            return fail("K castling right without e1 king / h1 rook");
        if ((p.castling_ & WQ_CASTLE) && !(has(4, 0, WHITE, KING) && has(0, 0, WHITE, ROOK)))
            return fail("Q castling right without e1 king / a1 rook");
        if ((p.castling_ & BK_CASTLE) && !(has(4, 7, BLACK, KING) && has(7, 7, BLACK, ROOK)))
            return fail("k castling right without e8 king / h8 rook");
        if ((p.castling_ & BQ_CASTLE) && !(has(4, 7, BLACK, KING) && has(0, 7, BLACK, ROOK)))
            return fail("q castling right without e8 king / a8 rook");
    }

    // Non-side-to-move king must not be in check
    if (p.in_check(~p.stm_)) {
        return fail("non-side-to-move king is in check");
    }

    // 4. En passant
    std::string_view ep = fields[3];
    if (ep.empty()) return fail("empty ep field");
    if (ep != "-") {
        if (!p.is_8x8()) return fail("en passant not allowed off 8x8");
        int ep_sq = parse_sq(ep, 8, 8);
        if (ep_sq == NO_SQ) return fail("invalid ep square");

        int expected_rank = (p.stm_ == WHITE) ? 5 : 2;
        if (sq_rank(ep_sq) != expected_rank) return fail("ep square on wrong rank");
        int behind_sq = (p.stm_ == WHITE) ? (ep_sq + 8) : (ep_sq - 8);
        int cap_pawn_sq = (p.stm_ == WHITE) ? (ep_sq - 8) : (ep_sq + 8);
        if (p.piece_at(ep_sq) != NO_PIECE || p.piece_at(behind_sq) != NO_PIECE) {
            return fail("ep target or origin square occupied");
        }
        Color cap_color = WHITE;
        if (p.piece_at(cap_pawn_sq, &cap_color) != PAWN || cap_color != ~p.stm_) {
            return fail("no enemy pawn for ep square");
        }

        // Canonicalize: keep ep_sq only if at least one legal ep capture exists.
        bool any_legal = false;
        uint64_t cand_pawns = tables().pawn_att[~p.stm_][ep_sq] & p.bb_[p.stm_][PAWN];
        while (cand_pawns) {
            int from_sq = pop_lsb(cand_pawns);
            if (p.ep_capture_legal(from_sq, ep_sq, cap_pawn_sq, p.stm_)) {
                any_legal = true;
                break;
            }
        }
        if (any_legal) {
            p.ep_sq_ = static_cast<int8_t>(ep_sq);
        }
    }

    p.hash_ = p.compute_hash();
    out = p;
    return true;
}

std::optional<Position> Position::from_fen(std::string_view fen) {
    Position p;
    if (!parse(fen, p)) return std::nullopt;
    return p;
}

std::string Position::to_fen() const {
    std::string s;
    s.reserve(96);
    for (int r = h_ - 1; r >= 0; --r) {
        int empty = 0;
        for (int f = 0; f < w_; ++f) {
            Color c = WHITE;
            PieceType pt = piece_at(make_sq(f, r), &c);
            if (pt == NO_PIECE) {
                ++empty;
            } else {
                if (empty > 0) {
                    s.push_back(static_cast<char>('0' + empty));
                    empty = 0;
                }
                s.push_back(piece_to_char(c, pt));
            }
        }
        if (empty > 0) s.push_back(static_cast<char>('0' + empty));
        if (r > 0) s.push_back('/');
    }

    s.push_back(' ');
    s.push_back(stm_ == WHITE ? 'w' : 'b');
    s.push_back(' ');

    if (castling_ == 0) {
        s.push_back('-');
    } else {
        if (castling_ & WK_CASTLE) s.push_back('K');
        if (castling_ & WQ_CASTLE) s.push_back('Q');
        if (castling_ & BK_CASTLE) s.push_back('k');
        if (castling_ & BQ_CASTLE) s.push_back('q');
    }

    s.push_back(' ');
    if (ep_sq_ == NO_SQ) {
        s.push_back('-');
    } else {
        s.append(sq_to_string(ep_sq_));
    }
    return s;
}

int Position::legal_moves(Move* out) const {
    const Tables& t = tables();
    Move* it = out;

    Color us = stm_;
    Color them = ~us;
    int ksq = king_square(us);
    uint64_t occ_all = occupancy();
    uint64_t occ_us = occ_[us];
    uint64_t occ_them = occ_[them];

    uint64_t checkers = attackers_to(ksq, them, occ_all);
    int num_checkers = popcount(checkers);

    // 1. King moves
    uint64_t occ_no_king = occ_all ^ sq_bb(ksq);
    uint64_t k_targets = t.king_att[ksq] & board_mask_ & ~occ_us;
    while (k_targets) {
        int to = pop_lsb(k_targets);
        if (!is_square_attacked(to, them, occ_no_king)) {
            *it++ = Move{static_cast<uint8_t>(ksq), static_cast<uint8_t>(to), NO_PIECE};
        }
    }

    if (num_checkers >= 2) {
        return static_cast<int>(it - out);
    }

    // 2. Castling
    if (num_checkers == 0 && is_8x8()) {
        if (us == WHITE) {
            if ((castling_ & WK_CASTLE) &&
                !(occ_all & (sq_bb(5) | sq_bb(6))) &&
                !is_square_attacked(5, BLACK, occ_all) &&
                !is_square_attacked(6, BLACK, occ_all)) {
                *it++ = Move{4, 6, NO_PIECE};
            }
            if ((castling_ & WQ_CASTLE) &&
                !(occ_all & (sq_bb(1) | sq_bb(2) | sq_bb(3))) &&
                !is_square_attacked(3, BLACK, occ_all) &&
                !is_square_attacked(2, BLACK, occ_all)) {
                *it++ = Move{4, 2, NO_PIECE};
            }
        } else {
            if ((castling_ & BK_CASTLE) &&
                !(occ_all & (sq_bb(61) | sq_bb(62))) &&
                !is_square_attacked(61, WHITE, occ_all) &&
                !is_square_attacked(62, WHITE, occ_all)) {
                *it++ = Move{60, 62, NO_PIECE};
            }
            if ((castling_ & BQ_CASTLE) &&
                !(occ_all & (sq_bb(57) | sq_bb(58) | sq_bb(59))) &&
                !is_square_attacked(59, WHITE, occ_all) &&
                !is_square_attacked(58, WHITE, occ_all)) {
                *it++ = Move{60, 58, NO_PIECE};
            }
        }
    }

    // 3. Pinned pieces
    uint64_t pinned = 0;
    uint64_t rq = bb_[them][ROOK] | bb_[them][QUEEN];
    uint64_t bq = bb_[them][BISHOP] | bb_[them][QUEEN];
    uint64_t pinners = (rook_attacks(ksq, 0, board_mask_) & rq)
                     | (bishop_attacks(ksq, 0, board_mask_) & bq);
    while (pinners) {
        int psq = pop_lsb(pinners);
        uint64_t b = t.between[ksq][psq] & occ_all;
        if (b && (b & (b - 1)) == 0 && (b & occ_us)) {
            pinned |= b;
        }
    }

    uint64_t target_mask;
    if (num_checkers == 0) {
        target_mask = board_mask_ & ~occ_us;
    } else {
        int csq = lsb(checkers);
        target_mask = (t.between[ksq][csq] | checkers) & ~occ_us;
    }

    // 4. Pawns
    int up = (us == WHITE) ? 8 : -8;
    int promo_rank = (us == WHITE) ? (h_ - 1) : 0;
    int start_rank = (us == WHITE) ? 1 : 6;
    bool allow_double = is_8x8();

    uint64_t pawns = bb_[us][PAWN];
    if (num_checkers == 1) pawns &= ~pinned;

    while (pawns) {
        int from = pop_lsb(pawns);
        uint64_t pin_line = (pinned & sq_bb(from)) ? t.line[ksq][from] : ~0ULL;

        int to1 = from + up;
        if (!(occ_all & sq_bb(to1))) {
            if (sq_bb(to1) & target_mask & pin_line) {
                emit_pawn_move(it, from, to1, promo_rank);
            }
            if (allow_double && sq_rank(from) == start_rank) {
                int to2 = to1 + up;
                if (!(occ_all & sq_bb(to2)) && (sq_bb(to2) & target_mask & pin_line)) {
                    *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to2), NO_PIECE};
                }
            }
        }

        uint64_t caps = t.pawn_att[us][from] & occ_them & target_mask & pin_line;
        while (caps) {
            int to = pop_lsb(caps);
            emit_pawn_move(it, from, to, promo_rank);
        }
    }

    // En passant
    if (ep_sq_ != NO_SQ) {
        int cap_pawn_sq = (us == WHITE) ? (ep_sq_ - 8) : (ep_sq_ + 8);
        uint64_t ep_cand = t.pawn_att[~us][ep_sq_] & bb_[us][PAWN];
        while (ep_cand) {
            int from = pop_lsb(ep_cand);
            if (ep_capture_legal(from, ep_sq_, cap_pawn_sq, us)) {
                *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(ep_sq_), NO_PIECE};
            }
        }
    }

    // 5. Knights
    uint64_t knights = bb_[us][KNIGHT] & ~pinned;
    while (knights) {
        int from = pop_lsb(knights);
        uint64_t targets = t.knight_att[from] & target_mask;
        while (targets) {
            int to = pop_lsb(targets);
            *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), NO_PIECE};
        }
    }

    // 6. Bishops
    uint64_t bishops = bb_[us][BISHOP];
    if (num_checkers == 1) bishops &= ~pinned;
    while (bishops) {
        int from = pop_lsb(bishops);
        uint64_t targets = bishop_attacks(from, occ_all, board_mask_) & target_mask;
        if (pinned & sq_bb(from)) targets &= t.line[ksq][from];
        while (targets) {
            int to = pop_lsb(targets);
            *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), NO_PIECE};
        }
    }

    // 7. Rooks
    uint64_t rooks = bb_[us][ROOK];
    if (num_checkers == 1) rooks &= ~pinned;
    while (rooks) {
        int from = pop_lsb(rooks);
        uint64_t targets = rook_attacks(from, occ_all, board_mask_) & target_mask;
        if (pinned & sq_bb(from)) targets &= t.line[ksq][from];
        while (targets) {
            int to = pop_lsb(targets);
            *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), NO_PIECE};
        }
    }

    // 8. Queens
    uint64_t queens = bb_[us][QUEEN];
    if (num_checkers == 1) queens &= ~pinned;
    while (queens) {
        int from = pop_lsb(queens);
        uint64_t targets = queen_attacks(from, occ_all, board_mask_) & target_mask;
        if (pinned & sq_bb(from)) targets &= t.line[ksq][from];
        while (targets) {
            int to = pop_lsb(targets);
            *it++ = Move{static_cast<uint8_t>(from), static_cast<uint8_t>(to), NO_PIECE};
        }
    }

    return static_cast<int>(it - out);
}

std::vector<Move> Position::legal_moves() const {
    Move buf[MAX_MOVES];
    int n = legal_moves(buf);
    return std::vector<Move>(buf, buf + n);
}

bool Position::has_legal_moves() const {
    Move buf[MAX_MOVES];
    return legal_moves(buf) > 0;
}

Position Position::make_move(Move m) const {
    const Tables& t = tables();
    Position next = *this;

    Color us = stm_;
    Color them = ~us;
    int from = m.from;
    int to = m.to;
    PieceType pt = piece_at(from);
    PieceType cap = piece_at(to);

    if (ep_sq_ != NO_SQ) {
        next.hash_ ^= t.z_ep[ep_sq_];
        next.ep_sq_ = NO_SQ;
    }
    next.hash_ ^= t.z_castling[castling_];

    if (cap != NO_PIECE) {
        next.remove_piece(to, them, cap);
    }

    next.remove_piece(from, us, pt);
    next.put_piece(to, us, (m.promo != NO_PIECE) ? m.promo : pt);

    if (pt == PAWN && to == ep_sq_) {
        int cap_sq = (us == WHITE) ? (to - 8) : (to + 8);
        next.remove_piece(cap_sq, them, PAWN);
    } else if (pt == KING && std::abs(sq_file(to) - sq_file(from)) == 2) {
        int rank = sq_rank(from);
        if (sq_file(to) == 6) {
            next.remove_piece(make_sq(7, rank), us, ROOK);
            next.put_piece(make_sq(5, rank), us, ROOK);
        } else {
            next.remove_piece(make_sq(0, rank), us, ROOK);
            next.put_piece(make_sq(3, rank), us, ROOK);
        }
    }

    if (is_8x8()) {
        next.castling_ &= t.castling_mask[from] & t.castling_mask[to];
        if (pt == PAWN && std::abs(to - from) == 16) {
            int cand_ep = (from + to) / 2;
            int f = sq_file(to);
            uint8_t enemy_pawn = static_cast<uint8_t>((them << 3) | PAWN);
            bool any_legal = false;
            if (f > 0 && next.board_[to - 1] == enemy_pawn &&
                next.ep_capture_legal(to - 1, cand_ep, to, them)) {
                any_legal = true;
            } else if (f < 7 && next.board_[to + 1] == enemy_pawn &&
                       next.ep_capture_legal(to + 1, cand_ep, to, them)) {
                any_legal = true;
            }
            if (any_legal) {
                next.ep_sq_ = static_cast<int8_t>(cand_ep);
                next.hash_ ^= t.z_ep[cand_ep];
            }
        }
    }

    next.hash_ ^= t.z_castling[next.castling_];
    next.stm_ = them;
    next.hash_ ^= t.z_stm;
    return next;
}

std::optional<Move> Position::parse_move(std::string_view s) const {
    if (s.size() != 4 && s.size() != 5) return std::nullopt;
    int from = parse_sq(s.substr(0, 2), w_, h_);
    int to = parse_sq(s.substr(2, 2), w_, h_);
    if (from == NO_SQ || to == NO_SQ) return std::nullopt;

    PieceType promo = NO_PIECE;
    if (s.size() == 5) {
        switch (s[4]) {
            case 'q': promo = QUEEN; break;
            case 'r': promo = ROOK; break;
            case 'b': promo = BISHOP; break;
            case 'n': promo = KNIGHT; break;
            default: return std::nullopt;
        }
    }

    Move target{static_cast<uint8_t>(from), static_cast<uint8_t>(to), promo};
    Move buf[MAX_MOVES];
    int n = legal_moves(buf);
    for (int i = 0; i < n; ++i) {
        if (buf[i] == target) return target;
    }
    return std::nullopt;
}

GameStatus Position::status() const {
    if (has_legal_moves()) return GameStatus::ONGOING;
    return in_check() ? GameStatus::CHECKMATE : GameStatus::STALEMATE;
}

bool Position::operator==(const Position& o) const {
    if (w_ != o.w_ || h_ != o.h_ || stm_ != o.stm_ ||
        castling_ != o.castling_ || ep_sq_ != o.ep_sq_ || hash_ != o.hash_) {
        return false;
    }
    for (int c = 0; c < 2; ++c) {
        for (int pt = 0; pt < 6; ++pt) {
            if (bb_[c][pt] != o.bb_[c][pt]) return false;
        }
    }
    return true;
}

uint64_t perft(const Position& pos, int depth) {
    if (depth <= 0) return 1;
    Move buf[MAX_MOVES];
    int n = pos.legal_moves(buf);
    if (depth == 1) return static_cast<uint64_t>(n);

    uint64_t nodes = 0;
    for (int i = 0; i < n; ++i) {
        nodes += perft(pos.make_move(buf[i]), depth - 1);
    }
    return nodes;
}

std::vector<std::pair<Move, uint64_t>> divide(const Position& pos, int depth) {
    Move buf[MAX_MOVES];
    int n = pos.legal_moves(buf);

    std::vector<std::pair<Move, uint64_t>> res;
    res.reserve(n);
    for (int i = 0; i < n; ++i) {
        uint64_t cnt = (depth <= 1) ? 1 : perft(pos.make_move(buf[i]), depth - 1);
        res.emplace_back(buf[i], cnt);
    }
    std::sort(res.begin(), res.end(), [](const auto& a, const auto& b) {
        return a.first.to_string() < b.first.to_string();
    });
    return res;
}

} // namespace mchess
