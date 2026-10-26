# Syncra — Timing Report (Task 10.4)

Measured on 2026-10-26 on the development Mac (Apple M2 Pro, models on the GPU through Metal), with the demo company loaded (`make demo`) and the 66 questions of `make eval`. Ollama runs qwen3:8b natively with 8192 tokens of context.

The target was the first word of an answer in under 3 seconds. **It is met only partly: about 3.5 to 4 seconds after a question, once the models are loaded.** The gap is the answer model reading its prompt, explained below with the ways to close it.

---

## Time per stage, models loaded

**Memory, prompt guard and intent: a few milliseconds each.** Loading the last turns is one query; the intent router answers in about 6 ms; the guard is a small classifier (not measured: it needs `HF_TOKEN`).

**Rewriting a follow-up: 0.4 to 0.9 seconds** (qwen3:4b, only when the chat has history).

**Search: about 0.2 seconds** for the three searches in parallel and the reranker, 0.4 to 0.7 seconds as the evaluation measures it alongside other work. On the demo data the database queries take a few milliseconds; the embedder and the reranker take the rest.

**First word: median 3.4 seconds after the search** (max 10 s, the first question while models were still loading). Almost all of it is qwen3:8b reading the prompt before it can write.

**The whole answer: median 5.7 seconds.**

**The claim check: median 1.3 seconds**, after the last word and before the checked reply replaces the draft.

**Small talk: instant.** No search, no LLM.

---

## Where the first-word time goes

**The answer prompt is 1,100 to 1,700 tokens**: the rules and examples (about 700, the same for every question) and up to 8 pieces of evidence.

**qwen3:8b reads about 420 tokens per second on this machine.** Ollama keeps the shared beginning of the prompt cached between questions, so a typical question costs the evidence and the question, about 1,000 tokens, or roughly 2.4 seconds, plus the search and the first generated word.

**Cold starts were the worst part, and are fixed.** The first question after starting used to take 8 to 19 seconds while the embedder, reranker, NLI model and qwen3:8b loaded. The API now loads them in the background when it starts (`WARM_UP`), and Ollama keeps its models loaded for 30 minutes after each call (`OLLAMA_KEEP_ALIVE`) instead of 5.

---

## What was tuned

**Model warm-up at API start**, in a background thread so the API answers at once.

**Ollama keep-alive of 30 minutes**, so qwen3:8b isn't reloaded between questions.

**A shorter timeout for chat calls** (`CHAT_TIMEOUT_SECONDS`, 30 s, one retry), so a hung Ollama costs a user 30 seconds, not six minutes.

**HNSW needs no tuning yet.** With pgvector's iterative scan, the filtered vector search takes milliseconds on the demo data. Revisit `hnsw.ef_search` once a real install holds hundreds of thousands of chunks.

**Every chat reply logs its stage timings** (memory, guard, intent, rewrite, search, first word, answer, check), and replies slower than `SLOW_ANSWER_SECONDS` show up in `GET /admin/status`.

---

## Closing the gap (your choice)

**Answer with qwen3:4b instead of qwen3:8b.** About twice as fast to read the prompt, so the first word would come at roughly 1.5 to 2 seconds. Answers may be a little weaker; `make eval` would show by how much. One line in `config/models.yaml`.

**Send fewer pieces of evidence**, e.g. `TOP_K_EVIDENCE=5`. Fewer tokens to read, at some risk of missing the piece that holds the answer (the evaluation found every expected source within the top 8).

**Turn on Ollama's flash attention** (`OLLAMA_FLASH_ATTENTION=1` in Ollama's environment), which speeds up reading long prompts on Apple GPUs. This is a setting of the Ollama app, not of Syncra.

**A faster machine.** A desktop NVIDIA GPU reads prompts several times faster than a laptop.

To measure again: load the demo, then `make eval`.
