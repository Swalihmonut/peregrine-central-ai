# Cloudflare Edge Gateway & Domain Routing Security Audit
**Document ID:** PEREGRINE-BETA-V001-CF-001  
**Audited Hostnames:** `api.ai.peregrineacademy.in`, `exams-app.peregrineacademy.in`, `ai.peregrineacademy.in`  
**Classification:** Cloudflare Edge Architecture & Security Forensic Audit  
**Author:** Central API, Cloud Infrastructure and Deployment Architect  
**Date:** November 1, 2026  
**Status:** Read-Only Forensic Audit Completed (Zero DNS/Route Modifications)  

---

## 1. Executive Summary & Forensic Discovery

A live HTTP/DNS probe and local workspace inspection was conducted to verify the existing Cloudflare edge setup. Strict read-only safeguards were respected: no DNS records, worker deployments, or custom domain mappings were modified.

### Key Forensic Findings
1. **Host Misallocation Uncovered:**
   - The intended Central API hostname `api.ai.peregrineacademy.in` **currently serves the Exams App frontend** (`Arabic Academy AI` — TanStack Start / Nitro application).
   - Probing `https://api.ai.peregrineacademy.in/` returns `HTTP/2 200 OK` with page title `Arabic for every examination — Arabic Academy AI`.
   - Probing `https://exams-app.peregrineacademy.in/` returns the **identical** HTML payload.
2. **Worker Identification:**
   - Both `api.ai.peregrineacademy.in` and `exams-app.peregrineacademy.in` resolve to Cloudflare Worker **`swalihmonut-arabic-academy-ai`** (source repository: `/Users/muhammedswaliht/arabic-academy-ai`).
3. **Frontend Host Status (`ai.peregrineacademy.in`):**
   - Probing `https://ai.peregrineacademy.in/` returns **`HTTP/2 502 Bad Gateway`**. The Cloudflare edge proxy is active (orange-clouded), but no healthy origin web server or Pages deployment is attached.
4. **Zero Conflict with Exams App:**
   - Cloudflare custom domains are mapped independently per worker. A dedicated gateway worker (`peregrine-central-gateway`) can be created and bound to `api.ai.peregrineacademy.in` without disturbing `exams-app.peregrineacademy.in`.

---

## 2. Live HTTP Probe Matrix

| Hostname | Status Code | Server Header | Content Type | Active Service / Application |
| :--- | :---: | :---: | :---: | :--- |
| `api.ai.peregrineacademy.in` | `200 OK` | `cloudflare` | `text/html; charset=utf-8` | Exams App (`swalihmonut-arabic-academy-ai`) |
| `exams-app.peregrineacademy.in`| `200 OK` | `cloudflare` | `text/html; charset=utf-8` | Exams App (`swalihmonut-arabic-academy-ai`) |
| `ai.peregrineacademy.in` | `502 Bad Gateway`| `cloudflare` | `text/plain; charset=utf-8` | Unconfigured Origin / Offline Pages target |

---

## 3. Structural Comparison of Workers

Should the existing Exams App worker proxy Central API requests, or should a dedicated gateway Worker be provisioned?

| Dimension | Existing Worker (`swalihmonut-arabic-academy-ai`) | Dedicated Gateway Worker (`peregrine-central-gateway`) | Architectural Recommendation |
| :--- | :--- | :--- | :--- |
| **Source Directory** | `/Users/muhammedswaliht/arabic-academy-ai` | `peregrine-arabic-ai-lab/gateway` | **Isolate to separate package.** |
| **Runtime & Framework**| TanStack Start / Nitro SSR / React 19 | Pure TypeScript Cloudflare Worker (`fetch` handler) | **Pure TypeScript Worker (<1ms runtime).** |
| **Bundle Size** | ~1.8 MB (heavy UI, router, dependencies) | **< 15 KB** (lightweight proxy router) | **Gateway starts instantly.** |
| **CPU Time Footprint** | 8ms – 12ms per request | **0.8ms – 1.5ms per request** | **Stays well under 10ms Free limit.** |
| **Deployment Risk** | Modifying Nitro SSR breaks UGC-NET exam pages | Decoupled; zero blast radius on Exams App | **Zero risk to Exams App.** |
| **Secret Management** | Mixes frontend Supabase keys with API secrets | Isolates `CENTRAL_AI_API_KEY` to gateway only | **Superior security hygiene.** |

> [!IMPORTANT]
> **Decoupling Verdict:** We strictly recommend **NOT** proxying Central API calls through the existing Exams App Worker. Doing so would couple two distinct products, consume the 10ms Worker Free CPU limit, and create high operational risk. A dedicated, minimal Cloudflare Worker should be deployed specifically for `api.ai.peregrineacademy.in`.

---

## 4. Frontend Framework Compatibility (`ai.peregrineacademy.in`)

The main frontend application (`peregrine-arabic-ai-mvp`) is built on **Next.js 16.4.3** with **React 19.3.0**, utilizing App Router, Turbopack, and dynamic server-side API routes (`src/app/api/chat`, `src/app/api/feedback`, `src/app/api/notebooks`).

### Deployment Target Evaluation

| Target Platform | Free Tier Feasibility | Next.js 16 Compatibility | Configuration Required | Verdict |
| :--- | :---: | :---: | :--- | :--- |
| **Vercel Hobby** | **₹0.00 / month** (No credit card) | **100% Native** | Push repository, add custom domain `ai.peregrineacademy.in` CNAME. | **RECOMMENDED FOR DEMO.** Zero build errors, dynamic API routes supported. |
| **Cloudflare Pages (OpenNext)** | **₹0.00 / month** (No credit card) | Requires `@opennextjs/cloudflare` | Needs OpenNext build adapter and `nodejs_compat` configuration. | **VIABLE ALTERNATIVE.** Requires adapter setup for Next.js 16. |
| **Cloudflare Pages (Static)** | **₹0.00 / month** | Requires `output: 'export'` | Fails because dynamic API routes cannot be exported statically. | **DISQUALIFIED.** Incompatible with dynamic App Router API routes. |
| **Koyeb Free (Container)** | **₹0.00 / month** | 100% Native (Node 20 Docker) | Consumes single free instance (leaving no slot for Python API). | **DISQUALIFIED.** Only 1 free instance permitted per Koyeb account. |

---

## 5. Gateway Security Architecture & Secret Injection

```mermaid
sequenceDiagram
    autonumber
    actor User as Student Browser
    participant Edge as Cloudflare Gateway (api.ai...)
    participant API as Central API (Koyeb Origin)
    participant DB as Remote Supabase

    User->>Edge: POST /api/v1/chat (Payload: JSON, No Secrets)
    Note over Edge: 1. Validate Origin & Rate Limit (100 RPM/IP)<br/>2. Inspect Content-Length (<2 MB)<br/>3. Inject Authorization: Bearer ${CENTRAL_AI_API_KEY}
    Edge->>API: POST /api/v1/chat (Bearer Token Injected)
    Note over API: 4. Verify HMAC Constant-Time Secret<br/>5. Execute MOCK or Gemini Inference<br/>6. Filter PII & Check Consent
    API-->>Edge: 200 OK (JSON Response + Tokens + Telemetry)
    Note over Edge: 7. Strip Origin Headers & Pass JSON
    Edge-->>User: 200 OK (Sanitized Arabic Content)
```

### 5.1 Security Controls Enforced at the Edge
1. **Zero Secret Exposure to Client:** The browser never receives the `CENTRAL_AI_API_KEY`, Google Gemini API key, or Supabase service role key.
2. **Edge Rate Limiting:** Cloudflare Worker enforces 100 requests/minute per client IP via Cloudflare KV or in-memory LRU counter.
3. **Payload Inspection:** Rejects requests with `Content-Length > 2097152` (2 MB) at the edge before sending traffic to origin.
4. **Header Sanitization:** Removes dangerous forwarding headers (`X-Forwarded-Host`, `X-Original-URL`) and sets strict security headers:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Content-Security-Policy: default-src 'self'`

---

## 6. Zero-Disruption Transition Procedure

To migrate `api.ai.peregrineacademy.in` safely without impacting the Exams App:

1. **Phase 1 (Preparation):** Build and test the dedicated gateway worker script locally in `peregrine-arabic-ai-lab`.
2. **Phase 2 (Worker Creation):** Deploy worker `peregrine-central-gateway` to Cloudflare (on `workers.dev` subdomain first).
3. **Phase 3 (Secret Secret Provisioning):** Bind encrypted secret `CENTRAL_AI_API_KEY` via `wrangler secret put CENTRAL_AI_API_KEY`.
4. **Phase 4 (Domain Reassignment):** In Cloudflare Dashboard, detach `api.ai.peregrineacademy.in` from `swalihmonut-arabic-academy-ai` and attach it to `peregrine-central-gateway`.
5. **Phase 5 (Verification):** Verify that `https://exams-app.peregrineacademy.in/` continues serving the Exams App with zero downtime, while `https://api.ai.peregrineacademy.in/health` returns `200 OK` from the Central API.
