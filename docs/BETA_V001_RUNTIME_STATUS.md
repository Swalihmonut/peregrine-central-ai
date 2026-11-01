# Central AI Runtime & API Status Report — Beta V-001

**Document Version:** 1.0.0 (Beta V-001)  
**Role:** Agent 2 — Local AI Runtime and API Engineer  
**Host Architecture:** Apple Silicon M4 (MacBook Air, Mac16,12, 10 Cores, 32 GB Unified Memory, macOS 27.0.1)  
**Workspace:** `/Users/muhammedswaliht/peregrine-arabic-ai-lab`  
**Status:** OPERATIONAL & TESTED (Mock test suite: 11/11 Passed; Zero external package installations)

---

## 1. Runtime Readiness Summary

The Central Arabic AI Service prototype has been successfully engineered, isolated, and verified in the lab workspace at `central_runtime_api/`.

| Component / Capability | Status | Implementation Artefact | Verification Result |
| :--- | :---: | :--- | :--- |
| **API Server Core** | `OPERATIONAL` | `central_runtime_api/server.py` | Native `ThreadingHTTPServer` with CORS, JSON error envelopes, and request ID tracking. |
| **Pydantic Schemas** | `OPERATIONAL` | `central_runtime_api/schemas.py` | Strictly typed request/response contracts for Chat, Tutor, Speaking, and Exams. |
| **Provider Manager** | `OPERATIONAL` | `central_runtime_api/services/provider_manager.py` | Enforces sequential execution lock (`threading.Lock`) and 15 GB disk safety interlock. |
| **Mock Provider Adapter** | `OPERATIONAL` | `central_runtime_api/adapters/mock_adapter.py` | High-fidelity deterministic Arabic responses; zero GPU/model loading required. |
| **Ollama Adapter** | `OPERATIONAL` | `central_runtime_api/adapters/ollama_adapter.py` | Streaming chunk parser; strict thinking isolation; returns `MODEL_REASONING_ONLY` if content is empty. |
| **MLX Jais Adapter** | `OPERATIONAL` | `central_runtime_api/adapters/mlx_adapter.py` | OpenAI-compatible endpoint client; delimiter stripper; captures `finish_reason`. |
| **Hosted Adapter** | `OPERATIONAL` | `central_runtime_api/adapters/hosted_adapter.py` | Extensible adapter stub ready for HUMAIN Node, OpenAI, or remote vLLM endpoints. |
| **Automated Test Suite** | `PASS (100%)` | `central_runtime_api/test_api.py` | **11/11 tests passed** (Health, Ready, Chat, Tutor, Speaking, Exams, Validation, Safety). |
| **Lab Integration Tests**| `PASS (100%)` | `tests/test_central_api.py` & `test_runners.py`| **24/24 combined tests passed** cleanly. |

---

## 2. Host Machine Capacity Snapshot

- **Physical Host:** Apple Silicon MacBook Air (Mac16,12), Apple M4 SoC, 10 CPU Cores, 32 GB Unified Memory.
- **Disk Storage (`/System/Volumes/Data`):**
  - Total Volume: `926 GiB` | Used: `874 GiB` | **Available: `23 GiB` (98% capacity utilized)**.
  - Headroom above 15 GB hard stop: **`8 GiB`**.
  - Headroom above 10 GB emergency reserve floor: **`13 GiB`**.
- **Memory Pressure:**
  - Kernel memory pressure: **`77%` free headroom (Tier: Normal)**.
  - Clean, reclaimable inactive file cache: **`~12.3 GB`**.
  - Active encrypted swap: **`2.86 GB`** (stable, unexpanding).
- **Process Status:**
  - Port 11434: Ollama daemon active (PID 13701, 0 models loaded in VRAM).
  - Port 8080: Closed (Jais MLX server stopped).
  - Port 8000: Default target for Central AI API (unbound, ready).

---

## 3. Dependency & Environment Integrity Audit

In strict compliance with Mission Task 9 (*"Use existing installed packages only where possible. Do not install a new stack without documenting why"*):

- **Zero Packages Installed:** No external packages were installed.
- **Utilized Installed Stack:**
  - `python`: CPython 3.11.18 (`.venv`)
  - `pydantic`: 2.14.2 (Request/Response schemas)
  - `http.server`: Standard Library (`ThreadingHTTPServer`)
  - `urllib` / `json` / `threading` / `time`: Standard Library
- **Preservation of Other Environments:**
  - Main Virtual Environment (`.venv`): Intact and preserved.
  - MLX Virtual Environment (`.venv-mlx`): Intact and preserved.
  - Prosody Virtual Environment (`.venv-prosody`): Intact and preserved.
  - Specialist Tools (`specialist_tools/`): Untouched.
  - Benchmark Suites (`benchmarks/`): Untouched.

---

## 4. Application Integration Readiness

The Central AI API is immediately consumable by the Peregrine application suite using the default `mock` provider during frontend and application development:

```bash
# Start the Central AI API in background or active shell
.venv/bin/python -m central_runtime_api.run --port 8000 --provider mock
```

### Application Connection Map:
1. **Arabic AI Tutor:** Connect to `POST http://127.0.0.1:8000/api/v1/tutor/explain`.
2. **AI Speaking Partner:** Connect to `POST http://127.0.0.1:8000/api/v1/speaking/respond`.
3. **Exams App:** Connect to `POST http://127.0.0.1:8000/api/v1/exams/explain`.
4. **General Assistant:** Connect to `POST http://127.0.0.1:8000/api/v1/chat`.

---

## 5. Next Steps & Operator Action

1. **Application Integration Testing:** Application engineers can immediately integrate against `http://127.0.0.1:8000` using the mock adapter.
2. **Sequential Model Inference Activation:** When the Operator grants authorization for live inference:
   - To use Qwen: Start server with `--provider ollama --model qwen3:4b`.
   - To use Jais: Launch Jais MLX server on port 8080 and start Central API with `--provider mlx_jais`.
3. **Continuous Resource Guard:** The API server will automatically reject requests if host disk space drops below 15 GB.
