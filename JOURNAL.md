# JOURNAL.md

Engineering journal for `bynder-image-tool`. Records the *why* behind shipped
changes — decisions, rationale, gotchas, things that didn't work. Git history
covers the *what*; this file covers the reasoning future-you (or future Claude)
won't be able to recover from `git log`.

Format: newest first. Maintenance rules in `CLAUDE.md` § *Journal maintenance*.

---

## Unreleased

### 2026-04-27 — Bulk Export: Browse-by-SKU view with per-asset & per-SKU zip downloads

**What shipped**
- Bulk Export tab now renders a "Browse by SKU" section under the existing
  CSV download. Images grouped per SKU in expanders, 4-column thumbnail grid
  using `BynderAsset.thumbnail_url` (CDN — no Bynder API hit, throttle-safe).
- Per-asset **Download ↗** link button pointing at the resolved full-res CDN
  URL (same URL the CSV emits).
- Per-SKU two-step **Build .zip → Download `<sku>.zip`** flow. Zip is built
  in-memory by fetching each asset's full-res URL via `requests`, written
  with arcnames `<sku>__<filename>` (collisions disambiguated as `(2)`).
- Pagination at 25 SKUs/page (`INLINE_PAGE_SIZE`) so 2000-SKU runs don't
  blow up the DOM.
- New `src/core/sku_bundle.py::build_sku_zip()` — framework-agnostic helper
  with an injectable `fetch` callable for testing.
- New `BulkExportResult.assets_by_sku: dict[str, list[BynderAsset]]` —
  parallel to `rows`, keyed on SKU. CSV contract (`BulkExportRow`,
  `to_csv_bytes`, `CSV_COLUMNS`) is unchanged.
- 6 new tests in `tests/test_sku_bundle.py` + 1 new assertion in
  `tests/test_bulk_export_runner.py`. Full suite: 99 passed.

**Why**
User wanted bulk export to double as a quick image browser — find a SKU,
eyeball its assets, grab one image (or all of them) without copy-pasting URLs
out of the CSV. CSV-only output forced an extra round-trip to a file picker.

**How to verify**
- `pytest tests/ -q` → 99 passed.
- Live (http://rdzhmu8lzvc7aqhc16v6gaec.137.220.62.47.sslip.io): Bulk
  Export → paste a few SKUs known to have Bynder hits → Generate. Confirm
  thumbnails render in expanders, **Download ↗** opens/downloads the
  full-res file, **Build .zip** then **Download `<sku>.zip`** produces a
  zip with every image for that SKU.
- 30+ SKUs → confirm Prev/Next paginator and 25-per-page slicing.

**Follow-up the same day**
- Per-asset download swapped from `st.link_button` (which navigated to the
  Bynder CDN URL — and Bynder doesn't send `Content-Disposition: attachment`,
  so browsers rendered images inline) to a two-step **Prepare → Save**
  pattern matching the existing per-SKU zip flow. Bytes are fetched on
  click via `sku_bundle.fetch_asset_bytes` (renamed from the private
  `_default_fetch`), stashed in `st.session_state`, and served via a real
  `st.download_button`. New `_clear_cached_bytes()` wipes per-asset and
  per-SKU-zip bytes from session_state when a fresh export runs.

**Gotchas**
- Streamlit's `st.download_button` requires bytes at render time, not on
  click — that's why everything downloadable is a two-step pattern.
  Pre-fetching every visible asset on render would mean ~25 SKUs × ~5
  assets × 1–5 MB each = potentially hundreds of MB on every paginator
  click. Two-step + session_state is the right cost/UX trade.
- Switched to a `st.session_state["bulk_export_state"]` stash so paginator
  clicks and "Build .zip" reruns don't lose the export result. Previously
  the tab's whole state was gated on the **Generate CSV** button being
  True on the current run, which meant any subsequent button click wiped
  the view.
- `BynderAsset` is a frozen dataclass with no SQLAlchemy linkage, so
  reading `result.assets_by_sku` after `session_scope()` exits is safe.

---

_(Promote items from here into a dated section at end-of-session or release time.)_

---

## 2026-04-27 — Bynder SKU asset cache + doc refresh (`cf36501`)

### What shipped
- New `contentup_image_bynder_asset_cache` table — one row per SKU keyed on
  the SKU itself, JSON column with the raw Bynder asset list, plus a
  `cached_at` timestamp. Default TTL **7 days** (`BYNDER_CACHE_TTL_DAYS`).
- `BynderAssetCache.get_or_fetch(sku, fetch_fn, force_refresh=False)` is the
  single entry point. Wired into `bulk_export.run_export` and
  `package_helpers.build_package_context`. Both still accept `cache=None` so
  existing tests stayed untouched.
- Bulk Export — summary now shows **Cached** alongside Rows / Missing /
  Errors. New "Force refresh from Bynder" checkbox bypasses the cache.
- Package SKU — new "Refresh from Bynder" button next to *Fetch Bynder
  assets*.
- Renamed `_to_asset` → `to_asset` (no external callers) so the cache module
  can reconstruct `BynderAsset` objects from cached raw records.
- 92 tests passing (10 new: 7 cache, 3 bulk-export integration).
- Docs catch-up — README cache section, CLAUDE.md core-modules + deployment
  sections, `.env.example` updated.

### Why
Bulk Export was hitting Bynder once per SKU on every run. A 2000-SKU run
consumed roughly half the 4500-call/5-min tenant rate cap. User: *"I don't
want to query Bynder if we already have the links for SKUs."* Cache lives in
the SQLite DB on the `/app/db` volume that Coolify already had mounted —
survives redeploys for free.

### How to verify
- `pytest tests/ -v` → 92 passed.
- Live (http://rdzhmu8lzvc7aqhc16v6gaec.137.220.62.47.sslip.io): paste 5 SKUs
  in Bulk Export, generate. Repeat. Second run shows `Cached: 5` and is
  near-instant. Tick "Force refresh from Bynder" to confirm bypass.
- Live: Package SKU → fetch a SKU → re-enter same SKU → instant; click
  "Refresh from Bynder" → re-queries.

### Gotchas
- **Empty results are cached intentionally.** If Bynder gets new images for a
  previously-empty SKU, the user must hit Force Refresh or wait for TTL.
- The Coolify env-var POST endpoint **rejects** the `is_build_time` field
  (HTTP 422). Use only `is_preview`, `is_literal`, `is_multiline`.
- Alembic autogenerate against SQLite required pre-creating `./db/` and
  pointing `DATABASE_URL` at a SQLite file (the local `.env` had a Postgres
  URL pointing at a stopped container).

---

## 2026-04-23 — Coolify deploy live + optional Bynder permanent token (`c04d783`)

### What shipped
- App live at http://rdzhmu8lzvc7aqhc16v6gaec.137.220.62.47.sslip.io
  (Coolify UUID `rdzhmu8lzvc7aqhc16v6gaec`, branch `master`, port 8501).
- `src/config.py` no longer requires `BYNDER_PERMANENT_TOKEN`
  unconditionally. Now requires *exactly one* of: permanent token, OR both
  `BYNDER_CLIENT_ID` + `BYNDER_CLIENT_SECRET`.
- Coolify env vars set via API: `BYNDER_CLIENT_ID`, `BYNDER_CLIENT_SECRET`,
  `STREAMLIT_USERNAME`, `STREAMLIT_PASSWORD`.
- Persistent volumes confirmed pre-mounted on Coolify: `/app/db`,
  `/app/infographics`, `/app/overrides`.
- `.env.coolify` rewritten to point at this app's UUID (it had been copied
  from `popsockets-content-manager` and was targeting that app's UUID).

### Why
First deploy attempt crashed during `alembic upgrade head` with
`RuntimeError: Missing required env vars: BYNDER_PERMANENT_TOKEN,
STREAMLIT_USERNAME, STREAMLIT_PASSWORD`. The Streamlit creds genuinely
weren't set, but the permanent-token requirement was a config bug —
`make_bynder_client()` already prefers client credentials (auto-refreshing)
when both are set, so requiring the token at config-load time prevented the
client-credentials path from ever running.

### How to verify
- `GET /api/v1/applications/rdzhmu8lzvc7aqhc16v6gaec` → `running:healthy`.
- `curl http://.../`_stcore/health` → `ok` (HTTP 200).
- Login `admin` / `PopSockets2026!` lands on the Streamlit nav.

### Gotchas
- **Coolify env-var GET endpoint is sandbox-blocked** (pulls live secrets
  into the chat transcript). Use POST/PATCH only; verify writes by triggering
  a deploy and reading the failure mode of the build container.
- Alembic `env.py` calls `load_config()` at import time, so missing env vars
  fail *before* migrations run. The deploy log surfaces this as a Python
  `RuntimeError` traceback inside the alembic call — easy to misread as an
  alembic problem.
- Coolify warns "Dockerfile or Docker Image based deployment detected. The
  healthcheck needs a curl or wget…" — harmless. Our Dockerfile installs
  curl and defines its own `HEALTHCHECK`; Coolify's `health_check_enabled`
  is false because it defers to the Dockerfile probe.
