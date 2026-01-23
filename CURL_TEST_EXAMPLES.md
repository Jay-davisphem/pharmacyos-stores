# cURL Test Examples for Field Detection Integration

API Key: `sk_snuWwofjn03bdGJB-fuddE9opMeXkgdeLUegdyfpVVYiWldm44Ek308X7ahdFtqZ`

Base URL: `http://localhost:8000`

---

## 1. Register a New Client

```bash
curl -X POST http://localhost:8000/v1/clients/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "org_name": "Test Org",
    "distributor_id": "dist_test_001",
    "password": "SecurePass123"
  }'
```

**Response:**
```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "sk_...",
  "message": "Client registered successfully"
}
```

Save the `api_key` for the bulk-ingest requests.

---

## 2. First Bulk Ingest (Standard Field Names) - Detection Triggered

This request will trigger AI field detection since no mapping exists yet.

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_snuWwofjn03bdGJB-fuddE9opMeXkgdeLUegdyfpVVYiWldm44Ek308X7ahdFtqZ" \
  -d '[
    {
      "sku": "SKU-001",
      "price": 19.99,
      "quantity": 50,
      "category": "pain relief",
      "date": "2026-01-23"
    },
    {
      "sku": "SKU-002",
      "price": 24.99,
      "quantity": 30,
      "category": "vitamins",
      "date": "2026-01-23"
    },
    {
      "sku": "SKU-003",
      "price": 14.99,
      "quantity": 75,
      "category": "supplements",
      "date": "2026-01-23"
    }
  ]'
```

**Expected Response:**
```json
{
  "processed": 3
}
```

**What happens internally:**
- ✅ No field mapping found in database
- ✅ AI (Gemini) analyzes the first object
- ✅ Detects `quantity_field: "quantity"` and `price_field: "price"`
- ✅ Stores mapping in database for this organization
- ✅ Processes all 3 items using detected fields

---

## 3. Second Bulk Ingest (Reuse Mapping) - No AI Call

This request will **NOT** trigger AI detection—it reuses the stored mapping from request #2.

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_snuWwofjn03bdGJB-fuddE9opMeXkgdeLUegdyfpVVYiWldm44Ek308X7ahdFtqZ" \
  -d '[
    {
      "sku": "SKU-004",
      "price": 29.99,
      "quantity": 20,
      "category": "cold medicine",
      "date": "2026-01-23"
    },
    {
      "sku": "SKU-005",
      "price": 9.99,
      "quantity": 100,
      "category": "bandages",
      "date": "2026-01-23"
    }
  ]'
```

**Expected Response:**
```json
{
  "processed": 2
}
```

**What happens internally:**
- ✅ Field mapping found in database (stored from request #2)
- ✅ **NO AI call made** (faster, cheaper)
- ✅ Uses stored mapping: `quantity_field: "quantity"`, `price_field: "price"`
- ✅ Processes both items using stored mapping

---

## 4. Test with Non-Standard Field Names (New Client)

First register a new client, then send data with alternative field names to test AI detection.

```bash
curl -X POST http://localhost:8000/v1/clients/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alt_fields@example.com",
    "org_name": "Alternative Fields Org",
    "distributor_id": "dist_alt_001",
    "password": "SecurePass123"
  }'
```

Save the returned `api_key`, then:

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY_FROM_REGISTRATION>" \
  -d '[
    {
      "sku": "PROD-101",
      "unit_price": 49.99,
      "quantity_available": 15,
      "stock_status": "in stock",
      "date": "2026-01-23"
    },
    {
      "sku": "PROD-102",
      "unit_price": 34.99,
      "quantity_available": 42,
      "stock_status": "in stock",
      "date": "2026-01-23"
    }
  ]'
```

**Expected Response:**
```json
{
  "processed": 2
}
```

**What happens internally:**
- ✅ No field mapping found (first request for this organization)
- ✅ AI (Gemini) analyzes first object with non-standard names
- ✅ Detects `quantity_field: "quantity_available"` and `price_field: "unit_price"`
- ✅ Stores this mapping in database
- ✅ Processes both items using detected fields

---

## 5. Update Existing Items (Deduplication)

Send the same SKU with updated quantity and price. The system will recognize it as a duplicate (based on all fields except price/quantity) and update it.

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_snuWwofjn03bdGJB-fuddE9opMeXkgdeLUegdyfpVVYiWldm44Ek308X7ahdFtqZ" \
  -d '[
    {
      "sku": "SKU-001",
      "price": 17.99,
      "quantity": 60,
      "category": "pain relief",
      "date": "2026-01-23"
    }
  ]'
```

**Expected Response:**
```json
{
  "processed": 1
}
```

**What happens internally:**
- ✅ Field mapping retrieved from database (established in request #2)
- ✅ Item recognized as duplicate based on similarity rule (all fields except price/quantity match)
- ✅ Existing record updated: `price: 19.99 → 17.99`, `quantity: 50 → 60`

---

## Testing Workflow (Sequential)

Run these commands in order to see the full workflow:

```bash
# 1. Start the server
uvicorn app.main:app --reload

# 2. In another terminal, register a client
curl -X POST http://localhost:8000/v1/clients/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "workflow_test@example.com",
    "org_name": "Workflow Test",
    "distributor_id": "dist_workflow_001",
    "password": "SecurePass123"
  }'

# 3. Copy the API key from response, then do first ingest (triggers AI detection)
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -d '[
    {"sku": "A001", "price": 10.0, "quantity": 5, "name": "Item A"},
    {"sku": "A002", "price": 20.0, "quantity": 10, "name": "Item B"}
  ]'

# 4. Do second ingest (reuses stored mapping, no AI call)
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -d '[
    {"sku": "A003", "price": 15.0, "quantity": 8, "name": "Item C"}
  ]'

# 5. View all records (requires Bearer token)
# First get a token:
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "email": "workflow_test@example.com",
    "password": "SecurePass123"
  }'

# Then use the token to get batch:
curl -X GET http://localhost:8000/v1/automation/batch \
  -H "Authorization: Bearer <YOUR_BEARER_TOKEN>"
```

---

## Testing with Different Field Names

```bash
# Register a new organization
curl -X POST http://localhost:8000/v1/clients/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "nonstandard@example.com",
    "org_name": "Non-Standard Fields",
    "distributor_id": "dist_nonstandard_001",
    "password": "SecurePass123"
  }'

# First ingest with non-standard names (AI will detect them)
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -d '[
    {
      "id": "P001",
      "cost": 5.50,
      "stock": 200,
      "supplier": "Supplier A"
    },
    {
      "id": "P002",
      "cost": 7.25,
      "stock": 150,
      "supplier": "Supplier B"
    }
  ]'

# Second ingest with same field names (mapping reused)
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -d '[
    {
      "id": "P003",
      "cost": 3.99,
      "stock": 500,
      "supplier": "Supplier C"
    }
  ]'
```

---

## Error Testing

### Test with Invalid API Key

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_invalid_key" \
  -d '[
    {"sku": "TEST", "price": 10, "quantity": 5}
  ]'
```

**Expected Response:** `401 Unauthorized`

### Test with Missing API Key

```bash
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -d '[
    {"sku": "TEST", "price": 10, "quantity": 5}
  ]'
```

**Expected Response:** `403 Forbidden`

### Test with Batch Size Exceeding Limit

```bash
# Generate array of 1001 items (exceeds default max_batch_size of 1000)
curl -X POST http://localhost:8000/v1/bulk-ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_snuWwofjn03bdGJB-fuddE9opMeXkgdeLUegdyfpVVYiWldm44Ek308X7ahdFtqZ" \
  -d '[
    {"sku": "ITEM-1", "price": 10, "quantity": 5},
    {"sku": "ITEM-2", "price": 15, "quantity": 3}
    ...
  ]'
```

**Expected Response:** `413 Payload Too Large`

---

## Key Behaviors to Verify

✅ **First Ingest Detection:**
- Send data with standard field names → AI detects them → Stored in DB

✅ **Second Ingest Reuse:**
- Send similar data → No AI call → Uses stored mapping → Faster

✅ **Non-Standard Fields:**
- Send data with `quantity_available`, `unit_price`, etc. → AI detects them correctly

✅ **Deduplication:**
- Send same SKU with different price/quantity → Existing record updated

✅ **Error Handling:**
- Invalid API key → Rejected
- Missing API key → Rejected
- Batch too large → Rejected

---

## Performance Notes

- **First Request per Org:** ~1-3 seconds (includes Gemini AI call)
- **Subsequent Requests:** ~500ms (no AI overhead, uses cached mapping)
- **Batch Processing:** Linear time scaling with batch size

---

## Debug Tips

Check database state:
```bash
sqlite3 debug.db "SELECT * FROM field_mappings;"
```

Check migration applied:
```bash
cd /home/davisphem/Documents/Codes/external/stores && \
alembic current
```

View API logs:
```bash
# Terminal where uvicorn is running will show request logs
```
