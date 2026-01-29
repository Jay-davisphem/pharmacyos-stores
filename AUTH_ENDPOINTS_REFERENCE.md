# Authentication Endpoints Reference

## Overview
This document lists all authentication endpoints for password reset and API key management.

---

## 1. Reset API Key

**Endpoint:** `POST /v1/auth/api-key/reset`

**Method:** `POST`

**Authentication:** None (uses email/password)

**Description:** Regenerates the API key for bulk ingestion using email and password credentials.

### Request Body

```json
{
  "email": "admin@usepharmacyos.com",
  "password": "StrongPass123"
}
```

### Request Headers

```
Content-Type: application/json
```

### Success Response (200)

```json
{
  "api_key": "sk_newGeneratedKey123...",
  "distributor_id": "dist_12345"
}
```

### Error Responses

**401 Unauthorized** - Invalid credentials:
```json
{
  "detail": "Invalid credentials"
}
```

**429 Too Many Requests** - API key reset cooldown active:
```json
{
  "detail": "API key reset cooldown active"
}
```
**Headers:** `Retry-After: 3600` (seconds until next reset allowed)

### Example cURL

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/api-key/reset' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "admin@usepharmacyos.com",
    "password": "StrongPass123"
  }'
```

### Rate Limit Cooldown

- **Default cooldown:** 60 minutes (configurable)
- After resetting, you must wait this duration before resetting again
- Check `Retry-After` header for exact wait time in seconds

---

## 2. Request Password Reset

**Endpoint:** `POST /v1/auth/password-reset/request`

**Method:** `POST`

**Authentication:** None

**Description:** Initiates a password reset by sending a reset token via email. The token is valid for one-time use.

### Request Body

```json
{
  "email": "admin@usepharmacyos.com"
}
```

### Request Headers

```
Content-Type: application/json
```

### Success Response (200)

```json
{
  "reset_token": "reset_token_here"  // Only returned if RESET_TOKEN_DEBUG=true
}
```

Or (if debug mode disabled):

```json
{}
```

### Error Responses

**404 Not Found** - Email not registered:
```json
{
  "detail": "Email not found"
}
```

### Example cURL

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/password-reset/request' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "admin@usepharmacyos.com"
  }'
```

### Process Flow

1. User requests password reset with their email
2. System generates a one-time reset token
3. Email is sent to the registered email address with reset link/token
4. User checks email and gets the reset token
5. User calls `/v1/auth/password-reset/confirm` with the token

**Debug Mode:** If `RESET_TOKEN_DEBUG=true` in environment, the token is returned in response (for testing).

---

## 3. Confirm Password Reset

**Endpoint:** `POST /v1/auth/password-reset/confirm`

**Method:** `POST`

**Authentication:** None

**Description:** Completes the password reset using the token received via email and sets a new password.

### Request Body

```json
{
  "reset_token": "reset_token_from_email",
  "new_password": "NewStrongPass456"
}
```

### Request Headers

```
Content-Type: application/json
```

### Success Response (200)

```json
{
  "status": "ok"
}
```

### Error Responses

**401 Unauthorized** - Invalid or expired token:
```json
{
  "detail": "Invalid token"
}
```

### Example cURL

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/password-reset/confirm' \
  -H 'Content-Type: application/json' \
  -d '{
    "reset_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "new_password": "NewStrongPass456"
  }'
```

### Token Lifecycle

- **Generated:** When user requests password reset
- **Sent:** Via email to registered address
- **Valid:** One-time use only
- **Expires:** After used or after configured expiration time
- **Cannot be reused:** After successful password reset

---

## Complete Example: Full Password Reset Flow

### Step 1: Request Reset Token

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/password-reset/request' \
  -H 'Content-Type: application/json' \
  -d '{"email": "admin@usepharmacyos.com"}'

# Response:
# {} (check email for reset token)
# OR with debug mode:
# {"reset_token": "abc123xyz..."}
```

### Step 2: Confirm Password Reset

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/password-reset/confirm' \
  -H 'Content-Type: application/json' \
  -d '{
    "reset_token": "abc123xyz...",
    "new_password": "MyNewPassword789"
  }'

# Response:
# {"status": "ok"}
```

### Step 3: Login with New Password

Now you can:
- Use the new password for API key reset
- Use email/password to request access tokens

---

## Complete Example: API Key Reset Flow

### Step 1: Reset API Key

```bash
curl -X POST 'https://stores.usepharmacyos.com/v1/auth/api-key/reset' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "admin@usepharmacyos.com",
    "password": "StrongPass123"
  }'

# Response:
# {"api_key": "sk_new123...", "distributor_id": "dist_12345"}
```

### Step 2: Update Your Client

Replace your old API key with `sk_new123...` in your bulk-ingest requests.

---

## Error Handling Summary

| Code | Endpoint | Error | Meaning |
|------|----------|-------|---------|
| 401 | `/v1/auth/api-key/reset` | Invalid credentials | Email/password mismatch |
| 429 | `/v1/auth/api-key/reset` | API key reset cooldown active | Must wait before resetting again |
| 404 | `/v1/auth/password-reset/request` | Email not found | Email not registered |
| 401 | `/v1/auth/password-reset/confirm` | Invalid token | Token expired or already used |

---

## Best Practices

✅ **DO:**
- Store API keys securely (environment variables, secrets manager)
- Change API keys regularly for security
- Use strong passwords (12+ characters, mixed case, numbers, symbols)
- Keep reset tokens confidential
- Check `Retry-After` header before retrying failed requests

❌ **DON'T:**
- Hardcode API keys in source code
- Share reset tokens via unsecured channels
- Reuse old API keys after rotation
- Use the same password for multiple services

---

## Configuration

### Password Reset

- **Token Expiry:** Configurable (default: 24 hours)
- **Debug Mode:** Set `RESET_TOKEN_DEBUG=true` to return token in response

### API Key Reset

- **Cooldown:** `api_key_reset_cooldown_minutes` (default: 60 minutes)
- **Prevents abuse:** Must wait between successive resets

---

## Endpoints Summary Table

| Method | Endpoint | Purpose | Requires |
|--------|----------|---------|----------|
| POST | `/v1/auth/api-key/reset` | Rotate API key | Email, Password |
| POST | `/v1/auth/password-reset/request` | Start password reset | Email |
| POST | `/v1/auth/password-reset/confirm` | Complete password reset | Reset Token, New Password |

---

## Related Endpoints

- `POST /v1/clients/register` - Create new organization and get initial API key
- `POST /v1/auth/token` - Get bearer token for automation access

See full API documentation at: `https://stores.usepharmacyos.com/docs`
