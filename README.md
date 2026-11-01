# Peregrine Central AI Runtime & Arabic NLP Core Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Architecture: ASGI](https://img.shields.io/badge/architecture-ASGI%20%2F%20HTTP-green.svg)]()
[![Container Ready](https://img.shields.io/badge/container-Docker%20Rootless-orange.svg)]()
[![Status: Beta V-001](https://img.shields.io/badge/release-Beta%20V--001-purple.svg)]()

Canonical unified AI runtime backend, multi-agent generation (MAG) pipeline, and Arabic linguistic intelligence engine for the **Peregrine Arabic AI** ecosystem.

---

## 1. System Architecture Overview

Peregrine Central AI serves as the singular authoritative intelligence gateway powering all Peregrine client surfaces:
- **Peregrine Arabic Digital Reader & Spoken Arabic Reader**
- **AI Speaking Partner (Rashid & Maryam — Emirati & Modern Standard Arabic)**
- **Arabic AI Tutor (Grammar, Morphology, Syntactic Analysis)**
- **Exams App & LMS Assessment Engine**
- **Academic Research Assistant**

```
                     ┌─────────────────────────────────────────────────────────┐
                     │               Peregrine Client Applications             │
                     │  (Next.js Web / Mobile Apps / LMS / Exams App / Reader) │
                     └────────────────────────────┬────────────────────────────┘
                                                  │ HTTPS / JSON API
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │            Peregrine Central AI Runtime Engine          │
                     │          (High-Performance Python ASGI / Uvicorn)       │
                     ├─────────────────────────────────────────────────────────┤
                     │  Middleware:                                            │
                     │   • Privacy Anonymizer & Consent Stripper               │
                     │   • Token Bucket / RPM Rate Limiter                     │
                     │   • Storage Safety Guard (Disk Free Threshold Check)    │
                     ├─────────────────────────────────────────────────────────┤
                     │  Service Router & Dispatch:                             │
                     │   • /api/v1/chat              • /api/v1/speaking/respond│
                     │   • /api/v1/tutor/explain     • /api/v1/exams/explain   │
                     │   • /api/v1/feedback          • /health, /ready         │
                     └───────┬──────────────────┬───────────────────┬──────────┘
                             │                  │                   │
             ┌───────────────▼──┐       ┌───────▼──────────┐ ┌──────▼──────────────┐
             │  Knowledge Core  │       │ Provider Manager │ │ Continuous Learning │
             │  • Arabic RAG    │       │  & Adapters      │ │ • Feedback Store    │
             │  • Arabic MAG    │       │  • Hosted (Groq) │ │ • Anonymized Queue  │
             │  • Vector Store  │       │  • MLX (Jais)    │ │ • Candidate Dataset │
             │  • Morph/Stemmer │       │  • Ollama (Qwen) │ │   Generator Worker  │
             └──────────────────┘       │  • Mock Fallback │ └─────────────────────┘
                                        └──────────────────┘
```

---

## 2. Repository Layout

```
peregrine-central-ai/
├── central_runtime_api/           # The canonical Central AI Runtime ASGI/HTTP API server
│   ├── adapters/                  # Model adapters: Base, Hosted (Groq/OpenAI), Ollama, MLX Jais, Mock
│   │   ├── base.py
│   │   ├── hosted_adapter.py      # OpenAI-compatible / Groq Llama 3.3 70B adapter
│   │   ├── mlx_adapter.py         # Apple Silicon MLX local inference adapter
│   │   ├── mock_adapter.py        # Zero-credential test & fallback adapter
│   │   └── ollama_adapter.py      # Local Ollama runner adapter
│   ├── middleware/                # Security & operational middleware
│   │   ├── privacy.py             # PII masking & GDPR/privacy consent enforcer
│   │   └── rate_limiter.py        # Token-bucket sliding window rate limiter
│   ├── services/                  # Business logic services
│   │   ├── feedback_store.py      # User feedback & consent database
│   │   ├── provider_manager.py    # Active/fallback inference provider router
│   │   └── router.py              # Endpoint request validation & handlers
│   ├── workers/                   # Background tasks
│   │   └── feedback_worker.py     # Asynchronous continuous learning aggregation worker
│   ├── asgi.py                    # Production ASGI application entrypoint
│   ├── server.py                  # Standalone HTTP server & handler
│   ├── config.py                  # Central configuration & disk guard
│   ├── schemas.py                 # Pydantic request/response data models
│   ├── health_check.py            # Detailed diagnostic health checker
│   ├── run.py                     # CLI launcher
│   └── test_api.py                # In-process API integration tests
├── knowledge_core/                # Arabic RAG, MAG, and NLP core engine
│   ├── arabic_mag.py              # Multi-Agent Generator (Arabic dialect & grammar specialist)
│   ├── arabic_nlp.py              # Arabic NLP pre/post-processing & normalization
│   ├── arabic_rag.py              # Retrieval Augmented Generation engine
│   ├── embeddings.py              # Text embedding generation (Deterministic & Provider)
│   └── vector_store.py            # Vector similarity store with category filtering
├── specialist_tools/              # Specialist Arabic NLP tools & services
│   ├── pyarud_service.py          # Prosody & poetic meter analyzer service
│   ├── test_pyarud_service.py
│   ├── test_camel_tools.py
│   ├── test_mishkal.py
│   ├── test_pyarabic.py
│   ├── test_qalsadi.py
│   ├── test_qutrub.py
│   ├── verify_pyarud_full.py
│   └── run_all_nlp_tests.py
├── reference/                     # Historical / reference implementations
│   └── khaliji-chat.js            # Battle-tested Speaking Partner Vercel serverless function (Groq/Whisper)
├── tests/                         # Complete test suite
│   ├── test_central_api.py        # HTTP server & runtime integration tests
│   ├── test_rag_mag.py            # Arabic RAG/MAG linguistic intelligence tests
│   ├── test_arabic_specialist_deterministic.py  # Deterministic Arabic NLP tests
│   ├── test_cloud_container_readiness.py        # ASGI container readiness tests
│   ├── test_qa_suite.py           # Comprehensive QA test harness
│   ├── test_runners.py            # Test orchestration runner
│   └── staging_smoke_test.py      # Staging environment smoke tests
├── docs/                          # Architecture specs, capability matrices, deployment guides
│   ├── EXISTING_AI_CAPABILITY_INVENTORY.md
│   ├── BETA_V001_CENTRAL_AI_API.md
│   ├── BETA_V001_CENTRAL_API_DEPLOYMENT_READINESS.md
│   ├── BETA_V001_CLOUD_HOSTING_ARCHITECTURE.md
│   ├── BETA_V001_CLOUDFLARE_GATEWAY_SECURITY_AUDIT.md
│   ├── BETA_V001_SPEAKING_PARTNER_DESIGN.md
│   ├── BETA_V001_API_QA_PLAN.md
│   ├── BETA_V001_API_QA_RESULTS.md
│   ├── BETA_V001_ARABIC_CAPABILITY_MATRIX.md
│   ├── BETA_V001_ARABIC_DATA_SCHEMA.md
│   ├── BETA_V001_ARABIC_LEARNING_PIPELINE.md
│   ├── BETA_V001_CLOUD_INTEGRATION_TEST_PLAN.md
│   ├── BETA_V001_DEPLOYMENT_RUNBOOK.md
│   ├── BETA_V001_FINAL_FREE_DEMO_ARCHITECTURE.md
│   ├── BETA_V001_MODEL_PROVIDER_STATUS.md
│   ├── BETA_V001_ZERO_COST_BETA_IMPLEMENTATION_PLAN.md
│   ├── BETA_V001_ZERO_COST_DEPLOYMENT_RECOMMENDATION.md
│   ├── CENTRAL_API_CLOUD_DEPLOYMENT_AUDIT.md
│   └── CLOUDFLARE_WORKER_CENTRAL_API_COMPATIBILITY.md
├── Dockerfile                     # Cloud container deployment Dockerfile
├── docker-compose.yml             # Local / staging docker-compose definition
├── requirements.txt               # Base Python requirements (Fast, zero-heavy-deps)
├── requirements-specialist.txt    # Specialist Arabic NLP requirements (PyArabic, Mishkal, Qalsadi, etc.)
└── .env.example                   # Sanitized environment template (no real keys)
```

---

## 3. Core API Endpoints

All responses conform to the unified `CentralAPIResponse` schema:

| Endpoint | Method | Purpose | Key Parameters |
|---|---|---|---|
| `/health` | `GET` | Container liveness check | None |
| `/ready` | `GET` | Readiness & storage capacity check | None |
| `/api/v1/chat` | `POST` | General Arabic conversational assistant | `messages`, `parameters`, `user_id` |
| `/api/v1/tutor/explain` | `POST` | Grammar, I'rab, morphology, syntax explanation | `concept_or_text`, `level`, `focus_area` |
| `/api/v1/speaking/respond`| `POST` | Speaking Partner (Rashid/Maryam, Emirati/MSA) | `user_utterance`, `scenario`, `dialect`, `history` |
| `/api/v1/exams/explain` | `POST` | Assessment distracter & rationale analysis | `question`, `options`, `correct_answer`, `user_answer` |
| `/api/v1/feedback` | `POST` | User feedback & opt-in continuous learning data | `category`, `rating`, `user_consent` |
| `/api/v1/feedback/consent/withdraw` | `POST` | Instant user data purge & consent withdrawal | `user_id` |

### Sample Response Contract
```json
{
  "content": "مرحباً بك! أنا راشد، شريكك في التدرب على اللهجة الإماراتية...",
  "model": "llama-3.3-70b-versatile",
  "provider": "hosted",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 124,
    "completion_tokens": 58,
    "total_tokens": 182
  },
  "latency_ms": 312.4,
  "request_id": "req-9b8c2d1e-7f4a",
  "metadata": {
    "dialect": "emirati",
    "persona": "rashid"
  }
}
```

---

## 4. Inference Providers & Fallback Hierarchy

Peregrine Central AI uses a decoupled provider architecture:

1. **`hosted` (Primary Cloud Provider)**:
   - High-throughput OpenAI-compatible endpoint (Groq Llama 3.3 70B, vLLM, RunPod).
   - Low latency (~300–600ms) for real-time Speaking Partner dialogues.
2. **`mlx_jais` (Apple Silicon Hardware Acceleration)**:
   - Optimized for local development and private on-premise execution using Apple Metal Performance Shaders.
3. **`ollama` (Local Model Runner)**:
   - Local CPU/GPU fallback running Qwen 2.5 / 3.
4. **`mock` (Deterministic Zero-Cost Engine)**:
   - Provides deterministic, syntactically valid Arabic responses for automated CI/CD testing, integration verification, and zero-cost local sandboxing without external credentials.

Automatic fallback kicks in seamlessly when the primary provider encounters network partition, rate limits, or timeout thresholds.

---

## 5. Quickstart & Local Execution

### Prerequisites
- Python 3.11+
- pip

### 1. Install Dependencies
```bash
# Core API dependencies
pip install -r requirements.txt

# (Optional) Specialist Arabic NLP toolchain
pip install -r requirements-specialist.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your specific provider settings
```

### 3. Launch Server
```bash
# Using ASGI (Uvicorn - recommended for production)
python3 -m central_runtime_api.run --server asgi --host 0.0.0.0 --port 8000

# Or using built-in standalone HTTP server
python3 -m central_runtime_api.run --server http --host 0.0.0.0 --port 8000
```

### 4. Verify Health & Readiness
```bash
curl -s http://127.0.0.1:8000/health | jq .
curl -s http://127.0.0.1:8000/ready | jq .
```

---

## 6. Docker Container Deployment

The repository includes an enterprise-ready, rootless, multi-stage Docker build:

### Build Container
```bash
docker build -t peregrine-central-ai:latest .
```

### Run Container
```bash
docker run -d \
  --name peregrine-central-ai \
  -p 8000:8000 \
  -e CENTRAL_AI_PROVIDER=mock \
  -e CENTRAL_AI_ENV=production \
  -v peregrine_ai_data:/app/data \
  peregrine-central-ai:latest
```

### Run with Docker Compose
```bash
docker-compose up -d
docker-compose logs -f central-ai-api
```

---

## 7. Running the Test Suites

All tests are designed to execute reproducibly without requiring live credentials:

```bash
# 1. Cloud Container Readiness & ASGI In-Memory Suite (15 tests)
python3 -m unittest tests/test_cloud_container_readiness.py

# 2. Runtime API Socket & HTTP Lifecycle Suite (17 tests)
CENTRAL_AI_ENFORCE_DISK_LIMIT=false python3 -m unittest tests/test_central_api.py

# 3. Arabic RAG, MAG, & Vector Store Suite (15 tests)
CENTRAL_AI_ENFORCE_DISK_LIMIT=false python3 -m unittest tests/test_rag_mag.py

# 4. Specialist Arabic NLP Deterministic Suite
python3 -m unittest tests/test_arabic_specialist_deterministic.py
```

---

## 8. Security & Data Protection Guarantees

- **Zero Hardcoded Secrets**: All credentials and API keys are injected strictly via environment variables.
- **GDPR & Privacy Compliance**:
  - PII (emails, phone numbers, identifiers) is automatically masked by `central_runtime_api/middleware/privacy.py`.
  - Continuous learning ingestion is strictly opt-in (`user_consent: true`).
  - `POST /api/v1/feedback/consent/withdraw` guarantees atomic removal of user contributions from learning queues.
- **Rootless Container Execution**: The production Docker image runs as an unprivileged service user (`appuser: UID 10001`).
- **Disk Saturation Guard**: Storage safety thresholds prevent unmonitored disk exhaustion in high-concurrency environments.

---

## 9. License

Proprietary and Confidential.  
Copyright © 2026 Peregrine Academy / Peregrine Hub. All rights reserved.
