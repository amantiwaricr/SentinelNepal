# collector/ — lab traffic collector (Phase 6)

`sentinel-collector` turns lab packet captures into flow records and sends them to the
backend ingest API. It runs in the Docker lab (`docker compose --profile lab`); step-by-step
use is in [`docs/lab-runbook.md`](../docs/lab-runbook.md).

```
dumpcap (capture container) ──► /captures/lab_NNNNN_<time>.pcapng (30 s ring buffer)
                                      │ finished files only
                                      ▼
tshark -T fields (fixed argument list, no shell) ──► sentinel_ml.live: packets → flows
  → UNSW-NB15 features + 100-connection window ──► POST /api/v1/ingest/flows (bearer token)
heartbeat every 10 s ──► POST /api/v1/ingest/heartbeat (counters, last problem)
```

- **TShark does the protocol dissection**; the collector only groups its fields into
  bidirectional flows. All feature engineering lives in `ml/sentinel_ml/live/`. The
  dataset-to-TShark mapping, including the approximated features, is in
  [`docs/feature-mapping.md`](../docs/feature-mapping.md).
- **Capture files:**
  - A file is read only once dumpcap has moved on to a newer one.
  - Files are ordered by the start time in their name, because dumpcap restarts its
    sequence number when it restarts.
  - Idle flows are ended 60 s behind real time, so a flow that continues in the file being
    written is not split. TCP flows already closed by FIN/RST end without that lag.
- **Sending:**
  - Records wait in a bounded in-memory buffer (oldest dropped first, and counted) and are
    posted in batches of `BATCH_SIZE` (the API accepts up to 500).
  - The collector retries with backoff up to 60 s while the API is unreachable.
  - Records the API refuses (HTTP 4xx) are counted and dropped.
- **Mode:** the backend decides whether flows are scored (collector `observation` or
  `inference`, plus the live gate). The collector never scores anything itself.
- **Privileges:**
  - The collector runs as an unprivileged user, on a read-only root filesystem, with no
    capabilities.
  - It reads the capture volume read-only and cannot capture packets itself.

## Commands

```bash
sentinel-collector run
```

```bash
sentinel-collector replay FILE.csv --rate 50 --limit 1000
```

`replay` sends UNSW-NB15 CSV rows (tagged `replay`, `feature_source: dataset_csv`) through
the same API. Use it as a fallback when live capture is not available.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `COLLECTOR_TOKEN` | — (required) | from `python -m app.cli create-collector --name …` |
| `SENTINEL_API_URL` | `http://backend:8000/api/v1` | http(s) only |
| `CAPTURE_DIR` | `/captures` | directory of dumpcap ring-buffer files |
| `STATE_FILE` | `/tmp/sentinel-collector.state` | names of files already read |
| `BATCH_SIZE` / `BUFFER_LIMIT` | 200 / 20000 | records per POST / records kept while the API is down |
| `HEARTBEAT_SECONDS` / `POLL_SECONDS` | 10 / 2 | |
| `FLOW_IDLE_TIMEOUT` | 30 | seconds without packets before a flow ends |

## Development

```bash
cd collector
pip install -r requirements-dev.txt
pip install -e ../ml
pip install -e .
```

```bash
ruff format --check . && ruff check . && mypy && pytest
```

The tests use synthetic packets and CSV rows (RFC 5737 documentation addresses). The capture
tests need `tshark` on `PATH` and are skipped without it; CI installs it.
