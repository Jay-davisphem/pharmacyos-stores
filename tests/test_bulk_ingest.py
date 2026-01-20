import uuid

import pytest


@pytest.mark.asyncio
async def test_bulk_ingest(client):
    register = await client.post(
        "/v1/clients/register",
        json={
            "email": f"bulk-{uuid.uuid4()}@example.com",
            "org_name": "Bulk Org",
            "password": "StrongPass123",
        },
    )
    api_key = register.json()["api_key"]

    payload = [
        {"sku": "SKU-1", "price": 10, "quantity": 5, "date": "2026-01-20"},
        {"sku": "SKU-1", "price": 12, "quantity": 6, "date": "2026-01-20"},
    ]

    response = await client.post(
        "/v1/bulk-ingest",
        json=payload,
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 2
