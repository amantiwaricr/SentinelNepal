from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.model_version import ModelVersion
from tests.integration.helpers import make_alert


def test_alert_listing_filters_sorting_and_pagination(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    make_alert(db, registered_model, src_ip="10.10.0.23", attack_score=0.95, severity="high")
    make_alert(db, registered_model, src_ip="10.10.0.24", predicted_category="DoS")
    make_alert(
        db,
        registered_model,
        src_ip="192.168.56.7",
        dst_ip="172.16.0.9",
        attack_score=0.5,
        status="dismissed",
    )

    def ids(query: str) -> list[int]:
        response = analyst.get(f"/api/v1/alerts{query}")
        assert response.status_code == 200, response.text
        return [a["id"] for a in response.json()["items"]]

    assert ids("") == [3, 2, 1]
    assert ids("?src_ip=10.10.0.23") == [1]
    assert ids("?cidr=10.10.0.0/24") == [2, 1]
    assert ids("?category=DoS") == [2]
    assert ids("?status=dismissed") == [3]
    assert ids("?severity=high") == [1]
    assert ids("?sort=attack_score") == [3, 2, 1]
    page = analyst.get("/api/v1/alerts?page=2&page_size=2").json()
    assert page["total"] == 3 and [a["id"] for a in page["items"]] == [1]


def test_alert_filters_reject_bad_input(analyst: TestClient) -> None:
    for query in ("?src_ip=999.1.1.1", "?cidr=10.0.0.0/8", "?category=Normal", "?sort=src_ip"):
        assert analyst.get(f"/api/v1/alerts{query}").status_code == 422, query


def test_alert_detail_and_status_change_are_audited(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    alert = make_alert(db, registered_model)
    detail = analyst.get(f"/api/v1/alerts/{alert.id}").json()
    assert detail["model"]["id"] == registered_model.id
    assert detail["evidence"]["note"] == "synthetic test alert"
    assert detail["src_ip"] == "10.10.0.23"
    response = analyst.patch(f"/api/v1/alerts/{alert.id}", json={"status": "acknowledged"})
    assert response.status_code == 200 and response.json()["status"] == "acknowledged"
    # "linked" can only be set by linking the alert to an incident.
    assert analyst.patch(f"/api/v1/alerts/{alert.id}", json={"status": "linked"}).status_code == 422
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "alert.status_changed")).one()
    assert entry.details == {"from": "new", "to": "acknowledged"}
    assert entry.actor_label == "analyst1"
    assert analyst.get("/api/v1/alerts/999").status_code == 404


def test_ip_investigation_reports_observed_data_only(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    make_alert(
        db, registered_model, src_ip="10.10.0.23", dst_port=22, predicted_category="Exploits"
    )
    make_alert(db, registered_model, src_ip="10.10.0.23", dst_port=80)
    make_alert(db, registered_model, src_ip="10.10.0.99", dst_ip="10.10.0.23")
    data = analyst.get("/api/v1/ips/10.10.0.23").json()
    assert data["alerts_total"] == 3
    assert (data["alerts_as_source"], data["alerts_as_destination"]) == (2, 1)
    assert data["by_category"] == {"Reconnaissance": 2, "Exploits": 1}
    assert data["destination_ports"] == {"22": 1, "80": 2}
    assert data["containing_subnet"] == "10.10.0.0/24"
    assert data["alerts_in_subnet"] == 3
    assert len(data["recent_alerts"]) == 3
    assert "geolocation" in data["note"]
    assert analyst.get("/api/v1/ips/not-an-ip").status_code == 422
    assert analyst.get("/api/v1/ips/2001:db8::1").json()["containing_subnet"] == "2001:db8::/64"


def test_subnet_summary(analyst: TestClient, registered_model: ModelVersion, db: Session) -> None:
    make_alert(db, registered_model, src_ip="10.10.0.23")
    make_alert(db, registered_model, src_ip="10.10.1.5", dst_ip="172.16.0.1")
    data = analyst.get("/api/v1/subnets", params={"cidr": "10.10.0.0/16"}).json()
    assert data["alerts_total"] == 2
    assert data["top_source_ips"] == {"10.10.0.23": 1, "10.10.1.5": 1}
    broad = analyst.get("/api/v1/subnets", params={"cidr": "10.0.0.0/8"})
    assert broad.status_code == 422 and broad.json()["error"]["code"] == "cidr_too_broad"


def test_dashboard_summary_counts_stored_data(
    analyst: TestClient, registered_model: ModelVersion, db: Session
) -> None:
    empty = analyst.get("/api/v1/dashboard/summary").json()
    # Regression: an unfiltered count once lacked a FROM clause and reported 1 on an empty DB.
    assert empty["alerts_total"] == 0 and empty["alerts_new"] == 0
    make_alert(db, registered_model, severity="high")
    make_alert(db, registered_model, source="live", status="acknowledged")
    data = analyst.get("/api/v1/dashboard/summary").json()
    assert data["alerts_total"] == 2 and data["alerts_new"] == 1
    assert data["alerts_by_source"] == {"dataset": 1, "live": 1}
    assert data["top_source_ips"] == {"10.10.0.23": 2}
    assert data["active_models"][0]["id"] == registered_model.id
    assert analyst.get("/api/v1/dashboard/summary?source=dataset").json()["alerts_total"] == 1
    assert analyst.get("/api/v1/dashboard/summary?source=live").json()["alerts_total"] == 1


def test_component_health(
    analyst: TestClient, registered_model: ModelVersion, anon: TestClient
) -> None:
    assert anon.get("/api/v1/health/components").status_code == 401
    components = analyst.get("/api/v1/health/components").json()["components"]
    assert components["database"]["status"] == "ok"
    assert components["dataset_model"]["status"] == "ok"
    assert components["firewall_helper"]["status"] == "not_configured"
    assert components["analysis_worker"]["status"] == "not_configured"
