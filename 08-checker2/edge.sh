#!/usr/bin/env bash
# Hand-made edge certificates (edge/*.cert): both checkers must give the same verdict.
here="$(cd "$(dirname "$0")" && pwd)"; fail=0; n=0
for f in "$here"/edge/*.cert; do
  a=$(python3 "$here/../03-checker/mcheck.py" verify "$f" 2>&1 | head -1)
  b=$("$here/mcheck2" verify "$f" 2>&1 | head -1)
  n=$((n+1)); [ "$a" = "$b" ] || { fail=1; echo "DIFF $f python=$a go=$b"; }
done
echo "edge certs: $n compared, $([ $fail = 0 ] && echo all agree || echo DISAGREEMENTS)"; exit $fail
