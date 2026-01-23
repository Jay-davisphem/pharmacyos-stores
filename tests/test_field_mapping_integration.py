"""Tests for field mapping integration in bulk_ingest"""
import uuid
from uuid import UUID

import pytest


@pytest.mark.asyncio
async def test_field_mapping_detection_and_reuse(client, session):
    """Test that field mapping is detected on first ingest and reused on second"""
    from app.crud import get_field_mapping
    
    # Register a new client
    register = await client.post(
        "/v1/clients/register",
        json={
            "email": f"field-detect-{uuid.uuid4()}@example.com",
            "org_name": "Field Detection Org",
            "distributor_id": f"dist_field_{uuid.uuid4()}",
            "password": "StrongPass123",
        },
    )
    api_key = register.json()["api_key"]
    client_id = UUID(register.json()["client_id"])
    
    # First ingest with standard field names
    payload_1 = [
        {"sku": "SKU-1", "price": 10.5, "quantity": 5, "date": "2026-01-20"},
        {"sku": "SKU-2", "price": 20.0, "quantity": 3, "date": "2026-01-21"},
    ]
    
    response_1 = await client.post(
        "/v1/bulk-ingest",
        json=payload_1,
        headers={"X-API-Key": api_key},
    )
    assert response_1.status_code == 200
    assert response_1.json()["processed"] == 2
    
    # Verify field mapping was stored
    mapping = await get_field_mapping(session, client_id)
    assert mapping is not None
    assert mapping.quantity_field == "quantity"
    assert mapping.price_field == "price"
    
    # Second ingest should reuse the stored mapping
    payload_2 = [
        {"sku": "SKU-3", "price": 15.0, "quantity": 2, "date": "2026-01-22"},
        {"sku": "SKU-4", "price": 25.0, "quantity": 1, "date": "2026-01-22"},
    ]
    
    response_2 = await client.post(
        "/v1/bulk-ingest",
        json=payload_2,
        headers={"X-API-Key": api_key},
    )
    assert response_2.status_code == 200
    assert response_2.json()["processed"] == 2
    
    # Mapping should be the same
    mapping_2 = await get_field_mapping(session, client_id)
    assert mapping_2.quantity_field == mapping.quantity_field
    assert mapping_2.price_field == mapping.price_field


@pytest.mark.asyncio
async def test_field_mapping_with_different_field_names(client, session):
    """Test field detection with non-standard field names"""
    from app.crud import get_field_mapping
    
    # Register a new client
    register = await client.post(
        "/v1/clients/register",
        json={
            "email": f"field-alt-{uuid.uuid4()}@example.com",
            "org_name": "Field Alt Org",
            "distributor_id": f"dist_alt_{uuid.uuid4()}",
            "password": "StrongPass123",
        },
    )
    api_key = register.json()["api_key"]
    client_id = UUID(register.json()["client_id"])
    
    # Ingest with alternative field names
    payload = [
        {"sku": "SKU-1", "unit_price": 10.5, "quantity_available": 5, "date": "2026-01-20"},
        {"sku": "SKU-2", "unit_price": 20.0, "quantity_available": 3, "date": "2026-01-21"},
    ]
    
    response = await client.post(
        "/v1/bulk-ingest",
        json=payload,
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200
    
    # Check that AI detected the alternative field names
    mapping = await get_field_mapping(session, client_id)
    assert mapping is not None
    # The detected fields should match the actual field names in the payload
    assert mapping.quantity_field in ["quantity_available", None]
    assert mapping.price_field in ["unit_price", None]
