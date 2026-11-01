# Cloudflare Worker & Central API Compatibility Analysis (Corrected)
**Domain Inspected:** `api.ai.peregrineacademy.in` & `exams-app.peregrineacademy.in`  
**Worker Identified:** `swalihmonut-arabic-academy-ai`  
**Worker Project Source:** `/Users/muhammedswaliht/arabic-academy-ai`  
**Target Routing Host:** `api.ai.peregrineacademy.in`  
**Frontend Host:** `ai.peregrineacademy.in`  
**Audit Date:** 2026-10-31  

---

## 1. Live Domain Ownership & Routing Discovery

A live HTTP/DNS probe of the Peregrine Academy domains revealed critical routing realities:

```bash
curl -sI https://api.ai.peregrineacademy.in/
# Status: HTTP/2 200 OK | Server: cloudflare | Content-Type: text/html; charset=utf-8
# Title: "Arabic for every examination — Arabic Academy AI"
```

### Empirical Findings:
1. **Wrong Application Currently Bound to Approved Hostname:**
   - The approved Central API hostname `api.ai.peregrineacademy.in` is **currently serving the Exams App frontend** (`Arabic Academy AI`).
   - Both `api.ai.peregrineacademy.in` and `exams-app.peregrineacademy.in` are routed by Cloudflare DNS to the exact same Cloudflare Worker: `swalihmonut-arabic-academy-ai`.
   - The hostname does **not** currently serve the Central AI Runtime API.
2. **Frontend Domain (`ai.peregrineacademy.in`) Status:**
   - A probe to `https://ai.peregrineacademy.in/` currently returns **HTTP/2 502 Bad Gateway**, indicating that the origin server or Pages deployment for the main AI suite frontend is currently offline or unconfigured.
3. **Domain Attachment Policy:**
   - In accordance with audit instructions, **no domain attachments, routes, or DNS records have been modified**. The domain attachment remains untouched.

---

## 2. Distinguishing the Existing Worker from the Central API Gateway

| Dimension | Existing Exams App Worker (`swalihmonut-arabic-academy-ai`) | Intended Central AI Gateway Worker |
| :--- | :--- | :--- |
| **Source Location** | `/Users/muhammedswaliht/arabic-academy-ai` | Not yet created (to be created in `peregrine-arabic-ai-lab`) |
| **Framework** | TanStack Start / Nitro SSR / React 19 | Lightweight pure TypeScript / Cloudflare Worker router |
| **Current Function** | Full web UI for UGC-NET / Kerala PSC exams, questions, syllabus | Edge reverse-proxy, auth injection, and rate limiting |
| **Current Hostnames** | `exams-app.peregrineacademy.in` & `api.ai.peregrineacademy.in` | Should be dedicated exclusively to `api.ai.peregrineacademy.in` |
| **Conflict** | `api.ai` intercepts API calls with HTML pages. | Requires decoupling `api.ai` from the Exams App Worker. |

---

## 3. Secure Edge Proxying Without Exposing Secrets

Can a Cloudflare Worker proxy authenticated requests to a separately hosted Python Central API without leaking credentials?

**YES, using Cloudflare Worker Encrypted Secrets:**
1. **Secret Storage:** The gateway key is stored in Cloudflare's encrypted key management using:
   ```bash
   wrangler secret put CENTRAL_AI_API_KEY
   ```
2. **Server-Side Injection:** The student browser calls `https://api.ai.peregrineacademy.in/api/v1/chat` with their user Supabase JWT:
   ```javascript
   // Inside Worker fetch handler (Edge compute)
   export default {
     async fetch(request, env) {
       const url = new URL(request.url);
       
       // 1. Validate student session via Supabase JWT (optional edge auth)
       const userToken = request.headers.get("Authorization");
       
       // 2. Clone request and inject hidden Central API key
       const backendUrl = new URL(url.pathname, env.PYTHON_API_ORIGIN); // e.g. Koyeb/Cloud Run URL
       const modifiedHeaders = new Headers(request.headers);
       modifiedHeaders.set("Authorization", `Bearer ${env.CENTRAL_AI_API_KEY}`);
       modifiedHeaders.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP"));
       
       // 3. Dispatch subrequest to Python backend
       return fetch(backendUrl.toString(), {
         method: request.method,
         headers: modifiedHeaders,
         body: request.body,
       });
     }
   }
   ```
3. **Security Assurance:** The student client and browser DevTools only see communication with `https://api.ai.peregrineacademy.in`. The backend service token (`CENTRAL_AI_API_KEY`) is injected entirely within Cloudflare's secure edge isolation and is **never transmitted to or readable by the client**.

---

## 4. Next.js, TanStack SSR, and Cloudflare Pages Compatibility Limitations

The Peregrine Arabic AI suite contains two frontend codebases:
1. `Developer/peregrine-arabic-ai-mvp`: Next.js 15 (React 19).
2. `arabic-academy-ai`: TanStack Start (Nitro SSR).

### 4.1 Cloudflare Pages Compatibility Evaluation

| Framework & Architecture | Deployment Target on Cloudflare | Technical Compatibility & Limitations |
| :--- | :--- | :--- |
| **Static Next.js Export (`output: 'export'`)** | **Cloudflare Pages (Direct Upload)** | **100% COMPATIBLE & RECOMMENDED.** Compiles to pure static HTML/CSS/JS. Served via Cloudflare global CDN with zero execution limits, unlimited bandwidth, and zero cost. |
| **Dynamic Next.js SSR (App Router)** | **Cloudflare Pages (with OpenNext)** | **MODERATE RISK.** Next.js App Router relies heavily on Node.js runtime APIs. On Cloudflare edge workers, streaming responses, complex middleware, and Node built-ins can encounter runtime exceptions or exceed the 10ms CPU limit. |
| **TanStack Start SSR (`arabic-academy-ai`)** | **Cloudflare Workers (Nitro Preset)** | **COMPATIBLE BUT SENSITIVE.** Currently deployed as `swalihmonut-arabic-academy-ai`. Subject to the strict 10ms CPU limit per request on the Free plan. As documented in the 1101 incident report, unresolved promise chains or long async loops terminate the worker. |

---

## 5. Required Owner Remediations Before Cloud Launch

1. **Decouple `api.ai.peregrineacademy.in` from the Exams App Worker:**
   - In Cloudflare Dashboard, remove `api.ai.peregrineacademy.in` from the `swalihmonut-arabic-academy-ai` worker route list.
   - Point `api.ai.peregrineacademy.in` to the dedicated Central API gateway or container backend.
2. **Resolve `ai.peregrineacademy.in` 502 Error:**
   - Configure the Cloudflare Pages deployment for the redesigned Peregrine Arabic AI MVP frontend to serve `ai.peregrineacademy.in`.
