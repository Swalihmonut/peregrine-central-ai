# Cloud Integration Test Plan — Beta V-001 Private Demo
**Target Scope:** End-to-End System Integration from Browser to Remote AI Model & Database  
**Author:** Central API, Hosting and Infrastructure Engineer  
**Date:** 2026-11-01  
**Status:** DRAFT SPECIFICATION (To be executed upon staging deployment)  

---

## 1. Test Architecture & Data Flow

```
[1. Student Browser]
        │  (HTTPS / TLS 1.3)
        ▼
[2. Next.js Frontend App] (Vercel Hobby / Node Container / Tunnel)
        │  (Internal API Route Dispatch)
        ▼
[3. Cloudflare Edge Gateway] (api.ai.peregrineacademy.in)
        │  (Injected Service Bearer Token)
        ▼
[4. Python Central AI API] (Koyeb Free Container / asgi.py)
        ├──► [5A. Inference Provider] (Mock Provider / Google Gemini Flash)
        └──► [5B. Persistence Layer] (Supabase PostgreSQL + pgvector)
```

---

## 2. Comprehensive Integration Test Matrix

### Stage 1: Browser → Frontend Integration
- **Test 1.1: Visual & Layout Stability**
  - Verify page loads with HTTP 200 across Chrome, Safari, and mobile viewports.
  - Verify Arabic typography (Amiri / IBM Plex Sans Arabic) and diacritics (tashkeel) render without glyph clipping.
- **Test 1.2: Client-Side Session & State**
  - Verify learner auth state persists across route transitions (`/tutor`, `/speaking`, `/exams`, `/notebook`).
  - Verify unauthorized access to protected routes redirects to the sign-in modal.

### Stage 2: Frontend → Gateway Integration
- **Test 2.1: CORS Preflight & Exact Origin Matching**
  - Dispatch `OPTIONS` preflight from `https://ai.peregrineacademy.in` to `https://api.ai.peregrineacademy.in`.
  - Assert HTTP 204 No Content with `Access-Control-Allow-Origin: https://ai.peregrineacademy.in` and `Vary: Origin`.
- **Test 2.2: Request ID Propagation**
  - Dispatch `POST /api/v1/chat` with custom `X-Request-ID: test-trace-101`.
  - Assert that response header `x-request-id` and JSON payload `request_id` both match `test-trace-101`.
- **Test 2.3: Route Handlers Execution**
  - Verify all 15 Next.js API routes (`/api/chat`, `/api/feedback`, `/api/notebooks`, etc.) respond correctly without 404 or SSR crashes.

### Stage 3: Gateway → Central API Integration
- **Test 3.1: Edge Secret Injection**
  - Verify that student client does not supply `CENTRAL_AI_API_KEY`.
  - Verify gateway worker injects `Authorization: Bearer <SECRET_KEY>` server-side before calling Koyeb.
- **Test 3.2: Rate Limiting & Concurrency Headers**
  - Dispatch requests at 10 RPM. Verify response includes `X-RateLimit-Limit: 60`, `X-RateLimit-Remaining: 59-50`.
  - Dispatch 65 rapid requests. Verify 61st request returns HTTP 429 Too Many Requests with `X-RateLimit-Reset`.
- **Test 3.3: Request Body Limit Enforcement (DoS Guard)**
  - Dispatch 2.5 MB JSON payload. Verify Central API intercepts and returns HTTP 413 `PAYLOAD_TOO_LARGE`.

### Stage 4: Central API → Model Provider Integration
- **Test 4.1: Mock Provider Baseline**
  - With `CENTRAL_AI_PROVIDER=mock`, dispatch Tutor, Speaking, and Exams requests.
  - Verify response status is `success`, content is pedagogically structured, and latency is <25 ms.
- **Test 4.2: Gemini Flash Remote Inference**
  - With `CENTRAL_AI_PROVIDER=hosted` and `HOSTED_ENDPOINT` configured, dispatch Arabic linguistic query.
  - Assert real generated answer content, token accounting (`prompt_tokens`, `completion_tokens`), and finish reason `stop`.
- **Test 4.3: Model Timeout Interception**
  - Simulate upstream provider taking >120 seconds.
  - Verify Central API terminates gracefully with HTTP 500 and error code `MODEL_TIMEOUT`, without crashing the ASGI worker.

### Stage 5: Central API / Frontend → Supabase Integration
- **Test 5.1: Vector Embedding & Similarity Search**
  - Ingest an Arabic text source into `notebook_sources`. Generate 768-dim embedding and insert into `notebook_chunks`.
  - Execute semantic search via `match_notebook_chunks(query_embedding, match_threshold=0.5)`.
  - Assert that relevant Arabic passages are returned with cosine similarity score > 0.70.
- **Test 5.2: Row Level Security (RLS) Isolation**
  - Attempt to read User B's notebook records using User A's JWT token.
  - Assert that PostgreSQL returns 0 rows, confirming strict multi-tenant isolation.

---

## 3. Resilience, Reliability & Recovery Test Suite

### Test 6.1: Cold-Start Wakeup Verification (Koyeb 1-Hour Sleep)
1. Leave the Koyeb Free instance idle for 65 minutes until it enters deep sleep.
2. Dispatch `GET /health` from an external client.
3. **Pass Criteria:**
   - Container provisions and responds within **1.0 to 5.0 seconds**.
   - Status code is HTTP 200 OK.
   - Subsequent requests complete in **<50 ms**.

### Test 6.2: Provider Failure & Automatic Fallback
1. Configure `CENTRAL_AI_PROVIDER=hosted` and `CENTRAL_AI_FALLBACK_PROVIDER=mock`.
2. Provide an invalid hosted inference endpoint to simulate cloud provider downtime.
3. Dispatch `POST /api/v1/chat`.
4. **Pass Criteria:**
   - Central API logs warning: `Primary provider 'hosted' failed... Attempting fallback to 'mock'`.
   - Request completes successfully with HTTP 200 and fallback content.
   - Zero unhandled exceptions returned to user.

### Test 6.3: Consent Withdrawal & Feedback Purge Verification
1. Submit feedback with `consent_for_training=True` for `user_id: learner_omar`.
2. Verify record enters `learning_queue.jsonl`.
3. Submit withdrawal request: `POST /api/v1/feedback/consent/withdraw` with `user_id: learner_omar`.
4. **Pass Criteria:**
   - Response returns `{"status": "consent_revoked", "purged_records_count": 1}`.
   - Learning queue depth decreases by 1; learner_omar's data is permanently purged from candidate datasets.

### Test 6.4: Supabase Manual Backup & Restore Dry-Run
1. Execute manual logical backup:
   ```bash
   PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump -h "db.YOUR_PROJECT.supabase.co" -U postgres -d postgres -f "/tmp/backup_test.sql"
   ```
2. Verify backup file size > 0 and contains valid SQL DDL (`CREATE TABLE`, `CREATE INDEX`).
3. Assert backup script completes with return code 0.
