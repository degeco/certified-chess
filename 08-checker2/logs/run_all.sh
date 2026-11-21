#!/usr/bin/env bash
cd /home/dege/chess/08-checker2
./compare.sh ../05-solver/certs > logs/compare_solver.txt 2>&1
./compare.sh ../04-tablebase/results 2000 1 > logs/compare_tablebase.txt 2>&1
python3 mutate.py 200 1 > logs/mutate.txt 2>&1; echo "exit=$?" >> logs/mutate.txt
python3 mutate.py 200 1 --with-crlf > logs/mutate_crlf.txt 2>&1; echo "exit=$?" >> logs/mutate_crlf.txt
echo done > logs/done
