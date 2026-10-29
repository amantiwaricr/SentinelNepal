"""Recommendations generated from stored alerts, through the API."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion
from app.models.recommendation import Recommendation
from tests.integration.helpers import make_alert

SCAN = {
    "predicted_category": "Reconnaissance",
    "attack_score": 0.95,
    "evidence": {"default_decision": "Reconnaissance", "note": "synthetic test alert"},
}


def set_precision(db: Session, model: ModelVersion, precision: dict[str, float]) -> None:
    model.metrics = {**model.metrics, "test": {"per_class_precision": precision}}
    db.commit()


def test_alert_detail_generates_evidence_based_recommendations_once(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    set_precision(db, registered_model, {"Normal": 0.99, "Reconnaissance": 0.8})
    # Synthetic scan pattern: one source, six destination ports, in one dataset scope.
    for port in (21, 22, 25, 80, 443):
        make_alert(db, registered_model, dst_port=port, **SCAN)
    alert = make_alert(db, registered_model, dst_port=8080, **SCAN)

    body = analyst.get(f"/api/v1/alerts/{alert.id}").json()
    recs = body["recommendations"]
    assert [r["rule_id"] for r in recs] == ["recon.review_exposure", "recon.watch_source"]
    watch = recs[1]
    assert watch["evidence_present"]["many_ports_from_source"] == {
        "met": True,
        "description": "Alerts from the same source to at least 5 different destination ports",
        "observed": "6 ports",
    }
    assert watch["requires_human_approval"] is True
    assert "10.10.0.23" in watch["action"]

    # Stored once: later reads return the same rows instead of regenerating.
    again = analyst.get(f"/api/v1/recommendations?alert_id={alert.id}").json()
    assert [r["id"] for r in again] == [r["id"] for r in recs]
    count = db.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.alert_id == alert.id)
    )
    assert count == 2


def test_alerts_without_addresses_get_investigation_only(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    set_precision(db, registered_model, {"Normal": 0.99, "Exploits": 0.9})
    alert = make_alert(
        db,
        registered_model,
        src_ip=None,
        dst_ip=None,
        src_port=None,
        dst_port=None,
        service="-",
        predicted_category="Exploits",
        attack_score=0.97,
        evidence={"default_decision": "Exploits"},
    )
    recs = analyst.get(f"/api/v1/recommendations?alert_id={alert.id}").json()
    assert [r["rule_id"] for r in recs] == ["fallback.investigate"]
    assert recs[0]["evidence_present"]["source_address"]["met"] is False
    assert recs[0]["requires_human_approval"] is False


def test_unreliable_categories_never_get_containment(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    set_precision(db, registered_model, {"Normal": 0.99, "Reconnaissance": 0.1})
    for port in (21, 22, 25, 80, 443):
        make_alert(db, registered_model, dst_port=port, **SCAN)
    alert = make_alert(db, registered_model, dst_port=8080, **SCAN)
    recs = analyst.get(f"/api/v1/recommendations?alert_id={alert.id}").json()
    assert [r["rule_id"] for r in recs] == ["recon.review_exposure", "fallback.investigate"]
    assert "reliable_category" in recs[1]["reason"]


def test_recommendations_for_missing_alert(analyst: TestClient) -> None:
    response = analyst.get("/api/v1/recommendations?alert_id=999999")
    assert response.status_code == 404


def test_rule_catalogue_is_published(analyst: TestClient) -> None:
    rules = analyst.get("/api/v1/recommendations/rules").json()
    by_id = {r["rule_id"]: r for r in rules}
    assert by_id["bruteforce_like.review_auth"]["heuristic"] is True
    assert by_id["bruteforce_like.review_auth"]["categories"] == []
    assert by_id["exploit.contain"]["kind"] == "contain"
    assert {e["name"] for e in by_id["exploit.contain"]["required_evidence"]} >= {
        "source_address",
        "reliable_category",
    }
    assert by_id["unknown.investigate"]["requires_human_approval"] is False


def test_model_listing_reports_low_precision_categories(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    set_precision(db, registered_model, {"Normal": 0.99, "DoS": 0.3, "Exploits": 0.7})
    model = analyst.get("/api/v1/models").json()[0]
    assert model["low_precision_categories"] == ["DoS"]
    assert model["precision_source"] == "test"
