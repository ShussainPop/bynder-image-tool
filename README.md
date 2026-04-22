# Bynder Image Tool

Streamlit app that pulls product images from Bynder by SKU, maps them to Amazon
image slots via per-product-line filename rules, splices reusable infographics,
and exports rename-ready zip packages for Amazon upload.

## Quickstart (local)

    cp .env.example .env
    # edit .env: set BYNDER_PERMANENT_TOKEN, STREAMLIT_PASSWORD at minimum

    docker compose up --build -d

Open http://localhost:8501

## Development

    python -m venv .venv
    source .venv/Scripts/activate  # or .venv/bin/activate on *nix
    pip install -r requirements.txt

    docker compose up -d postgres   # just the database
    alembic upgrade head

    streamlit run src/ui/app.py

If `streamlit run` reports `ModuleNotFoundError: No module named 'bynder_sdk'`,
the `streamlit` on your PATH is resolving to system Python instead of the venv.
Either re-activate the venv, or call the venv's binary directly:
`.venv/Scripts/streamlit.exe run src/ui/app.py` (Windows).

The product catalog (`data/barcelona.xlsx`) is gitignored — it contains
proprietary cost data. The tool resolves SKUs from Supabase first and falls
back to the Excel file, so running against Supabase avoids the dependency.
Ask a teammate for the file if you need local Excel-only development.

## Tests

    pytest tests/ -v --cov=src

## Architecture

- `src/core/` — framework-agnostic business logic. Ports to `popsockets-content-manager` in Phase 2.
- `src/db/` — SQLAlchemy models + Alembic migrations. Tables use `contentup_image_` prefix.
- `src/ui/` — Streamlit tabs. Discarded when we port to content_manager's React frontend.

## Workflow

1. **Mapping Wizard** (per product line, once)
   - Step 1: Paste sample filenames → regex → position → Amazon slot map
   - Step 2: Upload infographics tagged by tier + slot
   - Step 3: Review coverage

2. **Package SKU** (per SKU, daily)
   - Enter SKU
   - Tool fetches from Bynder + applies rules + splices infographics
   - Manual overrides per slot if needed
   - Click Package → renamed zip downloads

3. **Library** — browse/delete infographics across all lines.

4. **Bulk Export** (ad-hoc)
   - Paste SKUs or upload a CSV (first column = SKU)
   - Tool queries Bynder's keyword index for each SKU and filters client-side to assets that mention the SKU in `property_SKUs`, tags, description, or filename. Covers the PopSockets tenant's inconsistent legacy tagging; dedupes by asset id; rate-limited to stay under Bynder's tenant cap
   - Downloads a CSV: one row per matched asset with `sku, image_name, image_link, tags, upc, asset_id`
   - Use the CSV to drive Amazon uploads, spreadsheets, or hand off to a VA
   - Optional env vars (see `.env.example`): `BYNDER_CSV_DERIVATIVE_KEY` for full-resolution CDN URLs, `BYNDER_CSV_UPC_KEYS` to override UPC metaproperty lookup
   - Configuring a full-resolution Bynder derivative: see appendix §16 of `docs/superpowers/specs/2026-04-21-bulk-sku-csv-export-design.md`

## Deployment (Coolify/Vultr)

- Point Coolify at this repo
- Set env vars: `DATABASE_URL` (Supabase), `BYNDER_PERMANENT_TOKEN`, `STREAMLIT_USERNAME`, `STREAMLIT_PASSWORD`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Optional: `BYNDER_CSV_DERIVATIVE_KEY`, `BYNDER_CSV_UPC_KEYS` (for Bulk Export — see Workflow §4)
- Mount persistent volume at `/app/infographics`
- Expose port 8501 behind Coolify's reverse proxy

## Design docs and plans

Full design specs and task-level implementation plans live under
`docs/superpowers/`:

- `specs/2026-04-20-bynder-image-tool-design.md` — original tool design
- `specs/2026-04-21-bulk-sku-csv-export-design.md` — Bulk Export feature design (includes Bynder admin guide for configuring full-resolution derivatives in appendix §16)
- `plans/2026-04-20-bynder-image-tool.md` — original build plan
- `plans/2026-04-21-bulk-sku-csv-export.md` — Bulk Export build plan

## Phase 2 migration to popsockets-content-manager

See `docs/superpowers/specs/2026-04-20-bynder-image-tool-design.md` section 16.
