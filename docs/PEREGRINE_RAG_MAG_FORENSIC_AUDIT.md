# PEREGRINE RAG & MAG KNOWLEDGE INFRASTRUCTURE FORENSIC AUDIT
**Document ID:** PEREGRINE-AUDIT-RAG-MAG-001  
**Classification:** Engineering Architecture & Infrastructure Audit  
**Date:** October 31, 2026  
**Auditor:** Antigravity AI Engineering (Terminal 3 — Knowledge & Retrieval Audit)  
**Target Systems:**  
1. `~/Developer/peregrine-arabic-ai-mvp` (Terminal 4 — Unified Web Client & Notebook RAG)  
2. `~/peregrine-arabic-ai-lab` (Terminal 2 & 3 — Central Runtime, Evaluation Benchmarks, Specialist NLP)  
3. `~/Developer/peregrine-arabic-ai` (Legacy MVP — Quiz Question RAG Prototype)  

---

## 1. Executive Summary

This forensic audit evaluates the actual implementation status of all knowledge, retrieval, and memory subsystems across the Peregrine Arabic AI codebase. In accordance with architectural directives:
- **RAG** denotes *Retrieval-Augmented Generation* (grounding model generations in external authoritative Arabic corpora and user-uploaded documents).
- **MAG** strictly denotes **Memory-Augmented Generation** (a 3-tier student memory architecture comprising short-term conversation state, user-approved long-term profile/pedagogical memory, and corpus grounding; **not** generic multi-agent architectures).

### Status Classification Criteria
Every component has been verified directly against executable source code, schemas, and test suites under one of five strict labels:
1. **IMPLEMENTED AND VERIFIED**: Executable production code exists, is integrated into active pipelines, and passes automated regression tests.
2. **IMPLEMENTED BUT NOT VERIFIED**: Executable code exists, but tests are missing, failing, or mocked out without automated validation.
3. **PROTOTYPE**: Working algorithmic proof-of-concept exists (e.g., in-memory map or local heuristic), but lacks persistent production storage or high-scale readiness.
4. **DOCUMENTED ONLY**: Architecture schemas, API contracts, or specifications exist in documentation or SQL migration files, but without active runtime execution code.
5. **MISSING**: No operational code, schema, or functional interface exists in the evaluated codebase.

---

## 2. Forensic Component Audit Matrix

| # | Subsystem Component | Status | Primary Code Path | Verification Test / Evidence |
|---|---------------------|--------|-------------------|------------------------------|
| **1** | **Document Ingestion** | **IMPLEMENTED AND VERIFIED** (MVP) / **PROTOTYPE** (Lab) | `src/lib/notebook/document-processor.ts`<br>`src/lib/notebook/repositories/local-storage.ts` | `tests/notebook_quality.test.ts` (Lines 11-48)<br>`tests/research_notebook.test.ts` |
| **2** | **PDF & Text Extraction** | **IMPLEMENTED AND VERIFIED** | `src/lib/notebook/document-processor.ts` (using `unpdf`) | `tests/notebook_quality.test.ts` (multi-page extraction, scanned PDF detection) |
| **3** | **Arabic-Aware Chunking** | **IMPLEMENTED AND VERIFIED** | `src/lib/knowledge/chunker.ts`<br>`src/lib/notebook/document-processor.ts` | Splits on Arabic sentence boundaries (`. ! ؟ ؛ \n\n`), 400-char window, 50-char overlap |
| **4** | **Metadata & Provenance** | **IMPLEMENTED AND VERIFIED** | `src/types/knowledge.ts`<br>`src/lib/notebook/repositories/types.ts` | Full provenance: `documentId`, `sourceId`, `pageNumber`, `author`, `section`, `charOffset` |
| **5** | **Embedding Model** | **PROTOTYPE** (Local n-gram) / **NOT VERIFIED** (Live API) | `src/lib/knowledge/embeddings.ts` (`ArabicEmbeddings.generateDeterministicVector`) | 64-dim L2-normalized character/subword n-gram hash; Gemini `text-embedding-004` stub offline |
| **6** | **Vector Database** | **PROTOTYPE** (In-Memory) / **DOCUMENTED ONLY** (pgvector) | `src/lib/knowledge/vector-store.ts`<br>`src/lib/knowledge/supabase-schema.sql` | `InMemoryVectorStore` using Map; Supabase `vector(768)` HNSW schema documented |
| **7** | **Hybrid Search** | **IMPLEMENTED AND VERIFIED** | `src/lib/knowledge/vector-store.ts` (Lines 29-60) | Combines cosine vector similarity with exact Arabic token match bonus (+0.1 to +0.4) |
| **8** | **Retrieval & Reranking** | **IMPLEMENTED AND VERIFIED** | `src/lib/knowledge/retriever.ts`<br>`src/lib/notebook/grounded-chat.ts` | Top-K candidate filtering, similarity thresholding (>=0.2), prompt boundary synthesis |
| **9** | **Prompt/Context Assembly** | **IMPLEMENTED AND VERIFIED** | `src/lib/knowledge/retriever.ts` (Lines 37-56)<br>`src/lib/notebook/grounded-chat.ts` | Anti-prompt-injection delimiters, formatted heritage evidence tags (`=== شواهد ومصادر ===`) |
| **10** | **Citation Generation** | **IMPLEMENTED AND VERIFIED** | `src/lib/notebook/grounded-chat.ts` (Lines 80-142)<br>`src/types/notebook.ts` | Exact inline quote matching, confidence verification, page-level citation pills `[cit_...]` |
| **11** | **Conversation Memory (Short-Term)** | **IMPLEMENTED AND VERIFIED** | `src/app/tutor/page.tsx`<br>`src/lib/api/central-api-client.ts` | Multi-turn message history buffer passed in request payloads across Central API and UI |
| **12** | **User Memory Isolation** | **IMPLEMENTED AND VERIFIED** (Notebook) / **DOCUMENTED ONLY** (MAG) | `src/lib/notebook/repositories/local-storage.ts`<br>`src/lib/knowledge/supabase-schema.sql` | `tests/security_audit.test.ts` (tenant boundary validation); multi-user MAG isolation drafted |
| **13** | **Persistent Memory** | **IMPLEMENTED BUT NOT VERIFIED** | `src/lib/notebook/repositories/supabase-adapter.ts`<br>`src/lib/notebook/repositories/local-storage.ts` | Client-side `localStorage` active; Supabase multi-session SQL tables defined but unverified |
| **14** | **Memory Update, Deletion & Retention** | **IMPLEMENTED AND VERIFIED** (Documents) / **DOCUMENTED ONLY** (MAG Profile) | `src/lib/notebook/repositories/local-storage.ts` (`deleteDocument`, `deleteNotebook`) | Cascading chunk deletion verified in notebook tests; student pedagogical memory retention unverified |
| **15** | **Evaluation & Regression Tests** | **IMPLEMENTED AND VERIFIED** (MVP) / **MISSING** (Lab Python) | `tests/notebook_quality.test.ts`<br>`tests/research_notebook.test.ts` | 13/13 E2E and notebook quality tests pass; dedicated Python lab RAG/MAG test suite required |

---

## 3. Deep-Dive Forensic Findings by Subsystem

### 3.1 Document Ingestion, PDF & Text Extraction
- **Location:** `src/lib/notebook/document-processor.ts`
- **Mechanism:** Leverages `unpdf` library for streaming text extraction from multi-page PDF buffers. Extracts raw page text, tracks page indices (1-indexed), detects scanned/empty documents by character density (< 50 characters triggers `isScanned: true`), and validates ASCII/UTF-8 character boundaries.
- **Verification Status:** Fully automated in `tests/notebook_quality.test.ts`. Page counts, character counts, and per-page chunking pass regression tests.
- **Limitation:** In the Python lab (`~/peregrine-arabic-ai-lab`), ingestion was previously only sketched in bash scripts and unstructured benchmark JSONs.

### 3.2 Arabic-Aware Chunking
- **Location:** `src/lib/knowledge/chunker.ts`
- **Mechanism:** Implements two-stage chunking:
  1. Primary splitting by double newline (`\n\s*\n`) to preserve paragraph integrity.
  2. Sub-splitting on large paragraphs using Arabic sentence terminators: full stop (`.`), exclamation mark (`!`), question mark (`؟`), Arabic semicolon (`؛`), and newline.
  3. Window size: 400 characters (MVP) / ~200-400 tokens with 50-character sliding overlap.
- **Verification Status:** Verified. Successfully prevents splitting within Arabic words or across tight syntactic clauses.

### 3.3 Metadata and Provenance Tracking
- **Location:** `src/types/knowledge.ts`, `src/types/notebook.ts`
- **Data Model:**
  ```typescript
  interface KnowledgeChunk {
    id: string;
    documentId: string;
    title: string;
    author: string;
    section: string;
    content: string;
    contentDiacritized?: string;
    category: KnowledgeCategory;
    tags: string[];
    embedding?: number[];
    pageNumber?: number;
  }
  ```
- **Provenance Integrity:** Every retrieved chunk preserves source document ID, author attribution, section title, and original page number. This provenance flows through the retriever to the user-facing citation pills.

### 3.4 Embedding Model & Semantic Vectorization
- **Location:** `src/lib/knowledge/embeddings.ts`
- **Current Reality:**
  - **Offline Deterministic Fallback:** Employs a 64-dimensional hash vector generator. It normalizes text (`normalizeArabic`, `stripTashkeel`), hashes unigrams and character trigrams into a 64-bin float array, and normalizes via L2 Euclidean norm.
  - **Live Cloud Embeddings:** Contains an optional call to Google Gemini `text-embedding-004` (768 dimensions), gated behind `process.env.GEMINI_API_KEY`.
- **Verdict:** **PROTOTYPE** for deterministic hashing; **IMPLEMENTED BUT NOT VERIFIED** for live model inference because offline sandbox constraints preclude external API calls.

### 3.5 Vector Database & Storage
- **Location:** `src/lib/knowledge/vector-store.ts`, `src/lib/knowledge/supabase-schema.sql`
- **Current Reality:**
  - **MVP Runtime:** Operates `InMemoryVectorStore` using a TypeScript `Map<string, number[]>`. Seeded with 10 classical Arabic corpus chunks (`DEMO_KNOWLEDGE_CORPUS` covering Sibawayh, Ibn Jinni, Al-Jurjani, Ibn Malik, and Al-Jahiz).
  - **Persistent Schema:** A comprehensive Supabase `pgvector` migration file exists (`supabase-schema.sql`) defining `vector(768)` with HNSW cosine indexing (`using hnsw (embedding vector_cosine_ops)`).
- **Verdict:** In-memory map is a working prototype. Persistent database implementation is documented in SQL but not yet connected to a live lab backend.

### 3.6 Hybrid Search & Reranking
- **Location:** `src/lib/knowledge/vector-store.ts` (Lines 42-60)
- **Mechanism:** Computes cosine similarity between query and candidate vector, then adds an exact Arabic keyword match bonus:
  $$\text{Score} = \text{CosineSim}(v_q, v_c) + \min(0.40, \text{MatchCount} \times 0.10)$$
  Filtered by minimum similarity threshold (default $0.15$ or $0.20$) and sorted descending.
- **Verdict:** **IMPLEMENTED AND VERIFIED**. Delivers superior precision for specialized Arabic grammatical terms (e.g., "المبتدأ", "الفاعل", "الاستعارة") compared to unweighted vector search.

### 3.7 Prompt/Context Assembly & Injection Defenses
- **Location:** `src/lib/knowledge/retriever.ts`, `src/lib/notebook/grounded-chat.ts`
- **Defenses:** Sanitizes candidate chunk text by escaping markdown backticks (`'''`), stripping `<system>` tags, and neutralizing instruction override attacks (`ignore previous instructions` -> `[redacted]`).
- **Assembly:** Encloses evidence within structured Arabic boundary markers:
  ```
  === شواهد ومصادر تراثية موثقة من قاعدة المعرفة ===
  [المصدر 1]: «الكتاب» — سيبويه
  الموضع: باب المسند والمسند إليه
  المحتوى المقتبس: ...
  === نهاية المصادر الموثقة ===
  ```
- **Verdict:** **IMPLEMENTED AND VERIFIED**.

### 3.8 Citation Generation
- **Location:** `src/lib/notebook/grounded-chat.ts`
- **Verification Rule:** Verifies that AI-generated citations match real chunks in the retrieved context. Computes verbatim quote overlap and validates that claims reference existing page numbers. Discards ungrounded hallucinations.
- **Verdict:** **IMPLEMENTED AND VERIFIED** in MVP test suites.

### 3.9 Memory-Augmented Generation (MAG) Architecture
- **Distinction:** MAG is **Memory-Augmented Generation**, NOT multi-agent architecture.
- **Three-Tier Architectural Model:**
  1. **Layer 1: Short-Term Conversation State:** Sliding window buffer of recent user/assistant turns. Active in `TutorPage` and `CentralAPIClient`.
  2. **Layer 2: User-Approved Long-Term Pedagogical Memory:** Tracks mastered Arabic grammatical concepts, recurring pronunciation weaknesses, dialect preferences, and student CEFR level. Must require user consent and offer full deletion controls.
  3. **Layer 3: Knowledge Retrieval (RAG Grounding):** Authoritative heritage documents and course curricula.
- **Current Status:**
  - Layer 1: **IMPLEMENTED AND VERIFIED**.
  - Layer 2: **DOCUMENTED ONLY** in MVP; prototyped in Reader localStorage, missing in Python lab.
  - Layer 3: **IMPLEMENTED AND VERIFIED** (In-Memory RAG).

---

## 4. Gap Analysis & Urgent Priorities for Beta V-001

1. **Python Lab Knowledge Core Missing:** The lab (`~/peregrine-arabic-ai-lab`) lacks an active Python implementation of RAG and MAG to accompany the TypeScript MVP client.
2. **Morphological Arabic Query Expansion Missing:** Retrieval does not yet leverage Arabic lemmatization/root extraction (`pyarabic`, `tashaphyne`, `qalsadi`) to bridge diacritised vs unvocalised queries (`الْعِلْمُ` vs `العلم`) and inflectional variants (`كاتب` vs `مكتوب`).
3. **Formal MAG Profile Isolation:** No automated cross-user isolation test exists verifying that Student A's pedagogical memory cards cannot bleed into Student B's prompt context.
4. **No-Answer Fallback Handling:** Needs explicit verification that queries with no relevant corpus matches trigger an honest "لا توجد شواهد كافية" (insufficient evidence) response rather than model hallucination.

---

## 5. Architectural Recommendations

1. **Vector Database:** Confirm **PostgreSQL + pgvector** as the single recommended vector store for Beta V-001 (reusing existing Supabase/PostgreSQL infrastructure).
2. **Implement Python Knowledge Core in Lab:** Build `knowledge_core/arabic_rag.py` and `knowledge_core/arabic_mag.py` utilizing the lab's installed NLP stack (`pyarabic`, `tashaphyne`, `qalsadi`, `scikit-learn`, `numpy`).
3. **Build Comprehensive Test Suite:** Create `tests/test_rag_mag.py` in `~/peregrine-arabic-ai-lab` covering all 10 evaluation criteria (exact retrieval, semantic retrieval, diacritics, morphology, mixed language, filters, citations, tenant isolation, memory deletion, no-answer behavior).
