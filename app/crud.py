from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessToken, ApiClient, FieldMapping, PasswordResetToken, StoreItem
from app.utils import compute_fingerprint, extract_number


async def create_api_client(
    session: AsyncSession,
    email: str,
    org_name: str,
    distributor_id: str,
    api_key_hash: str,
    api_key_sha: str,
    password_hash: str,
    password_salt: str,
) -> ApiClient:
    existing = await session.execute(select(ApiClient).where(ApiClient.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")
    existing_distributor = await session.execute(
        select(ApiClient).where(ApiClient.distributor_id == distributor_id)
    )
    if existing_distributor.scalar_one_or_none():
        raise ValueError("Distributor ID already registered")
    client = ApiClient(
        email=email,
        org_name=org_name,
        distributor_id=distributor_id,
        api_key_hash=api_key_hash,
        api_key_sha=api_key_sha,
        password_hash=password_hash,
        password_salt=password_salt,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


async def create_access_token(
    session: AsyncSession,
    api_client_id,
    token_hash: str,
) -> AccessToken:
    token = AccessToken(api_client_id=api_client_id, token_sha=token_hash)
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def update_api_key(
    session: AsyncSession,
    client: ApiClient,
    api_key_hash: str,
    api_key_sha: str,
) -> None:
    client.api_key_hash = api_key_hash
    client.api_key_sha = api_key_sha
    client.last_api_key_reset_at = datetime.now(UTC)
    await session.commit()


async def create_password_reset_token(
    session: AsyncSession,
    api_client_id,
    token_hash: str,
) -> PasswordResetToken:
    token = PasswordResetToken(api_client_id=api_client_id, token_sha=token_hash)
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def mark_reset_token_used(
    session: AsyncSession,
    token: PasswordResetToken,
    password_hash: str,
    password_salt: str,
) -> None:
    await session.execute(
        update(ApiClient)
        .where(ApiClient.id == token.api_client_id)
        .values(password_hash=password_hash, password_salt=password_salt)
    )
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token.id)
        .values(used_at=datetime.now(UTC))
    )
    await session.commit()


async def bulk_upsert_items(
    session: AsyncSession,
    api_client_id,
    payloads: list[dict[str, Any]],
    quantity_field: str | None = None,
    price_field: str | None = None,
) -> int:
    rows = []
    now = datetime.now(UTC)
    for payload in payloads:
        # Skip invalid payloads (empty or missing required fields)
        if not payload or not isinstance(payload, dict):
            continue
        
        fingerprint = compute_fingerprint(payload, price_field, quantity_field)
        rows.append(
            {
                "api_client_id": api_client_id,
                "fingerprint": fingerprint,
                "data": payload,
                "price": extract_number(payload, price_field or "price"),
                "quantity": extract_number(payload, quantity_field or "quantity"),
                "updated_at": now,
                "created_at": now,
                "is_exported": False,
                "exported_at": None,
            }
        )

    if not rows:
        return 0

    if session.bind.dialect.name == "postgresql":
        stmt = pg_insert(StoreItem).values(rows)
        update_columns = {
            "data": stmt.excluded.data,
            "price": stmt.excluded.price,
            "quantity": stmt.excluded.quantity,
            "updated_at": now,
            "is_exported": False,
            "exported_at": None,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["api_client_id", "fingerprint"],
            set_=update_columns,
        )
        await session.execute(stmt)
        await session.commit()
        return len(rows)

    processed = 0
    for row in rows:
        result = await session.execute(
            select(StoreItem).where(
                StoreItem.api_client_id == api_client_id,
                StoreItem.fingerprint == row["fingerprint"],
            )
        )
        item = result.scalar_one_or_none()
        if item:
            for key, value in row.items():
                if key == "created_at":
                    continue
                setattr(item, key, value)
        else:
            session.add(StoreItem(**row))
        processed += 1
    await session.commit()
    return processed


async def fetch_automation_batch(
    session: AsyncSession,
    api_client_id,
    limit: int,
):
    query = (
        select(StoreItem)
        .where(
            StoreItem.is_exported.is_(False),
            StoreItem.api_client_id == api_client_id,
        )
        .order_by(StoreItem.created_at)
        .limit(limit)
    )
    if session.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    result = await session.execute(query)
    items = list(result.scalars().all())
    if not items:
        return []

    ids = [item.id for item in items]
    await session.execute(
        update(StoreItem)
        .where(StoreItem.id.in_(ids))
    .values(is_exported=True, exported_at=datetime.now(UTC))
    )
    await session.commit()
    return items


async def get_field_mapping(session: AsyncSession, api_client_id) -> FieldMapping | None:
    """Get stored field mapping for an organization."""
    result = await session.execute(
        select(FieldMapping).where(FieldMapping.api_client_id == api_client_id)
    )
    return result.scalar_one_or_none()


async def create_field_mapping(
    session: AsyncSession,
    api_client_id,
    quantity_field: str | None,
    price_field: str | None,
) -> FieldMapping:
    """Store detected field mapping for an organization."""
    # Delete old mapping if exists
    await session.execute(
        update(FieldMapping).where(FieldMapping.api_client_id == api_client_id).values(
            quantity_field=quantity_field, price_field=price_field, detected_at=datetime.now(UTC)
        )
    )
    
    # Check if update affected anything
    result = await session.execute(
        select(FieldMapping).where(FieldMapping.api_client_id == api_client_id)
    )
    mapping = result.scalar_one_or_none()
    
    if not mapping:
        # Create new if doesn't exist
        mapping = FieldMapping(
            api_client_id=api_client_id,
            quantity_field=quantity_field,
            price_field=price_field,
        )
        session.add(mapping)
    
    await session.commit()
    await session.refresh(mapping)
    return mapping
