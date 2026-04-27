# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Streamlit app that pulls product images from Bynder by SKU, maps them to Amazon image slots (`MAIN`, `PT01`…`PT08`) via per-product-line filename rules, splices reusable infographics for empty slots, and exports rename-ready zip packages for Amazon upload. Also exposes a bulk SKU→CSV export that returns one row per matched Bynder asset.

Part of the PopSockets workspace (see `c:\Projects\CLAUDE.md`). Shares Supabase with `popsockets-content-manager`, `amazon-tactical-dashboard`, and `Apify`. All tables in this project use the `contentup_image_` prefix.

## Common commands

```bash
# Local dev (venv + Streamlit)
python -m venv .venv
source .venv/Scripts/activate        # Windows bash; use .venv/bin/activate on *nix
pip install -r requirements.txt
docker compose up -d postgres        # optional — only if DATABASE_URL points to Postgres
alembic upgrade head
streamlit run src/ui/app.py          # serves on :8501

# Full stack via Docker
docker compose up --build -d

# Tests
pytest tests/ -v --cov=src
pytest tests/test_bynder_client.py -v                     # single file
pytest tests/test_bynder_client.py::test_name -v          # single test

# Alembic
alembic revision --autogenerate -m "description"
alembic upgrade head
```

If `streamlit run` fails with `ModuleNotFoundError: bynder_sdk`, the shell resolved `streamlit` outside the venv. Call the venv binary directly: `.venv/Scripts/streamlit.exe run src/ui/app.py`.

## Architecture

Three-layer split designed for a Phase 2 port into `popsockets-content-manager` (FastAPI + React). Preserve this boundary when adding features.

- **`src/core/`** — framework-agnostic business logic. No Streamlit, no FastAPI. Tests call these directly. Ports to `popsockets-content-manager` unchanged in Phase 2.
- **`src/db/`** — SQLAlchemy 2.0 models + Alembic migrations. All tables prefixed `contentup_image_`.
- **`src/ui/`** — Streamlit tabs (wizard / package / library / bulk export). Thin orchestration over `core/`. Discarded when porting to the content_manager's React frontend.

### Core modules

- `bynder_client.py` — wraps `bynder-sdk` v2. `BynderClient.search_by_sku()` issues a single keyword query and filters client-side across `property_SKUs` / tags / description / filename to cover the PopSockets tenant's inconsistent historical tagging. Downloads require a second call (`media_download_url`) because list responses omit `original`. Enforces a sliding-window throttle of 4000 calls / 5 min (10% under the tenant cap of 4500). The `to_asset()` helper (public, formerly `_to_asset`) is reused by `bynder_asset_cache.py` to reconstruct `BynderAsset` from raw cached records.
- `bynder_asset_cache.py` — DB-backed cache for `search_by_sku` results. One row per SKU in `contentup_image_bynder_asset_cache` (JSON column with the raw asset list + `cached_at`). `BynderAssetCache.get_or_fetch(sku, fetch_fn, force_refresh=False)` is the canonical entry point — returns `(assets, was_cache_hit)`. Default TTL 7 days, configurable via `BYNDER_CACHE_TTL_DAYS`. **Empty results are cached** to avoid re-querying SKUs Bynder has nothing for. Wired into `bulk_export.run_export` and `package_helpers.build_package_context`; both accept an optional `cache=` and `force_refresh=` parameter, defaulting to None for back-compat with tests.
- `mapping_engine.py` — `AMAZON_SLOTS` is the canonical slot tuple (`MAIN`, `PT01`…`PT08`). `assign_slots()` uses first-writer-wins on collisions; callers wanting deterministic collision resolution must pre-sort.
- `product_catalog.py` — `ProductCatalog.lookup()` hits Supabase first (`contentup_products` table, columns `seo_cluster_1`, `tier`, `item_description`) and falls back to the gitignored `data/barcelona.xlsx`. Running against Supabase avoids the Excel dependency entirely.
- `infographic_library.py` — stores uploaded infographics to `infographics/<slug>/<tier>/<uuid>.ext`. DB row + file are written as a pair; a DB failure unlinks the file.
- `amazon_packager.py` — validates (≤10MB, JPEG/PNG, warns <1000px) and zips with Amazon-compliant arcnames `<SKU>.<SLOT>.<ext>`.
- `bulk_export.py` — SKU→CSV runner. `MAX_SKUS_PER_RUN=2000`. CSV is UTF-8 with BOM for Excel. Columns fixed: `sku, image_name, image_link, tags, upc, asset_id`. `BulkExportResult.cache_hits` counts SKUs served from cache (surfaced in the UI summary).
- `bynder_urls.py` — URL precedence for CSV export: configured derivative key → `original` → `webimage` fallback.

### DB & config

- `src/db/session.py` — `get_engine()` is `@lru_cache`'d (single engine per process). For SQLite, connects with `PRAGMA foreign_keys=ON` (otherwise FKs are silently ignored). UI code must use `session_scope()` from `src/ui/deps.py` — Streamlit reruns `render()` on every widget interaction and the context manager prevents session leaks.
- `src/config.py` — `Config` is a frozen dataclass loaded once from `.env` via `load_config()`. Always required: `DATABASE_URL`, `BYNDER_DOMAIN`, `STREAMLIT_USERNAME`, `STREAMLIT_PASSWORD`. **Bynder auth**: require *exactly one* of `BYNDER_PERMANENT_TOKEN` or both `BYNDER_CLIENT_ID + BYNDER_CLIENT_SECRET`. Optional: Supabase, `BYNDER_CSV_DERIVATIVE_KEY`, `BYNDER_CSV_UPC_KEYS`, `BYNDER_CACHE_TTL_DAYS` (default 7).
- `DATABASE_URL` defaults to SQLite (`sqlite:///./db/bynder_tool.db`). Data volume (~5k product links) fits comfortably; Postgres is optional.
- Bynder auth: `make_bynder_client()` prefers `BYNDER_CLIENT_ID/SECRET` (client credentials, auto-refresh) over `BYNDER_PERMANENT_TOKEN`.

### UI

- `app.py` prepends project root to `sys.path` so `from src....` resolves when Streamlit runs it directly.
- Auth is shared-credential basic auth via `require_auth()`; single login for Phase 1 (no per-user state).
- `package_tab.py` builds a `PackageContext` (see `package_helpers.py`): Bynder-mapped slots first, then infographics fill empties, then manual overrides via `SkuOverride` rows + `overrides/<sku>/` files.

## Bynder tenant quirks (do not change without Bynder admin coordination)

- SKU metaproperty is named `SKUs` (plural). Server-side queries use `property_SKUs`.
- Full-resolution CDN URLs require a configured derivative. Without `BYNDER_CSV_DERIVATIVE_KEY`, the bulk export falls back to `original`, then to the ~800px `webimage` thumbnail. Admin guide: `docs/superpowers/specs/2026-04-21-bulk-sku-csv-export-design.md` appendix §16.
- Tenant rate cap is 4500 req / 5 min. Throttling is in `BynderClient`; do not bypass it.

## Tests

- `tests/conftest.py` provides `db_engine` + `db_session` fixtures backed by SQLite in-memory with FKs enforced via `PRAGMA`. Production is Postgres/Supabase; SQLite is fine for model-level unit tests.
- `tests/fixtures/` includes `barcelona_sample.xlsx` (generated by `make_barcelona_sample.py`) and `bynder_media_list.json` (a recorded Bynder API response). The real `data/barcelona.xlsx` is gitignored (contains cost data).
- Tests inject `sdk` into `BynderClient(sdk=...)` directly — never call `BynderClient.from_permanent_token()` in tests.

## Deployment

Coolify/Vultr. App UUID `rdzhmu8lzvc7aqhc16v6gaec` on host `137.220.62.47:8000`. Live URL: http://rdzhmu8lzvc7aqhc16v6gaec.137.220.62.47.sslip.io. Dockerfile runs `alembic upgrade head && streamlit run src/ui/app.py`. Required env vars per `.env.example`.

Persistent volumes already mounted on Coolify (verify with `GET /api/v1/applications/{uuid}/storages`):
- `/app/db` → SQLite DB **and** the Bynder asset cache. Wiping this loses all wizard config, infographics metadata, package history, and cache rows.
- `/app/infographics` → uploaded infographic image files.
- `/app/overrides` → per-SKU manual override files.

Coolify env-var management via API: `POST /api/v1/applications/{uuid}/envs` with `{"key": ..., "value": ..., "is_preview": false, "is_literal": true, "is_multiline": false}`. Do **not** include `is_build_time` (not allowed). The READ endpoint is sandbox-blocked to avoid pulling secrets into transcripts.

## Design docs

Full design specs and build plans live under `docs/superpowers/specs/` and `docs/superpowers/plans/`. The Phase 2 migration strategy (porting `src/core/` into `popsockets-content-manager`) is section 16 of `2026-04-20-bynder-image-tool-design.md`.

## Journal maintenance

`JOURNAL.md` (repo root, sibling to this file) records the *why* behind shipped changes — decisions, rationale, gotchas, dead-ends. Git history covers the *what*. They complement each other; keep them in sync.

### When to write
- At the end of a session that produced a real commit: feature, bugfix, schema change, auth change, deploy/infra change.
- Before opening a PR.
- **Skip** for: whitespace, formatting, lockfile bumps, dependency upgrades with no behavior change, comment-only edits, and doc-only commits that document already-journaled work.

### Where
- Append new items under `## Unreleased` (top of file).
- **Never edit dated entries** — they are immutable. If a later change relates, write a new entry that links back.
- At end-of-session checkpoint or release time, promote `## Unreleased` items into a dated entry: `## YYYY-MM-DD — short title (commit `abc1234` / PR #N)`.

### How
Every entry must cite at least one of: 7-char commit SHA, PR number, or specific filename. If you can't cite something concrete, the change isn't journal-worthy.

Per-entry shape (≤5 sections, drop ones that aren't relevant):
1. **Header** — `## YYYY-MM-DD — short title (cite commit/PR)`
2. **What shipped** — bullets, past tense, behavior-level (not file-level diff narration).
3. **Why** — 1–3 sentences. The reason, not the code.
4. **How to verify** — manual repro or the covering test path. Critical for a Streamlit-behind-basic-auth tool with no production CI smoke test.
5. **Gotchas / Open questions** — optional. Vendor quirks (Bynder, Coolify, Supabase), invariants, traps future-you will trip on.

### Signal filter
- Decisions and rationale → write it down.
- Failed approaches and dead-ends → write it down (git only records what shipped).
- Vendor quirks (Bynder rate caps, Coolify API edge cases, Supabase grants) → write it down.
- Diff mechanics, file lists, code that's already self-evident → skip.

### Trust rules for the journal
- Don't backdate entries. The current date sits at the top of `## Unreleased`; promote on the day it's written.
- Don't paraphrase or "summarize" old entries. They are the record.
- If you discover a past entry was wrong, add a new entry correcting it — don't rewrite history.
