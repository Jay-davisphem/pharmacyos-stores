import uuid

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_allowed_origin_token(client):
    payload = {
        "email": f"origin-allow-{uuid.uuid4()}@example.com",
        "org_name": "Origin Org",
        "distributor_id": "dist_origin",
        "password": "StrongPass123",
    }
    register = await client.post("/v1/clients/register", json=payload)
    assert register.status_code == 200

    response = await client.post(
        "/v1/auth/token",
        json={"email": payload["email"], "password": payload["password"]},
        headers={"origin": "https://app.usepharmacyos.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_denied_origin(client):
    payload = {
        "email": f"origin-deny-{uuid.uuid4()}@example.com",
        "org_name": "Origin Deny",
        "distributor_id": "dist_origin_deny",
        "password": "StrongPass123",
    }
    await client.post("/v1/clients/register", json=payload)

    with pytest.raises(HTTPException) as exc:
        await client.post(
            "/v1/auth/token",
            json={"email": payload["email"], "password": payload["password"]},
            headers={"origin": "https://evil.com"},
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_bulk_ingest_ignores_origin(client):
    payload = {
        "email": f"origin-bulk-{uuid.uuid4()}@example.com",
        "org_name": "Origin Bulk",
        "distributor_id": "dist_origin_bulk",
        "password": "StrongPass123",
    }
    register = await client.post("/v1/clients/register", json=payload)
    api_key = register.json()["api_key"]

    response = await client.post(
        "/v1/bulk-ingest",
        json=[{"sku": "ORIGIN-SKU"}],
        headers={"origin": "https://evil.com", "X-API-Key": api_key},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_allowed_host_token(client):
    payload = {
        "email": f"host-allow-{uuid.uuid4()}@example.com",
        "org_name": "Host Org",
        "distributor_id": "dist_host",
        "password": "StrongPass123",
    }
    register = await client.post("/v1/clients/register", json=payload)
    assert register.status_code == 200

    response = await client.post(
        "/v1/auth/token",
        json={"email": payload["email"], "password": payload["password"]},
        headers={"host": "app.usepharmacyos.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_denied_host(client):
    payload = {
        "email": f"host-deny-{uuid.uuid4()}@example.com",
        "org_name": "Host Deny",
        "distributor_id": "dist_host_deny",
        "password": "StrongPass123",
    }
    await client.post("/v1/clients/register", json=payload)

    with pytest.raises(HTTPException) as exc:
        await client.post(
            "/v1/auth/token",
            json={"email": payload["email"], "password": payload["password"]},
            headers={"host": "evil.com"},
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_bulk_ingest_ignores_host(client):
    payload = {
        "email": f"host-bulk-{uuid.uuid4()}@example.com",
        "org_name": "Host Bulk",
        "distributor_id": "dist_host_bulk",
        "password": "StrongPass123",
    }
    register = await client.post("/v1/clients/register", json=payload)
    api_key = register.json()["api_key"]

    response = await client.post(
        "/v1/bulk-ingest",
        json=[{"sku": "HOST-SKU"}],
        headers={"host": "evil.com", "X-API-Key": api_key},
    )
    assert response.status_code == 200