.PHONY: all test unit blackbox edge compare mutate clean
all: mcheck2

mcheck2: go.mod rules.go cert.go main.go
	GOMAXPROCS=4 go build -buildvcs=false -p 4 -o mcheck2 .

test: mcheck2 unit blackbox edge compare mutate

unit:
	go test -buildvcs=false -p 4 -count=1 ./...

blackbox: mcheck2
	./blackbox.sh

compare: mcheck2
	./compare.sh ../04-tablebase/results 2000 1
	./compare.sh ../05-solver/certs

mutate: mcheck2
	python3 mutate.py 200 1

clean:
	rm -f mcheck2

edge: mcheck2
	./edge.sh
