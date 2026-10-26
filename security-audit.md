# Syncra Security Audit

**Date:** 2026-10-15 · **Scope:** whole repo + full git history, branch `njr` (= `development`) · **Checklist:** [`security.md`](security.md)

## What the app is today

Most of the checklist can't apply yet, because the features it checks haven't been built. Today Syncra is:

- **API:** one endpoint, `GET /health`. No login, no users, no chat endpoint, no uploads, no payments.
- **Worker:** pulls GitHub, Jira and Slack every 15 minutes, scrubs personal data and secrets with Presidio, and stores the result in Postgres.
- **Frontend:** none (`frontend/` holds only a placeholder; the UI is Phase 9).
- **Deployment:** a Dockerfile and docker-compose for one Linux host. No CI, Kubernetes, Terraform or reverse proxy in the repo.

Items for features that don't exist yet are marked **N/A (later phase)**. Each one also says what that phase must do.
Those are the **"must do when built"** list at the end. Treat it as a requirement for Phases 5–9.

---

## 1. Executive summary: top 5 risks

1. **Jira JQL injection.** A source id like `PAY" OR project = "HR` pulled other projects' tickets and tagged them as `PAY`, so people who can see PAY would see HR data. **Status: fixed.**
2. **GitHub path traversal.** A source id like `../user` hit `/user/issues`, which returns issues from every repo the token can see, under a harmless-looking tag. **Status: fixed.**
3. **API has no authentication**, and compose published it on every network interface. **Status: mitigated.** It is bound to `127.0.0.1`; real auth is Phase 9.
4. **Supply chain.** Model weights weren't pinned, so whatever was pushed to the repo got downloaded, and Python deps have no lock file. **Status: models pinned;** the lock file is still open.
5. **No security headers, a public Swagger page in production, and the server version leaked.** **Status: fixed.**

There are **no real secrets** in the code or anywhere in the git history (details in §3).

---

## 2. Findings

Status: ✅ PASS · ❌ FAIL → 🔧 fixed · ⚠️ open · ➖ N/A

**S-01 · Backend · High · 🔧 fixed.** JQL injection through `sources.external_id`, at `app/connectors/jira.py:126`. Fix: ids are validated in `build_connector` (`app/connectors/__init__.py:15`).

**S-02 · Backend · High · 🔧 fixed.** Path traversal in GitHub API paths through `external_id`, at `app/connectors/github.py:108`. Fix: the same allowlist regex.

**S-03 · Backend · Low · 🔧 fixed.** The Slack id wasn't validated, so it could name a DM channel (`app/connectors/slack.py:100`). Fix: only `C…` / `G…` channel ids are accepted.

**S-04 · Backend · Medium · 🔧 fixed.** GitHub paging followed any `Link: next` URL, sending the token there (`app/connectors/github.py:90`). Fix: paging refuses to leave the API host.

**S-05 · Infra · High · 🔧 fixed.** The API port was published on `0.0.0.0` with no auth (`docker-compose.yml`, `api.ports`). Fix: `127.0.0.1:` plus a TLS reverse proxy.

**S-06 · Backend · Medium · 🔧 fixed.** No security headers or CSP (`app/main.py`). Fix: middleware on every response.

**S-07 · Backend · Medium · 🔧 fixed.** Swagger / OpenAPI was public in production (`app/main.py`). Fix: the `API_DOCS` setting, default **off**; compose forces it off.

**S-08 · Backend · Low · 🔧 fixed.** No generic 500 and no correlation id (`app/main.py`). Fix: `{"detail","request_id"}` plus `X-Request-ID`; details only go to the server log.

**S-09 · Infra · Low · 🔧 fixed.** The `server: uvicorn` header leaked the server software (`Dockerfile` CMD, compose `api.command`). Fix: `--no-server-header`.

**S-10 · Infra · Medium · 🔧 fixed.** Model weights weren't pinned (`config/models.yaml`). Fix: an exact commit hash per HF model (the gated Prompt Guard is pinned once downloaded).

**S-11 · Infra · Medium · ⚠️ open.** No Python lock file, so image builds resolve the latest deps (`Dockerfile:21`, `pyproject.toml`). Fix: §8 "fix this sprint".

**S-12 · Infra · Low · 🔧 fixed.** Containers could gain privileges through setuid (`docker-compose.yml`). Fix: `no-new-privileges:true` on api and worker.

**S-13 · Infra · Low · 🔧 fixed.** The build context included `.git` (`.dockerignore`). Fix: `.git` excluded.

**S-14 · Backend · Low · 🔧 fixed.** `CREATE DATABASE` was built with an f-string (`scripts/init_local_db.py:24`). Fix: `psycopg.sql.Identifier`.

**S-15 · Data · Low · 🔧 fixed.** `.env.example` missed `SLACK_API_URL` and had no TLS note for remote DBs (`.env.example`). Fix: added both.

**S-16 · Infra · Low · ⚠️ open.** The `ollama` container runs as root, as the upstream image does (`docker-compose.yml`, `ollama`). It isn't published on any port: accept it, or run it rootless later.

**S-17 · Infra · Low · ⚠️ open.** The `pgvector/pgvector:pg17` tag isn't pinned to a digest (`docker-compose.yml`). Fix: pin `@sha256:` on the deploy host.

**S-18 · Backend · Low · ⚠️ open.** Outbound retries have no backoff or jitter, and 5xx errors aren't retried (`gateway.py:93`, the connectors' `_get`). Fix later.

**S-19 · Data · Low · ⚠️ open.** The old local-dev DB password `syncra` is in git history (commits before `c858982`). Never use it anywhere (README warning added).

### Full checklist (every item)

**§1 Secrets**

- ✅ **No secret literals in source / config / comments.** Only fake test values in `tests/test_scrub.py`. They must look real to test the scrubber, and the Slack one is split so scanners don't fire.
- ➖ **Supabase / Stripe / Razorpay keys.** Not used.
- ✅ **DB connection string only in env.** `DATABASE_URL`; compose builds it from `POSTGRES_PASSWORD`, which is required (`:?`).
- ➖ **OAuth / JWT secrets.** No auth yet (Phase 9).
- ✅ **Third-party keys (GitHub, Jira, Slack, HF) in env.** In `settings.py`, all optional and `None` by default.
- ➖ **`NEXT_PUBLIC_` / `REACT_APP_` / `VITE_` exposure.** No frontend.
- 🔧 **`.env` git-ignored, `.env.example` complete.** Ignored at the root and in `.dockerignore`; `.env.example` completed.
- ✅ **No secrets in Docker images or logs.** `.env` isn't copied (dockerignore), and compose uses `env_file` at runtime. Logs print counts, cursors and model names only.
- ✅ **Git history scan.** A regex scan of all commits for Slack/GitHub/AWS/OpenAI/HF/Atlassian tokens, private keys and URLs with passwords found only fakes and the old local dev password (S-19). `gitleaks` isn't installed; GitHub push protection is on for the repo and already caught the fake Slack token.

**§2 Personal data** (see the map in §4)

- ✅ **Collection points mapped.** See §4.
- ✅ **Logs free of personal data.** `sync.py:103` logs kind, name, counts and cursor; connector logs name only the repo, project or channel; `last_error` holds the exception text (URLs, not tokens).
- ✅ **Third parties get only what they need.** GitHub, Jira and Slack receive only API reads; Ollama and HF run locally; nothing is sent to hosted LLMs.
- ➖ **Password hashing.** No passwords are stored (Phase 9: argon2/bcrypt).
- ➖ **Cookies / localStorage.** No frontend.
- ✅ **Response filtering.** Only `/health`.
- ➖ / ⚠️ **Data deletion.** No user accounts yet. Deleting a `sources` row cascades to its items, chunks, decisions and graph links (links since migration 0002). Phase 9 must add per-user deletion (FKs are already `ON DELETE CASCADE` on `users`), including the person entities whose aliases are that user's accounts.

**§3 Frontend:** every item is ➖ **N/A (no frontend until Phase 9)**. XSS, CSRF, CORS, CSP, clickjacking, open redirects, token storage, OAuth/PKCE, HTTPS/mixed content, WebSocket/SSE auth, UI rate limiting, `npm audit`/SRI and error display are all in the "must do when built" list.

**§4 Backend**

- ✅ **SQL injection.** ORM / `insert().values()` everywhere. The only raw SQL is `CREATE DATABASE` (S-14, fixed) and the test-only `TRUNCATE` built from metadata names.
- ✅ **SSRF.** Outbound hosts come only from operator env (`GITHUB_API_URL`, `JIRA_BASE_URL`, `SLACK_API_URL`), not from users, and the paging host is pinned (S-04).
- 🔧 **Input validation.** Source ids (S-01..03); connector payloads parsed with pydantic `RawItem`; `yaml.safe_load`; no `pickle`/`eval`/`subprocess` with input (`pull_ollama_models.py` passes names from our own yaml as an argv list).
- ➖ **File uploads.** None.
- ➖ **Webhooks.** None (polling).
- ➖ **Auth on every endpoint / IDOR / RBAC / JWT / passwords / reset tokens / default admins.** No auth yet; `/health` is intentionally public. **Phase 9 blocker:** don't expose the API publicly before this exists.
- ➖ **Rate limiting.** No auth or chat endpoints yet. Phase 9 (§7 config).
- ✅ / ⚠️ **Request size / timeouts / pagination caps.** Outbound timeouts are 30 s (connectors) and 120 s (Ollama); the body size limit belongs to the reverse proxy (§7).
- ✅ **Backpressure / queues.** No queue; the scheduler has `max_instances=1`, `coalesce=True` (`jobs/scheduler.py:37`).
- ⚠️ **Retries / backoff / circuit breaker.** Rate-limit waits are honoured, but there's no jitter (S-18).
- ➖ **Business logic / payments.** No payments.
- ✅ **Race conditions.** Upsert with `ON CONFLICT … WHERE hash differs`, plus the cursor, in one transaction (`sync.py:68`).
- ✅ **Idempotency.** Re-running a sync stores nothing new (content hash).
- ➖ **Sagas / pub-sub / DLQ.** None.
- ✅ **Cron jobs: no overlap, credentials secure.** `max_instances=1`; tokens from env.
- ✅ **Fail fast on missing config.** `ConfigError` names each missing field (`settings.py:95`), and connectors raise if their token is missing.
- 🔧 **Generic errors + correlation id.** S-08.
- ✅ **Debug code / test endpoints / debug default off.** No debug endpoints; `--reload` only in `make run` (local); docs off by default (S-07).
- 🔧 **Security headers.** S-06.
- ✅ **CORS.** Not enabled, so browsers block cross-origin calls. Phase 9: explicit frontend origin only.
- 🔧 **Internal exposure (`.env`, `.git`, DB admin, Swagger, health).** The API serves no files, Swagger is off in prod, `/health` returns only `{"status":"ok"}`, and the DB is bound to `127.0.0.1`.
- ⚠️ **TLS in transit / HSTS / at rest.** HSTS header added; TLS termination and disk encryption are on the host (§9 "what I need").
- ✅ / ⚠️ **DB: TLS, no default creds, least privilege, not public.** Password required, port on `127.0.0.1` only, same Docker network (TLS not needed). **The app connects as the Postgres superuser:** create a restricted app role (§8).
- ✅ **Migrations safe.** One initial migration; downgrade drops everything, so never run it in production.
- ➖ **API versioning.** One version.

**§5 AI / LLM**

- ➖ **Prompt injection.** No LLM reads ingested text yet (Phase 3 decision reader, Phase 5 chat). The gateway already separates `system` from `prompt` (`gateway.py:71`).
- ✅ / ➖ **Permission filtering in retrieval.** Every item **must** carry `access_tags` (fail-closed validator, `connectors/base.py:33`); the query-side filter is Phase 6.
- ✅ **Scrub before store / embed / LLM.** `sync_source` scrubs every item before saving (`sync.py:101`).
- ➖ **LLM actions need approval.** Phase 8.
- 🔧 **Model supply chain.** HF revisions pinned (S-10); no `trust_remote_code`; local-only (no hosted APIs).

**§6 Infra / CI/CD**

- ➖ **CI/CD.** No CI in the repo. GitHub push protection is active.
- ✅ **Docker non-root / minimal / no baked secrets.** `python:3.12-slim`, multi-stage, `USER syncra` (uid 1000), `.env` excluded.
- ⚠️ **Read-only filesystem.** Not enabled, because it's untested (no local Docker). Try `read_only: true` + `tmpfs: /tmp` on the host.
- ➖ **Kubernetes / Terraform / Helm.** Not used.
- ⚠️ **Reverse proxy / WAF / DDoS.** Not in the repo. Config in §7.
- ⚠️ **DNS / TLS certs.** Needs the domain (§9).
- ➖ **Feature flags.** None.
- ⚠️ **Rollback.** `alembic upgrade head` runs on api start; keep migrations backward compatible and back up before deploys.
- ⚠️ **Backups / DR.** Nothing in the repo. §10 checklist.
- ⚠️ **Logs / alerting / incident response.** Logs go to stdout (docker). §10.
- ✅ **Fail closed.** Missing config → no start; untagged item → rejected; failing source → skipped and recorded.

---

## 3. Secrets found

**Fake Slack/GitHub/AWS tokens, a fake private key and a fake password**, in `backend/tests/test_scrub.py`. Kept as test fixtures for the scrubber, with the Slack value split. Rotate? No, they're not real.

**The local dev DB password `syncra`**, in old commits (the Task 0.2 Docker dev setup, removed in `c858982`). It's gone from the code, and compose now **requires** `POSTGRES_PASSWORD`. Rotate? Never reuse it.

**Real tokens and passwords**: nowhere in the code or history. They live in `backend/.env` (git-ignored). Rotate one at once if it's ever committed.

## 4. Personal-data map

**Emails, phones, cards, IBANs, SSNs and IPs in message text** enter through the GitHub, Jira and Slack connectors and would be stored in `items.text` / `items.title`. They're sent nowhere, and they're replaced with `<EMAIL_ADDRESS>` etc. **before** storage (`scrub.py`).

**Secrets pasted into messages** (tokens, keys, connection strings, JWTs) enter the same way and would be stored in `items`. They're sent nowhere, and they're replaced the same way, with `<SLACK_TOKEN>` etc.

**Person names** (authors, assignee display names) come from the connectors. They're stored in `items.author` (`github:login`, `jira:<accountId>`, `slack:<userId>`), plus the Jira assignee name in `items.text`, and sent nowhere. They're kept on purpose ("who built X" is the product) and covered by per-source deletion.

**Links to source items** come from the connectors and are stored in `items.link`, and are sent nowhere. They point back to the original, permission-controlled system.

**The Jira account email and API token, and the GitHub and Slack tokens** come from `.env` and live in process memory only. They're sent only to their own API, in auth headers, and are never logged or stored in the DB.

**Users, chat history and actions** (Phases 5–9) will be stored in `users`, `chat_*` and `actions`, and sent nowhere, because the LLMs are local. Cascade delete per user is ready in the schema.

---

## 5. Attack paths (Critical / High)

**S-01 JQL injection.** An attacker who can add or edit a source (today: DB access; Phase 9: the "connect a source" UI) sets the Jira key to `PAY" OR project = "HR`. The worker builds `project = "PAY" OR project = "HR"` and stores every HR ticket tagged `jira:project:PAY`. Anyone allowed to see PAY can then read salaries, performance reviews and other HR tickets through chat. **Damage:** a cross-project data leak that the permission model can't catch. **Fix:** strict key regex, below.

**S-02 GitHub path traversal.** The repo is set to `../user` (or `acme/../../orgs/acme`). The calls become `/user/issues` etc. and return issues from **every** repo the token can reach, tagged `github:repo:../user`. **Damage:** private-repo data leaks under a tag that may be granted broadly. **Fix:** owner/repo regex, and `.`/`..` rejected as the repo name.

**S-05 Unauthenticated API on a public port.** As soon as Phase 5 adds `/chat`, anyone who can reach the port can query the whole company memory. **Fix:** port bound to localhost; publish only through a TLS proxy, and only once auth exists.

## 6. Corrected code (what changed)

`backend/app/connectors/__init__.py`:
```python
EXTERNAL_ID = {
    "github": re.compile(r"[A-Za-z0-9-]+/(?!\.{1,2}$)[A-Za-z0-9._-]+"),  # owner/repo
    "jira": re.compile(r"[A-Z][A-Z0-9_]+"),  # project key
    "slack": re.compile(r"[CG][A-Z0-9]+"),  # public / private channel id
}

def build_connector(source: Source) -> Connector:
    pattern = EXTERNAL_ID.get(source.kind)
    if pattern and not pattern.fullmatch(source.external_id):
        raise ValueError(f"invalid {source.kind} external_id {source.external_id!r}")
    ...
```
Every scheduled sync goes through `build_connector`, so one check covers all of them. A bad id shows up in `sources.last_error`.

`backend/app/connectors/github.py` (paging):
```python
next_url = response.links.get("next", {}).get("url")
if next_url and httpx.URL(next_url).host not in ("", self._origin):
    raise RuntimeError(f"GitHub paging left {self._origin}; not sending the token")
```

`backend/app/main.py`: a security middleware adds the headers, a strict CSP (none on `/docs`), `X-Request-ID`, and a generic 500 `{"detail": "Internal server error", "request_id": …}`. Docs are controlled by `API_DOCS` (default `False`).

`backend/docker-compose.yml`: `127.0.0.1:${API_PORT}:8000`, `--no-server-header`, `API_DOCS: "false"`, `security_opt: [no-new-privileges:true]`.

`backend/config/models.yaml`: `revision: <commit sha>` on every downloaded HF model.

Tests: `backend/tests/test_security.py` covers crafted ids, the off-host token, headers, the generic 500 and the docs default. 65 tests pass and lint is clean.

## 7. Recommended config

**Reverse proxy (Caddy) on the host.** It handles TLS, HSTS, the size limit and the rate limit. Caddy gets certificates automatically:
```caddyfile
syncra.example.com {
    request_body {
        max_size 1MB
    }
    # needs the caddy-ratelimit plugin; or use nginx limit_req below
    rate_limit {
        zone per_ip {
            key    {remote_host}
            events 60
            window 1m
        }
    }
    reverse_proxy 127.0.0.1:8000
}
```
nginx equivalent: `client_max_body_size 1m; limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;` plus a stricter `zone=login rate=5r/m` on the Phase 9 login route and `3r/h` on password reset.

**Least-privilege DB role** (production, run once as the superuser):
```sql
CREATE ROLE syncra_app LOGIN PASSWORD '<from secrets manager>';
GRANT CONNECT ON DATABASE syncra TO syncra_app;
GRANT USAGE ON SCHEMA public TO syncra_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO syncra_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO syncra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO syncra_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO syncra_app;
```
Run migrations as the owner role, and the API and worker as `syncra_app`.

**Phase 9 additions** (when auth and the frontend land): FastAPI `CORSMiddleware(allow_origins=["https://syncra.example.com"], allow_credentials=True)`; session in an `HttpOnly; Secure; SameSite=Lax` cookie; argon2 (`argon2-cffi`) for any local passwords, or SSO only; rate limiter `slowapi` with 5/min on login and 3/h on reset; frontend CSP `default-src 'self'; script-src 'self'; frame-ancestors 'none'`.

## 8. Remediation plan

**Fix now (done in this pass):** S-01–S-10, S-12–S-15.

**Fix this sprint:**
1. **Lock file (S-11):** `pip-compile --generate-hashes` (or `uv pip compile`) to produce `requirements.lock`, install it in the Dockerfile with `pip install --require-hashes -r requirements.lock`, then `pip install --no-deps .`.
2. **Restricted DB role** (§7).
3. **Secret scanning in CI / pre-commit:** add a `gitleaks` pre-commit hook and a GitHub Action with `pip-audit` and `trivy image`.
4. Pin `pgvector/pgvector:pg17@sha256:…` (S-17).

**Fix later / with the phase that needs it:**
- Phase 3 / 5: wrap ingested text as quoted data in prompts; never let model output trigger tools without the Phase 8 approval step.
- Phase 6: permission filter **inside** every vector and full-text query (`access_tags && :user_tags`), with a test proving a user without access gets nothing.
- Phase 9: auth (SSO preferred), CORS, CSRF, cookies, rate limits, per-user data deletion, frontend CSP, `npm audit` in CI.
- S-16, S-18, read-only container filesystem.

## 9. What I need from you

- **Deploy target:** host or cloud, domain name, and whether a proxy, load balancer or WAF sits in front.
- **TLS and disk encryption** on that host, and where Postgres backups go.
- **Secrets manager** (or confirmation that a `.env` on the host is acceptable, with `chmod 600`).
- **Auth choice for Phase 9:** company SSO (Google / Okta / GitHub OAuth) or local accounts.

## 10. Post-deployment checklist

- [ ] API reachable **only** through the TLS proxy; `curl http://<host>:8000` from outside fails
- [ ] `https://<domain>/docs` returns 404
- [ ] `docker compose exec postgres` → app connects as `syncra_app`, not the superuser
- [ ] Daily `pg_dump` (encrypted, off-host); **restore tested** once a month
- [ ] Alerts on: worker `sync failed` lines, `sources.last_error` set, 5xx rate, 401/403 spikes (Phase 9)
- [ ] Logs kept 30+ days, shipped off-host (tamper-resistant)
- [ ] **Secret rotation runbook:** revoke at the provider (GitHub / Atlassian / Slack / HF) → new value in `.env` → `docker compose up -d` → check `sources.last_error` is clear. Do it every 90 days, and right away if one leaks
- [ ] Incident runbook: who is on call, how to stop the worker (`docker compose stop worker`), how to purge a leaked item (`DELETE FROM items WHERE …` cascades to chunks)
- [ ] Re-run `security.md` before each phase goes live
