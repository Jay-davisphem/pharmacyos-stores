import uuid

import pytest


@pytest.mark.asyncio
async def test_password_reset_flow(client):
    email = f"reset-{uuid.uuid4()}@example.com"
    password = "StrongPass123"
    new_password = "NewStrongPass456"

    register = await client.post(
        "/v1/clients/register",
        json={
            "email": email,
            "org_name": "Reset Org",
            "distributor_id": "dist_reset",
            "password": password,
        },
    )
    assert register.status_code == 200

    reset_request = await client.post(
        "/v1/auth/password-reset/request",
        json={"email": email},
    )
    assert reset_request.status_code == 200
    reset_token = reset_request.json()["reset_token"]

    reset_confirm = await client.post(
        "/v1/auth/password-reset/confirm",
        json={"reset_token": reset_token, "new_password": new_password},
    )
    assert reset_confirm.status_code == 200

    token_response = await client.post(
        "/v1/auth/token",
        json={"email": email, "password": new_password},
    )
    assert token_response.status_code == 200
    assert "access_token" in token_response.json()