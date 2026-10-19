#!/bin/sh
# Pomiar wszystkich modeli na OPUBLIKOWANEJ wersji jerzyk-bench (po anonimizacji), do tabel w README i kartach.
# Uruchamiać na komputerze z co najmniej 16 GB pamięci: Bielik 11B potrzebuje ok. 8 GB pamięci.
#
#   python3 wydanie.py                         # najpierw zbiór w wersji do publikacji (wydanie/hf-dataset/data)
#   caffeinate -ims ./run_wydanie_eval.sh      # na Macu; na Linuksie bez caffeinate
#   python3 tabela.py --pub                    # tabele z wyników *-pub
#
# Potrzebne: .venv (laya), llama-server, pliki GGUF (TRENING.md), opcjonalnie .venv-basal (run_basal.sh).
# Ścieżki GGUF można podać zmiennymi: BIELIK_GGUF=… QWEN_GGUF=… ./run_wydanie_eval.sh
# Skrypt pomija modele, które mają już wynik w results/ — można go przerwać i uruchomić ponownie.
cd "$(dirname "$0")"
export USE_TF=0
D=wydanie/hf-dataset/data
TEST="$D/sad_test.jsonl $D/adm_test.jsonl $D/ksieg_test.jsonl $D/email_test.jsonl"
REAL="$D/sad_real_test.jsonl $D/adm_real_test.jsonl"
FRAG="$D/sad_real_fragmenty_test.jsonl"
BIELIK_GGUF=${BIELIK_GGUF:-models/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf}
QWEN_GGUF=${QWEN_GGUF:-models/Qwen3-8B-Q4_K_M.gguf}
mkdir -p logs results
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python   # laya jest tylko w .venv
[ -f "$D/sad_test.jsonl" ] || { echo "brak $D — najpierw python3 wydanie.py"; exit 1; }

# ocena jednego modelu na trzech zestawach: NAZWA RODZAJ URL [dodatkowe argumenty evaluate.py]
ocen() {
  n=$1; k=$2; u=$3; shift 3
  for zestaw in "pub:$TEST" "pub-real:$REAL" "pub-frag:$FRAG"; do
    s=${zestaw%%:*}; pliki=${zestaw#*:}
    [ -f "results/bench-$n-$s.json" ] && continue
    "$PY" evaluate.py --kind "$k" --url "$u" --name "$n-$s" "$@" $pliki > "logs/eval-$n-$s.log" 2>&1 \
      || { echo "$n-$s: błąd, zob. logs/eval-$n-$s.log"; return 1; }
  done
  echo "$n gotowy"
}

# serwer llama.cpp dla modelu GGUF na czas pomiaru: NAZWA PLIK_GGUF
llm() {
  [ -f "$2" ] || { echo "$1: brak $2 (pomijam)"; return; }
  llama-server -m "$2" --port 9940 -c 16384 -np 1 -ngl 99 > "logs/serve-$1-pub.log" 2>&1 &
  pid=$!
  until curl -s localhost:9940/health | grep -q ok; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$1: serwer padł"; tail -5 "logs/serve-$1-pub.log"; return; }
  done
  ocen "$1" llm http://127.0.0.1:9940
  kill $pid; sleep 3
}

ocen jerzyk-1.0 laya models/jerzyk-1.0 --kalibracja models/jerzyk-1.0/calibration.json
llm qwen3-8b "$QWEN_GGUF"
llm bielik-11b "$BIELIK_GGUF"
if [ -x .venv-basal/bin/basal-serve ]; then
  .venv-basal/bin/basal-serve --model Remek/basal-2.0-mini-MLX-8bit --mode mlx --port 9950 > logs/serve-basal-pub.log 2>&1 &
  pid=$!
  until curl -s localhost:9950/health >/dev/null 2>&1; do sleep 5; kill -0 $pid 2>/dev/null || break; done
  ocen basal-2.0-mini systemone http://127.0.0.1:9950
  kill $pid
else
  echo "basal: brak .venv-basal (pomijam; zob. run_basal.sh)"
fi
