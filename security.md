# Security Audit Prompt

Paste everything below the line into a coding agent before deploying.

---

You are a senior application security engineer who also thinks like an attacker. Before this app
goes live, audit the **entire codebase and its git history** for security vulnerabilities, secret
leaks and personal-data handling problems. **Fix what you can directly in the code**; for anything you
can't fix, give the exact fix.

## Ground rules

- **Do not guess.** Base every finding on code you actually read. If something isn't visible
  (infra config, cloud settings, CI, DNS), list exactly what you need from me.
- **Don't skip any item silently.** Mark every checklist item **PASS / FAIL / NOT APPLICABLE**.
  NOT APPLICABLE needs a reason (e.g. "no payments in this app").
- Every finding needs: **what** the vulnerability is, **where** it is (`file:line`), **how an attacker
  would exploit it**, **how much damage** it could do, and the **exact fix** (corrected code).
- Priority order: **data theft and unauthorized access first**, then secrets, then abuse and logic
  flaws, then hardening.

---

## 1. Secrets

1. **No secret as a string literal anywhere in the source code**: not in code, config files, utility
   functions, comments, tests, Dockerfiles or CI files. This covers API keys, passwords, tokens,
   database URLs and credentials. Move every one to environment variables and show what each was moved to.
2. Check these specifically:
   - **Supabase**: the anon key may be client-side **only if Row Level Security is enabled on every
     table**. The service-role key must **never** appear in client code.
   - **Stripe / Razorpay**: only the publishable key goes client-side. The secret key stays on the server.
   - **Database connection strings** (PostgreSQL, MongoDB, …): env var only, never hardcoded.
   - **OAuth client secrets and JWT signing secrets**: server-side only.
   - **Third-party API keys** (OpenAI, SendGrid, Twilio, Firebase, AWS, GitHub, Jira, Slack, Hugging
     Face, …): all in env vars.
3. **Frontend exposure**: env vars prefixed `NEXT_PUBLIC_`, `REACT_APP_` or `VITE_` are shipped to the
   browser. No sensitive value may use these prefixes. Also check the built client bundle for
   secrets and internal URLs.
4. **`.gitignore` and `.env.example`**: `.env` (and variants) must be git-ignored. `.env.example` must
   list **every** variable the app reads, with placeholders and no real values.
5. **Docker images and logs**: no secrets baked into images (`COPY .env`, `ARG`/`ENV` with secrets)
   or printed in logs or CI output.
6. **Git history**: scan the full history (e.g. `gitleaks` / `trufflehog`). If any secret was ever
   committed, the old value is still in the history. Add a README warning to **rotate every previously
   committed secret immediately**, and explain how to purge the history.

**Deliver:** a list of every secret found, one short paragraph each: what it is, where it was, what it was moved to, and whether to rotate it (yes/no).

---

## 2. Personal data flow

1. **Map every collection point**: emails, phone numbers, passwords, names, addresses, dates of birth,
   payment info, IP addresses, device info, and personal data pulled in from integrations. For each
   one, trace where it **enters → travels → is stored → is sent externally**.
2. **Clean all logs**: check every `console.log`, `print`, logger call and error handler. If any
   outputs emails, passwords, phone numbers, tokens or other personal data, replace that data with
   `[REDACTED]` or remove the log.
3. **Third-party integrations** (analytics, error tracking, payments, email, AI APIs, data-source
   APIs): list exactly what user data each one receives. Strip any field it doesn't need.
4. **Passwords**: hashed with bcrypt, argon2 or scrypt (never MD5/SHA alone). Never stored in
   plaintext, logged, returned in responses, or sent anywhere except the hashing function.
5. **Cookies and storage**: sensitive cookies use `HttpOnly`, `Secure` and `SameSite`. No PII, JWTs or
   secrets in `localStorage` or `sessionStorage`.
6. **Response filtering**: no endpoint returns more than the client needs. No password hashes, no
   internal IDs that aren't needed, no other users' data. Use explicit response schemas.
7. **Data deletion**: users must be able to delete their data. If there's no way, add a basic flow
   that removes or anonymizes all of a user's personal data.

**Deliver:** a complete data map, one short paragraph per kind of data: what is collected, where it's stored, where it's sent, and what you fixed.

---

## 3. Frontend

**Injection and browser attacks**
- **XSS**: find unsafe output (`dangerouslySetInnerHTML`, `innerHTML`, `v-html`, unsanitized user
  content, `javascript:` URLs). Sanitize (e.g. DOMPurify) and encode output.
  Try JavaScript in every text field: usernames, bios, comments, search bars, file names.
- **CSRF**: state-changing requests use CSRF tokens or SameSite cookies. No state changes on GET.
- **CORS**: the frontend talks only to allowed origins. Never a wildcard origin with credentials.
- **Security headers / CSP**: strict CSP, `X-Content-Type-Options`, `X-Frame-Options` /
  `frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`.
- **Clickjacking and open redirects**: validate redirect parameters and restrict iframe embedding.

**Authentication and sessions**
- Token storage: prefer `HttpOnly` + `Secure` + `SameSite` cookies over web storage.
- Logout, token expiry handling, and the silent refresh / rotation flow.
- OAuth: PKCE, `state` validation, redirect URI validation.
- Role checks must happen on the server, not just by hiding UI elements.

**Transport and real-time**
- HTTPS only, no mixed content.
- WebSockets / SSE / long polling: origin validation, auth on connect, and no tokens in URLs or
  query strings on reconnect.
- No sensitive data in URLs, logs or the browser console.

**Robustness**
- Debounce or rate-limit sensitive actions in the UI (login, OTP, reset). Real enforcement is on the server.
- Dependencies: `npm audit` / lockfile review, typosquatted packages, Subresource Integrity on
  third-party scripts.
- Errors never show stack traces or sensitive information to users. Check for memory leaks.

---

## 4. Backend

**Input and injection**
- **SQL injection**: no string-concatenated or f-string SQL. Use parameterized queries or the ORM
  safely. Check search fields, filters and login forms.
- **SSRF**: any fetch of a user-supplied URL (webhooks, image fetch, imports, connector base URLs)
  needs an allowlist and must block internal IP ranges and cloud metadata endpoints (`169.254.169.254`).
- **Validation**: schema-validate all input, including URL params and API fields. File uploads:
  check type on the server, limit size, prevent path traversal, and don't serve uploads executable
  from the app domain. Also check for command injection and unsafe deserialization
  (`pickle`, `yaml.load`, `eval`).
- **Webhooks**: signature verification, replay protection, timestamp tolerance, idempotency.

**Authentication and authorization**
- **Every** protected endpoint has server-side auth. List any endpoint that works without a token,
  and check that expired or malformed tokens are rejected.
- **IDOR/BOLA**: try every endpoint that takes a user, order, document or chat ID. Can user A read or
  change user B's data by changing the ID? Ownership must be checked on the server.
- **RBAC**: least privilege. A regular user must not reach admin endpoints by guessing URLs or
  editing their role in the JWT or session.
- **JWT**: strong algorithm (no `none`), signature verified, short expiry, refresh-token rotation,
  revocation or blacklist on logout, signing key kept in secure storage.
- **Passwords**: bcrypt/argon2, brute-force protection, account lockout.
- **Password reset tokens**: random, single-use, expire within 15 minutes, tied to one user.
- **No default admin accounts** or known credentials.

**Abuse and availability**
- **Rate limiting** per IP and per user. Minimum: **login 5/min per IP**, **password reset 3/hour**.
  Also cover signup (mass accounts), OTP, messaging (spam), file uploads (storage fill), search and
  expensive endpoints (including LLM calls), and promo or referral codes (infinite use).
- Request size limits, timeouts and pagination caps.
- Backpressure and queue limits, so a flood can't exhaust memory or workers.
- DDoS / WAF: say what belongs at the edge and what belongs in the app.
- Outbound calls: retries with exponential backoff and jitter, plus circuit breakers.

**Business logic** (mark N/A with a reason if there are no payments)
- Never trust client-side prices: the server calculates totals, taxes and discounts. Try changing
  price, quantity or discount in the request body.
- Negative amounts, stacked discounts, restarting free trials, self-referral.
- Verify payment-provider webhook signatures (Stripe, Razorpay). Check payment status on the server
  before unlocking paid features.

**Concurrency and data integrity**
- Race conditions in check-then-act code (balances, coupons, inventory, one-time tokens): use
  transactions or locking.
- Idempotency keys on payment and critical POST endpoints.
- Deadlocks and thread safety in shared state.
- Sagas / distributed transactions: failed steps must compensate safely.
- Queues / pub-sub: validate payloads, authenticate producers and consumers, make consumers
  idempotent, and handle dead-letter queues without losing or leaking data.
- **Cron / scheduled jobs**: credentials secured, and no duplicate or overlapping runs.

**Errors, debug code and config**
- **Fail fast on config**: the app refuses to start, with a clear message, if a critical variable
  is missing (database URL, auth secret, required API keys). Optional ones get safe defaults.
- **Generic errors**: client errors return a generic message plus a **correlation ID**. No stack
  traces, SQL, file paths or internal details; those go to server logs only.
- **Debug code**: debug mode defaults to OFF. Remove debug prints, commented-out code blocks,
  TODO/FIXME comments about missing security, hardcoded test credentials, and test-only endpoints
  (`/test`, `/debug`, `/seed-data`, `/admin-backdoor`).
- **Security headers on every response**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Strict-Transport-Security: max-age=31536000; includeSubDomains`, and a CSP restricting scripts to
  your own domain (Express: `helmet`; FastAPI: middleware).
- **CORS**: explicit origins only, never `*` with credentials (unless the API is genuinely public).

**Internal exposure**: check whether any of these are reachable: DB admin panels, env vars in
error messages, `.env` or `.git` over HTTP, Swagger/OpenAPI docs that should be internal, and health
endpoints that leak system info.

**Data protection**
- TLS 1.2+ and HSTS in transit. Encryption at rest for the DB, backups and object storage.
- The DB uses **TLS in production**, has no default credentials, uses a least-privilege app user, and
  its port is not open to the internet. Check connection-pool limits.
- Migrations: nothing destructive or unsafe, and a rollback path exists.
- API versioning: deprecated versions don't keep insecure endpoints alive.

---

## 5. AI / LLM-specific (if the app uses LLMs, RAG or data connectors)

- **Prompt injection**: text from users or ingested sources (Slack, Jira, GitHub, documents) must not
  be able to override system instructions, trigger actions, or exfiltrate data. Treat retrieved
  content as data, not instructions.
- **Permission leaks in retrieval**: search and RAG must filter by the asking user's access
  **inside the query**, so private repos, channels or projects never reach another user's answer.
- **PII and secret scrubbing** happens before anything is stored, embedded or sent to a model.
- **Actions** proposed by the LLM (creating tickets, sending messages) require explicit user approval.
- **Model and data supply chain**: pin model revisions, don't load untrusted pickled weights, and
  don't send data to hosted LLM APIs if the app promises local-only processing.

---

## 6. Infrastructure, CI/CD and post-deployment

**Build and deploy**
- CI/CD: secrets handling, pinned dependency and action versions, no secrets in logs, signed
  artifacts, dependency and image vulnerability scanning.
- Docker: non-root user, minimal base image, no baked-in secrets, read-only filesystem where
  possible, internal services (DB, model servers) not published on public ports.
- Kubernetes: network policies, RBAC, Secrets (not ConfigMaps), pod security context, resource
  limits, liveness and readiness probes.
- IaC (Terraform / Helm): no hardcoded credentials, no overly permissive security groups or IAM,
  state files secured.
- Reverse proxy / gateway / load balancer: TLS termination, header hardening, request size limits,
  rate limiting, WAF rules, DDoS protection.
- DNS and TLS: valid certificates with auto-renewal, HSTS, no subdomain-takeover risk.

**Release safety**
- Feature flags: secure defaults, and no sensitive flags exposed to clients.
- Blue-green / canary / rolling deploys: a safe rollback path, including for DB migrations.
- Backups, failover and disaster recovery: encrypted, access-controlled, tested, with documented RTO/RPO.

**Observability and response**
- Logs, metrics and traces contain no sensitive data, and logs are tamper-resistant.
- Alerts for security events: failed-login spikes, 401/403 surges, unusual traffic, privilege changes.
- SLOs/SLIs include security signals.
- Incident response: on-call runbook, postmortem template, and a key-rotation procedure for leaked secrets.
- Failure testing: network partitions, clock skew (token expiry), dependency outages. The app
  must **fail closed**, not open.
- Serverless / cold starts: auth and rate limiting still work, and secrets load securely.

---

## Output format

1. **Executive summary**: the top 5 most critical risks.
2. **Findings list**: one short paragraph per finding, giving its ID, area (Secrets/Data/Frontend/Backend/AI/Infra),
   vulnerability, severity (Critical/High/Medium/Low), file:line, status (PASS/FAIL/N/A) and fix.
   Every checklist item above appears, including PASS and N/A ones. Don't use markdown tables anywhere in the report:
   short paragraphs and lists are easier to read.
3. **Secrets list** (section 1) and **personal-data map** (section 2).
4. **Attack paths**: for each Critical/High finding, what an attacker does, the damage, and the fix.
5. **Corrected code** for every Critical and High finding, plus a list of the changes you made.
6. **Recommended config files**: security headers / CSP, rate limiter, CORS, hardened Dockerfile, `.env.example`.
7. **Remediation plan**: fix now, fix this sprint, fix later.
8. **Post-deployment checklist**: monitoring, alerting, secret rotation, backup tests, incident runbook.
9. **What I need from you**: anything you couldn't see (infra, cloud, CI, DNS, secrets manager).
