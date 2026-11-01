# Owner Approval Checklist — Beta V-001 Zero-Cost Private Demo
**Document Version:** 1.0.0 (Pre-Implementation Action Gates)  
**Target:** Peregrine Arabic AI Staging & Demo Launch  
**Date:** 2026-11-01  
**Author:** Central API, Hosting and Infrastructure Engineer  

---

## 1. Executive Summary

In accordance with strict safety directives, zero cloud resources have been provisioned, zero DNS records have been modified, and zero billing accounts have been activated.

Before the engineering team can implement the zero-cost staging environment, the project owner must review and explicitly authorize the following 6 decision gates:

---

## 2. Master Owner Approval Action Gates

### [GATE-01] Cloudflare Domain Decoupling for `api.ai.peregrineacademy.in`
- **Current State:** `https://api.ai.peregrineacademy.in/` is actively bound to the Exams App Worker (`swalihmonut-arabic-academy-ai`), serving the Exams App HTML frontend.
- **Required Action:** Authorize decoupling `api.ai.peregrineacademy.in` from `swalihmonut-arabic-academy-ai` in the Cloudflare Dashboard.
- **Safety Guarantee:** `https://exams-app.peregrineacademy.in/` will remain completely untouched and live.
- **Owner Approval Required:** `[ ] APPROVED   [ ] REJECTED`

---

### [GATE-02] Frontend Hosting Platform Selection (Next.js 16)
- **Current State:** `https://ai.peregrineacademy.in/` returns HTTP 502 Bad Gateway. Code inspection proves the app uses Next.js 16.4.3 with 15 server-side API routes and cannot be statically exported to Cloudflare Pages.
- **Recommended Action:** Authorize deploying `Developer/peregrine-arabic-ai-mvp` to **Vercel Hobby Free Tier** (100% free, zero credit card, native Next.js 16 serverless Route Handler support).
- **Alternative:** Authorize running a Node.js Docker container on Koyeb.
- **Owner Approval Required:** `[ ] APPROVED VERCEL HOBBY   [ ] APPROVED KOYEB NODE CONTAINER`

---

### [GATE-03] Python Central API Hosting on Koyeb Free Tier (Nano)
- **Current State:** Central API is container-ready, consuming ~145 MB disk and 37 MB RAM (tested at 100 concurrent requests). Fits effortlessly in Koyeb's 512 MB RAM / 2 GB disk free tier.
- **Known Limitations to Accept:**
  - Mandatory scale-to-zero sleep after 1 hour of platform inactivity.
  - 1 to 5-second cold-start delay on first request following an idle hour.
  - Ephemeral container storage (writes to `/app/data` are wiped on sleep).
- **Owner Approval Required:** `[ ] APPROVED FOR DEMO   [ ] REJECTED`

---

### [GATE-04] Koyeb Disk Limit Setting (`CENTRAL_AI_MIN_DISK_FREE_GB=0.5`)
- **Current State:** Default `config.py` enforces `min_disk_free_gb=15.0`. Because Koyeb Free instances only have a 2 GB SSD, leaving this at default will cause all inference calls to fail with `DISK_SAFETY_THRESHOLD_BREACHED`.
- **Required Action:** Authorize setting `CENTRAL_AI_MIN_DISK_FREE_GB=0.5` in the Koyeb environment variable configuration.
- **Owner Approval Required:** `[ ] APPROVED   [ ] REJECTED`

---

### [GATE-05] Remote Inference Pilot API Key vs. Mock Mode
- **Current State:** No remote model credentials are configured. Central API runs in Mock Mode (deterministic Arabic pedagogical responses).
- **Decision:**
  - **Option A (Free Remote API):** Supply a free Google Gemini 1.5/2.0 Flash API key (15 RPM / 1M TPM free, zero payment card) for live dynamic Arabic generation during the demo.
  - **Option B (Mock Mode):** Run the invited demo in pure Mock Mode with zero external API calls.
- **Owner Approval Required:** `[ ] OPTION A (GEMINI FREE KEY)   [ ] OPTION B (MOCK MODE)`

---

### [GATE-06] Supabase Free Tier Inactivity & Manual Backup Policy
- **Current State:** Supabase PostgreSQL with `pgvector` has sufficient capacity for the demo (~35 MB consumed of 500 MB). Supabase Free automatically pauses if 7 consecutive days pass with zero queries, and automated backups are not included on the Free plan.
- **Required Action:** Acknowledge the 7-day pause rule (1-click manual unpause via dashboard) and authorize the engineering team to execute the documented weekly manual `pg_dump` backup runbook.
- **Owner Approval Required:** `[ ] ACKNOWLEDGED & APPROVED   [ ] REJECTED`

---

## 3. Next Steps Following Sign-Off

Upon receiving owner sign-off on the gates above:
1. Engineer executes Cloudflare domain decoupling (Gate 01).
2. Engineer connects repository to Vercel Hobby and binds `ai.peregrineacademy.in` (Gate 02).
3. Engineer launches Koyeb container with `CENTRAL_AI_MIN_DISK_FREE_GB=0.5` (Gates 03 & 04).
4. Engineer executes the 6-stage end-to-end cloud integration test suite and delivers the final staging sign-off report.
