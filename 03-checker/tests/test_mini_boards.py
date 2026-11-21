"""Hand-checked rules tests for mini boards (3x3, 4x4, 4x5, 5x5, rectangular)."""

from __future__ import annotations

import unittest

from rules import apply_move, in_check, legal_moves, parse_position


class TestMiniBoards(unittest.TestCase):
    def test_named_mini_start_positions_parse_and_roundtrip(self) -> None:
        for fen in (
            "rqkr/pppp/PPPP/RQKR w - -",
            "rqkr/pppp/4/PPPP/RQKR w - -",
            "rnbqk/ppppp/5/PPPPP/RNBQK w - -",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -",
        ):
            pos = parse_position(fen)
            self.assertEqual(pos.to_fen(), fen)

    def test_single_step_pawns_only_on_mini_boards(self) -> None:
        # On 4x5, White pawns on rank 2 must only step one square (no double step).
        pos = parse_position("rqkr/pppp/4/PPPP/RQKR w - -")
        moves = legal_moves(pos)
        self.assertEqual(moves, ["a2a3", "b2b3", "c2c3", "d2d3"])

        # Even on 8x7 (one dimension != 8), mini rules apply: no double step!
        pos87 = parse_position("4k3/8/8/8/8/PPPPPPPP/4K3 w - -")
        moves87 = legal_moves(pos87)
        self.assertIn("e2e3", moves87)
        self.assertNotIn("e2e4", moves87)

    def test_no_castling_or_ep_off_8x8(self) -> None:
        # Castling rights other than '-' must be rejected off 8x8.
        with self.assertRaises(ValueError):
            parse_position("4k3/8/8/8/8/8/R3K2R w KQ -")
        # En passant other than '-' must be rejected off 8x8.
        with self.assertRaises(ValueError):
            parse_position("4k3/8/8/8/3pP3/8/4K3 b - e3")
        # Even with K on e1 and R on h1 on 8x7, no castling move is generated.
        pos = parse_position("4k3/8/8/8/8/8/R3K2R w - -")
        self.assertNotIn("e1g1", legal_moves(pos))
        self.assertNotIn("e1c1", legal_moves(pos))

    def test_promotion_on_3x3_and_4x4(self) -> None:
        # 3x3: White pawn on a2 can push to a3 (4 promos) or capture rook on b3 (4 promos).
        pos = parse_position("1rk/P2/2K w - -")
        moves = legal_moves(pos)
        promo_moves = [m for m in moves if m.startswith("a2")]
        self.assertEqual(
            promo_moves,
            ["a2a3b", "a2a3n", "a2a3q", "a2a3r", "a2b3b", "a2b3n", "a2b3q", "a2b3r"],
        )
        promoted = apply_move(pos, "a2b3q")
        self.assertEqual(promoted.to_fen(), "1Qk/3/2K b - -")
        self.assertTrue(in_check(promoted))

        # 4x4: Black pawn on a2 promotes on rank 1.
        pos4 = parse_position("k3/4/p3/1B1K b - -")
        black_promos = [m for m in legal_moves(pos4) if m.startswith("a2")]
        self.assertEqual(
            black_promos,
            ["a2a1b", "a2a1n", "a2a1q", "a2a1r", "a2b1b", "a2b1n", "a2b1q", "a2b1r"],
        )

    def test_pins_on_mini_boards(self) -> None:
        # 5x5: White rook on c2 is pinned orthogonally by Black rook on c5 to White king on c1.
        pos = parse_position("k1r2/5/5/2R2/2K2 w - -")
        rook_moves = [m for m in legal_moves(pos) if m.startswith("c2")]
        self.assertEqual(rook_moves, ["c2c3", "c2c4", "c2c5"])

        # 4x4: White knight on b2 is pinned diagonally by Black bishop on d4 to White king on a1.
        pos_diag = parse_position("1k1b/4/1N2/K3 w - -")
        knight_moves = [m for m in legal_moves(pos_diag) if m.startswith("b2")]
        self.assertEqual(knight_moves, [])

    def test_check_evasion_capture_block_and_double_check(self) -> None:
        # 5x5: Black rook on e1 checks White king on a1.
        # White rook on b3 can interpose on b1; White bishop on b4 can capture on e1;
        # King can move to a2 or b2 (not b1).
        pos = parse_position("3k1/1B3/1R3/5/K3r w - -")
        self.assertTrue(in_check(pos))
        self.assertEqual(legal_moves(pos), ["a1a2", "a1b2", "b3b1", "b4e1"])

        # 4x4 double check: White king on a1 checked by Black rook on d1 and Black bishop on c3.
        # White rook on b2 cannot resolve double check; only king move a1a2 is legal.
        pos_dbl = parse_position("k3/2b1/1R2/K2r w - -")
        self.assertTrue(in_check(pos_dbl))
        self.assertEqual(legal_moves(pos_dbl), ["a1a2"])

    def test_stalemate_on_3x3_4x4_5x5(self) -> None:
        # 3x3 stalemate: Black king on a3, White king on c2, White pawn on a2? Wait:
        # White king on c2 covers b3, b2, b1. White queen on b1? No, b1 checks a2.
        # Clean 3x3 stalemate: k on a3, Q on c2 (attacks b3, b2, a2), K on c1 -> a3 not attacked!
        p3 = parse_position("k2/2Q/2K b - -")
        self.assertFalse(in_check(p3))
        self.assertEqual(legal_moves(p3), [])

        # 4x4 stalemate: k on a4, Q on c3 (covers b4, b3, a3), K on d1.
        p4 = parse_position("k3/2Q1/4/3K b - -")
        self.assertFalse(in_check(p4))
        self.assertEqual(legal_moves(p4), [])

        # 5x5 stalemate: k on a5, Q on c4 (covers b5, b4, a4), K on e1.
        p5 = parse_position("k4/2Q2/5/5/4K b - -")
        self.assertFalse(in_check(p5))
        self.assertEqual(legal_moves(p5), [])

    def test_checkmate_on_3x3_4x4_5x5(self) -> None:
        # 3x3 checkmate: k on a3, Q on b2 protected by K on c1.
        m3 = parse_position("k2/1Q1/2K b - -")
        self.assertTrue(in_check(m3))
        self.assertEqual(legal_moves(m3), [])

        # 4x4 checkmate: k on a4, Q on b3 protected by K on c2.
        m4 = parse_position("k3/1Q2/2K1/4 b - -")
        self.assertTrue(in_check(m4))
        self.assertEqual(legal_moves(m4), [])

        # 5x5 checkmate: back-rank mate by rook on e5 with pawns on a4, b4, c4?
        # Even simpler: k on a5, Q on b4 protected by K on c3.
        m5 = parse_position("k4/1Q3/2K2/5/5 b - -")
        self.assertTrue(in_check(m5))
        self.assertEqual(legal_moves(m5), [])

    def test_parser_rejects_invalid_positions(self) -> None:
        bad_fens = [
            "k1/2 w - -",                        # 2x2 too small
            "k8/9/9/9/9/9/9/9/8K w - -",         # 9x9 too big
            "k3/3/4/3K w - -",                   # inconsistent rank widths
            "k21/4/4/3K w - -",                  # non-maximal empty run
            "4/4/4/3K w - -",                    # missing black king
            "kk2/4/4/3K w - -",                  # two black kings
            "k2P/4/4/3K w - -",                  # white pawn on top rank
            "k3/4/4/p2K w - -",                  # black pawn on bottom rank
            "k2R/4/4/3K w - -",                  # opponent king in check
            "k3/4/4/3K x - -",                   # bad stm
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w QK -",  # bad castling order
            "4k3/8/8/8/8/8/8/4K3 w - e6",        # ep without black pawn on e5
        ]
        for fen in bad_fens:
            with self.subTest(fen=fen):
                with self.assertRaises(ValueError):
                    parse_position(fen)

    def test_pawns_on_rank_1_or_top_rank_rejected_v1_1(self) -> None:
        # SPEC v1.1 section 3: no pawn of either colour on rank 1 or rank H.
        bad_pawn_fens = [
            # 3x3 (rank 3 = top, rank 1 = bottom)
            "k1P/3/2K w - -",  # White pawn on rank H (3x3)
            "k1p/3/2K w - -",  # Black pawn on rank H (3x3)
            "k2/3/P1K w - -",  # White pawn on rank 1 (3x3)
            "k2/3/p1K w - -",  # Black pawn on rank 1 (3x3)
            # 5x5 (rank 5 = top, rank 1 = bottom)
            "k3P/5/5/5/4K w - -",  # White pawn on rank H (5x5)
            "k3p/5/5/5/4K w - -",  # Black pawn on rank H (5x5)
            "k4/5/5/5/P3K w - -",  # White pawn on rank 1 (5x5)
            "k4/5/5/5/p3K w - -",  # Black pawn on rank 1 (5x5)
            # 8x8 (rank 8 = top, rank 1 = bottom)
            "4k2P/8/8/8/8/8/8/4K3 w - -",  # White pawn on rank 8 (8x8)
            "4k2p/8/8/8/8/8/8/4K3 w - -",  # Black pawn on rank 8 (8x8)
            "4k3/8/8/8/8/8/8/P3K3 w - -",  # White pawn on rank 1 (8x8)
            "4k3/8/8/8/8/8/8/p3K3 w - -",  # Black pawn on rank 1 (8x8)
        ]
        for fen in bad_pawn_fens:
            with self.subTest(fen=fen):
                with self.assertRaises(ValueError):
                    parse_position(fen)


if __name__ == "__main__":
    unittest.main()
