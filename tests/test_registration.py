import uuid

import pytest


@pytest.mark.asyncio
async def test_register_client(client):
    payload = {
        "email": f"test-{uuid.uuid4()}@example.com",
        "org_name": "Test Org",
        "password": "StrongPass123",
    }
    response = await client.post("/v1/clients/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert "client_id" in data
