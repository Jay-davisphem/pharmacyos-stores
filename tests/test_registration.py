import uuid

import pytest


@pytest.mark.asyncio
async def test_register_client(client):
    payload = {
        "email": f"test-{uuid.uuid4()}@example.com",
        "org_name": "Test Org",
        "distributor_id": "dist_test",
        "password": "StrongPass123",
    }
    response = await client.post("/v1/clients/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert "client_id" in data
    assert data["distributor_id"] == "dist_test"


@pytest.mark.asyncio
async def test_distributor_id_unique(client):
    email_one = f"dupe-{uuid.uuid4()}@example.com"
    email_two = f"dupe-{uuid.uuid4()}@example.com"
    payload = {
        "org_name": "Dup Org",
        "password": "StrongPass123",
        "distributor_id": "dist_unique",
    }
    first = await client.post(
        "/v1/clients/register",
        json={"email": email_one, **payload},
    )
    assert first.status_code == 200

    second = await client.post(
        "/v1/clients/register",
        json={"email": email_two, **payload},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_api_key_reset(client):
    email = f"reset-key-{uuid.uuid4()}@example.com"
    password = "StrongPass123"
    payload = {
        "email": email,
        "org_name": "Key Reset Org",
        "distributor_id": "dist_reset_key",
        "password": password,
    }
    register = await client.post("/v1/clients/register", json=payload)
    assert register.status_code == 200
    old_key = register.json()["api_key"]

    reset = await client.post(
        "/v1/auth/api-key/reset",
        json={"email": email, "password": password},
    )
    assert reset.status_code == 200
    assert reset.json()["api_key"] != old_key
    assert reset.json()["distributor_id"] == "dist_reset_key"

    second_reset = await client.post(
        "/v1/auth/api-key/reset",
        json={"email": email, "password": password},
    )
    assert second_reset.status_code == 429
