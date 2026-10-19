#!/bin/sh
# Ocena modelu Laya/Jerzyk na teście (wygenerowany + prawdziwy). Użycie: ./eval_laya.sh NAZWA MODEL [PLIK_KALIBRACJI]
cd "$(dirname "$0")"
export USE_TF=0
TEST="data/bench/sad_test.jsonl data/bench/adm_test.jsonl data/bench/ksieg_test.jsonl data/bench/email_test.jsonl"
REAL="data/bench/sad_real_test.jsonl data/bench/adm_real_test.jsonl"
KAL=${3:+--kalibracja $3}
.venv/bin/python evaluate.py --kind laya --url "$2" --name "$1" $KAL $TEST > "logs/eval-$1.log" 2>&1
.venv/bin/python evaluate.py --kind laya --url "$2" --name "$1-real" $KAL $REAL > "logs/eval-$1-real.log" 2>&1
