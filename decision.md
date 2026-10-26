# Syncra — Decisions

This file explains the choices made while building Syncra so far (Phases 0–4). For each one it says what was picked, what else was possible, and why this option won.

Code-level details are in [`progress.md`](progress.md), and how the parts work together is in [`flow.md`](flow.md).

---

## Where the decisions came from

**The architecture was yours.** The tools in your diagrams were given: Presidio, SetFit, GLiNER, Qwen3 on Ollama, Qwen3-Embedding, SBERT, Prompt Guard 2, a cross-encoder, DeBERTa, and PostgreSQL with pgvector. So were the key numbers (15 minutes, 1024 dimensions, HNSW, 10 turns, best 8, high / medium / low). `agent.md` forbids swapping any of them without asking, so nothing below replaces them.

**Some calls during the build were yours too.** No Docker on your machine, all backend code in `backend/`, and tests kept out of the setup docs because they're for the coding agents. Tokens are shared separately instead of being written into `guide.md`, and `requirements.txt` exists because you asked for it.

**Everything else was decided by the coding agents** while building each task. Those decisions follow, grouped by the part of the system they belong to, roughly in build order.

---

## 1. Planning the build

**51 small tasks in 11 phases (0–10), each with "Depends on", "Build" and "Done when".** One big spec would have been quicker to write, but one Claude Code session can't build it all, and you couldn't check it piece by piece. A small task can be built in one session and checked against a clear list.

**`agent.md` and `progress.md` as the hand-over between sessions.** Every new session starts with no memory, so it reads how to work (`agent.md`) and what was already built and why (`progress.md`). Each log entry has a "Decisions" section, which is where most of this file comes from.

**The plan left the web framework, the job runner and the frontend framework open**, for the first tasks to pick once there was code to pick them for. The choices made are in sections 2 and 7; the frontend is still open (Phase 9).

**A few things your diagrams didn't show were added to the plan.** User login and linked accounts (Task 5.1), because "only search what the user may see" needs to know who is asking. Labelled training examples for both SetFit classifiers, because they can't learn without them. The 90% accuracy and "first word in under 3 seconds" targets are guesses, to be replaced by real numbers.

---

## 2. Language, tools and project layout

**Python 3.12, installed with pip into a plain virtual environment.** The AI libraries Syncra needs (PyTorch, transformers, spaCy, Presidio) are Python-first, and 3.12 was on your Mac and supported by all of them. uv or Poetry would have been faster or tidier, but neither was installed, and every extra tool is one more setup step for your friends.

**FastAPI for the web API, instead of Flask or Django.** It checks requests and responses with pydantic, which Syncra already uses for settings and items, and it has async and streaming built in for word-by-word answers. Django would bring its own database layer and admin that compete with SQLAlchemy, and Flask would need add-ons for validation and async.

**The API documentation is FastAPI's own Swagger page**, at `/docs` (and ReDoc at `/redoc`). It is generated from the code: each endpoint's group, one-line summary, request and response models, and its error codes. A hand-written `swagger.yaml` would drift from the code, and a separate docs tool would be one more package. A test fails if an endpoint returns an undocumented shape or forgets its login check in the docs. Like before, the page is off in production.

**All backend code in `backend/`, as one package called `app`.** The first version was built at the repo root, because deleting the old empty scaffold (125 zero-byte files) was blocked at first. When you asked for everything in `backend/`, the scaffold was removed and the code moved in.

**The package is split by job:** `api`, `learning`, `chat`, `models`, `db`, `jobs` and `config`, with the yaml files in `backend/config/`. `app` is the name the FastAPI docs use, so imports read `from app.main import app`.

**A Makefile for every command.** `make install`, `make run`, `make worker`, `make migrate` and the rest call the virtual environment's programs directly, so nobody has to activate it or remember long commands. `make` comes with Apple's command line tools, which Homebrew installs anyway, and with most Linux setups.

**ruff as the only linter and formatter.** One fast tool replaces flake8, black and isort, with a single config in `pyproject.toml`.

**`requirements.txt` kept next to `pyproject.toml`.** You asked for a plain list of what to install, models included. `pyproject.toml` stays the source of truth (`make install` uses it), so a package added there must be added to `requirements.txt` too.

---

## 3. Your machine vs production

**Locally, Syncra uses your own Postgres and Ollama, not Docker.** That was your rule after the first Docker attempt, and it keeps the local setup light. Syncra uses the Homebrew PostgreSQL 18 that already ran on port 5434 with pgvector, plus the Ollama app. `make db-init` creates the database and turns on pgvector, so nobody has to do it by hand.

**Docker is kept for production only.** `backend/Dockerfile` and `docker-compose.yml` run Postgres, Ollama, the API and the worker on one Linux server. The image is built in two stages and runs as a non-root user. It uses CPU-only PyTorch unless you build it with the GPU option, because the GPU build is gigabytes bigger.

**One API process in production.** Each process holds its own copy of the loaded models in memory, so four API processes would mean four copies of every model in RAM. One is enough until speed is measured in Task 10.4.

**The API container runs the migrations when it starts, and the worker waits until the API is healthy.** That way the tables always match the code before anything uses them. A separate migration step in the deploy would work too, but it's easy to forget.

**The compose project name is fixed to `syncra`.** Without it, Docker names the project after its folder (`backend`), which matched another project on your Mac and replaced that project's database container during the first attempt. Its data survived, and the fixed name stops this from happening again.

**Production images have fixed versions where possible.** `ollama/ollama:0.35.0` is an exact version, the same as your local Ollama, because a `latest` tag could change underneath you between two deploys. `pgvector/pgvector:pg17` fixes Postgres 17 but still moves with new pgvector releases; pinning its exact digest is still open (`security-audit.md` S-17).

---

## 4. Configuration

**One settings class (pydantic-settings) reads `.env` and the environment.** It converts values to the right types, and if something required is missing it stops at startup with one message naming every missing field. Only `DATABASE_URL` is required, so the app starts before any source tokens are added. Environment variables win over `.env`, which is what Docker needs.

**Models are listed by job ("role") in `config/models.yaml`.** The code asks for a role such as `answer_writer` and never names a model, so changing a model means editing that role's entry in the yaml (its name and, for Hugging Face models, its pinned revision). Model names in `.env` would mean a dozen more variables, and names in the code would break the "config, not constants" rule.

**The key numbers are settings, with your values as defaults.** 15 minutes, 10 turns and best 8 can be changed in `.env` without touching code. The 1024 can only change together with the embedder and a rebuilt `chunks` table, because the vector column is created at that size. Later tasks added the chunk size, the overlap and the decision reader's length limits the same way.

**Prompts live in versioned files** (`config/prompts/decision_reader.v1.yaml`), and models.yaml says which version each role uses. Changing the wording means adding a `v2` instead of editing `v1`, so the old version stays around to compare against. Prompts written as strings inside the Python code would mix wording changes with code changes.

**Bad configuration fails at startup.** The API loads the settings and the model list as it starts, so a typo shows up at once with a clear message instead of in the middle of a sync.

---

## 5. The database

**SQLAlchemy 2 for queries and Alembic for migrations.** This is the standard Python pairing: tables are described once in Python, and every schema change is a numbered migration that can be applied and undone. Raw SQL files would need hand-made versioning, and Django's ORM would mean using Django.

**Migrations are written by hand, not generated.** That gives exact control over the parts autogenerate handles poorly: turning on the pgvector extension, the HNSW and GIN indexes, and the generated keyword column. The folder is called `migrations/` because a folder named `alembic/` hid the `alembic` library from Python.

**Plain synchronous database code with psycopg 3, not async.** The slow part of Syncra is running models, not waiting for the database, so async database code would add complexity for little gain. psycopg 3 is the current Postgres driver and can switch to async later if the chat needs it.

**The whole schema was created at once in Task 0.4.** Tables for users, chat and actions exist already, although nothing writes to them yet, because that task asked for the full knowledge store up front. Changes since then are new migrations (so far only `0002`).

**Permissions are tags on each item.** Every item stores who may see it as a list such as `github:repo:acme/payments`, `jira:project:PAY`, `slack:channel:C123` or `public`, with an index on that list. Searches will keep only the items whose tags overlap the user's, inside the same SQL query.

**The other ways to do permissions were worse here.** A separate permissions table would add a join to every search. Postgres row-level security would hide the filter in database policies, which is harder to see and check than a plain condition in each query. Filtering after the search is what your design rules out, because the best 8 matches could all be hidden ones.

**The `items.status` column is the work queue.** New items arrive as `new`, and the pipeline moves each one to `processed`, `noise` or `failed`. A message broker like Redis or RabbitMQ is the usual tool for this, but it would be a second data store, which your "one database" rule forbids.

**The keyword index needs no code.** `chunks.tsv` is a column Postgres computes by itself from each chunk's text, with a GIN index on it, so it can never fall out of step with the text. A trigger or app code that fills it would be one more thing to get right.

**The knowledge graph is three plain tables: `entities`, `entity_aliases` and `edges`.** An edge links any two things (a person, an item, a chunk, a decision) by type and id. So one table holds every kind of link, and one query shape follows any of them.

**A graph database was ruled out.** Neo4j would be a second database, which your rule forbids, and Postgres's AGE graph extension would add its own query language (Cypher) for lookups that plain SQL joins already do. One table per kind of link would mean a new table for every new kind.

**The same link can't be stored twice.** `edges` is unique on (from, relation, to), so re-running anything can never create duplicate links.

**The vector index uses cosine distance and pgvector's default build settings** (`m=16`, `ef_construction=64`). HNSW was your choice, and cosine fits because the vectors are normalised. Tuning waits until there is real data to measure (Task 10.4).

---

## 6. Talking to the AI models

**One gateway file for every model call** (`app/ml/gateway.py`), as the plan asked. It is the only code that talks to Ollama or loads a Hugging Face model, and each call logs the model, the time it took and the token or item count. Changing how models run means changing one file.

**A small Ollama client of our own, instead of the `ollama` package or LangChain.** It is about 120 lines on top of httpx, the HTTP library the connectors use too, and gives exact control over timeouts, retries, JSON output and streaming. LangChain especially would be a big dependency for things Syncra doesn't use.

**Qwen3's "thinking" mode is off by default.** With thinking on, the decision reader was 5 to 10 times slower and no better, and JSON answers come out cleaner without it. A single call can still turn it on if a later task needs it.

**Normal and streamed answers retry differently.** A normal call retries twice when Ollama can't be reached or sends back an unreadable reply; a badly formed answer from the model itself is the caller's job (the decision reader retries it once). A streamed answer retries only if nothing was sent yet, because retrying after the first words would repeat text the user already saw.

**Hugging Face models are loaded once per process and kept in memory**, on the GPU when there is one (Apple's MPS on your Mac). A `DEVICE` setting forces the CPU if a model misbehaves on the GPU. Loading a model for every call would cost seconds each time.

**Models are downloaded ahead of time** with `make download-models`, so the worker never stalls on a download. The gated Prompt Guard model is skipped with a warning until a Hugging Face token is set.

---

## 7. The background worker

**APScheduler inside the worker, not Celery.** Celery needs a broker such as Redis or RabbitMQ, which would be a second data store next to Postgres. APScheduler is a plain library that runs the job every 15 minutes inside `make worker`, while the item statuses in Postgres do the queuing.

**Runs never overlap.** If a run is still going when the next one is due, that run is skipped (with a warning in the log) and the job tries again at the following 15-minute mark. Runs missed while the worker was paused collapse into one, and the first run starts as soon as the worker does, instead of 15 minutes later.

**The worker is a separate process from the API.** Learning keeps the CPU and GPU busy for seconds at a time, and that must not slow down chat answers. It also lets you stop the worker without stopping the API.

**APScheduler is held below version 4**, because version 4 is a rewrite with a different API.

---

## 8. Pulling data from GitHub, Jira and Slack

**Connectors only fetch; one shared module saves.** Each connector turns its tool's data into the same item format and hands it back, and `sync.py` alone writes to the database. Saving, de-duplication and cursor handling are written once instead of three times.

**Plain HTTP calls instead of the official SDKs.** One HTTP library (httpx) for all three tools means one way to handle timeouts, paging and rate limits. The SDKs (PyGithub, slack_sdk, the Jira client) would be three more dependencies, each with its own retry logic and data types.

**Every item must say who may see it.** An item without permission tags is rejected when it is created ("fail closed"), so a connector bug can't make something visible to everyone. GitHub items get the repo tag (plus `public` for public repos), Jira items the project tag, and Slack items the channel tag.

**Only new or changed items are fetched.** Each source keeps a cursor (the newest timestamp seen), saved in the same transaction as its items. If the worker crashes halfway, neither the items nor the cursor move, so nothing is skipped.

**Changes are spotted with a fingerprint.** Each item stores a hash of its type, title, text, author and link. On the next sync an unchanged item is skipped, and a changed one is updated and set back to `new` so it is learned again.

**People are stored by account id, not display name**: `github:alice`, `jira:<accountId>`, `slack:U0123`. Display names change and two people can share one, while account ids stay fixed. Readable names come later, from aliases and linked accounts.

**GitHub through its REST API.** One paged call to the `issues` endpoint returns issues and PRs together and accepts a `since` date. Reviews need one extra call per changed PR, which is fine every 15 minutes, and only reviews that approve, request changes or have text are kept. GraphQL could fetch everything in fewer calls, but needs much more query code.

**GitHub numbers issues and PRs together**, so both are stored as `#42`, and their comments and reviews point at that number.

**Jira through the newer `search/jql` endpoint.** JQL dates have no time zone, so the cursor is first converted into the Jira user's own time zone, and Jira's rich-text format is flattened to plain text. Comments come with the search results, which is fast but capped per issue (noted in `progress.md`).

**A whole Slack thread is one item**, with every reply as a `slack:U01: text` line in order. Decisions are made across a thread, so the decision reader and the search need all of it. Messages outside threads are single items.

**Slack looks back 7 days on every run**, because a new reply doesn't make an old thread show up as new in Slack's history. Threads with new replies are fetched again whole. Replies to threads older than that are missed until a full re-sync (noted).

**Direct messages are never fetched**, and channel housekeeping events (joins, topic changes) are skipped. Bot messages are stored and left for triage to drop, as your design says. They are recorded under the bot's id (`slack:B…`) so the triage rule can recognise them.

**Rate limits are respected.** When a tool says "slow down", the connector waits as long as it asks (at most 15 minutes) and tries again. After three attempts in all, it gives up until the next run.

**One broken source doesn't stop the others.** Its error is logged and saved in `sources.last_error`, and the next source runs. The stored error is ready for the sources screen in Task 9.4.

**Connecting a source means adding a row to `sources`**, until the settings screen exists (Task 9.4). Tokens stay in `.env`, one set per installation; per-source tokens can come with that screen.

---

## 9. Hiding private data

**Presidio runs on every item before it is saved**, so nothing reaches the database, the search index or a model unscrubbed. Scrubbing later, at search time, would mean the private data was already stored.

**People's names are not hidden.** "Who built X" is the product, so Presidio's name detector isn't used at all. It looks only for emails, phone numbers, card numbers, IBANs, US social security numbers and IP addresses.

**Secret detectors were added**, because Presidio doesn't look for tokens: AWS keys, GitHub and Slack tokens, private keys, connection strings with passwords, `password = …` assignments and JWTs. Each hit becomes a label such as `<SLACK_TOKEN>`, so the text stays readable and shows that something was removed.

**The password rule is strict so that code survives.** An unquoted value only counts as a secret if it is at least 8 characters long, contains a digit and has no `.`, `(` or `[`. That keeps `settings.api_key` and `get_token()` intact, at the cost of missing unquoted passwords without digits.

**Presidio runs on the small English spaCy model** (`en_core_web_sm`). What Syncra hides is found by patterns, not by spaCy's name finder, so a bigger spaCy model would only add load time.

**IP addresses are hidden, internal ones included.** This could hide useful infrastructure details; it's noted to relax if it hurts answers.

---

## 10. Dropping noise (triage)

**299 hand-written training examples** (151 useful, 148 noise) in `config/triage.yaml`, covering every item type from all three tools. There was no real labelled data yet. They include deliberate look-alikes, such as the review "approved: lgtm" (useful) next to a plain "LGTM" comment (noise).

**Reviews that approve or request changes are labelled useful in the examples**, even with no text, because they're the only record of who reviewed what. The classifier still makes the final call; there's no hard rule for them.

**Simple rules run before the model.** Empty items and anything written by a bot are noise without asking the model, which is cheaper. A thread started by a bot still goes to the model, because people may have replied in it. The cost: a PR opened by a bot (Dependabot, say) is dropped even if people discuss it, although their replies are still learned on their own.

**SetFit (from your design) was checked against a simpler option.** A plain classifier on unchanged sentence vectors scored 83.7% on the early data and SetFit 93.9%, so SetFit stayed.

**The configured MiniLM model as SetFit's base, after trying bigger ones.** bge-small did worse, and a larger mpnet model scored the same but trained five times slower. Every model tripped on the same hard examples, so the fix was better examples, not a bigger model.

**Five training pairs per example (`num_iterations=5`) instead of SetFit's default sampling.** On this data it was as accurate as the default, but trained in about 16 seconds instead of 150.

**Each machine trains its own copy.** `make train-triage` takes about 30 seconds, saves the model in `backend/models/` (outside git) and stops with an error below 90% accuracy (it reached 98.3%). Committing the 87 MB model would bloat the repo.

**SetFit's own loader is bypassed.** It ignores the pinned model version and contacts Hugging Face on every load. Syncra builds and loads the model itself, and classifying makes no network calls.

---

## 11. Cutting text into chunks

**Chunk size is counted in characters (1500, with 200 overlapping), not tokens.** Counting tokens would need a tokenizer loaded just for that. The embedder accepts about 32,000 tokens, far more than 1500 characters, so the size is set for search precision, not to fit the model.

**Slack messages and code blocks are kept whole** when they fit, and other text is cut at line breaks and sentence ends. A message or a code example cut in half is harder to find and to read, so the overlap is made of whole pieces too.

**A code block bigger than a chunk is cut between lines.** Otherwise one pasted 50 KB log would become a single giant chunk for the embedder and the answer prompt.

**The chunker doesn't touch the database.** In the database, a chunk's link, author, time and permissions stay on its item and are joined when needed, instead of being copied onto every chunk.

---

## 12. Finding entities

**The small GLiNER model** (`gliner_small-v2.1`), for speed on a laptop. It finds names well but sometimes mixes up services and tools, and tags odd words as people (`consumer`, `fyi`). A bigger GLiNER may do better; switching means updating the `entity_finder` and `entity_finder_encoder` entries in models.yaml, which is left for you to decide.

**Plain labels (`person`, `service`, `tool`, `project`) and GLiNER's default cut-off of 0.5.** Longer label wordings found nothing more, and lower cut-offs (0.3–0.4) added junk like `p99` as a project.

**Slack markup is cleaned before GLiNER reads it.** GLiNER read the `slack:U01:` line prefixes as a tool called "slack", so they're removed first. It also read `<@U03>` as a person called "U03", so it now sees only the mention's label, and the mention itself is recorded as the person `slack:U03`.

**GLiNER's tokenizer is pinned too.** GLiNER normally downloads its tokenizer from the moving `main` branch of another model repo, which would break the "every model pinned" rule. Syncra pins that repo and downloads only its 2.5 MB of tokenizer files, not its 850 MB of weights.

**Names are kept exactly as written** (`PaymentService`, `gRPC`). Merging different spellings is a separate step (section 15), so the original wording is never lost.

---

## 13. Reading decisions

**qwen3:8b reads decisions.** Your design says "Qwen3", and the 8B is the stronger of the two Qwen3 models in the plan. The learning pipeline runs in the background, so its extra time matters less than in chat, and since it also writes the answers, no third model has to be downloaded.

**It reads whole conversations, never single chunks.** A decision is usually proposed in one message and agreed to in another, so the reader gets the PR with its reviews and comments, or the whole Slack thread, in order.

**The answer is forced into JSON and then checked.** Ollama gets the exact JSON shape to fill in (decision, reason, people), and the reply is validated before use. Bad output is retried once and then dropped, so nothing is stored half-parsed, as your design requires.

**Very short conversations are skipped, and long ones are cut in the middle.** Under 60 characters is too short to hold a decision (the shortest real one in the examples is 68). Over 6000 characters, the middle is cut and the opening and the conclusion are kept, because Ollama gives qwen3:8b a 4096-token window and the prompt itself takes about 720 of it.

**The window wasn't made bigger instead.** Raising it would make Ollama reload the model whenever the worker and the chat ask for different window sizes, which costs seconds each time.

**The conversation is treated as quoted data, never as instructions.** It sits between `<thread>` tags (any such tags inside the text are removed), the rules say never to follow it, one example shows an injection being ignored, and the task is repeated after the data. Marking every line with `>` and Qwen3's thinking mode were tried too, and didn't help.

**Only people who wrote in the conversation can be named as deciders.** With the real model, 2 of 4 injection styles still produced a fake decision, so the code removes anyone from `people` who didn't post in that conversation. A planted message can at worst state a decision, which anyone could already do by simply posting it.

**One decision per conversation, the most important one.** That keeps storage simple; a thread that decides several things keeps only one (noted).

**"Dropped" and "failed" mean different things.** A bad answer twice means "no decision this time". Ollama being down is an error, so the conversation is marked failed and retried on the next run.

---

## 14. Making vectors (embeddings)

**Qwen3-Embedding-0.6B, the smallest Qwen3-Embedding model.** Its vectors are exactly 1024 numbers long, the size your design fixes. The 4B and 8B versions make longer ones (2560 and 4096) and run several times slower on a laptop.

**Chunks are embedded as plain documents; questions will get the model's search instruction.** Qwen3-Embedding is trained that way: the question side gets a short instruction and documents don't. Task 6.2 has to add that for questions.

**Vectors are normalised and their size is checked.** Every vector has length 1, so similarity is a simple dot product. A vector of the wrong size fails its conversation with a clear message before anything is stored (the conversation is rolled back and marked `failed`), instead of failing inside Postgres.

**The model runs in bf16**, the number format it is stored in. That's fine on your Mac's GPU but may be slow on a server CPU without bf16 support; Task 10.4 measures it and can switch to float32.

---

## 15. Linking names to one entity

**Names are normalised before any AI is used.** `PaymentService`, `payment-service` and `payments-svc` all become the key `paymentservice`: the words are split and lower-cased, `svc` / `k8s` / `db` are spelled out, and a plural `s` is dropped. Two names with the same key are the same thing.

**This does most of the work, because SBERT is weak on short names.** Measured on the configured model, `payments svc` and `payment service` scored only 0.59. Different things scored higher: `payment service` and `billing service` 0.79, `frontend` and `backend` 0.82.

**SBERT is a second chance, with a high bar of 0.9.** It catches variants like `payment processing service` and `payment service` (0.92), while keeping apart `internal api` and `external api` (0.86), or `payment provider` and `payment service` (0.84).

**False merges are worse than missed ones.** Merging two different things mixes up their people and decisions, while a missed merge only leaves a duplicate. So the bar stays high, even though `postgres` and `postgresql` (0.899) then stay separate.

**Names with different numbers never merge.** `billing v1` and `billing v2` scored 0.90, as high as real variants, so the numbers have to match before SBERT is even asked.

**People are never merged by similarity.** Two different people can have very similar names, and merging them would credit one person's work to the other. People merge only on an exact name key or through their accounts.

**Services, tools and projects can merge with each other.** GLiNER calls RabbitMQ a service in one place and a tool in another, so one name across those three types is one entity, and the first type seen wins. A project and a person with the same name stay separate.

**Accounts from different tools are joined only through Syncra users.** `github:alice` and `slack:U01` become one person only when a user links both accounts (Task 5.1). That user's display name then also pulls in any person known only by that name. Guessing across tools from display names alone could merge two different people.

**The oldest entity survives a merge** and takes over the other's aliases and links. A bug turned up here: the merge rewrites rows directly in SQL, which left already-loaded data stale, so the session is now refreshed after every merge.

**SBERT vectors of names are cached for the whole process**, and the known names are loaded once per conversation. That is fine for thousands of names; storing keys and vectors in the database is the upgrade if it ever reaches tens of thousands.

---

## 16. Writing the knowledge graph

**A conversation's old links and decision are deleted, then the new ones are written.** Comparing old and new links one by one would be more code and leave more room for stale links. Delete-then-write means a re-run never leaves duplicates or stale links, and a re-read decision simply replaces the old one.

**Every link remembers the item it was learned from.** That makes "forget what this item said" a single delete. Migration `0002` also makes links disappear with their item; before it, deleting a source left its links behind.

**Link directions are fixed:** person → item (authored, reviewed), chunk → entity (mentions), person → decision (decided) and decision → entity (about). Graph search (Task 6.4) will follow them both ways.

**"About" links come from the names in the decision's text**, matched by key against the entities found in that conversation, not from another model call. It's free and exact, but only works if GLiNER found the entity somewhere in the conversation (noted).

**`owns` and `depends_on` aren't written yet.** Nothing extracts them: GLiNER finds names, not relationships, and the decision reader returns only the decision, the reason and the people. Guessing them would put wrong facts into the graph.

**Bots never become people**, and a PR author's own review comments don't count as reviewing their own PR.

**`decisions.people` stores account ids**, the same ids the `decided` links point at, so the two can't disagree. Readable names come from aliases.

---

## 17. Search indexes

**Saving a chunk is indexing it.** The vector index and the keyword index both exist since the first migration, so a stored chunk with its vector is searchable at once. Both searches were confirmed to go through their index rather than reading the whole table.

**An item's chunks are always replaced as a whole.** That keeps re-learning simple, but chunk ids change each time. So nothing may keep a chunk id long-term: graph links are rewritten in the same step, and chat history (Phase 7) must store links and text instead.

**No index tuning yet.** pgvector's defaults stay until there is real data to measure (Task 10.4).

**Keyword search uses Postgres's English rules**, which split words and cut them down to their stem, so "refunds" finds "refund". Ticket ids like `PAY-1234` still match exactly, but `retry_limit` also matches "retry limits"; Task 6.3 decides whether that's good enough.

---

## 18. Running the whole pipeline

**The unit of work is a conversation**: a PR, issue, Slack thread or message (or a commit) with its replies. When any part of it is new, the whole conversation is learned again, which is the simplest way to keep decisions right because they need the whole thread. The cost is that an active PR's older comments are processed again.

**Each conversation is its own transaction.** If one fails, for example because Ollama is down, only that conversation is undone and marked `failed`; the rest are saved, and failed ones are retried on the next run. One transaction for the whole run would lose everything on a single error, and one per item can't work because decisions need the whole thread.

**Models get their work in batches.** Triage classifies all new items in one call, and GLiNER and the embedder take one conversation's chunks per call. Conversations aren't batched together, because the decision reader's LLM call takes most of the time anyway.

**Items that turn into noise are forgotten.** An edit can turn a useful message into "+1", so its chunks, links and decision are deleted.

**People are merged at the end of every run**, so accounts linked since the last run are picked up without a separate job.

**A failing conversation is retried on every run, with no limit yet.** Counting attempts is the upgrade if one keeps failing, since each retry can cost an LLM call.

---

## 19. Security

**Source ids are checked against strict patterns before any sync** (`owner/repo`, a Jira key, a Slack channel id). Otherwise a crafted Jira key could pull another project's tickets under the wrong permissions, and a crafted repo like `../user` could read every repo the token can see.

**The GitHub token never leaves GitHub's API address.** If a paging link ever points at another host, the sync stops instead of following it.

**Every API response gets security headers and a strict content policy** (except the local `/docs` page, which loads Swagger from a CDN). Errors return only "Internal server error" with an id to quote, and the details go to the server log. This was in place before any real endpoint, so new endpoints get it for free.

**The interactive API docs (`/docs`) are off unless switched on.** `.env.example` turns them on for local use, and production forces them off.

**In production, the API and the database listen only on the server itself.** The API has no login yet, so it must stay behind a TLS proxy and private until auth exists (Phase 9).

**Every Hugging Face model downloaded so far is pinned to an exact commit**, so a change pushed to a model's repository can't silently swap the weights Syncra runs. Prompt Guard 2 gets its pin when it's first downloaded, and the Ollama models are pinned by version tag.

**The fake Slack token used to check the scrubber is split in two**, so the code never holds a whole one. GitHub's push protection had blocked a push because of it, and the local history was rewritten to remove the whole token (nothing was pushed).

**`security.md` got an extra AI section** covering prompt injection through synced messages, permission leaks in search, scrubbing before embedding, approval for actions and pinned models. The generic prompts you combined didn't cover the risks specific to an AI chatbot.

---

## 20. Users and login

**Local accounts with a password, as Task 5.1 asks.** Company sign-in (Google, Okta or GitHub) is still yours to pick for Phase 9. It would sit in front of the same tokens: after the sign-in callback, Syncra hands out a token exactly as the password login does.

**Passwords are hashed with scrypt from Python's standard library.** It is one of the three hashes `security.md` accepts (with bcrypt and argon2), so no extra package is needed. The settings are OWASP's minimum (16 MiB of memory per hash), and one check takes about 0.16 seconds, which makes guessing slow. The settings are stored with each hash, so they can be raised later without breaking old passwords.

**A login is a random token kept in Postgres, not a signed JWT.** The database stores only its SHA-256, so a copy of the database holds no usable logins. Logging out deletes the row and expiry is a timestamp, with no signing secret to manage. A JWT can't be revoked before it expires without keeping a list in the database anyway.

**Tokens expire after 12 hours** (`TOKEN_TTL_HOURS`), about a working day. Expired ones are deleted whenever someone logs in, so no cleanup job is needed.

**A wrong password and an unknown username get the same answer, after the same work.** Otherwise the reply or its timing would tell an attacker which usernames exist.

**Only admins link GitHub, Jira and Slack accounts to users (your call).** From Phase 6 those accounts decide what a user may search, so letting users claim accounts themselves would let anyone claim a colleague's Slack account and read their private channels. Users see their own links. Self-service linking with a real sign-in to each tool can come with the Phase 9 settings screen.

**Admin work is two commands for now**, `make add-user` and `make link-account`, the same way connecting a source is one SQL row. Admin endpoints would need an admin role check and more to secure, for a job done a handful of times. The password is typed at a hidden prompt, never as a command argument, so it can't end up in the shell history.

**Every endpoint except `/health` and the login itself needs a token.** A test asks every endpoint in the API's own list without a token, with a made-up one and with a malformed header, so a new endpoint that forgets the login check fails the tests.

**No login rate limit in the app yet.** `security-audit.md` puts it on the reverse proxy for Phase 9 (5 tries a minute per address), and until then the API listens only on the machine itself.

---

## 21. The chat

**A user only ever sees their own chats.** Every chat lookup includes the user, and someone else's chat answers "not found", exactly like a chat that doesn't exist, so chat ids can't be probed.

**A turn is one user message and the replies after it**, and the chat remembers the last 10 (`CHAT_MEMORY_TURNS`). Counting messages instead would drift whenever a reply is missing, for example after an error, while a question without an answer still counts as a turn.

**Messages are ordered by their id, not their time.** Two messages saved in one database transaction get the same timestamp, so time alone can't tell which came first.

**The chat list shows the most recently used chat first.** Saving a message marks its chat as used.

**The question rewriter answers in a fixed JSON shape, at temperature 0.** With Ollama's plain JSON mode, qwen3:4b often answered with a different shape (it echoed the history back); with the exact shape it was right on every smoke test. At its default randomness it sometimes reworded the same follow-up differently and once garbled a word ("didn't" became "didn:"); at temperature 0 the answers were stable. The temperature lives in `models.yaml` as an `options` entry of the role, which any Ollama role can now use.

**Only the newest 4000 characters of the chat go to the rewriter** (`REWRITER_MAX_CHARS`). Ollama gives qwen3:4b a 4096-token window, and ten turns of long answers would not fit; the last turns are what a follow-up refers to.

**If the rewriter fails, the message is used as it is**, with a warning in the log. The user is waiting, so there is no retry, and searching for "who reviewed it?" literally is better than an error. The decision reader is different: it runs in the background, so it retries or waits for the next run.

**Small talk gets a canned reply, chosen by a few keywords.** "thanks" gets "You're welcome!", "bye" a goodbye, "what can you do?" a short explanation and a greeting a greeting. There is no search and no LLM, so the reply takes milliseconds, as your design asks; writing it with the LLM would make "thanks" wait a second or more.

**The intent router learned from 321 hand-written messages**, with look-alikes on purpose: "how do I open a ticket?" is a question but "open a ticket for it" is an action, and a bare "PAY-1234" is a question. It scored 98.5% on the messages held back from training, and got all 35 messages written afterwards right.

**It trains with 20 example pairs per message instead of triage's 5.** Over six different splits it averaged 97% with 20 and 92% with 5, as good as a five times bigger model. Triage didn't gain from more pairs; telling "how do I open a ticket?" from "open a ticket" does. The number is set per classifier in `models.yaml`.

**No "when unsure, call it a question" rule.** Sending the router's unsure answers to the question path fixed as many messages as it broke, so it was dropped.

**Both classifiers are trained the same way**: `make train-triage` and `make train-intent-router` run one script, which trains on 80% of the examples and reports the accuracy on the other 20%.

**The chat history is quoted data for the rewriter**, between tags it can't close, like the decision reader's threads. An answer in the history may quote a planted Slack message, and the rewriter must not follow it.

---

## 22. Chat-side models

**Where your design names only a kind of model, the usual small version of it was picked.** All of them are built and tested now, except Prompt Guard 2, which waits for the Hugging Face token.

**qwen3:4b rewrites follow-up questions, as your design says.** It runs on every follow-up message, and the smaller model keeps those replies fast.

**Llama Prompt Guard 2, the 86M version** rather than the 22M one, for better detection. Meta gates it, so it needs a Hugging Face token.

**`cross-encoder/ms-marco-MiniLM-L-6-v2` reranks the evidence.** It's the standard small search reranker for sentence-transformers, fast enough to score many matches for every question.

**`cross-encoder/nli-deberta-v3-base` checks the claims.** It's a DeBERTa model trained to tell whether a sentence follows from a passage, which is exactly the check your design describes.

**The intent router will use the same MiniLM base as triage**, so it can reuse the training code from Task 2.2.

---

## 23. Finding evidence

**Each source remembers who may see it.** Every sync stores the source's members: Slack channel members, the collaborators of a private GitHub repo, and the Jira users allowed to browse the project. A user sees an item when one of their linked accounts is a member of its source, or when it is public. Checking the tools live during every chat would be slow and would need their APIs on the chat path.

**The permission check is one condition inside every search query.** The searches only ever read rows the user may see, so the best 8 can never be filled with hidden matches. Admins get no bypass: they see what their own accounts see.

**Access changes take up to 15 minutes.** Someone removed from a channel keeps seeing it until the next sync. If a source's member list can't be read, its sync fails and the old list stays, rather than opening the source to everyone.

**Questions are embedded with Qwen3-Embedding's search instruction**, the way the model was trained, while chunks are embedded plain. pgvector's iterative scan keeps the index search going until enough visible chunks are found, otherwise a filtered search can come back short.

**Keyword search treats ids as required.** Words that look like ids, function names or error codes (`PAY-1234`, `charge_card`, `E4012`) must all appear; other words are optional. Requiring every word would miss "what does PAY-1234 say?", and making ids optional would let common words outrank them.

**Graph search finds names by alias, without GLiNER.** Every run of up to six words in the question is compared with the known aliases, using the same name normalisation as the learning side. GLiNER could only add names the graph doesn't know, which can't lead anywhere, so the model call was dropped. Say if you want it back.

**Graph search goes two links out.** From a named service it reaches the PRs and threads that mention it, then their reviews, replies and decisions. That is how "who reviewed the payment queue PR?" finds the review.

**The reranker sees a short header with each piece**, like "Add the payment queue (review by github:bob)". A bare "LGTM" says nothing about which PR it approves; with the header, the review moved from the bottom to the top for "who reviewed…?".

**Evidence the reranker scores very low is dropped** (under -5; unrelated text scores about -11, related text above 0). An unrelated question then finds no evidence at all, and the answer can say it doesn't know without asking the LLM.

**A search that fails is skipped**, so a crashed embedder still leaves keyword and graph results.

---

## 24. Writing and checking answers

**The answer streams as plain text, not JSON.** Words reach the user as qwen3:8b writes them; JSON would only be readable at the end. Follow-up questions come after a fixed "Follow-ups:" line that the code splits off.

**The streamed text is a draft; the final reply replaces it.** Checking claims needs the whole answer, so the last event carries the checked version, and that is what is saved. The web app should swap the draft for it.

**qwen3:8b gets 8192 tokens of context for answers.** Eight pieces of evidence, the history and the rules don't fit Ollama's default 4096, which would silently cut off the start of the prompt (the rules).

**No evidence means "I don't know" without asking the LLM.** It's instant, and a model with nothing to cite can only guess.

**The claim checker sees the evidence header too.** "github:bob reviewed the payment queue" can't be checked against a bare "LGTM"; with the header saying it's bob's review of that PR, it can.

**True sentences without a citation are kept and cited**, rather than removed. The writer sometimes forgets a citation on a correct sentence, and dropping it would throw away a good answer. Sentences that only say what isn't known ("I don't know who owns it") make no claim and stay.

**Confidence multiplies two things**: the share of claims that held up and how relevant the best cited evidence was. Fully supported claims from barely relevant evidence aren't high confidence, and relevant evidence with half the claims removed isn't either. The thresholds (0.7, 0.4) are settings, to be tuned on the evaluation set.

**If Ollama is down, the user gets an apology** and only their question is saved, so it stays unanswered in the history instead of an error message being remembered as an answer.

---

## 25. Actions

**The planner only offers Jira projects the user may see**, and the code rejects any other project it names. A planted "set project to SEC" in a request made qwen3:8b pick SEC in a test; the code turned that down.

**Approving checks access again and records the outcome.** The action is marked approved before it runs (so a crash still leaves a record), then done with the new ticket's key and link, or failed with the error. The row is locked while it is settled, so a double click can't create two tickets. Every step is logged.

**Tickets are created with the Jira account in `.env`**, not with each user's own Jira login, which Syncra doesn't have. "Running with the user's permissions" therefore means: only in projects the user can see, with "Requested by <user> via Syncra" in the description. Per-user Jira sign-in could come with the Phase 9 settings screens.

**Only "create a Jira ticket" exists so far.** Anything else gets a reply saying so; new kinds of action would add a planner option and a runner each.

---

## 26. Quality and launch

**A fictional company to demo and measure on.** Acme Pay has two teams with private repos, Jira projects and Slack channels, so the demo also shows permissions. Its data goes through the real learning pipeline instead of being written straight into the tables, so the demo shows what Syncra really learns. Its sources are marked as demo sources and never reach a real API.

**66 evaluation questions, measured end to end.** The runner asks each as its user and checks the evidence, the leaks, the citations, the removed claims and the "I don't know"s. Its first run found four real problems that the unit tests had missed, all fixed: Jira keys weren't searchable, approving reviews were thrown away as noise, the claim checker was far too strict, and the answer writer added explanations of its own.

**The claim checker reads evidence the way the NLI model likes it.** The header became a sentence, claims citing two pieces are checked against both together, long threads are also read two sentences at a time, and an unsupported ", which …" tail is cut instead of deleting the whole sentence. Removed claims fell from 36% to 14%, and wrongly empty answers from 8 to 2, while every unanswerable question still got "I don't know".

**Evidence shows people's names.** Accounts an admin linked get the person's name next to them (`Carol Okafor (github:carol-ok)`), so answers name people and the checker can match "Carol" to her review.

**Leak tests check the prompt, not just the reply.** A private chunk reaching the LLM is a leak even if the model doesn't repeat it, so the tests look at what Ollama would have read. They found that `password=hunter2` slipped past the scrubber; short unquoted passwords are masked now.

**Problems are stored in the database for admins.** Failed syncs and learning runs, model errors and slow answers go into an `events` table that `GET /admin/status` shows. The API and the worker are separate processes, and one database is the rule, so no log service was added.

**The first word takes 3.5 to 4 seconds, not under 3.** Model warm-up removed the 8 to 19 second first question; what's left is qwen3:8b reading the evidence. `timing.md` lists the options: qwen3:4b for answers, fewer pieces of evidence, or Ollama's flash attention.

## 27. The web app

**React with Vite, not Next.js.** The API already does all the server work, so the app is a plain single-page app: one `npm run dev`, a static `dist/` for production, no second server to run. Next.js would add server rendering nobody needs here.

**Arc UI components instead of hand-made ones.** Buttons, fields, dialogs, the hover card behind citations, the command palette, timeline and metric cards come from Arc (uiarc.dev), installed as source with the shadcn CLI, so they can be read and changed. Its rules shaped the look: neutral surfaces, one accent (blue), two font weights, motion only to explain a change. 21st.dev was used for ideas only (inline citations, approval cards, source lists): its installs need an API key. Arc's AI chat blocks are paid, so the chat itself is built from the free parts.

**No router or data library.** Five screens fit in `#/…` hash routes and a few `fetch` calls in `src/api.ts`. React Router or TanStack Query can come in if the app grows past that.

**Vite passes `/api` to the API instead of opening CORS.** The browser sees one address, the API keeps its strict headers, and production does the same with the reverse proxy.

**The login token sits in the browser's local storage.** The API hands out bearer tokens, so that was the simple fit. A script injected into the page could read it; React never renders the tools' text as HTML and only `http(s)` links become clickable, which closes the usual way in. An httpOnly cookie would be stronger and needs API changes.

**Starter questions come from the user's own data, not a fixed list.** `GET /chat/suggestions` turns the newest decisions in tickets and PRs into "What did we decide about "…"?" questions, quoting the title. A template that rewrote titles as "Why did we decide to …" read badly for titles that name a thing ("Retry policy for merchant webhooks"), so the title stays as written. No LLM: it must be instant and can't leak what the permission filter hides.

**Two small API additions.** `GET /me` now says `is_admin`, so the app knows whether to show admin pages, and action cards carry their `session_id`, so a card shows up under its reply again after a reload.

**Hugging Face models run one call at a time.** Testing the app found that the API process crashed when the first question arrived while warm-up was still loading models, and the same happens with two questions at once: two models on Apple's GPU together trip a Metal assertion. A single lock in the model gateway fixed both; Ollama calls are not affected.

**Contrast fixed in three of Arc's colours.** Its muted grey and warning orange were under the 4.5:1 contrast small text needs, and so was the dark-mode green. The app darkens them in `src/index.css`; every screen now passes an automated accessibility check in light and dark.

---

## Decisions still waiting for you

**A bigger GLiNER model?** The small one mixes up services and tools and tags some junk as people. `gliner_medium-v2.1` or `gliner_large-v2.1` may do better, at some cost in speed.

**Where Syncra will be deployed.** The server, the domain, where backups go and how secrets are stored decide the rest of the production setup (`security-audit.md` §9).

**Serving the web app in production.** It's a static folder; the compose file doesn't serve it yet. Say which reverse proxy you'll use and it can be added.

**Company sign-in for the web app?** Local accounts with passwords exist now (section 20). Company sign-in (Google, Okta or GitHub) would avoid storing passwords at all, and can hand out the same tokens.

**A Hugging Face token for Prompt Guard 2.** The guard's code and tests are in, but the real model can't download until `HF_TOKEN` is set in `backend/.env` (with Meta's licence accepted). Until then, chat messages that reach the guard fail.

**Graph search without GLiNER?** Names in a question are found by alias lookup only (section 23). Say if you want GLiNER run on questions as your design describes.

**Per-user Jira sign-in for actions?** Tickets are created with the shared Jira account today (section 25).

**Answer with qwen3:4b to meet the 3-second target?** See `timing.md`: it would roughly halve the time to the first word, at some cost in answer quality that `make eval` can measure.

**Whether internal IP addresses should stay hidden.** Hiding them is safer, but can blank out useful infrastructure details in answers.
