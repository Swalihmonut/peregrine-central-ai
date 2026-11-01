import { createClient } from "@supabase/supabase-js";
import { createHash } from "node:crypto";
//#region server/payment.ts
function cleanEnvValue(value) {
	if (!value || typeof value !== "string") return "";
	return value.trim().replace(/^["']|["']$/g, "").trim();
}
function isServerTestMode() {
	return cleanEnvValue(process.env.RAZORPAY_KEY_ID).startsWith("rzp_test_");
}
async function getAuthenticatedUser(supabase, token) {
	if (!supabase || !token) return null;
	const authResponse = await (supabase.auth.getUser ? supabase.auth.getUser(token) : supabase.auth.api.getUser(token));
	const user = authResponse?.data?.user || authResponse?.user || authResponse?.data;
	if (authResponse?.error || !user) return null;
	return user;
}
var AI_TUTOR_MAX_CONTEXT_LENGTH = 2e4;
var AI_TUTOR_MAX_HISTORY_MESSAGE_LENGTH = 2e3;
function getAiProEnvironment() {
	return isServerTestMode() ? "test" : "live";
}
function getAiProDailyTurnLimit() {
	const raw = cleanEnvValue(process.env.AI_PRO_DAILY_TURN_LIMIT);
	if (!raw) return {
		configured: false,
		invalid: false,
		limit: null
	};
	if (!/^\d+$/.test(raw)) return {
		configured: false,
		invalid: true,
		limit: null
	};
	const limit = Number(raw);
	if (!Number.isInteger(limit) || limit < 1 || limit > 1e4) return {
		configured: false,
		invalid: true,
		limit: null
	};
	return {
		configured: true,
		invalid: false,
		limit
	};
}
function getAiTutorRateLimitPerMinute() {
	const raw = cleanEnvValue(process.env.AI_TUTOR_RATE_LIMIT_PER_MINUTE);
	if (!raw || !/^\d+$/.test(raw)) return 12;
	const limit = Number(raw);
	if (!Number.isInteger(limit) || limit < 1 || limit > 120) return 12;
	return limit;
}
function evaluateAiProEntitlement(rows, now = Date.now()) {
	const sorted = [...rows].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
	const active = sorted.find((row) => {
		const starts = Date.parse(row.starts_at);
		const expires = Date.parse(row.expires_at);
		return row.status === "active" && Number.isFinite(starts) && Number.isFinite(expires) && starts <= now && expires > now;
	});
	if (active) return {
		state: "active",
		entitlement: active
	};
	const latest = sorted[0] ?? null;
	if (!latest) return {
		state: "inactive",
		entitlement: null
	};
	if (latest.status === "revoked") return {
		state: "revoked",
		entitlement: latest
	};
	if (Date.parse(latest.expires_at) <= now) return {
		state: "expired",
		entitlement: latest
	};
	return {
		state: "inactive",
		entitlement: latest
	};
}
async function getAiProDecision(supabase, authId, environment, now = Date.now()) {
	const { data, error } = await supabase.from("ai_pro_entitlements").select("id, plan_key, environment, status, starts_at, expires_at, revoked_at, created_at").eq("auth_id", authId).eq("environment", environment).order("created_at", { ascending: false }).limit(20);
	if (error) throw new Error(error.message);
	return evaluateAiProEntitlement(data ?? [], now);
}
var AI_TUTOR_QUOTA_RESETS_AT = () => {
	const now = /* @__PURE__ */ new Date();
	return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0, 0)).toISOString();
};
function isValidAiTutorRequestId(requestId) {
	return Boolean(requestId && /^[A-Za-z0-9_-]{8,120}$/.test(requestId));
}
function hashAiTutorRequest(authId, kind, payload) {
	return createHash("sha256").update(JSON.stringify({
		authId,
		kind,
		payload
	})).digest("hex");
}
async function reserveAiTutorRequest(supabase, { authId, requestId, requestHash, kind, isPro, dailyLimit, rateLimitPerMinute }) {
	const { data, error } = await supabase.rpc("reserve_ai_tutor_request", {
		p_auth_id: authId,
		p_request_id: requestId,
		p_request_hash: requestHash,
		p_kind: kind,
		p_is_pro: isPro,
		p_daily_limit: dailyLimit,
		p_rate_limit_per_minute: rateLimitPerMinute
	});
	if (error) throw new Error(error.message);
	const row = Array.isArray(data) ? data[0] : data;
	if (!row) throw new Error("Quota reservation returned no result.");
	return {
		allowed: row.allowed === true,
		reason: String(row.reason ?? "unknown"),
		used: Number(row.used ?? 0),
		limit_value: row.limit_value === null || row.limit_value === void 0 ? null : Number(row.limit_value),
		remaining: row.remaining === null || row.remaining === void 0 ? null : Number(row.remaining),
		idempotent: row.idempotent === true,
		in_progress: row.in_progress === true,
		response_payload: row.response_payload ?? null
	};
}
async function storeAiTutorResponse(supabase, authId, requestId, payload) {
	const { error } = await supabase.from("ai_tutor_requests").update({
		response_payload: payload,
		completed_at: (/* @__PURE__ */ new Date()).toISOString()
	}).eq("auth_id", authId).eq("request_id", requestId);
	return !error;
}
async function releaseAiTutorRequest(supabase, authId, requestId, requestHash) {
	const { error } = await supabase.from("ai_tutor_requests").delete().eq("auth_id", authId).eq("request_id", requestId).eq("request_hash", requestHash).is("completed_at", null);
	return !error;
}
function quotaFromReservation(reservation, isPro) {
	return {
		used: reservation.used,
		limit: reservation.limit_value,
		remaining: reservation.remaining,
		resets_at: AI_TUTOR_QUOTA_RESETS_AT(),
		is_pro: isPro
	};
}
//#endregion
//#region server/api/khaliji-telemetry.ts
var TELEMETRY_BUFFER_SIZE = 200;
var telemetryBuffer = [];
function recordChatTelemetry(record) {
	try {
		telemetryBuffer.push(record);
		if (telemetryBuffer.length > TELEMETRY_BUFFER_SIZE) telemetryBuffer.shift();
	} catch (err) {
		console.error("Failed to append to in-memory telemetry buffer:", err);
	}
}
//#endregion
//#region server/api/khaliji-chat.ts
function bearerToken(req) {
	return req.headers.authorization?.match(/^Bearer\s+(.+)$/i)?.[1];
}
function quotaError(res, reservation, isPro, status, code, message) {
	return res.status(status).json({
		error: message,
		code,
		quota: quotaFromReservation(reservation, isPro)
	});
}
async function khalijiChatHandler(req, res, dependencies = {}) {
	res.setHeader("Cache-Control", "no-store");
	if (req.method !== "POST") {
		res.setHeader("Allow", "POST");
		return res.status(405).json({ error: "Method not allowed. Use POST." });
	}
	try {
		const declaredLength = Number(req.headers["content-length"] ?? 0);
		const body = req.body || {};
		if (Number.isFinite(declaredLength) && declaredLength > 65e5 || JSON.stringify(body).length > 65e5) return res.status(413).json({ error: "Request is too large." });
		const token = bearerToken(req);
		if (!token) return res.status(401).json({ error: "Your session is invalid. Please sign in again." });
		const supabaseUrl = cleanEnvValue(process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL);
		const supabaseAnonKey = cleanEnvValue(process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || process.env.VITE_SUPABASE_ANON_KEY);
		const serviceRoleKey = cleanEnvValue(process.env.SUPABASE_SERVICE_ROLE_KEY);
		const secretKey = cleanEnvValue(process.env.SUPABASE_SECRET_KEY);
		const privilegedKey = serviceRoleKey || (secretKey.startsWith("sb_secret_") ? secretKey : "") || "";
		if (!supabaseUrl || !supabaseAnonKey || !privilegedKey) {
			console.error("[khaliji-chat] Server Supabase configuration is missing.");
			return res.status(503).json({ error: "AI Tutor access could not be checked right now." });
		}
		const makeClient = dependencies.createClient ?? createClient;
		const authClient = makeClient(supabaseUrl, supabaseAnonKey, { auth: {
			persistSession: false,
			autoRefreshToken: false
		} });
		const user = await (dependencies.getUser ?? getAuthenticatedUser)(authClient, token);
		if (!user) return res.status(401).json({ error: "Your session is invalid. Please sign in again." });
		const privilegedClient = makeClient(supabaseUrl, privilegedKey, { auth: {
			persistSession: false,
			autoRefreshToken: false
		} });
		const mode = body.mode || "chat";
		if (mode !== "chat" && mode !== "transcribe") return res.status(400).json({ error: "Unsupported AI Tutor mode." });
		const headerRequestId = req.headers["x-request-id"];
		const requestId = body.requestId || body.request_id || (typeof headerRequestId === "string" ? headerRequestId : void 0);
		if (!isValidAiTutorRequestId(requestId)) return res.status(400).json({
			error: "A valid requestId is required for AI Tutor requests.",
			code: "INVALID_REQUEST_ID"
		});
		const message = typeof body.message === "string" ? body.message.trim() : "";
		const scenarioId = String(body.scenarioId ?? "general").slice(0, 120);
		const rawLesson = Number(body.activeLesson ?? 1);
		const activeLesson = Number.isInteger(rawLesson) && rawLesson >= 1 && rawLesson <= 80 ? rawLesson : 1;
		const gender = body.gender === "female" ? "female" : "male";
		const magContext = String(body.magContext ?? "").slice(0, AI_TUTOR_MAX_CONTEXT_LENGTH);
		const ragBookContext = String(body.ragBookContext ?? "").slice(0, AI_TUTOR_MAX_CONTEXT_LENGTH);
		const history = (Array.isArray(body.history) ? body.history : []).filter((item) => (item?.role === "user" || item?.role === "assistant") && typeof item.content === "string" && item.content.trim()).slice(-6).map((item) => ({
			role: item.role,
			content: String(item.content).trim().slice(0, AI_TUTOR_MAX_HISTORY_MESSAGE_LENGTH)
		}));
		let audioBase64 = "";
		if (mode === "transcribe") {
			audioBase64 = typeof body.audioBase64 === "string" ? body.audioBase64 : "";
			if (!audioBase64) return res.status(400).json({ error: "Missing audioBase64 for transcription." });
			if (audioBase64.length > 6e6) return res.status(413).json({ error: "Audio recording is too large." });
		} else {
			if (!message) return res.status(400).json({ error: "Missing message content." });
			if (message.length > 1200) return res.status(400).json({ error: "Message is too long." });
		}
		const apiKey = cleanEnvValue(process.env.GROQ_API_KEY);
		if (!apiKey) {
			console.error("[khaliji-chat] GROQ_API_KEY is not configured on the server.");
			return res.status(503).json({ error: "AI Tutor service is not configured." });
		}
		const environment = getAiProEnvironment();
		const isPro = (await (dependencies.getDecision ?? getAiProDecision)(privilegedClient, user.id, environment)).state === "active";
		const proLimit = getAiProDailyTurnLimit();
		const dailyLimit = isPro ? proLimit.limit : 10;
		if (isPro && !proLimit.configured) {
			console.error("[khaliji-chat] AI Pro daily turn limit is missing or invalid.");
			return res.status(503).json({
				error: "AI Pro access is not fully configured. Please contact support.",
				code: "PRO_QUOTA_NOT_CONFIGURED"
			});
		}
		const canonicalPayload = mode === "transcribe" ? { audioBase64 } : {
			message,
			scenarioId,
			activeLesson,
			gender,
			magContext,
			ragBookContext,
			history
		};
		const requestHash = hashAiTutorRequest(user.id, mode, canonicalPayload);
		const reservation = await (dependencies.reserve ?? reserveAiTutorRequest)(privilegedClient, {
			authId: user.id,
			requestId,
			requestHash,
			kind: mode,
			isPro,
			dailyLimit,
			rateLimitPerMinute: getAiTutorRateLimitPerMinute()
		});
		if (!reservation.allowed) {
			if (reservation.reason === "idempotency_conflict") return res.status(409).json({
				error: "This requestId was already used for a different request.",
				code: "IDEMPOTENCY_CONFLICT"
			});
			if (reservation.reason === "rate_limited") {
				res.setHeader("Retry-After", "60");
				return quotaError(res, reservation, isPro, 429, "RATE_LIMITED", "Too many AI Tutor requests. Please wait a moment and try again.");
			}
			if (reservation.reason === "free_daily_limit") return quotaError(res, reservation, isPro, 429, "FREE_DAILY_LIMIT_REACHED", "You have used today's free AI Tutor turns. AI Pro unlocks more daily practice.");
			if (reservation.reason === "pro_daily_limit") return quotaError(res, reservation, isPro, 429, "PRO_DAILY_LIMIT_REACHED", "You have reached today's AI Pro practice limit. It resets at midnight UTC.");
			if (reservation.reason === "quota_not_configured") return res.status(503).json({
				error: "AI Tutor access is not fully configured. Please contact support.",
				code: "PRO_QUOTA_NOT_CONFIGURED"
			});
			return quotaError(res, reservation, isPro, 429, "AI_TUTOR_LIMIT_REACHED", "AI Tutor requests are temporarily limited. Please try again later.");
		}
		if (reservation.idempotent) {
			if (reservation.response_payload) return res.status(200).json({
				...reservation.response_payload,
				request_id: requestId,
				quota: quotaFromReservation(reservation, isPro)
			});
			return res.status(409).json({
				error: "This AI Tutor request is already being processed.",
				code: "REQUEST_IN_PROGRESS",
				quota: quotaFromReservation(reservation, isPro)
			});
		}
		const fetchFn = dependencies.fetch ?? fetch;
		const storeFn = dependencies.store ?? storeAiTutorResponse;
		const releaseFn = dependencies.release ?? releaseAiTutorRequest;
		const quota = quotaFromReservation(reservation, isPro);
		if (mode === "transcribe") try {
			const buffer = Buffer.from(audioBase64.replace(/^data:audio\/\w+;base64,/, ""), "base64");
			if (!buffer.length) {
				await releaseFn(privilegedClient, user.id, requestId, requestHash);
				return res.status(400).json({ error: "Audio recording is invalid." });
			}
			const boundary = "----WebKitFormBoundary" + Math.random().toString(36).substring(2);
			const formBody = Buffer.concat([
				Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-large-v3-turbo\r\n--${boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nar\r\n--${boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\nلهجة خليجية إماراتية: يا هلا، شحالك، زين، باجر، عيل، ما قصرت، فالك طيب\r\n--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.webm"\r\nContent-Type: audio/webm\r\n\r\n`),
				buffer,
				Buffer.from(`\r\n--${boundary}--\r\n`)
			]);
			const whisperResp = await fetchFn("https://api.groq.com/openai/v1/audio/transcriptions", {
				method: "POST",
				headers: {
					Authorization: `Bearer ${apiKey}`,
					"Content-Type": `multipart/form-data; boundary=${boundary}`
				},
				body: formBody
			});
			if (!whisperResp.ok) {
				console.error("[khaliji-chat] Groq Whisper transcription failed:", whisperResp.status);
				await releaseFn(privilegedClient, user.id, requestId, requestHash);
				return res.status(502).json({ error: "Speech transcription failed. Please try again." });
			}
			const payload = { transcript: (await whisperResp.json()).text || "" };
			if (!await storeFn(privilegedClient, user.id, requestId, payload)) console.error("[khaliji-chat] Could not store transcription result.");
			return res.status(200).json({
				...payload,
				request_id: requestId,
				quota
			});
		} catch (err) {
			console.error("[khaliji-chat] Transcription error:", err);
			await releaseFn(privilegedClient, user.id, requestId, requestHash);
			return res.status(500).json({ error: "Audio transcription failed. Please try again." });
		}
		const messages = [
			{
				role: "system",
				content: `You are ${gender === "female" ? "Maryam (مريم)" : "Rashid (راشد)"}, an authentic native Emirati Arabic tutor for the textbook "Khaliji Arabic Through Stories" (Arabic Peregrine Academy).

MANDATORY RULES:
1. Always respond in authentic Emirati Khaliji dialect (اللهجة الإماراتية / الخليجية). NEVER speak in stiff Modern Standard Arabic (Fusha).
2. Incorporate 1-2 expressions from the provided <book_curriculum_context> below, matching the student's current Lesson ${activeLesson}.
3. Check the <student_memory_graph> below. If the student has weak pronunciation words, naturally prompt or use one of those words so they get practice.
4. Keep replies natural, supportive, and conversational (2-3 sentences max).
5. Output MUST BE strictly valid JSON matching this schema:
{
  "reply_display_arabic": "Your response in natural Arabic script",
  "reply_tts_phonetic": "Fully vocalized Emirati phonetic script with full tashkeel and terminal sukoons (تسكين أواخر الكلمات) for edge-tts",
  "reply_english": "Natural English translation",
  "rag_book_reference": "Lesson X, Section B/F: [Matched Expression from Book]",
  "mag_memory_note": "Short rationale for chosen vocabulary or feedback",
  "feedback_tip": "1-sentence constructive cultural or dialect tip",
  "suggested_replies": ["Short natural Emirati reply 1", "Short natural Emirati reply 2"]
}

${ragBookContext}

${magContext}
`
			},
			...history.map((h) => ({
				role: h.role,
				content: h.content
			})),
			{
				role: "user",
				content: message
			}
		];
		const models = [
			"allam-2-7b",
			"openai/gpt-oss-120b",
			"qwen/qwen3.8-27b",
			"openai/gpt-oss-20b"
		];
		let lastError = null;
		const startTime = Date.now();
		for (const model of models) try {
			const groqResp = await fetchFn("https://api.groq.com/openai/v1/chat/completions", {
				method: "POST",
				headers: {
					Authorization: `Bearer ${apiKey}`,
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					model,
					messages,
					temperature: .5,
					response_format: { type: "json_object" }
				})
			});
			if (!groqResp.ok) {
				const errorText = await groqResp.text();
				lastError = errorText;
				console.error(`Groq API Chat Error [${model}] (Status ${groqResp.status}):`, errorText);
				continue;
			}
			const rawContent = (await groqResp.json()).choices?.[0]?.message?.content;
			if (!rawContent) throw new Error(`Empty response content from model ${model}`);
			let cleanedJson = String(rawContent).trim();
			if (cleanedJson.startsWith("```")) cleanedJson = cleanedJson.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "");
			const parsed = JSON.parse(cleanedJson);
			const payload = {
				success: true,
				modelUsed: model,
				...parsed
			};
			try {
				const ragRef = parsed.rag_book_reference ? [String(parsed.rag_book_reference)] : [];
				recordChatTelemetry({
					timestamp: (/* @__PURE__ */ new Date()).toISOString(),
					lessonNumber: activeLesson,
					scenarioId,
					userQuery: message,
					modelResponse: parsed.reply_display_arabic || rawContent,
					modelUsed: model,
					ragChunksCited: ragRef,
					latencyMs: Date.now() - startTime
				});
			} catch (telemetryErr) {
				console.warn("Asynchronous telemetry recording skipped:", telemetryErr);
			}
			if (!await storeFn(privilegedClient, user.id, requestId, payload)) console.error("[khaliji-chat] Could not store chat result.");
			return res.status(200).json({
				...payload,
				request_id: requestId,
				quota
			});
		} catch (err) {
			lastError = err?.response?.data || err?.message || err;
			console.error(`Groq API Execution Exception [${model}]:`, lastError);
		}
		console.error("All Groq AI tutor models exhausted. Final error:", lastError);
		await releaseFn(privilegedClient, user.id, requestId, requestHash);
		return res.status(502).json({ error: "AI Tutor service temporarily unavailable. Please try again." });
	} catch (error) {
		console.error("[khaliji-chat] AI Tutor request failed.", error);
		return res.status(503).json({ error: "AI Tutor is temporarily unavailable. Please try again." });
	}
}
function handler(req, res, dependencies = {}) {
	return khalijiChatHandler(req, res, dependencies);
}
//#endregion
export { handler as default, khalijiChatHandler };
