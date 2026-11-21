"""8x8 perft, en-passant canonicalization, and castling tests."""

from __future__ import annotations

import unittest

from rules import apply_move, legal_moves, legal_transitions, parse_position, perft


class TestPerft8x8(unittest.TestCase):
    def test_startpos_perft(self) -> None:
        pos = parse_position("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -")
        self.assertEqual(perft(pos, 0), 1)
        self.assertEqual(perft(pos, 1), 20)
        self.assertEqual(perft(pos, 2), 400)
        self.assertEqual(perft(pos, 3), 8902)
        self.assertEqual(perft(pos, 4), 197281)

    def test_kiwipete_perft(self) -> None:
        pos = parse_position(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
        )
        self.assertEqual(perft(pos, 1), 48)
        self.assertEqual(perft(pos, 2), 2039)
        self.assertEqual(perft(pos, 3), 97862)

    def test_position3_perft(self) -> None:
        pos = parse_position("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -")
        self.assertEqual(perft(pos, 1), 14)
        self.assertEqual(perft(pos, 2), 191)
        self.assertEqual(perft(pos, 3), 2812)
        self.assertEqual(perft(pos, 4), 43238)

    def test_position4_perft(self) -> None:
        pos = parse_position(
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -"
        )
        self.assertEqual(perft(pos, 1), 6)
        self.assertEqual(perft(pos, 2), 264)
        self.assertEqual(perft(pos, 3), 9467)

    def test_position5_perft(self) -> None:
        pos = parse_position(
            "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -"
        )
        self.assertEqual(perft(pos, 1), 44)
        self.assertEqual(perft(pos, 2), 1486)
        self.assertEqual(perft(pos, 3), 62379)

    def test_perft_matches_full_apply_recursion(self) -> None:
        def slow_perft(pos, depth: int) -> int:
            if depth == 0:
                return 1
            return sum(slow_perft(nxt, depth - 1) for _, nxt in legal_transitions(pos))

        pos = parse_position(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -"
        )
        self.assertEqual(slow_perft(pos, 2), 2039)


class Test8x8RulesDetails(unittest.TestCase):
    def test_trailing_fen_counters_accepted_and_stripped(self) -> None:
        pos = parse_position(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        self.assertEqual(
            pos.to_fen(), "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
        )

    def test_ep_cleared_when_no_adjacent_pawn(self) -> None:
        pos = parse_position("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -")
        after_e4 = apply_move(pos, "e2e4")
        self.assertEqual(
            after_e4.to_fen(),
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -",
        )
        # Standard FEN reader accepts e3 and canonicalizes to '-'.
        parsed = parse_position(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        )
        self.assertIsNone(parsed.ep)
        self.assertEqual(parsed.to_fen(), after_e4.to_fen())

    def test_ep_set_when_legal_capture_exists(self) -> None:
        pos = parse_position("4k3/8/8/8/3p4/8/4P3/4K3 w - -")
        nxt = apply_move(pos, "e2e4")
        self.assertEqual(nxt.to_fen(), "4k3/8/8/8/3pP3/8/8/4K3 b - e3")
        self.assertIn("d4e3", legal_moves(nxt))
        after_ep = apply_move(nxt, "d4e3")
        self.assertEqual(after_ep.to_fen(), "4k3/8/8/8/8/4p3/8/4K3 w - -")

    def test_ep_cleared_under_horizontal_pin(self) -> None:
        # White rook on a4, Black pawn on d4, Black king on h4: e2e4 creates
        # pseudo-legal d4e3, which is ILLEGAL because it exposes king on h4 to Ra4.
        pos = parse_position("8/8/8/8/R2p3k/8/4P3/4K3 w - -")
        nxt = apply_move(pos, "e2e4")
        self.assertIsNone(nxt.ep)
        self.assertEqual(nxt.to_fen(), "8/8/8/8/R2pP2k/8/8/4K3 b - -")
        self.assertNotIn("d4e3", legal_moves(nxt))

    def test_ep_set_when_only_one_of_two_pawns_is_pinned(self) -> None:
        # Black pawn on d4 is pinned vertically by White rook on d1 to Black king on d8,
        # but Black pawn on f4 can legally capture en passant on e3.
        pos = parse_position("3k4/8/8/8/3p1p2/8/4P3/3RK3 w - -")
        nxt = apply_move(pos, "e2e4")
        self.assertEqual(nxt.to_fen(), "3k4/8/8/8/3pPp2/8/8/3RK3 b - e3")
        moves = legal_moves(nxt)
        self.assertNotIn("d4e3", moves)
        self.assertIn("f4e3", moves)

    def test_ep_set_when_it_resolves_check_by_capturing_checker(self) -> None:
        # White plays e2e4 giving check to Black king on f5; d4e3 captures the
        # checking pawn on e4 and is legal, so ep must be 'e3'.
        pos = parse_position("8/8/8/5k2/3p4/8/4P3/4K3 w - -")
        nxt = apply_move(pos, "e2e4")
        self.assertEqual(nxt.to_fen(), "8/8/8/5k2/3pP3/8/8/4K3 b - e3")
        self.assertIn("d4e3", legal_moves(nxt))

    def test_castling_rights_lost_on_rook_capture_and_king_move(self) -> None:
        # White bishop captures Black rook on h8 -> loses 'k' only.
        pos = parse_position("r3k2r/8/8/8/8/8/1B6/R3K2R w KQkq -")
        nxt = apply_move(pos, "b2h8")
        self.assertEqual(nxt.castling, "KQq")

        # Black castles queenside -> loses 'q'.
        nxt2 = apply_move(nxt, "e8c8")
        self.assertEqual(nxt2.castling, "KQ")
        self.assertEqual(nxt2.to_fen(), "2kr3B/8/8/8/8/8/8/R3K2R w KQ -")

    def test_castling_blocked_by_attacked_transit_square_but_not_b1(self) -> None:
        # Black rook on b8 attacks b1 (not king path) -> White can still castle queenside!
        pos = parse_position("1r2k3/8/8/8/8/8/8/R3K3 w Q -")
        self.assertIn("e1c1", legal_moves(pos))
        # Black rook on d8 attacks d1 (king transit square) -> White cannot castle queenside.
        pos2 = parse_position("3rk3/8/8/8/8/8/8/R3K3 w Q -")
        self.assertNotIn("e1c1", legal_moves(pos2))

    def test_castling_requires_king_and_rook_on_original_squares_v1_1(self) -> None:
        # SPEC v1.1 section 3: castling letters only where king and that rook stand on original squares.
        bad_castling_fens = [
            "4k3/8/8/8/8/8/8/4K3 w K -",        # missing White h1 rook
            "4k3/8/8/8/8/8/8/3K3R w K -",       # White king not on e1
            "4k3/8/8/8/8/8/8/4K3 w Q -",        # missing White a1 rook
            "4k3/8/8/8/8/8/8/R2K4 w Q -",       # White king not on e1
            "4k3/8/8/8/8/8/8/4K3 b k -",        # missing Black h8 rook
            "3k3r/8/8/8/8/8/8/4K3 b k -",       # Black king not on e8
            "4k3/8/8/8/8/8/8/4K3 b q -",        # missing Black a8 rook
            "r2k4/8/8/8/8/8/8/4K3 b q -",       # Black king not on e8
            "r3k2r/8/8/8/8/8/8/R3K2r w K -",    # Black rook (not White) on h1
        ]
        for fen in bad_castling_fens:
            with self.subTest(fen=fen):
                with self.assertRaises(ValueError):
                    parse_position(fen)


if __name__ == "__main__":
    unittest.main()
