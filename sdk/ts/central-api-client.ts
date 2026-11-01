/**
 * Central AI Runtime API Client
 * Server-Side HTTP Client for Peregrine Arabic AI Central Runtime & Terminal 2 Service
 * Supports auto-fallback to local deterministic synthesis when external service is offline
 */

export interface CentralChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface CentralGenerationParameters {
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  seed?: number;
}

export interface CentralChatRequest {
  request_id?: string;
  messages: CentralChatMessage[];
  parameters?: CentralGenerationParameters;
  model?: string;
}

export interface CentralTutorExplainRequest {
  request_id?: string;
  query: string;
  level?: "beginner" | "intermediate" | "advanced";
  topic?: "nahw" | "sarf" | "balagha" | "general" | string;
  parameters?: CentralGenerationParameters;
}

export interface CentralSpeakingRespondRequest {
  request_id?: string;
  user_utterance: string;
  scenario?: string;
  dialect?: "msa" | "emirati" | "levantine" | "egyptian" | string;
  dialogue_history?: CentralChatMessage[];
  parameters?: CentralGenerationParameters;
  persona?: "rashid" | "maryam" | string;
}

export interface CentralExamsExplainRequest {
  request_id?: string;
  question_text: string;
  options?: string[];
  correct_answer?: string;
  student_answer?: string;
  parameters?: CentralGenerationParameters;
}

export interface CentralAPIResponse {
  request_id: string;
  status: "success" | "error";
  content: string;
  model: string;
  provider: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  telemetry?: {
    latency_ms: number;
    finish_reason?: string;
    is_truncated?: boolean;
  };
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  timestamp: string;
  is_fallback?: boolean;
}

export interface CentralClientConfig {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
  enableFallback?: boolean;
}

export class CentralAPIClient {
  private baseUrl: string;
  private apiKey?: string;
  private timeoutMs: number;
  private enableFallback: boolean;

  constructor(config: CentralClientConfig = {}) {
    this.baseUrl = (
      config.baseUrl ||
      process.env.CENTRAL_AI_BASE_URL ||
      "http://127.0.0.1:8000"
    ).replace(/\/+$/, "");
    this.apiKey = config.apiKey || process.env.CENTRAL_AI_API_KEY;
    this.timeoutMs = config.timeoutMs || Number(process.env.CENTRAL_AI_TIMEOUT_MS) || 15000;
    this.enableFallback = config.enableFallback !== false;
  }

  private generateRequestId(prefix: string): string {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 7)}`;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
      headers["x-api-key"] = this.apiKey;
    }
    return headers;
  }

  /**
   * General Chat Completion
   */
  async chat(req: CentralChatRequest): Promise<CentralAPIResponse> {
    const requestId = req.request_id || this.generateRequestId("req");
    const payload = { ...req, request_id: requestId };

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/chat`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback cleanly if service unavailable
    }

    if (!this.enableFallback) {
      throw new Error(`Central AI Service unavailable at ${this.baseUrl}`);
    }

    const lastUserMsg = [...req.messages].reverse().find((m) => m.role === "user")?.content || "";
    return {
      request_id: requestId,
      status: "success",
      content: `[النموذج المركزي المحلي - وضع المحاكاة]: تمت معالجة استفسارك «${lastUserMsg.slice(0, 40)}» بنجاح وفق القواعد اللغوية المعتمدة.`,
      model: "peregrine-mock-v1",
      provider: "local-fallback",
      usage: { prompt_tokens: lastUserMsg.length, completion_tokens: 35, total_tokens: lastUserMsg.length + 35 },
      telemetry: { latency_ms: 12, finish_reason: "stop" },
      timestamp: new Date().toISOString(),
      is_fallback: true,
    };
  }

  /**
   * Arabic AI Tutor Explanation
   */
  async tutorExplain(req: CentralTutorExplainRequest): Promise<CentralAPIResponse> {
    const requestId = req.request_id || this.generateRequestId("tutor");
    const payload = { ...req, request_id: requestId };

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/tutor/explain`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback
    }

    if (!this.enableFallback) {
      throw new Error(`Central AI Service unavailable at ${this.baseUrl}`);
    }

    return {
      request_id: requestId,
      status: "success",
      content: `### شرح المعلم الذكي (${req.topic || "النحو العربي"}):\n\n**القاعدة الأساسية:**\nتخضع مسألة «${req.query}» للقواعد النحوية والصرفية المعتمدة في التراث اللغوي.\n\n**التفصيل والتحليل:**\n- يتم فحص الكلمات وتحديد موقعها الإعرابي والعوامل الداخلة عليها.\n- يُراعى الضبط التام بالحركات لبيان المعنى التركيبي الدقيق.`,
      model: "peregrine-tutor-v1",
      provider: "local-fallback",
      usage: { prompt_tokens: req.query.length, completion_tokens: 65, total_tokens: req.query.length + 65 },
      telemetry: { latency_ms: 15, finish_reason: "stop" },
      timestamp: new Date().toISOString(),
      is_fallback: true,
    };
  }

  /**
   * AI Speaking Partner Response (Rashid & Maryam)
   */
  async speakingRespond(req: CentralSpeakingRespondRequest): Promise<CentralAPIResponse> {
    const requestId = req.request_id || this.generateRequestId("speak");
    const payload = { ...req, request_id: requestId };

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/speaking/respond`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback
    }

    if (!this.enableFallback) {
      throw new Error(`Central AI Service unavailable at ${this.baseUrl}`);
    }

    const personaName = req.persona === "maryam" ? "مريم" : "راشد";
    const dialect = req.dialect || "emirati";
    const isEmirati = dialect.includes("emirati") || dialect.includes("gulf");

    const reply = isEmirati
      ? `يَا هَلَا وَالله! ${personaName} مَعَاكْ. سَمِعْتْ كَلَامِكْ عَنْ «${req.user_utterance.slice(0, 30)}».. وَالله زِينْ مَا قِلْتْ! شُو رَايِكْ نِكَمِّلْ سَوَالِفْنَا فِي مَوْضُوعْ ${req.scenario || "الْيَوْمْ"}؟`
      : `أهلاً بك! معك ${personaName}. سعدت بحديثك: «${req.user_utterance.slice(0, 30)}». كيف تحب أن نواصل محادثتنا اليوم؟`;

    return {
      request_id: requestId,
      status: "success",
      content: reply,
      model: "peregrine-speaking-v1",
      provider: "local-fallback",
      usage: { prompt_tokens: req.user_utterance.length, completion_tokens: 45, total_tokens: req.user_utterance.length + 45 },
      telemetry: { latency_ms: 18, finish_reason: "stop" },
      timestamp: new Date().toISOString(),
      is_fallback: true,
    };
  }

  /**
   * Arabic Exams Explanation & Distractor Analysis
   */
  async examsExplain(req: CentralExamsExplainRequest): Promise<CentralAPIResponse> {
    const requestId = req.request_id || this.generateRequestId("exam");
    const payload = { ...req, request_id: requestId };

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/exams/explain`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback
    }

    if (!this.enableFallback) {
      throw new Error(`Central AI Service unavailable at ${this.baseUrl}`);
    }

    let explanationContent = `### تحليل السؤال الامتحاني الأكاديمي\n\n`;
    explanationContent += `**نص المسألة:** ${req.question_text}\n\n`;

    if (req.correct_answer) {
      explanationContent += `**الإجابة الصحيحة المعتمدة:** «${req.correct_answer}»\n`;
      explanationContent += `**التعليل الأكاديمي:** تستند هذه الإجابة إلى القواعد النحوية واللغوية المقررة، حيث يقتضي المعنى التركيبي والعامل اللفظي هذا التوجيه.\n\n`;
    }

    if (req.student_answer) {
      const isMatch = req.correct_answer && req.student_answer.trim() === req.correct_answer.trim();
      explanationContent += `**تقييم إجابة الطالب («${req.student_answer}»):** ${
        isMatch
          ? "✅ إجابة موفقة وصحيحة."
          : "⚠️ إجابة غير دقيقة امتحانياً؛ ويُعزى الخطأ إلى التباس في تحديد العامل الإعرابي أو دلالة الكلمة."
      }\n\n`;
    }

    if (req.options && req.options.length > 0) {
      explanationContent += `**تحليل المشتتات والخيارات:**\n`;
      for (const opt of req.options) {
        const isCorrect = req.correct_answer && opt.trim() === req.correct_answer.trim();
        explanationContent += `- **«${opt}»**: ${
          isCorrect
            ? "الخيار الصائب مطابقاً للشاهد والقاعدة."
            : "مشتت غير صحيح لخروجه عن السياق اللغوي المطلوب."
        }\n`;
      }
      explanationContent += `\n`;
    }

    explanationContent += `**نصيحة الاختبارات:** تأكد دائماً من ضبط الكلمات وملاحظة العوامل السابقة قبل اختيار الإجابة النهائية.`;

    return {
      request_id: requestId,
      status: "success",
      content: explanationContent,
      model: "peregrine-exams-v1",
      provider: "local-fallback",
      usage: { prompt_tokens: req.question_text.length, completion_tokens: 120, total_tokens: req.question_text.length + 120 },
      telemetry: { latency_ms: 22, finish_reason: "stop" },
      timestamp: new Date().toISOString(),
      is_fallback: true,
    };
  }
}

export const centralApiClient = new CentralAPIClient();
