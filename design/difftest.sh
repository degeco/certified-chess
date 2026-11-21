#!/usr/bin/env bash
# Differential test: 02-engine (C++) against 03-checker (Python), move for move.
# Usage: design/difftest.sh [positions per board, default 2000] [seed, default 1]
# Passes only if both implementations print identical legal moves and identical
# canonical successor positions for every sampled position on every board size.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
n="${1:-2000}"; seed="${2:-1}"
eng="$root/02-engine/bin/mchess"; chk="$root/03-checker/mcheck.py"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
for size in 3x3 3x4 4x4 4x5 5x5 5x6 6x6 8x8; do
  w="${size%x*}"; h="${size#*x}"
  "$eng" random "$w" "$h" "$n" "$seed" | sort -u >"$tmp/pos"
  "$eng" batch <"$tmp/pos" >"$tmp/a"
  python3 "$chk" batch <"$tmp/pos" >"$tmp/b"
  if cmp -s "$tmp/a" "$tmp/b"; then
    printf '%s  OK   %s positions\n' "$size" "$(wc -l <"$tmp/pos")"
  else
    fail=1
    printf '%s  DIFF first mismatch:\n' "$size"
    diff "$tmp/a" "$tmp/b" | head -4
  fi
done
exit "$fail"
