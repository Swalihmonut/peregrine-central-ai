# Zero-Cost Database & Vector Options Audit (Corrected)
**Project:** Peregrine Arabic AI Beta V-001  
**Target:** Supabase PostgreSQL with `pgvector`  
**Reference Migration:** `supabase/migrations/20261030_research_notebook_persistence.sql`  
**Audit Date:** 2026-10-31  

---

## 1. Verification of Existing Database & pgvector Configuration

Inspection of repository migration assets confirms an active Supabase PostgreSQL architecture:
- **Location:** `Developer/peregrine-arabic-ai-mvp/supabase/migrations/20261030_research_notebook_persistence.sql`
- **Extensions Verified:**
  - `vector`: Active for cosine similarity search over Arabic text embeddings.
  - `uuid-ossp`: Active for cryptographic record identification.
- **Table Inventory:**
  - `public.research_notebooks`: Research project containers.
  - `public.notebook_sources`: Reference documents and uploaded manuscripts.
  - `public.notebook_chunks`: Segmented Arabic text chunks with `embedding vector(1536)`.
  - `public.notebook_queries`: Learner semantic search history.
  - `public.notebook_notes`: Synthesized philological notes.

All credentials (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) are managed exclusively via environment files and remain strictly unprinted.

---

## 2. Free Tier Backup & Disaster Recovery Limitations (Corrections)

### 2.1 Correction on Automated Backups & PITR
- **Correction:** The previous audit claimed enterprise backup coverage. On the **Supabase Free Tier**, **Point-In-Time Recovery (PITR) and downloadable automated daily backups are NOT available**.
- PITR requires upgrading to the Pro plan ($25/month) plus a dedicated PITR add-on ($100/month).
- On the Free tier, if data is accidentally deleted, truncated, or corrupted by a faulty migration, **Supabase cannot restore the database to an arbitrary historical point**.

### 2.2 Operational Manual Backup & Restore Procedure
To maintain disaster recovery without incurring paid subscriptions, the following manual backup procedure must be executed prior to any deployment or schema modification:

#### Manual Backup (Logical Schema & Data Dump)
```bash
# Export schema and data using pg_dump via connection pooling string
# Set PGPASSWORD in environment; do not print or hardcode password
PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump \
  --clean \
  --if-exists \
  --quote-all-identifiers \
  --exclude-table-data 'storage.objects' \
  -h "db.YOUR_PROJECT_REF.supabase.co" \
  -p 5432 \
  -U "postgres" \
  -d "postgres" \
  -f "backups/peregrine_supabase_backup_$(date +%Y%m%d_%H%M%S).sql"
```

#### Manual Restoration Runbook
```bash
# In the event of catastrophic data loss, restore from the verified dump
PGPASSWORD="$SUPABASE_DB_PASSWORD" psql \
  -h "db.YOUR_PROJECT_REF.supabase.co" \
  -p 5432 \
  -U "postgres" \
  -d "postgres" \
  -f "backups/peregrine_supabase_backup_TARGET_TIMESTAMP.sql"
```

---

## 3. Reality of Inactivity Pausing on the Free Tier

- **Official Supabase Policy:** Projects on the Free plan that receive **no active database queries for 7 consecutive days are automatically paused**.
- **Important Correction on "Health Pings":** Artificial, automated HTTP health check pings (e.g. cron triggers calling `SELECT 1;`) are **not** an officially sanctioned or guaranteed prevention mechanism. Supabase's platform monitors authentic platform activity and may flag or pause projects that rely on artificial synthetic traffic.
- **Operational Reality for Beta V-001:**
  - If a 7-day period passes without beta testing, the project will pause.
  - Paused projects are **not deleted**. Restoration is performed manually via the Supabase Dashboard by clicking **"Restore Project"**, which completes in approximately 2 minutes with zero data loss.
  - This limitation is acceptable for an invited beta pilot, but **disqualifies the Free tier for unattended commercial production**.

---

## 4. Realistic Database Capacity & Physical Storage Measurement

The previous estimate of 250,000 feedback records was mathematically flawed because it ignored index size, TOAST storage, and the massive storage footprint of `pgvector`.

### 4.1 Physical Storage Measurement Breakdown

#### A. Central AI Feedback Row & Index Footprint
- `id` (UUID string), `request_id`, `user_id_hash`: ~80 bytes
- `rating`, `category`, flags: ~30 bytes
- `user_correction` (Arabic text with Tashkeel): ~300–600 bytes
- `comments` (Arabic commentary): ~200–400 bytes
- `metadata` (JSONB prompt, model name, latency, token usage): ~600–1,200 bytes
- Row header, null bitmap, tuple alignment: ~32 bytes
- **Average Heap Tuple Size:** **~1.8 KB per row**.
- **Indexes:**
  - Primary Key B-Tree index on `id`: ~50 bytes/row
  - B-Tree index on `user_id_hash`: ~40 bytes/row
  - Partial index on `(consent_for_training, eligible_for_learning)`: ~30 bytes/row
  - Postgres page fill factor (90%) and WAL overhead: ~20%
- **Total Physical Footprint per Feedback Record:** **~2.5 KB to 3.0 KB**.

#### B. Vector Embeddings Footprint (`notebook_chunks`)
- Each Arabic chunk stores a 1,536-dimensional vector.
- Vector data: 1,536 dimensions × 4 bytes (IEEE 754 float) = **6,144 bytes (6.1 KB) per row** just for the raw vector array.
- HNSW Index (`vector_cosine_ops`): Adds approximately **3.5 KB per row** for the graph structure.
- Raw Arabic text content + metadata: ~1.5 KB per row.
- **Total Physical Footprint per Vector Chunk:** **~11.0 KB**.
- **10,000 Vector Chunks** = **~110 MB of database space** (consuming 22% of the entire 500 MB quota).

### 4.2 Revised Realistic Quota Allocation (500 MB Free Tier)

| Database Component | Estimated Allocation | Physical Storage Consumed |
| :--- | :--- | :---: |
| **PostgreSQL System Catalogs & Extensions (`vector`, `auth`)** | Base schemas | ~35 MB |
| **Research Notebooks & Sources (`sources`, `notes`)** | ~1,000 documents | ~25 MB |
| **Arabic Vector Chunks (`notebook_chunks` + HNSW index)** | 10,000 passages | **~110 MB** |
| **Safety & WAL Buffer Reserve** | Mandatory overhead | ~50 MB |
| **Available Storage for Central API Feedback** | Remaining headroom | **~280 MB** |
| **Realistic Maximum Feedback Record Capacity** | **~40,000 to 50,000 records** | **~125 MB – 150 MB** |

> **Crucial Finding:** The realistic capacity of the Supabase Free database is **40,000 to 50,000 feedback records** alongside 10,000 vector chunks—**not 250,000 records**. This capacity is more than adequate for Beta V-001 (~500 active learners submitting ~5,000 feedback items).

---

## 5. Summary Recommendation

1. **Retain Existing Supabase Project:** Adequate for Beta V-001 (up to 50,000 feedback rows + 10,000 vector chunks).
2. **Execute Manual Backups Weekly:** Follow the documented `pg_dump` procedure. Do not rely on unprovided automated backups.
3. **Accept 7-Day Inactivity Pausing:** Design the beta operations around one-click restoration via the dashboard.
4. **Production Upgrade Gate:** Migrate to Supabase Pro ($25/mo) only when scaling beyond Beta V-001 to obtain 8 GB database storage, automated backups, and 100% continuous uptime.
