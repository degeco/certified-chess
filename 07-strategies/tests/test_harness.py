"""Unit tests for the strategy-program harness (SPEC v1.1 / LOOP v1 round 2)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import harness  # noqa: E402


class HarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_prog(self, name: str, code: str) -> Path:
        path = self.tmp_dir / name
        path.write_text(code, encoding="utf-8")
        return path

    # --- Length metrics (bytes and AST nodes) & static validation ---

    def test_measure_length_and_nodes_strip_docstrings_and_comments(self) -> None:
        code = '''"""Module docstring
spanning lines."""

# Leading comment
import rules  # inline comment


def move(pos):
    """Function docstring."""
    # Another comment
    return rules.legal_moves(pos)[0]  # trailing
'''
        expected = "import rules\ndef move(pos):\n    return rules.legal_moves(pos)[0]\n"
        self.assertEqual(harness.measure_program_length(code), len(expected.encode("utf-8")))
        self.assertEqual(
            harness.measure_program_nodes(code),
            harness.measure_program_nodes(expected),
        )
        # Adding a docstring or renaming variables must NOT change AST node count.
        renamed = "import rules\ndef move(position_arg):\n    return rules.legal_moves(position_arg)[0]\n"
        self.assertEqual(
            harness.measure_program_nodes(code),
            harness.measure_program_nodes(renamed),
        )

    def test_reject_forbidden_import(self) -> None:
        prog = self._write_prog(
            "bad_import.py",
            "import math\nimport rules\ndef move(pos):\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(prog)

    def test_reject_from_import_non_rules(self) -> None:
        prog = self._write_prog(
            "bad_from_import.py",
            "from os import path\nimport rules\ndef move(pos):\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(prog)

    def test_allow_exception_table_at_full_price(self) -> None:
        # Round 2 Rule 3: explicit position-to-move exception table is allowed,
        # and every node and byte of it counts in length.
        base_code = "import rules\ndef move(pos):\n    return rules.legal_moves(pos)[0]\n"
        table_code = (
            'import rules\n'
            'EXCEPTIONS = {"k1K1/4/4/2Q1 w - -": "c1a1"}\n'
            'def move(pos):\n'
            '    f = pos.to_fen()\n'
            '    if f in EXCEPTIONS:\n'
            '        return EXCEPTIONS[f]\n'
            '    return rules.legal_moves(pos)[0]\n'
        )
        p_base = self._write_prog("base.py", base_code)
        p_tbl = self._write_prog("tbl.py", table_code)
        _, b_base, n_base = harness.validate_program(p_base)
        _, b_tbl, n_tbl = harness.validate_program(p_tbl)
        self.assertGreater(b_tbl, b_base)
        self.assertGreater(n_tbl, n_base)
        move_fn, _ = harness.load_strategy(p_tbl)
        res = harness.expand_strategy(move_fn, "WIN w", "k1K1/4/4/2Q1 w - -", max_entries=10)
        self.assertTrue(res.ok, res.failure_reason)
        self.assertEqual(res.entries["k1K1/4/4/2Q1 w - -"], ("c1a1", 1))

    def test_reject_over_length_limit(self) -> None:
        prog = self._write_prog(
            "too_long.py",
            "import rules\ndef move(pos):\n    x = 1\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(prog, length_limit=20)

    # --- Round 2 Rule 2: lookahead, recursion, while loops, memo tables ---

    def test_reject_direct_and_mutual_recursion(self) -> None:
        rec = self._write_prog(
            "rec.py",
            "import rules\ndef helper(pos, d):\n    return helper(pos, d - 1) if d else None\n"
            "def move(pos):\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(rec)

        mut = self._write_prog(
            "mut.py",
            "import rules\ndef a(x):\n    return b(x)\ndef b(x):\n    return a(x)\n"
            "def move(pos):\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(mut)

    def test_reject_while_search_loop(self) -> None:
        prog = self._write_prog(
            "while_loop.py",
            "import rules\ndef move(pos):\n    q = [pos]\n    while q:\n        q.pop()\n"
            "    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(prog)

    def test_reject_memo_table_mutation_and_mutable_defaults(self) -> None:
        memo_mod = self._write_prog(
            "memo_mod.py",
            "import rules\nMEMO = {}\ndef move(pos):\n    MEMO[pos.to_fen()] = 'a1a2'\n"
            "    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(memo_mod)

        memo_def = self._write_prog(
            "memo_def.py",
            "import rules\ndef move(pos, cache={}):\n    return rules.legal_moves(pos)[0]\n",
        )
        with self.assertRaises(harness.ProgramValidationError):
            harness.validate_program(memo_def)

    def test_runtime_reject_three_ply_lookahead(self) -> None:
        # Allowed: ply 0 (pos) -> ply 1 (nxt) -> ply 2 (rp).
        # Forbidden: calling legal_transitions(rp) at ply 2 to look at ply 3.
        prog = self._write_prog(
            "three_ply.py",
            """import rules
def move(pos):
    for m, nxt in rules.legal_transitions(pos):
        for _, rp in rules.legal_transitions(nxt):
            _ = rules.legal_transitions(rp)
            return m
    return rules.legal_moves(pos)[0]
""",
        )
        move_fn, _ = harness.load_strategy(prog, enforce_lookahead=True)
        res = harness.expand_strategy(move_fn, "WIN w", "3k/4/4/K1Q1 w - -", max_entries=50)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "lookahead_limit")

    def test_runtime_allow_two_ply_lookahead(self) -> None:
        prog = self._write_prog(
            "two_ply.py",
            """import rules
def move(pos):
    for m, nxt in rules.legal_transitions(pos):
        reps = rules.legal_transitions(nxt)
        if not reps and rules.in_check(nxt):
            return m
    return rules.legal_moves(pos)[0]
""",
        )
        move_fn, _ = harness.load_strategy(prog, enforce_lookahead=True)
        res = harness.expand_strategy(move_fn, "WIN w", "k1K1/4/4/2Q1 w - -", max_entries=50)
        self.assertTrue(res.ok, res.failure_reason)

    # --- Deliberately wrong program for EACH failure kind ---

    def test_failure_cycle(self) -> None:
        prog = self._write_prog(
            "cycle_prog.py",
            """import rules
def move(pos):
    if pos.at(0, 0) == "K":
        return "a1b1"
    return "b1a1"
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "WIN w", "3k/4/Q3/K3 w - -", max_entries=500)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "cycle")
        self.assertIsNotNone(res.failure_pos)

    def test_failure_stalemate(self) -> None:
        prog = self._write_prog(
            "stalemate_prog.py",
            """import rules
def move(pos):
    return "c1b2"
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "WIN w", "k3/2K1/4/2Q1 w - -", max_entries=50)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "stalemate")
        self.assertEqual(res.failure_pos, "k3/2K1/4/2Q1 w - -")

    def test_failure_illegal_move(self) -> None:
        prog = self._write_prog(
            "illegal_prog.py",
            """import rules
def move(pos):
    return "a1d4"
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "WIN w", "3k/4/4/K1Q1 w - -", max_entries=50)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "illegal_move")
        self.assertEqual(res.failure_pos, "3k/4/4/K1Q1 w - -")

    def test_failure_missing_move(self) -> None:
        prog = self._write_prog(
            "missing_prog.py",
            """import rules
def move(pos):
    return None
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "WIN w", "3k/4/4/K1Q1 w - -", max_entries=50)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "missing_move")
        self.assertEqual(res.failure_pos, "3k/4/4/K1Q1 w - -")

    def test_failure_program_error(self) -> None:
        prog = self._write_prog(
            "error_prog.py",
            """import rules
def move(pos):
    raise RuntimeError("boom")
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "WIN w", "3k/4/4/K1Q1 w - -", max_entries=50)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "program_error")
        self.assertEqual(res.failure_pos, "3k/4/4/K1Q1 w - -")

    def test_failure_entry_limit(self) -> None:
        prog = self._write_prog(
            "draw_prog.py",
            """import rules
def move(pos):
    return rules.legal_moves(pos)[0]
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "ATLEAST_DRAW w", "3k/4/4/K3 w - -", max_entries=2)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "entry_limit")
        self.assertIsNotNone(res.failure_pos)

    def test_failure_checkmated(self) -> None:
        prog = self._write_prog(
            "mated_prog.py",
            """import rules
def move(pos):
    return rules.legal_moves(pos)[0]
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "ATLEAST_DRAW b", "k3/4/2K1/3Q b - -", max_entries=200)
        self.assertFalse(res.ok)
        self.assertEqual(res.failure_kind, "checkmated")

    # --- Prover-stalemate rule in ATLEAST_DRAW (SPEC v1.1) ---

    def test_atleast_draw_prover_stalemate_root_and_child(self) -> None:
        prog = self._write_prog(
            "any_draw.py",
            """import rules
def move(pos):
    return rules.legal_moves(pos)[0]
""",
        )
        move_fn, _ = harness.load_strategy(prog)
        res = harness.expand_strategy(move_fn, "ATLEAST_DRAW b", "k3/2K1/1Q2/4 b - -", max_entries=50)
        self.assertTrue(res.ok, res.failure_reason)
        self.assertEqual(len(res.entries), 0)
        cert = self.tmp_dir / "stalemate_root.cert"
        harness.write_certificate(res, cert)
        valid, entries, max_rank, _, detail = harness.verify_with_mcheck(cert)
        self.assertTrue(valid, detail)
        self.assertEqual(entries, 0)
        self.assertEqual(max_rank, 0)

        res_kk = harness.expand_strategy(move_fn, "ATLEAST_DRAW w", "3k/4/4/K3 w - -", max_entries=500)
        self.assertTrue(res_kk.ok, res_kk.failure_reason)
        cert_kk = self.tmp_dir / "kk.cert"
        harness.write_certificate(res_kk, cert_kk)
        valid, entries, max_rank, _, detail = harness.verify_with_mcheck(cert_kk)
        self.assertTrue(valid, detail)
        self.assertGreater(entries, 0)
        self.assertEqual(max_rank, 0)

    # --- Wrong on one root cannot get a VALID certificate for that root ---

    def test_wrong_on_one_root_cannot_get_valid_certificate(self) -> None:
        good_root = "k1K1/4/4/2Q1 w - -"
        bad_root = "k3/2K1/4/2Q1 w - -"

        prog = self._write_prog(
            "one_bad_root.py",
            """import rules
def move(pos):
    if pos.at(2, 3) == "K":
        return "c1a1"
    return "c1b2"
""",
        )

        fam_dir = self.tmp_dir / "families"
        fam_dir.mkdir()
        (fam_dir / "two_roots.json").write_text(
            json.dumps(
                {
                    "name": "two_roots",
                    "claim": "WIN w",
                    "length_limit": 2000,
                    "max_entries": 100,
                    "roots": [good_root, bad_root],
                }
            ),
            encoding="utf-8",
        )
        scores_tsv = self.tmp_dir / "scores.tsv"
        summary = harness.score_program(
            prog,
            "two_roots",
            families_dir=fam_dir,
            scores_path=scores_tsv,
            jobs=1,
            record=True,
        )
        self.assertEqual(summary["covered"], 1)
        self.assertEqual(summary["total"], 2)
        failures = summary["failures"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].root, bad_root)
        self.assertEqual(failures[0].failure_kind, "stalemate")

        bad_cert = self.tmp_dir / "bad.cert"
        proc = subprocess.run(
            [
                sys.executable,
                str(BASE_DIR / "harness.py"),
                "expand",
                str(prog),
                "--claim",
                "WIN w",
                "--root",
                bad_root,
                "--out",
                str(bad_cert),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("FAILED", proc.stdout)
        self.assertFalse(bad_cert.exists())

        good_cert = self.tmp_dir / "good.cert"
        proc2 = subprocess.run(
            [
                sys.executable,
                str(BASE_DIR / "harness.py"),
                "expand",
                str(prog),
                "--claim",
                "WIN w",
                "--root",
                good_root,
                "--out",
                str(good_cert),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc2.returncode, 0, proc2.stdout + proc2.stderr)
        valid, entries, max_rank, _, detail = harness.verify_with_mcheck(good_cert)
        self.assertTrue(valid, detail)
        self.assertEqual(entries, 1)
        self.assertEqual(max_rank, 1)

    # --- Whole-class expand-all & audit-rank tests ---

    def test_expand_all_and_audit_rank_on_small_board(self) -> None:
        # 3x3 KQK is tiny and fast for unit testing expand-all + mcheck + audit-rank
        cert = self.tmp_dir / "kqk_3x3.cert"
        res = harness.expand_all_class(
            BASE_DIR / "strategies" / "kqk_v5.py",
            "KQK",
            3,
            3,
            cert,
            jobs=1,
            verify=True,
        )
        self.assertGreater(res["valid_positions"], 0)
        self.assertGreater(res["entries"], 0)
        self.assertTrue(res["verify_ok"], res["verify_detail"])
        self.assertEqual(res["verified_entries"], res["entries"])

        aud = harness.audit_rank(
            BASE_DIR / "strategies" / "kqk_v5.py",
            cert,
            jobs=1,
        )
        self.assertEqual(aud["entries"], res["entries"])
        self.assertEqual(
            aud["total_steps"], aud["decrease"] + aud["equal"] + aud["increase"]
        )

    # --- Round 3: LIA linter and witness-move audit ---

    def test_lint_lia_rejects_nonlinear_and_loops_and_accepts_linear(self) -> None:
        # kqk_v7 uses bw * bh and a generator sum over squares -> must be rejected
        res_v7 = harness.lint_lia(BASE_DIR / "strategies" / "kqk_v7.py")
        self.assertFalse(res_v7["ok"])
        joined = "\n".join(res_v7["violations"])
        self.assertIn("bw * bh", joined)
        self.assertIn("sum", joined)

        # Division by variable must be rejected
        bad_div = self._write_prog(
            "bad_div.py",
            "import rules\ndef _pot(pos):\n    return (pos.width // pos.height,)\ndef move(pos):\n    return rules.legal_moves(pos)[0]\n",
        )
        res_div = harness.lint_lia(bad_div)
        self.assertFalse(res_div["ok"])

        # Pure LIA function must be accepted
        good_lia = self._write_prog(
            "good_lia.py",
            """import rules
def _f(p, c):
    i = p.board.index(c)
    return i % p.width, i // p.width
def _pot(pos):
    if "Q" not in pos.board:
        return (99, 99)
    w, h = pos.width, pos.height
    kf, kr = _f(pos, "K")
    qf, qr = _f(pos, "Q")
    bf, br = _f(pos, "k")
    d = abs(kf - bf) + max(abs(kr - br), 2 * (w // 2))
    return (0, d if bf < qf else -d)
def move(pos):
    return rules.legal_moves(pos)[0]
""",
        )
        res_good = harness.lint_lia(good_lia)
        self.assertTrue(res_good["ok"], res_good["violations"])

    def test_audit_hint_reports_violations_on_bad_hint(self) -> None:
        prog = self._write_prog(
            "bad_hint.py",
            """import rules
def _pot(pos):
    return (0,)
def hint(pos):
    return "a1a1"
def move(pos):
    return rules.legal_moves(pos)[0]
""",
        )
        res = harness.audit_hint(prog, "KQK", 3, 3, jobs=1)
        self.assertFalse(res["ok"])
        self.assertEqual(res["illegal"], res["valid_positions"])


if __name__ == "__main__":
    unittest.main()
