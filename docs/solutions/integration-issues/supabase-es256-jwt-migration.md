---
title: "Supabase JWT 401 on all protected endpoints after silent HS256-to-ES256 migration"
date: 2026-04-10
tags:
  - supabase
  - jwt
  - es256
  - hs256
  - jwks
  - authentication
  - pyjwt
  - 401-unauthorized
component: backend/app/auth.py
symptom: "401 Unauthorized on all protected API endpoints despite valid Google sign-in and visible dashboard"
root_cause: "Supabase silently migrated JWT signing from HS256 (symmetric HMAC) to ES256 (elliptic curve). The legacy JWT secret displayed in the Supabase dashboard was no longer used to sign tokens, so backend HS256 verification always failed."
fix: "Replaced HS256 secret-based verification with PyJWKClient fetching Supabase public ES256 key from JWKS endpoint"
difficulty: hard
investigation_signals:
  - "401 (not 403) proved token WAS being sent — HTTPBearer returns 403 when no Authorization header"
  - "getSession() stale-cache fix did not resolve the issue"
  - "/auth/debug endpoint revealed token header alg: ES256 vs backend expecting HS256"
  - "Supabase dashboard still displayed legacy JWT secret that was no longer active"
---

# Supabase ES256 JWT Migration — Silent Algorithm Change Breaks Auth

## Problem

After deploying bahtzang-trader with Supabase Auth (Google OAuth), all protected API endpoints returned **401 Unauthorized** even though the user was successfully signed in. The frontend showed the dashboard (not the login page), confirming Supabase had a valid session — but every API call to the FastAPI backend failed.

## Investigation Steps

1. **Is the token being sent?** The error was 401, not 403. FastAPI's `HTTPBearer` returns 403 when the Authorization header is missing entirely. 401 means the token was sent but rejected. **Conclusion: token IS being sent.**

2. **Is the token stale?** Replaced `getSession()` calls with a `setApiToken()` push model from the AuthProvider's `onAuthStateChange` listener. Still failed. **Conclusion: not a stale token issue.**

3. **What's the actual error?** Added a `/auth/debug` POST endpoint that accepted a token and ran step-by-step verification:
   - Step 1: Decode without verification → payload looked correct (`email`, `aud: "authenticated"`)
   - Step 2: Verify with `SUPABASE_JWT_SECRET` + HS256 → **`InvalidAlgorithmError: The specified alg value is not allowed`**
   - Step 3: The JWT secret length was 88 characters (correct for Supabase legacy secret)

4. **The smoking gun:** The unverified token header showed `"alg": "ES256"`, not `"HS256"`. The token was signed with an elliptic curve algorithm, but the backend was trying to verify with HMAC.

5. **Root cause confirmed:** Supabase migrated from HS256 to ES256 for JWT signing. The "legacy JWT secret (still used)" shown in the Supabase dashboard was misleading — it was no longer being used to sign new tokens.

## Root Cause

Supabase silently changed their JWT signing algorithm from **HS256** (symmetric, shared secret) to **ES256** (asymmetric, elliptic curve P-256). The dashboard still displays the legacy JWT secret, but new tokens are signed with an EC private key. Verification requires the public key, available at the JWKS endpoint.

## Solution

**Before (broken):**
```python
import jwt
from app.config import settings

payload = jwt.decode(
    token,
    settings.SUPABASE_JWT_SECRET,  # Shared secret — no longer used for signing
    algorithms=["HS256"],           # Wrong algorithm
    audience="authenticated",
)
```

**After (working):**
```python
import jwt
from jwt import PyJWKClient
from app.config import settings

_jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_jwks_url)

# Get the signing key that matches the token's `kid` header
signing_key = _jwks_client.get_signing_key_from_jwt(token)

payload = jwt.decode(
    token,
    signing_key.key,             # Public key fetched from JWKS
    algorithms=["ES256"],         # Correct algorithm
    audience="authenticated",
)
```

**Environment variable change:**
- Removed: `SUPABASE_JWT_SECRET`
- Added: `SUPABASE_URL` (e.g., `https://xxx.supabase.co`) — used to construct the JWKS endpoint URL

**Dependency:**
```
PyJWT[crypto]  # The [crypto] extra installs cryptography for ES256 support
```

## Why This Was Hard to Diagnose

1. **Misleading dashboard:** Supabase still shows "legacy JWT secret (still used)" in Project Settings → API → JWT Settings, but tokens are no longer signed with it.
2. **No migration notice:** No email, no changelog entry, no deprecation warning in the API response.
3. **Auth appeared to work:** The frontend showed the dashboard (Supabase JS client handles ES256 natively), so the user appeared signed in. Only backend verification failed.
4. **Generic error message:** The initial code caught `jwt.InvalidTokenError` and returned "Invalid token" — the specific `InvalidAlgorithmError` was swallowed.

## Prevention Strategies

### Quick Diagnostic (run first next time)
```bash
# Decode the token header to see what algorithm it claims
python3 -c "import base64,json,sys; print(json.dumps(json.loads(base64.urlsafe_b64decode(sys.argv[1].split('.')[0]+'==')),indent=2))" "$TOKEN"

# Check what JWKS publishes
curl -s "$SUPABASE_URL/auth/v1/.well-known/jwks.json" | python3 -m json.tool
```

### Make Code Resilient to Future Changes
- Use `PyJWKClient` (already implemented) — keys are fetched dynamically
- Accept multiple algorithms: `algorithms=["ES256", "RS256", "EdDSA"]`
- Log the token's `alg` header on verification failure for instant diagnosis
- Consider `supabase.auth.getUser(token)` API as algorithm-agnostic fallback (adds network hop)

### Test Cases
```python
def test_rejects_hs256_token():
    """HS256 tokens must NOT be accepted (prevents algorithm confusion)."""
    token = jwt.encode({"sub": "u1", "aud": "authenticated"}, "secret", algorithm="HS256")
    with pytest.raises(Exception):
        require_auth(mock_creds(token))

def test_jwks_publishes_ec_keys():
    """Integration: verify JWKS endpoint has EC (not RSA/HMAC) keys."""
    resp = httpx.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    for key in resp.json()["keys"]:
        assert key["kty"] == "EC"
```

## Cross-References

- **Same pattern (external API silent change):** `/Users/jameschang/Projects/fbst/docs/solutions/api-changes/mlb-api-recent-stats-deprecation.md`
- **Supabase OAuth timing issues:** `/Users/jameschang/Projects/alephco.io/alephco.io-app/docs/solutions/integration-issues/oauth-login-flash-after-google-callback.md`
- **Supabase PKCE flow failures:** `/Users/jameschang/Projects/alephco.io/alephco.io-app/docs/solutions/integration-issues/full-stack-deployment-pipeline-auth-dns-spa-fixes.md`
- **KTV Singer Apple Sign In (also ES256):** `/Users/jameschang/Projects/ktv-singer/ktv-singer-tvos/docs/DEVELOPMENT_LOG.md` (lines 192-213)

## Cross-Project Pattern

| Project | Auth Strategy | Vulnerable to Algorithm Change? |
|---------|--------------|-------------------------------|
| bahtzang-trader | Local JWKS verification (ES256) | No (now uses JWKS) |
| fbst | `supabaseAdmin.auth.getUser(token)` | No (API call, algorithm-agnostic) |
| fsvppro / alephco.io | `supabase.auth.getUser(token)` | No (API call) |
| bbq-judge | next-auth JWT strategy | No (next-auth handles it) |

The bahtzang-trader approach (local JWKS) is faster (no network call after cache) but requires keeping the allowed algorithms list current. The fbst/fsvppro approach (`getUser()` API call) is slower but completely algorithm-agnostic.
