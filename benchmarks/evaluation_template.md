# Arabic Model Benchmark Evaluation Rubric & Template

**Document Identifier:** `benchmarks/evaluation_template.md`  
**Companion File:** `benchmarks/evaluation_template.json`  
**Purpose:** Standardized manual and automated evaluation rubric for assessing Arabic LLM outputs against classical linguistic scholarship.

---

## 1. Foundational Ground-Truth Policy

> [!IMPORTANT]
> **Ground Truth Rule:** Ground truth is strictly external and grounded in verified classical Arabic philology, dictionaries (*لسان العرب*، *القاموس المحيط*), and standard grammatical treatises (*الكتاب* لسيبويه، *شرح المفصل*، *دلائل الإعجاز*).
> **Non-Self-Assessment Rule:** **Under no circumstances shall an LLM's self-evaluation, internal confidence score, or peer-LLM rating be accepted as ground truth.** Multi-agent evaluator nodes (e.g., in LangGraph) provide automated heuristic synthesis only and must be audited against the external reference criteria.

---

## 2. Five Core Evaluation Dimensions (Max: 50 Points)

| Dimension | Weight | Max Score | Core Focus |
|---|---|---|---|
| **1. Arabic Correctness (`arabic_correctness`)** | 20% | 10 pts | Absence of syntactical errors (*لحن*), proper case endings (*إعراب*), morphological accuracy, correct spelling (*رسم إملائي*). |
| **2. Terminology Precision (`terminology_precision`)** | 20% | 10 pts | Strict utilization of recognized classical terminology (*ألقاب الإعراب، الزحاف والعلل، النظم، صيغ الإعلال والإبدال*). |
| **3. Hallucination Absence (`hallucination_absence`)** | 25% | 10 pts | Absolute fidelity of Quranic verses, poetic attributions, and citations. Zero tolerance for fabricated rules or false attributions. |
| **4. Uncertainty Calibration (`uncertainty_calibration`)** | 15% | 10 pts | Proper handling of syntactical polysemy (*تعدد الأوجه الإعرابية*), noting school differences (*البصريون والكوفيون*), avoiding false dogmatism. |
| **5. Response Quality & Depth (`response_quality`)** | 20% | 10 pts | Logical sequencing, depth of reasoning (*تعليل*), structural completeness, pedagogical clarity. |

---

## 3. Scoring Criteria Guide

### 1. Arabic Correctness (0 – 10)
- **9–10:** Flawless classical Arabic, impeccable syntax, zero orthographic or case errors.
- **7–8:** Strong eloquence with minor, non-syntactic typos that do not corrupt parsing.
- **5–6:** Noticeable grammatical errors (e.g., mismatch in dual/plural concord or broken broken plurals).
- **3–4:** Frequent grammatical mistakes (*لحن جلي*) altering fundamental clause structures.
- **0–2:** Severe broken Arabic, gibberish, or syntactical incoherence.

### 2. Terminology Precision (0 – 10)
- **9–10:** Exhaustive and exact employment of standard philological terminology.
- **7–8:** Accurate standard terms with minor informal vernacular phrasing.
- **5–6:** Over-reliance on generic vocabulary instead of precise technical terms.
- **3–4:** Conflation of terminology across separate sciences (e.g., mixing prosodic *زحاف* with morphological *إعلال*).
- **0–2:** Complete absence or misapplication of philological terminology.

### 3. Hallucination Absence (0 – 10)
- **9–10:** 100% faithful to authentic texts, correct verse citations, verified attributions.
- **7–8:** Accurate core facts; minor non-substantive discrepancies in secondary historical narratives.
- **5–6:** Misattributed poetic verses or minor factual conflation outside Quranic citations.
- **3–4:** Corrupted Quranic text, invented syntactic rules, or fabricated poetic lines.
- **0–2:** Widespread hallucination of non-existent sources, scholars, or linguistic canons.

### 4. Uncertainty Calibration (0 – 10)
- **9–10:** Insightful recognition of valid alternative parses (*أوجه الإعراب*) and scholarly variance.
- **7–8:** Clear primary analysis with explicit acknowledgment of credible alternatives.
- **5–6:** Only one perspective provided without acknowledging well-known school disputes.
- **3–4:** Dogmatic assertion of a weak or irregular opinion (*وجه شاذ أو ضعيف*).
- **0–2:** Outright rejection of verified canonical readings or valid syntactic variants.

### 5. Response Quality & Depth (0 – 10)
- **9–10:** Deep, comprehensive deconstruction with didactic structure and persuasive reasoning.
- **7–8:** Thorough answer answering all sub-questions cleanly and logically.
- **5–6:** Brief or superficial response addressing core questions without explanatory depth.
- **3–4:** Fragmented answer omitting key parts of the question prompt.
- **0–2:** Irrelevant, off-topic, or truncated non-response.

---

## 4. Evaluation Record Template (JSON Structure)

Evaluators must record their assessment in the accompanying JSON schema:
```json
{
  "evaluator_name": "<Human Expert or Calibrated Benchmark Pipeline>",
  "evaluator_type": "external_expert",
  "evaluation_date": "YYYY-MM-DD",
  "benchmark_id": "arabic_day1",
  "question_id": "q01_nahw",
  "model_evaluated": "qwen3:4b",
  "scores": {
    "arabic_correctness": 10,
    "terminology_precision": 10,
    "hallucination_absence": 10,
    "uncertainty_calibration": 10,
    "response_quality": 10
  },
  "total_score": 50,
  "percentage": 100.0,
  "notes": {
    "ground_truth_alignment": "Full alignment with Sibawayh and standard syntactical consensus.",
    "hallucinations_detected": "None",
    "critical_weaknesses": []
  }
}
```
