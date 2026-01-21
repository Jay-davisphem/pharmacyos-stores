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

## API endpoints

- `POST /v1/clients/register` — register (email, org, distributor_id, password) and receive API key
- `POST /v1/auth/token` — exchange email/password for bearer token (returns distributor_id)
- `POST /v1/auth/api-key/reset` — rotate API key (email/password)
- `POST /v1/auth/password-reset/request` — request a reset token (email)
- `POST /v1/auth/password-reset/confirm` — confirm reset with token and new password
- `POST /v1/bulk-ingest` — bulk upsert with `X-API-Key`
- `GET /v1/automation/batch` — fetch unexported records with `Authorization: Bearer <token>`

## Notes

- `price` and `quantity` are optional and stored separately for faster access.
- All payloads are stored in full as JSON.

## API Docs

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
