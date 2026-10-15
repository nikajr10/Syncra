# Syncra — Progress Log

Live record of what has been built. Agents add an entry here after every task (format in [`agent.md`](agent.md)).

## Current status

- **Current phase:** Phase 4 — Link and store
- **Next task:** 4.2 — Knowledge graph writer (4.3 Search indexes can run in parallel; Phase 5 can start any time)
- **Completed tasks:** 0.1–0.6 (Phase 0 complete), 1.1–1.6 (Phase 1 complete), 2.1–2.3 (Phase 2 complete), 3.1–3.4 (Phase 3 complete), 4.1

## Log

### Task 4.1 — Entity linking (SBERT)  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/link.py`:
  - `key(name)`: the normalised name every spelling of one thing shares. camelCase and separators are split, text is lower-cased, `svc` / `k8s` / `db` are expanded and plural `s` is dropped, so `PaymentService`, `payment-service` and `payments-svc` all become `paymentservice`.
  - `link_entities(session, found) -> {(name, type): entity id}`: a name with a known key goes to that entity. Otherwise SBERT (`entity_linker`, all-MiniLM-L6-v2) compares it with every existing name: at least `threshold` (0.9) similar and with the same numbers → that entity, else a new one. Every name becomes an alias (`source_kind` NULL). Services, tools and projects link across those types (GLiNER mixes them up; the first type seen wins). People link only to people, by exact key, never by SBERT.
  - `link_people(session, accounts) -> {account: entity id}`: the person entity of each item author, decision person or mention, found by its account alias (`github:alice`, with `source_kind` = the source). A new account gets a person entity named after it.
  - `link_identities(session)`: for each Syncra user, merges the person entities of the accounts they linked (`user_source_identities`) and of people known only by their display name, then adds every account and display name as an alias. A merge moves aliases and edges to the oldest entity and deletes the others.
- `find_entities` now also reports Slack mentions (`<@U03>`, `<@U03|maria>`) as people named `slack:U03` (score 1.0), so they link to that account's person.
- `entity_linker.threshold: 0.9` in models.yaml. `numpy` is declared as a dependency (it was already installed with sentence-transformers).
- Tests: the three names become one entity with three aliases, found again later by key and by SBERT ("payment processing service", 0.92); payment / billing / notification service and billing-v1 / v2 stay separate; RabbitMQ as a tool and as a service is one entity, "Jordan" the project and "Jordan" the person are two; accounts are merged through identities (aliases, a name-only person absorbed, edges moved, no stale ORM objects); Slack mentions become people.

**Key files**
- `backend/app/learning/link.py`, `backend/app/learning/entities.py`, `backend/config/models.yaml`, `backend/tests/test_link.py`

**Decisions**
- Normalisation does the heavy lifting, because SBERT on short names is a weak signal. Measured with all-MiniLM-L6-v2: `payments svc` vs `payment service` scores 0.59, while different things score higher: `payment service` vs `billing service` 0.79, `frontend` vs `backend` 0.82, `internal api` vs `external api` 0.86, and version pairs (`billing v1` / `v2`, `api v1` / `v2`) 0.90. So the key expands `svc` and drops plurals, the threshold is 0.9, and names with different numbers never merge.
- False merges are worse than missed ones (a merge mixes two things' people and decisions), so the threshold is conservative: `postgres` / `postgresql` (0.899) and typos stay separate entities.
- Aliases with a `source_kind` are accounts (`github:alice`, `slack:U01`, `jira:<accountId>`); aliases without one are names. Name matching never looks at accounts.
- An account becomes a person without any Syncra user. Accounts in different tools are linked only through `user_source_identities` (filled by Tasks 5.1 / 9.4); `link_identities` must run after identities change (Task 4.4 runs it on every learning run).
- A person entity's `name` is the first identifier seen (an account or a name). Display names are aliases, so readable names for answers come from the aliases (Phases 6 / 7).
- `link.key()` is the normalised-name contract: anything that matches text against aliases (Task 4.2 "about" links, Task 6.4 entities in questions) should compare keys.
- SBERT vectors of names are cached for the process; `link_entities` loads all name aliases once per call.
- `_merge` rewrites rows with SQL, so `link_identities` expires the session afterwards; a test holds an edge object across a merge to keep that true.

**How to run / test**
- `make test`

**Known issues / TODO**
- Two people with the same display name: a mention of that name links to the older one.
- First names (`Maria`) don't link to full names (`Maria Garcia`). GitHub `@login` mentions are not extracted (code decorators look the same).
- The connectors don't fetch Slack or GitHub display names, so people without a Syncra user are known only by their account id.

### Task 3.4 — Embedder  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/embed.py`: `embed_chunks(chunks)` returns one vector per chunk, in order, through `gateway.embed("embedder", …)` (Qwen3-Embedding-0.6B via sentence-transformers, batches of 32, normalised). Vectors that aren't `EMBEDDING_DIM` long raise a `ConfigError` before anything is stored.
- Tests (real model): vectors are 1024 long and unit length; a paraphrase scores more than 0.2 higher than an unrelated sentence; no chunks give no vectors; a wrong `EMBEDDING_DIM` fails clearly.

**Key files**
- `backend/app/learning/embed.py`, `backend/tests/test_embed.py`

**Decisions**
- Chunks are embedded as documents (no instruction prompt). Questions (Task 6.2) must use the model's `query` prompt (`encode(q, prompt_name="query")` adds "Instruct: Given a web search query, retrieve relevant passages…"). `gateway.embed` needs a `prompt_name` argument for that.
- transformers 5 loads Qwen3-Embedding in its checkpoint dtype, bf16, so vectors are unit length only to within ~3e-3. Cosine search is unaffected.

**How to run / test**
- `make test` (loading the 0.6B model adds about 10 s)

**Known issues / TODO**
- bf16 may be slow on a CPU without bf16 support (production `DEVICE=cpu`). Measure in Task 10.4 and load in float32 if it is.

### Task 3.3 — Decision reader step  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/decisions.py`: `read_decision(thread, entities, client=None) -> FoundDecision | None`.
  - Input is a whole conversation: `thread[0]` is the root (`pr`, `issue`, `thread` or `message`) and the rest its replies (reviews, comments), oldest first. Comments, reviews and commits are never read on their own.
  - Conversations with less than `DECISION_MIN_CHARS` (60) characters of text are skipped without a model call. Longer than `DECISION_MAX_CHARS` (6000): the middle is cut (`[…]`), keeping the opening and the conclusion.
  - Renders the thread in the Task 3.2 format, with `<thread>` tags removed from the data, and fills the v1 prompt with it and the entities (`name (type)`, deduplicated).
  - Calls Ollama with the `FoundDecision` JSON schema as `format`, then validates with pydantic. Bad output is retried once, then dropped with a warning. An empty decision means none. `OllamaError` (Ollama down) is not caught.
  - `people` keeps only authors who wrote in the conversation (item authors + Slack line authors), deduplicated.
- Settings `DECISION_MIN_CHARS`, `DECISION_MAX_CHARS`.
- Tests (mocked Ollama): good JSON (and the request: model, system prompt, JSON schema, quoted thread, entities); bad JSON then good; bad twice (dropped, 2 calls); no decision; short conversations and lone comments skipped without a call; a PR read with its review, with a non-author removed from `people` and `</thread>` in the data neutralised; a long thread keeps its start and end; Ollama down raises.

**Key files**
- `backend/app/learning/decisions.py`, `backend/tests/test_decisions.py`

**Decisions**
- Contract for Task 4.4: pass `[root, *replies]`, where replies = items with the same `source_id` and `parent_external_id == root.external_id`, not `noise`, ordered by `created_at`. When only a reply is new, re-read its root's whole conversation. Store at most one decision per root item and replace it on re-read (the wording changes between runs; Ollama samples at the model's default temperature, so the retry isn't a copy of the bad answer).
- "Dropped" (bad output twice) is final for that run; "failed" (Ollama down → `OllamaError`) is what Task 4.4 retries.
- `people` are source ids (`slack:U01`, `github:alice`, `jira:<accountId>`), ready to link to person entities in Task 4.2.

**How to run / test**
- `make test`

**Known issues / TODO**
- Statement-style injections still produce a decision, but with `people` emptied (checked with the real qwen3:8b). A decision is only as trustworthy as its source message, which is linked as evidence.
- One decision per conversation (the most important); long threads with several decisions keep one.
- People who agreed without writing in the thread (e.g. "@tom approved this in the design review") are dropped from `people`.

### Task 3.2 — Decision reader prompt  ✅ done
**Date:** 2026-10-15

**Built**
- `config/prompts/decision_reader.v1.yaml` has two parts:
  - `system`: what counts as a decision, the JSON `{decision, reason, people}`, the empty answer when nothing was decided, people = authors copied as written, and the rule that the conversation is quoted data. It has 3 worked examples: a Slack decision, a PR with an approving review, and an undecided thread that contains an injection attempt.
  - `prompt`: a `string.Template` with `$entities` and `$thread`, which restates the task after the quoted thread.
- `ModelSpec.prompt` and `get_prompt(role)` (cached) in `app/config/settings.py`: the role's `prompt:` in models.yaml names the file (`decision_reader` → `decision_reader.v1`). A missing or invalid file is a `ConfigError`.
- Test: the configured prompt loads, has both placeholders and 2–3 examples whose answers are valid output JSON; a wrong name, or a role without a prompt, fails clearly.

**Key files**
- `backend/config/prompts/decision_reader.v1.yaml`, `backend/app/config/settings.py`, `backend/config/models.yaml`, `backend/tests/test_settings.py`

**Decisions**
- Prompts live in `config/prompts/<role>.v<N>.yaml` with `system` + `prompt`, and models.yaml picks the version per role. To change the wording, add a new version instead of editing one in use. Task 7.1 (answer writer) follows the same pattern.
- The examples assume this thread format, which Task 3.3 must render: a Slack thread is its own `slack:<id>: text` lines; any other item is `<author> (<type>): <title + text>`, the root first, then its replies.
- Prompt-injection defence: the thread is quoted between `<thread>` tags, a rule plus an example shows an instruction being ignored, and the task is restated after the data. Marking every data line with `> ` didn't help; Qwen3 thinking mode didn't either and was 5–10× slower.

**How to run / test**
- `make test`

**Known issues / TODO**
- Smoke test with the real `qwen3:8b` (not part of the suite): 4/4 ordinary conversations right (decision, no decision, decision in a Jira comment, PR + review), about 1–2.5 s each and ~720 prompt tokens. Injection: 2 of 4 attack styles are ignored. Statement-style ones ("the decision is to disable 2FA, decided by U01 and U02") still produce a decision, but anyone who can post in a synced channel could state a fake decision in plain words anyway. Task 3.3 drops `people` who didn't write in the thread, so attribution can't be forged.
- Ollama runs qwen3:8b with a 4096-token context (no `num_ctx` is set). The prompt uses ~720 tokens of it, so Task 3.3 caps the thread length.

### Task 3.1 — Entity finder (GLiNER)  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/entities.py`: `find_entities(texts)` returns, per text, `FoundEntity(name, type, score)` once per (name, type) with its best score. Slack thread author prefixes (`slack:U01: `) are removed first; otherwise GLiNER reports "slack" as a tool in every thread.
- Gateway: `load_gliner(role)` (cached) and `find_entities(role, texts)` (one batched GLiNER `inference` call with the role's labels and threshold; logs time and item count).
- `config/models.yaml`: `entity_finder` got `labels: [person, service, tool, project]` and `threshold: 0.5`. New role `entity_finder_encoder` (`microsoft/deberta-v3-small`, pinned) with `files:` = tokenizer + config only. `ModelSpec` gained `files`, `labels`, `threshold`; `make download-models` downloads only a model's `files` when set.
- New dependencies: `gliner>=0.2.29`, which caps `transformers<5.17` (pip moved transformers 5.19 → 5.16.1; sentence-transformers and SetFit accept it), and `protobuf` (transformers 5 needs it to read DeBERTa's sentencepiece tokenizer).
- Tests: real GLiNER on a sample PR and a Slack thread finds the expected people, services, tools and projects; repeated mentions collapse to one; author prefixes are not entities; "thanks!" gives nothing; labels and threshold come from config.

**Key files**
- `backend/app/learning/entities.py`, `backend/app/models/gateway.py`, `backend/config/models.yaml`, `backend/tests/test_entities.py`

**Decisions**
- Entity types are `entity_finder.labels` in models.yaml; the unused `ENTITY_TYPES` constant was removed from `schema.py`. Plain labels: descriptive wordings ("software service", "technology", "internal service" …) were no better on sample text.
- `threshold: 0.5` (GLiNER's default) had the best precision; 0.3–0.4 added hits like `p99` (project) and `cc` (person).
- The GLiNER repo holds only weights; its tokenizer and encoder config come from `microsoft/deberta-v3-small`, which GLiNER would fetch from the moving `main` branch. `load_gliner` points it at the pinned `entity_finder_encoder` snapshot instead (every HF download stays pinned). Swapping GLiNER means updating both roles.
- Names are kept as written (`PaymentService`, `gRPC`); normalising and merging them is Task 4.1.

**How to run / test**
- `make install` (new deps) · `make download-models` (adds 2.5 MB of encoder files) · `make test`

**Known issues / TODO**
- gliner_small mixes up service and tool (RabbitMQ and gRPC → service, billing-api → tool) and sometimes tags metrics (`p99`) as projects. Task 4.1 should merge one name across types. A bigger GLiNER (`urchade/gliner_medium-v2.1` / `gliner_large-v2.1`) may type better: change `entity_finder` (with its revision) and re-run the tests.
- GLiNER reads at most 384 words per text, and every punctuation mark counts as a word; in code-heavy chunks, entities past that point are missed.
- Loading logs a transformers warning about an "incorrect regex pattern" in the DeBERTa tokenizer. It is a false alarm (tokens match sentencepiece exactly).
- Slack mentions stay raw (`<@U03>`) and are not found as people; Task 4.1 maps them through identities.

### Task 2.3 — Chunker  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/chunk.py`: `chunk_item(item)` cuts `item.full_text` (title + text) into chunks of at most `CHUNK_SIZE` characters (default 1500, about 375 tokens). Each chunk repeats up to `CHUNK_OVERLAP` characters (default 200) from the end of the previous one. `TextChunk` keeps `item_id`, `position`, `text`, `link`, `author`, `created_at`, `access_tags`.
- Pieces before packing: a Slack thread message (a `slack:<id>: …` line, Task 1.4 format) or a fenced code block stays whole when it fits in a chunk. Other text is cut at line breaks and sentence ends, a sentence longer than a chunk at spaces, and a single huge word by characters. The overlap is made of whole pieces, so a code block or message is never half-repeated.
- Settings `CHUNK_SIZE`, `CHUNK_OVERLAP` (characters).
- Tests: long text (sizes, overlap, nothing lost), code blocks (kept whole; an oversized one cut only between lines), very short and empty text, a Slack thread (every message whole and in order, including a multi-line one with code), item details carried over.

**Key files**
- `backend/app/learning/chunk.py`, `backend/tests/test_chunk.py`

**Decisions**
- Sizes are in characters, not tokens: no tokenizer to load, and Qwen3-Embedding's window (32k tokens) is far bigger than 1500 characters. Retrieval precision sets the size, not the window.
- The chunker is pure (no DB writes). Task 4.3 stores chunks in `chunks` (`item_id`, `position`, `text`, `vector`); link, author, time and permissions stay on `items` and are joined from there.
- A code block bigger than a chunk is cut between lines. Otherwise a pasted 50 KB log would become one huge chunk for the embedder and the answer prompt.

**How to run / test**
- `make test`

**Known issues / TODO**
- A chunk's `created_at` is its item's creation time; for a Slack thread that is the first message, not the latest reply.

### Task 2.2 — SetFit triage model  ✅ done
**Date:** 2026-10-15

**Built**
- Gateway: `train_setfit(role, texts, labels)` fine-tunes SetFit on the `<role>_base` body (pinned revision, fresh copy) with a logistic-regression head and saves it to `TRAINED_MODELS_DIR/<role>`; `load_setfit(role)` (cached) and `classify(role, texts)`.
- `app/learning/triage.py`: `examples()` reads `config/triage.yaml`; `train()` trains on a stratified 80/20 split (seed 42) and returns held-out accuracy; `is_obvious_noise(item)` is the rule pre-filter (no text, or a bot author: `github:…[bot]`, `slack:B…`; bot-started threads still go to the classifier); `triage(items)` labels each item `useful` / `noise`; `triage_new_items(session)` sets noise items to status `noise` and returns the useful ones (still `new`) for the chunker.
- `Item.full_text`: the title (unless the text already contains it), a blank line, then the text. Triage and the chunker read this.
- `make train-triage` (`scripts/train_triage.py`) trains, prints the held-out accuracy and exits 1 below 90%. **Held-out accuracy: 98.3% (59/60)**, about 25 s on an M2 Pro (MPS).
- Slack connector: bot messages are now authored `slack:<bot id>` (was the bot's user id), so the rule catches them.
- Setting `TRAINED_MODELS_DIR` (default `backend/trained_models`, git-ignored; compose uses `/models/trained` on the `hf_models` volume). New dependency `setfit>=1.2`.
- Tests: dataset; rules; queue marking with a fake classifier (rule-caught items never reach it, noise is skipped on the next run); one real training run into a temp dir (≥ 90% plus spot checks).

**Key files**
- `backend/app/learning/triage.py`, `backend/app/models/gateway.py`, `backend/scripts/train_triage.py`, `backend/tests/test_triage.py`

**Decisions**
- SetFit classifiers are addressed by role: `train_setfit("triage", …)` trains from `triage_base`. Task 5.5 reuses it: `train_setfit("intent_router", …)` and `classify("intent_router", texts)`.
- Never use `SetFitModel.from_pretrained`: it ignores the pinned revision for the body and calls the Hub to fill in its model card. The gateway builds and loads models itself; `load_setfit` makes no network calls.
- `num_iterations=5`: on this data it's as accurate as 20 iterations or SetFit's default oversampling (150 s), and 8x faster. A stronger body (bge-small, paraphrase-mpnet) didn't help; the data is the limit.
- `triage` takes a list (one batched model call). Useful items keep status `new` until Task 4.4 marks them `processed`, so a second triage run re-checks them but never noise.
- Bot authors: GitHub logins ending in `[bot]`, Slack ids starting with `B`. Jira automation has no marker; the classifier handles it.

**How to run / test**
- `make train-triage` · `make test` (the real training test adds about 20 s)

**Known issues / TODO**
- The worker doesn't triage yet. Task 4.4 wires it in; `load_setfit` raises a `ConfigError` ("run `make train-triage`") when the model is missing.
- Accuracy depends on the split: 90–98% over five random splits (mean 95%). Almost all misses are automated notices kept as useful, which is the safe direction.
- Existing Task 0.5 behaviour: loading a Hub model through `load_sentence_transformer` (also used for training here) makes one Hub metadata request (transformers lists chat templates), even when cached. It falls back to the cache when offline. Air-gapped hosts should set `HF_HUB_OFFLINE=1` after `make download-models`.

### Task 2.1 — Triage training data  ✅ done
**Date:** 2026-10-15

**Built**
- `config/triage.yaml`: 299 hand-written examples, 151 `useful` / 148 `noise`. The two top-level keys are the labels.
- Each example is what triage reads for one item: the title (when the text doesn't already contain it), a blank line, then the text, scrubbed, in the connectors' formats. Every item type is covered: PRs, issues, commits, reviews, inline review comments, Jira issues and comments, Slack messages and threads.
- Noise: thanks / +1 / emoji-only replies, CI and bot chatter (Codecov, Dependabot / Renovate, stale bots, Jira automation, CLA checks), trivial commits, nits, pings, social chat, junk tickets.
- Useful includes deliberate look-alikes: approving reviews however short (`approved: lgtm`), "+1 to RabbitMQ: <reason>", dependency pins with a reason, Jira tickets with no description.
- Test: both labels present and balanced (each ≥ 40%), 100–300 examples, all non-empty strings, no duplicates.

**Key files**
- `backend/config/triage.yaml`, `backend/tests/test_triage.py`

**Decisions**
- Reviews that approve or request changes are **useful** even with an empty body: they are the only record of who reviewed what (Task 4.2 `reviewed` links).
- A bot-started Slack thread with human replies is useful; only bot messages on their own are noise.
- Quote YAML examples that contain `: ` or ` #`, otherwise YAML reads a dict or cuts the text at a comment.

**How to run / test**
- `make test`

**Known issues / TODO**
- All examples are synthetic. When real items get misclassified, add them here and retrain (Task 2.2).

### Security pass (not a phase task)  ✅ done
**Date:** 2026-10-15

**Built**
- Checklist `security.md` run over the whole repo + git history; results and open items in `security-audit.md`.
- `build_connector` rejects malformed `sources.external_id` (fixes Jira JQL injection, GitHub path traversal, Slack DM ids).
- GitHub paging refuses `Link: next` URLs on another host (token never leaves the API host).
- API middleware: security headers, strict CSP (not on /docs), `X-Request-ID`, generic 500 `{"detail","request_id"}`.
- `API_DOCS` setting (default off; `.env.example` turns it on locally, compose forces it off).
- Compose: API bound to `127.0.0.1`, `--no-server-header`, `no-new-privileges`; `.git` in `.dockerignore`.
- `config/models.yaml`: every downloaded HF model pinned to a commit `revision`.

**Key files**
- `backend/app/learning/connectors/__init__.py`, `backend/app/learning/connectors/github.py`, `backend/app/api/main.py`, `backend/config/models.yaml`, `backend/docker-compose.yml`, `backend/tests/test_security.py`, `security-audit.md`

**Decisions**
- New source kinds must add an `EXTERNAL_ID` regex. New outbound clients must not follow URLs to other hosts with credentials.
- New endpoints get headers and generic errors from the middleware; never return exception text to clients.
- Changing an HF model means updating its `revision` too.
- Phase 3/5/6/9 must meet the "fix later" items in `security-audit.md` §8 (prompt injection, in-query permission filter, auth/CORS/rate limits, per-user deletion).

**How to run / test**
- `make test` (65 pass) · `make lint`

**Known issues / TODO**
- Open: Python lock file, restricted DB role, gitleaks/pip-audit in CI, image digest pins, retry jitter (see `security-audit.md` §8).

### Task 1.6 — Scheduled sync job  ✅ done
**Date:** 2026-10-15

**Built**
- `build_connector(source)` registry (`app/learning/connectors/__init__.py`): `sources.kind` → GitHub / Jira / Slack connector built from `sources.external_id` (repo `owner/name`, project key, channel id) and the tokens in settings.
- `sync_all_sources()` (`app/learning/sync.py`): every **enabled** source in its own session → connector → scrubber → `save_items`. A failing source is logged with a traceback, written to `sources.last_error`, and skipped; the others still run. Returns `{source name: rows changed | error}`.
- Scheduler job `sync_sources` (replaces the Task 0.6 heartbeat) every `SYNC_INTERVAL_MINUTES`, first run at worker start.
- Items land with `status = "new"` — that is the queue Phase 2 consumes. Duplicates: in-batch collapse + content-hash upsert (Task 1.1).
- Tests: two sources, one broken → error recorded, other synced; second run stores nothing new; disabled sources skipped; registry builds the right class.

**Key files**
- `backend/app/learning/connectors/__init__.py`, `backend/app/learning/sync.py`, `backend/app/jobs/scheduler.py`, `backend/tests/test_sync_job.py`, `backend/tests/test_jobs.py`

**Decisions**
- Connecting a source = inserting a `sources` row (`kind`, `name`, `external_id`, `enabled`); Task 9.4 adds the UI. Credentials stay in `.env` (`GITHUB_TOKEN`, `JIRA_*`, `SLACK_BOT_TOKEN`), one set per deployment.
- Tests inject `build=` (registry) and `session_factory=`; never monkeypatch connector modules.

**How to run / test**
- `make worker` (runs the sync immediately, then every 15 min) · `make test`

**Known issues / TODO**
- No per-source credentials yet (one GitHub token / Jira account / Slack bot per deployment).

### Task 1.5 — Privacy scrubber (Presidio)  ✅ done
**Date:** 2026-10-15

**Built**
- `Scrubber` (`app/learning/scrub.py`): Presidio `AnalyzerEngine` on spaCy `en_core_web_sm` (role `presidio_nlp` in `models.yaml`) + `AnonymizerEngine`. Masks `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `IBAN_CODE`, `US_SSN`, `IP_ADDRESS` and custom secret recognizers `AWS_ACCESS_KEY`, `GITHUB_TOKEN`, `SLACK_TOKEN`, `PRIVATE_KEY`, `CONNECTION_STRING`, `PASSWORD_ASSIGNMENT`, `JWT`. Each hit becomes `<ENTITY_TYPE>`.
- `scrub_item()` cleans `title` and `text`; `sync_source()` scrubs every item **before** saving (default; tests may pass `scrub=`).
- Tests: emails, phones, cards, AWS / GitHub / Slack tokens, private keys, connection strings, password assignments and JWTs are masked; `PaymentService`, `retry_limit`, `PAY-1234`, commit SHAs, versions, URLs, `settings.api_key`, `get_token()` and people's names are untouched; an integration test proves nothing unscrubbed reaches `items`.

**Key files**
- `backend/app/learning/scrub.py`, `backend/tests/test_scrub.py`; deps `presidio-analyzer`, `presidio-anonymizer`, `spacy` 3.8 + `en_core_web_sm` (installed from the spaCy release wheel in `pyproject.toml`)

**Decisions**
- **Person names are not masked** (the product is "who built what"). Only the entity list above is analysed, so Presidio's other recognisers (PERSON, LOCATION, DATE_TIME, URL …) never fire.
- Unquoted secret values must be ≥ 8 chars, contain a digit and no `.`, `(`, `[`; quoted values ≥ 6 chars. That keeps code identifiers alive at the cost of missing unquoted digit-free passwords.
- `get_scrubber()` is cached; loading spaCy costs ~1 s once per process.

**How to run / test**
- `make test`

**Known issues / TODO**
- IP addresses are masked, including internal ones; relax if that hurts answers about infrastructure.
- No AWS secret-key detector without a `key=` prefix (40-char base64 looks like SHAs).

### Task 1.4 — Slack connector  ✅ done
**Date:** 2026-10-15

**Built**
- `SlackConnector(channel_id)` (`app/learning/connectors/slack.py`): `conversations.info` (skips `is_im` / `is_mpim` → DMs never stored), `conversations.history` (cursor paging; `oldest` = cursor − `SLACK_THREAD_LOOKBACK_DAYS`), `conversations.replies` for every thread parent that has new activity → **one `thread` item per thread** with replies in order (`slack:U1: text` lines, title = first line), standalone messages → `message`. Channel bookkeeping subtypes (`channel_join`, …) skipped; 429 → `retry-after`.
- Cursor = latest `ts` seen (messages and replies). Tag `slack:channel:<ID>` (membership).
- Settings `SLACK_BOT_TOKEN`, `SLACK_WORKSPACE_URL` (permalinks), `SLACK_API_URL`, `SLACK_THREAD_LOOKBACK_DAYS` (7).

**Key files**
- `backend/app/learning/connectors/slack.py`, `backend/tests/test_slack_connector.py`

**Decisions**
- Authors are Slack user ids (`slack:U0123`); display names are resolved later through identities (Tasks 4.1 / 5.1). Raw Slack markup (`<@U1>`, `<url|label>`) is kept.
- Bot messages are stored (scrubbed) and left for SetFit triage (Phase 2) to drop, as `description.md` specifies.
- A thread that gets new replies is re-emitted whole; the upsert replaces the stored text and resets it to `new`.

**How to run / test**
- `make test`

**Known issues / TODO**
- Replies added to threads older than the look-back window are missed until a full re-sync (clear the cursor).
- Links need `SLACK_WORKSPACE_URL`; without it `link` is empty.

### Task 1.3 — Jira connector  ✅ done
**Date:** 2026-10-15

**Built**
- `JiraConnector(project_key)` (`app/learning/connectors/jira.py`): Jira Cloud `GET /rest/api/3/search/jql` with `nextPageToken` paging and JQL `project = "KEY" [AND updated >= "<cursor>"] ORDER BY updated ASC`. JQL has no timezone syntax, so the bound is rendered in the API user's Jira timezone (`/rest/api/3/myself`).
- Issues → `issue` items (title = summary; text = `Type · Status · Assignee` header + flattened description). Comments from the search payload → `comment` items with `parent_external_id` = issue key. 429 → wait `retry-after`, retry.
- `adf_to_text()` flattens Atlassian Document Format (paragraphs, headings, lists, code, mentions).
- Cursor = latest `updated` in UTC (`%Y-%m-%dT%H:%M:%S.%f%z`). Tag: `jira:project:<KEY>`.
- Settings `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (basic auth).

**Key files**
- `backend/app/learning/connectors/jira.py`, `backend/tests/test_jira_connector.py`

**Decisions**
- Item ids: issue key (`PAY-12`), `comment:<id>`; author `jira:<accountId>`; link `<base>/browse/<key>`.
- Same test pattern as GitHub: `transport=httpx.MockTransport(fake)` and `sleep=` injected.

**How to run / test**
- `make test`

**Known issues / TODO**
- Comments come from the search payload (Jira caps them per issue); very long comment threads need `/issue/{key}/comment` paging later.
- The minute-precision JQL bound re-fetches the last minute each run (deduped by content hash).

### Task 1.2 — GitHub connector  ✅ done
**Date:** 2026-10-15

**Built**
- `GitHubConnector(repo)` (`app/learning/connectors/github.py`): issues + PRs (`/issues?state=all&sort=updated&since=`), PR reviews (`/pulls/{n}/reviews`; approved / changes-requested or with a body), issue and PR conversation comments (`/issues/comments`), inline review comments (`/pulls/comments`), commits (`/commits?since=`).
- `Link`-header paging; primary and secondary rate limits (403/429 with `x-ratelimit-remaining: 0` or `retry-after`) wait (≤ 15 min, injectable `sleep`) and retry.
- Cursor = latest `updated_at` seen (`YYYY-MM-DDTHH:MM:SSZ`), passed back as `since`.
- Permissions: private repo → `github:repo:<owner/repo>`; public → `public` + the repo tag.
- Settings `GITHUB_TOKEN`, `GITHUB_API_URL`.

**Key files**
- `backend/app/learning/connectors/github.py`, `backend/tests/test_github_connector.py`

**Decisions**
- Item ids: `#<number>` (issue or PR; GitHub numbers are shared), `review:<id>`, `comment:<id>`, `review_comment:<id>`, commit sha. Comments and reviews point at `#<number>`.
- Review items read `approved: LGTM` (state + body); inline review comments carry the file path as `title`.
- Connectors take `transport=` (httpx.MockTransport) and `sleep=` so tests never touch the network or wait.

**How to run / test**
- `make test`

**Known issues / TODO**
- One `/pulls/{n}/reviews` call per updated PR (N+1); acceptable at the 15-minute cadence.

### Task 1.1 — Connector interface  ✅ done
**Date:** 2026-10-15

**Built**
- `RawItem` (pydantic, frozen): `external_id`, `type` (`ItemType` literal), `text`, `title`, `author`, `created_at`, `updated_at`, `link`, `parent_external_id`, `access_tags` (**required and non-empty**: an item nobody may see is rejected, fail closed); `content_hash()`.
- `Connector` protocol: `fetch_new(since_cursor) -> (items, next_cursor)`.
- `save_items(session, source, items, next_cursor)`: batched upsert on `(source_id, external_id)`; unchanged items (same content hash) are skipped, changed ones are updated and reset to status `new`; duplicates inside one batch collapse; cursor, `last_synced_at` and `last_error` updated; **one commit**. `sync_source(session, source, connector)` = fetch → save.
- Shared DB test fixtures in `tests/conftest.py`: `migrated_db` (session-scoped, migrated test DB) and `db_session` (truncates every table after the test). `tests/fakes.py`: `FakeConnector`, `item()`.

**Key files**
- `backend/app/learning/connectors/base.py` — `RawItem`, `Connector`
- `backend/app/learning/sync.py` — `save_items`, `sync_source`
- `backend/tests/test_sync.py`, `backend/tests/fakes.py`, `backend/tests/conftest.py`

**Decisions**
- Connectors are pure fetchers (no DB access); `sync.py` owns persistence. The cursor is an opaque string per source.
- Conventions: `author` = `kind:<id>` (`github:alice`, `jira:<accountId>`, `slack:U0123`); `external_id` = GitHub `#<number>` for issues **and** PRs (shared numbering), `comment:<id>`, `review:<id>`, commit sha; Jira issue key / `comment:<id>`; Slack `ts`. `parent_external_id` points at the PR / issue / thread.
- Access tags: `public`, `github:repo:<owner/repo>`, `jira:project:<KEY>`, `slack:channel:<ID>`. Task 6.1 filters with these.
- DB tests use the `db_session` fixture (commits allowed, tables truncated afterwards); never add per-test migration fixtures.

**How to run / test**
- `make test`

**Known issues / TODO**
- none

### Task 0.6 — Background job runner  ✅ done
**Date:** 2026-10-15

**Built**
- `app/jobs/scheduler.py`: APScheduler `BlockingScheduler`; `build_scheduler()` registers the dummy `heartbeat` job on an interval of `SYNC_INTERVAL_MINUTES` (runs once at startup, then every interval; `max_instances=1`, `coalesce=True` so runs never overlap). `make worker` starts it.
- Tests: the interval comes from config (and changes with the env), and a started worker fires the job and logs `heartbeat: worker alive`.

**Key files**
- `backend/app/jobs/scheduler.py`, `backend/tests/test_jobs.py`, `Makefile` target `worker`

**Decisions**
- **APScheduler 3 in-process, no Celery / broker.** One database is the rule; the `items.status` column is the work queue. Jobs are plain functions registered in `build_scheduler()`; Task 1.6 adds `sync_all_sources` there.
- The worker is a separate process from the API (`make worker` vs `make run`).

**How to run / test**
- `make worker` (Ctrl-C to stop) · `make test`

**Known issues / TODO**
- Single worker process, no persisted job state. Fine while jobs are idempotent and re-run on the interval.

### Task 0.5 — Model gateway  ✅ done
**Date:** 2026-10-15

**Built**
- `app/models/gateway.py`: `OllamaClient` (`generate`, `generate_json`, `stream`; JSON mode via Ollama `format`; timeout + retries from settings; Qwen3 thinking off by default), `ollama()` cached client, `device()` (cuda > mps > cpu, or `DEVICE` setting), cached `load_sentence_transformer(role)` / `load_cross_encoder(role)`, helpers `embed(role, texts)` (normalised) and `rerank(role, query, candidates)`.
- Every call logs `model=<name> took=<ms> prompt_tokens=… tokens=…` (Ollama) or `items=…` (HF) on logger `syncra.models`.
- `app/models/download.py` + `scripts/download_hf_models.py` (`make download-models`): downloads every `runtime: huggingface` model once; gated models are skipped with a warning unless `HF_TOKEN` is set.
- Tests: mocked Ollama (`httpx.MockTransport`) for generate / JSON / retry / stream; real tiny HF model (`all-MiniLM-L6-v2`, cached) loaded once and embedding; download logic with a fake downloader.

**Key files**
- `backend/app/models/gateway.py`, `backend/app/models/download.py`, `backend/scripts/download_hf_models.py`, `backend/tests/test_gateway.py`

**Decisions**
- Call models by **role**: `ollama().generate("answer_writer", prompt)`, `embed("embedder", texts)`, `rerank("reranker", q, docs)`. Never import `sentence_transformers` or call Ollama outside `app/models/`.
- Ollama requests set `think: false` (Qwen3) unless `think=True` is passed; JSON mode = `json_mode=True` or a JSON-schema dict.
- `stream()` retries only before the first token; `generate()` retries `retries` times (default 2) on HTTP / bad-JSON errors, then raises `OllamaError`.
- New loaders for other model types (GLiNER, SetFit, transformers pipelines) go in `gateway.py` as `@lru_cache` functions taking a role.
- `DEVICE=auto` picks the GPU (`mps` on Apple Silicon); set `DEVICE=cpu` if a model misbehaves on MPS.
- `httpx` is a runtime dependency now (Ollama client; connectors will reuse it).

**How to run / test**
- `make download-models` · `make test` (the HF test takes ~5 s after the first run)

**Known issues / TODO**
- `meta-llama/Llama-Prompt-Guard-2-86M` is gated: accept the licence on Hugging Face and set `HF_TOKEN` before Task 5.4.
- First `make test` after install is slow (~1 min) while torch / the model warm up.

### Task 0.4 — Database schema and migrations  ✅ done
**Date:** 2026-10-15

**Built**
- SQLAlchemy 2 ORM (`app/db/schema.py`) + Alembic migration `0001_initial_schema` creating: `users`, `user_source_identities`, `sources`, `sync_cursors`, `items`, `chunks` (`vector(1024)` + generated `tsv`), `entities`, `entity_aliases`, `edges`, `decisions`, `chat_sessions`, `chat_messages`, `actions`.
- Indexes: **HNSW** (`vector_cosine_ops`, m=16, ef_construction=64) on `chunks.vector`, **GIN** on `chunks.tsv` and `items.access_tags`, plus lookup indexes on status / edges / aliases.
- `app/db/engine.py`: `get_engine()` (cached), `new_session()`, `get_db()` FastAPI dependency.
- Test: downgrade → upgrade → insert and read one row in every table → cosine + full-text queries → downgrade (nothing left but `alembic_version`).
- Dev database migrated (`make migrate`).

**Key files**
- `backend/app/db/schema.py` — ORM models + allowed-value tuples (`ITEM_TYPES`, `ITEM_STATUSES`, `ENTITY_TYPES`, …)
- `backend/app/db/engine.py` — engine/session helpers
- `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial_schema.py`
- `backend/tests/test_db_schema.py`

**Decisions**
- Migrations live in `backend/migrations/` (not `alembic/`, which shadows the `alembic` package). Write them **by hand** with explicit column types on FK columns; the vector dim comes from `get_settings().embedding_dim`.
- `items.access_tags text[]` is the permission model: tags like `github:repo:org/x`, `jira:project:PAY`, `slack:channel:C123`, `public`. Task 6.1 filters with `access_tags && user_tags` inside the query.
- `items.status` (`new` → `processed` | `noise` | `failed`) is the Phase 2 work queue; no broker needed.
- `chunks.tsv` is a stored generated column (`to_tsvector('english', text)`), so the keyword index needs no app code.
- `edges` is polymorphic: `(src_type, src_id) -relation-> (dst_type, dst_id)` over node types `entity | item | chunk | decision` with optional `item_id` evidence; unique on the 5-tuple so re-runs don't duplicate.
- Authors / identities are strings like `github:alice`, `slack:U123`, `jira:<accountId>`; `user_source_identities` links them to Syncra users.
- Sessions: sync SQLAlchemy (`psycopg` 3), `expire_on_commit=False`.
- Tests that need the DB use the module-scoped `migrated` fixture + a per-test `session` that rolls back.

**How to run / test**
- `make migrate` (dev DB) · `make test` (uses `syncra_test`, leaves it empty)

**Known issues / TODO**
- SQLAlchemy 2.1 got installed (pin is `>=2.0`); no problems so far.

### Task 0.2 — Local services with Docker  ✅ done
**Date:** 2026-10-15

**Built**
- **Production** Docker setup (user decision: **no Docker for local development**): `backend/Dockerfile` (multi-stage, non-root, CPU torch by default, healthcheck) and `backend/docker-compose.yml` with `postgres` (`pgvector/pgvector:pg17`), `ollama` (`0.35.0`), `api` (runs migrations, then uvicorn) and `worker`. Named volumes for Postgres data, Ollama models and the Hugging Face cache.
- Local development uses the developer's **own PostgreSQL + pgvector** (dev machine: Homebrew PostgreSQL 18 on port **5434**) and **native Ollama**. `make db-init` (`scripts/init_local_db.py`) creates the `syncra` and `syncra_test` databases and enables `vector`.
- `backend/scripts/pull_ollama_models.py` (`make pull-models`): pulls every `runtime: ollama` model in `config/models.yaml` (qwen3:4b, qwen3:8b; both pulled on the dev machine). Test drives it with a fake `ollama` binary on PATH.
- `backend/.env.example` lists every setting; `backend/.env` is the local copy (gitignored).

**Key files**
- `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-compose.yml`, `backend/scripts/init_db.sql` (compose first start: enables `vector`), `backend/scripts/init_local_db.py`, `backend/scripts/pull_ollama_models.py`, `backend/.env.example`, `backend/tests/test_pull_ollama_models.py`

**Decisions**
- **Do not start Docker locally.** Dev = local Postgres + native Ollama; Docker = production only. The compose Postgres was verified once (Postgres 17 + pgvector 0.8.7 came up with the extension enabled) and torn down; the image build has not been run.
- Compose project name is pinned (`name: syncra`); the default (folder name `backend`) collided with another project's containers on the dev machine.
- In containers the API / worker get `DATABASE_URL` and `OLLAMA_BASE_URL` pointing at the `postgres` / `ollama` services (set in compose), `DEVICE=cpu`, `HF_HOME=/models`.
- DBeaver (local dev): host `localhost`, port `5434`, db `syncra`, user = macOS user, no password. Tests use `syncra_test` on the same server (derived by `conftest.py`, not in `.env`).

**How to run / test**
- Local: `make db-init && make migrate && make pull-models && make download-models && make test`
- Production: README section "Production (Docker)".

**Known issues / TODO**
- `docker compose build` has not been exercised (no local Docker by decision); the first production deploy must build and smoke-test the image.
- Ollama image tag `0.35.0` is assumed to exist on Docker Hub (matches the local version); bump if it does not.

### Task 0.3 — Configuration  ✅ done
**Date:** 2026-10-15

**Built**
- `Settings` (pydantic-settings) loads `backend/.env` + environment; `get_settings()` raises `ConfigError` naming every missing/invalid field.
- `config/models.yaml` lists every model from `description.md` §8 by **role**; `get_models_config()["answer_writer"]` returns a `ModelSpec(runtime, name, revision, gated)`.
- API lifespan calls both loaders, so bad config fails at startup with a clear message.
- Tests: env override changes values, missing `DATABASE_URL` fails clearly, every role present, bad yaml rejected.

**Key files**
- `backend/app/config/settings.py` — `Settings`, `ModelSpec`, `ModelsConfig`, `get_settings()`, `get_models_config()`, `ConfigError`
- `backend/config/models.yaml` — model roles
- `backend/tests/conftest.py` — forces `DATABASE_URL` to the test DB for every test run
- `backend/tests/test_settings.py`

**Decisions**
- Key numbers are settings: `SYNC_INTERVAL_MINUTES=15`, `CHAT_MEMORY_TURNS=10`, `TOP_K_EVIDENCE=8`, `EMBEDDING_DIM=1024`. Read them via `get_settings()`, never hard-code.
- Models are addressed by role name (`entity_finder`, `decision_reader`, `embedder`, `entity_linker`, `triage_base`, `presidio_nlp`, `question_rewriter`, `prompt_guard`, `intent_router_base`, `reranker`, `answer_writer`, `claim_checker`). Change models in yaml, not code.
- Ollama entries use the full tag as `name` (`qwen3:8b`); Hugging Face entries use the repo id, optional `revision`, `gated: true` when a token is needed.
- Env vars beat `.env`; empty env values are ignored. Only `DATABASE_URL` is required.
- Tests never touch the dev DB: `conftest.py` sets `DATABASE_URL` to `<dev db>_test` on the same server (e.g. `syncra_test`) and creates it if missing. No test settings in `.env`, README or user docs — testing is agent-only (user decision 2026-10-15).

**How to run / test**
- `cd backend && make test`

**Known issues / TODO**
- none

### Task 0.1 — Project skeleton  ✅ done
**Date:** 2026-10-15

**Built**
- Python project in **`backend/`**: `pyproject.toml`, `Makefile`; `.gitignore` and `README.md` at the repo root.
- FastAPI app with `GET /health` → `{"status": "ok"}` and a test for it.
- Package layout `backend/app/{api,learning,chat,models,db,jobs,config}` plus `backend/config/` (yaml), `backend/scripts/`, `backend/tests/`.
- The old empty scaffold (125 zero-byte files) in `backend/` was deleted.

**Key files**
- `backend/pyproject.toml` — deps (`fastapi`, `uvicorn`), dev deps (`pytest`, `httpx`, `ruff`), ruff + pytest config
- `backend/Makefile` — `make install` / `make run` / `make test` / `make lint` / `make fmt`
- `backend/app/api/main.py` — FastAPI app
- `backend/tests/test_health.py` — health test

**Decisions**
- **Python 3.12** via `python3.12 -m venv .venv` + pip (no uv/poetry). Override with `make install PYTHON=python3.11`.
- **Layout:** `app/api` (web API), `app/learning` (learning pipeline), `app/chat` (chatbot pipeline), `app/models` (model gateway), `app/db` (database), `app/jobs` (background jobs), `app/config` (settings code), `config/` (yaml + prompts), `scripts/`, `tests/` — all under `backend/`. `frontend/` is for the web app (Phase 9).
- Package is named `app` (as in the FastAPI docs layout); imports look like `from app.api.main import app`.
- **Linter + formatter:** ruff. **Tests:** pytest (`tests/` is a package, tests import `app` from the editable install).

**How to run / test**
- `cd backend && make install && make test && make lint`; `make run` then `curl localhost:8000/health`.

**Known issues / TODO**
- Starlette's TestClient warns that `httpx` is deprecated in favour of `httpx2`; harmless, revisit when `httpx2` is stable.
