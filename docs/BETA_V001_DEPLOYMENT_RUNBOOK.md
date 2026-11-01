# Peregrine Arabic AI Beta V-001 — Step-by-Step Deployment Runbook
**Document ID:** PEREGRINE-BETA-V001-RUNBOOK-001  
**Classification:** Cloud Operations & Staged Deployment Runbook  
**Target Environments:** Plan A (Local Acceptance), Plan B (Zero-Cost Private Cloud Demo), Plan C (Commercial Production)  
**Author:** Central API, Cloud Infrastructure and Deployment Architect  
**Date:** November 1, 2026  
**Execution Policy:** Strictly Declarative & Pre-Flight (Do NOT execute cloud provisioning or database mutations during audit)  

---

## 1. Overview of Deployment Stages

This runbook provides complete, syntax-verified terminal commands for orchestrating Peregrine Arabic AI across three discrete stages:

1. **Stage 1 (Plan A): Local Acceptance Runbook (₹0.00)**  
   Local Python ASGI process + Local Next.js 16 App Router. Pure in-memory/MOCK verification.
2. **Stage 2 (Plan B): Zero-Cost Private Cloud Demo Runbook (₹0.00)**  
   Koyeb Free Nano container + Cloudflare Gateway Worker + Supabase Free pgvector + Vercel Hobby Frontend.
3. **Stage 3 (Plan C): Reliable Commercial Production Transition Runbook ($30–$45/mo)**  
   Google Cloud Run (Mumbai, `min-instances: 1`) + Supabase Pro ($25/mo) + Cloudflare Workers Paid ($5/mo).

---

## 2. Plan A: Local Acceptance Runbook (₹0.00)

### Step A.1: Initialize Local Python Virtual Environment & Install API Dependencies
```bash
# Navigate to lab workspace
cd ~/peregrine-arabic-ai-lab

# Activate existing Python 3.11 virtual environment
source .venv/bin/activate

# Verify pinned runtime dependencies
pip install -r central_runtime_api/requirements.txt
```

### Step A.2: Launch Local Central API in MOCK Mode
```bash
# Export local configuration
export CENTRAL_AI_HOST="127.0.0.1"
export CENTRAL_AI_PORT="8000"
export CENTRAL_AI_ENV="development"
export CENTRAL_AI_PROVIDER="mock"
export CENTRAL_AI_MODEL="qwen3:4b"
export CENTRAL_AI_ENFORCE_DISK_LIMIT="false"
export CENTRAL_AI_CORS_ORIGINS="http://localhost:3000,http://localhost:3005"

# Launch via Uvicorn ASGI engine
python3 -m central_runtime_api.run --host 127.0.0.1 --port 8000 --server asgi
```

### Step A.3: Verify Local API Endpoints
Open a second terminal:
```bash
# Liveness probe
curl -s http://127.0.0.1:8000/health | jq .

# Readiness probe
curl -s http://127.0.0.1:8000/ready | jq .

# Test Arabic Chat in MOCK mode
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "ما هو إعراب كلمة العلمُ نورٌ؟"}]}' | jq .
```

### Step A.4: Launch Unified Next.js 16 Client & Run QA Acceptance
```bash
# Navigate to MVP client workspace
cd ~/Developer/peregrine-arabic-ai-mvp

# Ensure local dependencies are present
npm install

# Run unit and integration tests
npm test

# Launch development web server
npm run dev
# Accessible at http://localhost:3000
```

---

## 3. Plan B: Zero-Cost Private Cloud Demo Runbook (₹0.00)

> [!IMPORTANT]
> **Pre-Flight Notice:** Do not execute these provisioning commands during read-only audit turns. Execute only when cloud staging is explicitly authorized by the project owner.

### Step B.1: Build & Deploy Python Central API to Koyeb Free Tier

#### 1. Container Build & Push (via GitHub or Koyeb CLI)
```bash
# Option 1: Direct Koyeb CLI Deployment from Git repository
koyeb app create peregrine-ai

koyeb service create \
  --app peregrine-ai \
  --name central-api \
  --git github.com/your-org/peregrine-arabic-ai-lab \
  --git-branch main \
  --git-workdir central_runtime_api \
  --instance-type nano \
  --regions fra \
  --ports 8000:http \
  --routes /:8000 \
  --env CENTRAL_AI_HOST="0.0.0.0" \
  --env CENTRAL_AI_PORT="8000" \
  --env CENTRAL_AI_ENV="staging" \
  --env CENTRAL_AI_SERVER_ENGINE="asgi" \
  --env CENTRAL_AI_PROVIDER="mock" \
  --env CENTRAL_AI_ENFORCE_DISK_LIMIT="false" \
  --env CENTRAL_AI_CORS_ORIGINS="https://ai.peregrineacademy.in" \
  --env CENTRAL_AI_API_KEY="sec_gateway_peregrine_beta_2026"
```

#### 2. Verify Koyeb Deployment Status
```bash
koyeb service get peregrine-ai/central-api
# Expected: Healthy | Ingress: https://central-api-peregrine-ai.koyeb.app
```

---

### Step B.2: Deploy Dedicated Cloudflare Edge Gateway Worker

#### 1. Initialize Gateway Worker Project
```bash
mkdir -p ~/peregrine-arabic-ai-lab/gateway && cd ~/peregrine-arabic-ai-lab/gateway

# Initialize minimal wrangler.jsonc
cat << 'EOF' > wrangler.jsonc
{
  "name": "peregrine-central-gateway",
  "main": "src/index.ts",
  "compatibility_date": "2026-10-31",
  "compatibility_flags": ["nodejs_compat"],
  "vars": {
    "ORIGIN_URL": "https://central-api-peregrine-ai.koyeb.app"
  }
}
EOF
```

#### 2. Implement Pure Edge Proxy (`src/index.ts`)
```typescript
export interface Env {
  ORIGIN_URL: string;
  CENTRAL_AI_API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // 1. Handle CORS Pre-Flight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "https://ai.peregrineacademy.in",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // 2. Reject large bodies before forwarding (> 2 MB)
    const contentLength = parseInt(request.headers.get("content-length") || "0", 10);
    if (contentLength > 2097152) {
      return new Response(JSON.stringify({ error: "PAYLOAD_TOO_LARGE" }), {
        status: 413,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 3. Clone and enrich request for origin
    const targetUrl = new URL(url.pathname + url.search, env.ORIGIN_URL);
    const originHeaders = new Headers(request.headers);
    originHeaders.set("Host", targetUrl.host);
    originHeaders.set("Authorization", `Bearer ${env.CENTRAL_AI_API_KEY}`);

    try {
      const originResponse = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: originHeaders,
        body: request.body,
        redirect: "follow",
      });

      // Pass response back with CORS headers attached
      const responseHeaders = new Headers(originResponse.headers);
      responseHeaders.set("Access-Control-Allow-Origin", "https://ai.peregrineacademy.in");
      return new Response(originResponse.body, {
        status: originResponse.status,
        headers: responseHeaders,
      });
    } catch (err: any) {
      return new Response(JSON.stringify({ error: "GATEWAY_TIMEOUT_OR_SLEEPING", details: err.message }), {
        status: 504,
        headers: { "Content-Type": "application/json" },
      });
    }
  },
};
```

#### 3. Provision Secret & Deploy Worker
```bash
# Securely inject secret token
wrangler secret put CENTRAL_AI_API_KEY --name peregrine-central-gateway

# Deploy worker to Cloudflare Edge
wrangler deploy --name peregrine-central-gateway
```

#### 4. Reassign Domain in Cloudflare Dashboard
1. Navigate to: **Workers & Pages** -> **`swalihmonut-arabic-academy-ai`** -> **Settings** -> **Domains & Routes**.
2. Remove Custom Domain: `api.ai.peregrineacademy.in` (Do **not** remove `exams-app.peregrineacademy.in`).
3. Navigate to: **Workers & Pages** -> **`peregrine-central-gateway`** -> **Settings** -> **Domains & Routes**.
4. Add Custom Domain: `api.ai.peregrineacademy.in`.

---

### Step B.3: Deploy Next.js 16 Frontend to Vercel (Hobby Free Tier)
```bash
# Navigate to MVP repository
cd ~/Developer/peregrine-arabic-ai-mvp

# Deploy via Vercel CLI (or link repository via GitHub)
npx vercel --prod

# Link custom domain: ai.peregrineacademy.in
npx vercel domains add ai.peregrineacademy.in
```

### Step B.4: Apply Supabase Migrations & Initial Backup
```bash
# 1. Execute baseline backup of existing Supabase database
PGPASSWORD="${SUPABASE_DB_PASSWORD}" pg_dump \
  --host="db.atuktsyhhgpsemsnvbyb.supabase.co" \
  -U "postgres" -d "postgres" \
  -f "./backups/pre_migration_backup_$(date +%Y%m%d).sql"

# 2. Apply Research Notebook & pgvector schema
PGPASSWORD="${SUPABASE_DB_PASSWORD}" psql \
  --host="db.atuktsyhhgpsemsnvbyb.supabase.co" \
  -U "postgres" -d "postgres" \
  -f "supabase/migrations/20261030_research_notebook_persistence.sql"
```

---

## 4. Plan C: Reliable Commercial Production Runbook ($30–$45/mo)

When transitioning beyond the invited beta to public 24/7 commercial traffic:

### Step C.1: Provision Google Cloud Run (Mumbai `asia-south1`)
```bash
# Deploy with 1 always-on warm instance to eliminate cold starts
gcloud run deploy peregrine-central-api \
  --image="gcr.io/peregrine-production/central-api:v1.0.0" \
  --region="asia-south1" \
  --platform="managed" \
  --min-instances=1 \
  --max-instances=10 \
  --memory="1Gi" \
  --cpu="1" \
  --set-env-vars="CENTRAL_AI_ENV=production,CENTRAL_AI_PROVIDER=hosted"
```

### Step C.2: Upgrade Supabase to Pro Tier ($25/mo)
1. In Supabase Dashboard -> Organization Billing -> Upgrade to Pro.
2. Enable **Automated Daily Backups** & **7-Day Point-In-Time Recovery (PITR)**.
3. Database storage expands automatically from 500 MB to 8 GB.
4. 7-Day inactivity pausing is completely deactivated.

### Step C.3: Upgrade Cloudflare Workers to Paid Tier ($5/mo)
1. Workers Paid expands CPU execution limits from 10 ms to **50 ms**.
2. Unlocks unlimited subrequests and native Cloudflare Rate Limiting Rules.
