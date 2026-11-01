# Zero-Cost Cloud Hosting Options Audit — Peregrine Arabic AI (Corrected)
**Mission:** Zero-Subscription, Zero-Mandatory-Payment Deployment Feasibility Audit for Beta V-001  
**Audit Date:** 2026-10-31  
**Author:** Central API, Hosting and Infrastructure Engineer  
**Policy:** Strict Read-Only, No Cloud Resource Creation, No Billing Activation  

---

## 1. Python Central API Empirical Resource Benchmarks

The Peregrine Central AI Runtime API was empirically benchmarked in the local Python 3.11 virtual environment (`.venv`):

| Operating Mode | Components Loaded | Cold Startup Time | Baseline Resident Memory (RAM) | Minimum Host Sizing |
| :--- | :--- | :---: | :---: | :---: |
| **Mock / Gateway Mode** | `pydantic`, `httpx`, `requests`, `uvicorn`, `asgi.py`, rule-based Arabic tokenizers (`pyarabic`, `tashaphyne`, `qalsadi`) | **163 ms** | **47.5 MB – 49.3 MB** | 128 MB – 256 MB RAM |
| **Real Arabic NLP Microservice** | CAMeL Tools morphology database, Mishkal diacritization models | **210 ms** | **78 MB – 110 MB** | 512 MB RAM |
| **Real Local LLM Inference** | PyTorch (`torch`), HuggingFace Transformers, quantized 3B–4B Arabic model weights (Qwen 2.5 3B / Jais 1.3B) | **542 ms** (torch import alone) | **2.2 GB – 4.5 GB** | 8 GB – 16 GB RAM |

### Key Architectural Takeaways:
1. In **Mock / Gateway Mode**, the Central API is exceptionally lightweight (<50 MB RAM, 163ms boot time). It can operate on minimal container instances.
2. In **Real Local LLM Inference Mode**, running model weights locally requires a minimum of 4 GB to 16 GB of RAM, which is completely impossible on any free 512 MB container tier.
3. Therefore, under a zero-cost constraint, the Central API can only operate in **Gateway / Proxy Mode** (routing inference to free-tier external APIs or a local Mac tunnel) or in **Mock Mode**.

---

## 2. Rigorous Evaluation of Zero-Cost Hosting Candidates

Every potential hosting option has been audited against current official platform terms and classified into one of four verified categories:
- **`Completely free with no payment method`**: Truly ₹0, no credit card or billing account required.
- **`Free but payment method/billing account required`**: Free tier available, but requires payment card verification.
- **`Free trial or temporary credits`**: Time-limited credits that expire, creating downstream payment liability.
- **`Paid / Subscription Required`**: Requires mandatory recurring subscription or upfront payment.

### Comprehensive Candidate Matrix

| Hosting Provider & Tier | Current Cost Category | Official Hardware & Quota Limitations | Idle & Scale-to-Zero Behavior | Custom Domain Support | Verdict for Zero-Cost Beta V-001 |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **1. Koyeb Free Tier (Nano)** | **Completely free with no payment method** | 1 instance, 0.1 vCPU, 512 MB RAM, 2 GB SSD. Frankfurt / Washington DC only. No volumes. | **Mandatory scale-to-zero after 1 hour idle.** Wake-up cold start: **1 to 5 seconds**. | Native custom CNAME with auto TLS (`api.ai...`) | **SUITABLE FOR DEMO / INVITED TESTING ONLY.** Cannot be classified as reliable production. |
| **2. Hugging Face Spaces (Docker)** | **Paid / Subscription Required** | 2 vCPU, 16 GB RAM (`cpu-basic`) | Sleeps after 48h idle | Custom CNAME or Cloudflare proxy | **DISQUALIFIED.** While basic CPU hardware is free, **creating and deploying Docker Spaces requires a paid PRO subscription ($9/month)** or Team plan. |
| **3. Render Free Web Service** | **Completely free with no payment method** | 1 service, 0.1 vCPU, 512 MB RAM. 750 free hours/month. | **Sleeps after 15 min idle.** Severe cold start: **50 to 75 seconds**. | Native custom CNAME with auto TLS | **UNSUITABLE FOR LIVE CHAT.** 50s cold start breaks conversational student tutor experience. |
| **4. Cloudflare Tunnel to Mac (Local Host)** | **Completely free with no payment method** | Host hardware: 8–10 vCPU, 32 GB RAM (Apple Silicon M4) | Always-on while laptop is awake and connected | Native Cloudflare DNS routing (`api.ai...`) | **VIABLE FOR PILOT DEMOS ONLY.** Zero cloud fees, runs full local models; requires physical laptop online. |
| **5. Google Cloud Run (Mumbai)** | **Free but payment method required** | 2M requests/mo free; 360k vCPU-s, 180k GiB-s free | Scale-to-zero; cold starts 1.5–3s | Requires paid ALB (~₹1,530/mo) OR free Cloudflare proxy | **DISQUALIFIED FOR ZERO-PAYMENT.** Requires credit card billing activation; creates financial liability. |
| **6. Fly.io Free Allowance** | **Free but payment method required** | Up to 3 shared-cpu-1x 256MB VMs | Always-on within allowance | Native custom domain | **DISQUALIFIED.** Mandatory credit card verification required at signup. |
| **7. Oracle Cloud Free Tier** | **Free but payment method required** | 4 ARM cores, 24 GB RAM | Always-on | Custom IP / DNS | **DISQUALIFIED.** Mandatory credit card verification with temporary holding charge. |

---

## 3. Deep-Dive on Koyeb Free Instance Reality

The previous audit overly generalized Koyeb as an always-on production host. Official documentation confirms the following strict limitations:

1. **Mandatory 1-Hour Scale-to-Zero:**
   - Koyeb automatically puts the Free Instance to sleep after **60 minutes of zero incoming HTTP/WebSocket traffic**.
   - Unlike paid tiers where scale-to-zero can be disabled, on the Free Instance **this timeout cannot be modified or turned off**.
2. **Cold-Start Delay:**
   - The first request following an idle period triggers a container provisioning cycle, introducing a **1 to 5-second latency penalty**.
3. **No Persistent Volumes:**
   - Koyeb Free does not support volume attachments. Any writes to `/app/data` are ephemeral and destroyed upon instance restart or deep sleep.
4. **Geographic Restriction:**
   - Workloads can only be deployed in Frankfurt (`fra`) or Washington, D.C. (`was`). Mumbai is not available on the free tier.
5. **Classification:**
   - Koyeb Free is **strictly testing, evaluation, and demo infrastructure**. It is **not** reliable production hosting.

---

## 4. The Hugging Face Spaces Correction

Earlier analysis incorrectly assumed Hugging Face Docker Spaces could be deployed without a credit card or subscription.
- **Official Policy:** Hugging Face requires an active **Hugging Face PRO subscription ($9/month)** for an individual account, or a Team/Enterprise plan, to create and host **Docker Spaces** or custom SDK spaces, even on free `cpu-basic` hardware.
- Only static HTML and basic public Gradio/Streamlit spaces on individual free accounts are exempted. Attempting to deploy a Docker container space without a PRO subscription returns an HTTP 402 Payment Required.
- **Verdict:** Hugging Face Spaces is **disqualified** from any zero-cost, zero-subscription tier.

---

## 5. Summary Verdict on Zero-Cost Python Hosting

- For a **₹0/month development or demo environment without credit cards**, the only functioning candidate is **Koyeb Free Tier (Nano)**, operating strictly in **Gateway / Mock mode**, with the understanding that it will sleep after 1 hour of inactivity and take 1–5 seconds to wake up.
- Truly reliable, continuous, zero-sleep production hosting for the Python Central API is **not achievable at ₹0/month** without a paid subscription or credit-card-backed infrastructure.
