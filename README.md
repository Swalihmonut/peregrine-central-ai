# Peregrine Central AI Backend (`peregrine-central-ai`)

**Repository:** `https://github.com/Swalihmonut/peregrine-central-ai`  
**Target Hostname:** `api.ai.peregrineacademy.in`  
**Runtime:** Python 3.11 (Rootless ASGI 3.0 / Uvicorn / Standard Library BaseHTTP)  
**Container:** Docker multi-stage rootless container (`appuser`: UID 10001)  
**Status:** Beta V-001 Verified Staging Readiness (`DEPLOYMENT CONDITIONALLY VERIFIED`)

---

## 1. Overview & Mission

`peregrine-central-ai` is the centralized AI runtime API and intelligence routing engine for the **Peregrine Arabic AI** ecosystem. It acts as the unified backend brain serving:

1. **Arabic Digital Reader (`arabic.peregrineacademy.in`):** Interactive AI Tutor dialogue (Rashid & Maryam), curriculum RAG, and pronunciation error tracking.
2. **Peregrine Arabic AI Web Platform (`ai.peregrineacademy.in`):** Research Notebooks, Nahw/Sarf grammar analysis, Balagha rhetoric, and dialect studies.
3. **AI Speaking Partner:** Roleplay conversation practice in authentic Emirati, Levantine, Egyptian, and Modern Standard Arabic.
4. **Examination & Assessment Assistant:** Step-by-step exam question explanation, distractor justification, and rubric grading.

```
       ┌──────────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
       │   Arabic Digital Reader  │    │   Research Web App (MVP) │    │  Exams & Assessment App  │
       │ arabic.peregrineacademy  │    │   ai.peregrineacademy    │    │  exams.peregrineacademy  │
       └────────────┬─────────────┘    └────────────┬─────────────┘    └────────────┬─────────────┘
                    │                               │                               │
                    └───────────────────────┬───────┴───────────────────────────────┘
                                            │ HTTPS (Bearer Token / x-request-id)
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │    Cloudflare Gateway Worker (Edge)     │
                       │       api.ai.peregrineacademy.in        │
                       │    (25s Shield / 60 RPM Rate Limit)     │
                       └────────────────────┬────────────────────┘
                                            │
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │     Peregrine Central AI API Runtime    │
                       │          (Koyeb / Cloud Run)            │
                       │   ASGI 3.0 App / Pure Python 3.11       │
                       └────────────────────┬────────────────────┘
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
  ┌────────────────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
  │   Cloud Remote LLMs    │   │ Local Model Adapters   │   │ In-Memory Knowledge    │
  │   - Groq (LPU Whisper) │   │ - Ollama (Qwen 3:4B)   │   │ - Arabic RAG Engine    │
  │   - Hosted Allam 2:7B  │   │ - Apple Silicon MLX    │   │ - Student MAG Memory   │
  │   - DeepSeek / OpenAI  │   │ - Deterministic Mock   │   │ - Morphological NLP    │
  └────────────────────────┘   └────────────────────────┘   └────────────────────────┘
```

---

## 2. Key Architecture & Features

### A. Zero-Dependency High-Throughput ASGI 3.0 Engine
- Implemented as a native ASGI 3.0 application in [`central_runtime_api/asgi.py`](central_runtime_api/asgi.py) with full lifespan protocol (`lifespan.startup`, `lifespan.shutdown`).
- Benchmarked under concurrency: **36.97 MB RAM** under 100 concurrent requests (ideal for zero-cost 512 MB hosting like Koyeb Nano).
- Fallback standalone HTTP server in [`central_runtime_api/server.py`](central_runtime_api/server.py) using standard Python library (`http.server.ThreadingHTTPServer`).

### B. Resilient Provider & Fallback Architecture
- **Hosted Adapter:** OpenAI-compatible remote provider for Groq, DeepSeek, vLLM, or hosted Allam.
- **Ollama Adapter:** Local inference with strict `<think>` tag reasoning trace isolation.
- **MLX Jais Adapter:** Apple Silicon hardware-accelerated Arabic bilingual model execution.
- **Mock Adapter:** Offline, deterministic testing adapter that simulates realistic latency and outputs with zero GPU usage or external network dependencies.
- **Sequential Concurrency Lock & Provider Fallback:** Protects small memory instances from crashing while automatically routing to the fallback engine if the primary fails.

### C. Knowledge Core: In-Memory Arabic RAG & MAG
- **Arabic RAG (`knowledge_core/arabic_rag.py`):** BM25 exact and semantic retriever with citation verification and diacritic invariance.
- **Arabic MAG (`knowledge_core/arabic_mag.py`):** Spaced-repetition Student Memory Graph tracking pronunciation errors, mastery graduation, and rolling turns.
- **Morphological NLP (`knowledge_core/arabic_nlp.py`):** Diacritics stripping, Alef/Teh Marbuta normalization, and morphological stem lookup.

### D. Security, Privacy & Consent
- **Timing-Safe Auth:** Authorization tokens verified using `hmac.compare_digest`.
- **DoS Guard:** Enforced request body limits (`CENTRAL_AI_MAX_BODY_BYTES`, default 2 MB).
- **Exact CORS Matching:** Prevents wildcard CORS leaks in production.
- **PII Redaction & Anonymization:** In-flight stripping of email, phone, and civil IDs; deterministic SHA-256 user hashing.
- **GDPR Consent Withdrawal:** `/api/v1/feedback/consent/withdraw` endpoint purges all candidate and training records for the given student hash.

---

## 3. API Endpoints Reference

All inference and feedback endpoints require `Authorization: Bearer <CENTRAL_AI_API_KEY>` in staging/production.

| Method | Endpoint | Description | Auth Required? |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Liveness probe reporting version, active provider, and model | No |
| `GET` | `/ready` | Readiness probe checking disk space, memory, and feedback queue | No |
| `POST` | `/api/v1/chat` | General-purpose multi-turn chat completion | **Yes** |
| `POST` | `/api/v1/tutor/explain` | Specialized Arabic grammar, morphology, or rhetoric explanation | **Yes** |
| `POST` | `/api/v1/speaking/respond` | Authentic dialect dialogue partner (Rashid & Maryam) | **Yes** |
| `POST` | `/api/v1/exams/explain` | Assessment analysis, correct answer justification, distractor review | **Yes** |
| `POST` | `/api/v1/feedback` | Continuous learning telemetry & user feedback logging | **Yes** |
| `POST` | `/api/v1/feedback/consent/withdraw` | Immediate user consent withdrawal and data purge | **Yes** |

---

## 4. Repository Structure

```text
peregrine-central-ai/
├── central_runtime_api/          # Core Central AI runtime application package
│   ├── adapters/                 # Model provider adapters (hosted, ollama, mlx, mock)
│   ├── middleware/               # Rate limiting, PII sanitization, user anonymization
│   ├── services/                 # Provider manager, router, continuous learning store
│   ├── workers/                  # Background feedback ingestion & queue flusher
│   ├── asgi.py                   # Pure ASGI 3.0 application entrypoint
│   ├── config.py                 # Configuration loader & environment variables
│   ├── health_check.py           # Automated health check CLI probe script
│   ├── run.py                    # Server launcher supporting ASGI / uvicorn / http
│   ├── schemas.py                # Pydantic / dataclass request & response contracts
│   ├── server.py                 # Standalone BaseHTTPRequestHandler server
│   └── test_api.py               # Package-level unit tests
├── knowledge_core/               # Arabic RAG, MAG, and NLP modules
│   ├── arabic_mag.py             # Memory Augmented Generation (student error graph)
│   ├── arabic_nlp.py             # Text normalization, diacritics stripping, stemming
│   ├── arabic_rag.py             # Retrieval Augmented Generation & heritage corpus
│   ├── embeddings.py             # Deterministic & provider embedding interfaces
│   └── vector_store.py           # In-memory cosine similarity vector index
├── specialist_tools/             # Arabic specialist services (PyArud prosody, NLP)
│   ├── pyarud_service.py         # Subprocess wrapper for Arabic poetic meter/rhyme
│   └── test_*.py                 # Specialist linguistic regression tests
├── benchmarks/                   # Audit benchmark specifications & schemas
├── tests/                        # Automated QA and readiness test suites
│   ├── test_cloud_container_readiness.py  # 15 container readiness & CORS tests
│   ├── test_qa_suite.py                   # 36 comprehensive QA mission tests
│   ├── test_central_api.py                # 17 API endpoint unit tests
│   ├── test_rag_mag.py                    # 15 RAG & MAG infrastructure tests
│   ├── staging_smoke_test.py              # 7 staging deployment smoke gates
│   └── test_runners.py                    # 13 benchmark runner verification tests
├── scripts/                      # Operational automation scripts
│   ├── health_check.py           # Standalone HTTP probe
│   ├── run_qa_suite.py           # QA suite runner
│   └── run_staging_smoke_test.py # Smoke test runner
├── sdk/                          # Client SDKs for frontend integration
│   └── ts/central-api-client.ts  # TypeScript client adapter for Next.js & Reader
├── docs/                         # Architecture specifications, runbooks, and audits
├── Dockerfile                    # Production rootless multi-stage Dockerfile
├── docker-compose.yml            # Local & staging container composition
├── requirements.txt              # Production Python dependencies
├── .env.example                  # Sanitized environment configuration template
├── .gitignore                    # Git exclusions (no secrets, venvs, or databases)
└── README.md                     # Master documentation
```

---

## 5. Local Setup & Testing

### Prerequisites
- Python 3.11+
- Virtual environment recommended

### Installation
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Tests
All test suites can be executed offline in mock mode without paid credentials:

```bash
# 1. Cloud Container & ASGI Readiness (15 tests)
python3 -m unittest tests/test_cloud_container_readiness.py

# 2. Knowledge Core RAG & MAG Infrastructure (15 tests)
python3 -m unittest tests/test_rag_mag.py

# 3. Benchmark Runners Verification (13 tests)
python3 -m unittest tests/test_runners.py

# 4. Comprehensive QA Mission Suite (36 tests)
python3 -m unittest tests/test_qa_suite.py
```

### Running the API Server Locally
```bash
# Launch with high-performance ASGI server (uvicorn)
python3 -m central_runtime_api.run --host 0.0.0.0 --port 8000 --server asgi

# Or launch with native standard library server
python3 -m central_runtime_api.run --host 0.0.0.0 --port 8000 --server http
```

### Probing the Health Endpoint
```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
```

---

## 6. Docker & Container Deployment

### Build Container
```bash
docker build -t peregrine-central-ai:latest .
```

### Run with Docker Compose
```bash
docker compose up -d
```

### Cloud Run / Koyeb Notes
- **Ephemeral SSD Caution:** On hosting platforms with small root disks (e.g. Koyeb 2 GB SSD), set `CENTRAL_AI_MIN_DISK_FREE_GB=0.5` in the environment to avoid triggering the default 15 GB safety abort.
- **Port:** The container listens on port `8000` by default. Override via `CENTRAL_AI_PORT` or `PORT`.

---

## 7. Security & Credentials Policy

* **Strictly Zero Secrets:** No API keys, passwords, database URLs, or private tokens are stored in this repository.
* **Environment Variables:** All secrets are injected at runtime via environment variables (see [`.env.example`](.env.example)).
* **Timing-Safe Auth:** Endpoint access uses constant-time string comparisons to prevent timing attacks.
* **PII Anonymization:** Student identifiers are salted and hashed with SHA-256 before telemetry storage.

---
*Maintained by the Peregrine Arabic AI Infrastructure & Backend Engineering Team.*
