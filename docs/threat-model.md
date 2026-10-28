# SentinelNepal — Threat Model

> Status: **Phase 0 draft — awaiting approval.** Revisit in Phase 5 (security review) and
> Phase 7 (firewall). Method: asset inventory → trust boundaries → STRIDE per component →
> mitigations → residual risk.

## 1. Context and assumptions

* Deployed only in an **isolated university lab** (host-only/internal virtual network), not
  on the internet or a production network.
* Users are a small number of known accounts (students, supervisor) with `admin` or `analyst` roles.
* Monitoring happens only on systems and interfaces the team is authorised in writing to
  monitor, in line with institutional policy and applicable Nepali law (e.g. the Electronic
  Transactions Act, 2063 (2008)). No third-party traffic is captured, stored, or committed.
* The host OS of the lab VM is trusted and patched; console (hypervisor) access exists for recovery.

## 2. Assets

| Asset | Why it matters |
|---|---|
| Firewall control (ability to add nftables rules) | Misuse can cut off legitimate hosts or the lab itself |
| User credentials and sessions | Lead to all other assets |
| Audit log | Accountability; must be trustworthy for the evaluation |
| Alerts, incidents, notes | Contain IP addresses and analyst conclusions (sensitive in a real setting) |
| Model artifact (joblib/pickle) | Loading a tampered pickle executes arbitrary code |
| Uploaded datasets / traffic metadata | May contain sensitive data; can be oversized/malicious |
| Collector ingest token | Lets a party inject flow records |
| Configuration secrets (DB password, session secret, tokens) | Full compromise if leaked |

## 3. Trust boundaries

1. Browser ↔ API (untrusted user input, including authenticated users).
2. File upload ↔ dataset processor (untrusted file content).
3. Network traffic ↔ Zeek ↔ collector ↔ API (attacker-influenced data).
4. API ↔ PostgreSQL (app role with limited privileges).
5. API ↔ firewall helper (the only path to privileged operations).
6. Developer ↔ repository (secrets and data must not be committed).

## 4. STRIDE analysis and mitigations

### 4.1 Web API and authentication

| Threat | Example | Mitigation |
|---|---|---|
| Spoofing | Password guessing | Argon2id hashes; login rate limit per IP + username; temporary lockout after N failures; generic "invalid credentials" message; audit `auth.login.failed` |
| Spoofing | Session theft | Random 256-bit opaque token, only SHA-256 stored; HttpOnly, SameSite=Strict, Secure outside dev; idle + absolute expiry; logout revokes server-side |
| Tampering | CSRF on state-changing endpoints | SameSite=Strict + required custom header + strict CORS allowlist (no `*` with credentials) |
| Tampering | SQL injection | SQLAlchemy parameterised queries only; no string-built SQL; sort fields from allowlists; tests with injection payloads |
| Elevation | Analyst calls admin endpoint | Role dependency on every route; authorisation-matrix test covering every endpoint |
| Elevation | IDOR (another user's data) | All records are team-shared by design; role checks still applied; ids validated as integers |
| Info disclosure | Stack traces, SQL errors | Global exception handler returns envelope + request id only; details only in server logs |
| Info disclosure | XSS via notes/filenames/alert fields | React escaping; no `dangerouslySetInnerHTML`; CSP header from backend/static server; tests store and render payloads as text |
| DoS | Expensive queries | Pagination limit 100; CIDR prefix limits; query timeouts (`statement_timeout`) |

### 4.2 Dataset upload and processing

| Threat | Mitigation |
|---|---|
| Huge file / zip bomb | Size limit (default 200 MB, configurable); only `.csv`/`text/csv`; no archive extraction; streamed write with byte counter |
| Path traversal via filename | Store under server-generated UUID name; original filename kept only as metadata (length-limited, sanitised) |
| Malformed/hostile content | Chunked pandas read with explicit dtypes; per-row validation; row limit; reject non-numeric in numeric fields; NaN/inf handling |
| Formula (CSV) injection on export | Prefix cells beginning with `= + - @` when exporting |
| Resource exhaustion | One analysis at a time; queue length limit; timeouts |
| Poisoning the model | Uploads are **never** used for training; training uses only the official dataset with recorded hashes |

### 4.3 Machine-learning component

| Threat | Mitigation |
|---|---|
| Malicious pickle/joblib artifact | Load only from `ml/artifacts/` path configured on the server; verify SHA-256 against `model_versions` before loading; artifacts produced locally by the team; never load user-supplied models |
| Evasion (attacker shapes traffic) | Documented limitation; the model is one signal; human review required |
| Over-trust in scores | UI and API say "predicted" and "uncalibrated model score"; recommendations include limitations |
| Domain shift (lab 2015 data vs live) | Compatibility gate; observation-only mode; live results labelled separately from dataset results |
| Shortcut learning / leakage | IPs, ports, timestamps, `id` excluded; TTL ablation; validation-only selection |

### 4.4 Collector and ingest

| Threat | Mitigation |
|---|---|
| Spoofed/injected flow records | Per-collector bearer token (hashed in DB, rotatable); ingest endpoints accept only collector tokens; schema validation; size limits (≤ 500 records, ≤ 1 MB per request) |
| Spoofed source IPs in traffic → innocent IP blocked | Human approval required; evidence shown; UDP/ICMP spoofing warning in recommendation limitations; short expiry |
| Log flooding → backpressure | Bounded queues on both sides, counted drops, visible health |
| Sensitive data in logs | Collector logs counts and error codes, not payloads; Zeek logs not committed |
| Collector privilege | Runs as an unprivileged user that can only read Zeek's log directory; Zeek itself holds the capture capability |

### 4.5 Firewall helper (highest-risk component)

| Threat | Mitigation |
|---|---|
| Command injection | No shell; argument list built from `ipaddress` objects; fixed `op` enum; strict JSON schema with unknown fields rejected |
| Abuse through compromised web app | Helper re-validates independently; protected ranges configured **on the helper host** (read-only to the app); max prefix size; max active rules (e.g. 50); per-minute operation limit; deny by default |
| Locking out the lab / management | Protected: loopback, host addresses, gateway, management subnet, DNS, link-local, multicast, unspecified, broad prefixes; kernel-side timeouts; documented console recovery |
| Disturbing unrelated rules | Only `table inet sentinelnepal` is ever created/modified; never `flush ruleset`; integration test diffs the rest of the ruleset before/after |
| Unauthorised socket access | Unix socket mode `0660`, group `sentinel-fw` containing only the backend service user; peer credential check (`SO_PEERCRED`) |
| Repudiation | Every request/approval/execution/expiry/revoke in `audit_logs` with actor, target, request UUID; helper writes its own local log (journald) |
| Claiming success falsely | Status becomes `active` only after the helper returns success **and** a follow-up `list` verify shows the element |
| Permanent block after crash | Set-element timeouts enforced by the kernel; reconcile on API start-up and every 30 s |
| Approval bypass | State machine in one service function; `approve` requires `pending`, admin role, approver ≠ requester (default), and typed target confirmation; execution only from `approved` |

### 4.6 Database and audit

| Threat | Mitigation |
|---|---|
| Audit tampering via app | No update/delete endpoints; app DB role has only INSERT/SELECT on `audit_logs`; trigger raises on UPDATE/DELETE; migrations run with a separate owner role |
| Audit tampering by DB superuser | Out of scope (residual risk); stretch: hash chain to make tampering detectable |
| Credential leakage | Secrets only in environment/.env (git-ignored); `.env.example` contains placeholders; startup refuses default secrets when `ENVIRONMENT != development` |

### 4.7 Frontend and WebSocket

| Threat | Mitigation |
|---|---|
| Cross-site WebSocket hijacking | Validate `Origin` against allowlist; require session cookie; close on session expiry |
| Route guard bypass | Guards are UX only; every API call authorised server-side |
| Token storage XSS | No tokens in `localStorage`; HttpOnly cookie only |

### 4.8 Supply chain and repository

| Threat | Mitigation |
|---|---|
| Vulnerable dependencies | Pinned versions; `pip-audit` and `npm audit` in CI (report, triage) |
| Secrets/data committed | `.gitignore` for `.env`, datasets, artifacts, pcaps, Zeek logs; optional pre-commit secret scan |

## 5. Residual risks (accepted for an FYP lab)

* The model can be evaded and will produce false positives/negatives; this is inherent.
* A DB superuser or root on the lab VM can alter audit logs or firewall state.
* Single-process rate limiting resets on restart and does not scale horizontally.
* The `live_compatible` model is evaluated on Argus-derived features; live Zeek-derived
  features may behave differently even after the gate passes.
* Blocking a spoofed source address can harm the real owner of that address; mitigated only
  by human review and short expiry.

## 6. Security test checklist (to implement in Phases 3, 5, 7)

- [ ] Authorisation matrix for every endpoint and role
- [ ] Login lockout and rate limit
- [ ] Session expiry and logout revocation
- [ ] CSRF header requirement on POST/PATCH/DELETE
- [ ] CORS rejects unknown origins
- [ ] SQLi payloads in filters and search
- [ ] XSS payloads stored in notes/titles rendered inert
- [ ] Upload: wrong type, oversize, malformed rows, path-traversal filename
- [ ] Audit: update/delete blocked at DB level
- [ ] Model: hash mismatch refuses load
- [ ] Ingest: bad token, oversize batch, invalid records
- [ ] Firewall: invalid/protected targets, self-approval, unapproved execution, duplicates, timeout, revoke idempotency
- [ ] WebSocket: missing cookie, foreign Origin
