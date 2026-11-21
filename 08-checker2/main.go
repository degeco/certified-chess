package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

func usage() int {
	fmt.Fprintln(os.Stderr, "usage: mcheck2 verify <file.cert> | moves \"<pos>\" | batch | perft \"<pos>\" <depth>")
	return 2
}

type mv struct{ s, pos string }

func successors(p *Pos) []mv {
	var buf [256]Move
	ms := p.legal(buf[:0])
	out := make([]mv, 0, len(ms))
	for _, m := range ms {
		n := p.makeMove(m)
		out = append(out, mv{m.String(), n.String()})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].s < out[j].s })
	return out
}

func main() { os.Exit(run()) }

func run() int {
	args := os.Args[1:]
	if len(args) == 0 {
		return usage()
	}
	switch args[0] {
	case "verify":
		if len(args) != 2 {
			return usage()
		}
		return runVerify(args[1])
	case "moves":
		if len(args) != 2 {
			return usage()
		}
		p, err := ParsePosition(args[1], true)
		if err != nil {
			fmt.Fprintln(os.Stderr, "error:", err)
			return 1
		}
		for _, m := range successors(&p) {
			fmt.Printf("%s\t%s\n", m.s, m.pos)
		}
		return 0
	case "batch":
		sc := bufio.NewScanner(os.Stdin)
		sc.Buffer(make([]byte, 1<<20), 1<<26)
		out := bufio.NewWriterSize(os.Stdout, 1<<20)
		defer out.Flush()
		for sc.Scan() {
			line := sc.Text()
			p, err := ParsePosition(line, true)
			if err != nil {
				fmt.Fprintf(out, "%s\tERROR\n", line)
				continue
			}
			parts := make([]string, 0, 40)
			for _, m := range successors(&p) {
				parts = append(parts, m.s+":"+m.pos)
			}
			fmt.Fprintf(out, "%s\t%s\n", p.String(), strings.Join(parts, "|"))
		}
		return 0
	case "perft":
		if len(args) != 3 {
			return usage()
		}
		d, err := strconv.Atoi(args[2])
		if err != nil || d < 0 {
			return usage()
		}
		p, perr := ParsePosition(args[1], true)
		if perr != nil {
			fmt.Fprintln(os.Stderr, "error:", perr)
			return 1
		}
		bufs := make([][]Move, d+1)
		for i := range bufs {
			bufs[i] = make([]Move, 0, 256)
		}
		fmt.Println(perft(&p, d, bufs))
		return 0
	}
	return usage()
}
