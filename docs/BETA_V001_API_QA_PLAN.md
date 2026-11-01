# Central Arabic AI API & Cloud QA Test Plan — Beta V-001

**Document Version:** 1.0.0 (Beta V-001)  
**Role:** Central API, Hosting and Infrastructure QA Owner  
**Workspace:** `/Users/muhammedswaliht/peregrine-arabic-ai-lab`  
**Target Package:** `central_runtime_api`  
**Execution Environment:** macOS 27.0.1 (Apple Silicon M4) / Linux Rootless Container (Python 3.11)  
**Status:** COMPLETE & AUTOMATED

---

## 1. Executive Summary & Quality Strategy

The priority for **Beta V-001** is validating a **dependable, shared, and robust Central Arabic AI API service** that powers the entire Peregrine application ecosystem:
- **Arabic AI Tutor:** Syntactic parsing (`إعراب`), morphological analysis (`صرف`), and grammatical rule explanations.
- **AI Speaking Partner:** Interactive conversational turns in Modern Standard Arabic (MSA) and dialects (Emirati, Egyptian, Levantine).
- **Exams App:** Question analysis, correct option rationale, and distractor refutation.
- **Continuous Learning Pipeline:** Consent-gated operational feedback ingestion and candidate dataset generation for philologist review.

### Core Testing Tenets:
1. **Zero Contamination Verification:** Qwen 3 reasoning scratchpads (`<think>...</think>`) must remain strictly isolated. If token budgets are exhausted inside thinking traces, the API must return a clear `MODEL_REASONING_ONLY` error without emitting raw thought logs.
2. **Provider Independence & Fallback:** Client applications interact with a single invariant HTTP API contract. The runtime dynamically handles transitions between **Mock** (offline tests), **Ollama** (`qwen3:4b`), **MLX** (`IFM/Jais-3-3.7B-MLX-4bit`), and **Hosted Providers** (OpenAI / vLLM / HUMAIN Node), seamlessly executing automated provider fallback upon primary provider failures.
3. **Hardware Guarding & Mutual Exclusion:** Single-lock concurrency serialization prevents GPU memory exhaustion and disk swap expansion. Safety interlocks automatically reject queries if host disk headroom drops below the 15 GiB threshold.
4. **Consent Gate & Privacy Integrity:** Customer feedback is segregated at ingestion. Unconsented feedback is recorded strictly for operational telemetry and is guaranteed never to enter the learning queue. All PII (emails, GCC phone numbers, Saudi and Emirates IDs) is redacted, and user IDs are one-way hashed with SHA-256.
5. **Truth in Cloud Readiness:** In strict adherence to testing standards, **cloud readiness cannot and will not be claimed until the actual remote hosted service has been provisioned, deployed, and tested live**.

---

## 2. API Surface & Architecture Under Test

```
+───────────────────────────────────────────────────────────────────────────────────+
|                           Peregrine Application Ecosystem                         |
|   [ Arabic AI Tutor ]   [ AI Speaking Partner ]   [ Exams App ]   [ Research ]    |
+─────────────────────────────────────────+─────────────────────────────────────────+
                                          |
                                HTTP / JSON (REST API)
                                          |
+─────────────────────────────────────────v─────────────────────────────────────────+
|                  Central AI Runtime API (central_runtime_api)                     |
|                                                                                   |
|  [ Endpoints ]                                                                    |
|    GET  /health              GET  /ready                                          |
|    POST /api/v1/chat         POST /api/v1/tutor/explain                           |
|    POST /api/v1/speaking     POST /api/v1/exams/explain                           |
|    POST /api/v1/feedback                                                          |
|                                                                                   |
|  [ Middleware & Guards ]                                                          |
|    - Bearer API Key Authentication (CENTRAL_AI_API_KEY)                           |
|    - Sliding-Window Rate Limiter & Concurrency Guard                              |
|    - PII Redaction & User Anonymization Middleware                                |
|    - Pydantic Schema Validation & Error Envelope Generator                        |
|    - Sequential Hardware Execution Lock (threading.Lock)                          |
|    - Storage Safety Interlock (< 15 GB disk space abort)                          |
|    - Automated Provider Fallback Router                                           |
+─────────────────────────────────────────+─────────────────────────────────────────+
                                          |
                      Provider-Independent Abstract Interface
                                          |
         +-----------------+--------------+-----------------+-----------------+
         |                 |                                |                 |
         v                 v                                v                 v
   [ Mock Adapter ]  [ Ollama Adapter ]             [ MLX Adapter ]   [ Hosted Adapter ]
   (Offline / CI)    (qwen3:4b @ :11434)            (Jais 3 @ :8080)  (Remote Cloud vLLM)
```

---

## 3. The 13 Core QA Test Dimensions & Methodologies

The automated QA suite (`tests/test_qa_suite.py`) provides rigorous coverage across all 13 mission-critical functional areas:

### 3.1 Health and Readiness Endpoints
- **GET `/health`:** Validates HTTP 200, valid JSON response, status string `"ok"`, version tag (`0.1.0-beta`), active provider, and active model.
- **GET `/ready`:** Validates readiness status, active provider availability, disk storage free telemetry, memory pressure percentage, and sequential lock idle state.
- **Disk Safety Interlock:** Simulates low disk headroom (< 15 GB threshold) and verifies that `/ready` returns HTTP 503 (`not_ready_or_provider_stopped`).

### 3.2 Authentication and Authorization
- **Missing Token:** Requests to protected endpoints without `Authorization` header return HTTP 401 (`UNAUTHORIZED`).
- **Invalid Token:** Requests with invalid tokens return HTTP 401 (`UNAUTHORIZED`).
- **Valid Bearer Token:** Requests with valid `Bearer <token>` return HTTP 200 with standard response envelopes.
- **Public Infrastructure Probes:** Liveness (`/health`) and readiness (`/ready`) endpoints remain accessible without tokens to allow uninhibited container orchestrator health checks.

### 3.3 Valid and Invalid Requests
- **Valid Requests:** Successful processing across `/api/v1/chat`, `/api/v1/tutor/explain`, `/api/v1/speaking/respond`, and `/api/v1/exams/explain`.
- **Malformed JSON:** Sending corrupt JSON bytes returns HTTP 400 (`INVALID_JSON`).
- **Empty Body:** Sending an empty HTTP POST body returns HTTP 400 (`EMPTY_REQUEST_BODY`).
- **Schema Validation Errors:** Missing required fields or out-of-range parameters (e.g. `temperature > 2.0`, `max_tokens < 1`) return HTTP 422 (`SCHEMA_VALIDATION_ERROR`).
- **Endpoint Not Found:** Non-existent routes return HTTP 404 (`ENDPOINT_NOT_FOUND`).
- **CORS Options:** Preflight `OPTIONS` requests return HTTP 204 with required `Access-Control-Allow-*` headers.

### 3.4 Arabic and English Request Handling
- **Modern Standard Arabic (MSA) with Tashkeel:** Preserves full Arabic diacritical marks (حركات) without Unicode corruption, entity encoding errors, or mojibake.
- **Dialectal Diversity:** Verifies that dialectal variations (Emirati, Egyptian, Levantine) are handled in Speaking Partner scenarios.
- **Pure English:** Validates linguistic explanations and prompts queried entirely in English.
- **Code-Switching:** Validates mixed Arabic and English technical grammar queries.

### 3.5 Conversation History
- **Multi-Turn Chat Context:** Ensures multi-turn message arrays preserve chronological context and role sequences.
- **Dialogue History in Speaking Partner:** Tests passing prior turns in `dialogue_history` alongside the current user utterance.

### 3.6 Model Timeout and Unavailable Provider
- **Model Timeout:** Downstream inference timeouts return HTTP 500 (`MODEL_TIMEOUT`) with finish reason `"timeout"`.
- **Unavailable Provider:** Connection failures or offline providers return HTTP 500 (`PROVIDER_UNAVAILABLE`).
- **Hosted Adapter Configuration Guard:** Calling an unconfigured hosted provider returns HTTP 500 (`HOSTED_ENDPOINT_NOT_CONFIGURED`).

### 3.7 Empty Model Responses
- **Empty Output Interception:** When downstream model yields an empty or whitespace-only response, the runtime flags HTTP 500 (`EMPTY_MODEL_RESPONSE`) instead of exposing blank output to users.
- **Reasoning-Only Contamination Interception:** When reasoning models output only thinking traces without final answer content, the runtime isolates the scratchpad and returns HTTP 500 (`MODEL_REASONING_ONLY`).

### 3.8 Rate Limits and Concurrency
- **Rate Limit Headers:** Standard `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers returned on every request.
- **Sliding-Window RPM Enforcement:** Breaching configured requests per minute triggers HTTP 429 (`RATE_LIMIT_EXCEEDED`).
- **Concurrency & Lock Thread-Safety:** Simultaneous multi-threaded requests are serialized cleanly without memory corruption or race conditions.

### 3.9 Usage Tracking
- **Token Accounting:** Every response returns `prompt_tokens`, `completion_tokens`, and `total_tokens`.
- **Telemetry Latency:** Accurate timing measurement in milliseconds (`latency_ms`) and finish reason capture (`stop`, `length`, `error`).

### 3.10 Feedback Submission
- **Valid Feedback:** Submitting ratings (1-5), categories (e.g., `grammatical_error`, `helpful`), user corrections, and metadata returns HTTP 202 (`ACCEPTED`).
- **Schema Rejection:** Submitting out-of-bounds ratings (e.g., rating > 5 or < 1) returns HTTP 422 (`SCHEMA_VALIDATION_ERROR`).

### 3.11 Consent Enforcement & Privacy Middleware
- **Consent Gate Separation:** 
  - `consent_for_training = True` -> Written to `operational_feedback.jsonl` AND `learning_queue.jsonl`.
  - `consent_for_training = False` -> Written to `operational_feedback.jsonl` ONLY; continuous learning queue is never touched.
- **Candidate Dataset Filtering:** Continuous learning background worker exclusively incorporates records with explicit customer consent.
- **PII Scrubbing:** Anonymizes international emails, GCC/international phone numbers, Saudi National IDs/Iqamas, and UAE Emirates IDs to `[REDACTED_*]` tokens.
- **User Anonymization:** Deterministic SHA-256 one-way hashing with cryptographic salt.

### 3.12 Provider Fallback
- **Automated Fallback:** When the primary provider encounters an error (e.g., simulated failure or network timeout), the runtime automatically dispatches the query to the configured fallback provider and returns a successful response.
- **Unconfigured Fallback:** When no fallback provider is configured, the primary error is returned immediately.

### 3.13 Cloud Environment Configuration
- **Dynamic Configuration Loading:** Validates population of `APIConfig` from environment variables (`CENTRAL_AI_*`, `HOSTED_*`).
- **Containerization Specification:** Validates `Dockerfile` multi-stage build, rootless Python 3.11 runtime, port 8000 exposure, and automated container `HEALTHCHECK`.

---

## 4. Staging Smoke Test Procedure & Gates

The isolated staging smoke test (`tests/staging_smoke_test.py`) verifies 7 critical staging gates before any deployment is approved:

| Staging Gate | Target Component | Acceptance Criteria |
| :--- | :--- | :--- |
| **Gate 1: Infrastructure Health** | GET `/health` | HTTP 200, status `ok`, valid version and provider |
| **Gate 2: Host Readiness** | GET `/ready` | HTTP 200, `ready: true`, disk free > 15 GB, lock idle |
| **Gate 3: Security & Auth** | POST `/api/v1/chat` | 401 when unauthenticated, 200 when authenticated |
| **Gate 4: Domain Prompts** | Tutor, Speaking, Exams | HTTP 200, non-empty Arabic content, sub-100ms mock latency |
| **Gate 5: Safety Interlocks** | Malformed JSON & Reasoning | HTTP 400 for bad JSON, HTTP 500 `MODEL_REASONING_ONLY` |
| **Gate 6: Rate Limiting** | Response Headers | Valid `X-RateLimit-Limit` and `X-RateLimit-Remaining` |
| **Gate 7: Operational Feedback** | POST `/api/v1/feedback` | HTTP 202, consent properly recorded and enforced |

---

## 5. Repeatable Test Commands

All test procedures are 100% automated and repeatable. They run using the local Python 3.11 virtual environment without modifying production systems or using production credentials:

```bash
# 1. Execute the Full Automated QA Test Suite (36 Tests)
.venv/bin/python -m unittest tests/test_qa_suite.py

# 2. Execute the Integration Regression Test Suite (17 Tests)
.venv/bin/python -m unittest tests/test_central_api.py

# 3. Execute the Isolated Staging Smoke Test (7 Gates)
.venv/bin/python tests/staging_smoke_test.py

# 4. Execute the Standalone Automated Health-Check Script
.venv/bin/python central_runtime_api/health_check.py --url http://127.0.0.1:9010

# 5. Run the Unified QA Suite & Generate Machine-Readable Report
.venv/bin/python scripts/run_qa_suite.py --output reports/BETA_V001_API_QA_RESULTS.json
```

---

## 6. Staging Deployment Verification Checklist

This checklist must be executed on any newly provisioned staging or production environment prior to customer traffic redirection:

- [ ] **1. Cloud Compute Provisioning:**
  - [ ] Stateless API container deployed on GCP Cloud Run or AWS ECS Fargate.
  - [ ] Minimum 1 instance running; max auto-scale ceiling configured (e.g. 5 instances for beta).
  - [ ] Container CPU: 1 vCPU; Memory: 1 GiB.
- [ ] **2. Environment Variables & Secrets Injected:**
  - [ ] `CENTRAL_AI_PROVIDER` set to target engine (`hosted` or `mock`).
  - [ ] `CENTRAL_AI_API_KEY` injected via Secret Manager (never in plaintext).
  - [ ] `HOSTED_ENDPOINT` and `HOSTED_API_KEY` injected if using hosted inference.
  - [ ] `CENTRAL_AI_RATE_LIMIT_RPM` configured to 60.
- [ ] **3. Network & Edge Security:**
  - [ ] TLS 1.3 enforced at Cloudflare / CloudFront edge.
  - [ ] CORS headers restricted to authorized Peregrine client origins.
  - [ ] Request body size limit enforced at 2 MB.
- [ ] **4. Liveness & Readiness Probing:**
  - [ ] Orchestrator liveness probe configured to `GET /health` (interval: 10s, timeout: 3s).
  - [ ] Orchestrator readiness probe configured to `GET /ready` (interval: 10s, timeout: 3s).
- [ ] **5. Live Smoke-Test Execution:**
  - [ ] Execute `tests/staging_smoke_test.py --url https://<staging-domain> --api-key <staging-key>`.
  - [ ] Verify all 7 staging gates report `[✔ PASS]`.
- [ ] **6. Governance & Feedback Verification:**
  - [ ] Ephemeral scratch directory mounted with 24-hour retention.
  - [ ] Unconsented feedback test record confirmed absent from continuous learning queue.
  - [ ] CloudWatch / Cloud Logging audit stream confirmed active.
