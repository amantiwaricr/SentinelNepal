# firewall/ — restricted nftables helper

**Status: Phase 7 (not started).** A small, separately privileged service that accepts only
four operations (`block`, `unblock`, `list`, `health`) over a local Unix socket and manages
only the `inet sentinelnepal` nftables table, using kernel-enforced timeouts for expiry.

Safety rules (enforced from the first line of code):

- Runs only on an isolated, disposable Ubuntu lab VM — never on a developer's primary machine.
- Never flushes or replaces the host ruleset; never executes user-supplied commands.
- Every block requires an administrator-approved request recorded by the backend.

The emergency recovery procedure will be documented here in Phase 7.
