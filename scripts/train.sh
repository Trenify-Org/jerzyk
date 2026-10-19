#!/bin/sh
# Jerzyk v4: data v3 (SAOS 250, corrected e-mails) + 84 real official letters x2 (scripts/notices_training_data.py)
# -> training -> calibration -> evaluation. Run from any directory; it changes to the repository root.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs results
export USE_TF=0 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.75 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.6
DEV="data/bench/sad_dev.jsonl data/bench/adm_dev.jsonl data/bench/ksieg_dev.jsonl data/bench/email_dev.jsonl data/bench/sad_real_dev.jsonl"
REAL="data/bench/sad_real_test.jsonl data/bench/adm_real_test.jsonl"

# training on a Mac (Apple GPU, MPS)
[ -f models/jerzyk-v4/model.safetensors ] || .venv/bin/laya-train --data data/train_v4/train.jsonl \
  --base convaiinnovations/laya-multilingual --out models/jerzyk-v4 --epochs 4 --micro-batch 2 --grad-accum 8 \
  --shuffle-options --loss soft-ce --device mps > logs/train-v4.log 2>&1 || { echo "training v4 failed"; tail -3 logs/train-v4.log; exit 1; }
# training on an NVIDIA GPU (Linux / WSL2) instead of the line above:
#  --device cuda --micro-batch 8 --grad-accum 2

.venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-v4 --name dev-jerzyk-v4 $DEV > logs/eval-dev-v4.log 2>&1
.venv/bin/python -m scripts.calibrate --model models/jerzyk-v4 $DEV > logs/calibrate-v4.log 2>&1
./scripts/evaluate_model.sh jerzyk-v4-kal models/jerzyk-v4 models/jerzyk-v4.calibration.json
.venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-v4 --calibration models/jerzyk-v4.calibration.json --name jerzyk-v4-kal-real2 $REAL > logs/eval-v4-real2.log 2>&1
.venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-v4 --calibration models/jerzyk-v4.calibration.json --name jerzyk-v4-kal-frag data/bench/sad_real_fragmenty_test.jsonl > logs/eval-v4-frag.log 2>&1
echo "v4 ready"
