"""Phase 6: collectors, ingest, the live compatibility gate, scoring, health, WebSocket.

Flow records are SYNTHETIC: feature values from sentinel_ml.testing, addresses from the
RFC 5737 documentation ranges.
"""

from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentinel_ml.schema import CATEGORICAL_FEATURES, PROFILES
from sentinel_ml.testing import make_partitioned_frame
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.time import utcnow
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.collector import Collector
from app.models.model_version import ModelVersion
from app.services.audit import AuditContext
from app.services.live.collectors import create_collector
from tests.integration.conftest import drain_live_queue

LIVE_FEATURES = PROFILES["full_no_ttl"].features


def records(count: int, *, source: str = "tshark", offset: int = 0) -> list[dict[str, Any]]:
    frame = make_partitioned_frame(max(count, 40), seed=21).head(count)
    out = []
    for i, row in enumerate(frame.to_dict("records")):
        features = {
            name: (str(row[name]) if name in CATEGORICAL_FEATURES else float(row[name]))
            for name in LIVE_FEATURES
        }
        out.append(
            {
                "flow_id": f"synthetic-{offset + i}",
                "feature_source": source,
                "start_time": 1_761_600_000 + i,
                "last_time": 1_761_600_001 + i,
                "src_ip": f"192.0.2.{10 + i % 5}",
                "dst_ip": "198.51.100.20",
                "src_port": 40000 + i,
                "dst_port": 80,
                "features": features,
            }
        )
    return out


@pytest.fixture
def collector(db: Session) -> tuple[Collector, str]:
    return create_collector(db, AuditContext.system("test"), "lab-sensor")


@pytest.fixture
def sensor(app: FastAPI, collector: tuple[Collector, str]) -> TestClient:
    """A client authenticated as the collector (bearer token, no cookie, no CSRF header)."""
    return TestClient(app, headers={"Authorization": f"Bearer {collector[1]}"})


def ingest(sensor: TestClient, recs: list[dict[str, Any]], source: str = "live") -> dict[str, Any]:
    response = sensor.post("/api/v1/ingest/flows", json={"source": source, "records": recs})
    assert response.status_code == 202, response.text
    body: dict[str, Any] = response.json()
    return body


def test_collector_token_is_shown_once_and_stored_hashed(
    collector: tuple[Collector, str], db: Session
) -> None:
    row, token = collector
    assert row.mode == "observation" and len(token) >= 40
    assert token not in row.token_hash
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "collector.created")).one()
    assert entry.details == {"name": "lab-sensor"}


def test_ingest_needs_a_valid_token_and_failures_are_audited(app: FastAPI, db: Session) -> None:
    anon = TestClient(app)
    assert anon.post("/api/v1/ingest/heartbeat", json={"status": "running"}).status_code == 401
    wrong = TestClient(app, headers={"Authorization": "Bearer not-a-real-token"})
    assert wrong.post("/api/v1/ingest/heartbeat", json={"status": "running"}).status_code == 401
    denied = db.scalars(
        select(AuditLog).where(AuditLog.action == "collector.auth", AuditLog.outcome == "denied")
    ).all()
    assert [e.details["reason"] for e in denied] == ["missing token", "unknown token"]
    for _ in range(25):
        last = wrong.post("/api/v1/ingest/heartbeat", json={"status": "running"})
    assert last.status_code == 429


def test_heartbeat_marks_the_collector_online(
    sensor: TestClient, analyst: TestClient, collector: tuple[Collector, str], db: Session
) -> None:
    body = sensor.post(
        "/api/v1/ingest/heartbeat",
        json={"status": "running", "stats": {"packets": 120, "malformed_lines": 0}},
    ).json()
    assert body == {"mode": "observation", "live_scoring": False}
    listed = analyst.get("/api/v1/collectors").json()[0]
    assert listed["online"] is True and listed["heartbeat_stats"]["packets"] == 120
    health = analyst.get("/api/v1/health/components").json()["components"]["collectors"]
    assert health["status"] == "ok"
    # No heartbeat for longer than the offline threshold: shown as offline.
    row = db.get(Collector, collector[0].id)
    assert row is not None
    row.last_heartbeat_at = utcnow() - timedelta(seconds=120)
    db.commit()
    assert analyst.get("/api/v1/collectors").json()[0]["online"] is False
    health = analyst.get("/api/v1/health/components").json()["components"]["collectors"]
    assert health["status"] == "unavailable" and "lab-sensor" in health["detail"]
    # A collector that shuts down cleanly says so and is shown offline straight away.
    sensor.post("/api/v1/ingest/heartbeat", json={"status": "running"})
    assert analyst.get("/api/v1/collectors").json()[0]["online"] is True
    sensor.post("/api/v1/ingest/heartbeat", json={"status": "stopping"})
    assert analyst.get("/api/v1/collectors").json()[0]["online"] is False


def test_invalid_records_are_rejected_and_counted(
    app: FastAPI, sensor: TestClient, collector: tuple[Collector, str], db: Session
) -> None:
    good = records(3)
    bad = [
        {**good[0], "flow_id": "x1", "src_ip": "999.1.1.1"},
        {**good[0], "flow_id": "x2", "features": {**good[0]["features"], "dur": "NaN-ish" * 10}},
        {**good[0], "flow_id": "x3", "features": {"made_up_feature": 1}},
        {**good[0], "flow_id": "x4", "start_time": -5},
        {"flow_id": "x5"},
    ]
    body = ingest(sensor, good + bad)
    assert (body["accepted"], body["rejected"], body["dropped"]) == (3, 5, 0)
    assert len(body["rejection_examples"]) == 3
    row = db.get(Collector, collector[0].id)
    assert row is not None
    db.refresh(row)
    assert (row.records_received, row.records_rejected) == (8, 5)


def test_batch_limits(sensor: TestClient) -> None:
    too_many = sensor.post(
        "/api/v1/ingest/flows", json={"source": "live", "records": records(1) * 501}
    )
    assert too_many.status_code == 422
    huge = b'{"source": "live", "records": [' + b'{"x": "' + b"a" * 3_000_000 + b'"}]}'
    response = sensor.post(
        "/api/v1/ingest/flows", content=huge, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_observation_mode_shows_flows_but_scores_nothing(
    app: FastAPI,
    sensor: TestClient,
    analyst: TestClient,
    live_model: ModelVersion,
    db: Session,
) -> None:
    ingest(sensor, records(10))
    (result,) = drain_live_queue(app)
    assert not result.scored  # type: ignore[attr-defined]
    assert db.scalars(select(Alert)).all() == []
    flows = analyst.get("/api/v1/live/flows").json()
    assert len(flows) == 10 and flows[0]["scored"] is False and flows[0]["src_ip"]
    status = analyst.get("/api/v1/live/status").json()
    assert status["model_ready"] is False and status["compatible"] is True
    assert "not approved" in status["reason"] and "swin" in status["approximate_features"]


def test_gate_refuses_incompatible_models_and_unapproved_inference(
    app: FastAPI,
    admin: TestClient,
    collector: tuple[Collector, str],
    registered_model: ModelVersion,
    live_model: ModelVersion,
    db: Session,
) -> None:
    # The 'full' model needs ct_state_ttl, which TShark flows cannot supply.
    refused = admin.post(
        f"/api/v1/models/{registered_model.id}/live-approval", json={"approved": True}
    )
    assert refused.status_code == 409 and "ct_state_ttl" in refused.json()["error"]["message"]
    # Inference mode is refused until the live model is approved.
    mode = admin.patch(f"/api/v1/collectors/{collector[0].id}", json={"mode": "inference"})
    assert mode.status_code == 409 and mode.json()["error"]["code"] == "live_gate_closed"
    approved = admin.post(f"/api/v1/models/{live_model.id}/live-approval", json={"approved": True})
    assert approved.status_code == 200 and approved.json()["live_inference_approved"] is True
    mode = admin.patch(f"/api/v1/collectors/{collector[0].id}", json={"mode": "inference"})
    assert mode.status_code == 200 and mode.json()["mode"] == "inference"
    actions = [
        (e.action, e.outcome)
        for e in db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        if e.action in ("model.live_approval", "collector.mode_changed")
    ]
    assert actions == [
        ("model.live_approval", "denied"),
        ("collector.mode_changed", "denied"),
        ("model.live_approval", "success"),
        ("collector.mode_changed", "success"),
    ]


def _open_gate(admin: TestClient, collector: Collector, model: ModelVersion) -> None:
    assert admin.post(
        f"/api/v1/models/{model.id}/live-approval", json={"approved": True}
    ).is_success
    assert admin.patch(f"/api/v1/collectors/{collector.id}", json={"mode": "inference"}).is_success


def test_approved_inference_creates_live_alerts_once(
    app: FastAPI,
    sensor: TestClient,
    admin: TestClient,
    collector: tuple[Collector, str],
    live_model: ModelVersion,
    db: Session,
) -> None:
    _open_gate(admin, collector[0], live_model)
    batch = records(60)
    ingest(sensor, batch)
    (result,) = drain_live_queue(app)
    assert result.scored  # type: ignore[attr-defined]
    alerts = db.scalars(select(Alert)).all()
    assert alerts, "the synthetic attack rows should raise some alerts"
    first = alerts[0]
    assert first.source == "live" and first.collector_id == collector[0].id
    assert str(first.src_ip).startswith("192.0.2.") and first.dst_port == 80
    assert first.evidence["feature_source"] == "tshark"
    assert first.observed_at is not None
    # The collector resends the same flows (e.g. after a timeout): no duplicate alerts.
    ingest(sensor, batch)
    drain_live_queue(app)
    assert len(db.scalars(select(Alert)).all()) == len(alerts)
    row = db.get(Collector, collector[0].id)
    assert row is not None
    db.refresh(row)
    assert row.alerts_created == len(alerts) and row.records_processed == 120


def test_replay_is_scored_even_in_observation_mode(
    app: FastAPI, sensor: TestClient, live_model: ModelVersion, db: Session
) -> None:
    ingest(sensor, records(60, source="dataset_csv"), source="replay")
    (result,) = drain_live_queue(app)
    assert result.scored  # type: ignore[attr-defined]
    sources = {a.source for a in db.scalars(select(Alert)).all()}
    assert sources == {"replay"}


def test_full_queue_drops_and_counts_batches(
    app: FastAPI, sensor: TestClient, collector: tuple[Collector, str], db: Session
) -> None:
    from app.services.live.ingest import IngestQueue

    app.state.ingest_queue = IngestQueue(1)
    assert ingest(sensor, records(5))["dropped"] == 0
    assert ingest(sensor, records(5, offset=5))["dropped"] == 5
    row = db.get(Collector, collector[0].id)
    assert row is not None
    db.refresh(row)
    assert row.records_dropped == 5


def test_websocket_requires_session_and_allowed_origin(app: FastAPI, analyst: TestClient) -> None:
    with TestClient(app) as client:
        # No session cookie.
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/api/v1/events", headers={"Origin": "http://localhost:5173"}
            ) as ws,
        ):
            ws.receive_json()
        # A foreign site using the analyst's cookie.
        client.cookies = analyst.cookies
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/api/v1/events", headers={"Origin": "https://evil.example"}
            ) as ws,
        ):
            ws.receive_json()
        with client.websocket_connect(
            "/api/v1/events", headers={"Origin": "http://localhost:5173"}
        ) as ws:
            assert ws.receive_json() == {"type": "hello", "role": "analyst"}
            app.state.events.publish({"type": "alert.created", "alert": {"id": 1}})
            assert ws.receive_json()["type"] == "alert.created"
