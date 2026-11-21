package main

// Chess rules written from design/SPEC.md (v1.1) only.
// Board: up to 8x8, squares indexed rank*8+file regardless of W (a1 = 0).
// Pieces: white positive, black negative; 1=P 2=N 3=B 4=R 5=Q 6=K.

import (
	"errors"
	"strings"
)

const (
	Pawn   = 1
	Knight = 2
	Bishop = 3
	Rook   = 4
	Queen  = 5
	King   = 6
)

const (
	castK = 1 // white king side
	castQ = 2 // white queen side
	castk = 4 // black king side
	castq = 8 // black queen side
)

type Pos struct {
	b     [64]int8
	w, h  int8
	white bool // side to move is White
	cas   uint8
	ep    int8 // en-passant target square or -1
	king  [2]int8
}

type Move struct {
	from, to int8
	promo    int8 // 0 or piece type
	ep       bool
	castle   bool
}

func (p *Pos) full8() bool { return p.w == 8 && p.h == 8 }

func abs8(x int8) int8 {
	if x < 0 {
		return -x
	}
	return x
}

var pieceLetters = "PNBRQK"

func pieceFromLetter(c byte) int8 {
	i := strings.IndexByte(pieceLetters, c)
	if i >= 0 {
		return int8(i + 1)
	}
	i = strings.IndexByte("pnbrqk", c)
	if i >= 0 {
		return -int8(i + 1)
	}
	return 0
}

func letterOf(pc int8) byte {
	if pc > 0 {
		return pieceLetters[pc-1]
	}
	return "pnbrqk"[-pc-1]
}

func sqName(sq int8) string {
	return string([]byte{byte('a' + sq&7), byte('1' + sq>>3)})
}

func (m Move) String() string {
	s := sqName(m.from) + sqName(m.to)
	if m.promo != 0 {
		s += string(letterOf(-m.promo)) // lower case
	}
	return s
}

// String writes the canonical position string.
func (p *Pos) String() string {
	var sb strings.Builder
	for r := int(p.h) - 1; r >= 0; r-- {
		run := 0
		for f := 0; f < int(p.w); f++ {
			pc := p.b[r*8+f]
			if pc == 0 {
				run++
				continue
			}
			if run > 0 {
				sb.WriteByte(byte('0' + run))
				run = 0
			}
			sb.WriteByte(letterOf(pc))
		}
		if run > 0 {
			sb.WriteByte(byte('0' + run))
		}
		if r > 0 {
			sb.WriteByte('/')
		}
	}
	if p.white {
		sb.WriteString(" w ")
	} else {
		sb.WriteString(" b ")
	}
	if p.cas == 0 {
		sb.WriteByte('-')
	} else {
		if p.cas&castK != 0 {
			sb.WriteByte('K')
		}
		if p.cas&castQ != 0 {
			sb.WriteByte('Q')
		}
		if p.cas&castk != 0 {
			sb.WriteByte('k')
		}
		if p.cas&castq != 0 {
			sb.WriteByte('q')
		}
	}
	sb.WriteByte(' ')
	if p.ep < 0 {
		sb.WriteByte('-')
	} else {
		sb.WriteString(sqName(p.ep))
	}
	return sb.String()
}

var knightD = [8][2]int{{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}}
var kingD = [8][2]int{{1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, -1}}
var rookD = [4][2]int{{1, 0}, {0, 1}, {-1, 0}, {0, -1}}
var bishD = [4][2]int{{1, 1}, {-1, 1}, {-1, -1}, {1, -1}}

// attacked reports whether square sq is attacked by the given colour.
func (p *Pos) attacked(sq int, byWhite bool) bool {
	f, r := sq&7, sq>>3
	w, h := int(p.w), int(p.h)
	var sign int8 = 1
	if !byWhite {
		sign = -1
	}
	pr := r - 1
	if !byWhite {
		pr = r + 1
	}
	if pr >= 0 && pr < h {
		if f > 0 && p.b[pr*8+f-1] == sign*Pawn {
			return true
		}
		if f+1 < w && p.b[pr*8+f+1] == sign*Pawn {
			return true
		}
	}
	for _, d := range knightD {
		nf, nr := f+d[0], r+d[1]
		if nf >= 0 && nf < w && nr >= 0 && nr < h && p.b[nr*8+nf] == sign*Knight {
			return true
		}
	}
	for _, d := range kingD {
		nf, nr := f+d[0], r+d[1]
		if nf >= 0 && nf < w && nr >= 0 && nr < h && p.b[nr*8+nf] == sign*King {
			return true
		}
	}
	for _, d := range rookD {
		nf, nr := f+d[0], r+d[1]
		for nf >= 0 && nf < w && nr >= 0 && nr < h {
			pc := p.b[nr*8+nf]
			if pc != 0 {
				if pc == sign*Rook || pc == sign*Queen {
					return true
				}
				break
			}
			nf += d[0]
			nr += d[1]
		}
	}
	for _, d := range bishD {
		nf, nr := f+d[0], r+d[1]
		for nf >= 0 && nf < w && nr >= 0 && nr < h {
			pc := p.b[nr*8+nf]
			if pc != 0 {
				if pc == sign*Bishop || pc == sign*Queen {
					return true
				}
				break
			}
			nf += d[0]
			nr += d[1]
		}
	}
	return false
}

func (p *Pos) kingSq(white bool) int {
	if white {
		return int(p.king[0])
	}
	return int(p.king[1])
}

// inCheck: is the side to move in check?
func (p *Pos) inCheck() bool {
	return p.attacked(p.kingSq(p.white), !p.white)
}

// genPseudo appends all moves ignoring whether the mover's king ends up attacked
// (castling already checks its own attack conditions).
func (p *Pos) genPseudo(out []Move) []Move {
	w, h := int(p.w), int(p.h)
	var sign int8 = 1
	if !p.white {
		sign = -1
	}
	for r := 0; r < h; r++ {
		for f := 0; f < w; f++ {
			sq := r*8 + f
			pc := p.b[sq]
			if pc == 0 || (pc > 0) != p.white {
				continue
			}
			t := pc * sign
			from := int8(sq)
			switch t {
			case Pawn:
				dir := 1
				last := h - 1
				start := 1
				if !p.white {
					dir = -1
					last = 0
					start = h - 2
					if p.full8() {
						start = 6
					}
				}
				nr := r + dir
				if nr < 0 || nr >= h {
					break
				}
				addPawn := func(to int, capture bool) {
					if nr == last {
						for _, pr := range [4]int8{Knight, Bishop, Rook, Queen} {
							out = append(out, Move{from: from, to: int8(to), promo: pr})
						}
					} else {
						out = append(out, Move{from: from, to: int8(to)})
					}
				}
				if p.b[nr*8+f] == 0 {
					addPawn(nr*8+f, false)
					if p.full8() && r == start && p.b[(nr+dir)*8+f] == 0 {
						out = append(out, Move{from: from, to: int8((nr+dir)*8 + f)})
					}
				}
				for _, df := range [2]int{-1, 1} {
					nf := f + df
					if nf < 0 || nf >= w {
						continue
					}
					to := nr*8 + nf
					tp := p.b[to]
					if tp != 0 && (tp > 0) != p.white {
						addPawn(to, true)
					} else if tp == 0 && int8(to) == p.ep && p.full8() {
						// en passant: the enemy pawn stands beside us
						if p.b[r*8+nf] == -sign*Pawn {
							out = append(out, Move{from: from, to: int8(to), ep: true})
						}
					}
				}
			case Knight:
				for _, d := range knightD {
					nf, nr := f+d[0], r+d[1]
					if nf >= 0 && nf < w && nr >= 0 && nr < h {
						tp := p.b[nr*8+nf]
						if tp == 0 || (tp > 0) != p.white {
							out = append(out, Move{from: from, to: int8(nr*8 + nf)})
						}
					}
				}
			case King:
				for _, d := range kingD {
					nf, nr := f+d[0], r+d[1]
					if nf >= 0 && nf < w && nr >= 0 && nr < h {
						tp := p.b[nr*8+nf]
						if tp == 0 || (tp > 0) != p.white {
							out = append(out, Move{from: from, to: int8(nr*8 + nf)})
						}
					}
				}
				if p.full8() {
					out = p.genCastle(out, from)
				}
			case Bishop, Rook, Queen:
				if t != Bishop {
					out = p.slide(out, from, f, r, rookD[:])
				}
				if t != Rook {
					out = p.slide(out, from, f, r, bishD[:])
				}
			}
		}
	}
	return out
}

func (p *Pos) slide(out []Move, from int8, f, r int, dirs [][2]int) []Move {
	w, h := int(p.w), int(p.h)
	for _, d := range dirs {
		nf, nr := f+d[0], r+d[1]
		for nf >= 0 && nf < w && nr >= 0 && nr < h {
			tp := p.b[nr*8+nf]
			if tp == 0 {
				out = append(out, Move{from: from, to: int8(nr*8 + nf)})
			} else {
				if (tp > 0) != p.white {
					out = append(out, Move{from: from, to: int8(nr*8 + nf)})
				}
				break
			}
			nf += d[0]
			nr += d[1]
		}
	}
	return out
}

func (p *Pos) genCastle(out []Move, from int8) []Move {
	base := 0
	var ks, qs uint8 = castK, castQ
	if !p.white {
		base = 56
		ks, qs = castk, castq
	}
	if int(from) != base+4 {
		return out
	}
	opp := !p.white
	if p.cas&(ks|qs) == 0 || p.attacked(base+4, opp) {
		return out
	}
	if p.cas&ks != 0 && p.b[base+5] == 0 && p.b[base+6] == 0 &&
		!p.attacked(base+5, opp) && !p.attacked(base+6, opp) {
		out = append(out, Move{from: from, to: int8(base + 6), castle: true})
	}
	if p.cas&qs != 0 && p.b[base+1] == 0 && p.b[base+2] == 0 && p.b[base+3] == 0 &&
		!p.attacked(base+2, opp) && !p.attacked(base+3, opp) {
		out = append(out, Move{from: from, to: int8(base + 2), castle: true})
	}
	return out
}

// apply performs a move without computing the en-passant field (ep is cleared).
func (p *Pos) apply(m Move) Pos {
	n := *p
	pc := n.b[m.from]
	n.b[m.from] = 0
	if m.ep {
		n.b[int(m.from>>3)*8+int(m.to&7)] = 0
	}
	if m.promo != 0 {
		if pc > 0 {
			n.b[m.to] = m.promo
		} else {
			n.b[m.to] = -m.promo
		}
	} else {
		n.b[m.to] = pc
	}
	if m.castle {
		r8 := int(m.from>>3) * 8
		if m.to&7 == 6 {
			n.b[r8+5] = n.b[r8+7]
			n.b[r8+7] = 0
		} else {
			n.b[r8+3] = n.b[r8+0]
			n.b[r8+0] = 0
		}
	}
	if abs8(pc) == King {
		if pc > 0 {
			n.king[0] = m.to
		} else {
			n.king[1] = m.to
		}
	}
	if p.full8() {
		for _, s := range [2]int8{m.from, m.to} {
			switch s {
			case 0:
				n.cas &^= castQ
			case 7:
				n.cas &^= castK
			case 4:
				n.cas &^= castK | castQ
			case 56:
				n.cas &^= castq
			case 63:
				n.cas &^= castk
			case 60:
				n.cas &^= castk | castq
			}
		}
	}
	n.white = !p.white
	n.ep = -1
	return n
}

// epCaptureExists: does the side to move have a legal en-passant capture to p.ep?
func (p *Pos) epCaptureExists() bool {
	if p.ep < 0 || !p.full8() {
		return false
	}
	ef, er := int(p.ep&7), int(p.ep>>3)
	dir := 1
	var sign int8 = 1
	if !p.white {
		dir = -1
		sign = -1
	}
	// the enemy pawn that just moved stands on the square behind the target
	pr := er - dir
	if pr < 0 || pr > 7 || p.b[pr*8+ef] != -sign*Pawn || p.b[er*8+ef] != 0 {
		return false
	}
	for _, df := range [2]int{-1, 1} {
		nf := ef + df
		if nf < 0 || nf > 7 {
			continue
		}
		fs := pr*8 + nf
		if p.b[fs] != sign*Pawn {
			continue
		}
		q := p.apply(Move{from: int8(fs), to: p.ep, ep: true})
		if !q.attacked(q.kingSq(p.white), !p.white) {
			return true
		}
	}
	return false
}

// makeMove returns the canonical successor position.
func (p *Pos) makeMove(m Move) Pos {
	pc := p.b[m.from]
	n := p.apply(m)
	if abs8(pc) == Pawn && (m.to-m.from == 16 || m.from-m.to == 16) {
		n.ep = (m.from + m.to) / 2
		if !n.epCaptureExists() {
			n.ep = -1
		}
	}
	return n
}

// legal appends the legal moves.
func (p *Pos) legal(buf []Move) []Move {
	var tmp [256]Move
	ps := p.genPseudo(tmp[:0])
	buf = buf[:0]
	mover := p.white
	for _, m := range ps {
		n := p.apply(m)
		if !n.attacked(n.kingSq(mover), !mover) {
			buf = append(buf, m)
		}
	}
	return buf
}

func perft(p *Pos, depth int, bufs [][]Move) uint64 {
	if depth == 0 {
		return 1
	}
	ms := p.legal(bufs[depth])
	bufs[depth] = ms
	if depth == 1 {
		return uint64(len(ms))
	}
	var total uint64
	for _, m := range ms {
		n := p.makeMove(m)
		total += perft(&n, depth-1, bufs)
	}
	return total
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// ParsePosition parses and validates a position string (SPEC section 3).
// If lenient, two trailing numeric halfmove/fullmove fields are accepted and ignored.
// Returned position is always valid; the caller compares String() with the input
// when canonical form is demanded.
func ParsePosition(s string, lenient bool) (Pos, error) {
	var p Pos
	fields := strings.Split(s, " ")
	if len(fields) != 4 {
		if !(lenient && len(fields) == 6 && isDigits(fields[4]) && isDigits(fields[5])) {
			return p, errors.New("position must have exactly four space-separated fields")
		}
	}
	rows := strings.Split(fields[0], "/")
	if len(rows) < 3 || len(rows) > 8 {
		return p, errors.New("number of ranks must be 3..8")
	}
	p.h = int8(len(rows))
	W := -1
	var kings [2]int
	for i, row := range rows {
		r := len(rows) - 1 - i
		f := 0
		prevDigit := false
		for j := 0; j < len(row); j++ {
			c := row[j]
			if c >= '1' && c <= '8' {
				if prevDigit {
					return p, errors.New("non-maximal run of empty squares")
				}
				prevDigit = true
				f += int(c - '0')
				continue
			}
			prevDigit = false
			pc := pieceFromLetter(c)
			if pc == 0 {
				return p, errors.New("bad character in placement")
			}
			if f >= 8 {
				return p, errors.New("rank too long")
			}
			p.b[r*8+f] = pc
			if pc == King {
				p.king[0] = int8(r*8 + f)
				kings[0]++
			} else if pc == -King {
				p.king[1] = int8(r*8 + f)
				kings[1]++
			}
			f++
		}
		if i == 0 {
			W = f
		}
		if f != W {
			return p, errors.New("ranks have different lengths")
		}
		if W < 3 || W > 8 {
			return p, errors.New("board width must be 3..8")
		}
	}
	p.w = int8(W)
	// a long rank may have written past W in an earlier row; re-check emptiness beyond W
	for r := 0; r < int(p.h); r++ {
		for f := W; f < 8; f++ {
			if p.b[r*8+f] != 0 {
				return p, errors.New("rank too long")
			}
		}
	}
	if kings[0] != 1 || kings[1] != 1 {
		return p, errors.New("need exactly one king per side")
	}
	for f := 0; f < W; f++ {
		if p.b[f] == Pawn || p.b[f] == -Pawn || p.b[(int(p.h)-1)*8+f] == Pawn || p.b[(int(p.h)-1)*8+f] == -Pawn {
			return p, errors.New("pawn on first or last rank")
		}
	}
	switch fields[1] {
	case "w":
		p.white = true
	case "b":
		p.white = false
	default:
		return p, errors.New("bad side to move")
	}
	// the side not to move must not be in check
	if p.attacked(p.kingSq(!p.white), p.white) {
		return p, errors.New("side not to move is in check")
	}
	// castling
	p.cas = 0
	cs := fields[2]
	if cs == "" {
		return p, errors.New("empty castling field")
	}
	if cs != "-" {
		if !p.full8() {
			return p, errors.New("castling rights off 8x8")
		}
		last := -1
		for i := 0; i < len(cs); i++ {
			k := strings.IndexByte("KQkq", cs[i])
			if k < 0 || k <= last {
				return p, errors.New("bad castling field")
			}
			last = k
			p.cas |= 1 << uint(k)
		}
		if p.cas&castK != 0 && !(p.b[4] == King && p.b[7] == Rook) ||
			p.cas&castQ != 0 && !(p.b[4] == King && p.b[0] == Rook) ||
			p.cas&castk != 0 && !(p.b[60] == -King && p.b[63] == -Rook) ||
			p.cas&castq != 0 && !(p.b[60] == -King && p.b[56] == -Rook) {
			return p, errors.New("castling right without king and rook on original squares")
		}
	}
	// en passant
	p.ep = -1
	es := fields[3]
	if es != "-" {
		if !p.full8() {
			return p, errors.New("en passant square off 8x8")
		}
		if len(es) != 2 || es[0] < 'a' || es[0] > 'h' {
			return p, errors.New("bad en passant square")
		}
		wantRank := byte('6')
		if !p.white {
			wantRank = '3'
		}
		if es[1] != wantRank {
			return p, errors.New("en passant square on wrong rank")
		}
		p.ep = int8(int(es[1]-'1')*8 + int(es[0]-'a'))
		if !p.epCaptureExists() {
			return p, errors.New("en passant square without a legal en passant capture")
		}
		// the pawn must have come from the square it jumped over
		ef := int(p.ep & 7)
		origin := 6
		if !p.white {
			origin = 1
		}
		if p.b[origin*8+ef] != 0 {
			return p, errors.New("en passant: origin square of the double step is occupied")
		}
	}
	return p, nil
}
