from __future__ import annotations

from fastapi.testclient import TestClient

from triage_service.app import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_triage_endpoint_uses_complaint_document() -> None:
    request = {
        "id": "CASE-1",
        "complaint_document": (
            "**Channel:** Email\n"
            "**Received:** 2026-04-18 09:12 AEST\n"
            "**Customer ID:** CUST-1\n\n"
            "```\nYou charged me twice this month. Fix it and refund me.\n```"
        ),
    }

    with TestClient(app) as client:
        response = client.post("/triage", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "CASE-1"
    assert body["triage"]["category"] == "fees_charges"
    assert body["metadata"]["version"] == "v2"
