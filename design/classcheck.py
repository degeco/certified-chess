"""Count how many valid White-to-move positions of K+piece vs K a union certificate covers.
Usage: design/classcheck.py <file.cert> <Q|R> <W> <H>; exits 1 if any position is missing."""
import sys, itertools
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '03-checker'))
import rules
cert, piece, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
entries = set()
for line in open(cert):
    if not line.startswith('#'):
        entries.add(line.split('\t')[0])
def fen(sq):
    rows = []
    for r in range(H - 1, -1, -1):
        row, run = '', 0
        for f in range(W):
            c = sq.get((f, r))
            if c is None: run += 1
            else:
                if run: row += str(run); run = 0
                row += c
        if run: row += str(run)
        rows.append(row)
    return '/'.join(rows) + ' w - -'
cells = [(f, r) for f in range(W) for r in range(H)]
valid = covered = 0; missing = []
for a, b, c in itertools.permutations(cells, 3):
    s = fen({a: 'K', b: piece, c: 'k'})
    try: rules.parse_position(s)
    except ValueError: continue
    valid += 1
    if s in entries: covered += 1
    elif len(missing) < 3: missing.append(s)
print(f"{W}x{H} K{piece}K: valid_wtm={valid} covered={covered} cert_entries={len(entries)} missing={missing}")
sys.exit(0 if covered == valid else 1)
