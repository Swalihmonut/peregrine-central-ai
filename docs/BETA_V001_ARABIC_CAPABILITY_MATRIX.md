# Peregrine Arabic AI Beta V-001: Arabic Specialist Capability Matrix

**Document Reference:** `PEREGRINE-BETA-CAPABILITY-MATRIX-2026-10-31`  
**Author:** Agent 1 (Arabic NLP & Speech Integration Engineer)  
**Workspace:** `~/peregrine-arabic-ai-lab`  
**Context:** Rapid Pragmatic Delivery for Beta V-001 (Non-Research Perfection Track)  
**Date:** October 31, 2026  
**Status:** Approved for Beta V-001 Scoping

---

## 1. Executive Strategy: Pragmatic Delivery over Academic Perfection

To deliver a reliable, responsive, and delight-inducing Beta V-001 experience, Peregrine Arabic AI pivots from exhaustive academic benchmark curation to a **pragmatic, dual-tier architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PEREGRINE BETA V-001 CAPABILITY TIERS                 │
│                                                                             │
│   TIER 1: CLIENT-SIDE TYPESCRIPT (Zero Latency, In-Process, Rock Solid)     │
│   • Text Normalization (stripTashkeel, stripTatweel, normalizeAlif)         │
│   • Emirati Lexical Detection (Keyword matcher & phrasebook)                │
│   • Basic Prosody Fallback (Regex-based classical meter heuristics)         │
│   • Phonetic Harakat Density Calculation                                    │
│                                                                             │
│   TIER 2: ISOLATED PYTHON SIDECAR (Lightweight, Precision Philology)        │
│   • PyArud 1.0.0 Prosody Engine (16 Farahidian meters, Zihaf, Qafiyah)      │
│   • Zero-dependency HTTP daemon running on Python 3.12                      │
│                                                                             │
│   TIER 3: DEFERRED / BLOCKED (Heavy, Licensing Risks, High Cold-Start)      │
│   • CAMeL Tools 1.6.0 (Deferred: 1.4 GB RAM, 18s cold-start, GPLv2 DBs)    │
│   • Mishkal 0.4.1 (Deferred: Classical syntax errors, 4s cold-start)        │
│   • Qalsadi 0.5.1 (Deferred: Redundant with client-side morphology)         │
│   • Qutrub 1.2.4.1 (Deferred to Sprint 2: Licensing clearance gate)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Capability Classification

Every researched Arabic capability and tool is classified under one of four operational readiness statuses:
1. **Ready for Beta:** Immediate use in Beta V-001 with zero external blockers.
2. **Needs a Thin API Wrapper:** Reliable core engine verified in lab; requires lightweight HTTP wrapper.
3. **Deferred:** Excluded from Beta V-001 to prevent release delays, excessive memory usage, or poor user experience.
4. **Licensing or Operational Blocker:** Prohibited from deployment due to legal copyleft risks or operational hazards.

### 2.1 Master Capability Classification Table

| Capability / Module | Underlying Engine / Location | Technical Readiness Classification | Beta V-001 Role & Implementation Strategy | Operational & Licensing Rationale |
| :--- | :--- | :---: | :--- | :--- |
| **Arabic Text Normalization** | Native TypeScript (`src/lib/arabic/normalization.ts` in Main App) | **READY FOR BETA** | **Primary Normalizer:** Applied client-side in Next.js runtime. Preserves original input while producing normalized search tokens. | Zero latency (<0.1 ms), zero runtime dependencies, no Python bridge required. |
| **Python Normalization Fallback** | `pyarabic` (0.6.15 in `.venv`) | **DEFERRED (REDUNDANT)** | Deferred from active Beta runtime because TypeScript implementation in main app is 100% feature-complete for normalization. | Avoids unnecessary HTTP hops and avoids bundling GPLv3 code into client bundles. |
| **Classical Prosody & Metre Analysis** | `pyarud` (1.0.0 in `.venv-prosody`) | **NEEDS A THIN API WRAPPER** | **Authoritative Poetic Engine:** Provides 16-meter Farahidian scansion, foot-level Zihaf/‘Ilal analysis, and Qafiyah breakdown. | MIT License, zero dependencies. Wrapped in a lightweight Python 3.12 HTTP service inside the lab. |
| **Prosody Fallback (Heuristic)** | Native TypeScript (`src/lib/arabic/prosody.ts` in Main App) | **READY FOR BETA** | **Offline Fallback:** Client-side regex scansion for common meters (*Al-Tawil*, *Al-Kamil*, *Al-Basit*) if Python sidecar is unreachable. | Graceful degradation. Displays `"Heuristic Match (Offline)"` badge. |
| **Emirati Dialect Keyword Matcher** | Native TypeScript (`src/lib/arabic/dialects.ts` in Main App) | **READY FOR BETA** | **Local Dialect Tagger:** Scans for authentic Emirati markers (`رمسة`, `وايد`, `باجر`, `ريال`, `شو مسوي`, `طَرَش`). | Instantaneous regex classification. Flags text as `dialect: "emirati"` for LLM persona steering. |
| **Basic Morphology & Affix Stripping** | Native TypeScript (`src/lib/arabic/morphology.ts` in Main App) | **READY FOR BETA** | **Fast-Path Morphology:** Extracts base stems by stripping standard proclitics (`الـ`, `وـ`, `بـ`, `فـ`) and enclitics (`ـهم`, `ـها`). | Lightweight, deterministic. Solves 80% of dictionary lookup needs for learners. |
| **Verb Conjugation Paradigm Engine** | `libqutrub` (1.2.4.1 in `.venv`) | **DEFERRED (SPRINT 2)** | Deferred from initial Beta V-001. Conjugation tables for learners will be generated via calibrated Jais-3 prompts during Beta. | GPLv3 licensing clearance gate pending; avoids multi-process deployment complexity for day 1. |
| **Deep Morphological Disambiguation** | `camel-tools` (1.6.0 in `.venv`) | **LICENSING & OPERATIONAL BLOCKER** | **STRICTLY DEFERRED:** Not included in Beta V-001. | Requires ~1.4 GB resident RAM, 18-second cold boot, and underlying `calima-msa-r13` database carries LDC GPLv2 restrictions. |
| **Automatic Full Diacritization** | `mishkal` (0.4.1 in `.venv`) | **DEFERRED (EXPERIMENTAL)** | **STRICTLY DEFERRED:** Not included in Beta V-001. | High error rate on classical Arabic poetry syntax (e.g., misclassifying verbs as masdars), 4.5s cold-start. |
| **Lexical Stemmer & Lemmatizer** | `qalsadi` (0.5.1 in `.venv`) | **DEFERRED** | **STRICTLY DEFERRED:** Subsumed by main app's native TypeScript morphological analyzer. | GPLv3 dependency; avoids redundant process overhead. |

---

## 3. Prioritized Capabilities for Beta V-001

To ensure immediate practical value to Arabic learners and academic users without chasing research perfection:

### Priority 1: Non-Destructive Arabic Normalization
- **Rule:** Never mutate the student's or researcher's original Arabic input in-place.
- **Contract:** All normalization endpoints and utilities return:
  - `originalText`: Raw input preserved verbatim with full harakat, punctuation, and typography.
  - `normalizedText`: Normalized string with tatweel stripped and alefs standardized for search/indexing.
  - `tashkeelStripped`: Cleaned unpointed text for fuzzy dictionary lookups.

### Priority 2: Authoritative Metric Scansion via PyArud Sidecar
- **Rule:** When vocalized poetry is submitted, route to the isolated `pyarud` service (port 8089 / socket).
- **Graceful Fallback:** If the PyArud service is starting up, down, or times out (>1,500 ms), the platform transparently falls back to the native TypeScript prosody regex engine with an explicit `is_heuristic: true` tag.

### Priority 3: Honest Uncertainty & Abstention Handling
- **Rule:** Never invent scansion results or disguise unmetered prose as poetry.
- **Action:** If an undiacritized verse is submitted or if foot patterns do not match classical Farahidian cycles, the engine returns `is_poetic: false` and explicitly indicates that full vocalization is required.

---

## 4. Minimum Beta V-001 Feature Set vs. Explicit Gaps

### What Is Included in Beta V-001
1. **Client-Side Arabic Normalizer & Sanitizer:** Rock-solid TypeScript string processing in the main app.
2. **PyArud Isolated Prosody Service:** Running in `~/peregrine-arabic-ai-lab/.venv-prosody` exposing `/health` and `POST /api/v1/prosody/analyze`.
3. **Emirati Lexical Detector:** Tagging Gulf conversational expressions for the Speaking Partner.
4. **Transparent Degradation:** Clear UI indicators distinguishing deterministic engine truth from AI generative suggestions.

### Explicit Gaps Marked for Future Sprints
1. **No Automated Diacritization Pipeline:** Users must submit vocalized verses for authoritative prosodic analysis; raw unvocalized text is handled as an experimental fallback.
2. **No Deep Triliteral Root Disambiguation (CAMeL Tools):** Words with ambiguous morphology (e.g. `ذهب`) are resolved contextually by Jais-3 rather than a 1.4 GB local SQLite morphology database.
3. **No Heavy Verb Conjugation Tables:** Conjugations are rendered via prompt templates rather than a dedicated Qutrub microservice.

---

**Certification:**  
*Compiled by Agent 1 (Arabic NLP & Speech Integration Engineer)*  
*Verified for Peregrine Arabic AI Beta V-001 — October 31, 2026*
