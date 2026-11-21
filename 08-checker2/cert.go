package main

// Certificate checking, written from SPEC section 4.

import (
	"fmt"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type entry struct {
	pos  Pos
	mv   Move
	rank string // decimal, no leading zeros
	line int
}

type Result struct {
	Valid   bool
	Where   string // entry / line description when invalid
	Reason  string
	Claim   string
	Root    string
	Entries int
	MaxRank string
}

func rankLess(a, b string) bool {
	if len(a) != len(b) {
		return len(a) < len(b)
	}
	return a < b
}

func validRank(s string) bool {
	if s == "" || len(s) > 1000 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return s == "0" || s[0] != '0'
}

func bad(where, reason string) Result {
	return Result{Valid: false, Where: where, Reason: reason}
}

func findMove(ms []Move, s string) (Move, bool) {
	for _, m := range ms {
		if m.String() == s {
			return m, true
		}
	}
	return Move{}, false
}

func parseCanonical(s string) (Pos, error) {
	p, err := ParsePosition(s, false)
	if err != nil {
		return p, err
	}
	if p.String() != s {
		return p, fmt.Errorf("position is not in canonical form (canonical: %s)", p.String())
	}
	return p, nil
}

// proverStalemate: prover to move (caller guarantees), no legal move, not in check.
func proverStalemate(p *Pos) bool {
	var buf [256]Move
	return len(p.legal(buf[:0])) == 0 && !p.inCheck()
}

func CheckFile(path string) Result {
	data, err := os.ReadFile(path)
	if err != nil {
		return bad("file", "cannot read file: "+err.Error())
	}
	return CheckBytes(data)
}

func CheckBytes(data []byte) (res Result) {
	defer func() {
		if r := recover(); r != nil {
			res = bad("internal", fmt.Sprint("internal error: ", r))
		}
	}()
	if len(data) == 0 {
		return bad("file", "file is empty")
	}
	// The line terminator is "\n" only. A final line without terminator is accepted:
	// the spec does not require one. "\r" is not a terminator, so it ends up inside the
	// last field of a line, where it makes a position non-canonical or a rank non-decimal.
	text := string(data)
	if text[len(text)-1] == '\n' {
		text = text[:len(text)-1]
	}
	lines := strings.Split(text, "\n")
	if len(lines) < 3 {
		return bad("header", "fewer than three header lines")
	}
	if lines[0] != "#cert v1" {
		return bad("line 1", "first line must be '#cert v1'")
	}
	var win bool
	var proverWhite bool
	var claimText string
	switch lines[1] {
	case "#claim WIN w":
		win, proverWhite = true, true
	case "#claim WIN b":
		win, proverWhite = true, false
	case "#claim ATLEAST_DRAW w":
		win, proverWhite = false, true
	case "#claim ATLEAST_DRAW b":
		win, proverWhite = false, false
	default:
		return bad("line 2", "bad claim line")
	}
	claimText = strings.TrimPrefix(lines[1], "#claim ")
	if !strings.HasPrefix(lines[2], "#root ") {
		return bad("line 3", "third line must be '#root <position>'")
	}
	rootText := lines[2][len("#root "):]
	root, err := parseCanonical(rootText)
	if err != nil {
		return bad("root", "root: "+err.Error())
	}
	body := lines[3:]
	entries := make([]entry, 0, len(body))
	index := make(map[string]int, len(body))
	maxRank := "0"
	for i, ln := range body {
		lineNo := i + 4
		where := fmt.Sprintf("line %d", lineNo)
		f := strings.Split(ln, "\t")
		if len(f) != 3 {
			return bad(where, "entry must have exactly three tab-separated fields")
		}
		pos, err := parseCanonical(f[0])
		if err != nil {
			return bad(where, "entry position: "+err.Error())
		}
		if pos.w != root.w || pos.h != root.h {
			return bad(where, "entry position has a different board size than the root")
		}
		if !validRank(f[2]) {
			return bad(where, "bad rank '"+f[2]+"'")
		}
		if !win && f[2] != "0" {
			return bad(where, "rank must be 0 in ATLEAST_DRAW entries")
		}
		if _, dup := index[f[0]]; dup {
			return bad(where, "duplicate position")
		}
		if pos.white != proverWhite {
			return bad(where, "prover is not to move in entry position")
		}
		var buf [256]Move
		m, ok := findMove(pos.legal(buf[:0]), f[1])
		if !ok {
			return bad(where, "move '"+f[1]+"' is not legal")
		}
		index[f[0]] = len(entries)
		if rankLess(maxRank, f[2]) {
			maxRank = f[2]
		}
		entries = append(entries, entry{pos: pos, mv: m, rank: f[2], line: lineNo})
	}

	// replies: check that a successor position (prover to move) is acceptable.
	// For WIN it must be an entry with rank < bound (bound == "" means no bound).
	okReply := func(q *Pos, bound string) string {
		key := q.String()
		j, found := index[key]
		if win {
			if !found {
				if proverStalemate(q) {
					return "reply stalemates the prover (no entry allowed in WIN): " + key
				}
				return "reply has no entry: " + key
			}
			if bound != "" && !rankLess(entries[j].rank, bound) {
				return fmt.Sprintf("reply %s has rank %s, not below %s", key, entries[j].rank, bound)
			}
			return ""
		}
		if found || proverStalemate(q) {
			return ""
		}
		return "reply is neither an entry nor a prover stalemate: " + key
	}

	// root
	if root.white == proverWhite {
		if win {
			if _, ok := index[rootText]; !ok {
				return bad("root", "root (prover to move) is not an entry")
			}
		} else if _, ok := index[rootText]; !ok && !proverStalemate(&root) {
			return bad("root", "root (prover to move) is neither an entry nor a prover stalemate")
		}
	} else {
		var buf [256]Move
		replies := root.legal(buf[:0])
		if len(replies) == 0 {
			if win && !root.inCheck() {
				return bad("root", "opponent to move at root is stalemated, not mated")
			}
		}
		for _, r := range replies {
			q := root.makeMove(r)
			if why := okReply(&q, ""); why != "" {
				return bad("root", "after root reply "+r.String()+": "+why)
			}
		}
	}

	// entries, in parallel; report the first failing one in file order
	errs := make([]string, len(entries))
	var next int64
	var wg sync.WaitGroup
	nw := runtime.NumCPU()
	if nw > 4 {
		nw = 4
	}
	const chunk = 64
	for w := 0; w < nw; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				lo := int(atomic.AddInt64(&next, chunk)) - chunk
				if lo >= len(entries) {
					return
				}
				hi := lo + chunk
				if hi > len(entries) {
					hi = len(entries)
				}
				for i := lo; i < hi; i++ {
					errs[i] = checkEntry(&entries[i], win, okReply)
				}
			}
		}()
	}
	wg.Wait()
	for i, e := range errs {
		if e != "" {
			return bad(fmt.Sprintf("line %d (%s)", entries[i].line, entries[i].pos.String()), e)
		}
	}
	return Result{Valid: true, Claim: claimText, Root: rootText, Entries: len(entries), MaxRank: maxRank}
}

func checkEntry(e *entry, win bool, okReply func(*Pos, string) string) string {
	q := e.pos.makeMove(e.mv)
	var buf [256]Move
	replies := q.legal(buf[:0])
	if len(replies) == 0 {
		if win && !q.inCheck() {
			return "move stalemates the opponent"
		}
		return ""
	}
	if win && e.rank == "0" {
		return "rank 0 entry but the opponent has a legal reply"
	}
	for _, r := range replies {
		n := q.makeMove(r)
		if why := okReply(&n, e.rank); why != "" {
			return "after reply " + r.String() + ": " + why
		}
	}
	return ""
}

func runVerify(path string) int {
	t0 := time.Now()
	r := CheckFile(path)
	if !r.Valid {
		fmt.Println("INVALID")
		fmt.Println("entry:", r.Where)
		fmt.Println("reason:", r.Reason)
		return 1
	}
	fmt.Println("VALID")
	fmt.Println("claim:", r.Claim)
	fmt.Println("root:", r.Root)
	fmt.Println("entries:", r.Entries)
	fmt.Println("max_rank:", r.MaxRank)
	fmt.Printf("seconds: %.4f\n", time.Since(t0).Seconds())
	return 0
}
