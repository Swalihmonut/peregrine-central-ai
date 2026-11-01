# VECTOR DATABASE ARCHITECTURAL DECISION RECORD (ADR)
**Document ID:** PEREGRINE-ADR-VEC-001  
**Title:** Vector Database Selection & Storage Strategy for Beta V-001 and Production Scale  
**Date:** October 31, 2026  
**Status:** APPROVED FOR BETA V-001  
**Author:** Antigravity AI Engineering (Terminal 3 — Knowledge & Retrieval)  
**Target Systems:** Peregrine Arabic AI Unified Platform (`peregrine-arabic-ai-mvp` & `peregrine-arabic-ai-lab`)  

---

## 1. Context & Problem Statement

The Peregrine Arabic AI Unified Platform requires vector similarity search, metadata filtering, and semantic retrieval for:
1. Classical Arabic heritage text corpus (grammar, syntax, rhetoric, literature, dictionary glossaries).
2. User-uploaded research documents (PDFs, multi-page treatises, course notes).
3. Pedagogical memory embeddings (student topic mastery vectors, pronunciation error embeddings).

The vector solution must:
- Be free and commercially usable (permissive open-source license with no restrictive non-compete clauses).
- Support strict tenant/user isolation (metadata filters by `user_id`, `category`, `document_id`).
- Excel at Arabic retrieval (supporting exact keyword token matches, root-stem overlap, and diacritic insensitivity alongside dense semantic embeddings).
- Minimize operational complexity and cloud hosting cost for Beta V-001.
- Provide a clean horizontal scaling and migration path as corpus volume reaches hundreds of millions of chunks.

---

## 2. Comparative Evaluation Matrix

| Evaluation Dimension | Option A: PostgreSQL + pgvector (Recommended) | Option B: Qdrant (Self-Hosted / Cloud Free Tier) | Option C: Chroma (Embedded / Server) |
|---|---|---|---|
| **License** | **PostgreSQL License / Apache 2.0** (pgvector). Completely free, unrestricted commercial use. | **Apache 2.0** for core engine. Commercial cloud managed tier. | **Apache 2.0**. Free, unrestricted commercial use. |
| **Hosting Cost (Beta V-001)** | **$0.00 / month** (Reuses existing Supabase / PostgreSQL instance already deployed in Peregrine). | $0 (Self-hosted Docker on existing VM) or $0 (Qdrant Cloud 1GB cluster). | $0 (In-process SQLite/DuckDB or local container). |
| **Persistent Storage & Durability** | **Enterprise-grade ACID**. Write-Ahead Logging (WAL), transaction guarantees, point-in-time recovery. | In-memory with append-only write-ahead log & mmap snapshots. | Local SQLite + Parquet. Known crash corruption issues under high concurrent writes. |
| **Backup & Disaster Recovery** | Standard `pg_dump`, WAL-G, physical volume snapshots, native managed cloud backups. | Snapshot API, file-level directory backups. Requires dedicated custom backup job. | Directory copying. Lacks atomic multi-table point-in-time recovery. |
| **Relational & Metadata Filtering** | **Native SQL Joins & Filters**: Can filter directly on foreign keys (`user_id`, `tier`, `category`) in the same query index scan. | Fast payload index filtering (HNSW payload indexes). Cannot join with user tables. | Basic JSON metadata filtering. Inefficient with large candidate pools. |
| **Arabic Text & Hybrid Search** | **Superior Hybrid Retrieval**: Combines pgvector cosine/IP search with `pg_trgm` (trigrams) and Arabic full-text search (`tsvector`) in a single query. | Excellent dense vector search; sparse BM25 payload search supported, but no Arabic-specific stemmers. | Dense vectors only. Lacks native Arabic morphological/stemming capabilities. |
| **Operational Burden** | **Lowest**: 0 additional daemons, 0 extra monitoring stacks, 0 extra ports. DBAs already manage PostgreSQL. | Medium: Requires deploying and monitoring another container/service (Rust runtime). | Low for local dev, High in production (unstable multi-worker concurrency). |
| **Indexing Algorithms** | **HNSW** (Hierarchical Navigable Small World) & **IVFFlat**. Fast build, low memory footprint. | **HNSW** with scalar and product quantization. Highly optimized vector performance. | HNSW via hnswlib. |
| **Scale Ceiling** | 10M to 50M vectors per node (with HNSW index). Scales horizontally with Citus or read replicas. | 100M+ vectors with distributed clustering and memory quantization. | Practical ceiling ~1M vectors before performance degradation. |

---

## 3. Deep-Dive Comparative Assessment

### 3.1 Option A: PostgreSQL + pgvector (Supabase / Self-Hosted) — *RECOMMENDED*
- **Why It Fits Peregrine:**
  1. **Existing Infrastructure Reuse:** The Peregrine Arabic AI ecosystem already utilizes PostgreSQL via Supabase (`khaliji-arabic-through-stories`, `arabic-academy-ai`, and `src/lib/knowledge/supabase-schema.sql`). Deploying pgvector requires no new infrastructure, zero incremental cost, and zero new cloud service accounts.
  2. **Atomic Relational Integration:** Chunks, documents, user authentication records, and pedagogical memory states reside in the same ACID database. Document deletion (`DELETE FROM arabic_documents WHERE id = ...`) cascades atomically to all chunks via foreign key constraints, eliminating dangling orphan vectors.
  3. **Unmatched Hybrid Arabic Querying:** Standard vector databases require two separate systems to achieve hybrid search: a vector database and Elasticsearch/OpenSearch. In PostgreSQL, a single query can blend `pgvector` cosine similarity with `pg_trgm` trigram similarity (crucial for unvocalized Arabic roots) and exact term matching using a unified execution plan:
     ```sql
     select c.id, c.title, c.content,
            1 - (c.embedding <=> query_vec) as semantic_sim,
            similarity(c.content, query_text) as trigram_sim
     from arabic_knowledge_chunks c
     where c.category = 'nahw'
       and (c.user_id = current_user_id or c.user_id is null)
     order by (1 - (c.embedding <=> query_vec)) * 0.7 + similarity(c.content, query_text) * 0.3 desc
     limit 5;
     ```

### 3.2 Option B: Qdrant (Self-Hosted / Managed Free Tier)
- **Strengths:** Qdrant is written in Rust, exceptionally fast, supports payload filtering with payload indices, and has native sparse vector support for hybrid BM25.
- **Weaknesses for Beta V-001:** Requires running an additional service in Docker or managing an external cloud account. Separates user relational metadata (auth, subscriptions, usage quotas) from chunk vectors, introducing two-phase commits and risk of out-of-sync vector indices when users delete documents.
- **Role in Roadmap:** Qdrant is the recommended migration target if Peregrine's vector corpus exceeds 50 million chunks or requires sub-10ms latency across multi-billion vector clusters.

### 3.3 Option C: Chroma
- **Strengths:** Easy to spin up for ephemeral local Python tests.
- **Weaknesses for Production:** In-process SQLite architecture struggles with multi-process concurrency (Next.js serverless workers + FastAPI Central API workers). Lacks native Arabic morphological tooling and has historically suffered schema migrations and backward compatibility breaking changes.
- **Verdict:** Unsuitable for production multi-tenant Arabic AI workloads.

---

## 4. Definitive Recommendation for Beta V-001

> **DECISION:** Adopt **PostgreSQL + pgvector** as the single primary vector database for Peregrine Arabic AI Beta V-001, backed by the existing Supabase infrastructure.
>
> For local offline development and sandboxed evaluation in `~/peregrine-arabic-ai-lab`, maintain a 100% API-compatible **In-Memory & SQLite Vector Store** fallback.

### Justification Summary:
1. **Zero New Infrastructure Overhead:** Leverages existing database instances without adding new containers or subscriptions.
2. **ACID Tenant & User Isolation:** Complete security isolation through Row Level Security (RLS) and SQL `WHERE user_id = ...` foreign keys.
3. **Data Loss Prevention:** Eliminates split-brain state; deleting a document or user account cascades immediately to vectors.
4. **Permissive Open-Source License:** Both PostgreSQL and pgvector use permissive licenses permitting unrestricted commercial exploitation.

---

## 5. Production Scaling & Migration Path

As the Peregrine knowledge base scales through Beta and General Availability:

```
[Phase 1: Beta V-001 (0 - 500k chunks)]
PostgreSQL 15+ with pgvector (HNSW cosine index)
+ Local In-Memory Fallback for Offline Tests
       │
       ▼
[Phase 2: Scale (500k - 20M chunks)]
PostgreSQL with pgvector + Halfvec / PQ (Product Quantization)
+ Dedicated Read Replica for Vector Search
       │
       ▼
[Phase 3: Hyper-Scale (20M+ chunks)]
Dedicated Qdrant Distributed Cluster
(PostgreSQL retains relational metadata & syncs vectors via Change Data Capture / Debezium)
```

No architectural rework is required for Phase 1. The unified schemas defined in `src/lib/knowledge/supabase-schema.sql` are ready for immediate production binding.
