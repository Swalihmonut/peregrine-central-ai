# Cloud Run Cost Analysis & Custom Domain Routing Options
**Domain Target:** `api.ai.peregrineacademy.in`  
**DNS Manager:** Cloudflare  
**Target Region:** Mumbai (`asia-south1`)  
**Target Service:** `peregrine-central-ai-api`  

---

## 1. Cloud Run Compute Cost Analysis (Mumbai `asia-south1`)

Google Cloud Run operates on a pay-per-use model with a permanent monthly free tier.

### 1.1 Google Cloud Free Tier Allowance (Every Month)
Every Google Cloud billing account receives the following **free monthly tier**:
- **Requests:** 2,000,000 requests per month.
- **Compute:** 360,000 vCPU-seconds per month.
- **Memory:** 180,000 GiB-seconds per month.
- **Network Egress:** 1 GiB per month to any destination.

### 1.2 Cost Simulation for Peregrine Arabic AI Beta V-001 (Scale-to-Zero)

| Usage Metric | Expected Staging Volume | Free Allowance Consumed | Billable Units | Cost (USD) | Cost (INR approx.) |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Total Monthly Requests** | 50,000 requests | 2.5% of 2,000,000 | 0 | $0.00 | ₹0.00 |
| **Average Request Duration** | 1.5 seconds | — | — | — | — |
| **vCPU Consumption (1 vCPU)** | 75,000 vCPU-seconds | 20.8% of 360,000 | 0 | $0.00 | ₹0.00 |
| **Memory Consumption (1 GiB)**| 75,000 GiB-seconds | 41.6% of 180,000 | 0 | $0.00 | ₹0.00 |
| **Idle Instances (min=0)** | 0 idle instances | N/A | 0 | $0.00 | ₹0.00 |
| **Total Monthly Compute** | — | — | **0** | **$0.00** | **₹0.00** |

> **Crucial Finding:** The raw Cloud Run compute for Beta V-001 in scale-to-zero mode is **100% covered by the free tier**. However, an active Google Cloud Billing account (with credit card verification) is mandatory to create Cloud Run services.

---

## 2. Production Custom Domain Routing Options

The approved hostname is `api.ai.peregrineacademy.in`. Cloudflare manages DNS for `peregrineacademy.in`.

In the Mumbai (`asia-south1`) region, Cloud Run does **not** support direct domain mapping (direct domain mappings are in preview and restricted to limited regions such as `us-central1` and `europe-west1`).

The three viable architectural paths for routing `api.ai.peregrineacademy.in` to Cloud Run are evaluated below:

### Option A: Cloudflare Edge Reverse Proxy to Cloud Run (Recommended & Zero Cost)
- **Architecture:** Cloudflare DNS CNAME pointing to the Cloud Run default service URL (e.g., `peregrine-central-ai-api-xyz-as.a.run.app`), with Cloudflare Orange Cloud (Proxy) enabled.
- **TLS Termination:** Handled automatically by Cloudflare Universal SSL (free edge certificate) + Cloud Run automatic HTTPS certificate.
- **Cost:**
  - Cloudflare Proxy: **$0.00 / month (₹0)**
  - Cloud Run Ingress: **$0.00 / month (₹0)**
  - Total Recurring Cost: **₹0.00 / month**
- **Limitations:** Cloudflare Workers Free enforces a 10ms CPU limit for custom scripts; however, basic DNS CNAME proxying does **not** consume Worker CPU limits.

### Option B: Firebase Hosting Rewrites to Cloud Run (Google-Native Zero Cost)
- **Architecture:** Create a Firebase project linked to the Google Cloud project. Add a custom domain `api.ai.peregrineacademy.in` in Firebase Hosting, and configure `firebase.json` with a rewrite to Cloud Run:
  ```json
  "rewrites": [{ "source": "/**", "run": { "serviceId": "peregrine-central-ai-api", "region": "asia-south1" } }]
  ```
- **TLS Termination:** Managed automatically and freely by Google/Let's Encrypt through Firebase.
- **Cost:**
  - Firebase Spark Plan: **$0.00 / month (₹0)** (includes custom domains, SSL, and 10 GB/month egress).
  - Total Recurring Cost: **₹0.00 / month**
- **Limitations:** Requires linking Firebase Hosting to the GCP project.

### Option C: Global External Application Load Balancer (Enterprise & Paid)
- **Architecture:** Cloud Run Serverless Network Endpoint Group (NEG) attached to a Google Cloud Global External HTTP(S) Application Load Balancer.
- **TLS Termination:** Google-managed SSL certificate on the Load Balancer.
- **Cost:**
  - Global Forwarding Rule: $0.025 per hour for the first 5 rules.
  - **Mandatory Base Charge:** 730 hours × $0.025 = **~$18.25 / month (~₹1,530 / month)** even with ZERO traffic.
  - Data processing: $0.008 / GB.
- **Limitations:** Violates the zero-cost mandate. Not recommended for Beta V-001 staging.

---

## 3. Comprehensive Cost & Feasibility Comparison

| Metric / Dimension | Option A: Cloudflare Proxy (Recommended) | Option B: Firebase Rewrites | Option C: Google External ALB |
| :--- | :---: | :---: | :---: |
| **Mandatory Monthly Fixed Fee** | **₹0.00 ($0.00)** | **₹0.00 ($0.00)** | **~₹1,530 ($18.25)** |
| **Setup Complexity** | Low (Single CNAME in Cloudflare) | Medium (CLI setup) | High (VPC, NEG, SSL, LB) |
| **Latency Impact** | Edge cached / Anycast routing | Anycast CDN routing | Direct Google Anycast |
| **TLS Certificate Issuance** | Automatic via Cloudflare | Automatic via Google | Automatic via Google |
| **Vendor Lock-in** | Zero | Medium (Google/Firebase) | High (GCP ALB) |
| **Suitability for Beta V-001** | **BEST MATCH** | **VIABLE ALTERNATIVE** | **DISQUALIFIED (PAID)** |

---

## 4. Strict DNS Record Protocol

**STRICT COMPLIANCE DIRECTIVE:**  
No DNS `A` record or `CNAME` target may be invented or pre-configured in Cloudflare. The exact target will be generated exclusively when the service is provisioned:

1. **For Option A (Cloudflare Proxy):**
   - The target will be the exact Cloud Run generated service URL (e.g. `peregrine-central-ai-api-<hash>-as.a.run.app`).
   - The record added to Cloudflare will be:
     `CNAME api.ai -> peregrine-central-ai-api-<hash>-as.a.run.app (Proxied / Orange Cloud)`
2. **For Option B (Firebase Hosting):**
   - Firebase Hosting dashboard will provide two dedicated Google Anycast `A` records (e.g. `199.36.158.100`).
   - Only those exact IP addresses will be input into Cloudflare.
