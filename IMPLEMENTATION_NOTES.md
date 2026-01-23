# Field Mapping Integration Implementation Summary

## Overview

Integrated AI-powered field detection into the `/v1/bulk-ingest` endpoint. The system automatically detects which fields represent `quantity` and `price` on the first ingest for an organization, stores the mapping, and reuses it for all subsequent requests.

## Problem Solved

When customers have varying field names across different data sources (e.g., `quantity_available` vs `quantity`, `unit_price` vs `price`), the system couldn't correctly extract these critical fields for deduplication and inventory tracking. Manual field mapping was burdensome.

## Solution Architecture

### Database Changes

- **New Table: `field_mappings`**
  - `id` (UUID, primary key)
  - `api_client_id` (UUID, FK to api_clients, unique constraint)
  - `quantity_field` (String, nullable)
  - `price_field` (String, nullable)
  - `detected_at` (DateTime, when mapping was detected)

### Code Changes

#### `app/models.py`

Added `FieldMapping` SQLAlchemy model with:
- Unique constraint on `api_client_id` (one mapping per organization)
- Timestamps for audit trail

#### `app/crud.py`

Added two new functions:
- `get_field_mapping(session, api_client_id)` — retrieves stored mapping
- `create_field_mapping(session, api_client_id, quantity_field, price_field)` — stores detected mapping

Updated:
- `bulk_upsert_items()` now accepts `quantity_field` and `price_field` parameters for flexible field extraction

#### `app/main.py`

Enhanced `POST /v1/bulk-ingest` endpoint:
1. Checks if field mapping exists for the organization
2. If not (first ingest):
   - Extracts first object from batch
   - Calls Google Gemini API with a prompt requesting JSON response with `quantity_field` and `price_field`
   - Stores the detected (or null) mapping in database
3. If yes (subsequent ingests):
   - Retrieves stored mapping and reuses it
4. Passes detected fields to `bulk_upsert_items()` for extraction during upsert

**Detection Prompt:**

```text
Identify which fields represent quantity and price in this retail data.
Data: {sample_object}

Return JSON with exactly this structure:
{
  "quantity_field": "<field_name_or_null>",
  "price_field": "<field_name_or_null>"
}

Only return the JSON, no other text.
```

### Removed Components

- Separate `POST /v1/field-mapping` endpoint
- `FieldMappingRequest` and `FieldMappingResponse` schemas
- `app/field_mapper.py` module
- `tests/test_field_mapping.py`
- `FIELD_MAPPING.md` documentation

## Migration

- **Alembic Migration: `0005_add_field_mappings.py`**
  - Creates `field_mappings` table
  - Adds unique constraint on `api_client_id`
  - Applied successfully with `alembic upgrade head`

## Testing

### New Tests in `tests/test_field_mapping_integration.py`

**Test 1: `test_field_mapping_detection_and_reuse`**
- Registers new organization
- First ingest with standard field names (`price`, `quantity`)
- Verifies mapping is detected and stored correctly
- Second ingest verifies mapping is reused (not re-detected)

**Test 2: `test_field_mapping_with_different_field_names`**
- Tests detection with alternative field names (`unit_price`, `quantity_available`)
- Verifies AI correctly identifies non-standard field names

**Results:** All 14 tests pass ✓
- 12 existing tests still pass
- 2 new integration tests pass
- Full coverage of detection + reuse workflow

## Behavior

### First Ingest (with standard field names)

```json
POST /v1/bulk-ingest
X-API-Key: xyz123

[
  {"sku": "SKU-1", "price": 10.5, "quantity": 5, "date": "2026-01-20"},
  {"sku": "SKU-2", "price": 20.0, "quantity": 3, "date": "2026-01-21"}
]
```

→ AI detects `quantity_field: "quantity"`, `price_field: "price"` → Stored in DB

### First Ingest (with alternative field names)

```json
POST /v1/bulk-ingest
X-API-Key: abc456

[
  {"sku": "SKU-1", "unit_price": 19.99, "quantity_available": 50, "category": "vitamins"},
  {"sku": "SKU-2", "unit_price": 24.99, "quantity_available": 30, "category": "supplements"}
]
```

→ AI detects `quantity_field: "quantity_available"`, `price_field: "unit_price"` → Stored in DB

### Subsequent Ingests

```json
POST /v1/bulk-ingest
X-API-Key: xyz123

[
  {"sku": "SKU-3", "price": 15.0, "quantity": 2, "date": "2026-01-22"}
]
```

→ Retrieves stored mapping → Uses it for extraction → No AI call needed

## Configuration

Requires environment variables (already in `.env.example`):
- `GEMINI_API_KEY` — Google Generative AI API key
- `GEMINI_MODEL` — Model to use (defaults to `gemini-2.5-flash-lite`)

If `GEMINI_API_KEY` is not set, detection gracefully falls back to `None` for both fields (no error thrown).

## Documentation Updated

- **README.md**: Removed field-mapping endpoint docs, added automatic field detection explanation with examples

## Benefits

1. **Zero Configuration:** Organizations don't need to pre-configure field mappings
2. **One-Time Detection:** AI is called once per organization, stored in DB for reuse
3. **Flexible Field Names:** Handles any naming convention for quantity/price fields
4. **Essential for Deduplication:** Ensures price/quantity fields are correctly identified, which is critical for the similarity-based deduplication logic
5. **Graceful Degradation:** If AI detection fails or API is unavailable, system continues with `None` values

## Error Handling

- JSON parsing errors from Gemini API are caught and gracefully ignored
- If detection fails, `quantity_field` and `price_field` are stored as `None`
- System continues processing the batch even if detection encounters issues
