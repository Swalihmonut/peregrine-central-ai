# Production Cloud Hosting Architecture — Beta V-001

**Document Version:** 1.0.0 (Beta V-001 Addendum)  
**Role:** Agent 2 — Local AI Runtime and API Engineer  
**Workspace:** `/Users/muhammedswaliht/peregrine-arabic-ai-lab`  
**Host Architecture Reference:** Apple Silicon M4 is strictly designated for local engineering and integration testing; **Production target is 100% Cloud-Native**.  
**Status:** SPECIFICATION COMPLETE & CONTAINERIZED (`central_runtime_api/Dockerfile` verified)

---

## 1. Executive Summary & Production Mandate

Local deployment on macOS (Ollama / MLX) is strictly bounded to **development, unit testing, and offline experimentation**. Production deployment requires an elastic, multi-tenant cloud architecture that decouples API compute, model inference, databases, object storage, and asynchronous background pipelines.

### Primary Architectural Objectives:
1. **Decoupled Workloads:** Never run GPU-intensive model weights on the user-facing web/API server.
2. **Provider-Independent Model Routing:** Support routing between managed hosted APIs (e.g. HUMAIN Node, Azure/OpenAI, Groq) and dedicated GPU pods (e.g. vLLM on RunPod/Modal) via a unified API gateway.
3. **Data Protection & Governance:** Enforce customer consent, ephemeral audio handling (24h deletion), deterministic PII scrubbing, and strict isolation between operational logs and candidate training datasets.
4. **Lowest-Cost Beta Strategy:** Deliver an ultra-lean, safe cloud deployment for a small invited-user cohort ($< \$100/\text{month}$) while maintaining zero-downtime scalability to 1,000+ active customers.

---

## 2. Decoupled Cloud Architecture Overview

```
                                  [ Users & Client Apps ]
                      (Arabic AI Tutor, Speaking Partner, Exams App)
                                             │
                                   HTTPS / TLS 1.3 (WAF)
                                             │
                        ┌────────────────────▼────────────────────┐
                        │        Edge & API Gateway Layer         │
                        │    (Cloudflare / AWS CloudFront + WAF)  │
                        │  * DDoS Protection & SSL Termination    │
                        │  * Global Rate Limiting (60 RPM/IP)     │
                        └────────────────────┬────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
       [ Synchronous REST Traffic ]                     [ Asynchronous Media Traffic ]
                     │                                               │
┌────────────────────▼────────────────────┐     ┌────────────────────▼────────────────────┐
│      Stateless API Compute Layer        │     │         Audio Processing Layer          │
│       (GCP Cloud Run / AWS ECS)         │     │     (Worker Pool: Faster-Whisper / TTS) │
│  * Python 3.11 rootless Docker container│     │  * Ephemeral GCS/S3 scratch storage     │
│  * Pydantic schema validation           │     │  * Raw audio auto-deleted after 24 hrs  │
│  * Sliding-window rate limiting         │     │  * Emits clean text transcripts to API  │
│  * Sequential / concurrent request pool │     └────────────────────┬────────────────────┘
└────────────────────┬────────────────────┘                          │
                     │                                               │
         ┌───────────┴───────────┐                       ┌───────────┴───────────┐
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Model Inference │   │  Database Layer  │   │  Object Storage  │   │ Background Learn │
│      Layer       │   │ (Managed Postgres│   │ (S3 / Cloud Stor)│   │   Worker Pool    │
│  * Managed APIs  │   │    + pgvector)   │   │  * Candidate sets│   │  * PII redaction │
│  * Dedicated GPU │   │  * User profiles │   │  * Curated models│   │  * Consent audit │
│    vLLM Clusters │   │  * Progress logs │   │  * Review sets   │   │  * Manifests     │
└──────────────────┘   └──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## 3. Layer-by-Layer Subsystem Specification

### 3.1 Stateless API Compute Layer
- **Technology:** Serverless container instances (GCP Cloud Run or AWS ECS Fargate).
- **Packaging:** Rootless multi-stage Docker container (`central_runtime_api/Dockerfile`), image size $<180\text{ MB}$.
- **Scaling Characteristics:** 
  - Scale-to-zero when idle (zero cost during inactive hours for beta).
  - Concurrency ceiling: 80 concurrent connections per container instance.
  - Auto-scaling metric: Request latency $>1.5\text{s}$ or CPU utilization $>70\%$.
- **Responsibilities:** Request authentication, validation, domain-prompt formatting (Tutor, Speaking, Exams), rate limiting, request ID propagation, and dispatch to inference engines.

### 3.2 Model Inference Layer (Managed vs. Cloud GPU)
The API communicates with inference engines strictly via HTTP REST using the `HostedProviderAdapter` interface.

#### Option Comparison Matrix:
| Inference Paradigm | Candidate Providers | Cost Structure | Latency (TTFT) | Cold-Start | Maintenance Overhead | Suitability for Beta |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **A. Managed Serverless LLM APIs** | HUMAIN Node, Groq, Together AI, Azure OpenAI | **Pay-per-token** (~$0.20–$0.80 / 1M tokens) | **150–400 ms** | **0 s** | **Zero** | **STRONGLY RECOMMENDED FOR BETA** |
| **B. Serverless GPU Container** | Modal, RunPod Serverless, Baseten | **Pay-per-GPU-second** (~$0.0004–$0.0008 / s) | 250–600 ms | 15–45 s | Low | Viable for custom quantized models |
| **C. Dedicated Cloud GPU Instance** | RunPod Secure, Lambda Labs, GCP A100/L4 | **Fixed hourly** (~$0.35–$1.80 / hr flat) | 100–250 ms | 0 s | High (OS/driver patching, vLLM monitoring) | Overkill for Beta; ideal at $>1,000$ active users |

> **Production Recommendation for Beta:**  
> Start with **Option A (Managed Serverless LLM APIs)**. It has zero idle costs, zero infrastructure maintenance, zero cold starts, and charges strictly per token used. Transition to **Option B/C (vLLM on Dedicated GPUs)** only when query volume crosses the monthly cost inflection point (~500,000 queries/month).

### 3.3 Database Layer
- **Engine:** Managed PostgreSQL 16 (AWS RDS or Supabase / GCP Cloud SQL).
- **Data Partitions:**
  - `users`: Anonymized identity hashes, tier status, consent flags.
  - `dialogue_sessions`: Multi-turn conversational memory with automated 30-day time-to-live (TTL).
  - `exams_records`: Student test attempts and error history.
  - `knowledge_base_chunks`: Curated Arabic grammar references and dictionary chunks indexed with `pgvector` for semantic retrieval.
- **Connection Pooling:** Built-in connection pooler (e.g. PgBouncer or Supabase connection pooling) capped at 50 pool connections.

### 3.4 Object Storage Layer
- **Technology:** Encrypted S3-compatible bucket (AWS S3 or GCS Standard).
- **Lifecycle Policies:**
  - `scratch-audio/`: **24-hour expiration policy** (Hard auto-deletion).
  - `dataset-candidates/`: Strict versioned retention under SSE-S3 encryption.
  - `model-checkpoints/`: Versioned safetensors/GGUF models.

### 3.5 Audio Processing Layer (Speech-to-Text & Text-to-Speech)
- **Decoupled Pipeline:** Audio processing is completely separated from the central text inference path.
- **Ingestion:** Client uploads short audio chunk to a presigned S3 URL $\to$ triggers async transcription worker.
- **STT Engine:** `faster-whisper-large-v3` running on a shared CPU/GPU worker pool or managed API (e.g. Groq Whisper / Deepgram).
- **TTS Engine:** ElevenLabs Arabic or local Coqui-TTS server.
- **Zero Raw Retention Rule:** Audio bytes are processed in-memory or on ephemeral scratch disk, transcribed, and permanently dropped. Only the sanitized text transcript is returned to the API.

### 3.6 Background Learning Worker Pool
- **Technology:** Standalone background task container (`central_runtime_api/workers/feedback_worker.py`).
- **Execution Model:** Periodic cron execution (e.g. once every 24 hours).
- **Responsibilities:** 
  1. Pulls raw feedback from the ingestion queue.
  2. Enforces consent verification.
  3. Applies deterministic PII redaction (`middleware/privacy.py`).
  4. Formulates candidate records (`data/candidates/v{X}.jsonl`).
  5. Updates dataset version registry for human philologist evaluation.

---

## 4. Provider-Independent Dynamic Routing Strategy

The Central API Gateway implements dynamic routing rules based on request domains:

```
[ Incoming Request ]
         │
         ├── Domain: Grammar / Syntax (Tutor) ──► Route to Specialist Arabic Model (e.g. Jais 3 / HUMAIN)
         │
         ├── Domain: Fast Conversational (Speaking) ─► Route to Low-Latency Engine (e.g. Groq Llama-3-70B Arabic)
         │
         ├── Domain: Complex Exam Parsing ──────► Route to High-Reasoning Model (e.g. Qwen 2.5 72B / GPT-4o)
         │
         └── Fallback Trigger (Timeout > 5s) ───► Automatic Failover to Secondary Managed Provider
```

---

## 5. Security, Privacy & Compliance Controls

1. **Consent Gate:**
   - Every user account has an explicit `consent_for_training` boolean flag.
   - If `consent == False`, the feedback pipeline records the score for customer support, but the record is **cryptographically excluded** from candidate training datasets.
2. **Deterministic PII Redaction:**
   - Pre-ingestion regex filters redact emails, phone numbers, Saudi National IDs, UAE Emirates IDs, and credit cards.
3. **Data Subject Rights (GDPR / Saudi PDPL Compliance):**
   - **Right to Erasure:** A single call to `DELETE /api/v1/user/data` purges session history, operational logs, and deletes the user's records from all un-promoted candidate datasets.
   - **Access Control:** All inter-service calls require signed mTLS or JWT tokens with rotating secret rotation.

---

## 6. Recommended Cloud Configuration for Beta (Cheapest Safe Setup)

For an invited beta of 50–100 users, the most cost-effective and reliable architecture avoids paying for an idle dedicated GPU:

| Infrastructure Component | Provider & Plan | Monthly Fixed Cost | Usage Variable Cost |
| :--- | :--- | :---: | :---: |
| **API Compute** | GCP Cloud Run (1 vCPU, 512 MB RAM, Scale-to-Zero) | $0.00 | ~$2.00 / month |
| **Model Inference** | Managed Serverless LLM API (HUMAIN Node or Together AI) | $0.00 | ~$12.00 (pay-per-token) |
| **Database** | Supabase Free / Micro Tier (PostgreSQL + pgvector) | $0.00 | $0.00 (within free tier) |
| **Object Storage** | Cloudflare R2 / AWS S3 (Free tier: 10 GB) | $0.00 | ~$0.50 / month |
| **DNS & WAF** | Cloudflare Free Tier (DDoS, SSL, Edge Caching) | $0.00 | $0.00 |
| **Total Estimated Beta Cost** | | | **~$14.50 / month** |

> **Beta Conclusion:**  
> For $< \$20/\text{month}$, the lab can launch a fully redundant, enterprise-grade cloud API prototype capable of supporting up to 100 beta users without maintaining a single idle GPU server.
