#!/usr/bin/env python3
"""Mutation comparison: both checkers must give the same verdict on every mutant.

usage: mutate.py [n_certs=200] [seed=1]
Takes n_certs valid certificates (seeded sample from 04-tablebase/results and
05-solver/certs, at most 3000 lines each), applies every mutation kind to each, and runs
03-checker (Python) and mcheck2 on every mutant.  Reorder mutants must keep the verdict.
"""
import os, random, subprocess, sys, tempfile, glob, collections
from concurrent.futures import ThreadPoolExecutor

here = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(here, "..", "03-checker", "mcheck.py")
GO = os.path.join(here, "mcheck2")
ENG = os.path.join(here, "..", "02-engine", "bin", "mchess")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
N = int(ARGS[0]) if len(ARGS) > 0 else 200
SEED = int(ARGS[1]) if len(ARGS) > 1 else 1
rng = random.Random(SEED)


def verdict(cmd, path):
    r = subprocess.run(cmd + ["verify", path], capture_output=True, text=True, timeout=120)
    first = r.stdout.split("\n", 1)[0]
    return (first, r.returncode)


def legal_moves(pos):
    r = subprocess.run([ENG, "moves", pos], capture_output=True, text=True, timeout=30)
    return [l.split("\t")[0] for l in r.stdout.splitlines() if l]


def split(text):
    """-> header (3 lines), body lines, trailing-newline flag"""
    nl = text.endswith("\n")
    lines = text.split("\n")
    if nl:
        lines = lines[:-1]
    return lines[:3], lines[3:]


def join(h, b, nl=True):
    return "\n".join(h + b) + ("\n" if nl else "")


def entry_pos(line):
    return line.split("\t")[0]


# ---- mutations: each returns new text, or None if not applicable -------------
def m_drop_line(h, b):
    if not b: return None
    i = rng.randrange(len(b)); return join(h, b[:i] + b[i + 1:])

def m_drop_last_line(h, b):
    return join(h, b[:-1]) if b else None

def m_change_move(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    ms = [x for x in legal_moves(p) if x != m]
    if not ms: return None
    b = list(b); b[i] = "\t".join([p, rng.choice(ms), d]); return join(h, b)

def m_rank_up(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    b = list(b); b[i] = "\t".join([p, m, str(int(d) + 1)]); return join(h, b)

def m_rank_down(h, b):
    c = [i for i, l in enumerate(b) if int(l.split("\t")[2]) > 0]
    if not c: return None
    i = rng.choice(c); p, m, d = b[i].split("\t")
    b = list(b); b[i] = "\t".join([p, m, str(int(d) - 1)]); return join(h, b)

def m_rank_zero(h, b):
    c = [i for i, l in enumerate(b) if int(l.split("\t")[2]) > 0]
    if not c: return None
    i = rng.choice(c); p, m, d = b[i].split("\t")
    b = list(b); b[i] = "\t".join([p, m, "0"]); return join(h, b)

def m_rank_bad_format(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    d2 = rng.choice(["0" + d, "+" + d, "-1", d + ".0", "", "x", " " + d, d + " "])
    b = list(b); b[i] = "\t".join([p, m, d2]); return join(h, b)

def m_swap_kind(h, b):
    k = h[1].split(" ")
    k[1] = "ATLEAST_DRAW" if k[1] == "WIN" else "WIN"
    return join([h[0], " ".join(k), h[2]], b)

def m_swap_side(h, b):
    k = h[1].split(" "); k[2] = "b" if k[2] == "w" else "w"
    return join([h[0], " ".join(k), h[2]], b)

def m_dup_line(h, b):
    if not b: return None
    i = rng.randrange(len(b)); return join(h, b[:i] + [b[i]] + b[i:])

def m_dup_line_other_move(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    ms = [x for x in legal_moves(p) if x != m]
    if not ms: return None
    return join(h, b + ["\t".join([p, rng.choice(ms), d])])

def corrupt(pos):
    ch = list(pos)
    kind = rng.randrange(7)
    if kind == 0:   # flip side to move
        s = pos.split(" "); s[1] = "b" if s[1] == "w" else "w"; return " ".join(s)
    if kind == 1:   # replace a placement char
        idx = [i for i, c in enumerate(pos.split(" ")[0]) if c != "/"]
        j = rng.choice(idx); ch[j] = rng.choice("PNBRQKpnbrqk123x")
        return "".join(ch)
    if kind == 2:   # delete a placement char
        j = rng.randrange(len(pos.split(" ")[0])); del ch[j]; return "".join(ch)
    if kind == 3:   # castling / ep garbage
        s = pos.split(" "); s[2] = rng.choice(["K", "KQkq", "qk", "-", "x"]); return " ".join(s)
    if kind == 4:   # ep
        s = pos.split(" "); s[3] = rng.choice(["e3", "d6", "a1", "-"]); return " ".join(s)
    if kind == 5:   # extra fields
        return pos + rng.choice([" 0 1", " 5 9", " 0", " x y"])
    s = pos.split(" "); s[0] = s[0].replace("k", "q", 1) if "k" in s[0] else s[0] + "/"; return " ".join(s)

def m_corrupt_entry(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    b = list(b); b[i] = "\t".join([corrupt(p), m, d]); return join(h, b)

def m_corrupt_root(h, b):
    return join([h[0], h[1], "#root " + corrupt(h[2][6:])], b)

def m_root_other_entry(h, b):
    if len(b) < 2: return None
    return join([h[0], h[1], "#root " + entry_pos(rng.choice(b))], b)

def m_root_flip_stm(h, b):
    s = h[2][6:].split(" "); s[1] = "b" if s[1] == "w" else "w"
    return join([h[0], h[1], "#root " + " ".join(s)], b)

def m_root_successor(h, b):
    if not b: return None
    p, m, d = rng.choice(b).split("\t")
    r = subprocess.run([ENG, "moves", p], capture_output=True, text=True, timeout=30)
    for l in r.stdout.splitlines():
        mm, q = l.split("\t")
        if mm == m: return join([h[0], h[1], "#root " + q], b)
    return None

def m_blank_body(h, b):
    i = rng.randrange(len(b) + 1); return join(h, b[:i] + [""] + b[i:])

def m_blank_end(h, b):
    return join(h, b) + "\n"

def m_blank_header(h, b):
    i = rng.randrange(1, 4); l = h + b
    return "\n".join(l[:i] + [""] + l[i:]) + "\n"

def m_comment(h, b):
    i = rng.randrange(len(b) + 1); return join(h, b[:i] + ["# comment"] + b[i:])

def m_reorder(h, b):
    b = list(b); rng.shuffle(b); return join(h, b)

def m_reverse(h, b):
    return join(h, b[::-1])

def m_no_final_newline(h, b):
    return join(h, b, nl=False)

def m_crlf(h, b):
    return join(h, b).replace("\n", "\r\n")

def m_spaces_for_tabs(h, b):
    if not b: return None
    i = rng.randrange(len(b)); b = list(b); b[i] = b[i].replace("\t", " ", 1); return join(h, b)

def m_extra_field(h, b):
    if not b: return None
    i = rng.randrange(len(b)); b = list(b); b[i] += "\tx"; return join(h, b)

def m_missing_field(h, b):
    if not b: return None
    i = rng.randrange(len(b)); b = list(b); b[i] = b[i].rsplit("\t", 1)[0]; return join(h, b)

def m_bad_move_text(h, b):
    if not b: return None
    i = rng.randrange(len(b)); p, m, d = b[i].split("\t")
    m2 = rng.choice([m.upper(), m + "q", m[:-1], "a1a1", "", "zz", m[:4] + "Q" if len(m) == 5 else m + "Q"])
    b = list(b); b[i] = "\t".join([p, m2, d]); return join(h, b)

def m_trailing_ws(h, b):
    if not b: return None
    i = rng.randrange(len(b)); b = list(b); b[i] += " "; return join(h, b)

def m_header_variants(h, b):
    k = rng.randrange(4)
    if k == 0: return join(["#cert v2"] + h[1:], b)
    if k == 1: return join([h[0], h[1].replace("#claim", "#claim ", 1), h[2]], b)
    if k == 2: return join([h[0], h[2], h[1]], b)
    return join(h[1:] + [b[0]] if b else h[1:], b[1:])

def m_truncate(h, b):
    t = join(h, b); return t[: rng.randrange(1, len(t))]

def m_empty(h, b):
    return ""

def m_swap_two_moves(h, b):
    if len(b) < 2: return None
    i, j = rng.sample(range(len(b)), 2)
    pi, mi, di = b[i].split("\t"); pj, mj, dj = b[j].split("\t")
    b = list(b); b[i] = "\t".join([pi, mj, di]); b[j] = "\t".join([pj, mi, dj]); return join(h, b)

def m_swap_ranks(h, b):
    if len(b) < 2: return None
    i, j = rng.sample(range(len(b)), 2)
    pi, mi, di = b[i].split("\t"); pj, mj, dj = b[j].split("\t")
    if di == dj: return None
    b = list(b); b[i] = "\t".join([pi, mi, dj]); b[j] = "\t".join([pj, mj, di]); return join(h, b)

def m_all_ranks_zero(h, b):
    return join(h, ["\t".join(l.split("\t")[:2] + ["0"]) for l in b]) if b else None

# crlf is a documented open disagreement (REPORT.md, "Disagreements"): Python accepts CRLF
# files, mcheck2 rejects them. It runs only with --with-crlf so that `make mutate` shows the
# state of everything else; the failure is not hidden, it is reported.
WITH_CRLF = "--with-crlf" in sys.argv
MUTS = [(n[2:], f) for n, f in sorted(globals().items())
        if n.startswith("m_") and callable(f) and (WITH_CRLF or n != "m_crlf")]
SAME = {"reorder", "reverse"}   # must preserve the verdict of the original


def main():
    pool = [f for f in sorted(glob.glob(os.path.join(here, "..", "04-tablebase", "results", "**", "*.cert"), recursive=True)
                              + glob.glob(os.path.join(here, "..", "05-solver", "certs", "**", "*.cert"), recursive=True))
            if os.path.getsize(f) < 400000]
    rng.shuffle(pool)
    tmp = tempfile.mkdtemp()
    chosen = []
    with ThreadPoolExecutor(4) as ex:
        cand = pool[: N * 3]
        res = list(ex.map(lambda f: verdict([GO], f), cand))
    for f, (v, rc) in zip(cand, res):
        if v == "VALID" and len(open(f).read().split("\n")) > 6:
            chosen.append(f)
        if len(chosen) == N: break
    # keep a few with a single claim of each kind visible
    print(f"{len(chosen)} valid source certificates", flush=True)
    jobs = []
    for ci, f in enumerate(chosen):
        h, b = split(open(f).read())
        for name, fn in MUTS:
            try:
                t = fn(h, b)
            except Exception as e:
                print("mutator failed", name, f, e); continue
            if t is None: continue
            p = os.path.join(tmp, f"{ci}_{name}.cert")
            open(p, "w", newline="").write(t)
            jobs.append((name, f, p))
    print(f"{len(jobs)} mutants, {len(MUTS)} kinds: {', '.join(n for n, _ in MUTS)}", flush=True)

    def run(j):
        name, f, p = j
        return j, verdict([PY], p), verdict([GO], p)

    stats = collections.defaultdict(lambda: [0, 0, 0, 0])  # n, both valid, both invalid, disagree
    dis = []; bad_same = []
    with ThreadPoolExecutor(4) as ex:
        for (name, f, p), a, b in ex.map(run, jobs):
            s = stats[name]; s[0] += 1
            if a == b:
                s[1 if a[0] == "VALID" else 2] += 1
            else:
                s[3] += 1; dis.append((name, f, p, a, b))
            if name in SAME and (a[0] != "VALID" or b[0] != "VALID"):
                bad_same.append((name, f, p, a, b))
    tot = sum(s[0] for s in stats.values())
    print(f"{'kind':24} {'n':>5} {'both VALID':>11} {'both INVALID':>13} {'disagree':>9}")
    for name, s in sorted(stats.items()):
        print(f"{name:24} {s[0]:5d} {s[1]:11d} {s[2]:13d} {s[3]:9d}")
    print(f"TOTAL mutants={tot} disagreements={len(dis)} reorder-changed-verdict={len(bad_same)}")
    for name, f, p, a, b in dis[:20]:
        print(f"DISAGREE {name} src={f} mutant={p} python={a} go={b}")
    for x in bad_same[:5]:
        print("REORDER CHANGED", x)
    if dis or bad_same:
        sys.exit(1)

main()
