#!/bin/sh
# Measures all models on the PUBLISHED version of jerzyk-bench (after anonymisation), for the tables in the README and model cards.
# Run on a computer with at least 16 GB of memory: Bielik 11B needs about 8 GB of memory.
#
#   python3 -m scripts.build_release                 # first the dataset in the publication version (wydanie/hf-dataset/data)
#   caffeinate -ims scripts/evaluate_published.sh    # on a Mac; on Linux / WSL: scripts/evaluate_published.sh
#   python3 -m scripts.results_table --published     # tables from the *-pub results
#
# Needed: .venv (laya), llama-server, GGUF files (docs/TRAINING.md), optionally .venv-basal (scripts/evaluate_basal.sh).
# GGUF paths can be given with variables: BIELIK_GGUF=... QWEN_GGUF=... scripts/evaluate_published.sh
# The script skips models that already have results in results/, so it can be stopped and started again.
cd "$(dirname "$0")/.." || exit 1
export USE_TF=0
D=wydanie/hf-dataset/data
TEST="$D/sad_test.jsonl $D/adm_test.jsonl $D/ksieg_test.jsonl $D/email_test.jsonl"
REAL="$D/sad_real_test.jsonl $D/adm_real_test.jsonl"
FRAG="$D/sad_real_fragmenty_test.jsonl"
BIELIK_GGUF=${BIELIK_GGUF:-models/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf}
QWEN_GGUF=${QWEN_GGUF:-models/Qwen3-8B-Q4_K_M.gguf}
mkdir -p logs results
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python   # laya is installed only in .venv
[ -f "$D/sad_test.jsonl" ] || { echo "missing $D, run python3 -m scripts.build_release first"; exit 1; }
# machine name for the latency column of the table (scripts/results_table.py --published); can be overridden: HARDWARE="..." scripts/evaluate_published.sh
HARDWARE=${HARDWARE:-$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)}
HARDWARE=${HARDWARE:-$(sysctl -n machdep.cpu.brand_string 2>/dev/null)}
echo "$HARDWARE" > results/hardware-published.txt

# evaluates one model on the three sets: NAME KIND URL [extra evaluate arguments]
evaluate_model() {
  name=$1; kind=$2; url=$3; shift 3
  for subset in "pub:$TEST" "pub-real:$REAL" "pub-frag:$FRAG"; do
    suffix=${subset%%:*}; files=${subset#*:}
    [ -f "results/bench-$name-$suffix.json" ] && continue
    "$PY" -m scripts.evaluate --kind "$kind" --url "$url" --name "$name-$suffix" "$@" $files > "logs/eval-$name-$suffix.log" 2>&1 \
      || { echo "$name-$suffix: error, see logs/eval-$name-$suffix.log"; return 1; }
  done
  echo "$name ready"
}

# llama.cpp server for a GGUF model during the measurement: NAME GGUF_FILE
serve_gguf() {
  [ -f "results/bench-$1-pub-frag.json" ] && { echo "$1: results already exist (skipping)"; return; }
  [ -f "$2" ] || { echo "$1: missing $2 (skipping)"; return; }
  llama-server -m "$2" --port 9940 -c 16384 -np 1 -ngl 99 > "logs/serve-$1-pub.log" 2>&1 &
  pid=$!
  until curl -s localhost:9940/health | grep -q ok; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$1: server crashed"; tail -5 "logs/serve-$1-pub.log"; return; }
  done
  evaluate_model "$1" llm http://127.0.0.1:9940
  kill $pid; sleep 3
}

evaluate_model jerzyk-1.0 laya models/jerzyk-1.0 --calibration models/jerzyk-1.0/calibration.json
serve_gguf qwen3-8b "$QWEN_GGUF"
serve_gguf bielik-11b "$BIELIK_GGUF"
if [ -f results/bench-basal-2.0-mini-pub-frag.json ]; then
  echo "basal-2.0-mini: results already exist (skipping)"
elif [ -x .venv-basal/bin/basal-serve ]; then
  .venv-basal/bin/basal-serve --model Remek/basal-2.0-mini-MLX-8bit --mode mlx --port 9950 > logs/serve-basal-pub.log 2>&1 &
  pid=$!
  until curl -s localhost:9950/health >/dev/null 2>&1; do sleep 5; kill -0 $pid 2>/dev/null || break; done
  evaluate_model basal-2.0-mini systemone http://127.0.0.1:9950
  kill $pid
else
  echo "basal: no .venv-basal (skipping; see scripts/evaluate_basal.sh)"
fi
