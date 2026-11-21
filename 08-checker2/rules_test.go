package main

import "testing"

func perftOf(t *testing.T, pos string, depth int) uint64 {
	p, err := ParsePosition(pos, true)
	if err != nil {
		t.Fatalf("%s: %v", pos, err)
	}
	bufs := make([][]Move, depth+1)
	for i := range bufs {
		bufs[i] = make([]Move, 0, 256)
	}
	return perft(&p, depth, bufs)
}

func TestPerft8x8(t *testing.T) {
	cases := []struct {
		pos  string
		want []uint64
	}{
		{"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", []uint64{20, 400, 8902, 197281, 4865609}},
		{"r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -", []uint64{48, 2039, 97862, 4085603}},
		{"8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - -", []uint64{14, 191, 2812, 43238, 674624}},
		{"r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq -", []uint64{6, 264, 9467, 422333}},
		{"rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ -", []uint64{44, 1486, 62379, 2103487}},
		{"r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - -", []uint64{46, 2079, 89890, 3894594}},
	}
	for _, c := range cases {
		for i, want := range c.want {
			if got := perftOf(t, c.pos, i+1); got != want {
				t.Errorf("perft(%s, %d) = %d, want %d", c.pos, i+1, got, want)
			}
		}
	}
}

func TestValidity(t *testing.T) {
	const start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
	good := []string{
		start,
		start + " 0 1",
		"rqkr/pppp/PPPP/RQKR w - -",
		"3/3/k1K w - -",
		"4k3/8/8/3pP3/8/8/8/4K3 w - d6",
	}
	for _, s := range good {
		if _, err := ParsePosition(s, true); err != nil {
			t.Errorf("should be valid: %q: %v", s, err)
		}
	}
	bads := map[string]string{
		"no white king":                 "3/3/k2 w - -",
		"two white kings":               "3/1K1/k1K w - -",
		"two black kings":               "k1k/3/K2 w - -",
		"no black king":                 "3/3/K2 w - -",
		"pawn on rank 1":                "3/3/k1P w - -",
		"pawn on rank 1 black":          "3/3/p1K w - -",
		"white pawn on last rank":       "P2/3/k1K w - -",
		"black pawn on last rank":       "p2/3/k1K w - -",
		"opponent in check (w to move)": "k2/3/R1K w - -",
		"opponent in check (b to move)": "k2/2r/2K b - -",
		"castle off 8x8":                "r3k/5/5/5/R3K w K -",
		"castle without rook":           "r3k3/8/8/8/8/8/8/4K3 w k -",
		"castle without king":           "r3k2r/8/8/8/8/8/8/R2K3R w Q -",
		"castle wrong order":            "r3k2r/8/8/8/8/8/8/R3K2R w qK -",
		"castle duplicate":              "r3k2r/8/8/8/8/8/8/R3K2R w KK -",
		"castle empty":                  "r3k2r/8/8/8/8/8/8/R3K2R w  -",
		"castle rook wrong colour":      "r3k2r/8/8/8/8/8/8/r3K2R w Q -",
		"ep off 8x8":                    "k3/4/pP2/K3 w - a3",
		"ep without capture":            "4k3/8/8/3p4/8/8/8/4K3 w - d6",
		"ep wrong rank":                 "4k3/8/8/3pP3/8/8/8/4K3 w - d3",
		"ep pawn pinned":                "8/8/8/K2pP2r/8/8/8/4k3 w - d6",
		"ep square malformed":           "4k3/8/8/3pP3/8/8/8/4K3 w - d",
		"bad stm":                       "3/3/k1K x - -",
		"three fields":                  "3/3/k1K w -",
		"non-maximal empty run":         "3/3/k1K w - - x",
		"non-maximal digits":            "8/8/8/8/8/8/8/1111K1k1 w - -",
		"ragged ranks":                  "3/4/k1K w - -",
		"rank too long":                 "3/3/k1K1 w - -",
		"too few ranks":                 "3/k1K w - -",
		"too narrow":                    "2/2/kK w - -",
		"nine ranks":                    "8/8/8/8/8/8/8/8/k1K w - -",
		"bad piece":                     "3/3/k1X w - -",
		"zero digit":                    "3/3/k0K w - -",
		"double space":                  "3/3/k1K  w - -",
		"trailing nonnumeric":           "3/3/k1K w - - a b",
		"only one trailing":             "3/3/k1K w - - 0",
	}
	for name, s := range bads {
		if _, err := ParsePosition(s, true); err == nil {
			t.Errorf("%s: should be rejected: %q", name, s)
		}
	}
}

func TestEPAndCastlingSuccessors(t *testing.T) {
	// double step sets ep only if a legal capture exists
	p, _ := ParsePosition("4k3/8/8/3p4/4P3/8/8/4K3 b - -", false)
	_ = p
	q, err := ParsePosition("4k3/3p4/8/4P3/8/8/8/4K3 b - -", false)
	if err != nil {
		t.Fatal(err)
	}
	var buf [64]Move
	for _, m := range q.legal(buf[:0]) {
		if m.String() == "d7d5" {
			n := q.makeMove(m)
			if n.String() != "4k3/8/8/3pP3/8/8/8/4K3 w - d6" {
				t.Errorf("got %s", n.String())
			}
		}
	}
	r, _ := ParsePosition("4k3/3p4/8/8/8/8/8/4K3 b - -", false)
	for _, m := range r.legal(buf[:0]) {
		if m.String() == "d7d5" {
			if n := r.makeMove(m); n.String() != "4k3/8/8/3p4/8/8/8/4K3 w - -" {
				t.Errorf("got %s", n.String())
			}
		}
	}
	// castling rights lost by capturing the rook
	c, _ := ParsePosition("r3k2r/8/8/8/8/8/6b1/R3K2R b KQkq -", false)
	for _, m := range c.legal(buf[:0]) {
		if m.String() == "g2h1" {
			if n := c.makeMove(m); n.String() != "r3k2r/8/8/8/8/8/8/R3K2b w Qkq -" {
				t.Errorf("got %s", n.String())
			}
		}
	}
}
