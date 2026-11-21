#!/usr/bin/env bash
# Usage: compare.sh <dir> [sample size] [seed]
# Runs 03-checker (Python) and mcheck2 on every *.cert under <dir> (or on a seeded
# sample) and compares the verdict (first line + exit code).
# Prints the number of agreements and each disagreement with both verdicts.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dir="${1:?usage: compare.sh <dir> [sample] [seed]}"; sample="${2:-0}"; seed="${3:-1}"
py="$here/../03-checker/mcheck.py"; go="$here/mcheck2"
list="$(mktemp)"; trap 'rm -f "$list"' EXIT
find "$dir" -name '*.cert' | sort > "$list"
total=$(wc -l < "$list")
if [ "$sample" -gt 0 ] && [ "$total" -gt "$sample" ]; then
  shuf -n "$sample" --random-source=<(yes "$seed") "$list" | sort > "$list.s"; mv "$list.s" "$list"
fi
agree=0; dis=0; n=0; nv=0; ni=0
while IFS= read -r f; do
  # capture the whole output first: piping into head -1 would SIGPIPE the writer (rc 141)
  oa="$(python3 "$py" verify "$f" 2>&1)"; ra=$?; a="${oa%%$'\n'*}"
  ob="$("$go" verify "$f" 2>&1)"; rb=$?; b="${ob%%$'\n'*}"
  n=$((n+1))
  if [ "$a" = "$b" ] && [ "$ra" = "$rb" ]; then
    agree=$((agree+1)); if [ "$a" = VALID ]; then nv=$((nv+1)); else ni=$((ni+1)); fi
  else
    dis=$((dis+1)); echo "DISAGREE $f: python=[$a rc=$ra] go=[$b rc=$rb]"
  fi
done < "$list"
echo "compared $n of $total certs under $dir: agree=$agree (VALID=$nv INVALID=$ni) disagree=$dis"
[ "$dis" -eq 0 ]
