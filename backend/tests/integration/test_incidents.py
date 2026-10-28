from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.incident import Incident
from app.models.model_version import ModelVersion
from app.models.user import User
from tests.integration.conftest import run_queued_analyses
from tests.integration.helpers import make_alert, synthetic_csv


def test_alert_to_incident_workflow_is_persisted_and_audited(
    analyst: TestClient,
    admin: TestClient,
    analyst_user: User,
    admin_user: User,
    registered_model: ModelVersion,
    db: Session,
) -> None:
    alert = make_alert(db, registered_model)
    created = analyst.post(
        "/api/v1/incidents",
        json={"title": "Suspected scan of web server", "alert_ids": [alert.id]},
    )
    assert created.status_code == 201
    incident = created.json()
    assert incident["status"] == "new"
    assert incident["alert_count"] == 1 and incident["alerts"][0]["id"] == alert.id
    assert set(incident["allowed_transitions"]) == {"under_investigation", "false_positive"}
    db.expire_all()
    assert db.get(Alert, alert.id).status == "linked"  # type: ignore[union-attr]

    iid = incident["id"]
    note = analyst.post(f"/api/v1/incidents/{iid}/notes", json={"body": "Port sweep from .23"})
    assert note.status_code == 201 and note.json()["author_username"] == "analyst1"
    assign = analyst.patch(f"/api/v1/incidents/{iid}", json={"assigned_to": admin_user.id})
    assert assign.json()["assigned_to"] == admin_user.id
    step = analyst.patch(f"/api/v1/incidents/{iid}", json={"status": "under_investigation"})
    assert step.status_code == 200
    done = admin.patch(f"/api/v1/incidents/{iid}", json={"status": "confirmed"})
    assert done.json()["status"] == "confirmed"
    resolved = admin.patch(f"/api/v1/incidents/{iid}", json={"status": "resolved"})
    assert resolved.json()["resolved_at"] is not None
    unassign = analyst.patch(f"/api/v1/incidents/{iid}", json={"assigned_to": None})
    assert unassign.json()["assigned_to"] is None

    history = analyst.get(f"/api/v1/incidents/{iid}/history").json()
    actions = [(h["action"], h["actor_label"]) for h in history]
    assert actions == [
        ("incident.created", "analyst1"),
        ("incident.note_added", "analyst1"),
        ("incident.assigned", "analyst1"),
        ("incident.status_changed", "analyst1"),
        ("incident.status_changed", "admin1"),
        ("incident.status_changed", "admin1"),
        ("incident.assigned", "analyst1"),
    ]
    assert history[3]["details"] == {"from": "new", "to": "under_investigation"}
    notes = analyst.get(f"/api/v1/incidents/{iid}/notes").json()
    assert [n["body"] for n in notes] == ["Port sweep from .23"]


def test_incidents_cannot_be_created_as_confirmed(analyst: TestClient) -> None:
    response = analyst.post("/api/v1/incidents", json={"title": "Sneaky", "status": "confirmed"})
    assert response.status_code == 422  # unknown field rejected; every incident starts as new


def test_invalid_status_transitions_are_refused(analyst: TestClient) -> None:
    iid = analyst.post("/api/v1/incidents", json={"title": "Check"}).json()["id"]
    response = analyst.patch(f"/api/v1/incidents/{iid}", json={"status": "confirmed"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert response.json()["error"]["details"]["allowed"] == [
        "false_positive",
        "under_investigation",
    ]


def test_dataset_analysis_never_creates_incidents(
    app: FastAPI, analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    analyst.post(
        "/api/v1/datasets/analyses", files={"file": ("f.csv", synthetic_csv(200), "text/csv")}
    )
    run_queued_analyses(app)
    assert db.scalar(select(func.count()).select_from(Alert)) > 0
    assert db.scalar(select(func.count()).select_from(Incident)) == 0


def test_linking_validation_and_alert_status_lock(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    alert = make_alert(db, registered_model)
    iid = analyst.post("/api/v1/incidents", json={"title": "Linking"}).json()["id"]
    assert (
        analyst.post(f"/api/v1/incidents/{iid}/alerts", json={"alert_ids": [999]}).status_code
        == 404
    )
    linked = analyst.post(
        f"/api/v1/incidents/{iid}/alerts", json={"alert_ids": [alert.id, alert.id]}
    )
    assert linked.json()["alert_count"] == 1
    again = analyst.post(f"/api/v1/incidents/{iid}/alerts", json={"alert_ids": [alert.id]})
    assert again.json()["alert_count"] == 1  # idempotent
    conflict = analyst.patch(f"/api/v1/alerts/{alert.id}", json={"status": "dismissed"})
    assert conflict.status_code == 409
    detail = analyst.get(f"/api/v1/alerts/{alert.id}").json()
    assert detail["incidents"] == [{"id": iid, "title": "Linking", "status": "new"}]


def test_assignee_must_be_an_active_user(
    analyst: TestClient, admin: TestClient, admin_user: User, analyst_user: User
) -> None:
    iid = analyst.post("/api/v1/incidents", json={"title": "Assign"}).json()["id"]
    assert analyst.patch(f"/api/v1/incidents/{iid}", json={"assigned_to": 999}).status_code == 422


def test_notes_are_append_only_and_audited_without_content(
    analyst: TestClient, db: Session
) -> None:
    iid = analyst.post("/api/v1/incidents", json={"title": "Notes"}).json()["id"]
    analyst.post(f"/api/v1/incidents/{iid}/notes", json={"body": "<script>alert(1)</script>"})
    # Stored and returned as plain text; the frontend renders it as text (no HTML).
    notes = analyst.get(f"/api/v1/incidents/{iid}/notes").json()
    assert notes[0]["body"] == "<script>alert(1)</script>"
    assert analyst.post(f"/api/v1/incidents/{iid}/notes", json={"body": ""}).status_code == 422
    assert (
        analyst.post(f"/api/v1/incidents/{iid}/notes", json={"body": "x" * 10_001}).status_code
        == 422
    )
    for method in ("put", "patch", "delete"):
        response = analyst.request(method.upper(), f"/api/v1/incidents/{iid}/notes")
        assert response.status_code == 405
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "incident.note_added")).one()
    assert "script" not in str(entry.details)


def test_incident_listing_filters(analyst: TestClient, admin_user: User) -> None:
    analyst.post("/api/v1/incidents", json={"title": "One", "severity": "high"})
    analyst.post("/api/v1/incidents", json={"title": "Two", "assigned_to": admin_user.id})
    assert analyst.get("/api/v1/incidents").json()["total"] == 2
    assert [i["title"] for i in analyst.get("/api/v1/incidents?severity=high").json()["items"]] == [
        "One"
    ]
    assigned = analyst.get(f"/api/v1/incidents?assigned_to={admin_user.id}").json()["items"]
    assert [i["title"] for i in assigned] == ["Two"]
    assert analyst.get("/api/v1/incidents/999").status_code == 404
