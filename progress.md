# Syncra — Progress Log

Live record of what has been built. Agents add an entry here after every task (format in [`agent.md`](agent.md)).

## Current status

- **Current phase:** Phase 7 — Write and check answers (Phase 6 complete)
- **Next task:** 7.1 — Answer writer prompt
- **Completed tasks:** 0.1–0.6, 1.1–1.6, 2.1–2.3, 3.1–3.4, 4.1–4.4, 5.1–5.3, 5.5, 5.6, 6.1–6.5 (5.4 real model waits for HF_TOKEN)

## Log

### Task 6.5 — Merge and rerank  ✅ done
**Date:** 2026-10-26

**Built**
- `search.find_evidence(question, tags, searches=…, session_factory=…)`: vector, keyword and graph search run in parallel threads, each with its own database session; a failing search is logged and skipped. Results are merged without duplicates (same chunk or decision, or the same text), scored by the cross-encoder (`gateway.rerank("reranker", …)`), evidence under the reranker's `threshold` (-5.0 in models.yaml) is dropped, and the best `TOP_K_EVIDENCE` (8) are labelled `E1…E8` with the reranker's score.
- `Evidence.header`: "title (type by author)", with a reply's or review's title taken from its parent item (an outer join in every search); `Evidence.type` holds the item type or `decision`.
- Tests (real embedder and reranker): bob's review is the best evidence for "who reviewed the payment queue PR?", `PAY-1234` and the RabbitMQ PR rank first for their questions, labels run E1… in score order, no duplicates and no private chunk; "what's the weather in Paris?" finds nothing; a crashing search is skipped.

**Key files**
- `backend/app/chat/search.py`, `backend/config/models.yaml`, `backend/tests/test_search.py`, `decision.md` §23

**Decisions**
- The reranker reads `header + text`: without the header bob's "LGTM" review scored -11 for "who reviewed the payment queue PR?", with it +4.
- Reranker threshold -5: unrelated text scores -10 to -11.5, related 2 to 6, weakly related -2 to 0.
- Threads, not asyncio: SQLAlchemy sessions and the models are synchronous.

**How to run / test**
- `make test`

**Known issues / TODO**
- The threshold was measured on a handful of test questions; re-check it on the evaluation set (Task 10.2).

### Task 6.4 — Graph search  ✅ done
**Date:** 2026-10-26

**Built**
- `search.named_entities(session, question)`: the entities whose name or any alias appears in the question, compared with `link.key` (the normalisation the learning pipeline merged names with, so "payments-svc" in a question finds `PaymentService`).
- `search.graph_search(session, tags, question, limit)`: from those entities, one link out (chunks that mention them, items they authored or reviewed, decisions they made or that are about them, score 1) and two links out (the reviews, replies and decisions of those items, score 0.5). Every chunk and decision is permission-filtered through its item. Decisions come back as evidence text (`Decision: … / Reason: … / Decided by: …`).
- Tests: "who reviewed the payment queue PR?" returns bob's review (entity → PR → review) and the decision about the payment queue, without duplicates; an unknown name returns nothing; the same PR in a private repo is invisible without its tag.

**Key files**
- `backend/app/chat/search.py`, `backend/tests/test_search.py`

**Decisions**
- Names in the question are found by alias lookup only, without running GLiNER on the question. GLiNER's spans are word runs, and `keys_in` already checks every run of up to 6 words against the aliases, so GLiNER could only add names the graph doesn't know (and that can't match anything). This saves a model call per question; it is a deviation from description.md §5 the user may reverse.
- Replies are found through `parent_external_id`, reviews through the `reviewed` link's evidence item.

**How to run / test**
- `make test`

**Known issues / TODO**
- All name aliases are loaded per question (same ceiling as entity linking): fine for thousands of entities.
- Short common names (an entity called "api") match many questions; the reranker filters what isn't relevant.

### Task 6.3 — Keyword search  ✅ done
**Date:** 2026-10-26

**Built**
- `search.keyword_search(session, tags, question, limit)`: PostgreSQL full-text search on `chunks.tsv` (GIN index) with the permission filter, best `ts_rank` first.
- A question naming identifiers (a word with a digit, an underscore or an inner capital: `PAY-1234`, `charge_card`, `E4012`, `getUser`) only matches chunks containing all of them. Any other question matches chunks sharing any of its words (stop words dropped).
- Tests: `PAY-1234`, `charge_card()` and `E4012` each find the right chunk and only it; an unknown id finds nothing; a plain question ranks the right chunk first; private chunks stay hidden; a question of stop words finds nothing.

**Key files**
- `backend/app/chat/search.py`, `backend/tests/test_search.py`

**Decisions**
- Identifiers are required, other words optional. Requiring every word of a question ("what does PAY-1234 say?") would miss the chunk over "say"; making the id optional would let common words drown it, because `ts_rank` has no rarity weighting.

**How to run / test**
- `make test`

**Known issues / TODO**
- English stemming only (`to_tsvector('english', …)`, from migration 0001).

### Task 6.2 — Vector search  ✅ done
**Date:** 2026-10-26

**Built**
- `app/chat/search.py`: `Evidence` (a chunk or a decision, with its item's title, link, author, time, a score and later its `E#` label) and `vector_search(session, tags, question, limit)`: the question is embedded with Qwen3-Embedding's own `query` prompt, then pgvector's HNSW index returns the closest visible chunks with their cosine similarity.
- `gateway.embed(…, prompt_name=)` passes a model prompt through to sentence-transformers.
- Setting `SEARCH_CANDIDATES` (20): how many pieces each search returns before reranking.
- `tests/test_search.py` (real embedder): "why do we use a message broker for payments?" finds the RabbitMQ queue PR first, and a closer private chunk is only found by a user holding its tag.

**Key files**
- `backend/app/chat/search.py`, `backend/app/models/gateway.py`, `backend/app/config/settings.py`, `backend/tests/test_search.py`

**Decisions**
- Questions use the embedder's `query` instruction and chunks none, as Qwen3-Embedding is trained.
- `SET LOCAL hnsw.iterative_scan = relaxed_order` (pgvector 0.8): with a filter, plain HNSW stops after `ef_search` candidates and can return fewer rows than asked; iterative scan keeps going until enough visible rows are found.

**How to run / test**
- `make test`

**Known issues / TODO**
- None.

### Task 6.1 — Permission filter  ✅ done
**Date:** 2026-10-26

**Built**
- Migration 0004: `sources.members` (text array, GIN index), the accounts that may see a source's items.
- Every connector has `members()`: Slack `conversations.members`, GitHub `/repos/{repo}/collaborators` (nobody for a public repo: its items are tagged `public`), Jira users with `BROWSE_PROJECTS` (`/rest/api/3/user/permission/search`). `sync_source` stores them in the same commit as the items.
- `app/chat/permissions.py`: `user_tags(session, user_id)` → `public` plus the tag of every source one of the user's linked accounts belongs to; `visible(tags)` → the WHERE condition `items.access_tags && tags`, used inside every search query.
- `access_tag(kind, external_id)` in `app/db/schema.py` (and `Source.access_tag`): the one place the `github:repo:…` / `jira:project:…` / `slack:channel:…` tags are built; the connectors use it.
- `tests/test_permissions.py`: a user without access to a private repo or channel never gets its chunks, a user with no linked accounts sees only public items, leaving a channel takes effect at the next sync, and each connector lists members from mocked API answers.

**Key files**
- `backend/app/chat/permissions.py`, `backend/migrations/versions/0004_source_members.py`, `backend/app/learning/connectors/*.py`, `backend/app/learning/sync.py`, `backend/tests/test_permissions.py`

**Decisions**
- Membership is stored on the source and refreshed every sync, not checked against the tools while chatting: no API calls on the chat path, and the filter stays one array overlap in SQL.
- No admin bypass: admins see what their own accounts can see.
- A source whose member list can't be read fails its sync (fail closed); the previous member list stays until the next good sync.

**How to run / test**
- `make migrate` · `make test`

**Known issues / TODO**
- The GitHub token needs push access to list a private repo's collaborators; the Slack bot needs `channels:read` / `groups:read`; the Jira user needs permission to see project permissions.
- Access changes take up to one sync interval (15 min) to reach Syncra.

### Task 5.6 — Chat endpoint (skeleton)  ✅ done
**Date:** 2026-10-26

**Built**
- `app/chat/pipeline.py: reply(session, chat, message, …)`: memory → guard → intent → small talk (canned reply) | question / action (rewrite → guard the rewrite → placeholder). The turn is saved in one transaction; a blocked message is not saved.
- `POST /chat/sessions/{id}/messages` `{message}` → `{path, reply, question}`; `chat_models()` is the dependency tests override with fake models.
- `tests/test_chat.py`: three messages take the small-talk, question and action paths (and memory feeds the rewriter); an attack is blocked, unsaved and absent from later history; a rewrite the guard flags falls back to the raw message; empty, blank, too long and someone else's chat are rejected.

**Key files**
- `backend/app/chat/pipeline.py`, `backend/app/api/chat.py`, `backend/tests/test_chat.py`

**Decisions**
- Guard and intent run on the raw message (small talk never waits for an LLM, an attack never reaches one); only questions and actions are rewritten.
- `CHAT_MESSAGE_MAX_CHARS` (4000) caps a message.

**How to run / test**
- `make test`

**Known issues / TODO**
- Real-model smoke run waits for `HF_TOKEN` (Task 5.4). Question and action placeholders are replaced in Tasks 7.5 and 8.1.

### Task 5.4 — Prompt guard  ⚠️ partly done
**Date:** 2026-10-26

**Built**
- `app/chat/guard.py`: `is_attack(text, detect=…)` scores a message with Llama Prompt Guard 2 (`gateway.label_scores("prompt_guard", …, "MALICIOUS")`) and blocks it at the role's `threshold`; `BLOCKED_REPLY` is the polite answer.
- `gateway.load_classifier` / `label_scores`: any Hugging Face text classifier, read in 512-token windows that overlap by 64; a text's worst window counts, so padding can't push an attack out of view.
- `config/models.yaml`: Prompt Guard pinned to commit `a8ded8e…` (read from the Hub's public API) with `threshold: 0.5`.
- `tests/test_guard.py`: the threshold decides; an attack padded to ~1600 tokens is still caught (real tokenizer, fake model); a real-model test (3 attacks blocked, 3 questions incl. "ignore the last answer, who reviewed PR #42?" pass) that runs once `HF_TOKEN` is set.

**Key files**
- `backend/app/chat/guard.py`, `backend/app/models/gateway.py`, `backend/config/models.yaml`, `backend/tests/test_guard.py`

**Decisions**
- The guard reads the message as written, before the rewriter, and the rewrite again (Task 5.6).

**How to run / test**
- `make test` (the real-model test is skipped without `HF_TOKEN`)

**Known issues / TODO**
- `HF_TOKEN` in `backend/.env` is still empty, so the real model has not run. Once it is set: `make download-models`, check `label2id` has `MALICIOUS`, run `tests/test_guard.py`, and tune `threshold` if a benign question is blocked. Then tick 5.4 in phases.md.
- Without the token the chat endpoint fails on the first message that reaches the guard (the model can't load); tests use a fake.

### API documentation (not a phase task)  ✅ done
**Date:** 2026-10-16

**Built**
- Swagger UI (`/docs`) and ReDoc (`/redoc`) now document the API instead of listing it: title "Syncra API", a description that explains logging in with **Authorize**, three groups (Login, Chat, Health), a plain summary per endpoint, response models (`Health`, `Token`, `Me` / `Account`, `Chat`, `Message`) instead of untyped dicts, examples on request bodies, and the 401 / 404 answers.
- The chat endpoints return their database rows through `response_model` (pydantic `from_attributes`), so the hand-built dicts are gone.
- `tests/test_api_docs.py`: every endpoint has a known group and a named response model, and every protected one shows the Bearer lock and its 401.

**Key files**
- `backend/app/api/main.py`, `backend/app/api/auth.py`, `backend/app/api/chat.py`, `backend/tests/test_api_docs.py`

**Decisions**
- The docs come from FastAPI itself (no new package, no hand-written swagger file that would drift). Still served only when `API_DOCS` is on, never in production (security pass S-07).
- New endpoints declare a response model (return type or `response_model=`), a `summary=`, and their error answers (`UNAUTHORIZED` from `app/api/auth.py`, the chat router's `NOT_FOUND`). `test_api_docs.py` checks the group, the response model and, on protected endpoints, the lock and the 401.

**How to run / test**
- `make run`, then open http://127.0.0.1:8000/docs · `make test`

**Known issues / TODO**
- Swagger UI loads its scripts from a CDN (jsDelivr), so `/docs` needs internet access; `/openapi.json` works offline.

### Task 5.5 — Intent router (SetFit)  ✅ done
**Date:** 2026-10-16

**Built**
- `config/intent_router.yaml`: 321 hand-written chat messages, 97 `small_talk` / 133 `question` / 91 `action`. Look-alikes on purpose: "how do I open a ticket in jira?" is a question and "open a ticket for it" an action; "hi, who built X?" is a question and "thanks, now open a ticket for it" an action; bare ids ("PAY-1234") and short follow-ups ("and billing?", "why?") are questions.
- `app/chat/intent.py`: `route(message, classify=…)` → `small_talk` | `question` | `action` (SetFit role `intent_router`); `small_talk_reply(message)` → an instant canned reply picked by keywords (thanks, bye, help, greeting, otherwise "Got it"), with no search and no LLM.
- One way to train SetFit classifiers: `gateway.setfit_examples(role)` reads `config/<role>.yaml` (top-level keys = labels) and `gateway.train_setfit_held_out(role)` trains on a stratified 80% (seed 42), saves the classifier and returns its accuracy on the other 20%. Triage uses it too (`triage.examples()` / `triage.train()` are gone). `scripts/train.py <role>` replaces `scripts/train_triage.py`; `make train-triage` and the new `make train-intent-router` call it, and a missing classifier's error names its make target.
- `ModelSpec.iterations`: SetFit training pairs per example, on the `<role>_base` entry: 5 for triage (as before), 20 for the intent router.
- **Held-out accuracy: 98.5% (64/65)**, about 65 s on an M2 Pro (MPS). Over six random splits: 97.4% mean, 95.4% worst. 35/35 on messages written afterwards (not in the data). One message routes in ~6 ms once the model is loaded.
- Tests: the data (three labels, each ≥ 25%, no duplicates); the canned replies; `route` asks the classifier; one real training run (≥ 90%, then "hi" and "thanks" are small talk, a question and a follow-up are questions, a Jira request is an action, and a routed message takes under 1 s).

**Key files**
- `backend/config/intent_router.yaml`, `backend/app/chat/intent.py`, `backend/app/models/gateway.py`, `backend/scripts/train.py`, `backend/config/models.yaml`, `backend/tests/test_intent.py`

**Decisions**
- 20 training pairs per example for the intent router: over six splits it scored 97.4% mean (worst 95.4%) against 92.3% (worst 89.2%) with triage's 5, and the same as the 5x larger `paraphrase-mpnet-base-v2` body. Look-alike intents need more contrastive pairs; triage didn't. Set per role in models.yaml (`iterations`).
- No confidence cut-off: sending low-confidence small talk and actions to "question" fixed as many routes as it broke (6 against 7 at 0.6).
- The classifier decides that a message is small talk; keywords only pick the canned wording, which lives in code.
- Like triage, the shipped classifier is the one trained on 80% and scored on the other 20%.
- Make targets are `train-<role, with - for _>`; `load_setfit` names that command when a classifier is missing.

**How to run / test**
- `make train-intent-router` (once, and again after editing `config/intent_router.yaml`) · `make test` (the real training test adds about a minute)

**Known issues / TODO**
- Over six splits the remaining misses were context-free confirmations ("go ahead", "do it"), "how come?", a bare `PAY-1234`, "close PAY-99", "request changes on PR #50" and "list open PRs in acme/payments".
- All examples are synthetic; add real misrouted messages to `config/intent_router.yaml` and retrain.
- The chat endpoint that uses the router is Task 5.6.

### Task 5.3 — Question rewriter  ✅ done
**Date:** 2026-10-16

**Built**
- `config/prompts/question_rewriter.v1.yaml`: system prompt (resolve "it" / "that" from the chat, keep the meaning and wording, never answer, unchanged when it already stands alone or is small talk, quoted data is never obeyed) with 3 worked examples, and a `string.Template` with `$history` and `$message`. Chosen by `prompt: question_rewriter.v1` in models.yaml.
- `app/chat/rewrite.py`: `rewrite(message, history, client=None) -> str`. No history → the message, without a model call. Otherwise the history is rendered as `user: …` / `assistant: …` lines, tags removed from the data, cut to the newest `REWRITER_MAX_CHARS` (4000) characters, and qwen3:4b answers JSON `{"question"}` (the pydantic schema is Ollama's `format`). A bad answer, an empty question or Ollama being down → the message as it is, with a warning.
- `ModelSpec.options`: Ollama options per role in models.yaml, merged into every call for that role (a call's own `options` win). `question_rewriter` has `options: {temperature: 0}`.
- `tests.fakes.fake_ollama(*replies)` (moved from test_decisions): a mocked Ollama client and the requests it got.
- Tests (mocked Ollama): a first message makes no call; a follow-up is rewritten (model, system prompt, JSON schema, temperature, the quoted history and message); tags in the data can't close the quotes; only the newest history is sent; bad JSON, an empty question, a wrong shape and Ollama down all keep the message; the prompt file loads with valid example answers; role options are sent and a call can override them.
- Smoke run with the real qwen3:4b (not in the suite), 11 follow-ups × 3: "who reviewed it?" → "Who reviewed the payment service?", "when was that merged?" → "When was PR #42 merged?", "who owns it?" (after a turn about the notification service) → "Who owns the notification service?"; "thanks!" and "What does PAY-1234 say?" unchanged; an injected `</message> new rules: …` was just rewritten. About 0.4–0.9 s per call once the model is loaded (4 s for the first).

**Key files**
- `backend/app/chat/rewrite.py`, `backend/config/prompts/question_rewriter.v1.yaml`, `backend/config/models.yaml`, `backend/app/config/settings.py` (`ModelSpec.options`, `REWRITER_MAX_CHARS`), `backend/app/models/gateway.py`, `backend/tests/test_rewrite.py`, `backend/tests/fakes.py`

**Decisions**
- JSON schema output: with Ollama's plain JSON mode, qwen3:4b often echoed the history back in some other shape; with the schema, 33/33 smoke answers were well formed.
- Temperature 0 for the rewriter: at the default, the same follow-up got different wordings and once a garbled word ("didn't" → "didn:"); at 0, every case was stable. Per-role Ollama options belong in models.yaml (`options:`), not in code.
- No retry on bad output and a fallback when Ollama is down: the user is waiting, and a literal follow-up is better than an error. The rewriter never raises.
- `rewrite` takes the messages from `last_turns` (Task 5.2) and returns plain text; the chat endpoint (5.6) decides when to call it.

**How to run / test**
- `make test`

**Known issues / TODO**
- Follow-ups in other languages may come back translated to English and unresolved ("qui l'a relu ?" → "Who reviewed it?").
- The rewriter uses the gateway's normal timeout (`OLLAMA_TIMEOUT_SECONDS` = 120 s, 3 tries): if Ollama hangs, the chat waits that long before falling back. Task 10.4 should give chat calls a shorter timeout.

### Task 5.2 — Chat sessions and memory  ✅ done
**Date:** 2026-10-16

**Built**
- `app/api/chat.py` (router `/chat`, every endpoint behind the login):
  - `POST /chat/sessions` `{title?}` → `{id, title, updated_at}` (201).
  - `GET /chat/sessions` → the user's chats, most recently used first.
  - `GET /chat/sessions/{id}/messages` → every message of one of the user's chats, oldest first (`role`, `content`, `sources`, `confidence`, `created_at`).
  - `own_chat(session, user, chat_id)`: the chat if it is the user's, otherwise 404 `Chat not found` (someone else's chat looks like a missing one).
- `app/chat/memory.py`:
  - `add_message(session, chat, role, content)` saves a message and marks the chat as used; the caller commits.
  - `last_turns(session, chat_id, turns=None)` → the messages of the last `CHAT_MEMORY_TURNS` (10) turns, oldest first. A turn is a user message and the replies after it; an unanswered question still counts as one.
- `tests.fakes.login_as(session, username)` creates a user and returns headers with their token; `tests.fakes.api` is the shared TestClient.
- Tests: each user sees only their own chats (list, order by last use, 404 for someone else's or a missing chat, title length); messages saved in one transaction come back in order; with 11 turns (one unanswered) the oldest turn is not loaded, a smaller `turns` works, and a newer message in another chat never leaks in. Checked that the test fails with an off-by-one offset or without either chat filter.

**Key files**
- `backend/app/api/chat.py`, `backend/app/chat/memory.py`, `backend/tests/test_memory.py`, `backend/tests/fakes.py`

**Decisions**
- Order messages by `id`, never `created_at`: messages saved in one transaction share `now()`.
- Turns are counted by user messages, so a missing reply doesn't shift the window.
- `add_message` only flushes: the chat endpoint (5.6) saves a whole turn in one transaction.
- Chat history keeps text, never chunk ids (Task 4.3: chunk ids change when an item is re-learned). Phase 7 puts links and text in `chat_messages.sources`.

**How to run / test**
- `make test`

**Known issues / TODO**
- The chat list isn't paged, and chats can't be renamed or deleted yet (Phase 9 screens).
- Messages are only saved through `add_message` until the chat endpoint arrives in Task 5.6.

### Task 5.1 — Users and login  ✅ done
**Date:** 2026-10-16

**Built**
- `app/api/auth.py`:
  - Passwords: `hash_password` / `verify_password` with the standard library's scrypt (n=2^14, r=8, p=5: OWASP's minimum, 16 MiB; about 0.16 s per check), stored as `scrypt$n$r$p$salt$hash`. A login for an unknown user still runs one scrypt, so the timing doesn't reveal usernames.
  - `POST /auth/login` `{username, password}` → `{token, expires_at}`. The token is 32 random bytes (`secrets.token_urlsafe`); only its SHA-256 is stored, in the new `auth_tokens` table (migration 0003), and it expires after `TOKEN_TTL_HOURS` (12). Expired tokens are deleted at every login. Usernames are case-insensitive (stored lower-case).
  - `current_user` (the `CurrentUser` annotation): `Authorization: Bearer <token>` → the `User`, otherwise 401 `Not authenticated` with `WWW-Authenticate: Bearer`.
  - `POST /auth/logout` deletes the token; `GET /me` returns the username, display name and linked accounts.
  - `add_user` / `link_account` for admins, run by `make add-user` / `make link-account` (`scripts/users.py`, interactive; the password is read with getpass, never passed as an argument). Account ids get a format check per tool, and an account linked to one user can't be linked to another.
- Tests: salted scrypt hashes verify; login → /me → logout; a wrong password and an unknown user get the same answer; only the token's hash is stored; expired tokens stop working and are tidied up; every endpoint in the OpenAPI schema except `/health` and `/auth/login` answers 401 with no token, a made-up token and a non-Bearer header (so later endpoints are covered automatically); the input checks of `add_user` and `link_account`.
- Smoke run (not in the suite) in a throwaway database: `make add-user`, `make link-account` (and a rejected `slack:U01`), login and `/me`. Dev database migrated to 0003.

**Key files**
- `backend/app/api/auth.py`, `backend/migrations/versions/0003_auth_tokens.py`, `backend/app/db/schema.py` (`AuthToken`), `backend/scripts/users.py`, `backend/tests/test_auth.py`

**Decisions**
- Local accounts with a password, as the task asks. Company sign-in is still the user's call for Phase 9; it would hand out the same tokens after its callback.
- Opaque random tokens stored hashed in Postgres, not JWTs: logout and expiry are a row delete and a timestamp, with no signing secret to manage.
- scrypt from the standard library instead of adding argon2-cffi or bcrypt: `security.md` accepts scrypt, and no dependency is added.
- **Only admins link accounts (user decision, 2026-10-16).** From Phase 6 a user's linked accounts decide what they may search, so a self-claimed colleague's account would leak their channels. Users see their links in `/me`. Self-service linking with a real sign-in to each tool (OAuth) can come with the Phase 9 settings screen.
- Admin work is a CLI for now, like connecting a source is a SQL row: there are no admin endpoints, and `users.is_admin` is unused.
- Account ids are stored without the `kind:` prefix and exactly as the connectors write authors (`alice-gh`, a Jira accountId, `U0123ABC`), so `link_identities` (Task 4.1) finds their person entities.
- New endpoints take `user: CurrentUser` and `session: DB` (both from `app/api/auth.py`) and must check that what they touch belongs to `user`.
- FastAPI 0.143 keeps an included router as one `_IncludedRouter` entry in `app.routes`; list endpoints with `app.openapi()["paths"]` instead.

**How to run / test**
- `make migrate` (new migration 0003) · `make add-user` · `make link-account` · `make test` (106 pass)

**Known issues / TODO**
- No login rate limit or lockout in the app. `security-audit.md` §7 puts it on the reverse proxy (nginx `limit_req zone=login rate=5r/m`) for Phase 9; until then the API listens on 127.0.0.1 only, and each guess costs a 0.16 s scrypt.
- No password change or reset, and deleting a user or unlinking an account is SQL only (deleting a user cascades to their tokens, accounts and chats).
- `users.is_admin` isn't used yet: the admin is whoever can run the CLI on the server.

### Docs pass (not a phase task)  ✅ done
**Date:** 2026-10-16

**Built**
- `decision.md`: every choice made in Phases 0–4, what else was possible and why, plus the decisions still waiting for the user.
- `flow.md`: how data moves through the system end to end: the learning run step by step, what each table holds, a worked example, what happens on later changes, and the planned chat side.
- Every markdown table turned into short paragraphs or lists (`guide.md`, `agent.md`, `description.md`, `phases.md`, `security-audit.md`); content unchanged. `security.md` now asks auditors for lists instead of tables. `README.md`, `guide.md` and `agent.md` link the two new files.

**Key files**
- `decision.md`, `flow.md`, `agent.md`

**Decisions**
- No markdown tables in the docs (user preference): short paragraphs of 2–3 lines, or simple lists.
- Keep `flow.md` and `decision.md` current: a task that changes how data moves updates `flow.md`, and each real choice between alternatives is added to `decision.md` as well as to the log (`agent.md` §4 step 7).

**How to run / test**
- Docs only; no code changed.

**Known issues / TODO**
- `security-audit.md` is a snapshot from 2026-10-15. A few lines predate Phases 3–4 (e.g. "no LLM reads ingested text yet", "one initial migration"); the next audit run refreshes them.

### Task 4.4 — Learning pipeline orchestration  ✅ done
**Date:** 2026-10-16

**Built**
- `app/learning/pipeline.py`: `learn(session_factory, build, classify, client) -> counts` is one learning run. It calls `sync_all_sources` (connectors + Presidio), then `triage_new_items`. Then, for every conversation that has a new or failed item: chunk → GLiNER → decision reader → embed → `save_chunks` (4.3) → `write_graph` (4.2, linking with 4.1) → items `processed`. Finally it runs `link_identities`, logs and returns `{"sources", "noise", "learned", "failed"}`.
  - A conversation is a root item (PR, issue, Jira issue, Slack thread or message, or a commit) plus its non-noise replies, oldest first. A reply whose parent is missing or noise is a conversation of its own.
  - Each conversation is one transaction. The model calls come first, each taking all of its chunks in one batch; then its chunks and graph are replaced. A failure (Ollama down, a model error, a DB error) rolls the conversation back, marks its unprocessed items `failed` and logs the traceback; the other conversations continue. Failed items are retried on the next run.
  - Items that triage marks noise lose their chunks, links and decisions (an edit can turn a useful message into "+1").
- The worker's job is now `learn` (it was `sync_sources`), still every `SYNC_INTERVAL_MINUTES` with a first run at start.
- `find_entities`: GLiNER no longer sees Slack mention markup (it reported `<@U03>` as a person "U03"); it gets the mention's label, if any, instead.
- Tests (mocked sources, triage classifier and Ollama; real Presidio, GLiNER, embedder and SBERT):
  - One run fills items, chunks (all embedded), entities, aliases, links and decisions; the PR's `PaymentService` and the Slack thread's `payments-svc` are one entity. A second run with no new data changes no row and asks no model.
  - A conversation whose Ollama call fails is rolled back while the others are stored, and is learned on the next run.
  - A new review re-learns its PR: the decision is replaced, not added twice. A thread edited down to "+1" is forgotten.
  - Checked that the tests fail without the noise clean-up, or when replies are left out of conversations.
- Smoke run (not part of the suite) with the real triage model and qwen3:8b, on the same sample in a throwaway database: both decisions read correctly with the right people, `thanks!` dropped as noise. First run 35 s including model loading, second run 0.0 s.

**Key files**
- `backend/app/learning/pipeline.py`, `backend/app/jobs/scheduler.py`, `backend/app/learning/entities.py`, `backend/tests/test_pipeline.py`, `backend/tests/test_jobs.py`, `backend/tests/fakes.py` (`Feed`, `graph_links`)

**Decisions**
- The unit of work is the conversation, re-learned whole whenever any of its items is new. That is the simplest way to keep decisions (which need the whole thread) and "replace what these items said" correct. The cost: an active PR's older comments are chunked and embedded again.
- Batching: triage classifies all new items in one call; GLiNER and the embedder take one conversation's chunks per call. Conversations aren't batched together, because the decision reader's LLM call dominates the time anyway.
- `items.status`: `new` → `processed` | `noise` | `failed` (failed = retried next run). `learn()` doesn't raise for one bad conversation; it raises only if sync or triage fails as a whole (e.g. no trained triage model: `make train-triage`).
- Tests inject `session_factory=`, `build=`, `classify=` and `client=` (no monkeypatching). `tests.fakes.Feed` is a connector for any external ids; `tests.fakes.graph_links` reads the graph as readable triples.

**How to run / test**
- `make worker` (needs Ollama running and `make train-triage` done) · `make test`

**Known issues / TODO**
- A failing conversation is retried on every run with no limit; add an attempts counter if one keeps failing (each retry may cost an LLM call).
- Triage loads every new item into memory at once; a first sync of hundreds of thousands of items would need paging.
- If Ollama hangs instead of refusing connections, each long conversation waits up to `OLLAMA_TIMEOUT_SECONDS` × 3 before it fails.
- When a reply turns into noise, its conversation's decision isn't re-read until the conversation changes again.
- gliner_small also tags noise as people (`consumer` in a commit message, `fyi` in Slack), and those become person entities. A bigger GLiNER (Task 3.1 note) or a stopword list would help.

### Task 4.3 — Search indexes  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/index.py`: `save_chunks(session, item_ids, chunks, vectors) -> [Chunk]` replaces the chunks of those items with the new chunks and their vectors, and flushes so the rows have ids (the graph's `mentions` links need them). Saving a row is indexing it: `chunks.vector` is in the pgvector HNSW index (cosine) and `chunks.tsv` (generated from the text) in the GIN full-text index, both from migration 0001.
- Tests: three items (a PR, a Jira issue, a Slack message) chunked, embedded with the real embedder and saved. A raw `ORDER BY vector <=> :q` query with a paraphrased question returns the PR's chunk, and a raw `tsv @@ websearch_to_tsquery(...)` query for "refunds" returns the Jira chunk (stemmed from "refund"). With `enable_seqscan` off, `EXPLAIN` shows each query using `ix_chunks_vector_hnsw` / `ix_chunks_tsv`. Saving again replaces instead of duplicating, and saving no chunks for an item removes its old ones.

**Key files**
- `backend/app/learning/index.py`, `backend/tests/test_index.py`

**Decisions**
- An item's chunks are always replaced as a whole (delete, then insert), so chunk ids change when an item is reprocessed. Nothing may keep chunk ids across learning runs: graph links to chunks are rewritten in the same transaction (Task 4.2), and chat history (Phase 7) should store links and text, not chunk ids.
- Search queries must use the operators the indexes were built for: `<=>` (cosine, `vector_cosine_ops`) for vectors, and `tsv @@ <tsquery built with the 'english' config>` for keywords.
- No index tuning here (HNSW `m=16`, `ef_construction=64`, default `ef_search=40`); Task 10.4 measures it.

**How to run / test**
- `make test`

**Known issues / TODO**
- The 'english' config splits and stems identifiers: `retry_limit` is stored as `retri` + `limit`, `PAY-1234` as `pay` + `-1234`. Ticket ids still match exactly through `websearch_to_tsquery` (it builds the phrase `'pay' <-> '-1234'`; `PAY-1235` doesn't match), but `retry_limit` also matches `retry limits`. Task 6.3 decides whether that is good enough.

### Task 4.2 — Knowledge graph writer  ✅ done
**Date:** 2026-10-15

**Built**
- `app/learning/graph.py`: `write_graph(session, conversation, chunks, found, decision)` saves what one conversation (the root item, then its replies) says:
  - person **authored** item (every item's author, and everyone who wrote in a Slack thread); person **reviewed** PR (the authors of its review items, except the PR's own author); chunk **mentions** entity (GLiNER hits and Slack mentions, linked by Task 4.1); person **decided** decision; decision **about** entity (the services, tools and projects whose key appears in the decision or its reason).
  - At most one `decisions` row per root: `link` = the root's link, `decided_at` = the conversation's last activity, `people` = the deciders.
  - It first deletes the links learned from these items and their decisions, so re-running (or re-reading a decision) replaces instead of duplicating. A link that appears twice in one write is stored once (`ON CONFLICT DO NOTHING` on the unique 5-tuple).
- Migration `0002`: `edges.item_id` cascades with its item (it was SET NULL) and is indexed. Deleting an item or a source now deletes the links learned from it.
- `link.keys_in(text)`: the key of every run of up to 6 words in a text, i.e. which names it may mention. `triage.is_bot(author)` is shared by triage and the writer (bots are never people).
- Test: a PR (with bob's approving review and alice's reply on her own PR) and a Slack thread (with a bot line and a `<@U03>` mention), written twice: the expected 21 links and 8 entities exist exactly once. A re-read without a decision removes the old decision and its links; deleting the Slack source removes everything learned from it. Checked that the test fails without the delete-first step or the conflict handling.

**Key files**
- `backend/app/learning/graph.py`, `backend/migrations/versions/0002_edges_cascade_with_item.py`, `backend/app/db/schema.py`, `backend/app/learning/link.py`, `backend/app/learning/triage.py`, `backend/tests/test_graph.py`

**Decisions**
- Every link carries the item it was learned from (`edges.item_id`): the item itself for authored and mentions, the review for reviewed, the root for decided and about. "Replace what these items said" is then one delete, and deletion cascades.
- The unit of writing is a conversation (Task 3.3 contract: root first, then its non-noise replies, oldest first). Task 4.4 must pass the whole conversation, with the chunks of all its items, whenever any member changes.
- Directions: person → item (authored, reviewed), chunk → entity (mentions), person → decision (decided), decision → entity (about). Graph search (Task 6.4) follows them both ways.
- `decisions.people` holds account ids, the same ones the `decided` links resolve; readable names come from aliases.
- `owns` and `depends_on` are not written: nothing extracts them yet (GLiNER finds entities, not relations, and the decision reader returns only decision / reason / people).

**How to run / test**
- `make migrate` (new migration 0002) · `make test`

**Known issues / TODO**
- An "about" link needs GLiNER to have found the entity somewhere in the conversation; a service named only in the decision text gets none.
- Entities and person aliases stay when their last link goes (a deleted source's people keep their account aliases). Per-user deletion (Phase 9) must delete person entities by account alias.
- Slack thread repliers are linked as `authored` to the whole thread (each wrote part of it).

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
