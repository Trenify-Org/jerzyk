#!/bin/sh
# Jerzyk v4: dane v3 (SAOS 250, poprawione e-maile) + 84 prawdziwe pisma urzędowe ×2 (bip_trening.py) → trening → kalibracja → test.
cd "$(dirname "$0")"
export USE_TF=0 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.75 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.6
DEV="data/bench/sad_dev.jsonl data/bench/adm_dev.jsonl data/bench/ksieg_dev.jsonl data/bench/email_dev.jsonl data/bench/sad_real_dev.jsonl"
REAL="data/bench/sad_real_test.jsonl data/bench/adm_real_test.jsonl"
[ -f models/jerzyk-v4/model.safetensors ] || .venv/bin/laya-train --data data/train_v4/train.jsonl \
  --base convaiinnovations/laya-multilingual --out models/jerzyk-v4 --epochs 4 --micro-batch 2 --grad-accum 8 \
  --shuffle-options --loss soft-ce --device mps > logs/train-v4.log 2>&1 || { echo "trening v4 nieudany"; tail -3 logs/train-v4.log; exit 1; }
.venv/bin/python evaluate.py --kind laya --url models/jerzyk-v4 --name dev-jerzyk-v4 $DEV > logs/eval-dev-v4.log 2>&1
.venv/bin/python calibrate.py --model models/jerzyk-v4 $DEV > logs/calibrate-v4.log 2>&1
./eval_laya.sh jerzyk-v4-kal models/jerzyk-v4 models/jerzyk-v4.kalibracja.json
.venv/bin/python evaluate.py --kind laya --url models/jerzyk-v4 --kalibracja models/jerzyk-v4.kalibracja.json --name jerzyk-v4-kal-real2 $REAL > logs/eval-v4-real2.log 2>&1
.venv/bin/python evaluate.py --kind laya --url models/jerzyk-v4 --kalibracja models/jerzyk-v4.kalibracja.json --name jerzyk-v4-kal-frag data/bench/sad_real_fragmenty_test.jsonl > logs/eval-v4-frag.log 2>&1
echo "v4 gotowy"
