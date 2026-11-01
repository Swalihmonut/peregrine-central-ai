# Dedicated Central API Gateway Worker Specification — Beta V-001
**Worker Name:** `peregrine-central-ai-gateway`  
**Target Domain:** `api.ai.peregrineacademy.in`  
**Backend Origin:** `https://peregrine-api.koyeb.app` (or Cloud Run URL)  
**Date:** 2026-11-01  
**Author:** Central API, Hosting and Infrastructure Engineer  
**Isolation Guarantee:** 100% Isolated from the existing Exams App Worker (`swalihmonut-arabic-academy-ai`)  

---

## 1. Architectural Role & Boundary

The `peregrine-central-ai-gateway` is a lightweight, zero-dependency Cloudflare Edge Worker designed to operate exclusively on `api.ai.peregrineacademy.in`.

```
[Browser / Client]
       │
       ▼ (HTTPS)
[api.ai.peregrineacademy.in]
Cloudflare Edge Worker: peregrine-central-ai-gateway
  ├── 1. Edge CORS Check (https://ai.peregrineacademy.in)
  ├── 2. Edge Body Size Check (Max 2 MB)
  ├── 3. Edge Rate Limiter (60 RPM sliding window per IP)
  ├── 4. Server-Side Secret Injection (Authorization: Bearer <SECRET>)
  ├── 5. Subrequest Timeout Interception (AbortController: 25s)
  └── 6. Streaming Proxy Pass-through
       │
       ▼ (Secure Upstream Subrequest)
[Koyeb Free Container: https://peregrine-api.koyeb.app]
Python Central AI Runtime (asgi.py)
```

---

## 2. Production Gateway Worker Source Code (`gateway.ts`)

```typescript
/**
 * Peregrine Central AI Gateway Worker
 * Production Edge Proxy & Security Layer
 * Domain: api.ai.peregrineacademy.in
 */

export interface Env {
  BACKEND_ORIGIN: string;        // e.g. "https://peregrine-api.koyeb.app"
  CENTRAL_AI_API_KEY: string;    // Injected via: wrangler secret put CENTRAL_AI_API_KEY
  CORS_ORIGIN: string;           // "https://ai.peregrineacademy.in"
  MAX_BODY_BYTES: number;        // 2097152 (2 MB)
  UPSTREAM_TIMEOUT_MS: number;   // 25000 (25s, safely under CF 30s limit)
}

// In-memory edge rate limiter per data center edge node
const ipRateMap = new Map<string, { count: number; resetTime: number }>();

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const clientIp = request.headers.get("CF-Connecting-IP") || "127.0.0.1";
    const origin = request.headers.get("Origin") || "";
    const requestId = request.headers.get("X-Request-ID") || `gw-${crypto.randomUUID().slice(0, 12)}`;

    // 1. CORS Preflight (OPTIONS)
    if (request.method === "OPTIONS") {
      return handleCorsPreflight(origin, env);
    }

    // 2. CORS Origin Validation
    const corsHeaders = getCorsHeaders(origin, env);

    // 3. Edge Rate Limiting (60 RPM per IP)
    const now = Date.now();
    const rateData = ipRateMap.get(clientIp) || { count: 0, resetTime: now + 60000 };
    if (now > rateData.resetTime) {
      rateData.count = 0;
      rateData.resetTime = now + 60000;
    }
    rateData.count++;
    ipRateMap.set(clientIp, rateData);

    const remaining = Math.max(0, 60 - rateData.count);
    const resetSeconds = Math.ceil((rateData.resetTime - now) / 1000);

    const rateHeaders = {
      "X-RateLimit-Limit": "60",
      "X-RateLimit-Remaining": String(remaining),
      "X-RateLimit-Reset": String(resetSeconds),
      "X-Request-ID": requestId,
    };

    if (rateData.count > 60) {
      return jsonError(429, "RATE_LIMIT_EXCEEDED", `Too many requests. Limit: 60 RPM. Retry in ${resetSeconds}s.`, {
        ...corsHeaders,
        ...rateHeaders,
      });
    }

    // 4. Body Size Limit Enforcement (2 MB)
    const contentLength = parseInt(request.headers.get("content-length") || "0", 10);
    if (contentLength > (env.MAX_BODY_BYTES || 2097152)) {
      return jsonError(413, "PAYLOAD_TOO_LARGE", `Request body exceeds 2 MB limit.`, {
        ...corsHeaders,
        ...rateHeaders,
      });
    }

    // 5. Construct Upstream Request
    const targetUrl = new URL(url.pathname + url.search, env.BACKEND_ORIGIN);
    const forwardHeaders = new Headers(request.headers);

    // Inject hidden backend authorization secret
    forwardHeaders.set("Authorization", `Bearer ${env.CENTRAL_AI_API_KEY}`);
    forwardHeaders.set("X-Forwarded-For", clientIp);
    forwardHeaders.set("X-Gateway-Trace", requestId);

    // 6. Upstream Fetch with 25s Timeout Shield
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), env.UPSTREAM_TIMEOUT_MS || 25000);

    try {
      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: forwardHeaders,
        body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Clone response and merge edge security headers
      const responseHeaders = new Headers(response.headers);
      for (const [k, v] of Object.entries(corsHeaders)) {
        responseHeaders.set(k, v);
      }
      for (const [k, v] of Object.entries(rateHeaders)) {
        responseHeaders.set(k, v);
      }

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    } catch (err: any) {
      clearTimeout(timeoutId);

      if (err.name === "AbortError") {
        return jsonError(504, "UPSTREAM_TIMEOUT", "Central AI upstream timed out after 25s (model reasoning delay).", {
          ...corsHeaders,
          ...rateHeaders,
        });
      }

      return jsonError(502, "UPSTREAM_UNAVAILABLE", `Failed to connect to Central AI backend: ${err.message}`, {
        ...corsHeaders,
        ...rateHeaders,
      });
    }
  },
};

function getCorsHeaders(origin: string, env: Env): Record<string, string> {
  const allowed = env.CORS_ORIGIN || "https://ai.peregrineacademy.in";
  const matched = origin === allowed || origin.startsWith("http://localhost:") ? origin : allowed;
  return {
    "Access-Control-Allow-Origin": matched,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
    "Vary": "Origin",
  };
}

function handleCorsPreflight(origin: string, env: Env): Response {
  return new Response(null, {
    status: 204,
    headers: {
      ...getCorsHeaders(origin, env),
      "Access-Control-Max-Age": "86400",
    },
  });
}

function jsonError(status: number, code: string, message: string, headers: Record<string, string>): Response {
  return new Response(
    JSON.stringify({
      status: "error",
      error: { code, message },
      timestamp: new Date().toISOString(),
    }),
    {
      status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        ...headers,
      },
    }
  );
}
```

---

## 3. Deployment Configuration (`wrangler.jsonc`)

```jsonc
{
  "name": "peregrine-central-ai-gateway",
  "main": "src/gateway.ts",
  "compatibility_date": "2026-10-31",
  "compatibility_flags": ["nodejs_compat"],
  "vars": {
    "BACKEND_ORIGIN": "https://peregrine-api.koyeb.app",
    "CORS_ORIGIN": "https://ai.peregrineacademy.in",
    "MAX_BODY_BYTES": 2097152,
    "UPSTREAM_TIMEOUT_MS": 25000
  },
  "routes": [
    {
      "pattern": "api.ai.peregrineacademy.in/*",
      "zone_name": "peregrineacademy.in"
    }
  ]
}
```

---

## 4. Security Verification

1. **Secret Leakage Prevention:** The student client communicates over public HTTPS with `https://api.ai.peregrineacademy.in`. The secret `CENTRAL_AI_API_KEY` is bound as an encrypted environment secret and is **never returned in response headers or client payloads**.
2. **Cold-Start Buffer:** If the Koyeb backend is waking up (1–5 seconds), the 25s AbortController keeps the connection open without prematurely timing out.
3. **No 524 HTML Error Pages:** If an upstream inference times out, the Worker intercepts the abort and returns structured JSON (`UPSTREAM_TIMEOUT`), preventing Cloudflare's default HTML error pages from breaking client parsers.
