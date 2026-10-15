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

| # | Risk | Status |
|---|---|---|
| 1 | **Jira JQL injection.** A source id like `PAY" OR project = "HR` pulled other projects' tickets and tagged them as `PAY`, so people who can see PAY would see HR data. | **Fixed** |
| 2 | **GitHub path traversal.** A source id like `../user` hit `/user/issues`, which returns issues from every repo the token can see, under a harmless-looking tag. | **Fixed** |
| 3 | **API has no authentication** and compose published it on every network interface. | **Mitigated:** bound to `127.0.0.1`. Real auth is Phase 9. |
| 4 | **Supply chain.** Model weights weren't pinned, so whatever was pushed to the repo got downloaded. Python deps have no lock file. | **Models pinned.** Lock file is still open. |
| 5 | **No security headers, a public Swagger page in production, and the server version leaked.** | **Fixed** |

There are **no real secrets** in the code or anywhere in the git history (details in §3).

---

## 2. Findings

Status: ✅ PASS · ❌ FAIL → 🔧 fixed · ⚠️ open · ➖ N/A

| ID | Area | Vulnerability | Severity | File:Line | Status | Fix |
|---|---|---|---|---|---|---|
| S-01 | Backend | JQL injection through `sources.external_id` | **High** | `app/learning/connectors/jira.py:126` | 🔧 | Ids validated in `build_connector` (`app/learning/connectors/__init__.py:15`) |
| S-02 | Backend | Path traversal in GitHub API paths through `external_id` | **High** | `app/learning/connectors/github.py:108` | 🔧 | Same allowlist regex |
| S-03 | Backend | Slack id not validated (could name a DM channel) | Low | `app/learning/connectors/slack.py:100` | 🔧 | Only `C…` / `G…` channel ids |
| S-04 | Backend | GitHub paging followed any `Link: next` URL, sending the token there | Medium | `app/learning/connectors/github.py:90` | 🔧 | Refuses to leave the API host |
| S-05 | Infra | API port published on `0.0.0.0` with no auth | **High** | `docker-compose.yml` `api.ports` | 🔧 | `127.0.0.1:` + TLS reverse proxy |
| S-06 | Backend | No security headers / CSP | Medium | `app/api/main.py` | 🔧 | Middleware on every response |
| S-07 | Backend | Swagger / OpenAPI public in production | Medium | `app/api/main.py` | 🔧 | `API_DOCS` setting, default **off**; compose forces it off |
| S-08 | Backend | No generic 500 / correlation id | Low | `app/api/main.py` | 🔧 | `{"detail","request_id"}` + `X-Request-ID`; details only in the server log |
| S-09 | Infra | `server: uvicorn` header leaks the server software | Low | `Dockerfile` CMD, compose `api.command` | 🔧 | `--no-server-header` |
| S-10 | Infra | Model weights not pinned | Medium | `config/models.yaml` | 🔧 | Exact commit hash per HF model (gated Prompt Guard pinned once downloaded) |
| S-11 | Infra | No Python lock file: image builds resolve the latest deps | Medium | `Dockerfile:21`, `pyproject.toml` | ⚠️ | §8 "fix this sprint" |
| S-12 | Infra | Containers could gain privileges (setuid) | Low | `docker-compose.yml` | 🔧 | `no-new-privileges:true` on api + worker |
| S-13 | Infra | Build context included `.git` | Low | `.dockerignore` | 🔧 | `.git` excluded |
| S-14 | Backend | `CREATE DATABASE` built with an f-string | Low | `scripts/init_local_db.py:24` | 🔧 | `psycopg.sql.Identifier` |
| S-15 | Data | `.env.example` missed `SLACK_API_URL`; no TLS note for remote DBs | Low | `.env.example` | 🔧 | Added both |
| S-16 | Infra | `ollama` container runs as root (upstream image) | Low | `docker-compose.yml` `ollama` | ⚠️ | Not published on any port; accept or run rootless later |
| S-17 | Infra | `pgvector/pgvector:pg17` tag not pinned to a digest | Low | `docker-compose.yml` | ⚠️ | Pin `@sha256:` on the deploy host |
| S-18 | Backend | Outbound retries have no backoff or jitter; 5xx not retried | Low | `gateway.py:93`, connectors `_get` | ⚠️ | Fix later |
| S-19 | Data | Old local-dev DB password `syncra` in git history | Low | commits before `c858982` | ⚠️ | Never use it anywhere (README warning added) |

### Full checklist (every item)

**§1 Secrets**
| Item | Status | Notes |
|---|---|---|
| No secret literals in source / config / comments | ✅ | Only fake test values in `tests/test_scrub.py` (they must look real to test the scrubber; the Slack one is split so scanners don't fire) |
| Supabase / Stripe / Razorpay keys | ➖ | Not used |
| DB connection string only in env | ✅ | `DATABASE_URL`; compose builds it from `POSTGRES_PASSWORD`, which is required (`:?`) |
| OAuth / JWT secrets | ➖ | No auth yet (Phase 9) |
| Third-party keys (GitHub, Jira, Slack, HF) in env | ✅ | `settings.py`, all optional and `None` by default |
| `NEXT_PUBLIC_` / `REACT_APP_` / `VITE_` exposure | ➖ | No frontend |
| `.env` git-ignored, `.env.example` complete | 🔧 | Ignored at the root and in `.dockerignore`; `.env.example` completed |
| No secrets in Docker images or logs | ✅ | `.env` not copied (dockerignore); compose uses `env_file` at runtime. Logs print counts, cursors and model names only |
| Git history scan | ✅ | Regex scan for Slack/GitHub/AWS/OpenAI/HF/Atlassian tokens, private keys and URLs with passwords across all commits: only fakes and the old local dev password (S-19). `gitleaks` isn't installed; GitHub push protection is on for the repo and already caught the fake Slack token |

**§2 Personal data**: see the map in §4.
| Item | Status | Notes |
|---|---|---|
| Collection points mapped | ✅ | §4 |
| Logs free of personal data | ✅ | `sync.py:103` logs kind/name/counts/cursor; connector logs name repo/project/channel only; `last_error` holds the exception text (URLs, not tokens) |
| Third parties get only what they need | ✅ | GitHub/Jira/Slack receive only API reads; Ollama and HF run locally; nothing is sent to hosted LLMs |
| Password hashing | ➖ | No passwords stored (Phase 9: argon2/bcrypt) |
| Cookies / localStorage | ➖ | No frontend |
| Response filtering | ✅ | Only `/health` |
| Data deletion | ➖ / ⚠️ | No user accounts yet. Deleting a `sources` row cascades to its items, chunks, decisions and graph links (links since migration 0002). Phase 9 must add per-user deletion (FKs already `ON DELETE CASCADE` on `users`), including the person entities whose aliases are that user's accounts |

**§3 Frontend:** every item is ➖ **N/A (no frontend until Phase 9)**. XSS, CSRF, CORS, CSP, clickjacking, open redirects, token storage, OAuth/PKCE, HTTPS/mixed content, WebSocket/SSE auth, UI rate limiting, `npm audit`/SRI and error display are all in the "must do when built" list.

**§4 Backend**
| Item | Status | Notes |
|---|---|---|
| SQL injection | ✅ | ORM / `insert().values()` everywhere; only raw SQL is `CREATE DATABASE` (S-14, fixed) and the test-only `TRUNCATE` from metadata names |
| SSRF | ✅ | Outbound hosts come only from operator env (`GITHUB_API_URL`, `JIRA_BASE_URL`, `SLACK_API_URL`), not from users; paging host pinned (S-04) |
| Input validation | 🔧 | Source ids (S-01..03); connector payloads parsed with pydantic `RawItem`; `yaml.safe_load`; no `pickle`/`eval`/`subprocess` with input (`pull_ollama_models.py` passes names from our own yaml as an argv list) |
| File uploads | ➖ | None |
| Webhooks | ➖ | None (polling) |
| Auth on every endpoint / IDOR / RBAC / JWT / passwords / reset tokens / default admins | ➖ | No auth yet; `/health` is intentionally public. **Phase 9 blocker:** don't expose the API publicly before this exists |
| Rate limiting | ➖ | No auth / chat endpoints yet. Phase 9 (§7 config) |
| Request size / timeouts / pagination caps | ✅ / ⚠️ | Outbound timeouts 30 s (connectors), 120 s (Ollama); body size limit belongs to the reverse proxy (§7) |
| Backpressure / queues | ✅ | No queue; scheduler `max_instances=1`, `coalesce=True` (`jobs/scheduler.py:37`) |
| Retries / backoff / circuit breaker | ⚠️ | Rate-limit waits honoured; no jitter (S-18) |
| Business logic / payments | ➖ | No payments |
| Race conditions | ✅ | Upsert with `ON CONFLICT … WHERE hash differs` + cursor in one transaction (`sync.py:68`) |
| Idempotency | ✅ | Re-running a sync stores nothing new (content hash) |
| Sagas / pub-sub / DLQ | ➖ | None |
| Cron jobs: no overlap, credentials secure | ✅ | `max_instances=1`; tokens from env |
| Fail fast on missing config | ✅ | `ConfigError` names each missing field (`settings.py:95`); connectors raise if their token is missing |
| Generic errors + correlation id | 🔧 | S-08 |
| Debug code / test endpoints / debug default off | ✅ | No debug endpoints; `--reload` only in `make run` (local); docs off by default (S-07) |
| Security headers | 🔧 | S-06 |
| CORS | ✅ | Not enabled, so browsers block cross-origin calls. Phase 9: explicit frontend origin only |
| Internal exposure (`.env`, `.git`, DB admin, Swagger, health) | 🔧 | API serves no files; Swagger off in prod; `/health` returns only `{"status":"ok"}`; DB bound to `127.0.0.1` |
| TLS in transit / HSTS / at rest | ⚠️ | HSTS header added; TLS termination and disk encryption are on the host (§9 "what I need") |
| DB: TLS, no default creds, least privilege, not public | ✅ / ⚠️ | Password required; port `127.0.0.1` only; same Docker network (TLS not needed). **The app connects as the Postgres superuser.** Create a restricted app role (§8) |
| Migrations safe | ✅ | One initial migration; downgrade drops everything, so never run it in production |
| API versioning | ➖ | One version |

**§5 AI / LLM**
| Item | Status | Notes |
|---|---|---|
| Prompt injection | ➖ | No LLM reads ingested text yet (Phase 3 decision reader, Phase 5 chat). Gateway already separates `system` from `prompt` (`gateway.py:71`) |
| Permission filtering in retrieval | ✅ / ➖ | Every item **must** carry `access_tags` (fail-closed validator, `connectors/base.py:33`); the query-side filter is Phase 6 |
| Scrub before store / embed / LLM | ✅ | `sync_source` scrubs every item before saving (`sync.py:101`) |
| LLM actions need approval | ➖ | Phase 8 |
| Model supply chain | 🔧 | HF revisions pinned (S-10); no `trust_remote_code`; local-only (no hosted APIs) |

**§6 Infra / CI/CD**
| Item | Status | Notes |
|---|---|---|
| CI/CD | ➖ | No CI in repo. GitHub push protection is active |
| Docker non-root / minimal / no baked secrets | ✅ | `python:3.12-slim`, multi-stage, `USER syncra` (uid 1000), `.env` excluded |
| Read-only filesystem | ⚠️ | Not enabled: untested (no local Docker). Try `read_only: true` + `tmpfs: /tmp` on the host |
| Kubernetes / Terraform / Helm | ➖ | Not used |
| Reverse proxy / WAF / DDoS | ⚠️ | Not in repo. Config in §7 |
| DNS / TLS certs | ⚠️ | Need the domain (§9) |
| Feature flags | ➖ | None |
| Rollback | ⚠️ | `alembic upgrade head` on api start; keep migrations backward compatible and back up before deploys |
| Backups / DR | ⚠️ | Nothing in repo. §10 checklist |
| Logs / alerting / incident response | ⚠️ | Logs go to stdout (docker). §10 |
| Fail closed | ✅ | Missing config → no start; untagged item → rejected; failing source → skipped and recorded |

---

## 3. Secrets found

| What | Where | Moved to | Rotate? |
|---|---|---|---|
| Fake Slack/GitHub/AWS tokens, fake private key and password | `backend/tests/test_scrub.py` | Kept: test fixtures for the scrubber. Slack value split | No (not real) |
| Local dev DB password `syncra` | Old commits (Task 0.2 Docker dev setup, removed in `c858982`) | Gone from the code; compose now **requires** `POSTGRES_PASSWORD` | Never reuse it |
| Real tokens / passwords | Nowhere in code or history | `backend/.env` (git-ignored) | Rotate if a real one is ever committed |

## 4. Personal-data map

| Data | Enters at | Stored in | Sent externally | Protection |
|---|---|---|---|---|
| Emails, phones, cards, IBAN, SSN, IPs in message text | GitHub/Jira/Slack connectors | `items.text/title` | Nowhere | Replaced with `<EMAIL_ADDRESS>` etc. **before** storage (`scrub.py`) |
| Secrets pasted into messages (tokens, keys, connection strings, JWTs) | same | `items` | Nowhere | Same, replaced with `<SLACK_TOKEN>` etc. |
| Person names (authors, assignee display names) | connectors | `items.author` (`github:login`, `jira:<accountId>`, `slack:<userId>`), Jira assignee name in `items.text` | Nowhere | Kept on purpose ("who built X" is the product). Covered by per-source deletion |
| Links to source items | connectors | `items.link` | Nowhere | Point back to the original permission-controlled system |
| Jira account email + API token, GitHub/Slack tokens | `.env` | Process memory only | Their own API, in auth headers | Never logged or stored in the DB |
| Users, chat history, actions | (Phase 5–9) | `users`, `chat_*`, `actions` | Nowhere (local LLMs) | Cascade delete per user is ready in the schema |

---

## 5. Attack paths (Critical / High)

**S-01 JQL injection.** An attacker who can add or edit a source (today: DB access; Phase 9: the "connect a source" UI) sets the Jira key to `PAY" OR project = "HR`. The worker builds `project = "PAY" OR project = "HR"` and stores every HR ticket tagged `jira:project:PAY`. Anyone allowed to see PAY can then read salaries, performance reviews and other HR tickets through chat. **Damage:** a cross-project data leak that the permission model can't catch. **Fix:** strict key regex, below.

**S-02 GitHub path traversal.** The repo is set to `../user` (or `acme/../../orgs/acme`). The calls become `/user/issues` etc. and return issues from **every** repo the token can reach, tagged `github:repo:../user`. **Damage:** private-repo data leaks under a tag that may be granted broadly. **Fix:** owner/repo regex, and `.`/`..` rejected as the repo name.

**S-05 Unauthenticated API on a public port.** As soon as Phase 5 adds `/chat`, anyone who can reach the port can query the whole company memory. **Fix:** port bound to localhost; publish only through a TLS proxy, and only once auth exists.

## 6. Corrected code (what changed)

`backend/app/learning/connectors/__init__.py`:
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

`backend/app/learning/connectors/github.py` (paging):
```python
next_url = response.links.get("next", {}).get("url")
if next_url and httpx.URL(next_url).host not in ("", self._origin):
    raise RuntimeError(f"GitHub paging left {self._origin}; not sending the token")
```

`backend/app/api/main.py`: a security middleware adds the headers, a strict CSP (none on `/docs`), `X-Request-ID`, and a generic 500 `{"detail": "Internal server error", "request_id": …}`. Docs are controlled by `API_DOCS` (default `False`).

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
