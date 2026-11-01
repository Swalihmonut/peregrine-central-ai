# Central Arabic AI Runtime & API Specification — Beta V-001

**Document Version:** 1.0.0 (Beta V-001)  
**Role:** Agent 2 — Local AI Runtime and API Engineer  
**Workspace:** `/Users/muhammedswaliht/peregrine-arabic-ai-lab`  
**Package Location:** `/Users/muhammedswaliht/peregrine-arabic-ai-lab/central_runtime_api`  
**Host Architecture:** Apple Silicon M4 (10 Cores, 32 GB Unified Memory, macOS 27.0.1)  
**Status:** IMPLEMENTED & TESTED (Mock test suite: 11/11 Passed; Zero external package installations)

---

## 1. Executive Summary & Design Philosophy

The priority for **Beta V-001** is delivering a **working, dependable, shared Arabic AI service** across the application ecosystem rather than attempting to achieve a perfect single-model benchmark. 

The Central AI Runtime provides a unified, provider-independent HTTP interface designed to power:
- **Arabic AI Tutor:** Syntactic parsing (`إعراب`), morphological analysis (`صرف`), and grammatical rule explanations.
- **AI Speaking Partner:** Conversational dialogue, interactive turn-taking, and pronunciation/vocabulary support in MSA and Arabic dialects.
- **Exams App:** Question analysis, validation of correct options, and distractor refutation.
- **Research Assistant & Learning Applications:** General Arabic inquiry and structured knowledge synthesis.

### Key Architectural Tenets:
1. **Provider Independence:** Application clients interact with a uniform API contract. The underlying engine can seamlessly switch between **Mock** (offline testing), **Ollama** (`qwen3:4b`), **MLX** (`IFM/Jais-3-3.7B-MLX-4bit`), or **Hosted Models** (e.g. HUMAIN Node / vLLM / OpenAI) without requiring client code changes.
2. **Zero Reasoning Contamination:** In reasoning models like Qwen 3, chain-of-thought tokens are captured internally but **never exposed** to downstream applications. If the model exhausts its token budget within the thinking phase, the service returns a clear `MODEL_REASONING_ONLY` error rather than dumping raw English thinking scratchpads.
3. **Sequential Execution & Resource Protection:** To prevent memory exhaustion and disk swap expansion against the 23 GiB available disk headroom, all model calls are serialized through a thread-safe lock (`threading.Lock()`). Ollama and MLX are **never loaded concurrently**.
4. **Zero-Dependency Core:** Built using Python's native `http.server.ThreadingHTTPServer` alongside existing virtual environment packages (`pydantic==2.14.2`, `requests==2.34.2`, `httpx==0.28.1`), requiring zero new third-party installations.

---

## 2. System Architecture & Topology

```
+-----------------------------------------------------------------------------------+
|                           Peregrine Application Ecosystem                         |
|   [ Arabic AI Tutor ]   [ AI Speaking Partner ]   [ Exams App ]   [ Research ]   |
+-----------------------------------------+-----------------------------------------+
                                          |
                              HTTP / JSON (REST API)
                                          |
+-----------------------------------------v-----------------------------------------+
|                  Central AI Runtime API (central_runtime_api)                     |
|                                                                                   |
|  [ Endpoints ]                                                                    |
|    GET  /health              GET  /ready                                          |
|    POST /api/v1/chat         POST /api/v1/tutor/explain                           |
|    POST /api/v1/speaking     POST /api/v1/exams/explain                           |
|                                                                                   |
|  [ Middleware & Router ]                                                          |
|    - Request ID Propagation (X-Request-ID)                                        |
|    - Pydantic Schema Validation & Standardized Error Envelopes                    |
|    - Domain-Specific System Prompt Synthesis                                      |
|    - Sequential Hardware Execution Lock (threading.Lock)                          |
|    - Hard Disk Safety Interlock (Aborts if disk < 15 GB)                          |
+-----------------------------------------+-----------------------------------------+
                                          |
                 Provider-Independent Abstract Adapter Interface
                                          |
         +-----------------+--------------+-----------------+-----------------+
         |                 |                                |                 |
         v                 v                                v                 v
   [ Mock Adapter ]  [ Ollama Adapter ]             [ MLX Adapter ]   [ Hosted Adapter ]
   (Offline / CI)    (qwen3:4b @ :11434)            (Jais 3 @ :8080)  (Future Remote API)
   - Zero GPU use    - Stream parsing               - OpenAI compat   - HUMAIN Node
   - Sub-15ms        - Strict thinking isolation    - Delimiter strip - OpenAI / vLLM
   - 100% testable   - done_reason capture          - finish_reason   - Configured key
```

---

## 3. API Specification & Endpoints

### 3.1 Infrastructure Endpoints

#### `GET /health`
Returns high-level service health and runtime identity.

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "version": "0.1.0-beta",
  "active_provider": "mock",
  "active_model": "qwen3:4b",
  "timestamp": "2026-10-31T07:45:30.102345+00:00"
}
```

---

#### `GET /ready`
Verifies whether the runtime environment, active provider, and host resources are ready to accept inference requests.

**Response (`200 OK`):**
```json
{
  "ready": true,
  "active_provider": "mock",
  "active_model": "qwen3:4b",
  "provider_status": "ready",
  "disk_free_gb": 23.45,
  "memory_free_pct": 77.0,
  "sequential_lock_idle": true,
  "timestamp": "2026-10-31T07:45:30.113201+00:00"
}
```

---

### 3.2 Domain Application Endpoints

All `POST` endpoints accept structured JSON, generate or propagate `request_id`, and return a standardized `CentralAPIResponse` envelope.

#### A. General Chat: `POST /api/v1/chat`
General bilingual conversation supporting multi-turn dialogues.

**Request Schema:**
```json
{
  "request_id": "req-custom-1234",
  "messages": [
    {"role": "system", "content": "You are a helpful Arabic research assistant."},
    {"role": "user", "content": "ما الفرق بين النحو والصرف؟"}
  ],
  "parameters": {
    "temperature": 0.2,
    "max_tokens": 1024,
    "top_p": 0.95
  }
}
```

---

#### B. Arabic AI Tutor: `POST /api/v1/tutor/explain`
Specialized for grammatical, morphological, and rhetorical instruction.

**Request Schema:**
```json
{
  "query": "أعرب الجملة التالية إعراباً مفصلاً: إن العلم نور.",
  "level": "intermediate",
  "topic": "nahw",
  "parameters": {
    "temperature": 0.2,
    "max_tokens": 1024
  }
}
```

**Response (`200 OK`):**
```json
{
  "request_id": "tutor-8a7b9c1d2e3f",
  "status": "success",
  "content": "الإعراب المفصل:\n- «إنَّ»: حرف توكيد ونصب مبني على الفتح لا محل له من الإعراب.\n- «العلمَ»: اسم إنّ منصوب وعلامة نصبه الفتحة الظاهرة على آخره.\n- «نورٌ»: خبر إنّ مرفوع وعلامة رفعه الضمة الظاهرة على آخره.\nالقاعدة النحوية: تدخل (إنّ) وأخواتها على الجملة الاسمية فتنصب المبتدأ ويسمى اسمها، وترفع الخبر ويسمى خبرها.",
  "model": "qwen3:4b",
  "provider": "mock",
  "usage": {
    "prompt_tokens": 84,
    "completion_tokens": 112,
    "total_tokens": 196
  },
  "telemetry": {
    "latency_ms": 14.85,
    "finish_reason": "stop",
    "is_truncated": false
  },
  "error": null,
  "timestamp": "2026-10-31T07:45:30.118940+00:00"
}
```

---

#### C. AI Speaking Partner: `POST /api/v1/speaking/respond`
Interactive conversational partner with support for daily scenarios, pronunciation hints, and dialectal modes.

**Request Schema:**
```json
{
  "user_utterance": "السلام عليكم، كيف حالك اليوم؟",
  "scenario": "daily_conversation",
  "dialect": "msa",
  "dialogue_history": [],
  "parameters": {
    "temperature": 0.3,
    "max_tokens": 512
  }
}
```

---

#### D. Exams App: `POST /api/v1/exams/explain`
Automated pedagogical exam tutor providing correct answer rationale and distractor refutation.

**Request Schema:**
```json
{
  "question_text": "ما علامة إعراب الفاعل في جملة: «حضر المعلمون»؟",
  "options": ["الضمة", "الواو", "الألف", "الفتحة"],
  "correct_answer": "الواو",
  "student_answer": "الضمة",
  "parameters": {
    "temperature": 0.2,
    "max_tokens": 1024
  }
}
```

---

## 4. Error Handling & Safety Protocols

### 4.1 Standardized Error Envelope
When any error occurs (HTTP 400, 404, 422, or 500), the service returns a standard structured JSON envelope:

```json
{
  "request_id": "req-error-id",
  "status": "error",
  "content": null,
  "model": "qwen3:4b",
  "provider": "ollama",
  "usage": {
    "prompt_tokens": 116,
    "completion_tokens": 512,
    "total_tokens": 628
  },
  "telemetry": {
    "latency_ms": 38400.5,
    "finish_reason": "length",
    "is_truncated": true
  },
  "error": {
    "code": "MODEL_REASONING_ONLY",
    "message": "The model exhausted its token quota inside internal reasoning and generated no final Arabic answer. Thinking traces are withheld for safety.",
    "details": {
      "done_reason": "length",
      "completion_tokens": 512
    }
  },
  "timestamp": "2026-10-31T07:45:30.122410+00:00"
}
```

### 4.2 Error Taxonomy
| Error Code | HTTP Status | Root Cause & Remediation |
| :--- | :---: | :--- |
| `INVALID_JSON` | `400` | Request body could not be decoded as JSON. |
| `EMPTY_REQUEST_BODY` | `400` | POST request body was zero bytes. |
| `ENDPOINT_NOT_FOUND` | `404` | Requested path does not exist on the Central API. |
| `SCHEMA_VALIDATION_ERROR` | `422` | Missing required fields or incorrect data types (Pydantic). |
| `MODEL_REASONING_ONLY` | `500` | Model emitted only thinking tokens and 0 content tokens. Internal reasoning withheld. |
| `DISK_SAFETY_THRESHOLD_BREACHED`| `500` | Available host disk space fell below the 15.0 GB safety threshold. |
| `PROVIDER_CONNECTION_FAILED` | `500` | Ollama daemon at `:11434` is unreachable or stopped. |
| `MLX_SERVER_UNREACHABLE` | `500` | Jais MLX server at `:8080` is not active. |
| `HOSTED_ENDPOINT_NOT_CONFIGURED`| `500` | Hosted provider was selected but endpoint/key is missing. |

---

## 5. Configuration & Provider Replacement

The API is fully configurable through environment variables, requiring zero code modifications to change providers:

| Environment Variable | Default Value | Description / Permitted Values |
| :--- | :---: | :--- |
| `CENTRAL_AI_PROVIDER` | `mock` | `mock`, `ollama`, `mlx_jais`, `hosted` |
| `CENTRAL_AI_MODEL` | `qwen3:4b` | Active model identifier (e.g. `qwen3:4b`, `IFM/Jais-3-3.7B-MLX-4bit`) |
| `CENTRAL_AI_HOST` | `127.0.0.1` | Binding network interface |
| `CENTRAL_AI_PORT` | `8000` | HTTP listening port |
| `CENTRAL_AI_TIMEOUT` | `120.0` | Client timeout in seconds |
| `OLLAMA_ENDPOINT` | `http://127.0.0.1:11434`| Ollama host endpoint |
| `MLX_ENDPOINT` | `http://127.0.0.1:8080/v1` | OpenAI-compatible MLX server endpoint |
| `HOSTED_ENDPOINT` | *(empty)* | Base URL for remote hosted inference (e.g. `https://node.humain.com/v1`) |
| `HOSTED_API_KEY` | *(empty)* | Bearer authentication token for hosted endpoint |

---

## 6. Local Startup & Testing Runbook

### 6.1 Running the Automated Test Suite
The mock test suite verifies all 6 endpoints, error handling, thinking withholding, and request ID propagation offline without requiring model loading:

```bash
# Run Central AI test suite via venv
.venv/bin/python -m unittest central_runtime_api/test_api.py

# Run all test suites across the lab
.venv/bin/python -m unittest tests/test_central_api.py tests/test_runners.py
```

### 6.2 Starting the Central AI Server in Development Mode
```bash
# 1. Start with in-memory Mock Provider (Recommended for local app development)
.venv/bin/python -m central_runtime_api.run --port 8000 --provider mock

# 2. Start with local Ollama Provider (Requires running Ollama daemon)
.venv/bin/python -m central_runtime_api.run --port 8000 --provider ollama --model qwen3:4b

# 3. Start with local Jais MLX Provider (Requires MLX server on port 8080)
.venv/bin/python -m central_runtime_api.run --port 8000 --provider mlx_jais --model IFM/Jais-3-3.7B-MLX-4bit
```

### 6.3 Sample Curl Commands
```bash
# Check Health
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

# Check Readiness
curl -s http://127.0.0.1:8000/ready | python3 -m json.tool

# Query Arabic AI Tutor
curl -s -X POST http://127.0.0.1:8000/api/v1/tutor/explain \
  -H "Content-Type: application/json" \
  -d '{
    "query": "أعرب جملة إن العلم نور",
    "level": "intermediate",
    "topic": "nahw"
  }' | python3 -m json.tool

# Query AI Speaking Partner
curl -s -X POST http://127.0.0.1:8000/api/v1/speaking/respond \
  -H "Content-Type: application/json" \
  -d '{
    "user_utterance": "مرحبا، أود أن أتدرب على التحدث بالعربية الفصحى اليوم.",
    "scenario": "daily_conversation",
    "dialect": "msa"
  }' | python3 -m json.tool
```

---

## 7. Production Qualification & Operational Caveats

> [!WARNING]
> **Local Beta Disclaimer:**  
> The current setup runs on a consumer Apple Silicon MacBook Air M4 with 32 GB unified memory and 23 GiB available disk headroom.  
> 1. **Do not claim local model performance is production-grade:** Local small models (3.7B–4B) have known linguistic limitations (e.g., Qwen's grammatical category hallucinations and Jais's preliminary planning overhead).  
> 2. **Sequential Inference Only:** Concurrent requests are held by the server lock; high-concurrency production deployments require hosted serverless endpoints or dedicated multi-GPU clusters.  
> 3. **Hosted Expansion:** Production scaling should point `HOSTED_ENDPOINT` to an enterprise provider (e.g. HUMAIN Node or hosted vLLM) while retaining the exact same application contracts defined in this specification.
