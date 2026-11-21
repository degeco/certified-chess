"""Certificate verification, mutation tests, cycle tests, and CLI tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

from mcheck import verify_certificate
from rules import legal_moves, parse_position
from tests.mini_solver import (
    build_atleast_draw_certificate,
    build_win_certificate,
    solve_small,
)

MCHECK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcheck.py"))


class TestCertificatesAndMutations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_cert(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_real_kq_vs_k_4x4_win_certificates(self) -> None:
        # White to move: KQ vs K on 4x4 with Black king centralized is a forced win for White.
        win_w = build_win_certificate("4/1k2/4/Q2K w - -", "w")
        path_w = self._write_cert("kq_win_w.cert", win_w)
        res_w = verify_certificate(path_w)
        self.assertTrue(res_w.valid, res_w)
        self.assertEqual(res_w.claim, "WIN w")
        self.assertGreaterEqual(res_w.entries, 4)
        self.assertGreater(res_w.max_rank, 1)

        # KR vs K on 4x4 (deeper win tree with more entries and higher rank).
        win_kr = build_win_certificate("4/1k2/4/R2K w - -", "w")
        path_kr = self._write_cert("kr_win_w.cert", win_kr)
        res_kr = verify_certificate(path_kr)
        self.assertTrue(res_kr.valid, res_kr)
        self.assertEqual(res_kr.claim, "WIN w")
        self.assertGreater(res_kr.entries, 5)
        self.assertGreater(res_kr.max_rank, 2)

        # Opponent to move at root: Black to move in KQ vs K on 4x4, still WIN w.
        win_w_opp = build_win_certificate("4/1k2/4/Q2K b - -", "w")
        path_opp = self._write_cert("kq_win_w_opp.cert", win_w_opp)
        res_opp = verify_certificate(path_opp)
        self.assertTrue(res_opp.valid, res_opp)
        self.assertEqual(res_opp.claim, "WIN w")

        # Black wins: K vs KQ on 4x4.
        win_b = build_win_certificate("4/1K2/4/q2k b - -", "b")
        path_b = self._write_cert("kq_win_b.cert", win_b)
        res_b = verify_certificate(path_b)
        self.assertTrue(res_b.valid, res_b)
        self.assertEqual(res_b.claim, "WIN b")

    def test_real_draw_certificates_kvk_and_blocked(self) -> None:
        # K vs K on 4x4: ATLEAST_DRAW for both White and Black (contains cycles).
        for side in ("w", "b"):
            cert = build_atleast_draw_certificate("k3/4/4/3K w - -", side)
            path = self._write_cert(f"kvk_draw_{side}.cert", cert)
            res = verify_certificate(path)
            self.assertTrue(res.valid, res)
            self.assertEqual(res.claim, f"ATLEAST_DRAW {side}")
            self.assertEqual(res.max_rank, 0)

        # Sealed blocked pawn fortress on 4x5: no pawn can move or capture,
        # kings are sealed on ranks 1 and 5 -> ATLEAST_DRAW for both sides.
        blocked_fen = "k3/p1p1/PpPp/1P1P/3K w - -"
        for side in ("w", "b"):
            cert = build_atleast_draw_certificate(blocked_fen, side)
            path = self._write_cert(f"blocked_draw_{side}.cert", cert)
            res = verify_certificate(path)
            self.assertTrue(res.valid, res)
            self.assertEqual(res.claim, f"ATLEAST_DRAW {side}")

    def test_all_required_mutations_rejected(self) -> None:
        # Base WIN certificate: KQ vs K on 4x4.
        root_fen = "k3/4/4/1Q1K w - -"
        win_text = build_win_certificate(root_fen, "w")
        win_lines = win_text.splitlines()
        self.assertTrue(verify_certificate(self._write_cert("base_win.cert", win_text)).valid)

        # Base DRAW certificate: K vs K on 4x4.
        draw_text = build_atleast_draw_certificate("k3/4/4/3K w - -", "w")
        draw_lines = draw_text.splitlines()
        self.assertTrue(verify_certificate(self._write_cert("base_draw.cert", draw_text)).valid)

        # 1. Delete one entry that is needed (delete a non-root entry).
        non_root_idx = next(
            i for i in range(3, len(win_lines)) if not win_lines[i].startswith(root_fen + "\t")
        )
        mut_del = win_lines[:non_root_idx] + win_lines[non_root_idx + 1 :]
        res = verify_certificate(self._write_cert("m_delete.cert", "\n".join(mut_del) + "\n"))
        self.assertFalse(res.valid)

        # 2. Change a move to another legal move that loses the win.
        # In KQ vs K on 4x4, find a position in win_lines where a legal move loses the win
        # (e.g., drops the queen to the black king!).
        _, outcomes, _, _ = solve_small(root_fen)
        losing_mut_lines = None
        for i in range(3, len(win_lines)):
            p_str, orig_move, rank_str = win_lines[i].split("\t")
            p_pos = parse_position(p_str)
            for cand_move in legal_moves(p_pos):
                if cand_move == orig_move:
                    continue
                # Find a legal move whose resulting position is NOT a LOSS for Black.
                from rules import apply_move

                q_fen = apply_move(p_pos, cand_move).to_fen()
                if outcomes.get(q_fen) != "LOSS":
                    losing_mut_lines = list(win_lines)
                    losing_mut_lines[i] = f"{p_str}\t{cand_move}\t{rank_str}"
                    break
            if losing_mut_lines is not None:
                break
        self.assertIsNotNone(losing_mut_lines, "expected to find a win-losing legal move")
        res = verify_certificate(
            self._write_cert("m_lose_win.cert", "\n".join(losing_mut_lines) + "\n")
        )
        self.assertFalse(res.valid)

        # 3. Change a move to an illegal move.
        mut_illegal = list(win_lines)
        p0, _, r0 = mut_illegal[3].split("\t")
        mut_illegal[3] = f"{p0}\ta1d4\t{r0}"
        res = verify_certificate(
            self._write_cert("m_illegal.cert", "\n".join(mut_illegal) + "\n")
        )
        self.assertFalse(res.valid)

        # 4. Raise a child's rank to equal its parent's.
        # Find the root entry (which has rank > 1) and raise one of its children to root's rank.
        entry_idx = {
            win_lines[i].split("\t")[0]: i for i in range(3, len(win_lines))
        }
        root_i = entry_idx[root_fen]
        _, root_m, root_r = win_lines[root_i].split("\t")
        from rules import apply_move, legal_transitions

        q_after_root = apply_move(parse_position(root_fen), root_m)
        child_fen = legal_transitions(q_after_root)[0][1].to_fen()
        child_i = entry_idx[child_fen]
        cp, cm, _ = win_lines[child_i].split("\t")
        mut_rank = list(win_lines)
        mut_rank[child_i] = f"{cp}\t{cm}\t{root_r}"
        res = verify_certificate(
            self._write_cert("m_raise_rank.cert", "\n".join(mut_rank) + "\n")
        )
        self.assertFalse(res.valid)

        # 5. Flip the claimed side.
        mut_flip = list(win_lines)
        mut_flip[1] = "#claim WIN b"
        res = verify_certificate(
            self._write_cert("m_flip_side.cert", "\n".join(mut_flip) + "\n")
        )
        self.assertFalse(res.valid)

        # 6. Swap ATLEAST_DRAW for WIN.
        mut_swap = list(draw_lines)
        mut_swap[1] = "#claim WIN w"
        res = verify_certificate(
            self._write_cert("m_swap_claim.cert", "\n".join(mut_swap) + "\n")
        )
        self.assertFalse(res.valid)

        # 7. Duplicate a position.
        mut_dup = list(win_lines) + [win_lines[3]]
        res = verify_certificate(
            self._write_cert("m_dup.cert", "\n".join(mut_dup) + "\n")
        )
        self.assertFalse(res.valid)

        # 8. Corrupt a position string.
        mut_corrupt = list(win_lines)
        _, m3, r3 = mut_corrupt[3].split("\t")
        mut_corrupt[3] = f"k3/4/4/1Q1X w - -\t{m3}\t{r3}"
        res = verify_certificate(
            self._write_cert("m_corrupt.cert", "\n".join(mut_corrupt) + "\n")
        )
        self.assertFalse(res.valid)

        # 9. Use a non-canonical position string (trailing counters, non-maximal digits, bad ep).
        mut_noncanon_counters = list(win_lines)
        mut_noncanon_counters[2] = f"#root {root_fen} 0 1"
        res = verify_certificate(
            self._write_cert(
                "m_noncanon_counters.cert", "\n".join(mut_noncanon_counters) + "\n"
            )
        )
        self.assertFalse(res.valid)

        mut_noncanon_digits = list(win_lines)
        p3, m3, r3 = mut_noncanon_digits[3].split("\t")
        # Replace a '4' empty rank with '22' if present, else replace any '3' with '12'.
        bad_p3 = p3.replace("4", "22", 1) if "4" in p3 else p3.replace("3", "12", 1)
        self.assertNotEqual(bad_p3, p3)
        mut_noncanon_digits[3] = f"{bad_p3}\t{m3}\t{r3}"
        res = verify_certificate(
            self._write_cert(
                "m_noncanon_digits.cert", "\n".join(mut_noncanon_digits) + "\n"
            )
        )
        self.assertFalse(res.valid)

        # Non-canonical ep square on 8x8 (e3 listed when no legal ep capture exists).
        ep_cert = "\n".join(
            [
                "#cert v1",
                "#claim ATLEAST_DRAW b",
                "#root 4k3/8/8/8/4P3/8/8/4K3 b - e3",
                "4k3/8/8/8/4P3/8/8/4K3 b - e3\te8d8\t0",
            ]
        ) + "\n"
        res = verify_certificate(self._write_cert("m_noncanon_ep.cert", ep_cert))
        self.assertFalse(res.valid)

        # 10. Give a stalemating move in a WIN certificate.
        # Root: k on a4, Q on d3, K on d1 -> d3c3 stalemates Black on a4!
        stale_cert = "\n".join(
            [
                "#cert v1",
                "#claim WIN w",
                "#root k3/3Q/4/3K w - -",
                "k3/3Q/4/3K w - -\td3c3\t1",
            ]
        ) + "\n"
        res = verify_certificate(self._write_cert("m_stalemate.cert", stale_cert))
        self.assertFalse(res.valid)

        # 11a. Omit the root entry from the body.
        mut_omit_root_entry = [line for i, line in enumerate(win_lines) if i != root_i]
        res = verify_certificate(
            self._write_cert("m_omit_root_entry.cert", "\n".join(mut_omit_root_entry) + "\n")
        )
        self.assertFalse(res.valid)

        # 11b. Omit the #root header line.
        mut_omit_root_hdr = [win_lines[0], win_lines[1]] + win_lines[3:]
        res = verify_certificate(
            self._write_cert("m_omit_root_hdr.cert", "\n".join(mut_omit_root_hdr) + "\n")
        )
        self.assertFalse(res.valid)

    def test_cycle_rejected_in_win_and_accepted_in_atleast_draw(self) -> None:
        # Sealed 4x5 fortress: White king shuttles d1 <-> c1 while Black king roams a5..d5.
        # This forms a closed 8-state cycle (every entry transitions back into the cycle).
        entries = [
            ("k3/p1p1/PpPp/1P1P/3K w - -", "d1c1"),
            ("1k2/p1p1/PpPp/1P1P/3K w - -", "d1c1"),
            ("2k1/p1p1/PpPp/1P1P/3K w - -", "d1c1"),
            ("3k/p1p1/PpPp/1P1P/3K w - -", "d1c1"),
            ("k3/p1p1/PpPp/1P1P/2K1 w - -", "c1d1"),
            ("1k2/p1p1/PpPp/1P1P/2K1 w - -", "c1d1"),
            ("2k1/p1p1/PpPp/1P1P/2K1 w - -", "c1d1"),
            ("3k/p1p1/PpPp/1P1P/2K1 w - -", "c1d1"),
        ]
        root_fen = "k3/p1p1/PpPp/1P1P/3K w - -"
        draw_cycle = "\n".join(
            ["#cert v1", "#claim ATLEAST_DRAW w", f"#root {root_fen}"]
            + [f"{p}\t{m}\t0" for p, m in entries]
        ) + "\n"
        res_draw = verify_certificate(self._write_cert("cycle_draw.cert", draw_cycle))
        self.assertTrue(res_draw.valid, res_draw)

        # Same exact cycle with WIN and equal ranks (5) MUST be rejected!
        win_cycle = "\n".join(
            ["#cert v1", "#claim WIN w", f"#root {root_fen}"]
            + [f"{p}\t{m}\t5" for p, m in entries]
        ) + "\n"
        res_win = verify_certificate(self._write_cert("cycle_win.cert", win_cycle))
        self.assertFalse(res_win.valid)
        self.assertIn("not <", res_win.error_reason or "")

    def test_opponent_to_move_terminal_roots(self) -> None:
        # Opponent already checkmated at root: empty WIN certificate is valid!
        mate_cert = "\n".join(
            ["#cert v1", "#claim WIN w", "#root k2/1Q1/2K b - -"]
        ) + "\n"
        res = verify_certificate(self._write_cert("root_mate.cert", mate_cert))
        self.assertTrue(res.valid, res)
        self.assertEqual(res.entries, 0)

        # Opponent already stalemated at root: empty WIN certificate is INVALID!
        stale_win = "\n".join(
            ["#cert v1", "#claim WIN w", "#root k2/2Q/2K b - -"]
        ) + "\n"
        self.assertFalse(
            verify_certificate(self._write_cert("root_stale_win.cert", stale_win)).valid
        )

        # Opponent already stalemated at root: empty ATLEAST_DRAW certificate is VALID!
        stale_draw = "\n".join(
            ["#cert v1", "#claim ATLEAST_DRAW w", "#root k2/2Q/2K b - -"]
        ) + "\n"
        self.assertTrue(
            verify_certificate(self._write_cert("root_stale_draw.cert", stale_draw)).valid
        )

    def test_unreachable_invalid_entry_is_rejected(self) -> None:
        # SPEC section 4: checker verifies EVERY entry, not only those reachable from root.
        # Root is immediate mate-in-1 (c2b2 mates k on a3 with K on c1), plus an unreachable bad entry.
        cert = "\n".join(
            [
                "#cert v1",
                "#claim WIN w",
                "#root k2/2Q/2K w - -",
                "k2/2Q/2K w - -\tc2b2\t1",
                "k2/3/1QK w - -\tb1a1\t1",  # unreachable, and fails because Black has reply a3a2 not in entries
            ]
        ) + "\n"
        res = verify_certificate(self._write_cert("unreachable_bad.cert", cert))
        self.assertFalse(res.valid)

    def test_malformed_files_never_crash(self) -> None:
        malformed_cases = [
            ("empty.cert", ""),
            ("short.cert", "#cert v1\n#claim WIN w\n"),
            ("bad_ver.cert", "#cert v2\n#claim WIN w\n#root k2/2Q/2K w - -\n"),
            ("bad_claim.cert", "#cert v1\n#claim DRAW w\n#root k2/2Q/2K w - -\n"),
            ("bad_tabs.cert", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - - c2b2 1\n"),
            ("neg_rank.cert", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t-1\n"),
            ("nonzero_draw_rank.cert", "#cert v1\n#claim ATLEAST_DRAW w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t1\n"),
            ("blank_line.cert", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\n\nk2/2Q/2K w - -\tc2b2\t1\n"),
            ("wrong_board.cert", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t1\nk3/2Q1/4/3K w - -\tc3b3\t1\n"),
        ]
        for fname, content in malformed_cases:
            with self.subTest(fname=fname):
                path = self._write_cert(fname, content)
                res = verify_certificate(path)
                self.assertFalse(res.valid)

        # Binary invalid UTF-8 bytes
        bin_path = os.path.join(self.tmpdir, "binary.cert")
        with open(bin_path, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x80invalid")
        self.assertFalse(verify_certificate(bin_path).valid)

        # Non-existent file
        self.assertFalse(verify_certificate(os.path.join(self.tmpdir, "missing.cert")).valid)

    def test_v1_1_prover_stalemate_in_k3_1p2_1P2_3K(self) -> None:
        # TASK-2: k3/1p2/1P2/3K w - - generates both ATLEAST_DRAW certificates and both are VALID.
        from rules import apply_move, in_check, legal_transitions

        root_fen = "k3/1p2/1P2/3K w - -"
        for side in ("w", "b"):
            with self.subTest(prover=side):
                cert = build_atleast_draw_certificate(root_fen, side)
                path = self._write_cert(f"pawn_stalemate_draw_{side}.cert", cert)
                res = verify_certificate(path)
                self.assertTrue(res.valid, res)
                self.assertEqual(res.claim, f"ATLEAST_DRAW {side}")
                self.assertEqual(res.max_rank, 0)

                # Confirm the generated certificate genuinely relies on prover-stalemate replies.
                body_lines = cert.splitlines()[3:]
                entry_keys = {line.split("\t")[0] for line in body_lines}
                stalemate_replies = 0
                for line in body_lines:
                    p_str, move_str, _ = line.split("\t")
                    q_pos = apply_move(parse_position(p_str), move_str)
                    for _, qr_pos in legal_transitions(q_pos):
                        qr_str = qr_pos.to_fen()
                        if qr_str not in entry_keys:
                            self.assertFalse(in_check(qr_pos))
                            self.assertEqual(legal_moves(qr_pos), [])
                            stalemate_replies += 1
                self.assertGreater(stalemate_replies, 0)

    def test_v1_1_win_rejects_prover_stalemate_reply(self) -> None:
        # In K3/3q/2pp/1Nrk w - -, White plays b1c3 giving check to Black king on d1.
        # Black's ONLY legal reply is d3c3 -> K3/2q1/2pp/2rk w - -, which stalemates White!
        draw_cert = "\n".join(
            [
                "#cert v1",
                "#claim ATLEAST_DRAW w",
                "#root K3/3q/2pp/1Nrk w - -",
                "K3/3q/2pp/1Nrk w - -\tb1c3\t0",
            ]
        ) + "\n"
        self.assertTrue(
            verify_certificate(self._write_cert("prover_stale_reply_draw.cert", draw_cert)).valid
        )

        # Same reply in a WIN certificate MUST be INVALID.
        win_cert = "\n".join(
            [
                "#cert v1",
                "#claim WIN w",
                "#root K3/3q/2pp/1Nrk w - -",
                "K3/3q/2pp/1Nrk w - -\tb1c3\t1",
            ]
        ) + "\n"
        res_win = verify_certificate(self._write_cert("prover_stale_reply_win.cert", win_cert))
        self.assertFalse(res_win.valid)

        # Also check opponent-to-move root whose only reply stalemates the prover.
        opp_draw_cert = "\n".join(
            [
                "#cert v1",
                "#claim ATLEAST_DRAW w",
                "#root K3/2Nq/2pp/2rk b - -",
            ]
        ) + "\n"
        self.assertTrue(
            verify_certificate(self._write_cert("opp_stale_reply_draw.cert", opp_draw_cert)).valid
        )
        opp_win_cert = "\n".join(
            [
                "#cert v1",
                "#claim WIN w",
                "#root K3/2Nq/2pp/2rk b - -",
            ]
        ) + "\n"
        self.assertFalse(
            verify_certificate(self._write_cert("opp_stale_reply_win.cert", opp_win_cert)).valid
        )

    def test_v1_1_atleast_draw_rejects_prover_checkmate_reply(self) -> None:
        # In K3/2qr/1ppp/Nrkb w - -, White plays a1b3 giving check to Black king on c1.
        # Black's ONLY legal reply is c3b3 -> K3/1q1r/1ppp/1rkb w - -, which CHECKMATES White!
        draw_mate_cert = "\n".join(
            [
                "#cert v1",
                "#claim ATLEAST_DRAW w",
                "#root K3/2qr/1ppp/Nrkb w - -",
                "K3/2qr/1ppp/Nrkb w - -\ta1b3\t0",
            ]
        ) + "\n"
        res = verify_certificate(self._write_cert("prover_mate_reply_draw.cert", draw_mate_cert))
        self.assertFalse(res.valid)

        # Also check opponent-to-move root whose reply checkmates the prover.
        opp_mate_cert = "\n".join(
            [
                "#cert v1",
                "#claim ATLEAST_DRAW w",
                "#root K3/1Nqr/1ppp/1rkb b - -",
            ]
        ) + "\n"
        self.assertFalse(
            verify_certificate(self._write_cert("opp_mate_reply_draw.cert", opp_mate_cert)).valid
        )

    def test_v1_1_prover_stalemate_root_empty_body(self) -> None:
        # Prover stalemate at root with empty body is VALID for ATLEAST_DRAW (both sides).
        for side, root_fen in (("w", "K2/2q/2k w - -"), ("b", "k2/2Q/2K b - -")):
            with self.subTest(side=side, root_fen=root_fen):
                draw_cert = f"#cert v1\n#claim ATLEAST_DRAW {side}\n#root {root_fen}\n"
                res_draw = verify_certificate(
                    self._write_cert(f"prover_stale_root_draw_{side}.cert", draw_cert)
                )
                self.assertTrue(res_draw.valid, res_draw)
                self.assertEqual(res_draw.entries, 0)
                self.assertEqual(res_draw.max_rank, 0)

                # Same prover-stalemate root MUST be INVALID for WIN.
                win_cert = f"#cert v1\n#claim WIN {side}\n#root {root_fen}\n"
                self.assertFalse(
                    verify_certificate(
                        self._write_cert(f"prover_stale_root_win_{side}.cert", win_cert)
                    ).valid
                )

                # A prover-stalemate root may NOT appear as a body entry (no legal move exists).
                bad_entry = (
                    f"#cert v1\n#claim ATLEAST_DRAW {side}\n#root {root_fen}\n"
                    f"{root_fen}\ta3a2\t0\n"
                )
                self.assertFalse(
                    verify_certificate(
                        self._write_cert(f"prover_stale_entry_{side}.cert", bad_entry)
                    ).valid
                )

        # Prover CHECKMATE at root with empty body MUST be INVALID for ATLEAST_DRAW.
        mate_root = "#cert v1\n#claim ATLEAST_DRAW w\n#root K2/1q1/2k w - -\n"
        self.assertFalse(
            verify_certificate(self._write_cert("prover_mate_root_draw.cert", mate_root)).valid
        )

    def test_v1_1_invalid_pawns_castling_and_file_strictness_in_certs(self) -> None:
        # Pawns on rank 1 or rank H, either colour, on 3x3, 5x5, and 8x8 make certs INVALID.
        bad_pawn_cases = [
            ("3x3_P_top", "k1P/3/2K w - -", "c1b1"),
            ("3x3_p_top", "k1p/3/2K w - -", "c1b1"),
            ("3x3_P_bot", "k2/3/P1K w - -", "c1b1"),
            ("3x3_p_bot", "k2/3/p1K w - -", "c1b1"),
            ("5x5_P_top", "k3P/5/5/5/4K w - -", "e1d1"),
            ("5x5_p_top", "k3p/5/5/5/4K w - -", "e1d1"),
            ("5x5_P_bot", "k4/5/5/5/P3K w - -", "e1d1"),
            ("5x5_p_bot", "k4/5/5/5/p3K w - -", "e1d1"),
            ("8x8_P_top", "4k2P/8/8/8/8/8/8/4K3 w - -", "e1d1"),
            ("8x8_p_top", "4k2p/8/8/8/8/8/8/4K3 w - -", "e1d1"),
            ("8x8_P_bot", "4k3/8/8/8/8/8/8/P3K3 w - -", "e1d1"),
            ("8x8_p_bot", "4k3/8/8/8/8/8/8/p3K3 w - -", "e1d1"),
        ]
        for label, fen, move in bad_pawn_cases:
            with self.subTest(case=label):
                cert = f"#cert v1\n#claim ATLEAST_DRAW w\n#root {fen}\n{fen}\t{move}\t0\n"
                self.assertFalse(verify_certificate(self._write_cert(f"{label}.cert", cert)).valid)

        # Invalid pawn in an unreachable body entry with a valid root must also be INVALID.
        valid_root_bad_entry = (
            "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\n"
            "k2/2Q/2K w - -\tc2b2\t1\n"
            "k1p/3/2K w - -\tc1b1\t1\n"
        )
        self.assertFalse(
            verify_certificate(self._write_cert("bad_pawn_body.cert", valid_root_bad_entry)).valid
        )

        # Invalid castling rights in certificate root/body (no rook on h1) -> INVALID.
        bad_castle = (
            "#cert v1\n#claim ATLEAST_DRAW w\n#root 4k3/8/8/8/8/8/8/4K3 w K -\n"
            "4k3/8/8/8/8/8/8/4K3 w K -\te1d1\t0\n"
        )
        self.assertFalse(verify_certificate(self._write_cert("bad_castle.cert", bad_castle)).valid)

        # File strictness: leading zeros, signed ranks, and body comments -> INVALID.
        strictness_cases = [
            ("lead_zero_draw", "#cert v1\n#claim ATLEAST_DRAW w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t00\n"),
            ("lead_zero_win", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t01\n"),
            ("plus_rank", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t+1\n"),
            ("minus_zero", "#cert v1\n#claim ATLEAST_DRAW w\n#root k2/2Q/2K w - -\nk2/2Q/2K w - -\tc2b2\t-0\n"),
            ("body_comment", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\n# comment\nk2/2Q/2K w - -\tc2b2\t1\n"),
            ("body_comment_tabs", "#cert v1\n#claim WIN w\n#root k2/2Q/2K w - -\n# comment\tfoo\t0\nk2/2Q/2K w - -\tc2b2\t1\n"),
        ]
        for label, content in strictness_cases:
            with self.subTest(strictness=label):
                self.assertFalse(verify_certificate(self._write_cert(f"{label}.cert", content)).valid)


class TestCLI(unittest.TestCase):
    def _run(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, MCHECK_PATH, *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_verify_valid_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = os.path.join(tmpdir, "ok.cert")
            with open(valid_path, "w", encoding="utf-8") as fh:
                fh.write(build_win_certificate("k2/2Q/2K w - -", "w"))

            proc = self._run("verify", valid_path)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(proc.stdout.startswith("VALID\n"))
            for field in ("claim:", "root:", "entries:", "max_rank:", "seconds:"):
                self.assertIn(field, proc.stdout)

            bad_path = os.path.join(tmpdir, "bad.cert")
            with open(bad_path, "w", encoding="utf-8") as fh:
                fh.write("garbage\n")
            proc_bad = self._run("verify", bad_path)
            self.assertEqual(proc_bad.returncode, 1)
            self.assertTrue(proc_bad.stdout.startswith("INVALID\n"))
            self.assertIn("reason:", proc_bad.stdout)

    def test_cli_moves(self) -> None:
        proc = self._run("moves", "rqkr/pppp/4/PPPP/RQKR w - -")
        self.assertEqual(proc.returncode, 0)
        expected = [
            "a2a3\trqkr/pppp/P3/1PPP/RQKR b - -",
            "b2b3\trqkr/pppp/1P2/P1PP/RQKR b - -",
            "c2c3\trqkr/pppp/2P1/PP1P/RQKR b - -",
            "d2d3\trqkr/pppp/3P/PPP1/RQKR b - -",
        ]
        self.assertEqual(proc.stdout.splitlines(), expected)

    def test_cli_batch(self) -> None:
        inp = "\n".join(
            [
                "rqkr/pppp/4/PPPP/RQKR w - -",
                "k2/1Q1/2K b - -",
                "not a valid fen",
            ]
        ) + "\n"
        proc = self._run("batch", stdin=inp)
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            lines[0],
            "rqkr/pppp/4/PPPP/RQKR w - -\t"
            "a2a3:rqkr/pppp/P3/1PPP/RQKR b - -|"
            "b2b3:rqkr/pppp/1P2/P1PP/RQKR b - -|"
            "c2c3:rqkr/pppp/2P1/PP1P/RQKR b - -|"
            "d2d3:rqkr/pppp/3P/PPP1/RQKR b - -",
        )
        self.assertEqual(lines[1], "k2/1Q1/2K b - -\t")
        self.assertEqual(lines[2], "not a valid fen\tERROR")

    def test_cli_perft(self) -> None:
        proc = self._run(
            "perft", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", "2"
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "400")


if __name__ == "__main__":
    unittest.main()
