# Lab runbook — live monitoring with TShark (Phase 6)

This runbook starts the isolated Docker lab, captures its traffic with TShark, and shows the
flows and any model alerts on the dashboard. Commands are for **Windows PowerShell with
Docker Desktop**. They also work in a Linux shell: there, use `./` paths and `$PWD`.

## 0. Before you start: authorisation and safety

- **Only the lab is monitored.** The lab is two containers, `lab-server` and `lab-client`,
  on a Docker network marked `internal`. That network has no route to the internet, your
  PC, or the rest of the stack.
- Packet capture runs inside `lab-server`'s own network namespace. It sees only that
  container's traffic, never your Wi-Fi or Ethernet adapter.
- The traffic scripts in `lab/scripts/` are hard-wired to target `lab-server`.
- Keep the supervisor's **written authorisation** for this lab exercise with the project
  records. Do not point the collector at any other interface or capture directory.
- Model output is a **prediction, not proof**. Scores are uncalibrated. The model was
  trained on UNSW-NB15, whose flows were built by different tools (Argus/Bro), so its
  behaviour on lab flows has **not been validated**. Nothing is ever blocked automatically.

## 1. One-time setup

You need the normal stack working first (README, "Option A"). That means `.env` is filled
in, the users exist, and the `full` model is registered.

### 1.1 Train and register a live-compatible model

The `full` model cannot score live traffic: it needs `ct_state_ttl`, which TShark flows
cannot supply, and the server refuses to approve it. Train the `full_no_ttl` profile
(36 features) on the same dataset files:

```bash
cd ml
.venv\Scripts\Activate.ps1
sentinel-ml train --profile full_no_ttl
```

Note the new folder name `ml\artifacts\random_forest-full_no_ttl-<time>`. Then evaluate the
model and choose its threshold:

```bash
sentinel-ml evaluate artifacts\random_forest-full_no_ttl-<time>
```

```bash
sentinel-ml threshold artifacts\random_forest-full_no_ttl-<time> --target-fpr 0.05
```

```bash
cd ..
docker compose exec backend python -m app.cli register-model /models/random_forest-full_no_ttl-<time> --reports-dir /model-reports --activate
```

Activation applies per feature profile, so the `full` model stays active for dataset
analysis.

### 1.2 Register a collector and give it its token

```bash
docker compose exec backend python -m app.cli create-collector --name lab-sensor
```

The command prints a token **once**. The database stores only its SHA-256 hash. Open `.env`
and set:

```
COLLECTOR_TOKEN=<the printed token>
```

If the token is lost, create a new one with
`docker compose exec backend python -m app.cli rotate-collector-token <id>`.

## 2. Start the lab

```bash
docker compose --profile lab up -d --build
```

This adds four containers:

| Container | What it does |
|---|---|
| `lab-server` | nginx (port 80) and sshd (port 22); the account `labuser` has a locked password |
| `lab-client` | browses `lab-server` every few seconds (ordinary traffic) |
| `capture` | `dumpcap` writes 30-second ring-buffer files (20 files, about 10 minutes) to a Docker volume; unprivileged user, only `CAP_NET_RAW` |
| `collector` | reads each finished file with TShark, builds flows, posts them to the backend; unprivileged, read-only filesystem, no capture rights |

Open <http://localhost:5173>, sign in, and go to **Live Monitoring**. Within about a
minute, check that:

- the collector `lab-sensor` shows **Online** and **Observation mode**;
- **Recent flows** fill with `LIVE` rows, from `lab-client` to `lab-server:80`, state
  `FIN`;
- the gate says **Live scoring off** and gives the reason (the model is not approved yet).

In observation mode, flows are shown but **not scored**.

## 3. Turn on live scoring (admin)

1. **Model Evaluation** → the `full_no_ttl` model → **Approve for live use…** →
   **Approve**. The approval is recorded in the audit log.
2. **Live Monitoring** → `lab-sensor` → **Switch to inference…** → **Start scoring**.

The server refuses step 2 while the gate is closed. Withdrawing the approval, or switching
the collector back to observation, stops scoring at once.

## 4. Generate test traffic

Each script runs inside `lab-client` and only targets `lab-server`:

```bash
docker compose exec lab-client /lab/scan.sh
```

```bash
docker compose exec lab-client /lab/ssh-guess.sh
```

```bash
docker compose exec lab-client /lab/http-burst.sh
```

| Script | Traffic |
|---|---|
| `normal.sh` (always running) | a page request every 3–4 s |
| `scan.sh` | nmap TCP connect scan of ports 1–1024, at most 200 probes/s |
| `ssh-guess.sh` | 15 SSH logins with wrong passwords |
| `http-burst.sh` | 300 quick web requests, 20 at a time |

A flow reaches the dashboard after its capture file is finished (up to 30 s), plus the
time the flow takes to end. TCP flows end 2 s after FIN/RST. Other flows end after 30 s
idle, or later on a quiet network. The dashboard, Alerts list and Live Monitoring page update by themselves: the page
gets a WebSocket notification and re-reads the data. You do not need to reload.

**Write down what you actually see**: the script, the time, the alert count, the suspected
categories and the scores. Which categories the model predicts for these scripts is not
known in advance. Do not describe the result as "attack detected". You ran the script, so
you know the ground truth; the model's output is a suspicion to compare against it.

## 5. Inspect alerts

- **Alerts** → filter **Source: Live** → open an alert. It shows the suspected category,
  the uncalibrated score, the flow's addresses and ports, and the evidence. The evidence
  includes `feature_source: tshark`.
- Every flow is scored separately. A port scan therefore produces about one alert per
  probed port, not a single "scan" alert. Grouping alerts is not implemented (see the
  limitations in `PROJECT_STATUS.md`).

## 6. Collector failure and recovery

Clean stop (shows **Offline** straight away):

```bash
docker compose stop collector
```

Crash with no goodbye (shows **Offline** within 30 s of the last heartbeat):

```bash
docker compose kill collector
```

In both cases, check that:

- Live Monitoring shows the collector as **Offline**;
- **System & Settings** → Detection components shows `collectors: unavailable`.

Restart the collector:

```bash
docker compose start collector
```

It comes back **Online** within about 10 s. It then reads the capture files written while
it was down, as long as they are still in the 10-minute ring buffer. Flows it already sent
do not create duplicate alerts.

An unreadable capture file is counted under **Unreadable captures**, named in **Last
reported problem**, and skipped; the collector keeps running. The automated tests cover
this case (`collector/tests`); it was not provoked in the lab.

## 7. Replay a CSV (fallback without live capture)

Replay sends UNSW-NB15 rows through the same ingest API, tagged `REPLAY`. Replay needs only
an active `full_no_ttl` model, not the live approval. Your dataset files are in `ml\data`:

```bash
docker compose --profile lab run --rm --no-deps -v "${PWD}\ml\data:/data:ro" collector sentinel-collector replay /data/UNSW_NB15_testing-set.csv --limit 2000 --rate 200
```

The summary line shows rows read, rows rejected locally, and rows accepted by the API.
Replay alerts appear on the dashboard without a reload. Replaying the same file again
creates no duplicates, because each record is identified by file name and row number.

## 8. Stop and clean up

Stop the lab and keep the database:

```bash
docker compose --profile lab down
```

Also delete the captured packets (the `captures` volume):

```bash
docker volume rm sentinelnepal_captures
```

Never copy capture files out of the volume into the repository. `.gitignore` excludes pcaps,
but keep them out of the project folder entirely.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Collector exits with "COLLECTOR_TOKEN is not set" | Step 1.2; then `docker compose --profile lab up -d collector` |
| Collector online but **Rejected** grows | Look at the backend logs (`docker compose logs backend`); the ingest response lists up to 3 example reasons |
| No flows at all | `docker compose logs capture` — dumpcap needs `NET_RAW`; Docker Desktop provides it to Linux containers |
| "Live scoring off: … not approved" | Step 3 |
| "Live scoring off: needs ct_state_ttl" | You approved or activated a `full` model; use `full_no_ttl` (step 1.1) |
| Scripts fail with `\r` errors | The scripts were checked out with Windows line endings; `.gitattributes` prevents this, so re-clone or run `git add --renormalize .` |
