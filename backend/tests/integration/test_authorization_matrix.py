"""Every API route x {anonymous, analyst, admin}.

Adding a route without classifying it here fails the test, so new endpoints cannot ship
without an explicit decision about who may call them.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PUBLIC, ANALYST, ADMIN = "public", "analyst", "admin"

EXPECTED: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/health/live"): PUBLIC,
    ("GET", "/api/v1/health/ready"): PUBLIC,
    ("GET", "/api/v1/health/components"): ANALYST,
    ("POST", "/api/v1/auth/login"): PUBLIC,
    ("POST", "/api/v1/auth/logout"): ANALYST,
    ("GET", "/api/v1/auth/me"): ANALYST,
    ("GET", "/api/v1/users"): ADMIN,
    ("GET", "/api/v1/users/directory"): ANALYST,
    ("POST", "/api/v1/users"): ADMIN,
    ("PATCH", "/api/v1/users/{user_id}"): ADMIN,
    ("GET", "/api/v1/models"): ANALYST,
    ("GET", "/api/v1/models/active"): ANALYST,
    ("POST", "/api/v1/models/{model_id}/activate"): ADMIN,
    ("POST", "/api/v1/datasets/analyses"): ANALYST,
    ("GET", "/api/v1/datasets/analyses"): ANALYST,
    ("GET", "/api/v1/datasets/analyses/{run_id}"): ANALYST,
    ("GET", "/api/v1/alerts"): ANALYST,
    ("GET", "/api/v1/alerts/{alert_id}"): ANALYST,
    ("PATCH", "/api/v1/alerts/{alert_id}"): ANALYST,
    ("GET", "/api/v1/ips/{ip}"): ANALYST,
    ("GET", "/api/v1/subnets"): ANALYST,
    ("GET", "/api/v1/dashboard/summary"): ANALYST,
    ("GET", "/api/v1/incidents"): ANALYST,
    ("POST", "/api/v1/incidents"): ANALYST,
    ("GET", "/api/v1/incidents/{incident_id}"): ANALYST,
    ("PATCH", "/api/v1/incidents/{incident_id}"): ANALYST,
    ("POST", "/api/v1/incidents/{incident_id}/alerts"): ANALYST,
    ("GET", "/api/v1/incidents/{incident_id}/notes"): ANALYST,
    ("POST", "/api/v1/incidents/{incident_id}/notes"): ANALYST,
    ("GET", "/api/v1/incidents/{incident_id}/history"): ANALYST,
    ("GET", "/api/v1/recommendations"): ANALYST,
    ("GET", "/api/v1/firewall/requests"): ANALYST,
    ("GET", "/api/v1/firewall/requests/{request_id}"): ANALYST,
    # Creating requests needs an admin unless FIREWALL_ANALYSTS_MAY_REQUEST is set; that
    # service-level rule is tested in test_firewall.py.
    ("POST", "/api/v1/firewall/requests"): ANALYST,
    ("POST", "/api/v1/firewall/requests/{request_id}/approve"): ADMIN,
    ("POST", "/api/v1/firewall/requests/{request_id}/reject"): ADMIN,
    ("POST", "/api/v1/firewall/requests/{request_id}/revoke"): ADMIN,
    ("GET", "/api/v1/firewall/status"): ADMIN,
    ("GET", "/api/v1/audit-logs"): ADMIN,
}

PATH_VALUES = {"ip": "10.0.0.1"}


def _api_routes(app: FastAPI) -> set[tuple[str, str]]:
    # The OpenAPI schema is FastAPI's public, complete list of API routes (included routers
    # are not flattened onto app.routes).
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/")
        for method in operations
    }


def _url(path: str) -> str:
    for name in ("user_id", "model_id", "run_id", "alert_id", "incident_id", "request_id"):
        path = path.replace("{" + name + "}", "1")
    return path.replace("{ip}", PATH_VALUES["ip"])


def test_every_route_is_classified(app: FastAPI) -> None:
    assert _api_routes(app) == set(EXPECTED)


@pytest.mark.parametrize(("method", "path"), sorted(EXPECTED))
def test_role_enforcement(
    method: str, path: str, anon: TestClient, analyst: TestClient, admin: TestClient
) -> None:
    required = EXPECTED[(method, path)]
    url = _url(path)

    def status(client: TestClient) -> int:
        kwargs = {"json": {}} if method in {"POST", "PATCH"} else {}
        return client.request(method, url, **kwargs).status_code  # type: ignore[arg-type]

    anonymous = status(anon)
    if required == PUBLIC:
        assert anonymous not in (401, 403)
    else:
        assert anonymous == 401, f"{method} {path} allowed anonymous access ({anonymous})"

    as_analyst = status(analyst)
    if required == ADMIN:
        assert as_analyst == 403, f"{method} {path} allowed an analyst ({as_analyst})"
    else:
        assert as_analyst not in (401, 403), f"{method} {path} refused an analyst"

    # Logout last: it ends the admin session used for the other requests.
    if path != "/api/v1/auth/logout":
        assert status(admin) not in (401, 403), f"{method} {path} refused an admin"
