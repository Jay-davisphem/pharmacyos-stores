import uuid

import pytest


@pytest.mark.asyncio
async def test_automation_batch(client):
    email = f"auto-{uuid.uuid4()}@example.com"
    register = await client.post(
        "/v1/clients/register",
        json={
            "email": email,
            "org_name": "Auto Org",
            "distributor_id": "dist_auto",
            "password": "StrongPass123",
        },
    )
    api_key = register.json()["api_key"]

    token_response = await client.post(
        "/v1/auth/token",
        json={"email": email, "password": "StrongPass123"},
    )
    assert token_response.status_code == 200
    assert token_response.json()["distributor_id"] == "dist_auto"
    access_token = token_response.json()["access_token"]

    payload = [
        {"sku": "SKU-2", "price": 15, "quantity": 2, "date": "2026-01-20"},
    ]
    await client.post(
        "/v1/bulk-ingest",
        json=payload,
        headers={"X-API-Key": api_key},
    )

    response = await client.get(
        "/v1/automation/batch",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
