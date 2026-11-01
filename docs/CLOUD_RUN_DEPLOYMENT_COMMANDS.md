# Cloud Run Staging Deployment Commands & Operational Runbook
**Service:** `peregrine-central-ai-api`  
**Target Region:** Mumbai (`asia-south1`)  
**Container Registry:** Google Artifact Registry (`asia-south1-docker.pkg.dev/<PROJECT_ID>/peregrine-docker/central-ai-api:beta-v001`)  
**Status:** DRAFT SPECIFICATION (Do Not Execute Without Owner Explicit Approval)  

---

## 1. Container Build & Push Commands

### 1.1 Local Docker Build (Static Verification)
```bash
# Build the production container locally using Docker multi-stage build
docker build \
  -t asia-south1-docker.pkg.dev/PROJECT_ID_PLACEHOLDER/peregrine-docker/central-ai-api:beta-v001 \
  -f central_runtime_api/Dockerfile .
```

### 1.2 Google Cloud Build (Serverless Image Compilation)
```bash
# Submit build directly to Google Cloud Build without requiring a local Docker daemon
gcloud builds submit \
  --tag asia-south1-docker.pkg.dev/PROJECT_ID_PLACEHOLDER/peregrine-docker/central-ai-api:beta-v001 \
  --project PROJECT_ID_PLACEHOLDER
```

---

## 2. Cloud Run Staging Deployment Command

> **IMPORTANT:** Replace `PROJECT_ID_PLACEHOLDER` with the verified Google Cloud Project ID once created.

```bash
gcloud run deploy peregrine-central-ai-api \
  --image asia-south1-docker.pkg.dev/PROJECT_ID_PLACEHOLDER/peregrine-docker/central-ai-api:beta-v001 \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1024Mi \
  --min-instances 0 \
  --max-instances 2 \
  --concurrency 80 \
  --timeout 120s \
  --execution-environment gen2 \
  --set-env-vars CENTRAL_AI_ENV=staging \
  --set-env-vars CENTRAL_AI_SERVER_ENGINE=asgi \
  --set-env-vars CENTRAL_AI_PROVIDER=mock \
  --set-env-vars CENTRAL_AI_MODEL=qwen3:4b \
  --set-env-vars CENTRAL_AI_CORS_ORIGINS=https://ai.peregrineacademy.in,http://localhost:3000 \
  --set-env-vars CENTRAL_AI_MAX_BODY_BYTES=2097152 \
  --set-env-vars CENTRAL_AI_RATE_LIMIT_RPM=60 \
  --set-env-vars CENTRAL_AI_DATA_DIR=/app/data \
  --set-secrets CENTRAL_AI_API_KEY=CENTRAL_AI_API_KEY_SECRET:latest \
  --project PROJECT_ID_PLACEHOLDER
```

---

## 3. Staging Verification Protocol

Once deployed, execute the automated verification sequence against the generated service URL (`https://peregrine-central-ai-api-<hash>-as.a.run.app`):

### Step 1: Liveness Probe
```bash
curl -i https://SERVICE_URL/health
# Expected: HTTP 200 OK {"status": "ok", "version": "0.1.0-beta", "active_provider": "mock", "active_model": "qwen3:4b"}
```

### Step 2: Readiness Probe & Resource Telemetry
```bash
curl -i https://SERVICE_URL/ready
# Expected: HTTP 200 OK {"ready": true, "provider_status": "ready", ...}
```

### Step 3: Protected Endpoint Authentication Check
```bash
# 1. Unauthenticated request (Must return 401)
curl -i -X POST https://SERVICE_URL/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "مرحبا"}]}'

# 2. Authenticated request (Must return 200)
curl -i -X POST https://SERVICE_URL/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_STAGING_KEY" \
  -d '{"messages": [{"role": "user", "content": "ما إعراب سماء؟"}]}'
```

### Step 4: Run Automated Staging Smoke Test
```bash
STAGING_URL=https://SERVICE_URL STAGING_API_KEY=YOUR_STAGING_KEY \
  .venv/bin/python tests/staging_smoke_test.py
# Expected: 7 / 7 Gates Passed
```

---

## 4. Rollback & Disaster Recovery Runbook

If any defect, memory leak, or latency anomaly is observed in staging:

### Rollback to Previous Revision (Zero-Downtime)
```bash
# List recent revisions
gcloud run revisions list \
  --service peregrine-central-ai-api \
  --region asia-south1 \
  --project PROJECT_ID_PLACEHOLDER

# Roll back traffic immediately (100% routing to previous stable revision)
gcloud run services update-traffic peregrine-central-ai-api \
  --to-revisions PREVIOUS_REVISION_NAME=100 \
  --region asia-south1 \
  --project PROJECT_ID_PLACEHOLDER
```

### Emergency Stop (Quarantine Service)
```bash
# Scale instances immediately to 0 and deny all ingress
gcloud run services update peregrine-central-ai-api \
  --max-instances 0 \
  --region asia-south1 \
  --project PROJECT_ID_PLACEHOLDER
```
