#!/bin/sh
# Evaluates a Laya/Jerzyk model on the test set (generated + real documents).
# Usage: scripts/evaluate_model.sh NAME MODEL [CALIBRATION_FILE]
cd "$(dirname "$0")/.." || exit 1
export USE_TF=0
TEST="data/bench/sad_test.jsonl data/bench/adm_test.jsonl data/bench/ksieg_test.jsonl data/bench/email_test.jsonl"
REAL="data/bench/sad_real_test.jsonl data/bench/adm_real_test.jsonl"
CALIBRATION=${3:+--calibration $3}
.venv/bin/python -m scripts.evaluate --kind laya --url "$2" --name "$1" $CALIBRATION $TEST > "logs/eval-$1.log" 2>&1
.venv/bin/python -m scripts.evaluate --kind laya --url "$2" --name "$1-real" $CALIBRATION $REAL > "logs/eval-$1-real.log" 2>&1
