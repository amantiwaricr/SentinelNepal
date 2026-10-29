# SentinelNepal — Security Review (Phase 5)

_Reviewed 2026-10-29 against commit `a0fb731` plus the Phase 5 hardening changes. Scope: the
backend API, the frontend, dataset processing, and dependencies. The collector (Phase 6) and
the firewall helper (Phase 7) do not exist yet and are reviewed in their phases._

This review is a checklist walk-through by the development team, backed by automated tests.
It is not a penetration test. "Test" entries name the test that checks the behaviour; all of
them pass in CI.

## Summary

| Area | Result | Changed in Phase 5 |
|---|---|---|
| Authentication and sessions | No issue found | — |
| Authorisation | No issue found | Matrix extended to new endpoints |
| Password storage | No issue found | — |
| Input validation | Gap fixed: request body size was unbounded | Body size limit middleware |
| SQL injection | No issue found | Injection-string tests added |
| Cross-site scripting | No issue found | Stored-payload tests added; API CSP |
| CSRF and CORS | No issue found | — |
| Secret management | No issue found | Repository scan done |
| Error messages | No issue found | — |
| Audit integrity | Residual risk (documented) | — |
| File upload | Gap fixed: oversized uploads could be spooled to disk | Streamed limit |
| Dataset processing | Gap fixed: unknown columns were parsed | Known columns only |
| Dependencies | No known vulnerabilities (2026-10-29) | CI audit job |
| Recommendations | Designed to never overclaim | Rule tests |

## Findings by area

### Authentication and sessions
- Opaque 256-bit session tokens (`secrets.token_urlsafe(32)`), stored only as SHA-256; cookie
  `HttpOnly`, `SameSite=Strict`, path `/api`, `Secure` in production. Idle 30 min, absolute
  12 h. Logout and password reset revoke sessions.
  Tests: `test_login_sets_hardened_cookie_and_me_works`, `test_session_token_is_stored_only_as_a_hash`,
  `test_idle_and_absolute_expiry`, `test_logout_revokes_the_session`.
- One generic login error for every failure; the real reason goes to the audit log; a dummy
  hash is verified for unknown users so response time does not reveal valid usernames.
  Account lockout after 5 failures (15 min) and a per-IP rate limit.
  Tests: `test_failed_logins_share_one_generic_error`, `test_account_locks_after_repeated_failures`,
  `test_login_rate_limit_per_ip`, `test_injection_strings_at_login_get_the_generic_error`.
- The frontend never sees the token; nothing is kept in web storage (ESLint rule; the
  Phase 4 browser walkthrough found `localStorage`, `sessionStorage` and `document.cookie`
  empty after sign-in).

### Authorisation
- Every endpoint declares its role; `test_authorization_matrix.py` lists every route from the
  OpenAPI schema and fails if a new route is not classified. Phase 5 added
  `GET /recommendations/rules` (analyst).
- Sensitive actions are admin-only: user management, model activation, audit log, firewall
  approve/reject/revoke and status. Firewall requests are admin-only unless
  `FIREWALL_ANALYSTS_MAY_REQUEST` is set; approval needs a different admin unless
  `FIREWALL_ALLOW_SELF_APPROVAL` is set (solo demos).
- Recommendations never trigger actions. Containment suggestions say "consider requesting a
  temporary block", which still needs an admin-approved firewall request.

### Password storage
- Argon2id via `argon2-cffi` defaults: memory 64 MiB, 3 passes, parallelism 4 (an RFC 9106
  recommended setting), with rehash on login when parameters change. Minimum 12 characters,
  maximum 128, must not contain the username, at least 4 distinct characters.
- Passwords are never logged or audited (`test_password_reset_revokes_sessions_and_is_audited_without_the_password`);
  validation errors list fields without echoing input
  (`test_validation_error_lists_fields_without_echoing_input`).

### Input validation
- Request bodies are Pydantic models with `extra="forbid"` and length limits; query
  parameters are typed (IP, CIDR, enums, integers).
- **Fixed:** FastAPI read JSON bodies of any size into memory, including on the public login
  endpoint. `BodySizeLimitMiddleware` now refuses bodies over 64 KiB (the largest legitimate
  body is a 10,000-character note) with 413, checking `Content-Length` up front and counting
  streamed (chunked) bodies as they arrive.
  Tests: `test_oversized_json_body_is_refused_before_parsing`,
  `test_oversized_body_without_content_length_is_cut_off`, `test_oversized_fields_are_refused`.

### SQL injection
- All queries use SQLAlchemy expressions with bound parameters; there are no raw SQL strings
  outside reviewed migrations. IP filters are parsed with `ipaddress` before use.
- Tests: `test_injection_strings_in_filters_are_rejected_or_inert` sends five classic payloads
  to every alert, subnet, incident and audit filter: typed filters answer 422, free-text
  filters return no rows, and the data and tables are unchanged.

### Cross-site scripting
- React escapes all text; `dangerouslySetInnerHTML` is banned by ESLint; user text is shown
  in text nodes (notes keep line breaks with CSS, not HTML).
- Tests: `test_script_payloads_are_stored_and_returned_as_plain_data` (API stores and returns
  payloads verbatim as JSON), frontend tests render `<b>` in a note and `<script>` in audit
  details as literal text.
- **Added:** API responses carry `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
  `Cache-Control: no-store` and `Cross-Origin-Resource-Policy: same-origin`
  (`test_security_headers_present`). The interactive API docs (development only) are exempt
  so Swagger UI can load.
- **Open:** the frontend is served by the Vite dev server, which needs inline scripts for hot
  reload, so the page itself has no CSP yet. The production static build (Phase 8) must be
  served with `default-src 'self'; frame-ancestors 'none'; object-src 'none'`.

### CSRF and CORS
- State-changing API requests need `X-Requested-With: SentinelNepal`; cookies are
  `SameSite=Strict`; CORS is an explicit allowlist and `*` is refused at start-up.
  Tests: `test_state_changing_api_requests_need_the_csrf_header`, `test_cors_ignores_unknown_origin`,
  `test_cors_wildcard_rejected`.

### Secret management
- Secrets come from environment variables; the app refuses placeholder database passwords
  outside development (`test_placeholder_database_password_refused_in_production`); settings
  never print secrets (`test_secret_not_shown_in_repr`).
- Repository scan (2026-10-29): no `.env`, key or certificate files are tracked, and no
  password, token or key values are assigned in tracked source. The only credentials in the
  repository are the throwaway PostgreSQL password of the CI service container and
  `.env.example` placeholders.

### Error messages
- All errors use one envelope (`code`, `message`, `details`, `request_id`); unhandled errors
  return a generic 500 with a request ID and the detail only in the server log
  (`test_unhandled_exception_returns_generic_500_with_request_id`). The readiness check does
  not leak connection details (`test_ready_reports_unreachable_database_without_leaking_details`).

### Audit integrity
- Append-only: no update or delete endpoints, and a database trigger rejects `UPDATE`,
  `DELETE` and `TRUNCATE` on `audit_logs` (`test_database_rejects_audit_tampering`).
  Free text (notes, descriptions) is not copied into audit details
  (`test_free_text_is_not_copied_into_the_audit_log`).
- **Residual:** the application's database user owns the tables, so someone with its
  credentials could drop the trigger. A separate non-owner role for the app is planned for
  Phase 8.

### File upload
- `.csv` only, CSV sniffing of the first bytes, server-generated stored names, the original
  name kept as sanitised metadata, files never used for training, rejected files deleted.
  Tests: `test_upload_validation`, `test_uploaded_filename_is_metadata_only` (path traversal
  and markup in the name).
- **Fixed:** an upload without `Content-Length` could be written to a temporary file in full
  before the endpoint's size check. The body size limit now cuts the stream at the upload
  limit (`test_upload_over_the_limit_is_cut_off_while_streaming`).

### Dataset processing
- Files are read in chunks as strings and every value goes through the same validation;
  invalid rows are counted and rejected, never guessed. Model artifacts load only when their
  SHA-256 matches the database record (`test_modified_model_file_is_never_used`), and only
  from the configured artifacts directory.
- **Fixed:** columns not in the UNSW-NB15 schema were parsed and then ignored; a crafted file
  with thousands of columns would use far more memory. Only known columns are parsed now
  (`test_unknown_columns_in_uploaded_files_are_never_loaded`).
- **Residual:** a file within the size limit that consists of a single very long line is
  still read into memory in one piece (bounded by the upload limit).

### Dependencies
- `pip-audit 2.10.1` on `backend/requirements*.txt` and `ml/requirements*.txt`: no known
  vulnerabilities. `npm audit` on `frontend/package-lock.json`: 0 vulnerabilities. Both run
  2026-10-29. A CI job (`audit`) repeats them on every push.

### Recommendations
- Rules are transparent, versioned code; containment needs strong evidence (recorded source,
  strong score, model agreement, reliable category); otherwise only investigation is
  suggested and the missing evidence is named. No rule text claims an attack occurred
  (`test_no_rule_presents_an_alert_as_proof`). See `docs/recommendations.md`.

## How to repeat this review

```bash
cd backend && TEST_DATABASE_URL=… pytest tests/integration/test_security.py tests/integration/test_authorization_matrix.py tests/unit
pip install pip-audit && (cd backend && pip-audit -r requirements.txt -r requirements-dev.txt) && (cd ml && pip-audit -r requirements.txt -r requirements-dev.txt)
cd frontend && npm audit --audit-level=high
```
