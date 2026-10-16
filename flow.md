# Syncra — How It Works

This file follows Syncra's data from one end to the other. It starts with a pull request or a Slack message and ends with the facts stored in Postgres. Then it shows how a question will become a cited answer once the chat side is built.

Parts that don't exist yet are marked **(planned)**. For why things were built this way, see [`decision.md`](decision.md); for the full design, see [`description.md`](description.md).

---

## The big picture

Syncra is two programs sharing one PostgreSQL database. The **worker** (`make worker`) wakes up every 15 minutes, pulls new activity from GitHub, Jira and Slack, and turns it into searchable knowledge. The **API** (`make run`) is the door the chat uses; today it handles logins, and the chat endpoints arrive during Phase 5.

Everything runs on your own machine. The large language models (Qwen3) run in Ollama, the small models run inside the Python process, and all data lives in the one database. Nothing is sent to an outside AI service.

```
GitHub · Jira · Slack
      |  every 15 minutes
      v
connectors -> privacy scrubber -> items              (cleaned raw text)
      |
      v
triage: drop noise -> group into conversations
      |
      v
for each conversation:
  chunks -> entities -> decision -> vectors -> store chunks -> link names + graph
      |
      v
PostgreSQL: chunks (vector + keyword index), entities, links, decisions
      ^
      |  (planned, Phases 5–7)
question -> rewrite -> safety check -> intent -> search -> rerank -> answer -> check -> reply
```

---

## Before the first run

`backend/.env` tells Syncra where the database is (`DATABASE_URL`) and holds the source tokens. `config/models.yaml` lists every model by its job, and `config/prompts/` holds the instructions given to the LLM. If a required setting is missing, the API refuses to start and names it.

`make db-init` creates the database and `make migrate` creates the tables. `make pull-models` and `make download-models` fetch the models once, and `make train-triage` trains the noise filter on the examples in `config/triage.yaml` (about 30 seconds). The worker can't learn without that trained filter.

A source is connected by adding one row to the `sources` table: a GitHub repo (`acme/payments`), a Jira project key (`PAY`) or a Slack channel id (`C0123456789`). A screen for this comes in Phase 9.

---

## Every 15 minutes: one learning run

The worker's timer (APScheduler) starts a run as soon as the worker starts, then every `SYNC_INTERVAL_MINUTES`. If a run is still going when the next one is due, that run is skipped and the job waits for the following one, so two runs never overlap. Each run goes through the steps below (`app/learning/pipeline.py`).

### Step 1: Fetch what's new

The worker goes through every enabled source, one at a time. It first checks the source id against a strict pattern, so a malformed id can't reach another repo or project. Then it asks that tool's connector for everything new or changed since the source's **cursor**, which is the newest timestamp seen on the last run.

The GitHub connector fetches PRs and issues, their comments, PR reviews, inline review comments and commits. The Jira connector fetches issues with their comments. The Slack connector fetches channel messages and turns each thread into **one** item, with every reply as a `slack:U01: text` line in order. Direct messages are never fetched.

Every piece becomes the same kind of **item**: an id, a type (`pr`, `issue`, `comment`, `review`, `commit`, `message` or `thread`), a title, the text, the author, the time, a link back to the original and the item it replies to. People are stored by account id (`github:alice`, `jira:<accountId>`, `slack:U0123`), not by display name.

Each item also gets **access tags** that copy the tool's own permissions: `github:repo:acme/payments` (plus `public` for a public repo), `jira:project:PAY` or `slack:channel:C123`. An item without tags is rejected, so nothing can end up visible to everyone by mistake.

### Step 2: Hide private data

Before anything is saved, Presidio scans each item's title and text. Emails, phone numbers, card numbers, IBANs, US social security numbers and IP addresses are replaced with labels like `<EMAIL_ADDRESS>`. Secrets get the same treatment: AWS keys, GitHub and Slack tokens, private keys, connection strings with passwords, `password = …` lines and JWTs.

People's names are kept, because "who built what" is the whole point. Code names like `PaymentService` or `settings.api_key` are kept too.

### Step 3: Save the items

The cleaned items are saved into `items`, one row per source and id. Each item carries a fingerprint (a hash of its content). An unchanged item is skipped, a changed one is overwritten and set back to `new` so it is learned again, and a brand-new one starts as `new`.

The source's new cursor is saved in the same transaction as its items, so a crash can never skip anything. If a source fails (a bad token, the network is down), the error is written to `sources.last_error` and the worker moves on to the next source.

### Step 4: Drop noise (triage)

Every item with status `new` is sorted into **useful** or **noise**. Simple rules go first: an empty item, or one written by a bot (`github:…[bot]`, `slack:B…`), is noise straight away. The exception is a Slack thread a bot started, because people may have replied in it. Everything else goes to the SetFit classifier in one batch.

Noise is things like "thanks!", "+1", emoji-only replies and CI chatter. It gets status `noise` and is skipped from then on, unless it is edited. Useful items keep status `new` for now.

If an item that was useful before has become noise (a message edited down to "+1"), everything learned from it is deleted.

### Step 5: Group into conversations

The pipeline learns **conversations**, not single items, because a decision is usually proposed in one message and agreed to in another. A conversation is a root item (a PR, an issue, a Slack thread or message, or a commit) plus its replies that aren't noise, oldest first.

For every useful item, and every item that failed last time, the pipeline finds the root and learns that whole conversation again. A reply whose parent is missing, or is noise, is treated as a conversation of its own.

### Step 6: Learn each conversation

Each conversation is handled in its own database transaction, in this order:

1. **Chunks.** Each item's title and text are cut into pieces of at most 1500 characters, each repeating up to 200 characters from the end of the one before. A Slack message or a code block stays whole when it fits.
2. **Entities.** GLiNER reads each chunk and lists the people, services, tools and projects it names, for example `Alice Chen` (person), `PaymentService` (service) or `RabbitMQ` (tool). Slack mentions like `<@U03>` become the person `slack:U03`.
3. **Decision.** If the conversation is a PR, issue, thread or message with at least 60 characters, qwen3:8b reads all of it (cut in the middle beyond 6000 characters). It answers in JSON: what was decided, why, and by whom. A bad answer is retried once and then dropped, and only people who actually wrote in the conversation are kept as deciders.
4. **Vectors.** Qwen3-Embedding turns each chunk into a list of 1024 numbers that captures its meaning, called an **embedding**. Chunks that mean similar things get similar numbers, even when they use different words.
5. **Store the chunks.** The conversation's old chunks are replaced by the new ones with their vectors. Saving a chunk also indexes it: the vector goes into the HNSW index for meaning search, and Postgres builds the keyword index from the text by itself.
6. **Link names and write the graph.** The conversation's old links and decision are deleted first, so nothing is ever stored twice. Each author account is matched to its person, and each name GLiNER found is matched to one **entity**. So `PaymentService`, `payment-service` and `payments-svc` become one thing with three **aliases**. Then the new links and the decision are written.
7. **Done.** Every item in the conversation gets status `processed`, and the transaction is committed.

The links written in step 6 are: a person **authored** an item, a person **reviewed** a PR, a chunk **mentions** an entity, a person **decided** a decision, and a decision is **about** a service, tool or project. Each link remembers the item it was learned from, so it disappears together with that item.

Names are matched in two ways. First by a normalised spelling (split into words, lower case, `svc` read as "service", plural `s` dropped). If that finds nothing, a small SBERT model compares the name with every known name, and only a very close match (0.9 or more, with the same numbers) counts. People are only ever matched by exact name or by account.

### Step 7: When something breaks

If anything fails inside a conversation (Ollama is down, a model errors, the database refuses a write), only that conversation is rolled back. Its unprocessed items are marked `failed` and the error is logged, while the other conversations carry on. Failed items are picked up again on the next run.

The run as a whole stops only if fetching or triage can't run at all, for example when the noise filter hasn't been trained yet.

### Step 8: Merge people

At the end of every run, people are merged for each Syncra user whose accounts an admin linked (`make link-account`, Task 5.1). For example, `github:alice`, `slack:U01` and the display name `Alice Chen` become one person. An account nobody linked stays a person of its own.

### Step 9: Report

The run logs one line such as `learn: {'sources': 2, 'noise': 2, 'learned': 3, 'failed': 0}`. That reads: two sources tried, two items dropped as noise, three conversations learned, none failed.

---

## What the database holds afterwards

**`sources` and `sync_cursors`** hold the connected repos, projects and channels, when each last synced, its last error, and how far each has read.

**`items`** holds every cleaned item with its text, author, time, link, parent, access tags, fingerprint and status (`new`, `processed`, `noise` or `failed`).

**`chunks`** holds the pieces of text that searches will return. Each has its 1024-number vector (in the HNSW index) and a keyword column (`tsv`, in a GIN index) that Postgres keeps up to date by itself.

**`entities` and `entity_aliases`** hold one row per real person, service, tool or project, and every name or account it was seen under. Account aliases (`github:alice`) remember which tool they belong to; plain names don't.

**`edges`** holds the links between people, items, chunks, decisions and entities. Each link points to the item it came from, so deleting an item, or a whole source, deletes its links along with its chunks and decisions. The entities and aliases it introduced stay.

**`decisions`** holds one row per conversation that decided something: the decision, the reason, the deciders' account ids, a link to the source and the date of the conversation's last activity.

**`users` and `user_source_identities`** hold the Syncra users and the GitHub, Jira and Slack accounts an admin linked to each. **`auth_tokens`** holds one row per login: the SHA-256 of the token and when it expires, never the token itself.

**`chat_sessions` and `chat_messages`** hold each user's chats and every message in them, in the order they were sent. **`actions`** exists already but stays empty until Phase 8: approval cards.

---

## A worked example

This is the sample conversation used while building Phase 4.

**On GitHub**, `github:alice` opens PR #42, "Add a RabbitMQ queue between checkout and payments". Its description says the payment provider times out under load, and that Alice Chen moved the PaymentService behind RabbitMQ. `github:bob` approves it ("LGTM, ship it"), `github:carol` comments "thanks!", and `github:alice` pushes a commit, "Add payment queue consumer".

**In Slack**, `slack:U01` writes that payments-svc keeps timing out on Black Friday. `slack:U02` suggests putting RabbitMQ in front of payments-svc and mentions `<@U03>`, and U01 answers "agreed, RabbitMQ it is". A CI bot posts "Build #12 passed".

**Fetch and triage.** Six items are saved. The bot's message is noise by rule and "thanks!" is noise by the classifier; the PR, the review, the commit and the thread are useful.

**Conversations.** Three are learned: the PR with bob's review (carol's "thanks!" is left out), the commit on its own, and the Slack thread.

**Decisions.** The PR's decision reads roughly "Put a RabbitMQ queue between checkout and the payment service", because "the payment provider times out under load", decided by `github:alice` and `github:bob`. The thread's reads "Put RabbitMQ in front of payments-svc", decided by `slack:U01` and `slack:U02`. The commit isn't read for decisions.

The exact wording changes from run to run, but the real qwen3:8b found both decisions with these same people.

**Linking.** GLiNER finds `PaymentService` in the PR and `payments-svc` in the Slack thread. Both reduce to the same spelling key (`paymentservice`), so they become one entity with two aliases. That ties the GitHub decision and the Slack decision to the same service.

**Links stored**, among others: alice authored #42 and the commit, and bob reviewed #42. Alice and bob decided the PR's decision, which is about RabbitMQ and PaymentService. U01 and U02 decided the thread's decision, which is about PaymentService, and the thread's chunk mentions PaymentService and `slack:U03`.

**The next run.** Nothing changed at the source, so nothing new is saved, no model is asked, and no row changes. With the real models, the first run took about 35 seconds (mostly loading the models) and the second well under a second.

---

## When things change later

**A new reply**, say a second review on PR #42, makes the whole PR conversation new again. It's chunked and read again, and its old links and decision are replaced, never duplicated.

**An edit** changes the item's fingerprint, so it's saved as `new` and its conversation is learned again. If the edit turns it into noise ("+1"), what it said is deleted.

**Deleting a source** deletes its items, and with them their chunks, decisions and links. The entities and people it introduced stay.

**An admin linking a user's accounts** merges that person's records on the next run.

**Ollama being down** fails only the conversations that needed it, and they're retried on the next run.

---

## The API today

`make run` starts the FastAPI app at `http://127.0.0.1:8000`. `GET /health` answers `{"status": "ok"}` without a login; every other endpoint needs one. Every response carries security headers and a request id, and unexpected errors return only "Internal server error" with that id, never internal details.

**Logging in.** An admin creates users with `make add-user`; passwords are stored only as scrypt hashes. `POST /auth/login` checks the password and hands out a random token, and `auth_tokens` keeps only its SHA-256 with an expiry (12 hours by default). Each later request sends `Authorization: Bearer <token>`; the API hashes it, finds the user, and answers 401 if the token is missing, unknown or expired. `POST /auth/logout` deletes the token, and `GET /me` shows the user and the accounts an admin linked to them.

The interactive docs at `/docs` are on locally (`API_DOCS=true` in `.env`) and always off in production. In production the API listens only on the server itself until the Phase 9 hardening (TLS proxy, rate limits) is in place.

---

## The chat side (planned, Phases 5–8)

None of this is built yet. It's how the design in `description.md` will use what the worker stores, with the task that builds each step in brackets.

1. **Who's asking** (built). The user logs in with a token, and the GitHub, Jira and Slack accounts an admin linked to them decide what they may see (5.1).
2. **Memory** (built). The last 10 turns of the chat are loaded from `chat_messages`, oldest first. A turn is one user message and the replies after it (5.2).
3. **Rewrite.** If there is history, qwen3:4b turns a follow-up like "who built it?" into a standalone question like "who built the payment service?" (5.3).
4. **Safety.** Prompt Guard 2 blocks prompt-injection and jailbreak attempts with a polite reply (5.4).
5. **Intent.** A second SetFit classifier picks the path. Small talk gets an instant reply with no search, a request to *do* something goes to an approval card, and a question carries on (5.5).
6. **Search.** Three searches run at the same time, and each only looks at items whose access tags the user has; that filter sits inside the query itself (6.1). Vector search embeds the question with the same Qwen3-Embedding model and finds the closest chunks (6.2). Keyword search matches exact terms like `PAY-1234` (6.3). Graph search finds the entities named in the question through their aliases and follows links to related decisions and chunks (6.4).
7. **Rerank.** A cross-encoder scores every match against the question, and the best 8 become the evidence `E1`…`E8` (6.5).
8. **Answer.** qwen3:8b writes the answer only from that evidence, cites it as `[E1]`, and streams it word by word. If the evidence isn't enough, it says it doesn't know (7.1–7.2).
9. **Check.** A DeBERTa model checks each claim against the evidence it cites and removes the unsupported ones. The answer is then labelled high, medium or low confidence (7.3–7.4).
10. **Reply.** The user sees the answer, clickable sources, the confidence and suggested follow-up questions, and the turn is saved to the chat history (7.5).

**Actions (Phase 8).** A request like "open a Jira ticket to add monitoring for payments" becomes a filled-in **approval card**, saved as `pending` in `actions`. Nothing happens until the user approves. Then it runs with the user's own permissions, and every step is logged.

---

## The web app

`frontend/` holds a clickable prototype (`index.html`, `app.js`, `styles.css`). It runs on built-in demo data and isn't connected to the backend.

The real web app (Phase 9) will have the login, the chat screen with streamed answers and citations, the approval cards, and screens to connect sources and link accounts.

---

## Where each step lives in the code

All paths are under `backend/`.

- The 15-minute timer: `app/jobs/scheduler.py` (started by `make worker`)
- One learning run, start to finish: `app/learning/pipeline.py`
- Fetching: `app/learning/connectors/` (`github.py`, `jira.py`, `slack.py`; the source id check is in `__init__.py`)
- Saving items and cursors: `app/learning/sync.py`
- Hiding private data: `app/learning/scrub.py`
- The noise filter: `app/learning/triage.py`, trained on `config/triage.yaml`
- Chunks: `app/learning/chunk.py`
- Entities: `app/learning/entities.py`
- Decisions: `app/learning/decisions.py`, with its prompt in `config/prompts/decision_reader.v1.yaml`
- Vectors: `app/learning/embed.py`
- Matching names to entities and people: `app/learning/link.py`
- Links and decisions: `app/learning/graph.py`
- Storing chunks: `app/learning/index.py`
- Every model call: `app/models/gateway.py`, with the models listed in `config/models.yaml`
- Settings: `app/config/settings.py`, reading `.env`
- Tables: `app/db/schema.py`, created by the files in `migrations/versions/`
- The API: `app/api/main.py`; users, logins and linked accounts: `app/api/auth.py` (the admin commands are `scripts/users.py`); chats: `app/api/chat.py`
- Chat memory: `app/chat/memory.py`
