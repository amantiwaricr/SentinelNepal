# collector/ — live traffic collector

**Status: Phase 6 (not started).** Reads Zeek JSON logs on the isolated lab VM, validates and
normalises records, computes connection-window counts, and sends `FlowRecord` batches to the
backend ingest API. Also provides CSV replay through the same API.

Runs natively on the lab VM (not in Docker Compose) as an unprivileged user that can only read
Zeek's log directory. Only interfaces the team is authorised to monitor may be used.
