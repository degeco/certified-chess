# 03-checker, round 3: bring the checker to SPEC v1.2

A second checker (`08-checker2`, Go, written from the spec alone) now exists. It agrees with
yours on 6,197 mutated certificates and on move generation for 24,000 positions. It found two
inputs your checker accepts and it rejects. The spec now settles both (read
`../design/SPEC.md` sections 3, 4 and 7, "v1.2"). Same constraints as before: write only
inside `03-checker/`, do not read `../02-engine/` or `../08-checker2/`, standard library
only, keep it auditable.

## Changes required

1. **Line endings** (SPEC section 4): a carriage return anywhere in a certificate file makes
   it `INVALID`. Lines end with `\n` only; a missing final `\n` is accepted. Round 2 opened
   the file with universal newlines and also stripped a trailing `\r`.
2. **`ep` well-formedness** (SPEC section 3): reject an `ep` square unless every listed
   condition holds. Round 2 accepted `4k3/4p3/8/3Pp3/8/8/8/4K3 w - e6`, where the origin
   square of the double step (e7) is occupied.
3. Re-read the v1.2 validity list and the certificate file rules line by line against the
   code and fix any other difference you find. Report each one.

## Tests to add

- Certificates with `\r\n` line endings, with a bare `\r` inside a line, and with `\r` as the
  only line break: all `INVALID`. A valid certificate without a final newline: `VALID`.
- `ep` cases, each for White to move and mirrored for Black to move: origin square occupied
  (reject); target square occupied (reject); no enemy pawn in front (reject); wrong rank
  (reject); capturing pawn pinned so that no capture is legal (reject); a correct one
  (accept).
- All earlier tests still pass.

## Finish

Update `AUDIT.md`, append a "Round 3" section to `REPORT.md` with the full test output.
