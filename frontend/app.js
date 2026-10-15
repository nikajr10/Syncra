/* Syncra — clickable prototype. Vanilla JS, hash routing, demo data only (no backend). */
'use strict';

/* ---------- Utilities ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ic = (n, cls = '') => `<span class="ms ${cls}" aria-hidden="true">${n}</span>`;
const uid = p => p + Math.random().toString(36).slice(2, 8);
const initials = n => n.split(/[\s@.]+/).filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase();
const MIN = 6e4, HR = 36e5, DAY = 864e5, NOW = Date.now();
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fmtDate = iso => { const d = new Date(iso + 'T00:00:00'); return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`; };
function ago(ts) {
  const d = Date.now() - ts;
  if (d < MIN) return 'Just now';
  if (d < HR) return `${Math.floor(d / MIN)} min ago`;
  if (d < DAY) return `${Math.floor(d / HR)} h ago`;
  if (d < 2 * DAY) return 'Yesterday';
  if (d < 14 * DAY) return `${Math.floor(d / DAY)} days ago`;
  const t = new Date(ts); return `${t.getDate()} ${MONTHS[t.getMonth()]} ${t.getFullYear()}`;
}
const stripTags = s => s.replace(/\{\d+\}/g, '').replace(/<[^>]+>/g, '');
function hl(text, q) {
  const toks = tokens(q).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!toks.length) return esc(text);
  const re = new RegExp(`(${toks.join('|')})`, 'gi');
  return text.split(re).map((p, i) => i % 2 ? `<mark>${esc(p)}</mark>` : esc(p)).join('');
}
const STOP = new Set(['why', 'did', 'we', 'the', 'what', 'for', 'is', 'are', 'a', 'an', 'of', 'to', 'in', 'on', 'do', 'does', 'how', 'who', 'our', 'and', 'or', 'with', 'this', 'that', 'it', 'be', 'was']);
const tokens = q => (q || '').toLowerCase().split(/[^a-z0-9#\-]+/).filter(t => t.length > 1 && !STOP.has(t));
function announce(msg) { const l = $('#live'); l.textContent = ''; setTimeout(() => { l.textContent = msg; }, 50); }

const LOGO = `<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#e4b64e"/><path d="M9.5 13a4.5 4.5 0 0 1 4.5-4.5h6M22.5 19a4.5 4.5 0 0 1-4.5 4.5h-6" stroke="#121110" stroke-width="2.4" fill="none" stroke-linecap="round"/><circle cx="22" cy="8.5" r="2.3" fill="#121110"/><circle cx="10" cy="23.5" r="2.3" fill="#121110"/><circle cx="16" cy="16" r="2.3" fill="#121110"/></svg>`;

/* ---------- Static demo data ---------- */
const PEOPLE = {
  sa: { name: 'Sameer Acharya', role: 'Engineering Manager' },
  pn: { name: 'Priya Nair', role: 'Staff Engineer, Payments' },
  md: { name: 'Marco Diaz', role: 'Platform Lead' },
  ak: { name: 'Aisha Khan', role: 'Engineering Manager, Identity' },
  jl: { name: 'Jonas Lee', role: 'Site Reliability Engineer' },
};
const P = {
  github: { name: 'GitHub', mono: 'GH', desc: 'Repositories, pull requests, issues and Markdown docs.', scopeLabel: 'repositories', options: ['payments-service', 'platform-infra', 'web-app', 'docs', 'mobile-app', 'data-pipelines'], perms: ['Read repository contents and Markdown docs', 'Read pull requests, reviews and issues', 'Read organization members'], items: 1284 },
  jira: { name: 'Jira', mono: 'JI', desc: 'Projects, issues, epics and incident tickets.', scopeLabel: 'projects', options: ['PAY', 'AUTH', 'OPS', 'WEB', 'DATA'], perms: ['Read projects and issues you can access', 'Read comments and issue links', 'Create issues — only after you approve each one'], items: 842 },
  slack: { name: 'Slack', mono: 'SL', desc: 'Public channel messages and threads you select.', scopeLabel: 'channels', options: ['#payments-arch', '#platform', '#incidents', '#auth', '#payments-oncall', '#general'], perms: ['Read messages in selected public channels', 'Read channel and user names'], items: 3120 },
  confluence: { name: 'Confluence', mono: 'CF', desc: 'Spaces, pages and architecture decision records.', scopeLabel: 'spaces', options: ['ENG', 'ARCH', 'ONBOARD', 'SEC'], perms: ['Read pages in selected spaces', 'Read page history and authors'], items: 416 },
  gdrive: { name: 'Google Drive', mono: 'GD', desc: 'Docs, Sheets and Slides shared with you.', unavailable: true },
};
const KIND = { doc: ['Document', 'description'], pr: ['Pull request', 'merge'], issue: ['Issue', 'task_alt'], discussion: ['Discussion', 'forum'], incident: ['Incident', 'emergency'], code: ['Code', 'code'] };
const S = {
  s1: { provider: 'github', kind: 'doc', title: 'ADR-014: Use PostgreSQL for the payment ledger', loc: 'payments-service · docs/adr/014-ledger-postgres.md', author: 'pn', date: '2026-02-11', excerpt: 'Decision: PostgreSQL 15 is the system of record for ledger entries and balances. Multi-row writes must be atomic; balance updates run with SERIALIZABLE isolation. Approved by Marco Diaz and Aisha Khan.' },
  s2: { provider: 'jira', kind: 'issue', title: 'PAY-412 Evaluate datastore options for payment ledger', loc: 'Jira · PAY · Done', author: 'md', date: '2026-01-22', excerpt: 'Compared MongoDB, DynamoDB and PostgreSQL. Hard requirement: ACID across ledger entries and balances. DynamoDB rejected for multi-item transaction limits. Recommendation: PostgreSQL.' },
  s3: { provider: 'github', kind: 'pr', title: 'PR #482 Migrate ledger writes to PostgreSQL', loc: 'payments-service · merged', author: 'pn', date: '2026-03-04', excerpt: 'Moves LedgerWriter to PostgreSQL with SERIALIZABLE transactions. Implements ADR-014. Closes PAY-418. Reviewed by Jonas Lee.' },
  s4: { provider: 'slack', kind: 'discussion', title: 'Mongo vs Postgres for the ledger?', loc: '#payments-arch · thread, 14 replies', author: 'md', date: '2026-01-29', excerpt: 'Marco: we already run three Postgres clusters with on-call runbooks. Mongo would be a whole new operational surface for a team of four.' },
  s5: { provider: 'jira', kind: 'issue', title: 'PAY-431 Backfill historical ledger entries', loc: 'Jira · PAY · Done', author: 'jl', date: '2026-04-02', excerpt: 'Backfill of 18 months of ledger entries completed. Reconciliation diff against the legacy store: 0 rows.' },
  s6: { provider: 'github', kind: 'code', title: 'services/session/redis.ts', loc: 'payments-service · main', author: 'jl', date: '2026-06-18', excerpt: 'Session tokens are cached in redis-prod-1 with a 30 minute TTL. The API rate limiter shares the same cluster (key prefix rl:).' },
  s7: { provider: 'jira', kind: 'incident', title: 'OPS-88 Checkout latency spike — Redis eviction', loc: 'Jira · OPS · Resolved', author: 'jl', date: '2026-05-14', excerpt: 'Root cause: maxmemory reached on shared cluster redis-prod-1. Session keys were evicted, forcing re-authentication and a p95 checkout latency of 4.2s for 38 minutes.' },
  s8: { provider: 'slack', kind: 'discussion', title: 'Who owns redis-prod-1?', loc: '#platform · thread, 9 replies', author: 'md', date: '2026-06-02', excerpt: 'Marco: Platform owns redis-prod-1. Payments (sessions), Auth (rate limits) and Notifications (fan-out queue) all read from it today.' },
  s9: { provider: 'github', kind: 'doc', title: 'Authentication architecture', loc: 'docs · architecture/auth.md', author: 'ak', date: '2025-11-03', excerpt: 'All user authentication is delegated to Auth0 through the hosted login page. Services validate Auth0-issued JWTs at the gateway.' },
  s10: { provider: 'github', kind: 'pr', title: 'PR #533 Deploy Keycloak realm for customer SSO', loc: 'platform-infra · merged', author: 'jl', date: '2026-08-19', excerpt: 'Adds Helm values for a Keycloak realm (northwind-customers) and an OIDC client for the customer web app, behind the customer_sso_keycloak flag.' },
  s11: { provider: 'jira', kind: 'issue', title: 'AUTH-57 Evaluate Keycloak as Auth0 replacement', loc: 'Jira · AUTH · In progress', author: 'ak', date: '2026-07-02', excerpt: 'Auth0 MAU pricing increases 40% at renewal in December. Spike approved to evaluate self-hosted Keycloak. No architecture decision yet.' },
  s12: { provider: 'github', kind: 'doc', title: 'payments-service README', loc: 'payments-service · README.md', author: 'pn', date: '2026-05-20', excerpt: 'Dependencies: PostgreSQL (ledger), redis-prod-1 (sessions, rate limiting), Kafka (payment events). Owners: Payments team.' },
  s13: { provider: 'slack', kind: 'discussion', title: 'On-call rotation for Q3', loc: '#payments-oncall', author: 'ak', date: '2026-06-30', excerpt: '', access: 'revoked' },
  s14: { provider: 'slack', kind: 'discussion', title: 'Keycloak spike results', loc: '#auth · thread, 22 replies', author: 'jl', date: '2026-07-24', excerpt: 'Jonas: spike works for customer SSO. Employee login and SCIM provisioning not tested yet. Recommend shipping customer SSO behind a flag first.' },
  s15: { provider: 'jira', kind: 'issue', title: 'AUTH-61 Customer SSO for Enterprise plan', loc: 'Jira · AUTH · In progress', author: 'ak', date: '2026-08-01', excerpt: 'Enterprise customers need SAML/OIDC SSO by Q4. Implementation candidate: Keycloak realm per AUTH-57 spike.' },
  s16: { provider: 'jira', kind: 'issue', title: 'PAY-418 Move LedgerWriter to PostgreSQL', loc: 'Jira · PAY · Done', author: 'pn', date: '2026-02-14', excerpt: 'Implementation ticket for ADR-014. Switch LedgerWriter to PostgreSQL, keep dual-write for one week, then cut over.' },
};

const ANSWERS = {
  redis: {
    match: /redis|cache|impact|affect|replace|depend/i,
    confidence: 'Medium', why: 'Dependencies are inferred from code and Slack; no decision record covers Redis.',
    sources: ['s6', 's8', 's7', 's12'],
    body: ['Replacing Redis would most likely affect <strong>three services</strong> and <strong>three teams</strong>. The shared cluster <code>redis-prod-1</code> stores session tokens and backs the API rate limiter {1}, and notification fan-out reads from it too {2}.',
      'This cluster has failed before: in May 2026 memory pressure evicted session keys and caused a checkout latency spike (OPS-88) {3}.'],
    more: ['No architecture decision record covers Redis. Ownership is described only in a Slack thread {2}, so treat this as a starting point rather than a complete inventory.'],
    impact: [['dns', 'Services', 'session-service, rate-limiter, notifications-worker', 1], ['folder_code', 'Repositories', 'payments-service, platform-infra', 4], ['groups', 'Teams', 'Platform (owner), Payments, Auth', 2], ['emergency', 'Past incidents', 'OPS-88 · Checkout latency spike', 3]],
    entities: [['redis-prod-1', 'memory'], ['Platform team', 'groups'], ['session-service', 'dns'], ['Jonas Lee', 'person']],
    decision: 'd3',
    action: { project: 'OPS', summary: 'Investigate impact of replacing redis-prod-1', desc: 'Syncra found 3 services and 3 teams that depend on redis-prod-1 (sessions, rate limiting, notification fan-out). There is no decision record for this cluster.\n\nEvidence:\n- services/session/redis.ts\n- #platform: Who owns redis-prod-1?\n- OPS-88 Checkout latency spike' },
    followups: ['Why did we choose PostgreSQL for the payment ledger?', 'Which auth provider do we use?'],
  },
  auth: {
    match: /\bauth\b|authentication|keycloak|auth0|\bsso\b|login|identity provider/i,
    confidence: 'Low', why: 'Sources conflict and no approved decision record resolves them.',
    sources: ['s9', 's10', 's11'],
    conflict: [['s9', 'Architecture doc · Nov 2025', 'All user authentication is delegated to Auth0.'], ['s10', 'PR #533 · merged 19 Aug 2026', 'Deploys a Keycloak realm for customer SSO.']],
    body: ['Your sources disagree. The architecture document says all authentication is delegated to Auth0 {1}, but PR #533, merged on 19 Aug 2026, deploys a Keycloak realm for customer SSO {2}.',
      'AUTH-57 tracks an evaluation of Keycloak as an Auth0 replacement {3}, but no approved decision record exists yet. Syncra can’t tell which source reflects the current setup, so both are shown.'],
    entities: [['Auth0', 'key'], ['Keycloak', 'key'], ['Identity team', 'groups'], ['Aisha Khan', 'person']],
    decision: 'd2',
    action: { project: 'AUTH', summary: 'Reconcile auth architecture doc with Keycloak deployment', desc: 'docs/architecture/auth.md says all authentication uses Auth0, but PR #533 deployed a Keycloak realm for customer SSO. AUTH-57 has no approved decision.\n\nEvidence:\n- Authentication architecture (auth.md)\n- PR #533 Deploy Keycloak realm for customer SSO\n- AUTH-57 Evaluate Keycloak as Auth0 replacement' },
    followups: ['What could be affected if we replace Redis?', 'Why did we choose PostgreSQL for the payment ledger?'],
  },
  oncall: {
    match: /on-?call|rotation|pager/i,
    confidence: 'Medium', why: 'One of the original sources is no longer accessible to you.',
    sources: ['s13', 's5'],
    body: ['The Q3 rotation was shared in a Slack channel you can no longer access {1}, so its details are not shown here.', 'From sources you can still open: Jonas Lee was the on-call SRE for the ledger backfill in April {2}. Ask an admin or the Payments team for the current schedule.'],
    followups: ['Who was involved in ADR-014?'],
  },
  who: {
    match: /\bwho\b|involved|approv|author/i,
    confidence: 'High', why: 'Names come from the ADR approval block and pull request metadata.',
    sources: ['s1', 's4', 's3'],
    body: ['ADR-014 was written by <strong>Priya Nair</strong> (Staff Engineer, Payments) and approved by <strong>Marco Diaz</strong> (Platform Lead) and <strong>Aisha Khan</strong> on 11 Feb 2026 {1}.',
      'Marco and <strong>Jonas Lee</strong> (SRE) made the operational case in #payments-arch {2}. Priya implemented the change in PR #482, reviewed by Jonas {3}.'],
    entities: [['Priya Nair', 'person'], ['Marco Diaz', 'person'], ['Aisha Khan', 'person'], ['Jonas Lee', 'person']],
    decision: 'd1',
    followups: ['What could be affected if we replace Redis?', 'Which auth provider do we use?'],
  },
  postgres: {
    match: /postgres|ledger|database|datastore|mongo|adr-014/i,
    confidence: 'High', why: 'Four independent sources agree and the decision record is approved.',
    sources: ['s1', 's2', 's3', 's4', 's5'],
    body: ['PostgreSQL was chosen as the system of record for the payment ledger because ledger writes must be atomic across entries and balances, which needs ACID transactions with serializable isolation {1}{2}.',
      'Operational experience also counted: Platform already ran three PostgreSQL clusters with on-call runbooks, while MongoDB would have added a new system to operate {4}. DynamoDB was ruled out because of its limits on multi-item transactions {2}.'],
    more: ['The decision was recorded as ADR-014 on 11 Feb 2026 {1}, implemented in PR #482 {3}, and the historical backfill finished under PAY-431 with a zero-difference reconciliation {5}.'],
    entities: [['Payment Service', 'dns'], ['ADR-014', 'gavel'], ['Platform team', 'groups'], ['Priya Nair', 'person'], ['PostgreSQL', 'database']],
    decision: 'd1',
    followups: ['Who was involved in ADR-014?', 'What could be affected if we replace Redis?', 'Which auth provider do we use?'],
  },
};
const ANSWER_ORDER = ['redis', 'auth', 'oncall', 'who', 'postgres'];
const SUGGESTED = [
  ['history_edu', 'Why did we choose PostgreSQL for the payment ledger?'],
  ['account_tree', 'What could be affected if we replace Redis?'],
  ['group', 'Who was involved in ADR-014?'],
  ['rule', 'Which auth provider do we use?'],
];

const DECISIONS = {
  d1: {
    title: 'Use PostgreSQL for the payment ledger', status: ['success', 'check_circle', 'Approved'], date: '2026-02-11', ref: 'ADR-014', owner: 'pn', people: ['pn', 'md', 'ak', 'jl'], service: 'Payment Service',
    summary: 'PostgreSQL 15 is the system of record for all ledger entries and balances, with SERIALIZABLE isolation for balance updates.',
    why: ['Ledger writes must be atomic across entries and balances {1}{2}', 'Platform already operated three PostgreSQL clusters with runbooks {4}', 'DynamoDB’s multi-item transaction limits ruled it out {2}'],
    sources: ['s1', 's2', 's3', 's4', 's5'],
    timeline: [['2026-01-22', 'Datastore evaluation opened', 's2', 'search'], ['2026-01-29', 'Mongo vs Postgres debated in #payments-arch', 's4', 'forum'], ['2026-02-11', 'ADR-014 approved', 's1', 'gavel', true], ['2026-02-14', 'Implementation ticket PAY-418 created', 's16', 'task_alt'], ['2026-03-04', 'PR #482 merged: ledger writes on PostgreSQL', 's3', 'merge'], ['2026-04-02', 'Backfill completed with zero diff', 's5', 'check_circle']],
    graph: [['discussed in', '#payments-arch', 'slack'], ['tracked by', 'PAY-412', 'jira'], ['implemented by', 'PR #482', 'github'], ['affects', 'Payment Service', null]],
    impact: [['dns', 'Payment Service', 'Ledger reads and writes'], ['database', 'pg-ledger-prod', 'Primary + 2 replicas'], ['groups', 'Payments, Platform', 'Owners and operators']],
  },
  d2: {
    title: 'Adopt Keycloak for customer SSO', status: ['warning', 'warning', 'Potential contradiction'], date: '2026-08-19', ref: 'No ADR', owner: 'ak', people: ['ak', 'jl', 'md'], service: 'auth-gateway',
    summary: 'A Keycloak realm for customer SSO is deployed behind a flag, but the documented architecture still says all authentication goes through Auth0.',
    why: ['Auth0 MAU pricing rises 40% at the December renewal {3}', 'Enterprise customers need SSO by Q4 {4}', 'Spike showed customer SSO works; employee login untested {5}'],
    sources: ['s9', 's10', 's11', 's15', 's14'],
    contradiction: true,
    timeline: [['2025-11-03', 'Auth architecture documented: Auth0 only', 's9', 'description'], ['2026-07-02', 'AUTH-57 Keycloak evaluation opened', 's11', 'search'], ['2026-07-24', 'Spike results shared in #auth', 's14', 'forum'], ['2026-08-01', 'AUTH-61 Customer SSO for Enterprise', 's15', 'task_alt'], ['2026-08-19', 'PR #533 merged: Keycloak realm deployed', 's10', 'merge', true]],
    graph: [['contradicts', 'auth.md (Auth0)', 'github'], ['tracked by', 'AUTH-57', 'jira'], ['implemented by', 'PR #533', 'github'], ['affects', 'auth-gateway', null]],
    impact: [['dns', 'auth-gateway', 'Validates tokens from two issuers'], ['web', 'Customer web app', 'Login flow behind a flag'], ['handshake', 'Auth0 contract', 'Renewal in Dec 2026']],
  },
  d3: {
    title: 'Share one Redis cluster across services', status: ['info', 'info', 'No decision record'], date: '2026-06-02', ref: 'Inferred', owner: 'md', people: ['md', 'jl'], service: 'redis-prod-1',
    summary: 'Sessions, rate limiting and notification fan-out all use redis-prod-1. This was never formally decided; it is inferred from code and a Slack thread.',
    why: ['Session tokens and rate limits share one cluster {1}', 'Platform owns the cluster; three teams depend on it {2}', 'Memory pressure caused the OPS-88 incident {3}'],
    sources: ['s6', 's8', 's7'],
    timeline: [['2026-05-14', 'OPS-88: Redis eviction causes checkout latency', 's7', 'emergency', true], ['2026-06-02', 'Ownership clarified in #platform', 's8', 'forum'], ['2026-06-18', 'Session TTL set to 30 minutes', 's6', 'code']],
    graph: [['discussed in', '#platform', 'slack'], ['caused', 'OPS-88', 'jira'], ['defined in', 'redis.ts', 'github'], ['affects', 'session-service', null]],
    impact: [['dns', 'session-service', 'Session tokens'], ['speed', 'rate-limiter', 'API limits'], ['notifications', 'notifications-worker', 'Fan-out queue']],
  },
};

const EXPLAIN = {
  pr: { kind: 'GitHub pull request', title: 'PR #533 · Deploy Keycloak realm for customer SSO', url: 'github.com/northwind/platform-infra/pull/533',
    summary: 'This PR deploys a Keycloak realm for customer-facing SSO. That conflicts with the architecture doc, which says all authentication goes through Auth0 {1}. It looks like part of the AUTH-57 evaluation {2}, which has no approved decision record yet.',
    sources: ['s9', 's11'], decision: 'd2', related: ['s11', 's15'], discussions: ['s14'], people: ['jl', 'md', 'ak'],
    impact: ['auth-gateway service', 'Customer web app login', 'Enterprise SSO (AUTH-61)', 'Auth0 contract renewal · Dec 2026'],
    points: ['Adds a Helm chart for a Keycloak realm, northwind-customers, in platform-infra.', 'Configures an OIDC client for the customer web app behind the customer_sso_keycloak flag.', 'Employee login stays on Auth0; existing users are not migrated.', 'A reviewer asked for a rollback plan before the flag is enabled in production.'],
    extra: ['Changes touch 6 files: Helm values, a Terraform module and gateway issuer config.', 'The gateway now trusts two token issuers while the flag exists.'],
    items: ['Write a rollback plan before enabling customer_sso_keycloak (requested by reviewer)', 'Update docs/architecture/auth.md if Keycloak is adopted'] },
  jira: { kind: 'Jira issue', title: 'AUTH-57 · Evaluate Keycloak as Auth0 replacement', url: 'northwind.atlassian.net/browse/AUTH-57',
    summary: 'AUTH-57 is an open evaluation of replacing Auth0 with Keycloak, driven by Auth0 pricing {1}. A spike ran in July {2}, and PR #533 already deployed a Keycloak realm for customer SSO {3}, ahead of any approved decision.',
    sources: ['s11', 's14', 's10'], decision: 'd2', related: ['s10', 's15'], discussions: ['s14'], people: ['ak', 'jl'],
    impact: ['auth-gateway service', 'Employee and customer login', 'Auth0 contract renewal · Dec 2026'],
    points: ['Goal: decide whether to replace Auth0 before the December renewal.', 'Status: In progress, assigned to Aisha Khan.', 'Acceptance criteria include SCIM provisioning and employee SSO, both still untested.'],
    extra: ['Linked issues: AUTH-61 (customer SSO), AUTH-63 (SCIM).', 'Last comment 3 days ago asks for a cost comparison.'],
    items: ['Prepare a cost comparison before renewal (asked in latest comment)', 'Test SCIM provisioning and employee SSO'] },
  blog: { kind: 'Web page', title: 'Engineering blog: Our 2026 platform roadmap', url: 'eng.northwind.io/blog/2026-platform-roadmap', unsupported: true,
    points: ['Platform plans to consolidate on PostgreSQL and retire two legacy stores by Q1 2027.', 'A self-service developer portal is planned for internal APIs.', 'Observability moves to a single OpenTelemetry pipeline.'],
    extra: ['The roadmap is a draft and may change after quarterly planning.'],
    items: ['None found — this page describes plans, not assigned work'] },
};

/* ---------- State ---------- */
const STORE = 'syncra-proto-v1';
function seedConnectors(full) {
  if (!full) return { github: { status: 'not_connected' }, jira: { status: 'not_connected' }, slack: { status: 'not_connected' }, confluence: { status: 'not_connected' }, gdrive: { status: 'unavailable' } };
  return {
    github: { status: 'connected', scope: ['payments-service', 'platform-infra', 'web-app', 'docs'], items: 1284, lastSync: NOW - 12 * MIN, by: 'Sameer Acharya', history: [{ t: NOW - 12 * MIN, type: 'Incremental', result: 'success', items: '+38', dur: '42s' }, { t: NOW - 27 * MIN, type: 'Incremental', result: 'success', items: '+12', dur: '31s' }, { t: NOW - DAY, type: 'Full', result: 'success', items: '1,284', dur: '6m 12s' }] },
    jira: { status: 'indexing', progress: 72, scope: ['PAY', 'AUTH', 'OPS'], items: 606, lastSync: NOW - 4 * MIN, by: 'Sameer Acharya', history: [{ t: NOW - 4 * MIN, type: 'Initial', result: 'running', items: '606 of 842', dur: '—' }] },
    slack: { status: 'attention', error: 'invalid_auth', scope: ['#payments-arch', '#platform', '#incidents', '#auth'], items: 3120, lastSync: NOW - 3 * DAY, by: 'Marco Diaz', history: [{ t: NOW - 2 * DAY, type: 'Incremental', result: 'error', items: '0', dur: '2s', code: 'invalid_auth' }, { t: NOW - 3 * DAY + HR, type: 'Incremental', result: 'error', items: '0', dur: '2s', code: 'invalid_auth' }, { t: NOW - 3 * DAY, type: 'Incremental', result: 'success', items: '+214', dur: '1m 04s' }] },
    confluence: { status: 'not_connected' },
    gdrive: { status: 'unavailable' },
  };
}
function seedWorkspace(id, name, full, role = 'admin') {
  const ws = { id, name, desc: '', role, policyMembersConnect: false, retention: '30', connectors: seedConnectors(full), conversations: [], saved: [], audit: [], setupSkipped: false,
    members: [{ id: 'm1', name: 'Sameer Acharya', email: 'sameer@northwind.io', role: 'admin', status: 'Active', joined: NOW - 120 * DAY, you: true }] };
  if (!full) return ws;
  ws.desc = 'Payments, Platform and Identity engineering.';
  ws.members.push(
    { id: 'm2', name: 'Marco Diaz', email: 'marco@northwind.io', role: 'admin', status: 'Active', joined: NOW - 118 * DAY },
    { id: 'm3', name: 'Priya Nair', email: 'priya@northwind.io', role: 'member', status: 'Active', joined: NOW - 90 * DAY },
    { id: 'm4', name: 'Aisha Khan', email: 'aisha@northwind.io', role: 'member', status: 'Active', joined: NOW - 60 * DAY },
    { id: 'm5', name: 'Jonas Lee', email: 'jonas@northwind.io', role: 'member', status: 'Active', joined: NOW - 45 * DAY },
    { id: 'm6', name: 'dana@northwind.io', email: 'dana@northwind.io', role: 'member', status: 'Invited', joined: NOW - 6 * DAY });
  const conv = (id, q, key, t) => ({ id, title: q, created: t, updated: t, messages: [{ role: 'user', id: id + 'u', text: q }, { role: 'ai', id: id + 'a', q, key, status: 'done' }] });
  ws.conversations = [conv('c1', 'Why did we choose PostgreSQL for the payment ledger?', 'postgres', NOW - 2 * HR), conv('c2', 'What could be affected if we replace Redis?', 'redis', NOW - DAY - 3 * HR), conv('c3', 'What’s the on-call rotation for payments?', 'oncall', NOW - 5 * DAY)];
  ws.saved = [{ id: 'v1', type: 'answer', conv: 'c1', msg: 'c1a', at: NOW - HR }, { id: 'v2', type: 'source', src: 's7', at: NOW - 2 * DAY }];
  ws.audit = [
    { t: NOW - 2 * DAY, actor: 'Sameer Acharya', action: 'Created Jira issue', target: 'OPS-112 Add memory alerts to redis-prod-1', result: 'success', note: 'Approved by Sameer Acharya' },
    { t: NOW - 3 * DAY + HR, actor: 'Syncra', action: 'Sync failed', target: 'Slack · invalid_auth', result: 'error' },
    { t: NOW - 6 * DAY, actor: 'Sameer Acharya', action: 'Invited member', target: 'dana@northwind.io (Member)', result: 'success' },
    { t: NOW - 14 * DAY, actor: 'Sameer Acharya', action: 'Connected source', target: 'Jira · PAY, AUTH, OPS', result: 'success' },
    { t: NOW - 15 * DAY, actor: 'Marco Diaz', action: 'Connected source', target: 'Slack · 4 channels', result: 'success' },
    { t: NOW - 15 * DAY, actor: 'Sameer Acharya', action: 'Connected source', target: 'GitHub · 4 repositories', result: 'success' },
  ];
  return ws;
}
function defaultState() {
  return { authed: false, wsId: null, returnTo: null,
    user: { name: 'Sameer Acharya', email: 'sameer@northwind.io', title: 'Engineering Manager' },
    prefs: { style: 'balanced', sources: ['github', 'jira', 'slack'], confidence: true, pageCtx: false },
    workspaces: { w1: seedWorkspace('w1', 'Northwind Labs', true), w2: seedWorkspace('w2', 'Northwind Design', false, 'member') },
    askFilters: [], ext: { open: true, page: 'pr', tab: 'explain', explain: {}, summary: {}, pageCtx: false, conv: null } };
}
let state;
try { state = JSON.parse(localStorage.getItem(STORE)) || defaultState(); } catch (e) { state = defaultState(); }
const save = () => { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* storage unavailable: prototype still works in memory */ } };
const W = () => state.workspaces[state.wsId];
const conn = k => W().connectors[k];
const isAdmin = () => W()?.role === 'admin';
const SEARCHABLE = ['connected', 'indexing', 'attention'];
const searchable = () => Object.keys(P).filter(k => SEARCHABLE.includes(conn(k).status));
const findConv = id => W().conversations.find(c => c.id === id);
let dirty = false;

/* ---------- Overlays: modal, drawer, popover, toast ---------- */
const overlays = [];
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function focusFirst(root) { const el = root.querySelector('[data-autofocus]') || root.querySelector('input:not([type=checkbox]):not([disabled]), textarea, select') || root.querySelector('.modal-foot .btn, .drawer-foot .btn') || root.querySelector(FOCUSABLE); el?.focus(); }
function openOverlay(html, { drawer = false, wide = false, dismissible = true, label = 'Dialog' } = {}) {
  closePopover();
  const prev = document.activeElement;
  const ov = document.createElement('div');
  ov.className = 'overlay' + (drawer ? ' drawer-overlay' : '');
  ov.innerHTML = `<div class="${drawer ? 'drawer' : 'modal' + (wide ? ' wide' : '')}" role="dialog" aria-modal="true" aria-label="${esc(label)}">${html}</div>`;
  ov.addEventListener('mousedown', e => { if (e.target === ov && overlays.at(-1)?.dismissible) closeOverlay(); });
  document.body.appendChild(ov);
  overlays.push({ ov, prev, dismissible });
  focusFirst(ov);
  return ov.firstElementChild;
}
function setOverlay(html, { dismissible } = {}) { const top = overlays.at(-1); if (!top) return; top.ov.firstElementChild.innerHTML = html; if (dismissible !== undefined) top.dismissible = dismissible; focusFirst(top.ov); }
function closeOverlay() { const top = overlays.pop(); if (!top) return; top.ov.remove(); if (top.prev && document.contains(top.prev)) top.prev.focus(); }
const mHead = (title, sub = '', lead = '') => `<div class="modal-head">${lead}<div class="grow"><h2 class="h3">${title}</h2>${sub ? `<p class="text-2 body-3" style="margin-top:2px">${sub}</p>` : ''}</div><button class="icon-btn" data-action="close-overlay" aria-label="Close">${ic('close')}</button></div>`;
const dHead = (title, lead = '') => `<div class="drawer-head">${lead}<h2 class="h4 grow">${title}</h2><button class="icon-btn" data-action="close-overlay" aria-label="Close">${ic('close')}</button></div>`;

let confirmCb = null;
function confirmDialog({ title, body, confirm = 'Confirm', danger = false, requireText = '', onConfirm }) {
  confirmCb = onConfirm;
  openOverlay(`${mHead(title, '', `<div class="icon-tile" style="${danger ? 'background:var(--error-s);color:var(--error-i)' : ''}">${ic(danger ? 'warning' : 'help')}</div>`)}
    <div class="modal-body"><div class="text-2">${body}</div>
    ${requireText ? `<div class="field"><label for="confirm-text">Type <strong>${esc(requireText)}</strong> to confirm</label><input id="confirm-text" class="input" autocomplete="off" data-input="confirm-text" data-expect="${esc(requireText)}"></div>` : ''}</div>
    <div class="modal-foot"><button class="btn btn-outline" data-action="close-overlay">Cancel</button><button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-action="confirm-ok" ${requireText ? 'disabled' : ''}>${esc(confirm)}</button></div>`, { dismissible: !danger, label: title });
}

let popEl = null, popAnchor = null;
function openPopover(anchor, html, align = 'left') {
  if (popAnchor === anchor) return closePopover();
  closePopover();
  popEl = document.createElement('div');
  popEl.className = 'popover'; popEl.setAttribute('role', 'menu'); popEl.innerHTML = html;
  document.body.appendChild(popEl);
  const r = anchor.getBoundingClientRect();
  popEl.style.top = `${r.bottom + 6}px`;
  const left = align === 'right' ? r.right - popEl.offsetWidth : r.left;
  popEl.style.left = `${Math.max(8, Math.min(left, innerWidth - popEl.offsetWidth - 8))}px`;
  popAnchor = anchor; anchor.setAttribute('aria-expanded', 'true');
  popEl.querySelector('.menu-item')?.focus();
}
function closePopover() { popEl?.remove(); popAnchor?.setAttribute('aria-expanded', 'false'); popAnchor?.focus?.(); popEl = null; popAnchor = null; }

function toast(msg, { type = 'success', undo } = {}) {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `${ic(type === 'error' ? 'error' : type === 'info' ? 'info' : 'check_circle')}<span>${esc(msg)}</span>${undo ? '<button class="link-btn">Undo</button>' : ''}`;
  if (undo) t.querySelector('button').onclick = () => { undo(); t.remove(); };
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), undo ? 6000 : 4000);
}
async function copyText(text, msg = 'Copied to clipboard') {
  try { await navigator.clipboard.writeText(text); toast(msg); } catch (e) { toast('Couldn’t access the clipboard. Select the text and copy it manually.', { type: 'error' }); }
}
function audit(action, target, result = 'success', note = '') { W().audit.unshift({ t: Date.now(), actor: state.user.name, action, target, result, note }); }

/* ---------- Router ---------- */
const ROUTES = [
  ['/welcome', pWelcome, { pub: true, bare: true }], ['/sign-in', pSignIn, { pub: true, bare: true }],
  ['/workspaces', pWorkspaces, { bare: true, noWs: true }], ['/create-workspace', pCreateWs, { bare: true, noWs: true }],
  ['/', pHome], ['/setup', pSetup], ['/ask', pAsk, { full: true }], ['/ask/:id', pConversation, { full: true }],
  ['/search', pSearch], ['/decisions', pDecisions], ['/decisions/:id', pDecision],
  ['/history', pHistory], ['/saved', pSaved], ['/integrations', pIntegrations], ['/integrations/:provider', pConnector],
  ['/admin/members', pMembers, { admin: true }], ['/admin/sync', pSyncHealth, { admin: true }], ['/admin/audit', pAudit, { admin: true }], ['/admin/workspace', pWsSettings, { admin: true }],
  ['/settings/:tab', pSettings], ['/help', pHelp], ['/extension', pExtension, { bare: true }],
];
function parseHash() {
  const raw = location.hash.slice(1) || '/';
  const [path, qs] = raw.split('?');
  return { path: path || '/', query: Object.fromEntries(new URLSearchParams(qs || '')) };
}
function match(path) {
  const segs = path.split('/').filter(Boolean);
  for (const [pat, fn, opts = {}] of ROUTES) {
    const ps = pat.split('/').filter(Boolean);
    if (ps.length !== segs.length) continue;
    const params = {};
    if (ps.every((p, i) => p[0] === ':' ? (params[p.slice(1)] = decodeURIComponent(segs[i]), true) : p === segs[i])) return { fn, opts, params };
  }
  return null;
}
const safePath = p => typeof p === 'string' && p.startsWith('/') && !p.startsWith('//') && !/[\\:]/.test(p) ? p : '/';
function go(path) { const h = '#' + path; if (location.hash === h) render(true); else location.hash = h; }
let current = { path: '/', query: {} };
function render(nav = false) {
  const { path, query } = parseHash();
  current = { path, query };
  closePopover();
  if (nav) while (overlays.length) closeOverlay();
  const r = match(path);
  if (r && !r.opts.pub && !state.authed) { state.returnTo = path; return go(path === '/' ? '/welcome' : '/sign-in?expired=1'); }
  if (state.authed && !state.wsId && !(r && r.opts.noWs)) return go('/workspaces');
  if (r && r.opts.pub && state.authed && state.wsId) return go('/');
  const scroller = $('.main'), top = scroller?.scrollTop;
  let html;
  if (!r) html = state.authed && state.wsId ? shell(pNotFound(), path) : pNotFound(true);
  else if (r.opts.admin && !isAdmin()) html = shell(pDenied(), path);
  else { const body = r.fn(r.params, query); html = r.opts.bare ? body : shell(body, path, r.opts.full); }
  $('#app').innerHTML = html + (state.authed && state.wsId ? protoBar() : '');
  if (nav) { $('.main')?.scrollTo(0, 0); const h = $('#app h1'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); } const t = h?.cloneNode(true); t?.querySelectorAll('[aria-hidden]').forEach(x => x.remove()); document.title = (t ? t.textContent.trim() + ' · ' : '') + 'Syncra'; }
  else if (scroller && $('.main')) $('.main').scrollTop = top;
  mounted.splice(0).forEach(fn => fn());
  save();
}
const mounted = [];
const onMount = fn => mounted.push(fn);
const rerender = () => render(false);

let lastHash = location.hash;
window.addEventListener('hashchange', () => {
  if (dirty && location.hash !== lastHash) {
    const target = location.hash;
    history.replaceState(null, '', lastHash);
    confirmDialog({ title: 'Discard unsaved changes?', body: 'You have edits on this page that haven’t been saved. Leaving will discard them.', confirm: 'Discard changes', danger: true, onConfirm: () => { dirty = false; location.hash = target; } });
    return;
  }
  lastHash = location.hash;
  render(true);
});
window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

/* ---------- Shared bits ---------- */
const BADGE = { not_connected: ['', 'link_off', 'Not connected'], connecting: ['info', 'hourglass_top', 'Connecting'], indexing: ['info', 'progress_activity', 'Indexing'], connected: ['success', 'check_circle', 'Connected'], attention: ['warning', 'error', 'Needs attention'], disconnected: ['', 'link_off', 'Disconnected'], disconnecting: ['', 'hourglass_top', 'Disconnecting'], unavailable: ['', 'block', 'Unavailable'] };
const badge = (tone, icon, label) => `<span class="badge ${tone}">${ic(icon)}${esc(label)}</span>`;
const statusBadge = c => c.syncing ? badge('info', 'sync', 'Syncing') : badge(...BADGE[c.status]);
const prov = (k, size = '') => `<span class="prov prov-${k} ${size}" aria-hidden="true">${P[k].mono}</span>`;
const avatar = (name, size = '') => `<span class="avatar ${size}" title="${esc(name)}" aria-hidden="true">${esc(initials(name))}</span>`;
const person = id => PEOPLE[id] || { name: id, role: '' };
const crumbs = items => `<nav class="crumbs" aria-label="Breadcrumb">${items.map(([l, h], i) => (h ? `<a href="#${h}">${esc(l)}</a>` : `<span aria-current="page">${esc(l)}</span>`) + (i < items.length - 1 ? ic('chevron_right') : '')).join('')}</nav>`;
const pageHeader = (title, sub = '', actions = '', pre = '') => `${pre}<div class="page-header"><div><h1 class="title-3">${title}</h1>${sub ? `<p>${sub}</p>` : ''}</div>${actions ? `<div class="row-wrap">${actions}</div>` : ''}</div>`;
const empty = (icon, title, text, cta = '') => `<div class="empty"><div class="icon-tile">${ic(icon)}</div><h2 class="h3">${title}</h2><p>${text}</p>${cta ? `<div class="row-wrap" style="justify-content:center">${cta}</div>` : ''}</div>`;
function coverageNotice(scope) {
  const issues = Object.keys(P).filter(k => (!scope || scope.includes(k)) && ['indexing', 'attention'].includes(conn(k).status)).map(k => {
    const c = conn(k);
    return c.status === 'indexing' ? `${P[k].name} is still indexing (${c.progress}%)` : `${P[k].name} needs reconnecting — last synced ${ago(c.lastSync).toLowerCase()}`;
  });
  if (!issues.length) return '';
  return `<div class="alert warning" role="note">${ic('info')}<div class="alert-body"><span class="alert-title">Results may be incomplete.</span> ${issues.join('. ')}. <a href="#/integrations">View integrations</a></div></div>`;
}

/* ---------- Shell ---------- */
function shell(content, path, full = false) {
  const ws = W(), admin = ws.role === 'admin';
  const active = h => h === '/' ? path === '/' : path === h || path.startsWith(h + '/');
  const nav = (h, icon, label, extra = '', cls = '') => `<a class="nav-item ${cls}" href="#${h}" ${active(h) ? 'aria-current="page"' : ''}>${ic(icon)}<span>${label}</span>${extra}</a>`;
  const attention = Object.values(ws.connectors).filter(c => c.status === 'attention').length;
  return `<div class="shell" id="shell">
  <header class="topbar">
    <button class="icon-btn menu-toggle" data-action="toggle-nav" aria-label="Open navigation" aria-controls="sidebar">${ic('menu')}</button>
    <a class="brand" href="#/" aria-label="Syncra home">${LOGO}<span class="hide-sm">Syncra</span></a>
    <button class="ws-switch" data-action="ws-menu" aria-haspopup="menu" aria-expanded="false" aria-label="Workspace: ${esc(ws.name)}. Switch workspace">
      <span class="ws-avatar">${esc(initials(ws.name))}</span><span class="ws-name label-1">${esc(ws.name)}</span>${ic('unfold_more')}
    </button>
    <button class="cmd" data-action="cmd" aria-label="Search or jump to (Ctrl K)">${ic('search')}<span>Search or jump to…</span><span class="grow"></span><span class="kbd">⌘K</span></button>
    <button class="icon-btn" data-action="theme" aria-label="Switch to ${document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'} theme">${ic(document.documentElement.dataset.theme === 'dark' ? 'light_mode' : 'dark_mode')}</button>
    <button class="icon-btn" data-action="user-menu" aria-haspopup="menu" aria-expanded="false" aria-label="Account menu">${avatar(state.user.name, 'sm')}</button>
  </header>
  <nav class="sidebar" id="sidebar" aria-label="Primary">
    ${nav('/', 'home', 'Home')}
    ${nav('/ask', 'auto_awesome', 'Ask')}
    ${nav('/search', 'search', 'Search')}
    ${nav('/decisions', 'gavel', 'Decisions')}
    ${nav('/history', 'history', 'History')}
    ${nav('/saved', 'bookmark', 'Saved', ws.saved.length ? `<span class="badge count">${ws.saved.length}</span>` : '')}
    ${nav('/integrations', 'hub', 'Integrations', attention ? `<span class="badge warning count" aria-label="${attention} needs attention">${ic('error')}${attention}</span>` : '')}
    ${admin ? `<div class="nav-section eyebrow">Admin</div>
      ${nav('/admin/members', 'group', 'Members')}
      ${nav('/admin/sync', 'monitor_heart', 'Sync health')}
      ${nav('/admin/audit', 'receipt_long', 'Audit log')}
      ${nav('/admin/workspace', 'tune', 'Workspace')}` : ''}
    <div class="nav-section eyebrow">You</div>
    <a class="nav-item" href="#/settings/profile" ${path.startsWith('/settings') ? 'aria-current="page"' : ''}>${ic('settings')}<span>Settings</span></a>
    ${nav('/help', 'help', 'Help')}
    <span class="grow"></span>
    <a class="nav-item" href="#/extension">${ic('extension')}<span>Chrome extension</span><span class="badge ai count">Preview</span></a>
  </nav>
  <main class="main" id="main" tabindex="-1">${full ? content : `<div class="page">${content}</div>`}</main>
</div>`;
}
const protoBar = () => `<div class="proto-note" role="region" aria-label="Prototype controls">${ic('science')} Prototype
  <label class="sr-only" for="proto-role">Role in this workspace</label>
  <select id="proto-role" data-change="proto-role"><option value="admin" ${isAdmin() ? 'selected' : ''}>Admin</option><option value="member" ${!isAdmin() ? 'selected' : ''}>Member</option></select>
  <button class="icon-btn sm" style="color:inherit" data-action="reset" aria-label="Reset prototype data">${ic('restart_alt')}</button></div>`;

/* ---------- Auth & workspace pages ---------- */
function authLayout(inner) {
  return `<div class="auth"><aside class="auth-side">
    <a class="brand" href="#/welcome">${LOGO}Syncra</a>
    <div><p class="eyebrow" style="color:#c7c0b5">Organizational intelligence</p>
      <h2 class="title-2" style="margin-top:12px;max-width:460px">Your organization’s memory — with receipts.</h2>
      <p class="body-1" style="margin-top:16px;max-width:440px;opacity:.8">Syncra connects GitHub, Jira and Slack, then explains why decisions were made, who made them and what a change could affect. Every answer cites its sources.</p>
      <div class="flow" aria-label="How Syncra works">${['Connect', 'Ingest', 'Understand', 'Retrieve', 'Explain', 'Act'].map((s, i) => `<span class="${i === 4 ? 'on' : ''}">${s}</span>`).join('')}</div></div>
    <p class="body-3" style="opacity:.7">${ic('lock')} Syncra only retrieves what you can already open in each tool. Permission checks happen before anything reaches the AI.</p>
  </aside><main class="auth-main" id="main">${inner}</main></div>`;
}
function pWelcome() {
  return authLayout(`<div class="auth-card">
    <div class="ai-mark">${ic('auto_awesome')}</div>
    <div><h1 class="title-3">Welcome to Syncra</h1><p class="text-2 body-1" style="margin-top:8px">Ask questions about your organization and get answers grounded in your team’s code, tickets and conversations.</p></div>
    <div class="stack-sm"><a class="btn btn-primary btn-lg" href="#/sign-in">Sign in</a><a class="btn btn-outline btn-lg" href="#/sign-in?new=1">Get started</a></div>
    <button class="link-btn" style="align-self:flex-start" data-action="privacy-info">${ic('shield')} Privacy and permissions</button>
  </div>`);
}
function pSignIn(_, q) {
  return authLayout(`<div class="auth-card">
    <a href="#/welcome" class="label-2 row" style="color:var(--text-2)">${ic('arrow_back')} Back</a>
    <div><h1 class="title-3">${q.new ? 'Create your account' : 'Sign in to Syncra'}</h1><p class="text-2" style="margin-top:6px">Use your work account. We’ll find your workspace.</p></div>
    ${q.expired ? `<div class="alert info">${ic('schedule')}<div class="alert-body">Your session expired. Sign in again to continue where you left off.</div></div>` : ''}
    ${q.error ? `<div class="alert error" role="alert">${ic('error')}<div class="alert-body"><span class="alert-title">Sign-in was cancelled.</span> Nothing was created. Try again or use another method.</div></div>` : ''}
    <div class="stack-sm">
      <button class="btn btn-outline btn-lg sso-btn" data-action="sso" data-p="Google"><span class="prov xs" style="background:#4285f4">G</span>Continue with Google</button>
      <button class="btn btn-outline btn-lg sso-btn" data-action="sso" data-p="GitHub"><span class="prov xs prov-github">GH</span>Continue with GitHub</button>
      <button class="btn btn-outline btn-lg sso-btn" data-action="sso" data-p="Microsoft"><span class="prov xs" style="background:#2f6fbf">M</span>Continue with Microsoft</button>
    </div>
    <div class="divider-text">or</div>
    <form class="stack" data-form="signin" novalidate>
      <div class="field"><label for="email">Work email</label><input class="input" id="email" name="email" type="email" autocomplete="email" placeholder="you@company.com" aria-describedby="email-err"><span class="help error" id="email-err" hidden></span></div>
      <button class="btn btn-primary btn-lg" type="submit">Email me a sign-in link</button>
    </form>
    <p class="caption">Tip: enter an address containing “cancel” to see the provider-error state.</p>
  </div>`);
}
function pWorkspaces() {
  const list = Object.values(state.workspaces);
  return authLayout(`<div class="auth-card">
    <div><h1 class="title-3">Choose a workspace</h1><p class="text-2" style="margin-top:6px">Signed in as ${esc(state.user.email)}. <button class="link-btn" data-action="sign-out">Not you?</button></p></div>
    ${list.length ? `<div class="stack-sm">${list.map(w => {
      const n = Object.values(w.connectors).filter(c => SEARCHABLE.includes(c.status)).length;
      return `<button class="ws-row" data-action="pick-ws" data-id="${w.id}"><span class="ws-avatar" style="width:40px;height:40px;font-size:14px">${esc(initials(w.name))}</span><span class="grow"><span class="h4" style="display:block">${esc(w.name)}</span><span class="caption">${w.role === 'admin' ? 'Admin' : 'Member'} · ${w.members.length} member${w.members.length > 1 ? 's' : ''} · ${n} source${n === 1 ? '' : 's'} connected</span></span>${ic('chevron_right')}</button>`;
    }).join('')}</div>` : `<div class="alert info">${ic('info')}<div class="alert-body">You’re not a member of any workspace yet.</div></div>`}
    <div class="divider-text">or</div>
    <div class="grid-2"><a class="btn btn-outline" href="#/create-workspace">${ic('add')} Create workspace</a><button class="btn btn-outline" data-action="join-ws">${ic('mail')} Join with invite</button></div>
  </div>`);
}
function pCreateWs() {
  return authLayout(`<form class="auth-card" data-form="create-ws" novalidate>
    <a href="#/workspaces" class="label-2 row" style="color:var(--text-2)">${ic('arrow_back')} Workspaces</a>
    <div><h1 class="title-3">Create a workspace</h1><p class="text-2" style="margin-top:6px">A workspace is the boundary for your sources, members and answers. Nothing is created until you confirm.</p></div>
    <div class="field"><label for="ws-name">Workspace name</label><input class="input" id="ws-name" name="name" maxlength="48" placeholder="e.g. Northwind Engineering" aria-describedby="ws-name-err"><span class="help error" id="ws-name-err" hidden></span></div>
    <div class="field"><label for="ws-desc">Description <span class="muted">(optional)</span></label><textarea class="textarea" id="ws-desc" name="desc" rows="3" placeholder="What teams or projects is this for?"></textarea></div>
    <div class="row"><a class="btn btn-ghost" href="#/workspaces">Cancel</a><span class="grow"></span><button class="btn btn-primary" type="submit">Create workspace</button></div>
  </form>`);
}

/* ---------- Setup ---------- */
function setupSteps() {
  const ws = W(), cs = Object.values(ws.connectors);
  return [
    ['Connect a source', 'Authorize GitHub, Jira, Slack or Confluence.', cs.some(c => SEARCHABLE.includes(c.status)), '#/integrations', 'Connect source'],
    ['Sync and index content', 'Syncra builds a searchable, permission-aware index.', cs.some(c => c.status === 'connected'), '#/integrations', 'View status'],
    ['Ask a test question', 'Check that answers cite your sources.', ws.conversations.length > 0, '#/ask', 'Ask a question'],
    ['Invite teammates', 'Optional — answers respect each person’s access.', ws.members.length > 1, '#/admin/members', 'Invite'],
  ];
}
function pSetup() {
  const steps = setupSteps(), done = steps.filter(s => s[2]).length, ready = steps[0][2] && steps[1][2];
  return `<div style="max-width:720px;margin:0 auto" class="stack">
    ${pageHeader('Set up ' + esc(W().name), 'A few steps to get trustworthy answers. Progress is saved if you leave.')}
    <div class="row"><div class="progress grow" role="progressbar" aria-valuenow="${done}" aria-valuemin="0" aria-valuemax="4" aria-label="Setup progress"><span style="width:${done * 25}%"></span></div><span class="label-2">${done} of 4</span></div>
    <ol class="checklist">${steps.map(([t, d, ok, href, cta], i) => `<li class="${ok ? 'done' : ''}"><span class="step">${ok ? ic('check') : i + 1}</span><div class="grow"><div class="h4 step-title">${t}</div><div class="body-3 text-2">${d}</div></div>${ok ? '<span class="badge success">Done</span>' : (i === 3 && !isAdmin() ? '<span class="caption">Admins only</span>' : `<a class="btn btn-sm ${i === steps.findIndex(s => !s[2]) ? 'btn-primary' : 'btn-outline'}" href="${href}">${cta}</a>`)}</li>`).join('')}</ol>
    ${ready ? `<div class="card stack-sm" style="border-color:var(--ai-border)"><div class="row">${ic('auto_awesome', '')}<span class="h4">Try a sample question</span></div><p class="text-2 body-3">Edit it if you like — nothing is sent until you press Ask.</p>${composer({ id: 'sample', value: 'Why did we choose PostgreSQL for the payment ledger?', filters: false })}</div>` : ''}
    <div class="row"><span class="grow"></span><button class="btn btn-ghost" data-action="skip-setup">Skip for now</button></div>
  </div>`;
}

/* ---------- Home ---------- */
function pHome() {
  const ws = W(), steps = setupSteps(), setupDone = steps.slice(0, 3).every(s => s[2]);
  const hr = new Date().getHours(), greet = hr < 12 ? 'Good morning' : hr < 18 ? 'Good afternoon' : 'Good evening';
  const noSources = !searchable().length;
  const connRows = Object.keys(P).filter(k => !P[k].unavailable).map(k => { const c = conn(k); return `<a class="row" href="#/integrations/${k}" style="color:inherit;padding:6px 0">${prov(k)}<span class="grow label-1">${P[k].name}</span>${statusBadge(c)}</a>`; }).join('');
  return `${pageHeader(`${greet}, ${esc(state.user.name.split(' ')[0])}`, `Ask anything about ${esc(ws.name)} — answers cite the code, tickets and threads they come from.`)}
  <div class="stack">
    ${noSources ? `<div class="alert info">${ic('info')}<div class="alert-body"><span class="alert-title">No sources connected yet.</span> Answers will be limited until ${isAdmin() || ws.policyMembersConnect ? 'you connect' : 'an admin connects'} GitHub, Jira or Slack. <a href="#/integrations">Go to integrations</a></div></div>` : coverageNotice()}
    <div class="card">${composer({ id: 'home-q' })}
      <div class="row-wrap" style="margin-top:12px">${SUGGESTED.slice(0, 3).map(([i, q]) => `<button class="chip" data-action="ask-suggested" data-q="${esc(q)}">${ic(i)}${esc(q)}</button>`).join('')}</div></div>
    ${!setupDone && !ws.setupSkipped ? `<div class="card row-wrap" style="gap:16px"><div class="icon-tile">${ic('checklist')}</div><div class="grow"><div class="h4">Finish setting up</div><div class="body-3 text-2">${steps.filter(s => s[2]).length} of 4 steps done.</div></div><a class="btn btn-primary" href="#/setup">Continue setup</a></div>` : ''}
    <div class="grid-3">
      <section class="card"><div class="card-head"><h2 class="h4">Recent conversations</h2><a class="label-2" href="#/history">View all</a></div>
        ${ws.conversations.length ? `<div class="stack-sm">${ws.conversations.slice(0, 4).map(c => `<a href="#/ask/${c.id}" class="row" style="color:inherit;align-items:flex-start;padding:4px 0">${ic('chat_bubble', 'muted')}<span class="grow"><span class="label-1" style="display:block">${esc(c.title)}</span><span class="caption">${ago(c.updated)}</span></span></a>`).join('')}</div>` : '<p class="body-3 text-2">Your questions will appear here.</p>'}</section>
      <section class="card"><div class="card-head"><h2 class="h4">Source coverage</h2><a class="label-2" href="#/integrations">Manage</a></div>${connRows}</section>
      <section class="card"><div class="card-head"><h2 class="h4">Needs a look</h2></div>
        ${noSources ? '<p class="body-3 text-2">Syncra flags conflicting sources and undocumented decisions here once content is indexed.</p>' : `<div class="stack-sm">
          <a href="#/decisions/d2" class="alert warning" style="text-decoration:none">${ic('rule')}<div class="alert-body"><div class="alert-title">Potential contradiction</div><div class="body-3 text-2">Auth docs say Auth0; PR #533 deployed Keycloak.</div></div></a>
          <a href="#/decisions/d3" class="alert info" style="text-decoration:none">${ic('help')}<div class="alert-body"><div class="alert-title">Undocumented decision</div><div class="body-3 text-2">Shared Redis cluster has no decision record.</div></div></a></div>`}</section>
    </div>
    ${noSources ? '' : `<section class="card"><div class="card-head"><h2 class="h4">Recent decisions</h2><a class="label-2" href="#/decisions">Decision explorer</a></div><div class="grid-3">${Object.entries(DECISIONS).map(([id, d]) => decisionCard(id, d)).join('')}</div></section>`}
  </div>`;
}

/* ---------- Ask ---------- */
function composer({ id = 'q', value = '', conv = '', ext = false, filters = true, placeholder = 'Ask about decisions, people, code or incidents…' } = {}) {
  const f = state.askFilters;
  const chips = filters && !ext ? `<div class="row-wrap" role="group" aria-label="Limit to sources">${Object.keys(P).filter(k => SEARCHABLE.includes(conn(k).status)).map(k => `<button type="button" class="chip" data-action="toggle-filter" data-p="${k}" aria-pressed="${f.includes(k)}">${prov(k, 'xs')}${P[k].name}</button>`).join('')}
    ${f.length ? '<button type="button" class="link-btn label-2" data-action="clear-filters">Clear filters</button>' : ''}</div>` : '';
  const ctx = ext ? `<label class="switch label-2" title="Sends this tab’s title, description and changed file names. Code and comments are not sent.">
      <input type="checkbox" data-change="page-ctx" ${state.ext.pageCtx ? 'checked' : ''}>Use this page</label>` : '';
  return `<form class="composer" data-form="ask" data-conv="${conv}" data-ext="${ext ? 1 : ''}" novalidate>
    <label for="${id}" class="sr-only">Ask Syncra a question</label>
    <textarea id="${id}" name="q" rows="${ext ? 1 : 2}" placeholder="${placeholder}" data-composer aria-describedby="${id}-hint">${esc(value)}</textarea>
    <div class="composer-foot">${chips}${ctx}<span class="grow"></span><button class="btn btn-generate btn-sm" type="submit">${ic('arrow_upward')} Ask</button></div>
  </form><p class="help composer-hint" id="${id}-hint">${ext && state.ext.pageCtx ? `${ic('description')} Including: ${esc(EXPLAIN[state.ext.page].title)}` : 'Enter to ask · Shift + Enter for a new line'}</p>`;
}
function pAsk() {
  const none = !searchable().length;
  return `<div class="ask-layout"><div class="ask-scroll"><div class="ask-inner">
    <div class="ask-hero"><div class="ai-mark">${ic('auto_awesome')}</div><h1 class="title-3" style="margin-top:16px">Ask Syncra</h1>
      <p class="text-2 body-1" style="margin-top:8px">Answers come only from sources you can access, with citations you can open.</p></div>
    <div class="stack">${none ? `<div class="alert info">${ic('info')}<div class="alert-body">No sources are connected in this workspace, so Syncra has nothing to cite yet. <a href="#/integrations">Connect a source</a></div></div>` : coverageNotice()}
    ${composer({ id: 'ask-q' })}</div>
    <h2 class="eyebrow" style="margin-top:32px">Try asking</h2>
    <div class="suggested">${SUGGESTED.map(([i, q]) => `<button class="prompt-card" data-action="ask-suggested" data-q="${esc(q)}">${ic(i)}<span class="label-1">${esc(q)}</span></button>`).join('')}</div>
  </div></div></div>`;
}
function pConversation({ id }) {
  const c = findConv(id);
  if (!c) return `<div class="page">${pNotFound()}</div>`;
  onMount(() => { const sc = $('.ask-scroll'); if (sc && c.messages.at(-1)?.status === 'pending') sc.scrollTop = sc.scrollHeight; });
  return `<div class="ask-layout"><div class="ask-scroll"><div class="ask-inner">
    <div class="row between" style="margin-bottom:20px;gap:12px"><div class="grow"><h1 class="h2" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.title)}</h1><p class="caption">${ago(c.created)}${c.ext ? ' · Started in Chrome extension' : ''}</p></div>
      <a class="btn btn-outline btn-sm" href="#/ask">${ic('add')} New chat</a></div>
    <div class="thread" aria-live="off">${c.messages.map((m, i) => renderMsg(m, c, i === c.messages.length - 1)).join('')}</div>
  </div></div><div class="ask-dock">${composer({ id: 'follow-q', conv: c.id, placeholder: 'Ask a follow-up…' })}</div></div>`;
}
function renderMsg(m, c, isLast, compact = false) {
  if (m.role === 'user') return `<div class="msg-user" data-msg="${m.id}">${esc(m.text)}</div>`;
  return `<article class="msg-ai" data-msg="${m.id}" aria-label="Syncra answer"><div class="ai-avatar">${ic('auto_awesome')}</div><div class="answer ${m.expanded ? '' : 'collapsed'}">${aiBody(m, c, isLast, compact)}</div></article>`;
}
const STEPS = () => ['Checking your access to each source', `Searching ${searchable().map(k => P[k].name).join(', ') || 'connected sources'}`, 'Ranking evidence and following relationships', 'Writing a grounded answer'];
function aiBody(m, c, isLast, compact) {
  const ids = `data-conv="${c.id}" data-msg="${m.id}"`;
  if (m.status === 'pending') {
    const st = STEPS();
    return `<div class="thinking" role="status"><div class="row between"><span class="label-1" style="color:var(--ai-text)">Searching your connected sources…</span><button class="btn btn-outline btn-sm" data-action="stop" ${ids}>${ic('stop_circle')} Stop</button></div>
      <ul class="thinking-steps">${st.map((s, i) => `<li class="${i < m.step ? 'done' : i === m.step ? 'active' : ''}">${ic(i < m.step ? 'check_circle' : i === m.step ? 'progress_activity' : 'radio_button_unchecked')}${s}</li>`).join('')}</ul>
      <div class="ai-stroke" style="margin-top:12px"></div></div>`;
  }
  if (m.status === 'error') return `<div class="alert error" role="alert">${ic('cloud_off')}<div class="alert-body"><div class="alert-title">The request timed out.</div>Your question is saved. Nothing was answered, so no claims are shown.</div></div>
    <div class="row-wrap"><button class="btn btn-outline btn-sm" data-action="retry" ${ids}>${ic('refresh')} Retry</button><button class="btn btn-ghost btn-sm" data-action="edit-q" ${ids}>${ic('edit')} Edit question</button></div>`;
  if (m.status === 'stopped') return `<div class="alert info">${ic('stop_circle')}<div class="alert-body">Stopped before an answer was written. No partial claims are shown.</div></div><div><button class="btn btn-outline btn-sm" data-action="retry" ${ids}>${ic('refresh')} Retry</button></div>`;
  if (m.key === 'none') return noAnswer(m, c, ids, isLast);
  const a = ANSWERS[m.key];
  const cite = (p) => p.replace(/\{(\d+)\}/g, (_, n) => citeBtn(a.sources[n - 1], n));
  const provs = [...new Set(a.sources.map(s => P[S[s].provider].name))].join(', ');
  const saved = W().saved.some(v => v.type === 'answer' && v.msg === m.id);
  const conf = { High: ['success', 'verified'], Medium: ['info', 'info'], Low: ['warning', 'warning'] }[a.confidence];
  const partial = coverageNotice(a.sources.map(s => S[s].provider));
  return `<div class="answer-meta"><span class="badge ai">${ic('auto_awesome')}AI-generated</span>${state.prefs.confidence ? `<span class="badge ${conf[0]}" title="${esc(a.why)}">${ic(conf[1])}${a.confidence} confidence</span>` : ''}<span class="caption">${a.sources.length} sources · ${provs}</span></div>
    ${partial}
    ${a.conflict ? `<div class="conflict" role="note"><div class="row label-1" style="color:var(--warn-t)">${ic('rule')} Potential contradiction — Syncra hasn’t decided which source is right</div>
      <div class="conflict-grid"><div class="conflict-side"><div class="caption">${a.conflict[0][1]}</div><p class="body-3" style="margin-top:4px">“${a.conflict[0][2]}”</p>${citeBtn(a.conflict[0][0], 1, true)}</div><span class="vs">VS</span>
      <div class="conflict-side"><div class="caption">${a.conflict[1][1]}</div><p class="body-3" style="margin-top:4px">“${a.conflict[1][2]}”</p>${citeBtn(a.conflict[1][0], 2, true)}</div></div></div>` : ''}
    <div class="answer-text">${a.body.map(p => `<p>${cite(p)}</p>`).join('')}${a.more ? `<div class="answer-more"><p style="margin-top:10px">${a.more.map(cite).join('</p><p>')}</p></div>` : ''}</div>
    ${a.more && !m.expanded ? `<button class="link-btn label-2" style="align-self:flex-start" data-action="expand" ${ids}>Show more ${ic('expand_more')}</button>` : ''}
    ${a.impact ? `<div class="stack-sm"><div class="eyebrow">Likely impact area</div><div class="impact-list">${a.impact.map(([i, l, t, n]) => `<div class="impact-item">${ic(i, 'muted')}<div class="grow"><div class="label-2 muted">${l}</div><div class="label-1">${esc(t)} ${citeBtn(a.sources[n - 1], n)}</div></div></div>`).join('')}</div></div>` : ''}
    <div class="stack-sm"><div class="eyebrow">Sources</div><div class="sources">${a.sources.map((s, i) => sourceCard(s, i + 1)).join('')}</div></div>
    ${a.entities && !compact ? `<div class="stack-sm"><div class="eyebrow">Related</div><div class="entity-row">${a.entities.map(([t, i]) => `<span class="tag">${ic(i)}${esc(t)}</span>`).join('')}${a.decision ? `<a class="tag" href="#/decisions/${a.decision}" style="color:var(--link)">${ic('gavel')}Open decision</a>` : ''}</div></div>` : ''}
    ${m.summary === 'loading' ? `<div class="thinking" role="status"><span class="label-1" style="color:var(--ai-text)">Summarizing ${a.sources.length} sources…</span><div class="ai-stroke" style="margin-top:10px"></div></div>` : m.summary ? `<div class="card-flat stack-sm"><div class="row"><span class="badge ai">${ic('auto_awesome')}Source summary</span></div><ul style="margin:0;padding-left:18px">${a.sources.map((s, i) => S[s].access === 'revoked' ? `<li class="muted">Source ${i + 1} is no longer available to you.</li>` : `<li class="body-3" style="margin:4px 0"><strong>${esc(S[s].title)}</strong> — ${esc(S[s].excerpt.split('. ')[0])}. ${citeBtn(s, i + 1)}</li>`).join('')}</ul></div>` : ''}
    ${a.action ? actionCard(m, c, a) : ''}
    ${compact ? '' : `<details><summary class="caption" style="cursor:pointer">How this was answered</summary><ul class="body-3 text-2" style="margin:8px 0 0;padding-left:18px">
      <li>Permission check first: only items you can open in ${provs} were searched.</li><li>Hybrid retrieval: semantic + keyword search, plus knowledge-graph relationships.</li>
      <li>${a.sources.length * 4 + 3} candidates ranked → ${a.sources.length} cited.</li><li>Confidence ${a.confidence.toLowerCase()}: ${esc(a.why)}</li></ul></details>`}
    <div class="msg-actions" role="group" aria-label="Answer actions">
      <button class="icon-btn sm" data-action="copy-answer" ${ids} aria-label="Copy answer" title="Copy answer">${ic('content_copy')}</button>
      <button class="icon-btn sm" data-action="save-answer" ${ids} aria-pressed="${saved}" aria-label="${saved ? 'Remove from saved' : 'Save answer'}" title="${saved ? 'Remove from saved' : 'Save answer'}">${ic('bookmark', saved ? 'fill' : '')}</button>
      <button class="icon-btn sm" data-action="fb-up" ${ids} aria-pressed="${m.fb === 'up'}" aria-label="Helpful" title="Helpful">${ic('thumb_up', m.fb === 'up' ? 'fill' : '')}</button>
      <button class="icon-btn sm" data-action="fb-down" ${ids} aria-pressed="${m.fb === 'down'}" aria-label="Not helpful" title="Not helpful">${ic('thumb_down', m.fb === 'down' ? 'fill' : '')}</button>
      ${!m.summary ? `<button class="btn btn-ghost btn-sm" data-action="summarize" ${ids}>${ic('summarize')} Summarize sources</button>` : ''}
    </div>
    ${m.fbOpen ? feedbackBox(m, c) : ''}
    ${isLast && a.followups ? `<div class="followups" aria-label="Suggested follow-ups"><div class="eyebrow">Ask a follow-up</div>${a.followups.map(q => `<button class="followup" data-action="followup" data-conv="${c.id}" data-q="${esc(q)}">${ic('subdirectory_arrow_right')}<span class="body-3">${esc(q)}</span></button>`).join('')}</div>` : ''}`;
}
function noAnswer(m, c, ids, isLast) {
  const srcs = searchable();
  return `<div class="answer-meta"><span class="badge ai">${ic('auto_awesome')}AI-generated</span><span class="badge">${ic('search_off')}No evidence found</span></div>
    <div class="answer-text"><p>I couldn’t find evidence about this in the sources you can access, so I won’t guess.</p></div>
    <div class="card-flat stack-sm"><div class="eyebrow">Searched</div>${srcs.length ? srcs.map(k => { const x = conn(k); return `<div class="row body-3">${prov(k, 'xs')}<span class="grow">${P[k].name}</span><span class="caption">${x.status === 'indexing' ? `still indexing (${x.progress}%)` : x.status === 'attention' ? 'not synced recently' : `${(x.items || 0).toLocaleString()} items`}</span></div>`; }).join('') : '<p class="body-3 text-2">No sources are connected in this workspace.</p>'}
    ${c.filters?.length ? `<p class="caption">Limited to: ${c.filters.map(k => P[k].name).join(', ')}</p>` : ''}</div>
    <div class="stack-sm"><div class="eyebrow">Try</div><ul class="body-3 text-2" style="margin:0;padding-left:18px"><li>Use specific names: a service, ticket key or person.</li>${c.filters?.length ? '<li>Remove the source filters.</li>' : ''}<li>${conn('confluence').status === 'not_connected' ? '<a href="#/integrations/confluence">Connect Confluence</a> if the answer lives in docs.' : 'Check that the right sources are in scope.'}</li></ul></div>
    <div class="msg-actions"><button class="icon-btn sm" data-action="fb-down" ${ids} aria-label="Report a missing answer" title="Report a missing answer">${ic('flag')}</button></div>
    ${m.fbOpen ? feedbackBox(m, c) : ''}
    ${isLast ? `<div class="followups"><div class="eyebrow">Example questions</div>${SUGGESTED.slice(0, 2).map(([, q]) => `<button class="followup" data-action="followup" data-conv="${c.id}" data-q="${esc(q)}">${ic('subdirectory_arrow_right')}<span class="body-3">${esc(q)}</span></button>`).join('')}</div>` : ''}`;
}
function citeBtn(sid, n, labelled = false) {
  const s = S[sid], gone = s.access === 'revoked';
  if (labelled) return `<button class="link-btn label-2" style="margin-top:6px" data-action="cite" data-src="${sid}">${ic('open_in_new')} View source</button>`;
  return `<button class="cite ${gone ? 'unavailable' : ''}" data-action="cite" data-src="${sid}" aria-label="Source ${n}: ${esc(gone ? 'unavailable' : s.title)}">${n}</button>`;
}
function sourceCard(sid, n) {
  const s = S[sid], gone = s.access === 'revoked';
  return `<button class="source-card" data-action="cite" data-src="${sid}" aria-label="Preview source ${n}: ${esc(gone ? 'unavailable' : s.title)}">
    <span class="row"><span class="n">${n}</span>${prov(s.provider, 'xs')}<span class="caption grow">${P[s.provider].name} · ${KIND[s.kind][0]}</span></span>
    ${gone ? `<span class="t muted">${ic('lock')} Source unavailable</span><span class="caption">Your access was removed after this answer was written.</span>` : `<span class="t">${esc(s.title)}</span><span class="caption">${esc(person(s.author).name)} · ${fmtDate(s.date)}</span>`}</button>`;
}
function actionCard(m, c, a) {
  if (m.action) return `<div class="alert success">${ic('check_circle')}<div class="alert-body"><span class="alert-title">${esc(m.action)} created in Jira.</span> Recorded in the audit log. <a href="#/admin/audit">View audit log</a></div></div>`;
  return `<div class="action-card"><div class="icon-tile sm" style="background:transparent;color:var(--ai-icon)">${ic('add_task')}</div><div class="grow"><div class="label-1">Suggested action: create a Jira task</div><div class="body-3 text-2">${esc(a.action.summary)} · You’ll review it before anything is created.</div></div>
    <button class="btn btn-ai btn-sm" data-action="action-preview" data-conv="${c.id}" data-msg="${m.id}">${ic('visibility')} Preview task</button></div>`;
}
function feedbackBox(m, c) {
  const reasons = ['Incorrect', 'Missing context', 'Out of date', 'Bad sources', 'Other'];
  const f = m.fbDraft || { reasons: [], text: '' };
  return `<form class="feedback-box stack-sm" data-form="feedback" data-conv="${c.id}" data-msg="${m.id}">
    <div class="label-1">What went wrong?</div>
    <div class="row-wrap" role="group" aria-label="Reasons">${reasons.map(r => `<button type="button" class="chip" data-action="fb-reason" data-r="${r}" data-conv="${c.id}" data-msg="${m.id}" aria-pressed="${f.reasons.includes(r)}">${r}</button>`).join('')}</div>
    <label class="sr-only" for="fb-${m.id}">Details</label><textarea class="textarea" id="fb-${m.id}" name="text" rows="2" placeholder="Optional: tell us what the answer should have said" data-input="fb-text" data-conv="${c.id}" data-msg="${m.id}">${esc(f.text)}</textarea>
    <p class="caption">Feedback is reviewed by the Syncra team to improve retrieval. It doesn’t change answers immediately.</p>
    <div class="row"><span class="grow"></span><button type="button" class="btn btn-ghost btn-sm" data-action="fb-cancel" data-conv="${c.id}" data-msg="${m.id}">Cancel</button><button class="btn btn-primary btn-sm" type="submit">Submit feedback</button></div></form>`;
}

function pickAnswer(q, filters) {
  const avail = searchable();
  for (const k of ANSWER_ORDER) {
    const a = ANSWERS[k];
    if (!a.match.test(q)) continue;
    const ok = a.sources.some(s => avail.includes(S[s].provider) && (!filters.length || filters.includes(S[s].provider)));
    return ok ? k : 'none';
  }
  return 'none';
}
function ask(text, convId, ext = false) {
  const ws = W();
  let c = convId && findConv(convId);
  const isNew = !c;
  if (isNew) { c = { id: uid('c'), title: text.slice(0, 90), created: Date.now(), messages: [], filters: [...state.askFilters], ext }; ws.conversations.unshift(c); }
  else { ws.conversations = [c, ...ws.conversations.filter(x => x !== c)]; }
  c.messages.push({ role: 'user', id: uid('u'), text });
  const m = { role: 'ai', id: uid('a'), q: text, status: 'pending', step: 0, ctx: ext && state.ext.pageCtx ? state.ext.page : null };
  c.messages.push(m); c.updated = Date.now();
  if (ext) { state.ext.conv = c.id; rerender(); scrollPanel(); }
  else if (isNew) go('/ask/' + c.id); else { rerender(); const sc = $('.ask-scroll'); if (sc) sc.scrollTop = sc.scrollHeight; }
  announce('Searching your connected sources');
  run(c, m);
}
function run(c, m) {
  const n = STEPS().length;
  const tick = () => {
    if (m.status !== 'pending') return;
    m.step++;
    if (m.step >= n) {
      if (/\b(fail|timeout)\b/i.test(m.q)) m.status = 'error';
      else { m.status = 'done'; m.key = m.ctx && m.ctx !== 'blog' && /this|change|pr|page/i.test(m.q) && !ANSWER_ORDER.some(k => ANSWERS[k].match.test(m.q)) ? 'auth' : pickAnswer(m.q, c.filters || []); }
      save(); announce(m.status === 'error' ? 'Request failed' : 'Answer ready');
    } else setTimeout(tick, 650);
    refreshMsg(c, m);
  };
  setTimeout(tick, 650);
}
function refreshMsg(c, m) {
  const el = $(`[data-msg="${m.id}"]`);
  if (!el) return;
  el.outerHTML = renderMsg(m, c, c.messages.at(-1) === m, !!el.closest('.panel'));
}
function scrollPanel() { const b = $('.panel-body'); if (b) b.scrollTop = b.scrollHeight; }
function getMsg(el) { const c = findConv(el.dataset.conv); return { c, m: c?.messages.find(x => x.id === el.dataset.msg) }; }

/* ---------- Search ---------- */
function pSearch(_, q) {
  const query = q.q || '', srcF = (q.src || '').split(',').filter(Boolean), type = q.type || '', sort = q.sort || 'relevance';
  const avail = searchable();
  const toks = tokens(query);
  let results = Object.entries(S).filter(([, s]) => s.access !== 'revoked' && avail.includes(s.provider) && (!srcF.length || srcF.includes(s.provider)) && (!type || s.kind === type));
  if (toks.length) results = results.map(([id, s]) => { const t = s.title.toLowerCase(), e = s.excerpt.toLowerCase(); return [id, s, toks.reduce((n, k) => n + (t.includes(k) ? 3 : 0) + (e.includes(k) ? 1 : 0), 0)]; }).filter(r => r[2] > 0);
  else results = results.map(([id, s]) => [id, s, 0]);
  results.sort((a, b) => sort === 'newest' || !toks.length ? b[1].date.localeCompare(a[1].date) : b[2] - a[2]);
  const qs = (patch) => { const o = { q: query, src: srcF.join(','), type, sort, ...patch }; return '/search?' + new URLSearchParams(Object.entries(o).filter(([, v]) => v)).toString(); };
  const saved = W().saved;
  const filtersOn = srcF.length || type;
  return `${pageHeader('Search', 'Find documents, tickets, pull requests and threads across your connected sources.')}
  <form class="row" data-form="search" role="search" style="margin-bottom:16px">
    <div class="search-input grow">${ic('search')}<label for="sq" class="sr-only">Search query</label><input class="input" id="sq" name="q" value="${esc(query)}" placeholder="Search by keyword, ticket key or file name" autocomplete="off"></div>
    ${query ? `<a class="btn btn-ghost" href="#${qs({ q: '' })}" aria-label="Clear search">${ic('close')}</a>` : ''}<button class="btn btn-primary" type="submit">Search</button></form>
  ${!avail.length ? empty('hub', 'No sources to search', 'Connect GitHub, Jira or Slack and Syncra will index content you have access to.', `<a class="btn btn-primary" href="#/integrations">Go to integrations</a>`) : `
  <div class="search-layout">
    <aside class="stack" aria-label="Filters">
      <div class="filter-group"><div class="eyebrow">Source</div><div class="row-wrap">${avail.map(k => `<a class="chip" href="#${qs({ src: srcF.includes(k) ? srcF.filter(x => x !== k).join(',') : [...srcF, k].join(',') })}" aria-pressed="${srcF.includes(k)}" role="button">${prov(k, 'xs')}${P[k].name}</a>`).join('')}</div></div>
      <div class="field"><label class="eyebrow" for="stype">Content type</label><select class="select" id="stype" data-change="search-param" data-key="type"><option value="">All types</option>${Object.entries(KIND).map(([k, [l]]) => `<option value="${k}" ${type === k ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label class="eyebrow" for="ssort">Sort by</label><select class="select" id="ssort" data-change="search-param" data-key="sort"><option value="relevance">Relevance</option><option value="newest" ${sort === 'newest' ? 'selected' : ''}>Newest</option></select></div>
      ${filtersOn ? `<a class="link-btn label-2" href="#${qs({ src: '', type: '' })}">Clear all filters</a>` : ''}
    </aside>
    <section aria-label="Results">
      ${coverageNotice()}
      <p class="caption" style="margin:12px 0 4px" aria-live="polite">${query ? `${results.length} result${results.length === 1 ? '' : 's'} for “${esc(query)}”` : 'Recently updated across your sources'}</p>
      ${results.length ? results.map(([id, s]) => { const isSaved = saved.some(v => v.type === 'source' && v.src === id); return `<article class="result">${prov(s.provider)}<div class="grow" style="min-width:0">
        <h3><a href="#" data-action="open-original" data-src="${id}">${hl(s.title, query)}</a></h3>
        <div class="caption">${P[s.provider].name} · ${KIND[s.kind][0]} · ${esc(s.loc)} · ${esc(person(s.author).name)} · ${fmtDate(s.date)}</div>
        <p class="body-3">${hl(s.excerpt, query)}</p>
        <div class="row-wrap"><button class="btn btn-ghost btn-sm" data-action="cite" data-src="${id}">${ic('visibility')} Preview</button><button class="btn btn-ghost btn-sm" data-action="open-original" data-src="${id}">${ic('open_in_new')} Open original</button>
        <button class="btn btn-ghost btn-sm" data-action="save-source" data-src="${id}" aria-pressed="${isSaved}">${ic('bookmark', isSaved ? 'fill' : '')} ${isSaved ? 'Saved' : 'Save'}</button>
        ${query ? `<button class="btn btn-ghost btn-sm" data-action="ask-suggested" data-q="${esc(query)}">${ic('auto_awesome')} Ask about this</button>` : ''}</div></div></article>`; }).join('')
      : empty('search_off', 'No results', `Nothing matched “${esc(query)}”${filtersOn ? ' with the current filters' : ''}. Try broader terms${filtersOn ? ', remove filters' : ''}, or connect another source.`, `${filtersOn ? `<a class="btn btn-outline" href="#${qs({ src: '', type: '' })}">Remove filters</a>` : ''}<button class="btn btn-outline" data-action="ask-suggested" data-q="${esc(query)}">${ic('auto_awesome')} Ask Syncra instead</button><a class="btn btn-ghost" href="#/integrations">Connect a source</a>`)}
    </section></div>`}`;
}

/* ---------- Source preview drawer ---------- */
function openSource(sid) {
  const s = S[sid], gone = s.access === 'revoked';
  const isSaved = W().saved.some(v => v.type === 'source' && v.src === sid);
  const accessible = searchable().includes(s.provider);
  openOverlay(`${dHead(gone ? 'Source unavailable' : esc(s.title), prov(s.provider))}
    <div class="drawer-body">
      <div class="row-wrap">${badge('', KIND[s.kind][1], KIND[s.kind][0])}${gone ? badge('error', 'lock', 'Access revoked') : accessible ? badge('success', 'check_circle', 'Available') : badge('warning', 'link_off', 'Source disconnected')}</div>
      ${gone ? `<div class="alert error">${ic('lock')}<div class="alert-body"><div class="alert-title">You no longer have access to this item.</div>It was available when the answer was written. Syncra doesn’t show cached content you can’t open in ${P[s.provider].name}.</div></div>
        <div class="text-2 body-3">Ask the channel owner for access, or search for another source.</div>` : `
      <div><div class="eyebrow">Cited excerpt</div><blockquote style="margin:8px 0 0;padding:12px 14px;border-left:3px solid var(--primary);background:var(--surface);border-radius:0 var(--r) var(--r) 0" class="body-2">${esc(s.excerpt)}</blockquote></div>
      <dl class="stack-sm" style="margin:0">${[['Source', P[s.provider].name], ['Location', s.loc], ['Author', person(s.author).name], ['Updated', fmtDate(s.date)]].map(([k, v]) => `<div class="row between"><dt class="caption">${k}</dt><dd class="label-1" style="margin:0;text-align:right">${esc(v)}</dd></div>`).join('')}</dl>`}
    </div>
    <div class="drawer-foot">${gone ? `<a class="btn btn-outline" href="#/search" data-action="close-overlay-nav">Search again</a>` : `<button class="btn btn-ghost" data-action="save-source" data-src="${sid}" data-in-drawer="1" aria-pressed="${isSaved}">${ic('bookmark', isSaved ? 'fill' : '')} ${isSaved ? 'Saved' : 'Save source'}</button><button class="btn btn-primary" data-action="open-original" data-src="${sid}">${ic('open_in_new')} Open original</button>`}</div>`, { drawer: true, label: 'Source preview' });
}

/* ---------- Decisions ---------- */
function decisionCard(id, d) {
  return `<a class="card interactive stack-sm" href="#/decisions/${id}" style="text-decoration:none">
    <div class="row between">${badge(...d.status)}<span class="caption">${fmtDate(d.date)}</span></div>
    <div class="h4">${esc(d.title)}</div><p class="body-3 text-2">${esc(d.summary)}</p>
    <div class="row between" style="margin-top:auto"><div class="avatar-stack">${d.people.map(p => avatar(person(p).name, 'sm')).join('')}</div><span class="caption">${d.sources.length} sources · ${esc(d.ref)}</span></div></a>`;
}
function pDecisions(_, q) {
  const view = q.view || 'list';
  const none = !searchable().length;
  const tabs = `<div class="tabs" role="tablist"><a class="tab" role="tab" href="#/decisions" aria-selected="${view === 'list'}">Decisions</a><a class="tab" role="tab" href="#/decisions?view=timeline" aria-selected="${view === 'timeline'}">Timeline</a></div>`;
  if (none) return pageHeader('Decision explorer', 'Reconstructs what was decided, why, by whom and what happened next.') + empty('gavel', 'No decisions yet', 'Syncra finds decisions in ADRs, tickets, pull requests and discussions once sources are connected.', '<a class="btn btn-primary" href="#/integrations">Connect a source</a>');
  if (view === 'timeline') {
    const items = Object.entries(DECISIONS).flatMap(([id, d]) => d.timeline.map(t => ({ id, d, t }))).sort((a, b) => b.t[0].localeCompare(a.t[0]));
    let month = '';
    return `${pageHeader('Decision explorer', 'How organizational knowledge evolved, newest first.')}${tabs}
      <div class="card"><ol class="timeline">${items.map(({ id, d, t }) => { const m = t[0].slice(0, 7); const head = m !== month ? (month = m, `<li style="padding-bottom:12px"><span class="eyebrow">${MONTHS[+m.slice(5) - 1]} ${m.slice(0, 4)}</span></li>`) : ''; const s = S[t[2]];
        return `${head}<li class="${t[4] ? 'key' : ''}"><span class="node">${ic(t[3])}</span><div class="row-wrap" style="justify-content:space-between"><div><div class="label-1">${esc(t[1])}</div><div class="caption">${fmtDate(t[0])} · <a href="#/decisions/${id}">${esc(d.title)}</a></div></div><button class="chip" data-action="cite" data-src="${t[2]}">${prov(s.provider, 'xs')}${esc(s.title.split(' ').slice(0, 3).join(' '))}</button></div></li>`; }).join('')}</ol></div>`;
  }
  return `${pageHeader('Decision explorer', 'Reconstructs what was decided, why, by whom and what happened next.')}${tabs}
    <div class="grid-3">${Object.entries(DECISIONS).map(([id, d]) => decisionCard(id, d)).join('')}</div>`;
}
function graphSvg(d) {
  const pos = [[100, 46], [500, 46], [100, 234], [500, 234]];
  const node = (x, y, label, center, p) => `<g class="node ${center ? 'center' : ''}"><rect x="${x - 78}" y="${y - 18}" width="156" height="36" rx="8"/>${p ? `<rect x="${x - 70}" y="${y - 9}" width="18" height="18" rx="4" class="prov-${p}" style="fill:${{ slack: '#4a154b', jira: '#2c64c9', github: '#57606a' }[p]};stroke:none"/>` : ''}<text x="${x + (p ? 10 : 0)}" y="${y + 4}" text-anchor="middle">${esc(label)}</text></g>`;
  return `<svg class="graph" viewBox="0 0 600 280" role="img" aria-label="Relationships for ${esc(d.title)}: ${d.graph.map(g => `${g[0]} ${g[1]}`).join(', ')}">
    ${d.graph.map((g, i) => `<path class="edge" d="M300 140 L${pos[i][0]} ${pos[i][1]}"/><text class="edge-label" x="${(300 + pos[i][0]) / 2}" y="${(140 + pos[i][1]) / 2 - 6}" text-anchor="middle">${g[0]}</text>`).join('')}
    ${d.graph.map((g, i) => node(pos[i][0], pos[i][1], g[1], false, g[2])).join('')}
    ${node(300, 140, d.ref === 'No ADR' || d.ref === 'Inferred' ? d.title.split(' ').slice(0, 3).join(' ') : d.ref, true)}</svg>`;
}
function pDecision({ id }) {
  const d = DECISIONS[id];
  if (!d || !searchable().length) return pNotFound();
  const cite = p => p.replace(/\{(\d+)\}/g, (_, n) => citeBtn(d.sources[n - 1], n));
  return `${pageHeader(esc(d.title), '', `<button class="btn btn-outline" data-action="ask-suggested" data-q="${esc(id === 'd1' ? 'Who was involved in ADR-014?' : id === 'd2' ? 'Which auth provider do we use?' : 'What could be affected if we replace Redis?')}">${ic('auto_awesome')} Ask about this</button>${d.contradiction || id === 'd3' ? `<button class="btn btn-primary" data-action="action-preview-decision" data-id="${id}">${ic('add_task')} Create Jira task</button>` : ''}`, crumbs([['Decisions', '/decisions'], [d.title]]))}
  <div class="row-wrap" style="margin:-12px 0 24px">${badge(...d.status)}<span class="tag">${ic('gavel')}${esc(d.ref)}</span><span class="tag">${ic('dns')}${esc(d.service)}</span><span class="caption">${fmtDate(d.date)}</span></div>
  ${d.contradiction ? `<div class="alert warning" style="margin-bottom:16px">${ic('rule')}<div class="alert-body"><span class="alert-title">Potential contradiction.</span> ${cite('The architecture doc says Auth0 only {1}, while PR #533 deployed Keycloak {2}.')} Syncra labels this as potential — it doesn’t decide which source is correct.</div></div>` : ''}
  <div class="split">
    <div class="stack">
      <section class="card"><h2 class="h4">What was decided</h2><p class="body-1" style="margin-top:8px">${esc(d.summary)}</p>
        <h3 class="eyebrow" style="margin-top:20px">Why</h3><ul class="body-2" style="margin:8px 0 0;padding-left:20px">${d.why.map(w => `<li style="margin:6px 0">${cite(w)}</li>`).join('')}</ul></section>
      <section class="card"><h2 class="h4" style="margin-bottom:8px">Relationships</h2>${graphSvg(d)}</section>
      <section class="card"><h2 class="h4" style="margin-bottom:16px">Timeline</h2><ol class="timeline">${d.timeline.map(t => `<li class="${t[4] ? 'key' : ''}"><span class="node">${ic(t[3])}</span><div class="row-wrap" style="justify-content:space-between"><div><div class="label-1">${esc(t[1])}</div><div class="caption">${fmtDate(t[0])}</div></div><button class="chip" data-action="cite" data-src="${t[2]}">${prov(S[t[2]].provider, 'xs')}View source</button></div></li>`).join('')}</ol></section>
    </div>
    <div class="stack">
      <section class="card"><h2 class="h4" style="margin-bottom:12px">People involved</h2><div class="stack-sm">${d.people.map((p, i) => `<div class="row">${avatar(person(p).name)}<div class="grow"><div class="label-1">${esc(person(p).name)}</div><div class="caption">${esc(person(p).role)}</div></div>${p === d.owner ? '<span class="badge brand">Owner</span>' : i === 1 ? '<span class="badge">Approver</span>' : ''}</div>`).join('')}</div></section>
      <section class="card"><h2 class="h4" style="margin-bottom:12px">Change impact</h2><div class="stack-sm">${d.impact.map(([i, t, s]) => `<div class="impact-item">${ic(i, 'muted')}<div><div class="label-1">${esc(t)}</div><div class="caption">${esc(s)}</div></div></div>`).join('')}</div></section>
      <section class="card"><h2 class="h4" style="margin-bottom:12px">Evidence</h2><div class="sources" style="grid-template-columns:1fr">${d.sources.map((s, i) => sourceCard(s, i + 1)).join('')}</div></section>
    </div></div>`;
}

/* ---------- History & Saved ---------- */
function pHistory(_, q) {
  const list = [...W().conversations].sort((a, b) => q.sort === 'oldest' ? a.updated - b.updated : b.updated - a.updated);
  return `${pageHeader('History', 'Your conversations in this workspace. Only you can see them.', '<a class="btn btn-primary" href="#/ask">' + ic('add') + ' New conversation</a>')}
  ${list.length ? `<div class="row" style="margin-bottom:16px"><div class="search-input grow">${ic('search')}<label for="hq" class="sr-only">Search history</label><input class="input" id="hq" placeholder="Search conversations" data-input="filter-rows" data-target="#hist"></div>
    <label class="sr-only" for="hsort">Sort</label><select class="select" id="hsort" style="width:auto" data-change="history-sort"><option value="newest">Newest first</option><option value="oldest" ${q.sort === 'oldest' ? 'selected' : ''}>Oldest first</option></select></div>
  <div class="table-wrap"><table id="hist"><thead><tr><th>Conversation</th><th class="hide-sm">Messages</th><th>Updated</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
  ${list.map(c => `<tr class="clickable" data-row="${esc(c.title.toLowerCase())}" data-action="nav" data-href="/ask/${c.id}"><td><div class="label-1">${esc(c.title)}</div>${c.ext ? '<span class="caption">'+ ic('extension') + ' From Chrome extension</span>' : ''}</td><td class="hide-sm">${c.messages.length}</td><td class="caption">${ago(c.updated)}</td>
    <td style="text-align:right"><button class="icon-btn sm" data-action="delete-conv" data-id="${c.id}" aria-label="Delete conversation: ${esc(c.title)}">${ic('delete')}</button></td></tr>`).join('')}
  </tbody></table><p class="empty-filter body-3 text-2" style="padding:16px" hidden>No conversations match that search.</p></div>`
  : `<div class="card">${empty('history', 'No conversations yet', 'Questions you ask will appear here so you can pick up where you left off.', '<a class="btn btn-primary" href="#/ask">Ask a question</a>')}</div>`}`;
}
function pSaved(_, q) {
  const tab = q.tab || 'all', ws = W();
  const items = ws.saved.filter(v => tab === 'all' || v.type + 's' === tab);
  const tabs = `<div class="tabs" role="tablist">${[['all', 'All'], ['answers', 'Answers'], ['sources', 'Sources']].map(([k, l]) => `<a class="tab" role="tab" href="#/saved${k === 'all' ? '' : '?tab=' + k}" aria-selected="${tab === k}">${l} <span class="caption">${k === 'all' ? ws.saved.length : ws.saved.filter(v => v.type + 's' === k).length}</span></a>`).join('')}</div>`;
  const row = v => {
    if (v.type === 'answer') {
      const c = findConv(v.conv), m = c?.messages.find(x => x.id === v.msg);
      if (!c || !m) return '';
      const a = ANSWERS[m.key];
      return `<div class="card row" style="align-items:flex-start;gap:14px"><div class="icon-tile sm" style="background:var(--ai-surface);color:var(--ai-icon)">${ic('auto_awesome')}</div>
        <div class="grow" style="min-width:0"><a class="h4" href="#/ask/${c.id}" style="color:var(--text)">${esc(m.q)}</a><p class="body-3 text-2" style="margin:4px 0">${a ? esc(stripTags(a.body[0])).slice(0, 180) + '…' : 'No evidence found.'}</p><span class="caption">Saved answer · ${ago(v.at)} · ${a ? a.sources.length + ' citations' : ''}</span></div>
        <button class="btn btn-ghost btn-sm" data-action="unsave" data-id="${v.id}">${ic('bookmark_remove')} Remove from saved</button></div>`;
    }
    const s = S[v.src], gone = s.access === 'revoked' || !searchable().includes(s.provider);
    return `<div class="card row" style="align-items:flex-start;gap:14px">${prov(s.provider)}<div class="grow" style="min-width:0">
      ${gone ? `<div class="h4 muted">${ic('lock')} Source unavailable</div><p class="body-3 text-2">Access to this ${P[s.provider].name} item has changed.</p>` : `<button class="link-btn h4" style="color:var(--text);text-align:left" data-action="cite" data-src="${v.src}">${esc(s.title)}</button><p class="caption" style="margin-top:4px">${P[s.provider].name} · ${KIND[s.kind][0]} · saved ${ago(v.at)}</p>`}</div>
      <div class="row">${gone ? '' : `<button class="btn btn-ghost btn-sm" data-action="open-original" data-src="${v.src}">${ic('open_in_new')} Open original</button>`}<button class="btn btn-ghost btn-sm" data-action="unsave" data-id="${v.id}">${ic('bookmark_remove')} Remove</button></div></div>`;
  };
  return `${pageHeader('Saved', 'Answers and sources you bookmarked. Removing a bookmark never deletes the source.')}${tabs}
    ${items.length ? `<div class="stack-sm">${items.map(row).join('')}</div>` : `<div class="card">${empty('bookmark', 'Nothing saved here yet', 'Use the bookmark button under an answer, or “Save” on a search result, to keep it for later.', '<a class="btn btn-primary" href="#/ask">Ask a question</a><a class="btn btn-outline" href="#/search">Search sources</a>')}</div>`}`;
}

/* ---------- Integrations ---------- */
function connectorCta(k) {
  const c = conn(k), canConnect = isAdmin() || W().policyMembersConnect;
  if (P[k].unavailable) return `<button class="btn btn-outline btn-sm" disabled>Coming later</button>`;
  if (['not_connected', 'disconnected'].includes(c.status)) return canConnect ? `<button class="btn btn-primary btn-sm" data-action="connect" data-k="${k}">Connect</button>` : `<button class="btn btn-outline btn-sm" disabled title="Only admins can connect sources">Connect</button>`;
  if (c.status === 'connecting') return `<button class="btn btn-primary btn-sm" data-action="connect" data-k="${k}">Continue setup</button>`;
  if (c.status === 'attention' && isAdmin()) return `<button class="btn btn-primary btn-sm" data-action="reconnect" data-k="${k}">Reconnect</button><a class="btn btn-outline btn-sm" href="#/integrations/${k}">Manage</a>`;
  return `<a class="btn btn-outline btn-sm" href="#/integrations/${k}">${isAdmin() ? 'Manage' : 'View details'}</a>`;
}
function connectorSummary(k) {
  const c = conn(k);
  if (c.status === 'indexing') return `<div class="stack-sm"><div class="progress" role="progressbar" aria-valuenow="${c.progress}" aria-valuemin="0" aria-valuemax="100" aria-label="${P[k].name} indexing"><span style="width:${c.progress}%"></span></div><span class="caption">Indexing ${c.progress}% · not fully searchable yet</span></div>`;
  if (c.status === 'attention') return `<div class="alert warning" style="padding:8px 12px">${ic('error')}<div class="alert-body body-3">Authorization expired ${ago(c.lastSync).toLowerCase()}. Indexed content is still searchable but may be stale.</div></div>`;
  if (c.lastError) return `<div class="alert error" style="padding:8px 12px">${ic('error')}<div class="alert-body body-3">${esc(c.lastError)}</div></div>`;
  if (c.status === 'connected') return `<span class="caption">${c.scope.length} ${P[k].scopeLabel} · ${(c.items || 0).toLocaleString()} items · synced ${ago(c.lastSync).toLowerCase()}</span>`;
  return '';
}
function pIntegrations() {
  const canConnect = isAdmin() || W().policyMembersConnect;
  return `${pageHeader('Integrations', 'Syncra indexes what you choose, with each item’s original permissions. Answers only use content the asker can open.', isAdmin() ? '<a class="btn btn-outline" href="#/admin/sync">' + ic('monitor_heart') + ' Sync health</a>' : '')}
  ${!canConnect ? `<div class="alert info" style="margin-bottom:16px">${ic('info')}<div class="alert-body">Only workspace admins can connect or change sources here. You can view status.</div></div>` : ''}
  <div class="grid-3">${Object.keys(P).map(k => `<article class="card stack-sm" style="${P[k].unavailable ? 'opacity:.7' : ''}">
    <div class="row">${prov(k, 'lg')}<div class="grow"><h2 class="h4">${P[k].name}</h2>${statusBadge(conn(k))}</div></div>
    <p class="body-3 text-2">${P[k].desc}</p>${connectorSummary(k)}
    <div class="row-wrap" style="margin-top:auto;padding-top:8px">${connectorCta(k)}</div></article>`).join('')}</div>`;
}
function pConnector({ provider: k }) {
  if (!P[k] || P[k].unavailable) return pNotFound();
  const c = conn(k), p = P[k], admin = isAdmin(), live = SEARCHABLE.includes(c.status);
  const actions = admin && live ? `<button class="btn btn-outline" data-action="sync-now" data-k="${k}" ${c.syncing || c.status === 'indexing' || c.status === 'attention' ? 'disabled' : ''}>${ic('sync')} ${c.syncing ? 'Syncing…' : 'Sync now'}</button>
    <button class="btn btn-outline" data-action="reconnect" data-k="${k}">${ic('key')} Reconnect</button><button class="btn btn-outline" data-action="change-scope" data-k="${k}">${ic('tune')} Change scope</button>
    <button class="btn btn-danger-outline btn" data-action="disconnect" data-k="${k}">${ic('link_off')} Disconnect</button>` : '';
  return `${pageHeader(`<span class="row" style="gap:12px">${prov(k, 'lg')}${p.name}</span>`, p.desc, actions, crumbs([['Integrations', '/integrations'], [p.name]]))}
  ${!live ? `<div class="card">${empty('link_off', c.status === 'disconnected' ? `${p.name} is disconnected` : `${p.name} isn’t connected`, `Connect ${p.name} to index ${p.scopeLabel} you choose. Syncra only reads — it never changes anything in ${p.name}${k === 'jira' ? ' unless you approve a specific action' : ''}.`, connectorCta(k))}${c.lastError ? `<div class="alert error" style="max-width:520px;margin:0 auto">${ic('error')}<div class="alert-body">${esc(c.lastError)}</div></div>` : ''}</div>` : `
  ${c.status === 'attention' ? `<div class="alert warning" style="margin-bottom:16px">${ic('error')}<div class="alert-body"><div class="alert-title">Syncra can’t reach ${p.name}.</div>The authorization was revoked or expired (<span class="mono">${esc(c.error)}</span>). Content indexed before ${ago(c.lastSync).toLowerCase()} is still searchable; newer messages are missing. ${admin ? '' : 'Ask an admin to reconnect.'}</div>${admin ? `<button class="btn btn-primary btn-sm" data-action="reconnect" data-k="${k}">Reconnect</button>` : ''}</div>` : ''}
  ${!admin ? `<div class="alert info" style="margin-bottom:16px">${ic('visibility')}<div class="alert-body">You’re viewing this as a member. Only admins can sync, change scope or disconnect.</div></div>` : ''}
  <div class="grid-2" style="margin-bottom:16px">
    <section class="card stack-sm"><div class="card-head" style="margin:0"><h2 class="h4">Status</h2>${statusBadge(c)}</div>
      ${c.status === 'indexing' ? connectorSummary(k) : ''}
      <dl class="stack-sm" style="margin:0">${[['Last successful sync', ago(c.lastSync)], ['Items indexed', (c.items || 0).toLocaleString()], ['Schedule', 'Incremental every 15 min'], ['Connected by', c.by || state.user.name]].map(([a, b]) => `<div class="row between"><dt class="body-3 text-2">${a}</dt><dd class="label-1" style="margin:0">${esc(b)}</dd></div>`).join('')}</dl></section>
    <section class="card stack-sm"><div class="card-head" style="margin:0"><h2 class="h4">Access and scope</h2>${admin ? `<button class="link-btn label-2" data-action="change-scope" data-k="${k}">Change</button>` : ''}</div>
      <div class="row-wrap">${c.scope.map(s => `<span class="tag">${esc(s)}</span>`).join('')}</div>
      <div class="eyebrow" style="margin-top:8px">Permissions granted</div><ul class="body-3 text-2" style="margin:0;padding-left:18px">${p.perms.map(x => `<li>${x}</li>`).join('')}</ul></section>
  </div>
  <section><h2 class="h4" style="margin-bottom:12px">Sync history</h2><div class="table-wrap"><table><thead><tr><th>When</th><th>Type</th><th>Result</th><th class="hide-sm">Items</th><th class="hide-sm">Duration</th></tr></thead><tbody>
    ${(c.history || []).map((h, i) => `<tr ${h.result === 'error' ? `class="clickable" data-action="sync-error" data-k="${k}" data-i="${i}" tabindex="0"` : ''}><td class="caption">${ago(h.t)}</td><td>${h.type}</td><td>${h.result === 'success' ? badge('success', 'check_circle', 'Succeeded') : h.result === 'running' ? badge('info', 'progress_activity', 'Running') : badge('error', 'error', 'Failed') + ` <span class="link-btn label-2">Details</span>`}</td><td class="hide-sm">${h.items}</td><td class="hide-sm">${h.dur}</td></tr>`).join('')}
  </tbody></table></div></section>`}`;
}

/* Connect / reconnect / scope flow */
function connectFlow(k, mode = 'connect') {
  const p = P[k], c = conn(k), prevStatus = c.status;
  const sel = new Set(c.scope?.length ? c.scope : p.options.slice(0, 3));
  const before = new Set(c.scope || []);
  const intro = () => `${mHead(`Connect ${p.name}`, p.desc, prov(k, 'lg'))}<div class="modal-body">
    <div><div class="label-1">Syncra will request:</div><ul class="body-3 text-2" style="margin:8px 0 0;padding-left:18px">${p.perms.map(x => `<li style="margin:4px 0">${x}</li>`).join('')}</ul></div>
    <details class="acc"><summary>Learn about access</summary><div class="body-3">Content is indexed with its original permissions, and every question is checked against the asker’s ${p.name} access before retrieval. Credentials are encrypted and never shown in Syncra. Disconnecting revokes access and removes indexed content per your workspace retention policy.</div></details></div>
    <div class="modal-foot"><button class="btn btn-ghost" data-action="close-overlay">Cancel</button><button class="btn btn-primary" data-action="flow-oauth">Continue to ${p.name} ${ic('open_in_new')}</button></div>`;
  const oauth = () => `${mHead('Authorize Syncra', 'Simulated provider consent screen')}<div class="modal-body"><div class="oauth"><div class="oauth-bar">${ic('lock')} ${k === 'github' ? 'github.com/login/oauth/authorize' : k === 'slack' ? 'slack.com/oauth/v2/authorize' : 'auth.atlassian.com/authorize'}?client_id=syncra…</div>
    <div class="oauth-body"><div class="row">${prov(k, 'lg')}${ic('sync_alt', 'muted')}${LOGO}</div><div class="h4">Syncra wants to access your ${p.name} account</div><p class="body-3 text-2">Signed in as ${esc(state.user.email)}</p>
    <ul class="body-3" style="margin:0;padding-left:18px">${p.perms.map(x => `<li style="margin:4px 0">${x}</li>`).join('')}</ul></div></div></div>
    <div class="modal-foot"><button class="btn btn-outline" data-action="flow-deny">Deny</button><button class="btn btn-primary" data-action="flow-allow">Authorize</button></div>`;
  const scope = (warn) => `${mHead(`Choose ${p.scopeLabel} to index`, `Only ${p.scopeLabel} your ${p.name} account can access are listed.`, prov(k))}<div class="modal-body">
    <label class="check" style="border-bottom:1px solid var(--border-subtle);padding-bottom:10px"><input type="checkbox" data-change="scope-all" ${sel.size === p.options.length ? 'checked' : ''}><span class="label-1">Select all</span></label>
    <div style="max-height:260px;overflow-y:auto">${p.options.map(o => `<label class="check"><input type="checkbox" data-change="scope-item" value="${esc(o)}" ${sel.has(o) ? 'checked' : ''}><span>${esc(o)}</span></label>`).join('')}</div>
    <p class="caption" id="scope-count" aria-live="polite">${sel.size} of ${p.options.length} ${p.scopeLabel} selected</p>
    ${warn ? `<div class="alert warning" role="alert">${ic('warning')}<div class="alert-body"><span class="alert-title">${warn.length} ${p.scopeLabel} will be removed from search:</span> ${warn.map(esc).join(', ')}. Their indexed content is deleted per your retention policy. Confirm to continue.</div></div>` : ''}</div>
    <div class="modal-foot">${mode === 'connect' ? '<button class="btn btn-ghost" data-action="flow-back">Back</button>' : '<button class="btn btn-ghost" data-action="close-overlay">Cancel</button>'}<span class="grow"></span><button class="btn btn-primary" data-action="flow-scope-save" ${sel.size ? '' : 'disabled'}>${warn ? 'Confirm and save' : mode === 'connect' ? 'Start sync' : 'Save scope'}</button></div>`;
  const loading = msg => `<div class="modal-body" style="align-items:center;text-align:center;padding:40px 20px">${ic('progress_activity', '')}<span class="label-1" role="status">${msg}</span></div>`;
  let pendingWarn = null;
  flow = {
    oauth: () => setOverlay(oauth()),
    back: () => setOverlay(oauth()),
    deny: () => { c.status = prevStatus === 'connecting' ? 'not_connected' : prevStatus; c.lastError = `Authorization was denied in ${p.name}. Nothing was connected.`; closeOverlay(); toast(`${p.name} wasn’t connected`, { type: 'error' }); rerender(); },
    allow: () => {
      setOverlay(loading('Verifying authorization…'), { dismissible: false });
      setTimeout(() => {
        if (mode === 'reconnect') { Object.assign(c, { status: 'connected', error: null, lastError: null, syncing: 3 }); audit('Reconnected source', p.name); closeOverlay(); toast(`${p.name} reconnected — syncing now`); rerender(); return; }
        c.status = 'connecting'; c.lastError = null; setOverlay(scope(), { dismissible: true });
      }, 800);
    },
    toggle: (v, on) => { on ? sel.add(v) : sel.delete(v); pendingWarn = null; setOverlay(scope()); $(`.overlay input[value="${CSS.escape(v)}"]`)?.focus(); },
    all: on => { p.options.forEach(o => on ? sel.add(o) : sel.delete(o)); pendingWarn = null; setOverlay(scope()); },
    save: () => {
      const removed = [...before].filter(x => !sel.has(x));
      if (mode === 'scope' && removed.length && !pendingWarn) { pendingWarn = removed; return setOverlay(scope(removed)); }
      c.scope = [...sel];
      if (mode === 'scope') { if ([...sel].some(x => !before.has(x))) c.syncing = 3; audit('Changed scope', `${p.name} · ${c.scope.length} ${p.scopeLabel}`); closeOverlay(); toast('Scope saved'); return rerender(); }
      Object.assign(c, { status: 'indexing', progress: 0, live: true, items: 0, by: state.user.name, lastSync: Date.now(), history: [{ t: Date.now(), type: 'Initial', result: 'running', items: '—', dur: '—' }] });
      audit('Connected source', `${p.name} · ${c.scope.join(', ')}`);
      closeOverlay(); toast(`${p.name} connected — indexing started`); rerender();
    },
  };
  openOverlay(mode === 'connect' ? intro() : mode === 'reconnect' ? oauth() : scope(), { label: `${p.name} connection` });
}
let flow = null;

/* ---------- Controlled action (Jira task) ---------- */
function actionPreview(spec, onDone) {
  const body = () => `${mHead('Review Jira task', 'Nothing is created until you approve.', `<div class="icon-tile" style="background:var(--ai-surface);color:var(--ai-icon)">${ic('add_task')}</div>`)}
    <form class="modal-body" data-form="action" novalidate id="action-form">
      <div class="alert info">${ic('info')}<div class="alert-body body-3">Drafted by Syncra from cited evidence. Edit anything before approving. The issue will be created as you in Jira.</div></div>
      <div class="grid-2"><div class="field"><label for="a-proj">Project</label><select class="select" id="a-proj" name="project">${['PAY', 'AUTH', 'OPS'].map(x => `<option ${x === spec.project ? 'selected' : ''}>${x}</option>`).join('')}</select></div>
      <div class="field"><label for="a-type">Issue type</label><select class="select" id="a-type" name="type"><option>Task</option><option>Spike</option><option>Bug</option></select></div></div>
      <div class="field"><label for="a-sum">Summary</label><input class="input" id="a-sum" name="summary" value="${esc(spec.summary)}" required aria-describedby="a-sum-err"><span class="help error" id="a-sum-err" hidden></span></div>
      <div class="field"><label for="a-desc">Description</label><textarea class="textarea" id="a-desc" name="desc" rows="7">${esc(spec.desc)}</textarea></div>
      <div class="field"><label for="a-as">Assignee</label><select class="select" id="a-as" name="assignee"><option>Unassigned</option>${Object.values(PEOPLE).map(p => `<option>${esc(p.name)}</option>`).join('')}</select></div>
    </form>
    <div class="modal-foot"><button class="btn btn-ghost" data-action="close-overlay">Cancel</button><button class="btn btn-primary" type="submit" form="action-form">${ic('check')} Approve and create</button></div>`;
  actionCb = onDone;
  openOverlay(body(), { wide: true, label: 'Review Jira task' });
}
let actionCb = null;
function runAction(fd) {
  const summary = fd.get('summary').trim(), err = $('#a-sum-err');
  if (!summary) { err.hidden = false; err.innerHTML = ic('error') + 'Add a summary.'; $('#a-sum').setAttribute('aria-invalid', 'true'); $('#a-sum').focus(); return; }
  const proj = fd.get('project');
  const steps = (i, denied) => `${mHead(denied ? 'Action blocked' : i >= 3 ? 'Jira task created' : 'Creating Jira task…')}<div class="modal-body"><ol class="thinking-steps" style="margin:0">
    ${[['Approval recorded', 'You approved this action'], ['Permission check', denied ? 'Your role can’t run external actions in this workspace' : `Allowed: create issues in ${proj}`], ['Create issue in Jira', ''], ['Write audit log entry', '']].map(([t, d], n) => {
      const st = denied ? (n === 0 ? 'done' : n === 1 ? 'fail' : n === 3 ? 'done' : 'skip') : n < i ? 'done' : n === i ? 'active' : '';
      return `<li class="${st === 'done' ? 'done' : st === 'active' ? 'active' : ''}" style="${st === 'fail' ? 'color:var(--error-t)' : ''}">${ic(st === 'done' ? 'check_circle' : st === 'active' ? 'progress_activity' : st === 'fail' ? 'cancel' : 'radio_button_unchecked')}<span><span class="label-1">${t}</span>${d ? `<br><span class="caption">${d}</span>` : ''}</span></li>`; }).join('')}</ol>
    ${denied ? `<div class="alert error">${ic('block')}<div class="alert-body">Nothing was created in Jira. The attempt was recorded in the audit log. Ask a workspace admin to run this action.</div></div>` : i >= 4 ? `<div class="alert success">${ic('check_circle')}<div class="alert-body"><span class="alert-title">${proj}-${key.split('-')[1]} created:</span> ${esc(summary)}</div></div>` : ''}</div>
    ${denied || i >= 4 ? `<div class="modal-foot">${i >= 4 ? `<a class="btn btn-outline" href="#/admin/audit" data-action="close-overlay-nav">View audit log</a>` : ''}<button class="btn btn-primary" data-action="close-overlay">Done</button></div>` : ''}`;
  const key = `${proj}-${520 + Math.floor(Math.random() * 60)}`;
  if (!isAdmin()) { audit('Create Jira issue', `${proj} · ${summary}`, 'error', 'Blocked: role lacks external-action permission'); return setOverlay(steps(2, true), { dismissible: true }); }
  let i = 1; setOverlay(steps(i), { dismissible: false });
  const t = setInterval(() => { i++; setOverlay(steps(i), { dismissible: i >= 4 }); if (i >= 4) { clearInterval(t); audit('Created Jira issue', `${key} ${summary}`, 'success', `Approved by ${state.user.name}`); actionCb?.(key); save(); } }, 700);
}

/* ---------- Admin ---------- */
function pMembers() {
  const ws = W(), admins = ws.members.filter(m => m.role === 'admin' && m.status === 'Active').length;
  return `${pageHeader('Members', `${ws.members.length} people in ${esc(ws.name)}. Everyone sees only the source content they can access.`, `<button class="btn btn-primary" data-action="invite">${ic('person_add')} Invite member</button>`, crumbs([['Admin', '/admin/members'], ['Members']]))}
  <div class="row-wrap" style="margin-bottom:16px"><div class="search-input grow" style="min-width:220px">${ic('search')}<label for="mq" class="sr-only">Search members</label><input class="input" id="mq" placeholder="Search by name or email" data-input="filter-rows" data-target="#members"></div>
    <label class="sr-only" for="mrole">Role</label><select class="select" id="mrole" style="width:auto" data-change="filter-attr" data-attr="role" data-target="#members"><option value="">All roles</option><option value="admin">Admin</option><option value="member">Member</option></select>
    <label class="sr-only" for="mstat">Status</label><select class="select" id="mstat" style="width:auto" data-change="filter-attr" data-attr="status" data-target="#members"><option value="">All statuses</option><option>Active</option><option>Invited</option></select></div>
  <div class="table-wrap"><table id="members"><thead><tr><th>Name</th><th>Role</th><th>Status</th><th class="hide-sm">Joined</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
  ${ws.members.map(m => `<tr class="clickable" data-row="${esc((m.name + ' ' + m.email).toLowerCase())}" data-role="${m.role}" data-status="${m.status}" data-action="member" data-id="${m.id}" tabindex="0">
    <td><div class="row">${avatar(m.name)}<div><div class="label-1">${esc(m.name)}${m.you ? ' <span class="caption">(you)</span>' : ''}</div><div class="caption">${esc(m.email)}</div></div></div></td>
    <td>${m.role === 'admin' ? badge('brand', 'shield_person', 'Admin') : badge('', 'person', 'Member')}</td>
    <td>${m.status === 'Active' ? badge('success', 'check_circle', 'Active') : badge('info', 'schedule', 'Invited')}</td>
    <td class="hide-sm caption">${m.status === 'Invited' ? 'Invited ' : ''}${ago(m.joined)}</td><td style="text-align:right">${ic('chevron_right', 'muted')}</td></tr>`).join('')}
  </tbody></table><p class="empty-filter body-3 text-2" style="padding:16px" hidden>No members match these filters.</p></div>
  <p class="caption" style="margin-top:12px">${admins} active admin${admins === 1 ? '' : 's'}. A workspace always needs at least one admin.</p>`;
}
function memberDrawer(id) {
  const ws = W(), m = ws.members.find(x => x.id === id);
  if (!m) return;
  openOverlay(`${dHead(esc(m.name))}<div class="drawer-body">
    <div class="row">${avatar(m.name, 'lg')}<div><div class="h4">${esc(m.name)}</div><div class="body-3 text-2">${esc(m.email)}</div><div style="margin-top:6px">${m.status === 'Active' ? badge('success', 'check_circle', 'Active') : badge('info', 'schedule', 'Invitation pending')}</div></div></div>
    <div class="field"><label for="mrole-sel">Role <span class="caption">· Applies to this workspace</span></label><select class="select" id="mrole-sel" data-change="member-role-dirty" data-orig="${m.role}"><option value="member" ${m.role === 'member' ? 'selected' : ''}>Member — ask, search, save</option><option value="admin" ${m.role === 'admin' ? 'selected' : ''}>Admin — also manage sources, members and settings</option></select></div>
    <div id="member-err"></div>
    ${m.status === 'Invited' ? `<div class="card-flat row"><span class="grow body-3">Invitation sent ${ago(m.joined).toLowerCase()} · expires in 8 days</span><button class="btn btn-outline btn-sm" data-action="resend" data-id="${m.id}">Resend</button></div>` : ''}
    <hr class="sep"><div><div class="label-1">${m.status === 'Invited' ? 'Revoke invitation' : 'Remove from workspace'}</div><p class="body-3 text-2" style="margin:4px 0 10px">${m.status === 'Invited' ? 'The invite link will stop working.' : 'They lose access to this workspace and its answers immediately. Their conversations are deleted per retention policy.'}</p>
    <button class="btn btn-danger-outline btn-sm" data-action="remove-member" data-id="${m.id}">${ic('person_remove')} ${m.status === 'Invited' ? 'Revoke invite' : 'Remove member'}</button></div></div>
    <div class="drawer-foot"><button class="btn btn-ghost" data-action="close-overlay">Cancel</button><button class="btn btn-primary" data-action="save-role" data-id="${m.id}" id="save-role" disabled>Save role</button></div>`, { drawer: true, label: 'Member details' });
}
const lastAdmin = m => m.role === 'admin' && W().members.filter(x => x.role === 'admin' && x.status === 'Active').length <= 1;
function pSyncHealth() {
  const ws = W(), ks = Object.keys(P).filter(k => !P[k].unavailable);
  const live = ks.filter(k => SEARCHABLE.includes(conn(k).status));
  const errors = ks.reduce((n, k) => n + (conn(k).history || []).filter(h => h.result === 'error' && Date.now() - h.t < 3 * DAY).length, 0);
  const partial = ks.some(k => ['indexing', 'attention'].includes(conn(k).status));
  const events = ks.flatMap(k => (conn(k).history || []).map((h, i) => ({ k, h, i }))).sort((a, b) => b.h.t - a.h.t);
  const metric = (label, value, icon, tone = '') => `<div class="card metric"><div class="row between"><span class="label-2 text-2">${label}</span><span class="icon-tile sm" ${tone ? `style="background:var(--${tone}-s);color:var(--${tone}-i)"` : ''}>${ic(icon)}</span></div><div class="value">${value}</div></div>`;
  return `${pageHeader('Sync health', 'Indexing status across every connected source in this workspace.', '', crumbs([['Admin', '/admin/members'], ['Sync health']]))}
  <div class="grid-4" style="margin-bottom:24px">${metric('Sources connected', `${live.length} / ${ks.length}`, 'hub')}${metric('Items indexed', ks.reduce((n, k) => n + (conn(k).items || 0), 0).toLocaleString(), 'database')}${metric('Errors (72 h)', errors, 'error', errors ? 'error' : '')}${metric('Coverage', partial ? 'Partial' : live.length ? 'Complete' : 'None', partial ? 'warning' : 'check_circle', partial ? 'warn' : 'success')}</div>
  <h2 class="h4" style="margin-bottom:12px">Connectors</h2>
  <div class="table-wrap" style="margin-bottom:24px"><table><thead><tr><th>Source</th><th>State</th><th>Last successful sync</th><th class="hide-sm">Current job</th><th class="hide-sm">Errors</th></tr></thead><tbody>
  ${ks.map(k => { const c = conn(k), errs = (c.history || []).filter(h => h.result === 'error').length; return `<tr class="clickable" data-action="nav" data-href="/integrations/${k}" tabindex="0"><td><div class="row">${prov(k)}<span class="label-1">${P[k].name}</span></div></td><td>${statusBadge(c)}</td><td class="caption">${c.lastSync ? ago(c.lastSync) : '—'}</td><td class="hide-sm body-3">${c.status === 'indexing' ? `Initial index · ${c.progress}%` : c.syncing ? 'Incremental sync' : '—'}</td><td class="hide-sm">${errs ? badge('error', 'error', errs) : '<span class="caption">0</span>'}</td></tr>`; }).join('')}
  </tbody></table></div>
  <h2 class="h4" style="margin-bottom:12px">Recent sync events</h2>
  <div class="table-wrap"><table><thead><tr><th>When</th><th>Source</th><th>Event</th><th>Result</th></tr></thead><tbody>
  ${events.length ? events.map(({ k, h, i }) => `<tr ${h.result === 'error' ? `class="clickable" data-action="sync-error" data-k="${k}" data-i="${i}" tabindex="0"` : ''}><td class="caption">${ago(h.t)}</td><td>${P[k].name}</td><td>${h.type} sync · ${h.items} items</td><td>${h.result === 'success' ? badge('success', 'check_circle', 'Succeeded') : h.result === 'running' ? badge('info', 'progress_activity', 'Running') : badge('error', 'error', 'Failed') + ' <span class="link-btn label-2">Details</span>'}</td></tr>`).join('') : '<tr><td colspan="4" class="body-3 text-2">No sync events yet. Connect a source to start indexing.</td></tr>'}
  </tbody></table></div>`;
}
function syncErrorModal(k, i) {
  const h = conn(k).history[i];
  openOverlay(`${mHead('Sync failed', `${P[k].name} · ${ago(h.t)}`, `<div class="icon-tile" style="background:var(--error-s);color:var(--error-i)">${ic('error')}</div>`)}<div class="modal-body">
    <dl class="stack-sm" style="margin:0">${[['Provider error', `<span class="mono">${esc(h.code)} (HTTP 401)</span>`], ['Affected', `All ${conn(k).scope.length} ${P[k].scopeLabel} in scope`], ['Timestamp', new Date(h.t).toLocaleString()], ['Existing data', 'Previously indexed items remain searchable but may be stale']].map(([a, b]) => `<div class="row between" style="align-items:flex-start;gap:16px"><dt class="body-3 text-2">${a}</dt><dd class="label-1" style="margin:0;text-align:right">${b}</dd></div>`).join('')}</dl>
    <div class="alert info">${ic('build')}<div class="alert-body"><div class="alert-title">How to fix it</div>The ${P[k].name} token was revoked or expired. Reconnect with an account that can read the selected ${P[k].scopeLabel}.</div></div>
    <p class="caption">Tokens and secrets are never shown in Syncra.</p></div>
    <div class="modal-foot"><button class="btn btn-ghost" data-action="close-overlay">Close</button>${isAdmin() && conn(k).status === 'attention' ? `<button class="btn btn-primary" data-action="reconnect-from-modal" data-k="${k}">Reconnect ${P[k].name}</button>` : ''}</div>`, { label: 'Sync error details' });
}
function pAudit() {
  const list = W().audit;
  return `${pageHeader('Audit log', 'Every external action and administrative change in this workspace.', '', crumbs([['Admin', '/admin/members'], ['Audit log']]))}
  <div class="table-wrap"><table><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Outcome</th></tr></thead><tbody>
  ${list.length ? list.map(e => `<tr><td class="caption" style="white-space:nowrap">${ago(e.t)}</td><td><div class="row">${e.actor === 'Syncra' ? `<span class="avatar sm" style="background:var(--bg-selected)">S</span>` : avatar(e.actor, 'sm')}<span class="body-3">${esc(e.actor)}</span></div></td><td class="label-1">${esc(e.action)}</td><td class="body-3">${esc(e.target)}${e.note ? `<div class="caption">${esc(e.note)}</div>` : ''}</td><td>${e.result === 'success' ? badge('success', 'check_circle', 'Success') : badge('error', 'block', e.action.startsWith('Create') ? 'Blocked' : 'Failed')}</td></tr>`).join('') : '<tr><td colspan="5" class="body-3 text-2">No activity recorded yet.</td></tr>'}
  </tbody></table></div>`;
}
function pWsSettings() {
  const ws = W();
  return `${pageHeader('Workspace settings', 'These settings apply to everyone in this workspace.', '', crumbs([['Admin', '/admin/members'], ['Workspace']]))}
  <form class="card stack" data-form="ws-settings" data-dirty style="max-width:720px" novalidate>
    <div class="field"><label for="wn">Workspace name</label><input class="input" id="wn" name="name" value="${esc(ws.name)}" maxlength="48" required aria-describedby="wn-err"><span class="help error" id="wn-err" hidden></span></div>
    <div class="field"><label for="wd">Description</label><textarea class="textarea" id="wd" name="desc" rows="2">${esc(ws.desc)}</textarea></div>
    <label class="switch label-1" style="justify-content:space-between"><span>Members can connect sources<br><span class="help">Applies to this workspace · Admins can always connect</span></span><input type="checkbox" name="policy" ${ws.policyMembersConnect ? 'checked' : ''}></label>
    <div class="field"><label for="wr">After a source is disconnected</label><select class="select" id="wr" name="retention"><option value="0" ${ws.retention === '0' ? 'selected' : ''}>Delete indexed content immediately</option><option value="7" ${ws.retention === '7' ? 'selected' : ''}>Delete after 7 days</option><option value="30" ${ws.retention === '30' ? 'selected' : ''}>Delete after 30 days</option></select><span class="help">Applies to this workspace</span></div>
    <div class="row"><span class="grow"></span><button class="btn btn-ghost" type="reset" data-action="reset-form">Cancel</button><button class="btn btn-primary" type="submit">Save changes</button></div>
  </form>
  <section class="danger-zone stack-sm" style="max-width:720px;margin-top:32px"><h2 class="h4" style="color:var(--error-t)">Danger zone</h2>
    <div class="row-wrap between"><div><div class="label-1">Transfer ownership</div><div class="body-3 text-2">Make another admin the workspace owner.</div></div><button class="btn btn-outline btn-sm" data-action="transfer">Transfer</button></div><hr class="sep">
    <div class="row-wrap between"><div><div class="label-1">Delete workspace</div><div class="body-3 text-2">Removes all members, connections, indexed content and conversations. This can’t be undone.</div></div><button class="btn btn-danger btn-sm" data-action="delete-ws">Delete workspace</button></div></section>`;
}

/* ---------- Settings ---------- */
function pSettings({ tab }) {
  const tabs = `<div class="tabs" role="tablist">${[['profile', 'Profile'], ['preferences', 'Preferences'], ['privacy', 'Privacy & data']].map(([k, l]) => `<a class="tab" role="tab" href="#/settings/${k}" aria-selected="${tab === k}">${l}</a>`).join('')}</div>`;
  const u = state.user, p = state.prefs;
  let body;
  if (tab === 'profile') body = `<form class="card stack" data-form="profile" data-dirty style="max-width:640px" novalidate>
    <div class="row">${avatar(u.name, 'lg')}<div><div class="h4">${esc(u.name)}</div><div class="caption">Applies to you in every workspace</div></div></div>
    <div class="field"><label for="pn">Display name</label><input class="input" id="pn" name="name" value="${esc(u.name)}" required aria-describedby="pn-err"><span class="help error" id="pn-err" hidden></span></div>
    <div class="field"><label for="pt">Title</label><input class="input" id="pt" name="title" value="${esc(u.title)}"></div>
    <div class="field"><label for="pe">Email</label><input class="input" id="pe" value="${esc(u.email)}" readonly aria-describedby="pe-help"><span class="help" id="pe-help">Managed by your identity provider.</span></div>
    <div class="field"><label for="pw">Default workspace</label><select class="select" id="pw" name="ws">${Object.values(state.workspaces).map(w => `<option value="${w.id}" ${w.id === state.wsId ? 'selected' : ''}>${esc(w.name)}</option>`).join('')}</select><span class="help">Switching reloads all workspace-specific pages.</span></div>
    <div class="row"><span class="grow"></span><button class="btn btn-ghost" type="reset" data-action="reset-form">Cancel</button><button class="btn btn-primary" type="submit">Save changes</button></div></form>`;
  else if (tab === 'preferences') body = `<form class="card stack" data-form="prefs" data-dirty style="max-width:640px">
    <fieldset class="stack-sm" style="border:0;padding:0;margin:0"><legend class="label-1" style="margin-bottom:8px">Answer style <span class="caption">· Applies to you · future answers only</span></legend>
    ${[['concise', 'Concise', 'Short answers, key citations only'], ['balanced', 'Balanced', 'A direct answer plus supporting context'], ['detailed', 'Detailed', 'Full reasoning, timeline and related entities']].map(([v, l, d]) => `<label class="radio-card"><input type="radio" name="style" value="${v}" ${p.style === v ? 'checked' : ''}><span><span class="label-1">${l}</span><br><span class="body-3 text-2">${d}</span></span></label>`).join('')}</fieldset>
    <fieldset style="border:0;padding:0;margin:0"><legend class="label-1" style="margin-bottom:4px">Default sources for new questions</legend>${['github', 'jira', 'slack', 'confluence'].map(k => `<label class="check"><input type="checkbox" name="sources" value="${k}" ${p.sources.includes(k) ? 'checked' : ''}>${prov(k, 'xs')}<span>${P[k].name}</span></label>`).join('')}</fieldset>
    <label class="switch label-1" style="justify-content:space-between"><span>Show confidence on answers<br><span class="help">Applies to you</span></span><input type="checkbox" name="confidence" ${p.confidence ? 'checked' : ''}></label>
    <label class="switch label-1" style="justify-content:space-between"><span>Include current page by default in the extension<br><span class="help">Off by default. When on, the page’s title, description and file names are sent with your question.</span></span><input type="checkbox" name="pageCtx" ${p.pageCtx ? 'checked' : ''}></label>
    <div class="row"><button class="btn btn-ghost" type="button" data-action="reset-prefs">Reset to defaults</button><span class="grow"></span><button class="btn btn-primary" type="submit">Save preferences</button></div></form>`;
  else body = `<div class="stack" style="max-width:720px"><section class="card stack-sm"><h2 class="h4">What Syncra stores</h2><ul class="body-2 text-2" style="margin:0;padding-left:20px">
      <li>Indexed excerpts from sources your workspace connected, each tagged with its original permissions.</li><li>Your questions, answers and saved items in this workspace — visible only to you.</li><li>Feedback you submit, linked to the answer it’s about.</li><li>Audit entries for external actions and admin changes.</li></ul>
      <p class="body-3 text-2">Syncra checks your access before retrieval. Content you can’t open in the original tool is never sent to the AI model.</p></section>
    <section class="card stack-sm"><h2 class="h4">Data controls</h2>
      ${[['download', 'Export my data', 'Get a copy of your conversations, saved items and feedback.', '<button class="btn btn-outline btn-sm" data-action="export">Request export</button>'], ['delete_sweep', 'Delete conversation history', 'Removes all your conversations in this workspace.', '<button class="btn btn-danger-outline btn-sm" data-action="clear-history">Delete history</button>'], ['hub', 'Connected sources', 'Review what this workspace indexes and who connected it.', '<a class="btn btn-outline btn-sm" href="#/integrations">Review sources</a>']].map(([i, t, d, b]) => `<div class="row-wrap" style="padding:8px 0"><div class="icon-tile sm">${ic(i)}</div><div class="grow"><div class="label-1">${t}</div><div class="body-3 text-2">${d}</div></div>${b}</div>`).join('<hr class="sep">')}</section>
    <section class="danger-zone stack-sm"><h2 class="h4" style="color:var(--error-t)">Account</h2>
      <div class="row-wrap between"><div><div class="label-1">Sign out</div><div class="body-3 text-2">Your saved data stays on the server.</div></div><button class="btn btn-outline btn-sm" data-action="sign-out">Sign out</button></div><hr class="sep">
      <div class="row-wrap between"><div><div class="label-1">Delete account</div><div class="body-3 text-2">Deletes your profile and personal data in every workspace. Workspaces themselves are not deleted.</div></div><button class="btn btn-danger btn-sm" data-action="delete-account">Delete account</button></div></section></div>`;
  return pageHeader('Settings', 'Personal settings. Workspace-wide settings live under Admin.') + tabs + body;
}

/* ---------- Help & system ---------- */
function pHelp() {
  const last = W().conversations[0];
  return `${pageHeader('Help', 'Quick guides and a way to reach the team.')}
  <div class="split"><div class="stack">
    <section><h2 class="h4" style="margin-bottom:12px">Quick guide</h2>
    ${[['Ask vs Search', 'Ask gives you an answer written from cited evidence. Search finds the original documents, tickets and threads so you can read them yourself.'], ['Reading citations and confidence', 'Numbers in an answer open the exact excerpt used. Confidence reflects how many independent sources agree and whether a decision record exists — it’s a signal, not a guarantee.'], ['Why an answer might be incomplete', 'If a source is still indexing or needs reconnecting, Syncra shows a coverage notice. It never implies it searched everything when it didn’t.'], ['Controlled actions', 'Syncra can draft a Jira task from an answer. You review and approve it first; the action is permission-checked and written to the audit log.'], ['Chrome extension', 'Open the side panel on a GitHub pull request or Jira issue and choose “Explain this” to see related decisions, tickets, people and impact.']].map(([t, d], i) => `<details class="acc" ${i === 0 ? 'open' : ''}><summary>${t}</summary><div class="body-2">${d}</div></details>`).join('')}</section>
    <section class="card"><h2 class="h4" style="margin-bottom:8px">Keyboard shortcuts</h2><table><tbody>${[['⌘ K / Ctrl K', 'Search or jump to'], ['Enter', 'Ask'], ['Shift + Enter', 'New line in a question'], ['Esc', 'Close dialogs and panels']].map(([k, d]) => `<tr><td><span class="kbd">${k}</span></td><td class="body-3">${d}</td></tr>`).join('')}</tbody></table></section></div>
  <form class="card stack" data-form="report" novalidate><h2 class="h4">Report a problem</h2>
    <div class="field"><label for="rc">Category</label><select class="select" id="rc" name="cat"><option>Wrong or missing answer</option><option>Integration or sync issue</option><option>Access or permissions</option><option>Something else</option></select></div>
    <div class="field"><label for="rd">What happened?</label><textarea class="textarea" id="rd" name="desc" rows="4" aria-describedby="rd-err"></textarea><span class="help error" id="rd-err" hidden></span></div>
    ${last ? `<label class="check"><input type="checkbox" name="inc" checked><span class="body-3">Include my last question: “${esc(last.title)}”</span></label>` : ''}
    <button class="btn btn-primary" type="submit">Send report</button></form></div>`;
}
function pNotFound(bare = false) {
  const inner = empty('explore_off', 'Page not found', 'This page doesn’t exist, or the link points to something that’s no longer available.', `<a class="btn btn-primary" href="#/">Go home</a>`);
  return bare ? `<div class="page"><h1 class="sr-only">Not found</h1>${inner}</div>` : `<h1 class="sr-only">Not found</h1>${inner}`;
}
function pDenied() {
  return `<h1 class="sr-only">Access denied</h1>${empty('lock', 'You don’t have access to this page', 'Admin pages are only available to workspace admins. Ask an admin if you need access.', '<a class="btn btn-primary" href="#/">Go home</a><a class="btn btn-outline" href="#/help">Get help</a>')}`;
}

/* ---------- Chrome extension preview ---------- */
function pExtension() {
  const e = state.ext, ctx = EXPLAIN[e.page];
  const ghPr = `<div class="gh-page"><div style="font-size:14px;color:#656d76;margin-bottom:8px">northwind / <strong>platform-infra</strong></div><h1 class="gh-title">Deploy Keycloak realm for customer SSO <span style="color:#656d76">#533</span></h1>
    <div style="margin:10px 0 16px;display:flex;gap:8px;align-items:center;font-size:14px"><span class="gh-state">${ic('merge')} Merged</span><span><strong>jonas-lee</strong> merged 4 commits into <code>main</code> from <code>feat/keycloak-realm</code></span></div>
    <div class="gh-box"><div class="gh-box-h"><strong>jonas-lee</strong> commented</div><div class="gh-box-b">Part of the AUTH-57 spike. Adds a Keycloak realm <code>northwind-customers</code> and an OIDC client for the customer web app.<br><br>Everything is behind <code>customer_sso_keycloak</code> (off by default). Employee login is unchanged.</div></div>
    <div class="gh-box"><div class="gh-box-h"><strong>marco-diaz</strong> reviewed</div><div class="gh-box-b">LGTM for infra. Before we flip the flag in prod we need a rollback plan.</div></div>
    <div class="gh-box"><div class="gh-box-h"><code>helm/keycloak/values.yaml</code></div><div class="gh-diff"><div>  realm:</div><div class="add">+   name: northwind-customers</div><div class="add">+   sslRequired: external</div><div>  clients:</div><div class="del">-   - auth0-bridge</div><div class="add">+   - customer-web (oidc)</div></div></div></div>`;
  const jira = `<div class="gh-page"><div style="font-size:13px;color:#656d76">Projects / Identity / <strong>AUTH-57</strong></div><h1 class="gh-title" style="margin-top:6px">Evaluate Keycloak as Auth0 replacement</h1>
    <div style="display:flex;gap:8px;margin:12px 0"><span class="gh-state" style="background:#0c66e4">In progress</span><span style="font-size:13px">Assignee: <strong>Aisha Khan</strong> · Priority: High</span></div>
    <div class="gh-box"><div class="gh-box-h"><strong>Description</strong></div><div class="gh-box-b">Auth0 MAU pricing increases 40% at renewal in December. Evaluate self-hosted Keycloak for employee and customer login.<br><br><strong>Acceptance criteria</strong><br>• Customer SSO works (OIDC + SAML)<br>• Employee SSO and SCIM provisioning<br>• Cost comparison for 3 years</div></div>
    <div class="gh-box"><div class="gh-box-h"><strong>Marco Diaz</strong> · 3 days ago</div><div class="gh-box-b">Can we get a cost comparison before the renewal conversation?</div></div></div>`;
  const blog = `<div class="gh-page" style="max-width:760px"><div style="font-size:13px;color:#656d76">Northwind Engineering Blog · Draft</div><h1 class="gh-title" style="margin:8px 0 16px;font-weight:700">Our 2026 platform roadmap</h1><p style="line-height:1.7">We’re consolidating on PostgreSQL and retiring two legacy stores by Q1 2027. Next, a self-service developer portal for internal APIs, and a single OpenTelemetry pipeline for logs, metrics and traces…</p><p style="line-height:1.7;color:#656d76">This roadmap is a draft and may change after quarterly planning.</p></div>`;
  return `<div class="shell" style="grid-template-columns:1fr"><header class="topbar"><a class="brand" href="#/">${LOGO}<span class="hide-sm">Syncra</span></a><span class="badge ai">${ic('extension')}Chrome extension preview</span><span class="grow"></span>
    <label class="sr-only" for="ext-page">Simulated page</label><select class="select" id="ext-page" style="width:auto;height:34px" data-change="ext-page"><option value="pr" ${e.page === 'pr' ? 'selected' : ''}>GitHub PR #533</option><option value="jira" ${e.page === 'jira' ? 'selected' : ''}>Jira AUTH-57</option><option value="blog" ${e.page === 'blog' ? 'selected' : ''}>Unsupported page (blog)</option></select>
    <a class="btn btn-outline btn-sm" href="#/">${ic('arrow_back')}<span class="hide-sm">Dashboard</span></a></header>
  <main class="main" id="main" style="overflow:hidden"><h1 class="sr-only">Chrome extension preview</h1><div class="ext-stage" style="${e.open ? '' : 'grid-template-columns:1fr'}">
    <div class="browser"><div class="browser-bar"><span class="browser-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="browser-url">${ic('lock')} ${ctx.url}</span>
      <button class="ext-icon" data-action="ext-toggle" aria-pressed="${e.open}" aria-label="${e.open ? 'Close' : 'Open'} Syncra side panel">${LOGO}</button></div>
      ${e.page === 'pr' ? ghPr : e.page === 'jira' ? jira : blog}</div>
    ${e.open ? extPanel() : ''}</div></main></div>`;
}
function extPanel() {
  const e = state.ext, ws = W();
  const tab = (k, l) => `<button class="tab" role="tab" aria-selected="${e.tab === k}" data-action="ext-tab" data-tab="${k}">${l}</button>`;
  let body = '', foot = '';
  if (e.tab === 'explain') body = extExplain();
  else if (e.tab === 'ask') {
    const c = e.conv && findConv(e.conv);
    body = c ? `<div class="row between"><span class="caption">${esc(c.title)}</span><button class="link-btn label-2" data-action="ext-new">New chat</button></div><div class="thread">${c.messages.map((m, i) => renderMsg(m, c, i === c.messages.length - 1, true)).join('')}</div><a class="btn btn-ghost btn-sm" href="#/ask/${c.id}" target="_blank" rel="noopener">${ic('open_in_new')} Open in dashboard</a>`
      : `<div class="empty" style="padding:24px 8px"><div class="ai-mark">${ic('auto_awesome')}</div><h2 class="h4">Ask about ${esc(ws.name)}</h2><p class="body-3">Answers cite the code, tickets and threads they come from. Turn on “Use this page” to include this tab.</p></div>
        <div class="stack-sm">${(EXPLAIN[e.page].unsupported ? SUGGESTED.slice(0, 2).map(s => s[1]) : ['Why are we making this change?', 'What could this affect?']).map(q => `<button class="followup" data-action="ext-ask" data-q="${esc(q)}">${ic('subdirectory_arrow_right')}<span class="body-3">${esc(q)}</span></button>`).join('')}</div>`;
    foot = `<div class="panel-foot">${composer({ id: 'ext-q', ext: true, conv: e.conv || '', placeholder: 'Ask Syncra…' })}</div>`;
  } else {
    const sv = ws.saved.slice(0, 6);
    body = sv.length ? `<div class="stack-sm">${sv.map(v => { if (v.type === 'source') { const s = S[v.src]; return `<button class="ctx-row" data-action="cite" data-src="${v.src}">${prov(s.provider, 'xs')}<span class="grow"><span class="label-1" style="display:block">${esc(s.title)}</span><span class="caption">Saved source · ${ago(v.at)}</span></span></button>`; } const c = findConv(v.conv), m = c?.messages.find(x => x.id === v.msg); return m ? `<a class="ctx-row" href="#/ask/${c.id}" target="_blank" rel="noopener">${ic('auto_awesome', 'muted')}<span class="grow"><span class="label-1" style="display:block">${esc(m.q)}</span><span class="caption">Saved answer · ${ago(v.at)}</span></span>${ic('open_in_new', 'muted')}</a>` : ''; }).join('')}</div><a class="btn btn-ghost btn-sm" href="#/saved" target="_blank" rel="noopener">${ic('open_in_new')} All saved items</a>`
      : empty('bookmark', 'Nothing saved', 'Bookmark answers or sources to find them here.');
  }
  return `<aside class="panel" aria-label="Syncra side panel"><div class="panel-head">${LOGO}<button class="btn btn-ghost btn-sm" data-action="ws-menu" aria-haspopup="menu" aria-expanded="false" style="padding:0 6px">${esc(ws.name)} ${ic('expand_more')}</button><span class="grow"></span>
      <a class="icon-btn sm" href="#/history" target="_blank" rel="noopener" aria-label="History (opens dashboard)" title="History">${ic('history')}</a>
      <a class="icon-btn sm" href="#/settings/preferences" target="_blank" rel="noopener" aria-label="Settings (opens dashboard)" title="Settings">${ic('settings')}</a>
      <a class="icon-btn sm" href="#/help" target="_blank" rel="noopener" aria-label="Help and report an issue" title="Help">${ic('help')}</a>
      <button class="icon-btn sm" data-action="ext-toggle" aria-label="Close side panel">${ic('close')}</button></div>
    <div class="panel-tabs" role="tablist">${tab('explain', 'Explain this')}${tab('ask', 'Ask')}${tab('saved', 'Saved')}</div>
    <div class="panel-body">${body}</div>${foot}</aside>`;
}
function extExplain() {
  const e = state.ext, ctx = EXPLAIN[e.page], st = e.explain[e.page], sum = e.summary[e.page];
  const head = `<div class="ctx-card"><div class="row">${e.page === 'blog' ? `<span class="icon-tile sm">${ic('public')}</span>` : prov(e.page === 'pr' ? 'github' : 'jira')}<div class="grow" style="min-width:0"><div class="caption">${ctx.kind} · detected</div><div class="label-1">${esc(ctx.title)}</div></div></div>
    ${ctx.unsupported ? `<div class="alert info" style="padding:8px 12px">${ic('info')}<div class="alert-body body-3">Explain this works on GitHub pull requests and Jira issues. You can still summarize this page or ask about your connected sources.</div></div>` : ''}
    <div class="row-wrap">${!ctx.unsupported && !st ? `<button class="btn btn-generate btn-sm" data-action="ext-explain">${ic('auto_awesome')} Explain this</button>` : ''}${!sum ? `<button class="btn btn-ai btn-sm" data-action="ext-sum-start">${ic('summarize')} Summarize this page</button>` : ''}</div></div>`;
  let sumHtml = '';
  if (sum === 'disclose') sumHtml = `<div class="ctx-card"><div class="label-1">${ic('privacy_tip')} Before summarizing</div><p class="body-3 text-2">Syncra will read this tab’s visible text (title, description and comments) and send it for summarization. It isn’t stored unless you save the summary.</p><div class="row"><span class="grow"></span><button class="btn btn-ghost btn-sm" data-action="ext-sum-cancel">Cancel</button><button class="btn btn-primary btn-sm" data-action="ext-sum-go">Summarize</button></div></div>`;
  else if (sum && sum.loading) sumHtml = `<div class="thinking" role="status"><span class="label-1" style="color:var(--ai-text)">${sum.loading}</span><div class="ai-stroke" style="margin-top:10px"></div></div>`;
  else if (sum) {
    const pts = sum.len === 'short' ? ctx.points.slice(0, 2) : sum.len === 'long' ? [...ctx.points, ...ctx.extra] : ctx.points;
    sumHtml = `<div class="ctx-card"><div class="row between"><span class="badge ai">${ic('auto_awesome')}Page summary</span><a class="caption" href="#" data-action="noop">${ic('link')} Original page</a></div>
      <ul class="body-3" style="margin:0;padding-left:18px">${pts.map(p => `<li style="margin:4px 0">${esc(p)}</li>`).join('')}</ul>
      ${sum.items ? `<div class="eyebrow" style="margin-top:6px">Possible action items <span class="badge" style="margin-left:4px">Inferred</span></div><ul class="body-3" style="margin:0;padding-left:18px">${ctx.items.map(p => `<li style="margin:4px 0">${esc(p)}</li>`).join('')}</ul><p class="caption">Extracted from the page — not assigned to anyone.</p>` : ''}
      <div class="row-wrap"><button class="btn btn-ghost btn-sm" data-action="ext-sum-len" data-len="short" ${sum.len === 'short' ? 'disabled' : ''}>Shorter</button><button class="btn btn-ghost btn-sm" data-action="ext-sum-len" data-len="long" ${sum.len === 'long' ? 'disabled' : ''}>More detail</button>${!sum.items ? `<button class="btn btn-ghost btn-sm" data-action="ext-sum-items">Extract action items</button>` : ''}
      <button class="btn btn-ghost btn-sm" data-action="ext-ask-page">${ic('chat')} Ask about this page</button><button class="icon-btn sm" data-action="ext-sum-copy" aria-label="Copy summary">${ic('content_copy')}</button></div></div>`;
  }
  let ex = '';
  if (st === 'loading') ex = `<div class="thinking" role="status"><span class="label-1" style="color:var(--ai-text)">Finding related decisions, tickets and people…</span><div class="ai-stroke" style="margin-top:10px"></div></div>`;
  else if (st === 'done') {
    const d = DECISIONS[ctx.decision];
    const cite = p => p.replace(/\{(\d+)\}/g, (_, n) => citeBtn(ctx.sources[n - 1], n));
    const sec = (title, inner) => `<div class="ctx-card"><div class="eyebrow">${title}</div>${inner}</div>`;
    const srcRow = sid => { const s = S[sid]; return `<button class="ctx-row" data-action="cite" data-src="${sid}">${prov(s.provider, 'xs')}<span class="grow"><span class="label-1" style="display:block">${esc(s.title)}</span><span class="caption">${esc(s.loc)}</span></span></button>`; };
    ex = `<div class="stack-sm"><div class="row"><span class="badge ai">${ic('auto_awesome')}AI-generated</span><span class="badge warning">${ic('warning')}Low confidence</span></div><p class="answer-text">${cite(ctx.summary)}</p></div>
      ${d.contradiction ? `<div class="alert warning">${ic('rule')}<div class="alert-body body-3"><span class="alert-title">Potential contradiction.</span> Docs say Auth0 only; this ${e.page === 'pr' ? 'PR' : 'issue'} moves toward Keycloak.</div></div>` : ''}
      ${sec('Related decision', `<a class="ctx-row" href="#/decisions/${ctx.decision}" target="_blank" rel="noopener">${ic('gavel', 'muted')}<span class="grow"><span class="label-1" style="display:block">${esc(d.title)}</span>${badge(...d.status)}</span>${ic('open_in_new', 'muted')}</a>`)}
      ${sec('Related issues and PRs', ctx.related.map(srcRow).join(''))}
      ${sec('Discussions', ctx.discussions.map(srcRow).join(''))}
      ${sec('People', `<div class="stack-sm">${ctx.people.map(p => `<div class="row">${avatar(person(p).name, 'sm')}<span class="label-1 grow">${esc(person(p).name)}</span><span class="caption">${esc(person(p).role)}</span></div>`).join('')}</div>`)}
      ${sec('Potential impact', `<ul class="body-3" style="margin:0;padding-left:18px">${ctx.impact.map(i => `<li style="margin:3px 0">${esc(i)}</li>`).join('')}</ul>`)}
      <div class="row-wrap"><button class="btn btn-outline btn-sm" data-action="ext-ask-page">${ic('chat')} Ask a follow-up</button><button class="btn btn-ai btn-sm" data-action="action-preview-decision" data-id="${ctx.decision}">${ic('add_task')} Create Jira task</button></div>`;
  }
  return head + sumHtml + ex;
}

/* ---------- Command menu ---------- */
const CMD_PAGES = [['Home', '/', 'home'], ['Ask', '/ask', 'auto_awesome'], ['Search', '/search', 'search'], ['Decisions', '/decisions', 'gavel'], ['Timeline', '/decisions?view=timeline', 'timeline'], ['History', '/history', 'history'], ['Saved', '/saved', 'bookmark'], ['Integrations', '/integrations', 'hub'], ['Members', '/admin/members', 'group', 1], ['Sync health', '/admin/sync', 'monitor_heart', 1], ['Audit log', '/admin/audit', 'receipt_long', 1], ['Workspace settings', '/admin/workspace', 'tune', 1], ['Settings', '/settings/profile', 'settings'], ['Help', '/help', 'help'], ['Chrome extension preview', '/extension', 'extension']];
function cmdList(q) {
  const pages = CMD_PAGES.filter(p => (!p[3] || isAdmin()) && p[0].toLowerCase().includes(q.toLowerCase()));
  return `${q ? `<button class="menu-item" data-action="cmd-ask" data-q="${esc(q)}">${ic('auto_awesome')}Ask “${esc(q)}”</button><button class="menu-item" data-action="cmd-go" data-href="/search?q=${encodeURIComponent(q)}">${ic('search')}Search sources for “${esc(q)}”</button><div class="menu-sep"></div>` : ''}
    <div class="menu-label eyebrow">Go to</div>${pages.map(p => `<button class="menu-item" data-action="cmd-go" data-href="${p[1]}">${ic(p[2])}${p[0]}</button>`).join('') || '<p class="body-3 text-2" style="padding:8px 10px">No pages match.</p>'}`;
}
function openCmd() {
  openOverlay(`<div style="padding:12px;border-bottom:1px solid var(--border-subtle)"><div class="search-input">${ic('search')}<label for="cmd-q" class="sr-only">Search or jump to</label><input class="input" id="cmd-q" placeholder="Ask, search, or jump to a page…" autocomplete="off" data-input="cmd" data-autofocus></div></div><div id="cmd-list" style="padding:6px;max-height:50vh;overflow-y:auto">${cmdList('')}</div>`, { label: 'Command menu' });
}

/* ---------- Actions (click) ---------- */
const A = {
  'close-overlay': () => closeOverlay(),
  'close-overlay-nav': (el) => { closeOverlay(); go(el.getAttribute('href').slice(1)); },
  'confirm-ok': () => { const cb = confirmCb; confirmCb = null; closeOverlay(); cb?.(); },
  nav: el => go(el.dataset.href),
  noop: () => {},
  'toggle-nav': () => { $('#shell').classList.toggle('nav-open'); },
  theme: () => { const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = t; try { localStorage.setItem('syncra-theme', t); } catch (e) {} rerender(); },
  reset: () => confirmDialog({ title: 'Reset prototype?', body: 'Restores all demo data and signs you out.', confirm: 'Reset', onConfirm: () => { try { localStorage.removeItem(STORE); } catch (e) {} state = defaultState(); dirty = false; go('/welcome'); } }),
  'privacy-info': () => openOverlay(`${mHead('Privacy and permissions')}<div class="modal-body body-2 text-2"><p>Syncra indexes content from tools your workspace connects. Every item keeps its original permissions.</p><p>When you ask a question, Syncra first checks what <strong>you</strong> can open in each tool, then retrieves only that content. Unauthorized content is never sent to the AI model.</p><p>Admins choose which repositories, projects and channels are indexed, and can disconnect at any time.</p></div><div class="modal-foot"><button class="btn btn-primary" data-action="close-overlay">Got it</button></div>`, { label: 'Privacy' }),
  sso: el => { el.disabled = true; el.innerHTML = `${ic('progress_activity')} Redirecting to ${esc(el.dataset.p)}…`; setTimeout(signedIn, 700); },
  'sign-out': () => { state.authed = false; state.wsId = null; dirty = false; closeOverlay(); go('/sign-in'); toast('Signed out', { type: 'info' }); },
  'pick-ws': el => { state.wsId = el.dataset.id; state.askFilters = []; state.ext.conv = null; const ret = safePath(state.returnTo); state.returnTo = null; const steps = setupSteps(); go(ret !== '/' ? ret : !steps[0][2] && !W().setupSkipped ? '/setup' : '/'); },
  'join-ws': () => openOverlay(`${mHead('Join with an invite', 'Paste the link or code from your invitation email.')}<form class="modal-body" data-form="join" novalidate><div class="field"><label for="inv">Invite link or code</label><input class="input" id="inv" name="code" aria-describedby="inv-err"><span class="help error" id="inv-err" hidden></span></div><div class="row"><span class="grow"></span><button class="btn btn-ghost" type="button" data-action="close-overlay">Cancel</button><button class="btn btn-primary" type="submit">Join workspace</button></div></form>`, { label: 'Join workspace' }),
  'skip-setup': () => { W().setupSkipped = true; go('/'); toast('Setup skipped — you can finish it from Home any time', { type: 'info' }); },
  'ws-menu': el => openPopover(el, `<div class="menu-label eyebrow">Workspaces</div>${Object.values(state.workspaces).map(w => `<button class="menu-item" role="menuitemradio" aria-checked="${w.id === state.wsId}" data-action="switch-ws" data-id="${w.id}"><span class="ws-avatar">${esc(initials(w.name))}</span><span class="grow">${esc(w.name)}<br><span class="caption">${w.role === 'admin' ? 'Admin' : 'Member'}</span></span>${w.id === state.wsId ? ic('check') : ''}</button>`).join('')}<div class="menu-sep"></div><a class="menu-item" href="#/create-workspace">${ic('add')}Create workspace</a><a class="menu-item" href="#/workspaces">${ic('apps')}All workspaces</a>`),
  'switch-ws': el => { closePopover(); if (el.dataset.id === state.wsId) return; state.wsId = el.dataset.id; state.askFilters = []; state.ext.conv = null; state.ext.explain = {}; state.ext.summary = {}; toast(`Switched to ${W().name}`, { type: 'info' }); current.path === '/extension' ? rerender() : go('/'); },
  'user-menu': el => openPopover(el, `<div class="menu-label"><div class="label-1">${esc(state.user.name)}</div><div class="caption">${esc(state.user.email)}</div></div><div class="menu-sep"></div>
    <a class="menu-item" href="#/settings/profile">${ic('person')}Profile</a><a class="menu-item" href="#/settings/preferences">${ic('tune')}Preferences</a><a class="menu-item" href="#/settings/privacy">${ic('shield')}Privacy & data</a><a class="menu-item" href="#/extension">${ic('extension')}Chrome extension</a><a class="menu-item" href="#/help">${ic('help')}Help & feedback</a><div class="menu-sep"></div><button class="menu-item" data-action="sign-out">${ic('logout')}Sign out</button>`, 'right'),
  cmd: () => openCmd(),
  'cmd-go': el => { closeOverlay(); go(el.dataset.href); },
  'cmd-ask': el => { closeOverlay(); ask(el.dataset.q); },
  'toggle-filter': el => { const k = el.dataset.p, f = state.askFilters; state.askFilters = f.includes(k) ? f.filter(x => x !== k) : [...f, k]; el.setAttribute('aria-pressed', state.askFilters.includes(k)); keepComposer(); },
  'clear-filters': () => { state.askFilters = []; keepComposer(); },
  'ask-suggested': el => ask(el.dataset.q),
  followup: el => ask(el.dataset.q, el.dataset.conv, !!el.closest('.panel')),
  stop: el => { const { c, m } = getMsg(el); m.status = 'stopped'; refreshMsg(c, m); save(); announce('Stopped'); },
  retry: el => { const { c, m } = getMsg(el); m.status = 'pending'; m.step = 0; m.q = m.q.replace(/\b(fail|timeout)\b/gi, '').trim() || m.q; refreshMsg(c, m); run(c, m); },
  'edit-q': el => { const { m } = getMsg(el); const ta = $('[data-composer]'); if (ta) { ta.value = m.q; ta.focus(); } },
  expand: el => { const { c, m } = getMsg(el); m.expanded = true; refreshMsg(c, m); save(); },
  cite: el => openSource(el.dataset.src),
  'open-original': el => { const s = S[el.dataset.src]; toast(`Opens “${s.title}” in ${P[s.provider].name} in a new tab`, { type: 'info' }); },
  'copy-answer': el => { const { m } = getMsg(el); const a = ANSWERS[m.key]; copyText(`${[...a.body, ...(a.more || [])].map(stripTags).join('\n\n')}\n\nSources:\n${a.sources.map((s, i) => `${i + 1}. ${S[s].access === 'revoked' ? '(unavailable)' : S[s].title + ' — ' + S[s].loc}`).join('\n')}`, 'Answer and source links copied'); },
  'save-answer': el => { const { c, m } = getMsg(el); const ws = W(), idx = ws.saved.findIndex(v => v.type === 'answer' && v.msg === m.id);
    if (idx >= 0) { const [v] = ws.saved.splice(idx, 1); toast('Removed from saved', { undo: () => { ws.saved.splice(idx, 0, v); rerender(); } }); }
    else { ws.saved.unshift({ id: uid('v'), type: 'answer', conv: c.id, msg: m.id, at: Date.now() }); toast('Answer saved'); }
    rerender(); },
  'save-source': el => { const ws = W(), sid = el.dataset.src, idx = ws.saved.findIndex(v => v.type === 'source' && v.src === sid);
    if (idx >= 0) { const [v] = ws.saved.splice(idx, 1); toast('Removed from saved', { undo: () => { ws.saved.splice(idx, 0, v); rerender(); } }); } else { ws.saved.unshift({ id: uid('v'), type: 'source', src: sid, at: Date.now() }); toast('Source saved'); }
    if (el.dataset.inDrawer) { closeOverlay(); openSource(sid); } else rerender(); },
  unsave: el => { const ws = W(), idx = ws.saved.findIndex(v => v.id === el.dataset.id); const [v] = ws.saved.splice(idx, 1); rerender(); toast('Removed from saved. The source itself wasn’t changed.', { undo: () => { ws.saved.splice(idx, 0, v); rerender(); } }); },
  'fb-up': el => { const { c, m } = getMsg(el); if (m.fb === 'up') { m.fb = null; } else { m.fb = 'up'; m.fbOpen = false; toast('Thanks — feedback sent'); } refreshMsg(c, m); save(); },
  'fb-down': el => { const { c, m } = getMsg(el); m.fbOpen = !m.fbOpen; refreshMsg(c, m); if (m.fbOpen) $(`[data-msg="${m.id}"] .feedback-box .chip`)?.focus(); },
  'fb-reason': el => { const { c, m } = getMsg(el); m.fbDraft = m.fbDraft || { reasons: [], text: '' }; const r = el.dataset.r, rs = m.fbDraft.reasons; m.fbDraft.reasons = rs.includes(r) ? rs.filter(x => x !== r) : [...rs, r]; el.setAttribute('aria-pressed', m.fbDraft.reasons.includes(r)); },
  'fb-cancel': el => { const { c, m } = getMsg(el); m.fbOpen = false; m.fbDraft = null; refreshMsg(c, m); },
  summarize: el => { const { c, m } = getMsg(el); m.summary = 'loading'; refreshMsg(c, m); setTimeout(() => { m.summary = true; refreshMsg(c, m); save(); announce('Source summary ready'); }, 1200); },
  'action-preview': el => { const { c, m } = getMsg(el); const a = ANSWERS[m.key]; actionPreview(a.action, key => { m.action = key; refreshMsg(c, m); }); },
  'action-preview-decision': el => { const a = Object.values(ANSWERS).find(x => x.decision === el.dataset.id && x.action) || ANSWERS.auth; actionPreview(a.action, () => {}); },
  'delete-conv': (el, e) => { e.stopPropagation(); const ws = W(), c = findConv(el.dataset.id); confirmDialog({ title: 'Delete conversation?', body: `“${esc(c.title)}” and its answers will be permanently deleted. Sources aren’t affected.`, confirm: 'Delete', danger: true, onConfirm: () => { ws.conversations = ws.conversations.filter(x => x !== c); ws.saved = ws.saved.filter(v => v.conv !== c.id); if (state.ext.conv === c.id) state.ext.conv = null; rerender(); toast('Conversation deleted'); } }); },
  connect: el => connectFlow(el.dataset.k, 'connect'),
  reconnect: el => connectFlow(el.dataset.k, 'reconnect'),
  'reconnect-from-modal': el => { closeOverlay(); connectFlow(el.dataset.k, 'reconnect'); },
  'change-scope': el => connectFlow(el.dataset.k, 'scope'),
  'flow-oauth': () => flow.oauth(), 'flow-back': () => flow.back(), 'flow-deny': () => flow.deny(), 'flow-allow': () => flow.allow(), 'flow-scope-save': () => flow.save(),
  'sync-now': el => { const c = conn(el.dataset.k); if (c.syncing) return; c.syncing = 4; rerender(); toast(`${P[el.dataset.k].name} sync started`, { type: 'info' }); },
  disconnect: el => { const k = el.dataset.k, p = P[k], ret = { 0: 'immediately', 7: 'after 7 days', 30: 'after 30 days' }[W().retention];
    confirmDialog({ title: `Disconnect ${p.name}?`, danger: true, confirm: 'Disconnect', body: `<ul style="margin:0;padding-left:18px"><li>Syncra’s access token is revoked in ${p.name}.</li><li>Indexed content from ${conn(k).scope.length} ${p.scopeLabel} is deleted ${ret} (workspace retention policy).</li><li>New answers won’t use ${p.name}. Older answers show its citations as unavailable.</li></ul>`,
      onConfirm: () => { const c = conn(k); c.status = 'disconnecting'; rerender(); toast(`Disconnecting ${p.name}…`, { type: 'info' }); setTimeout(() => { Object.assign(c, { status: 'disconnected', scope: [], items: 0, syncing: 0, live: false, error: null }); audit('Disconnected source', p.name); rerender(); toast(`${p.name} disconnected`); }, 1200); } }); },
  'sync-error': el => syncErrorModal(el.dataset.k, +el.dataset.i),
  invite: () => openOverlay(`${mHead('Invite member', 'They’ll get an email to join ' + esc(W().name) + '.')}<form class="modal-body" data-form="invite" novalidate>
    <div class="field"><label for="ie">Email</label><input class="input" id="ie" name="email" type="email" placeholder="name@company.com" data-input="invite-validate" aria-describedby="ie-err"><span class="help error" id="ie-err" hidden></span></div>
    <div class="field"><label for="ir">Role</label><select class="select" id="ir" name="role"><option value="member">Member — ask, search and save</option><option value="admin">Admin — also manage sources and members</option></select></div>
    <div class="row"><span class="grow"></span><button type="button" class="btn btn-ghost" data-action="close-overlay">Cancel</button><button class="btn btn-primary" type="submit" id="invite-btn" disabled>Send invite</button></div></form>`, { label: 'Invite member' }),
  member: el => memberDrawer(el.dataset.id),
  'save-role': el => { const ws = W(), m = ws.members.find(x => x.id === el.dataset.id), role = $('#mrole-sel').value;
    if (m.role === 'admin' && role === 'member' && lastAdmin(m)) { $('#member-err').innerHTML = `<div class="alert error">${ic('error')}<div class="alert-body">${esc(m.name)} is the only admin. Make someone else an admin first.</div></div>`; return; }
    const apply = () => { m.role = role; audit('Changed role', `${m.name} → ${role === 'admin' ? 'Admin' : 'Member'}`); if (m.you && role === 'member') ws.role = 'member'; closeOverlay(); rerender(); toast('Role updated'); };
    if (role === 'member' && m.role === 'admin') { closeOverlay(); confirmDialog({ title: 'Remove admin privileges?', body: `${esc(m.name)} will no longer be able to manage sources, members or workspace settings.${m.you ? ' <strong>This is you</strong> — you’ll lose access to Admin pages.' : ''}`, confirm: 'Change role', danger: true, onConfirm: () => { m.role = role; audit('Changed role', `${m.name} → Member`); if (m.you) ws.role = 'member'; rerender(); toast('Role updated'); } }); }
    else apply(); },
  'remove-member': el => { const ws = W(), m = ws.members.find(x => x.id === el.dataset.id);
    if (lastAdmin(m)) { $('#member-err').innerHTML = `<div class="alert error">${ic('error')}<div class="alert-body">You can’t remove the last admin. Transfer admin access to someone else first.</div></div>`; return; }
    closeOverlay();
    confirmDialog({ title: m.status === 'Invited' ? 'Revoke invitation?' : `Remove ${esc(m.name)}?`, body: m.status === 'Invited' ? `The invitation to ${esc(m.email)} will stop working.` : `${esc(m.name)} loses access to ${esc(ws.name)} immediately, including its answers and saved items.${m.you ? ' <strong>This is you.</strong>' : ''}`, confirm: m.status === 'Invited' ? 'Revoke' : 'Remove member', danger: true,
      onConfirm: () => { ws.members = ws.members.filter(x => x !== m); audit(m.status === 'Invited' ? 'Revoked invite' : 'Removed member', m.email); if (m.you) { delete state.workspaces[ws.id]; state.wsId = null; go('/workspaces'); } else rerender(); toast(m.status === 'Invited' ? 'Invitation revoked' : 'Member removed'); } }); },
  resend: () => toast('Invitation resent'),
  transfer: () => { const admins = W().members.filter(m => m.role === 'admin' && !m.you && m.status === 'Active');
    if (!admins.length) return openOverlay(`${mHead('Transfer ownership')}<div class="modal-body"><div class="alert info">${ic('info')}<div class="alert-body">There are no other admins. Make a member an admin first.</div></div></div><div class="modal-foot"><a class="btn btn-primary" href="#/admin/members" data-action="close-overlay-nav">Go to members</a></div>`);
    confirmDialog({ title: 'Transfer ownership?', body: `${esc(admins[0].name)} will become the workspace owner. You’ll remain an admin.`, confirm: 'Transfer', onConfirm: () => { audit('Transferred ownership', admins[0].name); toast(`${admins[0].name} is now the owner`); } }); },
  'delete-ws': () => { const ws = W(); confirmDialog({ title: `Delete ${esc(ws.name)}?`, danger: true, requireText: ws.name, confirm: 'Delete workspace', body: 'All members lose access. Connections are revoked and all indexed content, conversations and audit history are permanently deleted.', onConfirm: () => { delete state.workspaces[ws.id]; state.wsId = null; dirty = false; go('/workspaces'); toast('Workspace deleted'); } }); },
  'reset-form': () => { dirty = false; setTimeout(rerender); },
  'reset-prefs': () => { state.prefs = { style: 'balanced', sources: ['github', 'jira', 'slack'], confidence: true, pageCtx: false }; dirty = false; rerender(); toast('Preferences reset'); },
  export: () => toast('Export requested — we’ll email a download link to ' + state.user.email),
  'clear-history': () => confirmDialog({ title: 'Delete all conversation history?', body: `All ${W().conversations.length} conversations in ${esc(W().name)} will be permanently deleted. Saved answers are removed too.`, confirm: 'Delete history', danger: true, onConfirm: () => { const ws = W(); ws.conversations = []; ws.saved = ws.saved.filter(v => v.type !== 'answer'); state.ext.conv = null; rerender(); toast('History deleted'); } }),
  'delete-account': () => confirmDialog({ title: 'Delete your account?', danger: true, requireText: 'DELETE', confirm: 'Delete account', body: 'Your profile, conversations, saved items and feedback are deleted in every workspace. Workspaces and their sources stay for other members.', onConfirm: () => { try { localStorage.removeItem(STORE); } catch (e) {} state = defaultState(); go('/welcome'); toast('Account deleted'); } }),
  // Extension
  'ext-toggle': () => { state.ext.open = !state.ext.open; rerender(); },
  'ext-tab': el => { state.ext.tab = el.dataset.tab; rerender(); if (state.ext.tab === 'ask') { scrollPanel(); $('#ext-q')?.focus(); } },
  'ext-explain': () => { const p = state.ext.page; state.ext.explain[p] = 'loading'; rerender(); setTimeout(() => { state.ext.explain[p] = 'done'; rerender(); announce('Explanation ready'); }, 1600); },
  'ext-sum-start': () => { state.ext.summary[state.ext.page] = 'disclose'; rerender(); },
  'ext-sum-cancel': () => { delete state.ext.summary[state.ext.page]; rerender(); },
  'ext-sum-go': () => { const p = state.ext.page, s = state.ext.summary; s[p] = { loading: 'Reading page…' }; rerender(); setTimeout(() => { s[p] = { loading: 'Creating summary…' }; rerender(); }, 700); setTimeout(() => { s[p] = { len: 'normal' }; rerender(); announce('Summary ready'); }, 1500); },
  'ext-sum-len': el => { const p = state.ext.page, cur = state.ext.summary[p]; state.ext.summary[p] = { loading: el.dataset.len === 'short' ? 'Shortening…' : 'Adding detail…' }; rerender(); setTimeout(() => { state.ext.summary[p] = { ...cur, len: el.dataset.len }; rerender(); }, 900); },
  'ext-sum-items': () => { state.ext.summary[state.ext.page].items = true; rerender(); },
  'ext-sum-copy': () => { const ctx = EXPLAIN[state.ext.page]; copyText(`${ctx.points.map(p => '• ' + p).join('\n')}\n\nSource: https://${ctx.url}`, 'Summary and page link copied'); },
  'ext-ask-page': () => { state.ext.tab = 'ask'; state.ext.pageCtx = true; state.ext.conv = null; rerender(); $('#ext-q')?.focus(); },
  'ext-ask': el => { if (!EXPLAIN[state.ext.page].unsupported) state.ext.pageCtx = true; ask(el.dataset.q, null, true); },
  'ext-new': () => { state.ext.conv = null; rerender(); $('#ext-q')?.focus(); },
};
function keepComposer() { const ta = $('[data-composer]'), v = ta?.value, id = ta?.id; rerender(); const n = id && $('#' + id); if (n) { n.value = v; } }
function signedIn() { state.authed = true; const ret = safePath(state.returnTo); if (!state.wsId) return go('/workspaces'); state.returnTo = null; go(ret); }

/* ---------- Forms ---------- */
function fieldError(id, msg) { const el = $('#' + id + '-err'), input = $('#' + id); if (!el) return; el.hidden = !msg; el.innerHTML = msg ? ic('error') + esc(msg) : ''; input?.setAttribute('aria-invalid', msg ? 'true' : 'false'); if (msg) input?.focus(); }
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const F = {
  ask: (f) => { const ta = f.querySelector('textarea'), text = ta.value.trim(), hint = f.nextElementSibling;
    if (!text) { if (hint) { hint.classList.add('error'); hint.innerHTML = ic('error') + 'Type a question first.'; } ta.focus(); return; }
    ask(text, f.dataset.conv || null, !!f.dataset.ext); },
  signin: f => { const email = f.elements.email.value.trim(); if (!EMAIL.test(email)) return fieldError('email', 'Enter a valid work email, like you@company.com.');
    if (/cancel/i.test(email)) return go('/sign-in?error=1');
    const btn = f.querySelector('button[type=submit]'); btn.disabled = true; btn.textContent = 'Checking…'; setTimeout(signedIn, 700); },
  'create-ws': f => { const name = f.elements.name.value.trim(); if (name.length < 2) return fieldError('ws-name', 'Enter a name with at least 2 characters.');
    if (Object.values(state.workspaces).some(w => w.name.toLowerCase() === name.toLowerCase())) return fieldError('ws-name', 'You already have a workspace with this name.');
    const id = uid('w'); const ws = seedWorkspace(id, name, false); ws.desc = f.elements.desc.value.trim(); ws.members[0] = { ...ws.members[0], name: state.user.name, email: state.user.email };
    state.workspaces[id] = ws; state.wsId = id; ws.audit.unshift({ t: Date.now(), actor: state.user.name, action: 'Created workspace', target: name, result: 'success' }); go('/setup'); toast(`${name} created`); },
  join: f => fieldError('inv', f.elements.code.value.trim() ? 'This invitation has expired or was revoked. Ask an admin to send a new one.' : 'Paste an invite link or code.'),
  search: f => { const q = f.elements.q.value.trim(); const cur = current.query; go('/search?' + new URLSearchParams(Object.entries({ ...cur, q }).filter(([, v]) => v)).toString()); },
  feedback: f => { const { c, m } = getMsg(f); const btn = f.querySelector('[type=submit]'); btn.disabled = true; btn.textContent = 'Sending…';
    setTimeout(() => { m.fb = 'down'; m.fbOpen = false; m.fbDraft = null; refreshMsg(c, m); save(); toast('Thanks — your feedback was sent'); }, 600); },
  action: f => runAction(new FormData(f)),
  invite: f => { const ws = W(), email = f.elements.email.value.trim().toLowerCase();
    if (!EMAIL.test(email)) return fieldError('ie', 'Enter a valid email address.');
    const dup = ws.members.find(m => m.email.toLowerCase() === email);
    if (dup) return fieldError('ie', dup.status === 'Invited' ? `${email} already has a pending invitation.` : `${email} is already a member.`);
    const role = f.elements.role.value; ws.members.push({ id: uid('m'), name: email, email, role, status: 'Invited', joined: Date.now() }); audit('Invited member', `${email} (${role === 'admin' ? 'Admin' : 'Member'})`); closeOverlay(); rerender(); toast(`Invitation sent to ${email}`); },
  'ws-settings': f => { const name = f.elements.name.value.trim(); if (name.length < 2) return fieldError('wn', 'Enter a name with at least 2 characters.');
    const ws = W(); Object.assign(ws, { name, desc: f.elements.desc.value.trim(), policyMembersConnect: f.elements.policy.checked, retention: f.elements.retention.value }); audit('Updated workspace settings', name); dirty = false; rerender(); toast('Workspace settings saved'); },
  profile: f => { const name = f.elements.name.value.trim(); if (!name) return fieldError('pn', 'Enter your display name.');
    Object.assign(state.user, { name, title: f.elements.title.value.trim() }); const me = W().members.find(m => m.you); if (me) me.name = name;
    const wsChanged = f.elements.ws.value !== state.wsId; dirty = false; if (wsChanged) { state.wsId = f.elements.ws.value; toast(`Saved. Switched to ${W().name}`); return go('/'); } rerender(); toast('Profile saved'); },
  prefs: f => { state.prefs = { style: f.elements.style.value, sources: [...f.querySelectorAll('[name=sources]:checked')].map(i => i.value), confidence: f.elements.confidence.checked, pageCtx: f.elements.pageCtx.checked }; state.ext.pageCtx = state.prefs.pageCtx; dirty = false; rerender(); toast('Preferences saved — they apply to new questions'); },
  report: f => { if (!f.elements.desc.value.trim()) return fieldError('rd', 'Describe what happened so we can help.'); f.reset(); toast('Report sent. Reference SYN-' + (1000 + Math.floor(Math.random() * 9000))); },
};

/* ---------- Event wiring ---------- */
document.addEventListener('click', e => {
  if (popEl && !popEl.contains(e.target) && !popAnchor?.contains(e.target)) closePopover();
  const el = e.target.closest('[data-action]');
  if (el && A[el.dataset.action]) { e.preventDefault(); A[el.dataset.action](el, e); return; }
  const nav = e.target.closest('.sidebar a');
  if (nav) $('#shell')?.classList.remove('nav-open');
});
document.addEventListener('submit', e => { const f = e.target.closest('[data-form]'); if (f && F[f.dataset.form]) { e.preventDefault(); F[f.dataset.form](f, e); } });
document.addEventListener('input', e => {
  const t = e.target;
  if (t.closest('form[data-dirty]')) dirty = true;
  if (t.matches('[data-composer]')) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; const hint = t.closest('form').nextElementSibling; if (hint?.classList.contains('error')) { hint.classList.remove('error'); hint.textContent = 'Enter to ask · Shift + Enter for a new line'; } }
  const k = t.dataset.input;
  if (k === 'filter-rows') applyRowFilters($(t.dataset.target));
  if (k === 'cmd') $('#cmd-list').innerHTML = cmdList(t.value.trim());
  if (k === 'confirm-text') $('.overlay [data-action="confirm-ok"]').disabled = t.value !== t.dataset.expect;
  if (k === 'invite-validate') { $('#invite-btn').disabled = !EMAIL.test(t.value.trim()); if (t.getAttribute('aria-invalid') === 'true') fieldError('ie', ''); }
  if (k === 'fb-text') { const { m } = getMsg(t); m.fbDraft = m.fbDraft || { reasons: [], text: '' }; m.fbDraft.text = t.value; }
});
document.addEventListener('change', e => {
  const t = e.target, k = t.dataset.change;
  if (t.closest('form[data-dirty]')) dirty = true;
  if (k === 'proto-role') { W().role = t.value; dirty = false; rerender(); toast(`Viewing as ${t.value === 'admin' ? 'an admin' : 'a member'}`, { type: 'info' }); }
  if (k === 'search-param') { go('/search?' + new URLSearchParams(Object.entries({ ...current.query, [t.dataset.key]: t.value }).filter(([, v]) => v)).toString()); }
  if (k === 'history-sort') go('/history' + (t.value === 'oldest' ? '?sort=oldest' : ''));
  if (k === 'filter-attr') applyRowFilters($(t.dataset.target));
  if (k === 'scope-item') flow.toggle(t.value, t.checked);
  if (k === 'scope-all') flow.all(t.checked);
  if (k === 'member-role-dirty') $('#save-role').disabled = t.value === t.dataset.orig;
  if (k === 'page-ctx') { state.ext.pageCtx = t.checked; keepComposer(); }
  if (k === 'ext-page') { state.ext.page = t.value; state.ext.pageCtx = state.prefs.pageCtx; rerender(); }
});
function applyRowFilters(table) {
  if (!table) return;
  const wrap = table.closest('.table-wrap'), q = (wrap.parentElement.querySelector('[data-input="filter-rows"]')?.value || '').toLowerCase().trim();
  const attrs = $$('[data-change="filter-attr"]').filter(s => s.dataset.target === '#' + table.id);
  let shown = 0;
  $$('tbody tr', table).forEach(r => { const ok = r.dataset.row.includes(q) && attrs.every(s => !s.value || r.dataset[s.dataset.attr] === s.value); r.hidden = !ok; shown += ok; });
  const msg = wrap.querySelector('.empty-filter'); if (msg) msg.hidden = shown > 0;
}
document.addEventListener('keydown', e => {
  const t = e.target;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k' && state.authed && state.wsId) { e.preventDefault(); overlays.length ? null : openCmd(); return; }
  if (e.key === 'Escape') { if (popEl) { closePopover(); return; } if (overlays.length && overlays.at(-1).dismissible) { closeOverlay(); return; } $('#shell')?.classList.remove('nav-open'); }
  if (t.matches('[data-composer]') && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); t.form.requestSubmit(); }
  if (t.matches('#cmd-q') && e.key === 'Enter') { e.preventDefault(); $('#cmd-list .menu-item')?.click(); }
  if (e.key === 'Enter' && t.matches('tr[tabindex]')) t.click();
  if (popEl && ['ArrowDown', 'ArrowUp'].includes(e.key)) { e.preventDefault(); const items = $$('.menu-item', popEl), i = items.indexOf(document.activeElement); items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus(); }
  if (e.key === 'Tab' && overlays.length) { const f = $$(FOCUSABLE, overlays.at(-1).ov).filter(x => x.offsetParent !== null); if (!f.length) return; if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f.at(-1).focus(); } else if (!e.shiftKey && document.activeElement === f.at(-1)) { e.preventDefault(); f[0].focus(); } }
});

/* Background ticker: indexing progress and running syncs */
setInterval(() => {
  let changed = false;
  for (const ws of Object.values(state.workspaces)) for (const [k, c] of Object.entries(ws.connectors)) {
    if (c.live && c.status === 'indexing') {
      c.progress = Math.min(100, (c.progress || 0) + 12); c.items = Math.round(P[k].items * c.progress / 100); changed = true;
      if (c.progress >= 100) { Object.assign(c, { status: 'connected', live: false, lastSync: Date.now() }); c.history[0] = { t: Date.now(), type: 'Initial', result: 'success', items: P[k].items.toLocaleString(), dur: '9s' }; if (ws.id === state.wsId) toast(`${P[k].name} is ready to search`); }
    }
    if (c.syncing > 0) { c.syncing--; changed = true; if (!c.syncing) { c.lastSync = Date.now(); c.history = [{ t: Date.now(), type: 'Incremental', result: 'success', items: '+' + (5 + Math.floor(Math.random() * 40)), dur: '3s' }, ...(c.history || [])]; if (ws.id === state.wsId) toast(`${P[k].name} sync complete`); } }
  }
  if (!changed) return;
  save();
  const p = current.path, busy = overlays.length || popEl || document.activeElement?.matches('input, textarea, select');
  if (!busy && state.wsId && (p === '/' || p === '/setup' || p.startsWith('/integrations') || p === '/admin/sync')) rerender();
}, 1000);

// Resume any answer that was mid-generation when the page was reloaded
if (state.wsId && W()) W().conversations.forEach(c => c.messages.forEach(m => { if (m.status === 'pending') m.status = 'stopped'; }));
render(true);
