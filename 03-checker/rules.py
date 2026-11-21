"""Trusted rules implementation for small-board and 8x8 chess (SPEC v1.2).

Designed for clarity and easy human auditing:
- Flat immutable mailbox board of size W x H (3 <= W, H <= 8).
- Index = rank * W + file, with file 0 = 'a' and rank 0 = '1'.
- 8x8 uses full FIDE movement (pawn double step, en passant, castling).
- All other board sizes use mini rules (single-step pawns, no ep, no castling).
"""

from __future__ import annotations

from dataclasses import dataclass

WHITE_PIECES = frozenset("PNBRQK")
BLACK_PIECES = frozenset("pnbrqk")
ALL_PIECES = WHITE_PIECES | BLACK_PIECES
PROMO_PIECES = ("q", "r", "b", "n")

KNIGHT_OFFSETS = (
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
)
KING_OFFSETS = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),           (1, 0),
    (-1, 1),  (0, 1),  (1, 1),
)
ORTHO_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAG_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ALL_DIRS = ORTHO_DIRS + DIAG_DIRS


@dataclass(frozen=True)
class Position:
    width: int
    height: int
    board: tuple[str, ...]
    stm: str
    castling: str
    ep: tuple[int, int] | None

    @property
    def is_8x8(self) -> bool:
        return self.width == 8 and self.height == 8

    def at(self, file_idx: int, rank_idx: int) -> str:
        return self.board[rank_idx * self.width + file_idx]

    def to_fen(self) -> str:
        return format_position(self)


def opponent(side: str) -> str:
    return "b" if side == "w" else "w"


def piece_color(piece: str) -> str | None:
    if piece in WHITE_PIECES:
        return "w"
    if piece in BLACK_PIECES:
        return "b"
    return None


def square_name(file_idx: int, rank_idx: int) -> str:
    return chr(ord("a") + file_idx) + str(rank_idx + 1)


def parse_square(text: str, width: int, height: int) -> tuple[int, int]:
    if len(text) != 2:
        raise ValueError(f"invalid square: {text!r}")
    file_idx = ord(text[0]) - ord("a")
    rank_idx = ord(text[1]) - ord("1")
    if not (0 <= file_idx < width and 0 <= rank_idx < height):
        raise ValueError(f"square out of bounds for {width}x{height}: {text!r}")
    return file_idx, rank_idx


def _find_king(board: tuple[str, ...], width: int, height: int, side: str) -> tuple[int, int]:
    king = "K" if side == "w" else "k"
    idx = board.index(king)
    return idx % width, idx // width


def is_square_attacked(
    board: tuple[str, ...],
    width: int,
    height: int,
    target_f: int,
    target_r: int,
    by_side: str,
) -> bool:
    """Return True if (target_f, target_r) is attacked by any piece of by_side."""
    if by_side == "w":
        pawn, knight, bishop, rook, queen, king = "P", "N", "B", "R", "Q", "K"
        pawn_src_r = target_r - 1
    else:
        pawn, knight, bishop, rook, queen, king = "p", "n", "b", "r", "q", "k"
        pawn_src_r = target_r + 1

    # Pawn attacks
    if 0 <= pawn_src_r < height:
        row_off = pawn_src_r * width
        if target_f > 0 and board[row_off + target_f - 1] == pawn:
            return True
        if target_f + 1 < width and board[row_off + target_f + 1] == pawn:
            return True

    # Knight attacks
    for df, dr in KNIGHT_OFFSETS:
        nf, nr = target_f + df, target_r + dr
        if 0 <= nf < width and 0 <= nr < height:
            if board[nr * width + nf] == knight:
                return True

    # King attacks
    for df, dr in KING_OFFSETS:
        nf, nr = target_f + df, target_r + dr
        if 0 <= nf < width and 0 <= nr < height:
            if board[nr * width + nf] == king:
                return True

    # Orthogonal sliding attacks (rook, queen)
    for df, dr in ORTHO_DIRS:
        nf, nr = target_f + df, target_r + dr
        while 0 <= nf < width and 0 <= nr < height:
            sq_piece = board[nr * width + nf]
            if sq_piece != ".":
                if sq_piece == rook or sq_piece == queen:
                    return True
                break
            nf += df
            nr += dr

    # Diagonal sliding attacks (bishop, queen)
    for df, dr in DIAG_DIRS:
        nf, nr = target_f + df, target_r + dr
        while 0 <= nf < width and 0 <= nr < height:
            sq_piece = board[nr * width + nf]
            if sq_piece != ".":
                if sq_piece == bishop or sq_piece == queen:
                    return True
                break
            nf += df
            nr += dr

    return False


def in_check(pos: Position, side: str | None = None) -> bool:
    """Return True if `side` (defaults to side to move) is currently in check."""
    checked_side = pos.stm if side is None else side
    kf, kr = _find_king(pos.board, pos.width, pos.height, checked_side)
    return is_square_attacked(
        pos.board, pos.width, pos.height, kf, kr, opponent(checked_side)
    )


def _has_legal_ep_capture(
    board: tuple[str, ...], stm: str, ep_sq: tuple[int, int]
) -> bool:
    """Return True if `stm` has at least one legal en-passant capture to `ep_sq` on 8x8."""
    ef, er = ep_sq
    if stm == "w":
        own_pawn, cap_r = "P", er - 1
    else:
        own_pawn, cap_r = "p", er + 1

    opp = opponent(stm)
    kf, kr = _find_king(board, 8, 8, stm)

    for src_f in (ef - 1, ef + 1):
        if not (0 <= src_f < 8):
            continue
        if board[cap_r * 8 + src_f] != own_pawn:
            continue
        # Simulate the en-passant capture and check own king safety.
        sim = list(board)
        sim[cap_r * 8 + src_f] = "."
        sim[cap_r * 8 + ef] = "."
        sim[er * 8 + ef] = own_pawn
        if not is_square_attacked(tuple(sim), 8, 8, kf, kr, opp):
            return True
    return False


def format_position(pos: Position) -> str:
    """Emit the canonical 4-field position string (SPEC section 3)."""
    rank_strs: list[str] = []
    for r in range(pos.height - 1, -1, -1):
        row = pos.board[r * pos.width : (r + 1) * pos.width]
        parts: list[str] = []
        empty = 0
        for ch in row:
            if ch == ".":
                empty += 1
            else:
                if empty:
                    parts.append(str(empty))
                    empty = 0
                parts.append(ch)
        if empty:
            parts.append(str(empty))
        rank_strs.append("".join(parts))

    placement = "/".join(rank_strs)
    castling = pos.castling if pos.castling else "-"
    ep = square_name(pos.ep[0], pos.ep[1]) if pos.ep is not None else "-"
    return f"{placement} {pos.stm} {castling} {ep}"


def _is_ascii_uint(s: str) -> bool:
    return bool(s) and s.isascii() and s.isdigit()


def parse_position(text: str) -> Position:
    """Parse a position string (4 fields, or 5/6 with trailing FEN counters).

    Enforces SPEC v1.2 sections 2 and 3:
    - Board dimensions 3 <= W, H <= 8, uniform rank widths, maximal empty runs.
    - Exactly one king per side; no pawn of either colour on rank 1 or rank H.
    - Opponent king is not in check.
    - Off 8x8: castling and ep must be '-'.
    - On 8x8: castling is a non-empty subset of 'KQkq' in order (or '-') with
      king and matching rook on their original squares; an ep square other than
      '-' must be on rank 6 (White) / rank 3 (Black), empty, with an empty
      origin square behind it (rank 7 / rank 2), an enemy pawn in front of it
      (rank 5 / rank 4), and at least one legal en-passant capture onto it.
    """
    if not isinstance(text, str) or "\t" in text or "\n" in text or "\r" in text:
        raise ValueError("position string contains forbidden whitespace")

    fields = text.split(" ")
    if len(fields) not in (4, 5, 6):
        raise ValueError(f"expected 4 (or 5-6) space-separated fields, got {len(fields)}")

    placement, stm, castling_str, ep_str = fields[:4]
    for extra in fields[4:]:
        if not _is_ascii_uint(extra):
            raise ValueError(f"invalid trailing FEN counter: {extra!r}")

    # Parse placement
    rank_strs = placement.split("/")
    height = len(rank_strs)
    if not (3 <= height <= 8):
        raise ValueError(f"board height must be in 3..8, got {height}")

    rows: list[list[str]] = []
    width: int | None = None
    for rank_str in rank_strs:
        if not rank_str:
            raise ValueError("empty rank in placement")
        row: list[str] = []
        prev_digit = False
        for ch in rank_str:
            if "1" <= ch <= "8":
                if prev_digit:
                    raise ValueError(f"non-maximal empty run in rank: {rank_str!r}")
                row.extend("." * int(ch))
                prev_digit = True
            elif ch in ALL_PIECES:
                row.append(ch)
                prev_digit = False
            else:
                raise ValueError(f"invalid character in placement: {ch!r}")
        if width is None:
            width = len(row)
            if not (3 <= width <= 8):
                raise ValueError(f"board width must be in 3..8, got {width}")
        elif len(row) != width:
            raise ValueError("inconsistent rank widths in placement")
        rows.append(row)

    assert width is not None
    # FEN lists top rank first; internal board stores rank 0 (bottom) first.
    board_list: list[str] = []
    for row in reversed(rows):
        board_list.extend(row)
    board = tuple(board_list)

    if board.count("K") != 1 or board.count("k") != 1:
        raise ValueError("position must have exactly one king per side")

    # No pawn of either colour may sit on rank 1 or rank H (SPEC v1.1 section 3).
    top_row = board[(height - 1) * width : height * width]
    bottom_row = board[0:width]
    if "P" in top_row or "p" in top_row or "P" in bottom_row or "p" in bottom_row:
        raise ValueError("pawn on rank 1 or top rank")

    if stm not in ("w", "b"):
        raise ValueError(f"invalid side to move: {stm!r}")

    # Side not to move cannot be in check.
    opp = opponent(stm)
    opp_kf, opp_kr = _find_king(board, width, height, opp)
    if is_square_attacked(board, width, height, opp_kf, opp_kr, stm):
        raise ValueError("opponent king is in check")

    is_8x8 = width == 8 and height == 8

    # Parse castling
    if castling_str == "-":
        castling = ""
    else:
        if not castling_str:
            raise ValueError("empty castling field")
        if not is_8x8:
            raise ValueError("castling rights must be '-' off 8x8")
        last_idx = -1
        for ch in castling_str:
            idx = "KQkq".find(ch)
            if idx <= last_idx:
                raise ValueError(f"invalid castling string: {castling_str!r}")
            last_idx = idx
        if "K" in castling_str and (board[4] != "K" or board[7] != "R"):
            raise ValueError("castling right 'K' requires K on e1 and R on h1")
        if "Q" in castling_str and (board[4] != "K" or board[0] != "R"):
            raise ValueError("castling right 'Q' requires K on e1 and R on a1")
        if "k" in castling_str and (board[7 * 8 + 4] != "k" or board[7 * 8 + 7] != "r"):
            raise ValueError("castling right 'k' requires k on e8 and r on h8")
        if "q" in castling_str and (board[7 * 8 + 4] != "k" or board[7 * 8 + 0] != "r"):
            raise ValueError("castling right 'q' requires k on e8 and r on a8")
        castling = castling_str

    # Parse en passant (SPEC v1.2 section 3).
    ep: tuple[int, int] | None = None
    if ep_str != "-":
        if not is_8x8:
            raise ValueError("en passant must be '-' off 8x8")
        ef, er = parse_square(ep_str, 8, 8)
        if stm == "w":
            if (
                er != 5
                or board[5 * 8 + ef] != "."
                or board[6 * 8 + ef] != "."
                or board[4 * 8 + ef] != "p"
            ):
                raise ValueError(f"invalid en-passant square for White: {ep_str!r}")
        else:
            if (
                er != 2
                or board[2 * 8 + ef] != "."
                or board[1 * 8 + ef] != "."
                or board[3 * 8 + ef] != "P"
            ):
                raise ValueError(f"invalid en-passant square for Black: {ep_str!r}")
        if not _has_legal_ep_capture(board, stm, (ef, er)):
            raise ValueError(f"en-passant square has no legal capture: {ep_str!r}")
        ep = (ef, er)

    return Position(
        width=width,
        height=height,
        board=board,
        stm=stm,
        castling=castling,
        ep=ep,
    )


def _pseudo_legal_moves(pos: Position) -> list[tuple[int, int, int, int, str]]:
    """Generate pseudo-legal moves as (f1, r1, f2, r2, promo) tuples."""
    w, h = pos.width, pos.height
    board = pos.board
    stm = pos.stm
    opp = opponent(stm)
    is_8x8 = pos.is_8x8
    moves: list[tuple[int, int, int, int, str]] = []

    for r in range(h):
        row_off = r * w
        for f in range(w):
            piece = board[row_off + f]
            if piece == "." or piece_color(piece) != stm:
                continue
            kind = piece.upper()

            if kind == "P":
                dr = 1 if stm == "w" else -1
                promo_r = h - 1 if stm == "w" else 0
                nr = r + dr
                if 0 <= nr < h:
                    # Single step forward
                    if board[nr * w + f] == ".":
                        if nr == promo_r:
                            for p in PROMO_PIECES:
                                moves.append((f, r, f, nr, p))
                        else:
                            moves.append((f, r, f, nr, ""))
                            # Double step on 8x8 from starting rank
                            start_r = 1 if stm == "w" else 6
                            if is_8x8 and r == start_r:
                                nr2 = r + 2 * dr
                                if board[nr2 * w + f] == ".":
                                    moves.append((f, r, f, nr2, ""))
                    # Diagonal captures and en passant
                    for df in (-1, 1):
                        nf = f + df
                        if not (0 <= nf < w):
                            continue
                        target = board[nr * w + nf]
                        if piece_color(target) == opp:
                            if nr == promo_r:
                                for p in PROMO_PIECES:
                                    moves.append((f, r, nf, nr, p))
                            else:
                                moves.append((f, r, nf, nr, ""))
                        elif is_8x8 and pos.ep == (nf, nr):
                            moves.append((f, r, nf, nr, ""))

            elif kind == "N":
                for df, dr in KNIGHT_OFFSETS:
                    nf, nr = f + df, r + dr
                    if 0 <= nf < w and 0 <= nr < h:
                        if piece_color(board[nr * w + nf]) != stm:
                            moves.append((f, r, nf, nr, ""))

            elif kind == "B" or kind == "R" or kind == "Q":
                dirs = DIAG_DIRS if kind == "B" else ORTHO_DIRS if kind == "R" else ALL_DIRS
                for df, dr in dirs:
                    nf, nr = f + df, r + dr
                    while 0 <= nf < w and 0 <= nr < h:
                        target = board[nr * w + nf]
                        if target == ".":
                            moves.append((f, r, nf, nr, ""))
                        else:
                            if piece_color(target) == opp:
                                moves.append((f, r, nf, nr, ""))
                            break
                        nf += df
                        nr += dr

            elif kind == "K":
                for df, dr in KING_OFFSETS:
                    nf, nr = f + df, r + dr
                    if 0 <= nf < w and 0 <= nr < h:
                        if piece_color(board[nr * w + nf]) != stm:
                            moves.append((f, r, nf, nr, ""))
                # Castling on 8x8
                if is_8x8 and pos.castling:
                    if stm == "w" and (f, r) == (4, 0):
                        if (
                            "K" in pos.castling
                            and board[7] == "R"
                            and board[5] == "."
                            and board[6] == "."
                            and not is_square_attacked(board, 8, 8, 4, 0, "b")
                            and not is_square_attacked(board, 8, 8, 5, 0, "b")
                            and not is_square_attacked(board, 8, 8, 6, 0, "b")
                        ):
                            moves.append((4, 0, 6, 0, ""))
                        if (
                            "Q" in pos.castling
                            and board[0] == "R"
                            and board[1] == "."
                            and board[2] == "."
                            and board[3] == "."
                            and not is_square_attacked(board, 8, 8, 4, 0, "b")
                            and not is_square_attacked(board, 8, 8, 3, 0, "b")
                            and not is_square_attacked(board, 8, 8, 2, 0, "b")
                        ):
                            moves.append((4, 0, 2, 0, ""))
                    elif stm == "b" and (f, r) == (4, 7):
                        if (
                            "k" in pos.castling
                            and board[7 * 8 + 7] == "r"
                            and board[7 * 8 + 5] == "."
                            and board[7 * 8 + 6] == "."
                            and not is_square_attacked(board, 8, 8, 4, 7, "w")
                            and not is_square_attacked(board, 8, 8, 5, 7, "w")
                            and not is_square_attacked(board, 8, 8, 6, 7, "w")
                        ):
                            moves.append((4, 7, 6, 7, ""))
                        if (
                            "q" in pos.castling
                            and board[7 * 8 + 0] == "r"
                            and board[7 * 8 + 1] == "."
                            and board[7 * 8 + 2] == "."
                            and board[7 * 8 + 3] == "."
                            and not is_square_attacked(board, 8, 8, 4, 7, "w")
                            and not is_square_attacked(board, 8, 8, 3, 7, "w")
                            and not is_square_attacked(board, 8, 8, 2, 7, "w")
                        ):
                            moves.append((4, 7, 2, 7, ""))

    return moves


def _apply_board(
    pos: Position, f1: int, r1: int, f2: int, r2: int, promo: str
) -> tuple[str, ...]:
    """Return the updated board tuple after executing a pseudo-legal move."""
    w = pos.width
    board = list(pos.board)
    piece = board[r1 * w + f1]
    board[r1 * w + f1] = "."

    # En-passant capture removes the pawn on the starting rank of the capturing pawn.
    if pos.is_8x8 and piece in ("P", "p") and f1 != f2 and pos.ep == (f2, r2):
        board[r1 * w + f2] = "."

    # Castling also moves the rook.
    if pos.is_8x8 and piece == "K" and f1 == 4 and r1 == 0:
        if f2 == 6 and r2 == 0:
            board[7] = "."
            board[5] = "R"
        elif f2 == 2 and r2 == 0:
            board[0] = "."
            board[3] = "R"
    elif pos.is_8x8 and piece == "k" and f1 == 4 and r1 == 7:
        if f2 == 6 and r2 == 7:
            board[7 * 8 + 7] = "."
            board[7 * 8 + 5] = "r"
        elif f2 == 2 and r2 == 7:
            board[7 * 8 + 0] = "."
            board[7 * 8 + 3] = "r"

    if promo:
        placed = promo.upper() if pos.stm == "w" else promo.lower()
    else:
        placed = piece
    board[r2 * w + f2] = placed
    return tuple(board)


def _finish_position(
    pos: Position,
    new_board: tuple[str, ...],
    f1: int,
    r1: int,
    f2: int,
    r2: int,
) -> Position:
    """Build the next canonical Position from a legal move's resulting board."""
    next_stm = opponent(pos.stm)
    piece = pos.board[r1 * pos.width + f1]

    # Update castling rights on 8x8 (king move, rook move, or rook capture).
    castling = pos.castling
    if pos.is_8x8 and castling:
        drop: set[str] = set()
        if piece == "K" or (f1, r1) == (4, 0):
            drop.update(("K", "Q"))
        if (f1, r1) == (7, 0) or (f2, r2) == (7, 0):
            drop.add("K")
        if (f1, r1) == (0, 0) or (f2, r2) == (0, 0):
            drop.add("Q")
        if piece == "k" or (f1, r1) == (4, 7):
            drop.update(("k", "q"))
        if (f1, r1) == (7, 7) or (f2, r2) == (7, 7):
            drop.add("k")
        if (f1, r1) == (0, 7) or (f2, r2) == (0, 7):
            drop.add("q")
        if drop:
            castling = "".join(c for c in castling if c not in drop)

    # Set en passant only if a pawn double-stepped AND a legal ep capture exists.
    new_ep: tuple[int, int] | None = None
    if pos.is_8x8 and piece in ("P", "p") and abs(r2 - r1) == 2:
        cand_ep = (f1, (r1 + r2) // 2)
        if _has_legal_ep_capture(new_board, next_stm, cand_ep):
            new_ep = cand_ep

    return Position(
        width=pos.width,
        height=pos.height,
        board=new_board,
        stm=next_stm,
        castling=castling,
        ep=new_ep,
    )


def _format_move(f1: int, r1: int, f2: int, r2: int, promo: str) -> str:
    return square_name(f1, r1) + square_name(f2, r2) + promo


def legal_moves(pos: Position) -> list[str]:
    """Return all legal move strings from `pos`, sorted lexicographically."""
    opp = opponent(pos.stm)
    w, h = pos.width, pos.height
    result: list[str] = []
    for f1, r1, f2, r2, promo in _pseudo_legal_moves(pos):
        new_board = _apply_board(pos, f1, r1, f2, r2, promo)
        kf, kr = _find_king(new_board, w, h, pos.stm)
        if not is_square_attacked(new_board, w, h, kf, kr, opp):
            result.append(_format_move(f1, r1, f2, r2, promo))
    result.sort()
    return result


def legal_transitions(pos: Position) -> list[tuple[str, Position]]:
    """Return sorted (move_str, next_pos) pairs for every legal move from `pos`."""
    opp = opponent(pos.stm)
    w, h = pos.width, pos.height
    transitions: list[tuple[str, Position]] = []
    for f1, r1, f2, r2, promo in _pseudo_legal_moves(pos):
        new_board = _apply_board(pos, f1, r1, f2, r2, promo)
        kf, kr = _find_king(new_board, w, h, pos.stm)
        if not is_square_attacked(new_board, w, h, kf, kr, opp):
            move_str = _format_move(f1, r1, f2, r2, promo)
            next_pos = _finish_position(pos, new_board, f1, r1, f2, r2)
            transitions.append((move_str, next_pos))
    transitions.sort(key=lambda item: item[0])
    return transitions


def apply_move(pos: Position, move_str: str) -> Position:
    """Apply `move_str` to `pos`, raising ValueError if `move_str` is not legal."""
    if not isinstance(move_str, str) or len(move_str) not in (4, 5):
        raise ValueError(f"invalid move syntax: {move_str!r}")
    f1, r1 = parse_square(move_str[0:2], pos.width, pos.height)
    f2, r2 = parse_square(move_str[2:4], pos.width, pos.height)
    promo = move_str[4] if len(move_str) == 5 else ""
    if promo and promo not in PROMO_PIECES:
        raise ValueError(f"invalid promotion piece: {promo!r}")

    target = (f1, r1, f2, r2, promo)
    if target not in _pseudo_legal_moves(pos):
        raise ValueError(f"illegal move {move_str!r} in {pos.to_fen()!r}")

    new_board = _apply_board(pos, f1, r1, f2, r2, promo)
    kf, kr = _find_king(new_board, pos.width, pos.height, pos.stm)
    if is_square_attacked(new_board, pos.width, pos.height, kf, kr, opponent(pos.stm)):
        raise ValueError(f"illegal move (leaves king in check): {move_str!r}")

    return _finish_position(pos, new_board, f1, r1, f2, r2)


def perft(pos: Position, depth: int) -> int:
    """Count legal move paths of length `depth` from `pos`."""
    if depth < 0:
        raise ValueError("perft depth must be non-negative")
    if depth == 0:
        return 1
    if depth == 1:
        return len(legal_moves(pos))
    return sum(perft(next_pos, depth - 1) for _, next_pos in legal_transitions(pos))
