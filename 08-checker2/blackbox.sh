#!/usr/bin/env bash
# Black-box move comparison: mcheck2 batch against 02-engine/bin/mchess batch on
# 3000 random positions per board size. Fails on any difference.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
eng="$here/../02-engine/bin/mchess"; chk="$here/mcheck2"
n="${1:-3000}"; seed="${2:-1}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
for size in 3x3 3x4 4x4 4x5 5x5 5x6 6x6 8x8; do
  w="${size%x*}"; h="${size#*x}"
  "$eng" random "$w" "$h" "$n" "$seed" > "$tmp/pos"
  "$eng" batch < "$tmp/pos" > "$tmp/a"
  "$chk" batch < "$tmp/pos" > "$tmp/b"
  if cmp -s "$tmp/a" "$tmp/b"; then
    printf '%s  OK   %s positions\n' "$size" "$(wc -l < "$tmp/pos")"
  else
    fail=1
    printf '%s  DIFF first mismatches:\n' "$size"
    diff "$tmp/a" "$tmp/b" | head -4
  fi
done
exit $fail
