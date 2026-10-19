# Jak wytrenować i ulepszać Jerzyka

Instrukcja odtworzenia całego procesu — na Macu, na komputerze z kartą NVIDIA albo na wynajętym serwerze w chmurze.

## 1. Jak to działa (w skrócie)

```
tasks.PRZEPISY ──► generator pism (LLM) ──► odsiew (drugi LLM) ──► trening Jerzyka (laya-train) ──► ocena (jerzyk-bench)
   „wezwanie,         Qwen pisze dane         Bielik odrzuca          Laya multilingual 322M           evaluate.py
    7 dni”            treningowe;             pisma niezgodne         uczy się odpowiedzi
                      Bielik pisze test       z przepisem             z przepisów
```

- **Odpowiedzi treningowe wynikają z przepisu**, nie z oceny modelu — model generujący ma tylko dobrze napisać pismo.
- **Duże modele (Bielik, Qwen) potrzebne są tylko do przygotowania danych.** Sam Jerzyk jest mały i działa nawet na procesorze.

## 2. Wymagania

| | Minimum | Zalecane |
|---|---|---|
| Python | 3.11 | 3.11 |
| Pamięć do generowania danych | 16 GB (jeden model naraz) | 32 GB+ (Bielik i Qwen naraz) lub karta 24 GB+ |
| Pamięć do treningu Jerzyka | 8 GB | 16 GB |
| Dysk | 20 GB | 40 GB |

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python laya fastapi uvicorn pypdf
```

Modele do przygotowania danych (licencja Apache 2.0):

| Model | Rola | Plik |
|---|---|---|
| Bielik 11B v3 | pisze zbiór testowy, odsiewa dane | `speakleash/Bielik-11B-v3.0-Instruct-GGUF` → `Bielik-11B-v3.0-Instruct.Q4_K_M.gguf` |
| Qwen3 8B | pisze dane treningowe | `Qwen/Qwen3-8B-GGUF` → `Qwen3-8B-Q4_K_M.gguf` |
| Laya multilingual | model bazowy Jerzyka | `convaiinnovations/laya-multilingual` (pobiera się sam) |

## 3. Różnice między sprzętem

Skrypty rozmawiają z modelami przez API zgodne z OpenAI (`/v1/chat/completions` z `logprobs`), więc serwer można wymienić bez zmian w kodzie.

| | Mac (Apple Silicon) | Karta NVIDIA (własna lub w chmurze) | Sam procesor |
|---|---|---|---|
| Serwer LLM | `llama-server` (Homebrew) | `vllm serve` albo `llama-server` z CUDA | — (za wolno) |
| Trening | `laya-train --device mps` | `laya-train --device cuda` | możliwy, bardzo wolny |
| Uruchamianie Jerzyka | tak | tak | **tak** (~0,1–0,3 s na pismo) |

### Mac — serwery modeli
```bash
llama-server -m models/Bielik-11B-v3.0-Q4_K_M.gguf --port 9934 -c 16384 -np 4 -ngl 99
llama-server -m models/Qwen3-8B-Q4_K_M.gguf       --port 9932 -c 16384 -np 4 -ngl 99
```

### NVIDIA — serwery modeli (vLLM, dużo szybsze przy wielu zapytaniach naraz)
```bash
pip install vllm
vllm serve speakleash/Bielik-11B-v3.0-Instruct --port 9934 --max-logprobs 20
vllm serve Qwen/Qwen3-8B                       --port 9932 --max-logprobs 20
```
Przy vLLM zwiększ równoległość skryptów, np. `--workers 32` zamiast domyślnych 4.

## 4. Proces krok po kroku

```bash
# 1. Zbiór testowy i dev (Bielik) — tylko raz; NIGDY nie trafia do treningu
python3 gen_bench.py --url http://127.0.0.1:9934            # data/bench/{domena}_{test,dev}.jsonl
python3 precheck.py  --url http://127.0.0.1:9934            # flagi podejrzanych pism
python3 review.py --flagi --ile 30                          # przegląd ręczny

# 2. Prawdziwe pisma
python3 saos.py --ile 300                                   # orzeczenia sądów (SAOS)
.venv/bin/python bip.py data/real/bip_urls.txt              # obwieszczenia urzędów

# 3. Dane treningowe (Qwen pisze, Bielik odsiewa)
python3 train_v1.py gen   --url http://127.0.0.1:9932 --n 500
python3 train_v1.py check --url http://127.0.0.1:9934
python3 train_v1.py build                                   # data/train_v1/train.jsonl

# 4. Trening
USE_TF=0 .venv/bin/laya-train --data data/train_v1/train.jsonl \
  --base convaiinnovations/laya-multilingual --out models/jerzyk-v1 \
  --epochs 4 --grad-accum 2 --shuffle-options --loss soft-ce --device mps   # albo cuda

# 5. Ocena na benchmarku
USE_TF=0 .venv/bin/python evaluate.py --kind laya --url models/jerzyk-v1 --name jerzyk-v1 data/bench/*_test.jsonl
python3 evaluate.py --kind llm --url http://127.0.0.1:9934 --name bielik data/bench/*_test.jsonl
```

Na Macu kroki 3–4 uruchamia jednym poleceniem `caffeinate -ims ./run_v1.sh`.
Wszystkie skrypty **wznawiają pracę od miejsca przerwania** — można je zatrzymać i uruchomić ponownie.

### Ile to trwa (zmierzone)

| Krok | Mac (Apple Silicon) | Karta klasy A100/H100 (szacunek) |
|---|---|---|
| 500 pism od Bielika (4 równolegle) | ~70 min | kilka minut |
| Ocena 500 pism przez Bielika | ~30 min | 1–2 min |
| Trening Jerzyka, 1 350 przykładów × 6 epok | ~40–60 min | ~5 min |
| Jerzyk: jedno pismo, 3 pytania | ~0,1 s | ~0,02 s |

Uwaga: gdy dwa modele dzielą jedną kartę (np. Bielik i Qwen naraz na Macu), każdy zwalnia mniej więcej dwukrotnie.

## 5. Jak ulepszać

| Co chcesz zrobić | Gdzie |
|---|---|
| Nowy rodzaj pisma lub wariant (np. „decyzja o rozbiórce, odwołanie 14 dni”) | `tasks.py`: `RODZAJE` + `PRZEPISY` |
| Nowa dziedzina / branża | `tasks.py`: nowe `RODZAJE[...]`, `questions()`, `PRZEPISY`; `gen_bench.py`: `ODBIORCA`, `realia()` |
| Nowe pytanie (np. „czy pismo wymaga podpisu”) | `tasks.py`: `questions()`; zasady oznaczania dopisz do `SPEC.md` |
| Więcej prawdziwych pism | `data/real/` — dopisz źródło (np. adresy do `bip_urls.txt`) |
| Bardziej różnorodne dane | `gen_bench.py`: listy `IMIONA`, `FIRMY`, `MIASTA`, `SCENARIUSZE_EMAIL`, `PRODUKTY` |
| Więcej danych | `train_v1.py gen --n 1000` (najlepiej na karcie NVIDIA) |
| Ustawienia treningu | `laya-train --help`: `--epochs`, `--encoder-lr`, `--grad-accum`, `--label-smoothing` |

Wskazówki z dotychczasowych wersji:
- największy zysk daje **jakość i jednoznaczność odpowiedzi** (twarde reguły w `SPEC.md`), potem **prawdziwe pisma**, a dopiero potem więcej danych;
- każdą zmianę oceniaj na **tym samym** zbiorze testowym i porównuj z poprzednią wersją;
- wyniki podawaj osobno dla pism prawdziwych i wygenerowanych.

## 6. Zasady, których nie łamiemy

1. **Zbiór testowy nigdy nie trafia do treningu** — ani w całości, ani w części.
2. **Test pisze inny model niż dane treningowe** (Bielik vs Qwen) — inaczej Jerzyk uczy się stylu testu.
3. **Dane treningowe tylko z modeli o otwartej licencji** (Apache 2.0) i z dokumentów urzędowych — nie z odpowiedzi Claude'a, ChatGPT ani innych usług, których warunki ograniczają trenowanie modeli.
4. **Dane osobowe:** dane generowane są fikcyjne; prawdziwe pisma anonimizujemy przed publikacją.
5. **Zmiana definicji w `SPEC.md` = ponowne oznaczenie danych** — stare etykiety przestają pasować.

## 7. Sesja w chmurze (gdy lokalnie za wolno)

1. Wynajmij serwer z kartą NVIDIA (24–80 GB), najlepiej u dostawcy z UE (np. Scaleway, OVH, Hetzner).
2. Skopiuj folder projektu **bez** `models/*.gguf`, `logs/`, `.venv/` i `data/bench/` (test zostaje lokalnie, chyba że chcesz tam też oceniać).
3. Zainstaluj zależności i vLLM (sekcje 2–3), uruchom kroki 3–5 z `--device cuda` i większym `--workers`.
4. Pobierz `models/jerzyk-vN` i `data/train_v1/`, **wyłącz serwer** — płacisz za czas jego działania.
