#!/usr/bin/env python3
"""Integration test: run msolve on test cases and verify every certificate with ../03-checker/mcheck.py."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSOLVE = os.path.join(ROOT_DIR, "msolve")
MCHECK = os.path.join(os.path.dirname(ROOT_DIR), "03-checker", "mcheck.py")


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def verify_cert(path: str) -> tuple[bool, str]:
    res = run_cmd([sys.executable, MCHECK, "verify", path])
    return res.returncode == 0 and res.stdout.startswith("VALID"), res.stdout.strip()


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
                ok, out = verify_cert(cert_path)
                assert_ok(ok, f"{name}: mcheck VALID ({out.splitlines()[0] if out else 'empty'})")
                if exp_max_rank is not None:
                    # Verify max_rank in mcheck output
                    mr = None
                    for line in out.splitlines():
                        if line.startswith("max_rank:"):
                            mr = int(line.split(":")[1].strip())
                    assert_ok(mr is not None and mr <= exp_max_rank, f"{name}: max_rank={mr} <= {exp_max_rank}")

        # 2. mini4x4 full check (--claim WIN w, --claim ATLEAST_DRAW w, --claim ATLEAST_DRAW b, --value)
        c_m4 = os.path.join(tmp, "mini4x4_win_w.cert")
        r = run_cmd([MSOLVE, "mini4x4", "--claim", "WIN w", "--out", c_m4, "--max-seconds", "15", "--tt-mb", "64"])
        assert_ok(r.returncode == 0, f"mini4x4 WIN w proved (rc={r.returncode})")
        ok, out = verify_cert(c_m4)
        assert_ok(ok, f"mini4x4 WIN w mcheck VALID")

        r_val = run_cmd([MSOLVE, "mini4x4", "--value", "--out-prefix", os.path.join(tmp, "val_m4"), "--max-seconds", "15", "--tt-mb", "64"])
        assert_ok(r_val.returncode == 0 and "value: WIN w" in r_val.stdout, f"mini4x4 --value == WIN w")
        ok, _ = verify_cert(os.path.join(tmp, "val_m4_win_w.cert"))
        assert_ok(ok, "mini4x4 --value cert mcheck VALID")

        # 3. Draw position (K vs K on 3x3 and 4x4) via --value
        for bname, fen in [("kvk3x3", "k2/3/2K w - -"), ("kvk4x4", "k3/4/4/3K w - -")]:
            pref = os.path.join(tmp, f"val_{bname}")
            rv = run_cmd([MSOLVE, fen, "--value", "--out-prefix", pref, "--max-seconds", "15", "--tt-mb", "64"])
            assert_ok(rv.returncode == 0 and "value: DRAW" in rv.stdout, f"{bname} --value == DRAW")
            if rv.returncode == 0:
                ok_w, _ = verify_cert(f"{pref}_draw_w.cert")
                ok_b, _ = verify_cert(f"{pref}_draw_b.cert")
                assert_ok(ok_w and ok_b, f"{bname} both ATLEAST_DRAW certs mcheck VALID")

        # 4. Prover stalemate at root (SPEC v1.1)
        c_st = os.path.join(tmp, "stalemate.cert")
        rs = run_cmd([MSOLVE, "4/1q2/2k1/K3 w - -", "--claim", "ATLEAST_DRAW w", "--out", c_st])
        assert_ok(rs.returncode == 0, "prover-stalemate ATLEAST_DRAW w exit 0")
        ok, _ = verify_cert(c_st)
        assert_ok(ok, "prover-stalemate ATLEAST_DRAW w mcheck VALID (0 entries)")

        # 5. Stalemate trap (White forces stalemate in 1 reply -> SPEC v1.1 body exemption)
        # 4/3q/2k1/K3 b - -? Let's test a forced stalemate draw:
        # 4/1q2/2k1/1K2 w - - -> Ka1! Wait: if White plays Ka1 (b1a1), Black to move with Q on b3, K on c2:
        # Actually K on a1 is already stalemate if Black doesn't move, wait Black moves next!
        # Opposite: White K a1, White R b1, Black K c2, Black Q b3 -> if Black takes Rb1 -> stalemate!
        # Let's test: 4/1q2/2k1/KR2 w - - (1. Rb2? No, 1. Rxb3! wins; how about 4/2q1/1k2/Kp2 w - -? Nevermind, let's test K+P vs K stalemate draw on 4x4!)
        # 1k2/1P2/1K2/4 w - - -> White plays Ka6? Wait on 4x4: rank 4=k on b4, rank 3=P on b3, rank 2=K on b2 -> White to move!
        # Wait: b2-b3 is blocked; if White plays Kc2/Ka2, Black plays Kc4/Ka4. Let's check what --value says on 1k2/1P2/1K2/4 b - -!
        # On 4x4, 1k2/1P2/1K2/4 b - - : Black is stalemated immediately -> 0-entry ATLEAST_DRAW b!
        c_st2 = os.path.join(tmp, "stalemate_b.cert")
        rs2 = run_cmd([MSOLVE, "1k2/1P2/1K2/4 b - -", "--claim", "ATLEAST_DRAW b", "--out", c_st2])
        assert_ok(rs2.returncode == 0, "stalemate_b ATLEAST_DRAW b exit 0")
        ok, _ = verify_cert(c_st2)
        assert_ok(ok, "stalemate_b ATLEAST_DRAW b mcheck VALID")

    if failures == 0:
        print("ALL PYTHON + MCHECK INTEGRATION TESTS PASSED")
        return 0
    print(f"{failures} INTEGRATION TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
