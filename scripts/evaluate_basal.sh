#!/bin/sh
# Measures basal models (github.com/rkinas/basal, Apache 2.0) on jerzyk-bench through their native /v1/systemone (MLX on a Mac).
# Usage: scripts/evaluate_basal.sh [mini 4.5B max]
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs results
TEST="data/bench/sad_test.jsonl data/bench/adm_test.jsonl data/bench/ksieg_test.jsonl data/bench/email_test.jsonl"
REAL="data/bench/sad_real_test.jsonl data/bench/adm_real_test.jsonl"
[ $# -eq 0 ] && set -- mini 4.5B max   # default: all three basal models
for m in "$@"; do
  name=basal-2.0-$m; [ "$m" = mini ] && repo=Remek/basal-2.0-mini-MLX-8bit || repo=Remek/basal-2.0-$m-MLX-8bit
  [ "$m" = max ] && repo=Remek/basal-2.0-max-MLX-8bit
  .venv-basal/bin/basal-serve --model "$repo" --mode mlx --port 9950 > "logs/serve-$name.log" 2>&1 &
  until curl -s localhost:9950/health >/dev/null 2>&1; do sleep 5; kill -0 $! 2>/dev/null || { echo "$name: server crashed"; tail -5 "logs/serve-$name.log"; continue 2; }; done
  python3 -m scripts.evaluate --kind systemone --url http://127.0.0.1:9950 --name "$name" $TEST > "logs/eval-$name.log" 2>&1
  python3 -m scripts.evaluate --kind systemone --url http://127.0.0.1:9950 --name "$name-real" $REAL > "logs/eval-$name-real.log" 2>&1
  kill $!; sleep 3
  echo "$name ready"
done
