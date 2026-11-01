# Zero-Cost Cloud Deployment Recommendation — Beta V-001 (Corrected)
**Service Suite:** Peregrine Arabic AI (Central AI Runtime API, Tutor, Speaking, Exams, Notebook)  
**Target Monthly Mandatory Spend:** **₹0.00 / month ($0.00)**  
**Audit Completed:** 2026-10-31  
**Author:** Central API, Hosting and Infrastructure Engineer  

---

## 1. Executive Verdict across Three Operational Tiers

To eliminate ambiguity, this assessment distinguishes three distinct deployment tiers and evaluates whether each is genuinely achievable at **₹0.00 / month**:

| Operational Tier | Definition & Audience | Achievable at ₹0.00 / month? | Core Prerequisites & Compromises |
| :--- | :--- | :---: | :--- |
| **Tier A: Free Development & Demo** | Internal developer testing, automated regression runs, and local/pilot stakeholder demonstrations. | **YES (₹0.00)** | Fully functional on local Apple Silicon (M4, 32 GB) via mock mode or local Ollama/MLX; or on Koyeb Free Nano (Frankfurt). |
| **Tier B: Free Invited Beta** | Controlled rollout for 20–50 invited Arabic learners with documented and accepted availability trade-offs. | **YES (₹0.00)** | Cloudflare Pages (Frontend) + Koyeb Free (Gateway) + Supabase Free (DB) + Free Tier Remote LLM Key (Gemini Flash). **Subject to 1-hr container sleep (1–5s wake-up) and 7-day Supabase pause**. |
| **Tier C: Reliable Production Hosting** | Commercial 24/7 public launch, multi-region low latency, guaranteed zero-sleep uptime, automated PITR backups, and high-concurrency LLM inference. | **NO (Not Achievable at ₹0.00)** | Unavoidable base fees: Cloud Run ALB in Mumbai (~₹1,530/mo) or Supabase Pro ($25/mo) + Container hosting (~$7–$20/mo). **True production requires ~$20–$50/mo (₹1,700–₹4,200/mo)**. |

---

## 2. Master Infrastructure Classification Matrix (Corrected)

| Infrastructure Component | Evaluated Option | Cost Classification | Monthly Mandatory Fee | Critical Operational Limitation |
| :--- | :--- | :---: | :---: | :--- |
| **Frontend Web App** | **Cloudflare Pages** | **Completely free with no payment method** | **₹0.00** | Unlimited bandwidth; ideal for static Next.js exports (`output: 'export'`). |
| **Edge DNS & SSL** | **Cloudflare Universal SSL** | **Completely free with no payment method** | **₹0.00** | Automatic edge TLS termination for `peregrineacademy.in`. |
| **Edge API Gateway** | **Cloudflare Workers Free** | **Completely free with no payment method** | **₹0.00** | 10ms CPU limit per request; subrequest timeout 30s. |
| **Python Central API (Option 1)** | **Koyeb Free Tier (Nano)** | **Completely free with no payment method** | **₹0.00** | **Mandatory scale-to-zero after 1 hour idle. 1–5s cold start delay.** 512 MB RAM (Gateway mode only). |
| **Python Central API (Option 2)** | **Local Mac Host via Cloudflare Tunnel** | **Completely free with no payment method** | **₹0.00** | 32 GB RAM, runs full local LLMs; requires physical Mac laptop to stay powered and connected. |
| **Python Central API (Option 3)** | *Hugging Face Spaces (Docker)* | **Paid / Subscription Required** | **$9.00 / month (~₹750)** | **DISQUALIFIED.** Creating Docker Spaces requires an active Hugging Face PRO subscription. |
| **Database & Vector Search** | **Existing Supabase Free Tier** | **Completely free with no payment method** | **₹0.00** | **No automated backups/PITR.** Pauses on 7 days idle. Measured limit: **~40k–50k feedback rows**. |
| **Audio Speech Processing** | **Browser Web Speech API** | **Completely free with no payment method** | **₹0.00** | Client-side TTS/STT on student device; zero server compute needed. |
| *Cloud Run (Alternative)* | *Google Cloud Run (asia-south1)* | *Free but payment method required* | *₹0.00 compute + ₹1,530/mo ALB* | Mandatory credit card billing account; external ALB fee in Mumbai. |

---

## 3. Recommended Tier B (Invited Beta) Zero-Cost Architecture

```
                                  [ STUDENT USER ]
                                         │
                                         ▼ (HTTPS)
       ┌─────────────────────────────────┴─────────────────────────────────┐
       │                 CLOUDFLARE EDGE PLATFORM (FREE TIER)              │
       │                                                                   │
       │  [ Cloudflare Pages ]               [ Cloudflare DNS & Proxy ]   │
       │   ai.peregrineacademy.in             api.ai.peregrineacademy.in   │
       │   (Static Export / Next.js)          (Edge Gateway & CNAME)       │
       └──────────────────┬───────────────────────────────┬────────────────┘
                          │                               │
                          │                               ▼ (Proxied HTTPS)
                          │             ┌───────────────────────────────────┐
                          │             │ KOYEB FREE TIER CONTAINER (NANO)  │
                          │             │   - 0.1 vCPU, 512 MB RAM          │
                          │             │   - Runs central_runtime_api:asgi │
                          │             │   - Frankfurt (fra) Region        │
                          │             │   - Sleeps after 1 hour of idle   │
                          │             └───────────────┬─┬─────────────────┘
                          │                             │ │
                          │        ┌────────────────────┘ │ (Outbound HTTPS REST)
                          │        │                      ▼
                          │        │       ┌────────────────────────────────┐
                          │        │       │ REMOTE FREE LLM PROVIDER       │
                          │        │       │ Google Gemini Flash Free Tier  │
                          │        │       │ (15 RPM / 1M TPM free, ₹0)     │
                          │        ▼       └────────────────────────────────┘
                          │ (HTTPS REST)
       ┌──────────────────┴───────────────────────────────────────────────┐
       │                EXISTING SUPABASE POSTGRESQL (FREE TIER)          │
       │  - Research Notebooks & Sources                                   │
       │  - 10,000 Arabic Vector Chunks (pgvector, 1536-dim)               │
       │  - Up to 50,000 Central API Feedback & Learning Queue Records    │
       │  - Manual weekly pg_dump backup protocol                          │
       └──────────────────────────────────────────────────────────────────┘
```

---

## 4. Discovered Configuration & Domain Blockers

1. **Approved API Hostname is Currently Misrouted:**
   - A live probe of `https://api.ai.peregrineacademy.in/` confirmed it currently returns the **Exams App HTML frontend** (`Arabic Academy AI`), bound to Worker `swalihmonut-arabic-academy-ai`.
   - The hostname does **not** currently route to the Central AI Runtime API.
   - Decoupling this domain mapping in Cloudflare Dashboard is required before deploying the Central API.
2. **Frontend Hostname (`ai.peregrineacademy.in`) is Down:**
   - A live probe confirmed `https://ai.peregrineacademy.in/` returns **HTTP 502 Bad Gateway**.
   - Cloudflare Pages must be pointed to this hostname to serve the redesigned Next.js frontend.

---

## 5. Explicit Known Limitations of the Tier B Invited Beta Launch

1. **Scale-to-Zero Latency on Koyeb:**
   - Students initiating a session after an hour of platform inactivity will wait **1 to 5 seconds** while the Koyeb Nano container provisions and boots.
2. **Supabase 7-Day Inactivity Pausing:**
   - If the beta platform experiences zero traffic for 7 consecutive days, the Supabase project will automatically pause. Restoration requires a manual 1-click action in the Supabase dashboard.
3. **Absence of Point-in-Time Recovery:**
   - Disasters must be mitigated by executing the documented manual `pg_dump` backup weekly.
4. **Finite Database Headroom:**
   - While adequate for Beta V-001, feedback records are capped at ~50,000 entries before database capacity approaches the 500 MB ceiling.

---

## 6. Actionable Owner Decisions to Proceed

1. **Confirm Launch Tier:**
   - Confirm launch as **Tier B: Free Invited Beta** with accepted 1-hr sleep and manual backup trade-offs.
2. **Select Remote Free Inference Provider:**
   - Authorize using a free tier API key (e.g. Google Gemini 1.5 Flash Free Tier, 15 RPM free with no payment method) for the 50-student pilot, OR maintain **Mock Mode**.
3. **Authorize Cloudflare Domain Routing Reconfiguration:**
   - Authorize detaching `api.ai.peregrineacademy.in` from the Exams App Worker and re-routing it to the Koyeb Central API backend URL.
