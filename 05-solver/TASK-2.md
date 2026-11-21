# 05-solver, round 2: settle `mini4x5`

Round 1 is accepted: every certificate you reported was re-verified by the lead with
`mcheck.py`, and `ATLEAST_DRAW w` for `mini4x5` (6,107 entries) also reproduced on a cloud
runner. Read `../AGENTS.md` again (new "Time" section) and `../design/SPEC.md` (now v1.2:
line endings and `ep` validity are spelled out; nothing changes for the solver's output).

## What the lead measured after round 1

A 25-minute run on this laptop, `./msolve mini4x5 --claim "WIN w" --max-seconds 1500
--max-nodes 600000000 --tt-mb 3072`, ended with `LIMIT` after 495,912,960 nodes:

```
a2a3 pn=2000000000 dn=0        (disproved: does not win)
b2b3 pn=968884318  dn=15
c2c3 pn=2000000000 dn=0        (disproved: does not win)
d2d3 pn=825360338  dn=1000000000
```

So more time alone does not help: the numbers on `d2d3` are at the saturation limit you
described in your own "Known gaps". Only `d2d3` can still win.

## Goal

Decide the value of `mini4x5`: either a `WIN w` certificate, or an `ATLEAST_DRAW b`
certificate (which together with the existing `ATLEAST_DRAW w` proves a draw). Either one
must be accepted by **both** checkers: `python3 ../03-checker/mcheck.py verify` and
`../08-checker2/mcheck2 verify` (build it with `make -C ../08-checker2` if needed; do not
read its source).

## Work, in this order

1. Fix the search so that it stays discriminating on deep, transposition-heavy trees:
   wider counters and a treatment of DAG overcounting are the two fixes you named. Show with
   a before/after measurement on `rqkr/1p1p/pPpP/P1PR/RQK1 b - -` (the bottleneck position
   of round 1) that it helps.
2. Use the tablebases. `../04-tablebase` has complete 2 to 4 piece tables for 4x5 and can
   extract certificates (`tbgen cert`); read its `REPORT.md` and sources. A search that stops
   at a tablebase position and splices in the extracted certificate should cut the 20 to 40
   plies your round 1 proofs spent converting won endgames. The final output must still be
   one flat SPEC certificate.
3. Divide the problem and keep every piece: prove sub-positions separately, save each
   certificate, and add a `msolve merge` that combines sub-certificates and the connecting
   moves into one certificate for the root. A merged certificate is checked like any other.
4. If the value is still open at the end, say exactly which positions remain, with their
   proof numbers, and give the command lines for runs longer than your 5-minute limit. The
   lead can run those on a cloud runner (2 cores, 7 GB, up to 6 hours).

## Report

Append "Round 2" to `REPORT.md` early and update it after every result. A value for
`mini4x5` counts only with both checkers' `VALID`. Anything else is reported as unproved.
