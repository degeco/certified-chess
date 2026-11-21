#!/usr/bin/env python3
"""Integration test: run msolve on test cases and verify every certificate with BOTH
../03-checker/mcheck.py AND ../08-checker2/mcheck2."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSOLVE = os.path.join(ROOT_DIR, "msolve")
MCHECK = os.path.join(os.path.dirname(ROOT_DIR), "03-checker", "mcheck.py")
MCHECK2 = os.path.join(os.path.dirname(ROOT_DIR), "08-checker2", "mcheck2")


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def verify_cert_both(path: str) -> tuple[bool, str]:
    r1 = run_cmd([sys.executable, MCHECK, "verify", path])
    ok1 = r1.returncode == 0 and r1.stdout.startswith("VALID")
    r2 = run_cmd([MCHECK2, "verify", path])
    ok2 = r2.returncode == 0 and r2.stdout.startswith("VALID")
    detail = f"mcheck1={'VALID' if ok1 else r1.stdout.strip()} mcheck2={'VALID' if ok2 else r2.stdout.strip()}"
    return (ok1 and ok2), f"{detail}\n{r1.stdout.strip()}"


def main() -> int:
    failures = 0

    def assert_ok(cond: bool, msg: str) -> None:
        nonlocal failures
        if cond:
            print(f"[PASS] {msg}")
        else:
            print(f"[FAIL] {msg}")
            failures += 1

    with tempfile.TemporaryDirectory(prefix="msolve_test_") as tmp:
        # 1. Forced mates on 8x8 (mate in 2, 3, 4, 5)
        mate_cases = [
            ("8x8_mate2", "3r2k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - -", "WIN w", 2),
            ("8x8_mate3_br", "r1r3k1/5ppp/8/8/8/4Q3/4RPPP/4R1K1 w - -", "WIN w", 3),
            ("8x8_mate3_phil", "4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -", "WIN w", 3),
            ("8x8_mate4_phil", "4r2k/6pp/8/6N1/8/1Q6/6PP/6K1 w - -", "WIN w", 4),
            ("8x8_mate5_phil", "2r3k1/6pp/8/6N1/1Q6/8/5PPP/6K1 w - -", "WIN w", 5),
            ("mini4x4_KQ_K", "3k/4/4/KQ2 w - -", "WIN w", None),
        ]

        for name, fen, claim, exp_max_rank in mate_cases:
            cert_path = os.path.join(tmp, f"{name}.cert")
            res = run_cmd([MSOLVE, fen, "--claim", claim, "--out", cert_path, "--max-seconds", "15", "--tt-mb", "64"])
            assert_ok(res.returncode == 0, f"{name}: msolve exit 0 (got {res.returncode})")
            if res.returncode == 0:
                ok, out = verify_cert_both(cert_path)
                assert_ok(ok, f"{name}: both checkers VALID ({out.splitlines()[0]})")
                if exp_max_rank is not None:
                    mr = None
                    for line in out.splitlines():
                        if line.startswith("max_rank:"):
                            mr = int(line.split(":")[1].strip())
                    assert_ok(mr is not None and mr <= exp_max_rank, f"{name}: max_rank={mr} <= {exp_max_rank}")

        # 2. mini4x4 full check (--claim WIN w, --value)
        c_m4 = os.path.join(tmp, "mini4x4_win_w.cert")
        r = run_cmd([MSOLVE, "mini4x4", "--claim", "WIN w", "--out", c_m4, "--max-seconds", "15", "--tt-mb", "64"])
        assert_ok(r.returncode == 0, f"mini4x4 WIN w proved (rc={r.returncode})")
        ok, _ = verify_cert_both(c_m4)
        assert_ok(ok, "mini4x4 WIN w both checkers VALID")

        r_val = run_cmd([MSOLVE, "mini4x4", "--value", "--out-prefix", os.path.join(tmp, "val_m4"), "--max-seconds", "15", "--tt-mb", "64"])
        assert_ok(r_val.returncode == 0 and "value: WIN w" in r_val.stdout, "mini4x4 --value == WIN w")
        ok, _ = verify_cert_both(os.path.join(tmp, "val_m4_win_w.cert"))
        assert_ok(ok, "mini4x4 --value cert both checkers VALID")

        # 3. Draw position (K vs K on 3x3 and 4x4) via --value
        for bname, fen in [("kvk3x3", "k2/3/2K w - -"), ("kvk4x4", "k3/4/4/3K w - -")]:
            pref = os.path.join(tmp, f"val_{bname}")
            rv = run_cmd([MSOLVE, fen, "--value", "--out-prefix", pref, "--max-seconds", "15", "--tt-mb", "64"])
            assert_ok(rv.returncode == 0 and "value: DRAW" in rv.stdout, f"{bname} --value == DRAW")
            if rv.returncode == 0:
                ok_w, _ = verify_cert_both(f"{pref}_draw_w.cert")
                ok_b, _ = verify_cert_both(f"{pref}_draw_b.cert")
                assert_ok(ok_w and ok_b, f"{bname} both ATLEAST_DRAW certs both checkers VALID")

        # 4. Prover stalemate at root (SPEC v1.2)
        c_st = os.path.join(tmp, "stalemate.cert")
        rs = run_cmd([MSOLVE, "4/1q2/2k1/K3 w - -", "--claim", "ATLEAST_DRAW w", "--out", c_st])
        assert_ok(rs.returncode == 0, "prover-stalemate ATLEAST_DRAW w exit 0")
        ok, _ = verify_cert_both(c_st)
        assert_ok(ok, "prover-stalemate ATLEAST_DRAW w both checkers VALID (0 entries)")

        c_st2 = os.path.join(tmp, "stalemate_b.cert")
        rs2 = run_cmd([MSOLVE, "1k2/1P2/1K2/4 b - -", "--claim", "ATLEAST_DRAW b", "--out", c_st2])
        assert_ok(rs2.returncode == 0, "stalemate_b ATLEAST_DRAW b exit 0")
        ok, _ = verify_cert_both(c_st2)
        assert_ok(ok, "stalemate_b ATLEAST_DRAW b both checkers VALID")

        # 5. Tablebase splice on 4x5 (5pc position with capture into 4pc TB win)
        c_tb5 = os.path.join(tmp, "tb5_win.cert")
        r5 = run_cmd([MSOLVE, "k3/1r2/2P1/1Q2/3K w - -", "--claim", "WIN w", "--out", c_tb5, "--max-seconds", "15", "--tt-mb", "64"])
        assert_ok(r5.returncode == 0 and "tb_hits:" in r5.stdout, "4x5 5pc TB-assisted WIN w solved")
        if r5.returncode == 0:
            ok, _ = verify_cert_both(c_tb5)
            assert_ok(ok, "4x5 5pc TB-spliced cert both checkers VALID")

        # 6. msolve merge CLI end-to-end test on mini4x4 (1. d2d3 -> Black replies c4d3, b4b3, a4a3)
        # Wait: let's test 1. a2a3 (or 1. c2d3 where Black's only legal reply is d4d3, plus 1. d2d3!).
        # Actually on mini4x4: after 1. b2a3 -> rqkr/Pppp/P1PP/RQKR b - -? Wait: White pawn on b2 captures a3!
        # Let's use 1. c2d3 (only legal reply d4d3 -> rqk1/pppr/PP1P/RQKR w - -) AND also test multi-reply merge on 8x8_mate3_phil!
        # In 8x8_mate3_phil (4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -), 1. Nh6+ has 2 Black replies: 1... Kh8 and 1... Kf8!
        m8_subs = [
            ("phil_kh8", "4r2k/5Npp/7N/8/8/1Q6/6PP/6K1 w - -"),  # wait: Nh6+ moves N from f7 to h6!
        ]
        # Exact FENs after 1. f7h6+: 4r1k1/6pp/7N/8/8/1Q6/6PP/6K1 b - -
        # Black replies: g8h8 -> 4r2k/6pp/7N/8/8/1Q6/6PP/6K1 w - -, g8f8 -> 4rk2/6pp/7N/8/8/1Q6/6PP/6K1 w - -
        merge_subs = [
            ("phil_kh8", "4r2k/6pp/7N/8/8/1Q6/6PP/6K1 w - -"),
            ("phil_kf8", "4rk2/6pp/7N/8/8/1Q6/6PP/6K1 w - -"),
        ]
        sub_paths = []
        for sname, sfen in merge_subs:
            sp = os.path.join(tmp, f"{sname}.cert")
            sr = run_cmd([MSOLVE, sfen, "--claim", "WIN w", "--out", sp, "--max-seconds", "10", "--tt-mb", "32"])
            assert_ok(sr.returncode == 0, f"merge sub {sname} proved")
            sub_paths.append(sp)
        merged_p = os.path.join(tmp, "phil_merged.cert")
        mr = run_cmd([MSOLVE, "merge", "--root", "4r1k1/5Npp/8/8/8/1Q6/6PP/6K1 w - -", "--claim", "WIN w",
                      "--root-move", "f7h6", "--out", merged_p] + sub_paths)
        assert_ok(mr.returncode == 0 and "status: MERGED_VALID" in mr.stdout, f"msolve merge phil exit 0 (got {mr.returncode}: {mr.stderr.strip()})")
        if mr.returncode == 0:
            ok, _ = verify_cert_both(merged_p)
            assert_ok(ok, "msolve merge phil cert both checkers VALID")

    if failures == 0:
        print("ALL PYTHON + DUAL-CHECKER INTEGRATION TESTS PASSED")
        return 0
    print(f"{failures} INTEGRATION TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
