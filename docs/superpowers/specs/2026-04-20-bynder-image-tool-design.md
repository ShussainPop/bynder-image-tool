# Bynder Image Pipeline Tool — Design Spec

**Date:** 2026-04-20
**Owner:** shussain@popsockets.com
**Status:** Draft — awaiting implementation plan

## 1. Purpose

Semi-automated pipeline that pulls product images from Bynder, maps them to Amazon's listing image slots (`MAIN`, `PT01`…`PT08`), splices in reusable infographics, and exports rename-ready zip packages for Amazon upload.

## 2. Scope

- **Phase 1 (this spec):** Standalone Streamlit app with Postgres backend. Local Docker for dev; Coolify/Vultr for team use.
- **Phase 2 (future, out of scope):** Integrate into `popsockets-content-manager` as a new "Image Pipeline" tab. Zero data migration — same tables, same SQLAlchemy models.

## 3. Goals

- Pull Bynder assets for a given SKU via OAuth2 or permanent token.
- Apply filename-based rules per product line to auto-assign Amazon slots.
- Allow manual reorder, swap, and custom upload per slot.
- Mix in local infographics by `(product_line, tier)` for empty slots.
- Produce a downloadable zip with Amazon-compliant filenames (`<SKU>.MAIN.jpg`, `<SKU>.PT01.jpg`, …).
- Keep a full audit trail of every package built.

## 4. Non-Goals (Phase 1)

- Automatic image classification via computer vision.
- Direct upload to Amazon SP-API.
- Bulk batch packaging (single SKU at a time in Phase 1).
- Multi-user authentication — single shared login behind Streamlit basic auth.

## 5. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| UI | Streamlit | Matches `content_Accuracy_Dashboard` pattern; fast to build |
| Language | Python 3.11 | Consistent with workspace |
| ORM | SQLAlchemy 2.0 | Matches `popsockets-content-manager` |
| Migrations | Alembic | Matches `popsockets-content-manager` |
| DB | Postgres 15 | Local Docker dev → shared Supabase prod |
| Bynder | `bynder-sdk` (Python) | Official SDK |
| Excel fallback | pandas + openpyxl | Matches workspace convention |
| Image handling | Pillow | Validation + optional resizing |
| Packaging | Docker + docker-compose | Deploy to Coolify/Vultr |

## 6. Data Sources

- **Bynder API** — OAuth2 or permanent token. Queries by SKU metaproperty. Rate limit: 4,500 req / 5 min.
- **Supabase** (project `xjvwwwfpauazdzibclmc` — shared with content_manager, tadash, apify) — primary product catalog lookup.
- **Excel fallback:** `C:\Users\sufis\Downloads\Barcelona 5.0 - Global Amazon Product List.xlsx`
  - `SKU` — primary key
  - `SEO Cluster 1` (column AN) — **product_line key**
  - `Tier for Forecasting - US` — tier
  - `Collection`, `Finance Planning Category`, `Item Description` — display context only

## 7. Architecture

```
bynder-image-tool/
├── src/
│   ├── core/                       (framework-agnostic — ports to FastAPI in Phase 2)
│   │   ├── bynder_client.py        (OAuth / permanent token, SKU search, download)
│   │   ├── product_catalog.py      (Supabase primary + Excel fallback)
│   │   ├── mapping_engine.py       (filename regex → Amazon slot)
│   │   ├── infographic_library.py  ((product_line, tier, slot) → file)
│   │   └── amazon_packager.py      (rename, validate, zip)
│   ├── db/
│   │   ├── models.py               (SQLAlchemy)
│   │   ├── session.py
│   │   └── alembic/
│   └── ui/                         (Streamlit — discarded in Phase 2)
│       ├── app.py
│       ├── wizard_tab.py
│       ├── package_tab.py
│       └── library_tab.py
├── infographics/                   (local file storage, gitignored)
├── tests/
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── .env.example
```

**Key discipline:** `src/core/` has zero Streamlit imports. All UI code stays in `src/ui/`. Phase 2 lifts `src/core/` and `src/db/` verbatim into `popsockets-content-manager/backend/app/services/image_pipeline/`.

## 8. Database Schema

Tables use `contentup_image_*` prefix in `public` schema, matching `contentup_` convention from content_manager.

```sql
CREATE TABLE contentup_image_product_lines (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,                    -- value of SEO Cluster 1
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE contentup_image_filename_patterns (
  id SERIAL PRIMARY KEY,
  product_line_id INT REFERENCES contentup_image_product_lines(id) ON DELETE CASCADE,
  regex TEXT NOT NULL,
  sample_filename TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE contentup_image_filename_rules (
  id SERIAL PRIMARY KEY,
  product_line_id INT REFERENCES contentup_image_product_lines(id) ON DELETE CASCADE,
  position_label TEXT NOT NULL,                 -- 'Front', 'Back', 'Scale'
  amazon_slot TEXT NOT NULL,                    -- 'MAIN' | 'PT01' | ... | 'PT08'
  UNIQUE (product_line_id, position_label)
);

CREATE TABLE contentup_image_infographics (
  id SERIAL PRIMARY KEY,
  product_line_id INT REFERENCES contentup_image_product_lines(id) ON DELETE CASCADE,
  tier TEXT NOT NULL,
  amazon_slot TEXT NOT NULL,
  file_path TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE contentup_image_sku_overrides (
  id SERIAL PRIMARY KEY,
  sku TEXT NOT NULL,
  amazon_slot TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('bynder', 'upload')),
  bynder_asset_id TEXT,
  uploaded_file_path TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (sku, amazon_slot)
);

CREATE TABLE contentup_image_package_history (
  id SERIAL PRIMARY KEY,
  sku TEXT NOT NULL,
  packaged_by TEXT,
  slot_manifest JSONB,                          -- {MAIN: {source, file}, PT01: {...}}
  zip_filename TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Indexes: `CREATE INDEX ON contentup_image_infographics (product_line_id, tier, amazon_slot);` — hot path for slot-fill lookup.

## 9. UI Surfaces

### 9.1 Mapping Wizard (Tab 1)

Per-product-line setup. Left nav lists existing lines (from Postgres + `SEO Cluster 1` values in catalog). Right pane = 3-step wizard.

**Step 1 — Filename rules**
- Paste 3–5 Bynder filenames for this line
- Tool infers regex (default: `_(\d{2})_(\w+)\.(png|jpg|jpeg)$`), editable
- Extracted unique position labels (`Front`, `Back`, `Scale`, `Detail`, …) surface as a table
- Each row gets an Amazon slot dropdown (`MAIN`/`PT01`…`PT08`)

**Step 2 — Infographic upload**
- Drag-drop or file picker
- Per file: tier dropdown (from `Tier for Forecasting - US`) + target slot dropdown
- Inline preview
- Files saved to `./infographics/<product_line_slug>/<tier>/<uuid>.<ext>`
- Metadata row inserted in `contentup_image_infographics`

**Step 3 — Review + save**
- Shows full rule set for this line + infographic coverage matrix (tier × slot)
- Flags gaps: "Tier A: MAIN infographic missing"
- Save commits all changes in a single Postgres transaction

### 9.2 Package SKU (Tab 2)

Daily driver. Workflow:

1. SKU input with autocomplete (catalog-backed)
2. Auto-lookup `SEO Cluster 1` + `Tier` from Supabase; Excel fallback
3. Fetch Bynder assets via SKU metaproperty
4. `mapping_engine` assigns each asset to a slot via product line rules
5. Empty slots filled from `contentup_image_infographics` matching `(product_line, tier, slot)`
6. **9-tile preview grid** (MAIN + PT01…PT08). Each tile shows:
   - Thumbnail
   - Source badge: `Bynder` / `Infographic` / `Empty` / `Override`
   - Original filename + dimensions
7. Manual fixes:
   - Drag-to-reorder across slots
   - Click-to-swap from a sidebar of unassigned Bynder assets
   - "Upload custom" button per slot (writes to `contentup_image_sku_overrides`)
8. **Package button:**
   - Validates (see Section 11)
   - Renames to `<SKU>.<SLOT>.<ext>`
   - Zips to `<SKU>_images.zip`
   - Offers browser download
   - Writes row to `contentup_image_package_history` with `slot_manifest` JSONB

### 9.3 Browse Library (Tab 3)

Tabular view of all infographics. Filter by product line, tier, slot. Actions: replace file, edit metadata, delete. Not in critical path.

## 10. Bynder Integration

- **Auth:** Permanent token in Phase 1 (simplest). OAuth2 authorization-code flow supported as config option for Phase 2 migration readiness.
- **Asset search:** `asset_bank_client.media_list({'propertyOptionId': <sku_option_id>})` — resolves SKU to Bynder's internal option ID via metaproperty lookup cache.
- **Download:** Stream `original` URL via `requests` to local temp dir.
- **Rate limiting:** Simple in-process sliding-window throttle; 4,000 req / 5 min safe target (10% under limit).

## 11. Amazon Filename Convention + Validation

Output filename: `<SKU>.<SLOT>.<ext>` where `<SLOT>` ∈ `{MAIN, PT01, PT02, PT03, PT04, PT05, PT06, PT07, PT08}`.

Validation performed at Package time:
- Minimum 1000×1000px — warn (non-blocking)
- JPEG or PNG only — block if violated
- MAIN must be opaque JPEG — warn if PNG with transparency
- File size < 10 MB — block if violated
- Slot collisions — block (should be impossible given UI, defensive check)

## 12. Error Handling

| Condition | UI response |
|---|---|
| Bynder auth fails | Toast with retry; link to Wizard → Settings |
| Bynder returns 0 assets for SKU | Warning banner + fallback to "all slots empty, fill manually" |
| SKU not in Supabase or Excel | Prompt for `product_line` + `tier` via dropdowns, proceed |
| Regex fails to match a filename | Asset listed under "Unmapped" section with manual-assign button |
| Infographic missing for a slot | Slot rendered as `Empty` with warning; package allowed with user confirmation |
| DB write fails | Toast error, do not produce zip |

## 13. Testing Strategy

- `pytest` + `pytest-cov`
- Unit tests per `src/core/` module with ≥80% coverage
- `bynder_client` tests use recorded fixtures (vcr.py style), no live API
- `mapping_engine` tests use curated filename samples per product line fixture
- `amazon_packager` end-to-end: input manifest → zip → validate contents
- UI tested manually — Streamlit's test harness is too thin for the ROI in Phase 1

## 14. Environment Variables

```
DATABASE_URL=postgresql://user:pass@localhost:5432/bynder_tool   # or Supabase URL in prod
BYNDER_DOMAIN=popsockets.bynder.com
BYNDER_PERMANENT_TOKEN=<token>
BYNDER_CLIENT_ID=<optional>
BYNDER_CLIENT_SECRET=<optional>
BYNDER_REDIRECT_URI=<optional>
PRODUCT_CATALOG_XLSX_PATH=./data/barcelona.xlsx
INFOGRAPHICS_DIR=./infographics
STREAMLIT_USERNAME=<shared>
STREAMLIT_PASSWORD=<shared>
```

## 15. Deployment

**Local dev:**
```
docker-compose up --build
```
Postgres on 5432, Streamlit on 8501.

**Coolify/Vultr (team prod):**
- Same Docker image
- `DATABASE_URL` points to Supabase
- Volume mount `/data/infographics` → persistent disk
- HTTP basic auth via Coolify reverse proxy (Streamlit's native auth is weak)

## 16. Phase 2 Migration (Future — documented for design discipline)

1. Copy `src/core/*` → `content_manager/backend/app/services/image_pipeline/`
2. Copy `src/db/models.py` contents into content_manager's SQLAlchemy models
3. Run the same Alembic migrations against shared Supabase
4. Add FastAPI routes in `content_manager/backend/app/routes/images.py` wrapping each core function
5. Build React gallery component in `content_manager/frontend/src/features/image-pipeline/`
6. Migrate infographics from local disk to Supabase Storage (scripted one-time move)

No schema migration. No data migration.

## 17. Open Questions

None at spec time. Infographic dimension/format requirements are left flexible in Phase 1 — will revisit if Amazon rejects any output zips during early use.
