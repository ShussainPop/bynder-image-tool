# Bulk SKU CSV Export — Design Spec

**Date:** 2026-04-21
**Owner:** shussain@popsockets.com
**Status:** Draft — awaiting implementation plan
**Parent:** `2026-04-20-bynder-image-tool-design.md` (adds a new tab to the same app)

## 1. Purpose

Let the user paste a list of SKUs, query Bynder for each, and download a single CSV where every row is one image: SKU, image name, image link (Bynder CDN URL), tags, UPC. The CSV is downstream-agnostic — user feeds it into Amazon flat files, internal spreadsheets, or hands it to a VA.

## 2. Scope

- New tab ("Bulk Export") in the existing Streamlit app at `src/ui/`
- Reuses existing Bynder dual-query SKU search (`BynderClient.search_by_sku`)
- Emits one row per Bynder asset matched to each SKU
- No DB persistence. No image downloads. URLs only.

## 3. Non-Goals

- Image download/packaging (that's the existing Package SKU tab)
- Amazon-format-specific export (user will massage the CSV downstream as needed)
- Background jobs, job history, or multi-user coordination
- Bynder derivative auto-configuration — we emit whatever URL is already available; an appendix documents how the admin upgrades quality later

## 4. CSV Schema

One row per Bynder asset. Columns in order:

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `sku` | The queried SKU | String; if an asset matches multiple queried SKUs via `property_SKUs`, a row is emitted per match |
| 2 | `image_name` | `BynderAsset.filename` | Already parsed in `_to_asset()` (bynder_client.py:106-113) |
| 3 | `image_link` | URL fallback chain (§7) | Always a URL string; never empty for a matched asset |
| 4 | `tags` | Raw asset `tags` list, joined by `"; "` | New field on `BynderAsset`, populated in `_to_asset()` |
| 5 | `upc` | Metaproperty lookup (§8) | Empty string if none found |
| 6 | `asset_id` | `BynderAsset.asset_id` | Useful for re-fetching / dedup; included by default |

- **File name**: `bynder_export_<YYYY-MM-DD_HHMMSS>.csv`
- **Encoding**: UTF-8 **with BOM** (so Excel opens it cleanly)
- **Quoting**: `csv.QUOTE_MINIMAL` (RFC 4180)
- **Newlines**: `\n` (not `\r\n`; Excel handles both)

## 5. UI Surface — "Bulk Export" Tab

Added to the sidebar nav in `src/ui/app.py`:

```
Navigate
○ Mapping Wizard
○ Package SKU
○ Library
● Bulk Export            ← new
```

Layout of the tab body:

```
Bulk Export
─────────────────────────────────────────────

Paste SKUs (one per line, or comma-separated):
┌────────────────────────────────────────────┐
│ 806781                                     │
│ 806782                                     │
│ 806783                                     │
└────────────────────────────────────────────┘

— OR —

Upload CSV  [ Choose file ]
  (first column used; header optional — "sku", "SKU", or no header all work)

☐ Include missing-SKU rows
  (when a SKU has no Bynder matches, emit one row with blank image_name/image_link)

[ Generate CSV ]

─── Progress: 23 / 150 SKUs ───────────────────

⚠ 3 SKUs with no Bynder matches:
   806901, 806902, 806905

[ Download bynder_export_2026-04-21_143022.csv ]
```

### 5.1 Parsing SKU input

- Accept paste **and** file upload. If both are populated, paste wins (user just saw it on screen).
- Paste: split on any whitespace or comma, strip, drop empties.
- CSV upload: first column only; skip first row if it looks like a header (`sku`/`SKU`/`Sku`); no pandas dependency needed — stdlib `csv`.
- Dedupe case-insensitively but preserve the **first** casing the user entered.
- Hard cap at **2,000 SKUs per run** to stay well under Bynder's 4,500 req / 5 min rate limit (§9). Over cap → error banner "Please split into smaller batches."

## 6. Data Flow

```
user pastes / uploads SKUs
        │
        ▼
bulk_export_tab.render()
        │
        ▼
parse_skus()  ── strip, dedupe, cap at 2000
        │
        ▼
for each sku (loop with st.progress):
    BynderClient.search_by_sku(sku)   ← existing method; returns list[BynderAsset]
        │
        ▼
    for each asset:
        row = build_row(sku, asset, derivative_key, upc_keys)
        writer.writerow(row)
        │
        ▼
on completion:
    csv_bytes = buffer.getvalue().encode("utf-8-sig")
    st.download_button(..., data=csv_bytes, file_name=<timestamped>)
```

No DB writes. No file-system writes. Everything stays in memory.

## 7. Image Link Fallback Chain

New helper: `src/core/bynder_urls.py`.

```python
def resolve_csv_url(raw_asset: dict, derivative_key: str | None) -> str:
    """Return the best available public CDN URL for this asset.

    Precedence:
      1. Configured custom derivative (admin-defined, e.g. 'amazon_full')
      2. `original` field (if tenant has public-originals enabled)
      3. `webimage` (always present but ~800px — low quality fallback)
    """
    thumbs = raw_asset.get("thumbnails") or {}
    if derivative_key and thumbs.get(derivative_key):
        return thumbs[derivative_key]
    if raw_asset.get("original"):
        return raw_asset["original"]
    return thumbs.get("webimage", "")
```

`derivative_key` is read from the new optional env var `BYNDER_CSV_DERIVATIVE_KEY`. Unset → chain skips step 1 automatically. **Tool works today without any Bynder admin changes**; the operator can upgrade URL quality later by following the appendix.

## 8. UPC Resolution

Extracted from the raw Bynder asset dict. Reads keys in order defined by env var `BYNDER_CSV_UPC_KEYS` (comma-separated; defaults to `property_UPC,property_GTIN,property_Barcode`). Returns empty string if no candidate key is present.

Why read multiple key names: (a) we don't know which name (if any) exists on the tenant today, (b) users can extend without code changes if they add a metaproperty later.

Metaproperties in Bynder list responses are returned as top-level `property_<Name>` keys where the value is either a string or a list of strings. Helper joins list values with `"; "`.

## 9. Rate Limiting and Performance

Bynder: **4,500 req / 5 min** tenant-wide.

`search_by_sku` fires **2 requests per SKU** (tags + property_SKUs). Theoretical max = 2,250 SKUs / 5 min. Our 2,000-SKU cap sits 10% under that.

Implementation:
- Simple sliding-window throttle in `BynderClient` (timestamps of last N requests; sleep if next would breach 4,000/5min — stays 10% under limit).
- Progress reported via `st.progress()` every SKU.
- No parallelism in Phase 1 — serial is fast enough and simpler. Revisit if user reports slowness.

## 10. Error Handling

| Condition | Behavior |
|---|---|
| Empty input after parse | Error banner: "Paste at least one SKU or upload a CSV." No download button. |
| > 2,000 SKUs | Error banner with split instruction. Input preserved so user can edit and retry. |
| Bynder auth fails | Toast with the exception message. Stop. |
| Single SKU raises (rate limit, network) | Retry once after 2s. If still fails, record in `errors` list, continue with remaining SKUs. |
| SKU returns 0 assets | Recorded in `missing_skus` list. If "Include missing-SKU rows" checked, emit one row per missing SKU with blank image fields. |
| All SKUs fail | Error banner "Bynder returned errors for every SKU" + first 3 error messages. No download button. |
| Some SKUs succeed, some fail | Partial download button **plus** a warning listing failed SKUs so user can retry them. |

## 11. Extensions to Existing Code

### 11.1 `src/core/bynder_client.py`

```python
@dataclass(frozen=True)
class BynderAsset:
    asset_id: str
    filename: str
    original_url: str
    sku: str | None
    extension: str
    thumbnail_url: str = ""
    tags: tuple[str, ...] = ()                              # NEW
    metaproperties: dict[str, str] = field(default_factory=dict)  # NEW
    raw: dict = field(default_factory=dict)                 # NEW — retained for CSV row building

# _to_asset() extended:
#   - tags = tuple(raw.get("tags") or ())
#   - metaproperties = {k: _stringify(v) for k, v in raw.items() if k.startswith("property_")}
#   - raw = raw (the full dict)
```

`_stringify()` joins list values with `"; "` and coerces scalars to `str`.

**Note:** storing `raw` makes `BynderAsset` no longer truly frozen-immutable (dicts are mutable). That's acceptable — we never mutate `raw` after construction. If a reviewer objects, we drop `raw` and re-read the relevant keys inside `build_row()` from metaproperties only.

### 11.2 `src/config.py`

Add:

```python
bynder_csv_derivative_key: str | None       # env: BYNDER_CSV_DERIVATIVE_KEY (optional)
bynder_csv_upc_keys: list[str]              # env: BYNDER_CSV_UPC_KEYS
                                            #   default: "property_UPC,property_GTIN,property_Barcode"
```

### 11.3 `src/ui/app.py`

One-line addition to the sidebar radio options list and a new import branch.

### 11.4 `.env.example`

Document the two new optional env vars with a comment pointing at the appendix.

## 12. New Modules

### 12.1 `src/core/bulk_export.py`

Framework-agnostic. Callable from Streamlit today, portable to FastAPI in Phase 2.

```python
@dataclass
class BulkExportRow:
    sku: str
    image_name: str
    image_link: str
    tags: str
    upc: str
    asset_id: str

@dataclass
class BulkExportResult:
    rows: list[BulkExportRow]
    missing_skus: list[str]            # queried but had zero matches
    failed_skus: list[tuple[str, str]] # (sku, error message)

def parse_sku_input(text: str) -> list[str]: ...
def parse_sku_csv(upload_bytes: bytes) -> list[str]: ...

def build_row(
    sku: str,
    asset: BynderAsset,
    derivative_key: str | None,
    upc_keys: list[str],
) -> BulkExportRow: ...

def run_export(
    skus: list[str],
    client: BynderClient,
    derivative_key: str | None,
    upc_keys: list[str],
    include_missing: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> BulkExportResult: ...

def to_csv_bytes(result: BulkExportResult) -> bytes:
    """UTF-8 with BOM, RFC4180 quoting, columns per §4."""
```

Signatures are chosen so Streamlit's session state and `st.progress` integration live entirely in the UI layer — `run_export` stays pure.

### 12.2 `src/core/bynder_urls.py`

Just the `resolve_csv_url` function from §7. Separate file because it's the seam we expect to grow (more URL types, format preferences) over time.

### 12.3 `src/ui/bulk_export_tab.py`

Owns the Streamlit layout from §5. Calls into `src/core/bulk_export.py` for all logic.

## 13. Testing

- `tests/core/test_bynder_urls.py`
  - derivative key present → returns it
  - derivative unset but `original` populated → returns original
  - both missing → returns webimage
  - all missing → empty string
- `tests/core/test_bulk_export_parse.py`
  - paste with newlines + commas + blanks → deduped list
  - CSV upload with header "SKU" → stripped
  - CSV upload without header → first cell used
  - over-cap input → raises
- `tests/core/test_bulk_export_builder.py`
  - one SKU, three assets → three rows, correct columns
  - asset with no `property_UPC` but has `property_GTIN` → `upc` column uses GTIN
  - asset with list-valued tags → tags joined with `"; "`
  - missing SKU with `include_missing=True` → emits blank-image row
  - rate limit exception → caught and recorded in `failed_skus`, export continues
- UI tested manually. Streamlit test harness remains out of scope per parent spec §13.

All Bynder-client interaction in tests uses the same recorded-fixture approach as the existing parent spec tests.

## 14. Files Touched — Summary

**New files:**
- `src/core/bulk_export.py`
- `src/core/bynder_urls.py`
- `src/ui/bulk_export_tab.py`
- `tests/core/test_bulk_export_parse.py`
- `tests/core/test_bulk_export_builder.py`
- `tests/core/test_bynder_urls.py`

**Modified files:**
- `src/core/bynder_client.py` — extend `BynderAsset`, populate new fields in `_to_asset()`
- `src/config.py` — add two new config fields
- `src/ui/app.py` — add tab to sidebar
- `.env.example` — document new env vars

**Unchanged:**
- DB schema / Alembic migrations (no new tables)
- Mapping Wizard, Package SKU, Library tabs
- Dockerfile, docker-compose.yml
- Existing Bynder authentication logic

## 15. Phase 2 Portability

`src/core/bulk_export.py` and `src/core/bynder_urls.py` port verbatim into `popsockets-content-manager` in Phase 2 alongside the rest of `src/core/`. FastAPI endpoint wraps `run_export()` and streams the CSV response. React tab mirrors the Streamlit layout. No schema changes needed.

## 16. Appendix — Configuring a Full-Resolution Bynder Derivative (Admin)

This is the recommended one-time setup for the tenant admin to get Amazon-quality URLs in the `image_link` column. Skip if you're happy with ~800px `webimage` URLs for now.

**A. Create the derivative**

1. In Bynder, go to **Account** (top-right user menu) → **Asset Management** → **Derivatives**
2. Click **+ New derivative**
3. Name it `amazon_full` (this value goes into `BYNDER_CSV_DERIVATIVE_KEY`)
4. Settings:
   - **Resize rule:** "Do not resize" (or "Max side: 2500" if you want a ceiling to stay under Amazon's 10 MB limit on very large sources)
   - **Format:** JPEG
   - **Quality:** 95
   - **Background:** White (matters only for transparent PNG sources)
5. Save

Bynder will backfill this derivative for all existing assets over several hours. New uploads get it automatically.

**B. Confirm it's publicly accessible**

1. Account → **Portal settings** → **Asset access**
2. Verify derivatives are exposed in the public CDN (on by default for most tenants)

**C. Point the tool at it**

In the Bynder Image Tool's `.env`:

```
BYNDER_CSV_DERIVATIVE_KEY=amazon_full
```

Restart the app (Coolify: redeploy; local Docker: `docker compose restart`).

**D. Verify**

Run a small Bulk Export for one test SKU. Open the resulting CSV, copy an `image_link` URL, paste into a browser. You should get a full-size JPEG rendered at the source's native resolution. If you instead get an 800px preview, the derivative name in the env var doesn't match what you created in step A3.

**E. Alternative — enable public `original`**

If you prefer serving the uploaded source file byte-for-byte (lossless, but you get whatever the photographer uploaded — possibly 40MB TIFFs): Account → Portal settings → **Asset access** → enable "Allow public download of originals." The fallback chain in §7 will then pick up the `original` URL automatically without setting `BYNDER_CSV_DERIVATIVE_KEY`.

## 17. Open Questions

None at spec time. UPC key names, derivative key name, and rate-limit headroom are all env-var-configurable, so changes post-implementation don't require code edits.
