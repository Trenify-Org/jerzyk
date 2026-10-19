# How to train and improve Jerzyk

How to reproduce the whole process — on a Mac, on a computer with an NVIDIA card, or on a rented cloud server.

## 1. How it works (in short)

```
jerzyk.questions.RECIPES ──► letter generator (LLM) ──► filter (second LLM) ──► Jerzyk training (laya-train) ──► evaluation (scripts.evaluate)
   "summons,                  Qwen writes training       Bielik rejects letters     Laya multilingual 322M
    7 days"                   data; Bielik writes the    that do not match the      learns the answers
                              test                       recipe                     from the recipes
```

- **Training answers follow from the recipe**, not from the model's evaluation — the generating model only has to write a good letter.
- **The large models (Bielik, Qwen) are needed only to prepare the data.** Jerzyk itself is small and runs even on a CPU.

## 2. Requirements

| | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.11 |
| Memory for generating data | 16 GB (one model at a time) | 32 GB+ (Bielik and Qwen at once) or a 24 GB+ card |
| Memory for training Jerzyk | 8 GB | 16 GB |
| Disk | 20 GB | 40 GB |

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[serve,data]"
```

From the repository root, `pip install -e .` installs the `jerzyk` package (defined in `pyproject.toml`). The extras add the rest: `serve` (the HTTP server, FastAPI and uvicorn) and `data` (PDF reading, pypdf).

Models for preparing the data (Apache 2.0 licence):

| Model | Role | File |
|---|---|---|
| Bielik 11B v3 | writes the test set, filters the data | `speakleash/Bielik-11B-v3.0-Instruct-GGUF` → `Bielik-11B-v3.0-Instruct.Q4_K_M.gguf` |
| Qwen3 8B | writes the training data | `Qwen/Qwen3-8B-GGUF` → `Qwen3-8B-Q4_K_M.gguf` |
| Laya multilingual | base model of Jerzyk | `convaiinnovations/laya-multilingual` (downloads by itself) |

## 3. Differences between hardware

The scripts talk to the models through an OpenAI-compatible API (`/v1/chat/completions` with `logprobs`), so the server can be swapped without changing the code.

| | Mac (Apple Silicon) | NVIDIA card (own or in the cloud) | CPU only |
|---|---|---|---|
| LLM server | `llama-server` (Homebrew) | `vllm serve` or `llama-server` built with CUDA | — (too slow) |
| Training | `laya-train --device mps` | `laya-train --device cuda` | possible, very slow |
| Running Jerzyk | yes | yes | **yes** (~0.1–0.3 s per letter) |

### Mac — model servers
```bash
llama-server -m models/Bielik-11B-v3.0-Q4_K_M.gguf --port 9934 -c 16384 -np 4 -ngl 99
llama-server -m models/Qwen3-8B-Q4_K_M.gguf       --port 9932 -c 16384 -np 4 -ngl 99
```

### NVIDIA — model servers (vLLM, much faster with many parallel requests)
```bash
pip install vllm
vllm serve speakleash/Bielik-11B-v3.0-Instruct --port 9934 --max-logprobs 20
vllm serve Qwen/Qwen3-8B                       --port 9932 --max-logprobs 20
```
With vLLM, raise the parallelism of the scripts, e.g. `--workers 32` instead of the default 4.

### NVIDIA — training (CUDA)
Example: a recent NVIDIA card. Install PyTorch with CUDA 12.8 wheels first, then the rest of the requirements:
```bash
uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -e ".[serve,data]"
```
Then train with `--device cuda --micro-batch 8 --grad-accum 2` in place of the Mac settings in section 4, step 4.

## 4. Step by step

```bash
# 1. Test and dev sets (Bielik) — once only; NEVER used for training
python3 -m scripts.generate_benchmark --url http://127.0.0.1:9934    # data/bench/{domain}_{test,dev}.jsonl
python3 -m scripts.check_benchmark  --url http://127.0.0.1:9934      # flags for suspicious letters
python3 -m scripts.review_benchmark --flags --count 30                 # manual review

# 2. Real letters
python3 -m scripts.fetch_saos --count 300                              # court rulings (SAOS)
.venv/bin/python -m scripts.fetch_notices data/real/bip_urls.txt     # public notices from offices

# 3. Training data (Qwen writes, Bielik filters)
python3 -m scripts.generate_training_data gen   --url http://127.0.0.1:9932 --n 500
python3 -m scripts.generate_training_data check --url http://127.0.0.1:9934
python3 -m scripts.generate_training_data build --out data/train_v4/train.jsonl --notice-repeats 2

# 4. Training
USE_TF=0 .venv/bin/laya-train --data data/train_v4/train.jsonl \
  --base convaiinnovations/laya-multilingual --out models/jerzyk-v4 \
  --epochs 4 --micro-batch 2 --grad-accum 8 \
  --shuffle-options --loss soft-ce --device mps        # on NVIDIA: --device cuda --micro-batch 8 --grad-accum 2

# 5. Calibration (temperatures fitted on dev only)
.venv/bin/python -m scripts.calibrate --model models/jerzyk-v4 \
  data/bench/sad_dev.jsonl data/bench/adm_dev.jsonl data/bench/ksieg_dev.jsonl \
  data/bench/email_dev.jsonl data/bench/sad_real_dev.jsonl

# 6. Evaluation on the benchmark
USE_TF=0 .venv/bin/python -m scripts.evaluate --kind laya --url models/jerzyk-v4 \
  --calibration models/jerzyk-v4.calibration.json --name jerzyk-v4 data/bench/*_test.jsonl
python3 -m scripts.evaluate --kind llm --url http://127.0.0.1:9934 --name bielik data/bench/*_test.jsonl
```

Steps 4–6 are run in one go by the pipeline script, `scripts/train.sh`. It starts from the v4 training data (`data/train_v4/train.jsonl`, built in step 3), trains Jerzyk, calibrates it on the dev sets, and evaluates it on the test sets. On a Mac, run it as `caffeinate -ims ./scripts/train.sh`. Its shorter helpers are `scripts/evaluate_model.sh NAME MODEL [CALIBRATION_FILE]` (evaluates one Laya model on the generated and real test sets) and `scripts/evaluate_published.sh` (measures all models on the published version of the benchmark; see `scripts/build_release.py`).

All scripts **resume where they stopped** — you can interrupt them and run them again.

### How long it takes (measured)

| Step | Mac (Apple Silicon) | A100/H100-class card (estimate) |
|---|---|---|
| 500 letters from Bielik (4 in parallel) | ~70 min | a few minutes |
| Evaluation of 500 letters by Bielik | ~30 min | 1–2 min |
| Training Jerzyk, 1,350 examples × 6 epochs | ~40–60 min | ~5 min |
| Jerzyk: one letter, 3 questions | ~0.1 s | ~0.02 s |

Note: when two models share one card (e.g. Bielik and Qwen at once on a Mac), each one runs roughly twice as slowly.

## 5. How to improve it

| What you want to do | Where |
|---|---|
| A new document type or variant (e.g. "decision on demolition, appeal within 14 days") | `jerzyk/questions.py`: `DOCUMENT_TYPES` + `RECIPES` |
| A new domain / industry | `jerzyk/questions.py`: new `DOCUMENT_TYPES[...]`, `questions()`, `RECIPES`; `scripts/generate_benchmark.py`: `RECIPIENT`, `concrete_details()` |
| A new question (e.g. "does the letter require a signature") | `jerzyk/questions.py`: `questions()`; add the labelling rules to `docs/SPEC.md` |
| More real letters | `data/real/` — add the source (e.g. addresses in `bip_urls.txt`) |
| More varied generated data | `scripts/generate_benchmark.py`: lists `FIRST_NAMES`, `SURNAMES`, `COMPANIES`, `CITIES`, `EMAIL_SCENARIOS`, `PRODUCTS` |
| More data | `python3 -m scripts.generate_training_data gen --n 1000` (best on an NVIDIA card) |
| Training settings | `laya-train --help`: `--epochs`, `--encoder-lr`, `--grad-accum`, `--label-smoothing` |

Tips from earlier versions:
- the biggest gain comes from **quality and clarity of the answers** (the hard rules in `docs/SPEC.md`), then from **real letters**, and only after that from more data;
- evaluate every change on the **same** test set and compare it with the previous version;
- report results separately for real and generated letters.

## 6. Rules we do not break

1. **The test set never goes into training** — neither in whole nor in part.
2. **The test is written by a different model than the training data** (Bielik vs Qwen) — otherwise Jerzyk learns the style of the test.
3. **Training data comes only from open-licence models** (Apache 2.0) and from official documents — not from answers of Claude, ChatGPT or other services whose terms restrict training models.
4. **Personal data:** generated data is fictitious; real letters are anonymised before publication.
5. **Changing a definition in `docs/SPEC.md` = relabelling the data** — old labels no longer match.

## 7. Cloud session (when it is too slow locally)

1. Rent a server with an NVIDIA card (24–80 GB), preferably from an EU provider (e.g. Scaleway, OVH, Hetzner).
2. Copy the project folder **without** `models/*.gguf`, `logs/`, `.venv/` and `data/bench/` (the test set stays local, unless you want to evaluate there too).
3. Install the dependencies and vLLM (sections 2–3), then run steps 3–6 with `--device cuda` and a higher `--workers`.
4. Download `models/jerzyk-vN` and `data/train_v4/`, then **switch off the server** — you pay for the time it runs.
