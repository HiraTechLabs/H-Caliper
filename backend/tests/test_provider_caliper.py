from __future__ import annotations

from httpx import AsyncClient
import pytest

pytestmark = pytest.mark.asyncio


async def test_provider_secret_not_returned_and_mock_health(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/v1/providers",
        json={"name": "Testing Mock", "type": "mock", "api_key": "a-never-return-this-secret", "enabled": True},
    )
    assert response.status_code == 201, response.text
    provider = response.json()
    serialized = str(provider)
    assert provider["has_api_key"] is True
    assert "api_key" not in provider
    assert "a-never-return-this-secret" not in serialized

    health = await admin_client.post(f"/api/v1/providers/{provider['id']}/test")
    assert health.status_code == 200, health.text
    assert health.json()["connected"] is True


async def test_unknown_provider_rejected_and_types_expose_capabilities(admin_client: AsyncClient):
    invalid = await admin_client.post(
        "/api/v1/providers", json={"name": "Imaginary", "type": "not-real"}
    )
    assert invalid.status_code == 400
    types = await admin_client.get("/api/v1/providers/types")
    assert types.status_code == 200
    mapping = {item["type"]: item for item in types.json()}
    assert mapping["freellmapi"]["capabilities"]["chat"] is True
    assert mapping["mock"]["capabilities"]["agent"] is True


async def test_reserved_slot_and_protected_caliper_proposal(admin_client: AsyncClient, project: dict):
    documents = (await admin_client.get(f"/api/v1/projects/{project['id']}/caliper")).json()
    assert len(documents) == 12
    doc = next(item for item in documents if item["slug"] == "security")
    proposal = await admin_client.post(
        f"/api/v1/caliper/{doc['id']}/proposals",
        json={"content": "# Revised security\n\nApproved rule.", "change_summary": "Clarify security", "reason": "Test"},
    )
    assert proposal.status_code == 201, proposal.text
    proposal_id = proposal.json()["id"]
    decided = await admin_client.post(
        f"/api/v1/caliper/proposals/{proposal_id}/decision",
        json={"approve": True, "notes": "Reviewed"},
    )
    assert decided.status_code == 200, decided.text
    current = await admin_client.get(f"/api/v1/caliper/{doc['id']}")
    assert current.status_code == 200
    assert current.json()["current_version"] == 2
    assert current.json()["content"].startswith("# Revised")

    slot = await admin_client.post(
        f"/api/v1/projects/{project['id']}/caliper/slot",
        json={"slug": "team-principle", "title": "Team Principle", "content": "# Team Principle"},
    )
    assert slot.status_code == 201, slot.text
    assert slot.json()["slot"] == 13
