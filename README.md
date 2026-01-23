# Store Bulk API

FastAPI service for bulk JSON ingestion with PostgreSQL storage, API key security, and automation batch retrieval.

## ✅ Behavior and rules

- **Similarity rule:** objects are considered the same if all top-level fields match **except** `price` and `quantity`.
- **Upsert behavior:** when a similar object is found, **fields are updated** with the incoming payload.
- **Batch ingestion:** payload is a raw list `[{...}, {...}]`.
- **Security:** API key for ingestion; bearer access token for batch retrieval (token exchange with email/password).
- **Rate limiting:** per account per IP, default 300 requests per 60 seconds.

## Configuration

Set environment variables (see `.env.example`):

- `DATABASE_URL`
- `MAX_BATCH_SIZE` (optional)
- `RESEND_API_KEY`
- `EMAIL` (sender address)
- `EMAIL_PROVIDER` (`resend` or `console`)
- `RESET_TOKEN_DEBUG` (optional: return reset token in API response)
- `RATE_LIMIT_REQUESTS`
- `RATE_LIMIT_WINDOW_SECONDS`
- `API_KEY_RESET_COOLDOWN_MINUTES`
- `ALLOWED_ORIGIN_REGEX` (optional override for origin guard)
- `GEMINI_API_KEY` (optional: for AI-powered field mapping)
- `GEMINI_MODEL` (optional: defaults to `gemini-2.5-flash-lite`)

## API endpoints

- `POST /v1/clients/register` — register (email, org, distributor_id, password) and receive API key
- `POST /v1/auth/token` — exchange email/password for bearer token (returns distributor_id)
- `POST /v1/auth/api-key/reset` — rotate API key (email/password)
- `POST /v1/auth/password-reset/request` — request a reset token (email)
- `POST /v1/auth/password-reset/confirm` — confirm reset with token and new password
- `POST /v1/bulk-ingest` — bulk upsert with `X-API-Key` (includes automatic AI-powered field detection on first ingest)
- `GET /v1/automation/batch` — fetch unexported records with `Authorization: Bearer <token>`

## Notes

- `price` and `quantity` are optional and stored separately for faster access.
- All payloads are stored in full as JSON.
- **Automatic AI Field Detection:** On the first `/v1/bulk-ingest` request for an organization, the API automatically uses Google Gemini to detect which fields represent `quantity` and `price`, even when named differently (e.g., `quantity_available`, `stock`, `unit_price`, `price_per_item`). The detected mapping is stored per organization and reused for all subsequent ingests, eliminating the need for manual field mapping configuration.

### Automatic Field Detection Example

**First Ingest (detection occurs automatically):**
```json
POST /v1/bulk-ingest
X-API-Key: <api-key>

[
  {
    "sku": "ABC123",
    "quantity_available": 50,
    "unit_price": 19.99,
    "category": "pain relief"
  },
  {
    "sku": "DEF456",
    "quantity_available": 30,
    "unit_price": 24.99,
    "category": "vitamins"
  }
]
```

The API automatically detects:
- `quantity_field`: `quantity_available`
- `price_field`: `unit_price`

**Subsequent Ingests (mapping reused):**
```json
POST /v1/bulk-ingest
X-API-Key: <api-key>

[
  {
    "sku": "GHI789",
    "quantity_available": 75,
    "unit_price": 14.99,
    "category": "supplements"
  }
]
```

The stored field mapping is automatically applied, no configuration needed.

## API Docs

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
