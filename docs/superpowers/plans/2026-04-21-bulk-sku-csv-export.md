# Bulk SKU CSV Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Bulk Export" Streamlit tab that takes a list of SKUs, queries Bynder (reusing the existing dual-query search), and emits one CSV row per matched asset with `sku, image_name, image_link, tags, upc, asset_id`.

**Architecture:** New framework-agnostic module `src/core/bulk_export.py` owns parsing, row building, orchestration, and CSV serialization. `src/core/bynder_urls.py` owns the URL fallback chain. `BynderAsset` gets two new fields (`tags`, `metaproperties`). UI is a thin `src/ui/bulk_export_tab.py` that calls into `src/core/` — no business logic in the tab. Rate limiting is a sliding-window throttle inside `BynderClient`.

**Tech Stack:** Python 3.11, Streamlit 1.40, `bynder-sdk` 2.0, stdlib `csv`, pytest + pytest-mock.

**Reference spec:** `docs/superpowers/specs/2026-04-21-bulk-sku-csv-export-design.md`

---

## File Map

**New files:**
- `src/core/bynder_urls.py` — URL fallback chain (Task 2)
- `src/core/bulk_export.py` — parsing, row builder, runner, CSV serialization (Tasks 4–7, 9)
- `src/ui/bulk_export_tab.py` — Streamlit layout (Task 10)
- `tests/test_bynder_urls.py` (Task 2)
- `tests/test_bulk_export_parse.py` (Task 4)
- `tests/test_bulk_export_builder.py` (Task 5)
- `tests/test_bulk_export_runner.py` (Tasks 6, 9)
- `tests/test_bulk_export_csv.py` (Task 7)

**Modified files:**
- `src/core/bynder_client.py` — extend `BynderAsset`, populate new fields in `_to_asset()`, add throttle in Task 9 (§11.1 of spec)
- `src/config.py` — two new config fields (§11.2 of spec)
- `src/ui/app.py` — add "Bulk Export" to sidebar (§11.3 of spec)
- `.env.example` — document new env vars (§11.4 of spec)
- `tests/test_bynder_client.py` — cover new BynderAsset fields
- `tests/test_config.py` — cover new config fields

---

## Task 1: Extend `BynderAsset` with `tags` and `metaproperties`

**Files:**
- Modify: `src/core/bynder_client.py`
- Modify: `tests/test_bynder_client.py`

- [ ] **Step 1: Write failing test for new `tags` and `metaproperties` fields**

Append to `tests/test_bynder_client.py`:

```python
def test_to_asset_captures_tags_and_metaproperties(mocker):
    raw = {
        "id": "asset-010",
        "name": "PCS_TEST_01_Front",
        "type": "image",
        "extension": ["jpg"],
        "property_SKUs": ["SKU-010"],
        "property_UPC": "842978104324",
        "property_Color": ["Black", "Carbon"],
        "tags": ["SKU-010", "swappable", "case"],
    }
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = [raw]
    client = BynderClient(sdk=fake_sdk)

    assets = client.search_by_sku("SKU-010")
    assert len(assets) == 1
    a = assets[0]
    assert a.tags == ("SKU-010", "swappable", "case")
    assert a.metaproperties["property_UPC"] == "842978104324"
    assert a.metaproperties["property_Color"] == "Black; Carbon"
    assert "property_SKUs" in a.metaproperties
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_client.py::test_to_asset_captures_tags_and_metaproperties -v`
Expected: FAIL with `AttributeError: 'BynderAsset' object has no attribute 'tags'`

- [ ] **Step 3: Extend the dataclass and `_to_asset()` in `src/core/bynder_client.py`**

At the top of `src/core/bynder_client.py`, change the imports to include `field`:

```python
from dataclasses import dataclass, field
```

Replace the `BynderAsset` dataclass (currently lines 11–19) with:

```python
@dataclass(frozen=True)
class BynderAsset:
    asset_id: str
    filename: str
    original_url: str  # may be empty; use download_asset() which resolves the signed URL
    sku: str | None
    extension: str
    thumbnail_url: str = ""  # Bynder 'webimage' CDN URL for preview
    tags: tuple[str, ...] = ()
    metaproperties: dict[str, str] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, hash=False, compare=False)
```

Replace the `_to_asset()` function (currently lines 106–123) with:

```python
def _to_asset(raw: dict, sku_key: str, searched_sku: str | None = None) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower()
    name = raw.get("name") or ""
    if ext and not name.lower().endswith(f".{ext}"):
        filename = f"{name}.{ext}"
    else:
        filename = name
    thumbs = raw.get("thumbnails") or {}
    thumb_url = thumbs.get("webimage") or thumbs.get("thul") or thumbs.get("mini") or ""
    raw_tags = raw.get("tags") or []
    tags = tuple(str(t) for t in raw_tags) if isinstance(raw_tags, list) else ()
    metaproperties = {
        k: _stringify_property(v)
        for k, v in raw.items()
        if k.startswith("property_")
    }
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=searched_sku,
        extension=ext,
        thumbnail_url=thumb_url,
        tags=tags,
        metaproperties=metaproperties,
        raw=raw,
    )


def _stringify_property(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if value is None:
        return ""
    return str(value)
```

- [ ] **Step 4: Run the new test and the existing suite**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_client.py -v`
Expected: all tests pass, including `test_to_asset_captures_tags_and_metaproperties`.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bynder_client.py tests/test_bynder_client.py
git commit -m "feat(bynder): expose tags and metaproperties on BynderAsset"
```

---

## Task 2: URL fallback chain (`resolve_csv_url`)

**Files:**
- Create: `src/core/bynder_urls.py`
- Create: `tests/test_bynder_urls.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bynder_urls.py`:

```python
from src.core.bynder_urls import resolve_csv_url


def test_prefers_configured_derivative_when_present():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {
            "webimage": "https://cdn/web.jpg",
            "amazon_full": "https://cdn/full.jpg",
        },
    }
    assert resolve_csv_url(raw, "amazon_full") == "https://cdn/full.jpg"


def test_falls_back_to_original_when_derivative_missing():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, "amazon_full") == "https://cdn/orig.jpg"


def test_falls_back_to_original_when_derivative_key_none():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, None) == "https://cdn/orig.jpg"


def test_falls_back_to_webimage_when_original_empty():
    raw = {
        "original": "",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, None) == "https://cdn/web.jpg"


def test_returns_empty_string_when_nothing_available():
    raw = {"thumbnails": {}}
    assert resolve_csv_url(raw, None) == ""


def test_handles_missing_thumbnails_dict():
    raw = {}
    assert resolve_csv_url(raw, "amazon_full") == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_urls.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.bynder_urls'`

- [ ] **Step 3: Implement `resolve_csv_url`**

Create `src/core/bynder_urls.py`:

```python
def resolve_csv_url(raw_asset: dict, derivative_key: str | None) -> str:
    """Return the best available public CDN URL for this Bynder asset.

    Precedence:
      1. Configured custom derivative (admin-defined, e.g. 'amazon_full')
      2. `original` field (if tenant has public-originals enabled)
      3. `webimage` (always present but ~800px - lower quality fallback)
    Empty string if none of these is populated.
    """
    thumbs = raw_asset.get("thumbnails") or {}
    if derivative_key and thumbs.get(derivative_key):
        return thumbs[derivative_key]
    original = raw_asset.get("original")
    if original:
        return original
    return thumbs.get("webimage", "")
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_urls.py -v`
Expected: all six tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bynder_urls.py tests/test_bynder_urls.py
git commit -m "feat(bulk-export): URL fallback chain for CSV export"
```

---

## Task 3: Config fields for derivative key and UPC keys

**Files:**
- Modify: `src/config.py`
- Modify: `.env.example`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for new config fields**

Append to `tests/test_config.py`:

```python
def test_config_parses_optional_derivative_and_upc_keys():
    env = {
        "DATABASE_URL": "postgresql://test",
        "BYNDER_DOMAIN": "popsockets.bynder.com",
        "BYNDER_PERMANENT_TOKEN": "tok",
        "STREAMLIT_USERNAME": "admin",
        "STREAMLIT_PASSWORD": "pw",
        "BYNDER_CSV_DERIVATIVE_KEY": "amazon_full",
        "BYNDER_CSV_UPC_KEYS": "property_UPC,property_GTIN",
    }
    with patch.dict(os.environ, env, clear=True), \
         patch("src.config.load_dotenv", lambda: None):
        from src.config import load_config
        cfg = load_config()
    assert cfg.bynder_csv_derivative_key == "amazon_full"
    assert cfg.bynder_csv_upc_keys == ["property_UPC", "property_GTIN"]


def test_config_defaults_derivative_key_none_and_upc_keys_standard():
    env = {
        "DATABASE_URL": "postgresql://test",
        "BYNDER_DOMAIN": "popsockets.bynder.com",
        "BYNDER_PERMANENT_TOKEN": "tok",
        "STREAMLIT_USERNAME": "admin",
        "STREAMLIT_PASSWORD": "pw",
    }
    with patch.dict(os.environ, env, clear=True), \
         patch("src.config.load_dotenv", lambda: None):
        from src.config import load_config
        cfg = load_config()
    assert cfg.bynder_csv_derivative_key is None
    assert cfg.bynder_csv_upc_keys == [
        "property_UPC", "property_GTIN", "property_Barcode"
    ]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'bynder_csv_derivative_key'`

- [ ] **Step 3: Extend `Config` and `load_config()` in `src/config.py`**

Replace the file contents with:

```python
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    database_url: str
    bynder_domain: str
    bynder_permanent_token: str
    streamlit_username: str
    streamlit_password: str
    bynder_client_id: str | None
    bynder_client_secret: str | None
    bynder_redirect_uri: str | None
    supabase_url: str | None
    supabase_service_key: str | None
    product_catalog_xlsx_path: str
    infographics_dir: str
    bynder_csv_derivative_key: str | None = None
    bynder_csv_upc_keys: list[str] = field(
        default_factory=lambda: ["property_UPC", "property_GTIN", "property_Barcode"]
    )


_REQUIRED = (
    "DATABASE_URL",
    "BYNDER_DOMAIN",
    "BYNDER_PERMANENT_TOKEN",
    "STREAMLIT_USERNAME",
    "STREAMLIT_PASSWORD",
)


def load_config() -> Config:
    load_dotenv()
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    upc_keys_raw = os.environ.get("BYNDER_CSV_UPC_KEYS", "")
    upc_keys = (
        [k.strip() for k in upc_keys_raw.split(",") if k.strip()]
        if upc_keys_raw
        else ["property_UPC", "property_GTIN", "property_Barcode"]
    )

    return Config(
        database_url=os.environ["DATABASE_URL"],
        bynder_domain=os.environ["BYNDER_DOMAIN"],
        bynder_permanent_token=os.environ["BYNDER_PERMANENT_TOKEN"],
        streamlit_username=os.environ["STREAMLIT_USERNAME"],
        streamlit_password=os.environ["STREAMLIT_PASSWORD"],
        bynder_client_id=os.environ.get("BYNDER_CLIENT_ID") or None,
        bynder_client_secret=os.environ.get("BYNDER_CLIENT_SECRET") or None,
        bynder_redirect_uri=os.environ.get("BYNDER_REDIRECT_URI") or None,
        supabase_url=os.environ.get("SUPABASE_URL") or None,
        supabase_service_key=os.environ.get("SUPABASE_SERVICE_KEY") or None,
        product_catalog_xlsx_path=os.environ.get(
            "PRODUCT_CATALOG_XLSX_PATH", "./data/barcelona.xlsx"
        ),
        infographics_dir=os.environ.get("INFOGRAPHICS_DIR", "./infographics"),
        bynder_csv_derivative_key=os.environ.get("BYNDER_CSV_DERIVATIVE_KEY") or None,
        bynder_csv_upc_keys=upc_keys,
    )
```

- [ ] **Step 4: Update `.env.example`**

Append to `.env.example`:

```
# Bulk Export CSV (optional)
# Derivative key configured in Bynder admin (see appendix of the design spec).
# Leave unset to fall back to 'original' then 'webimage'.
BYNDER_CSV_DERIVATIVE_KEY=
# Comma-separated metaproperty keys to try for UPC resolution.
# Default: property_UPC,property_GTIN,property_Barcode
BYNDER_CSV_UPC_KEYS=
```

- [ ] **Step 5: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_config.py -v`
Expected: all config tests pass.

- [ ] **Step 6: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/config.py tests/test_config.py .env.example
git commit -m "feat(config): add bynder_csv_derivative_key and bynder_csv_upc_keys"
```

---

## Task 4: SKU input parsing

**Files:**
- Create: `src/core/bulk_export.py` (initial — parse functions only)
- Create: `tests/test_bulk_export_parse.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bulk_export_parse.py`:

```python
import pytest
from src.core.bulk_export import parse_sku_input, parse_sku_csv, MAX_SKUS_PER_RUN


def test_parse_newline_delimited():
    assert parse_sku_input("806781\n806782\n806783") == ["806781", "806782", "806783"]


def test_parse_comma_delimited():
    assert parse_sku_input("806781, 806782 , 806783") == ["806781", "806782", "806783"]


def test_parse_mixed_whitespace_and_commas():
    assert parse_sku_input("806781\n  806782,806783\t806784") == [
        "806781", "806782", "806783", "806784"
    ]


def test_parse_strips_blank_lines():
    assert parse_sku_input("\n806781\n\n\n806782\n") == ["806781", "806782"]


def test_parse_dedupes_case_insensitively_preserves_first_casing():
    assert parse_sku_input("ABC-1\nabc-1\nABC-1") == ["ABC-1"]


def test_parse_empty_returns_empty_list():
    assert parse_sku_input("") == []
    assert parse_sku_input("   \n\n  ") == []


def test_parse_raises_over_cap():
    many = "\n".join(f"sku-{i}" for i in range(MAX_SKUS_PER_RUN + 1))
    with pytest.raises(ValueError, match="too many"):
        parse_sku_input(many)


def test_parse_csv_with_sku_header_takes_first_column():
    data = b"sku\n806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_uppercase_header():
    data = b"SKU\n806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_without_header_uses_first_row():
    data = b"806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_ignores_extra_columns():
    data = b"sku,name\n806781,Phone Grip\n806782,Case\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_skips_blank_rows():
    data = b"sku\n806781\n\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_handles_utf8_bom():
    data = b"\xef\xbb\xbfsku\n806781\n"
    assert parse_sku_csv(data) == ["806781"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.bulk_export'`

- [ ] **Step 3: Create `src/core/bulk_export.py` with parse functions**

Create `src/core/bulk_export.py`:

```python
"""Bulk SKU CSV export — framework-agnostic core.

Flow: parse SKUs -> for each SKU call BynderClient.search_by_sku ->
build one CSV row per asset -> serialize to CSV bytes.

Streamlit UI lives in src/ui/bulk_export_tab.py and only orchestrates.
"""
import csv
import io
import re


MAX_SKUS_PER_RUN = 2000

_HEADER_CANDIDATES = {"sku", "skus"}


def parse_sku_input(text: str) -> list[str]:
    """Split pasted SKU text on whitespace/commas, dedupe case-insensitively."""
    if not text:
        return []
    tokens = [t for t in re.split(r"[\s,]+", text) if t]
    return _dedupe_case_insensitive_over_cap(tokens)


def parse_sku_csv(data: bytes) -> list[str]:
    """Read the first column of a CSV upload. Skip header row if it says 'sku'."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return []
    first_cell = rows[0][0].strip().lower()
    if first_cell in _HEADER_CANDIDATES:
        rows = rows[1:]
    skus = [r[0].strip() for r in rows if r and r[0].strip()]
    return _dedupe_case_insensitive_over_cap(skus)


def _dedupe_case_insensitive_over_cap(skus: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for s in skus:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
    if len(result) > MAX_SKUS_PER_RUN:
        raise ValueError(
            f"too many SKUs: got {len(result)}, max is {MAX_SKUS_PER_RUN}. "
            "Split into smaller batches."
        )
    return result
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_parse.py -v`
Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bulk_export.py tests/test_bulk_export_parse.py
git commit -m "feat(bulk-export): parse SKU input from paste or CSV upload"
```

---

## Task 5: Row builder

**Files:**
- Modify: `src/core/bulk_export.py`
- Create: `tests/test_bulk_export_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bulk_export_builder.py`:

```python
from src.core.bynder_client import BynderAsset
from src.core.bulk_export import build_row, BulkExportRow


def _asset(**overrides) -> BynderAsset:
    defaults = dict(
        asset_id="asset-1",
        filename="806781_01_Front.jpg",
        original_url="",
        sku="806781",
        extension="jpg",
        thumbnail_url="https://cdn/web.jpg",
        tags=("806781", "swappable"),
        metaproperties={"property_SKUs": "806781"},
        raw={
            "id": "asset-1",
            "name": "806781_01_Front",
            "extension": ["jpg"],
            "thumbnails": {"webimage": "https://cdn/web.jpg"},
        },
    )
    defaults.update(overrides)
    return BynderAsset(**defaults)


def test_build_row_basic_shape():
    row = build_row("806781", _asset(), None, ["property_UPC"])
    assert isinstance(row, BulkExportRow)
    assert row.sku == "806781"
    assert row.image_name == "806781_01_Front.jpg"
    assert row.image_link == "https://cdn/web.jpg"
    assert row.tags == "806781; swappable"
    assert row.upc == ""
    assert row.asset_id == "asset-1"


def test_build_row_reads_upc_from_first_matching_key():
    asset = _asset(
        metaproperties={"property_SKUs": "806781", "property_GTIN": "842978104324"},
        raw={
            "id": "asset-1",
            "property_GTIN": "842978104324",
            "thumbnails": {"webimage": "https://cdn/web.jpg"},
        },
    )
    row = build_row("806781", asset, None, ["property_UPC", "property_GTIN"])
    assert row.upc == "842978104324"


def test_build_row_skips_empty_upc_keys():
    asset = _asset(
        metaproperties={"property_UPC": "", "property_GTIN": "842978104324"},
    )
    row = build_row("806781", asset, None, ["property_UPC", "property_GTIN"])
    assert row.upc == "842978104324"


def test_build_row_empty_tags_serialize_to_empty_string():
    row = build_row("806781", _asset(tags=()), None, [])
    assert row.tags == ""


def test_build_row_uses_configured_derivative_url():
    asset = _asset(
        raw={
            "id": "asset-1",
            "original": "",
            "thumbnails": {
                "webimage": "https://cdn/web.jpg",
                "amazon_full": "https://cdn/full.jpg",
            },
        },
    )
    row = build_row("806781", asset, "amazon_full", [])
    assert row.image_link == "https://cdn/full.jpg"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_builder.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_row' from 'src.core.bulk_export'`

- [ ] **Step 3: Add `BulkExportRow` and `build_row` to `src/core/bulk_export.py`**

At the top of `src/core/bulk_export.py`, add:

```python
from dataclasses import dataclass

from src.core.bynder_client import BynderAsset
from src.core.bynder_urls import resolve_csv_url
```

Then append to the file:

```python
@dataclass
class BulkExportRow:
    sku: str
    image_name: str
    image_link: str
    tags: str
    upc: str
    asset_id: str


def build_row(
    sku: str,
    asset: BynderAsset,
    derivative_key: str | None,
    upc_keys: list[str],
) -> BulkExportRow:
    image_link = resolve_csv_url(asset.raw, derivative_key)
    upc = _first_non_empty(asset.metaproperties, upc_keys)
    return BulkExportRow(
        sku=sku,
        image_name=asset.filename,
        image_link=image_link,
        tags="; ".join(asset.tags),
        upc=upc,
        asset_id=asset.asset_id,
    )


def _first_non_empty(props: dict[str, str], keys: list[str]) -> str:
    for k in keys:
        v = props.get(k, "")
        if v:
            return v
    return ""
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_builder.py -v`
Expected: all five tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bulk_export.py tests/test_bulk_export_builder.py
git commit -m "feat(bulk-export): row builder with UPC + URL resolution"
```

---

## Task 6: `run_export` orchestrator (happy path + per-SKU errors)

**Files:**
- Modify: `src/core/bulk_export.py`
- Create: `tests/test_bulk_export_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bulk_export_runner.py`:

```python
from src.core.bynder_client import BynderAsset
from src.core.bulk_export import run_export, BulkExportResult


class FakeClient:
    """Lightweight stand-in for BynderClient in tests."""
    def __init__(self, result_map=None, errors=None):
        self._results = result_map or {}
        self._errors = errors or {}
        self.calls: list[str] = []

    def search_by_sku(self, sku: str):
        self.calls.append(sku)
        if sku in self._errors:
            raise self._errors[sku]
        return self._results.get(sku, [])


def _asset(asset_id: str, sku: str) -> BynderAsset:
    return BynderAsset(
        asset_id=asset_id,
        filename=f"{sku}_{asset_id}.jpg",
        original_url="",
        sku=sku,
        extension="jpg",
        thumbnail_url="https://cdn/web.jpg",
        tags=(sku,),
        metaproperties={},
        raw={"id": asset_id, "thumbnails": {"webimage": "https://cdn/web.jpg"}},
    )


def test_run_export_collects_rows_per_sku():
    client = FakeClient(
        result_map={
            "A": [_asset("a1", "A"), _asset("a2", "A")],
            "B": [_asset("b1", "B")],
        }
    )
    result = run_export(
        skus=["A", "B"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert isinstance(result, BulkExportResult)
    assert len(result.rows) == 3
    assert [r.sku for r in result.rows] == ["A", "A", "B"]
    assert result.missing_skus == []
    assert result.failed_skus == []


def test_run_export_records_missing_skus_without_emitting_rows_by_default():
    client = FakeClient(result_map={"A": [_asset("a1", "A")]})
    result = run_export(
        skus=["A", "ZZZ"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert len(result.rows) == 1
    assert result.missing_skus == ["ZZZ"]


def test_run_export_emits_blank_rows_when_include_missing_true():
    client = FakeClient(result_map={})
    result = run_export(
        skus=["X"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        include_missing=True,
    )
    assert len(result.rows) == 1
    r = result.rows[0]
    assert r.sku == "X"
    assert r.image_name == ""
    assert r.image_link == ""
    assert r.tags == ""
    assert r.upc == ""
    assert r.asset_id == ""


def test_run_export_records_failures_and_continues():
    client = FakeClient(
        result_map={"A": [_asset("a1", "A")]},
        errors={"B": RuntimeError("rate limited")},
    )
    result = run_export(
        skus=["A", "B", "C"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert [r.sku for r in result.rows] == ["A"]
    assert result.missing_skus == ["C"]
    assert len(result.failed_skus) == 1
    assert result.failed_skus[0][0] == "B"
    assert "rate limited" in result.failed_skus[0][1]


def test_run_export_reports_progress():
    client = FakeClient(result_map={s: [] for s in ["A", "B", "C"]})
    seen: list[tuple[int, int]] = []
    run_export(
        skus=["A", "B", "C"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(1, 3), (2, 3), (3, 3)]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_runner.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_export'`

- [ ] **Step 3: Add `BulkExportResult`, `run_export`, and retry logic to `src/core/bulk_export.py`**

Append to `src/core/bulk_export.py`:

```python
from typing import Callable, Protocol


class _SearchClient(Protocol):
    def search_by_sku(self, sku: str) -> list[BynderAsset]: ...


@dataclass
class BulkExportResult:
    rows: list[BulkExportRow]
    missing_skus: list[str]
    failed_skus: list[tuple[str, str]]


def run_export(
    skus: list[str],
    client: _SearchClient,
    derivative_key: str | None,
    upc_keys: list[str],
    include_missing: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> BulkExportResult:
    rows: list[BulkExportRow] = []
    missing: list[str] = []
    failed: list[tuple[str, str]] = []
    total = len(skus)

    for i, sku in enumerate(skus, start=1):
        try:
            assets = client.search_by_sku(sku)
        except Exception as e:
            failed.append((sku, str(e)))
            if on_progress is not None:
                on_progress(i, total)
            continue

        if not assets:
            missing.append(sku)
            if include_missing:
                rows.append(BulkExportRow(
                    sku=sku, image_name="", image_link="",
                    tags="", upc="", asset_id="",
                ))
        else:
            for a in assets:
                rows.append(build_row(sku, a, derivative_key, upc_keys))

        if on_progress is not None:
            on_progress(i, total)

    return BulkExportResult(rows=rows, missing_skus=missing, failed_skus=failed)
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_runner.py -v`
Expected: all five tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bulk_export.py tests/test_bulk_export_runner.py
git commit -m "feat(bulk-export): run_export orchestrator with per-SKU error tolerance"
```

---

## Task 7: CSV serialization (`to_csv_bytes`)

**Files:**
- Modify: `src/core/bulk_export.py`
- Create: `tests/test_bulk_export_csv.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bulk_export_csv.py`:

```python
from src.core.bulk_export import (
    BulkExportResult, BulkExportRow, to_csv_bytes,
)


def _result(rows):
    return BulkExportResult(rows=rows, missing_skus=[], failed_skus=[])


def test_csv_has_utf8_bom():
    data = to_csv_bytes(_result([]))
    assert data.startswith(b"\xef\xbb\xbf"), "CSV must be UTF-8 with BOM for Excel"


def test_csv_header_row_matches_spec():
    data = to_csv_bytes(_result([]))
    first_line = data.decode("utf-8-sig").splitlines()[0]
    assert first_line == "sku,image_name,image_link,tags,upc,asset_id"


def test_csv_rows_are_serialized_in_order():
    rows = [
        BulkExportRow("A", "a.jpg", "https://cdn/a.jpg", "x; y", "111", "id-a"),
        BulkExportRow("B", "b.jpg", "https://cdn/b.jpg", "z", "222", "id-b"),
    ]
    decoded = to_csv_bytes(_result(rows)).decode("utf-8-sig")
    lines = decoded.splitlines()
    assert lines[1] == "A,a.jpg,https://cdn/a.jpg,x; y,111,id-a"
    assert lines[2] == "B,b.jpg,https://cdn/b.jpg,z,222,id-b"


def test_csv_quotes_values_with_commas():
    rows = [BulkExportRow("A", "a,b.jpg", "url", "t1, t2", "", "id-a")]
    decoded = to_csv_bytes(_result(rows)).decode("utf-8-sig")
    assert '"a,b.jpg"' in decoded
    assert '"t1, t2"' in decoded


def test_csv_empty_result_still_has_header():
    decoded = to_csv_bytes(_result([])).decode("utf-8-sig")
    lines = decoded.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("sku,")
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_csv.py -v`
Expected: FAIL with `ImportError: cannot import name 'to_csv_bytes'`

- [ ] **Step 3: Add `to_csv_bytes` to `src/core/bulk_export.py`**

Append to `src/core/bulk_export.py`:

```python
CSV_COLUMNS = ["sku", "image_name", "image_link", "tags", "upc", "asset_id"]


def to_csv_bytes(result: BulkExportResult) -> bytes:
    """Serialize to UTF-8 with BOM, RFC4180 quoting."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    for r in result.rows:
        writer.writerow([
            r.sku, r.image_name, r.image_link, r.tags, r.upc, r.asset_id,
        ])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_csv.py -v`
Expected: all five tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bulk_export.py tests/test_bulk_export_csv.py
git commit -m "feat(bulk-export): to_csv_bytes serializer with BOM"
```

---

## Task 8: Timestamped filename helper

**Files:**
- Modify: `src/core/bulk_export.py`
- Create: `tests/test_bulk_export_filename.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_bulk_export_filename.py`:

```python
import datetime as dt
from src.core.bulk_export import export_filename


def test_export_filename_format():
    when = dt.datetime(2026, 4, 21, 14, 30, 22)
    assert export_filename(when) == "bynder_export_2026-04-21_143022.csv"


def test_export_filename_defaults_to_now(monkeypatch):
    # sanity check — uses datetime.now() and matches the format
    name = export_filename()
    assert name.startswith("bynder_export_")
    assert name.endswith(".csv")
    assert len(name) == len("bynder_export_2026-04-21_143022.csv")
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_filename.py -v`
Expected: FAIL with `ImportError: cannot import name 'export_filename'`

- [ ] **Step 3: Add `export_filename` to `src/core/bulk_export.py`**

Add at the top of `src/core/bulk_export.py` (with the other imports):

```python
import datetime as _dt
```

And append to the file:

```python
def export_filename(now: _dt.datetime | None = None) -> str:
    when = now or _dt.datetime.now()
    return when.strftime("bynder_export_%Y-%m-%d_%H%M%S.csv")
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bulk_export_filename.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bulk_export.py tests/test_bulk_export_filename.py
git commit -m "feat(bulk-export): timestamped export filename helper"
```

---

## Task 9: Sliding-window rate throttle in `BynderClient`

Per spec §9: Bynder limit is 4,500 req / 5 min; stay 10% under at 4,000 / 5 min. `search_by_sku` fires 2 requests per SKU, so 2,000-SKU cap is safe with throttling.

**Files:**
- Modify: `src/core/bynder_client.py`
- Modify: `tests/test_bynder_client.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_bynder_client.py`:

```python
import time as _time


def test_throttle_blocks_when_window_full(mocker):
    # Patch the clock so "now" advances deterministically.
    clock = {"t": 1000.0}
    def fake_monotonic():
        return clock["t"]
    sleeps: list[float] = []
    def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += s

    mocker.patch("src.core.bynder_client.time.monotonic", side_effect=fake_monotonic)
    mocker.patch("src.core.bynder_client.time.sleep", side_effect=fake_sleep)

    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = []
    client = BynderClient(sdk=fake_sdk, throttle_limit=3, throttle_window_sec=5.0)

    # Fill the window with 3 requests at t=1000
    client.search_by_sku("A")   # 2 requests (tags + property_SKUs)
    # third API call (total=3) is still at t=1000; the *next* one would exceed limit
    assert sleeps == [], f"no sleep should fire until window overflows; got {sleeps}"

    # Now trigger a 4th request. With throttle_limit=3 we must sleep until
    # the oldest slot (at t=1000) ages out of the 5s window → sleep ~5s.
    client.search_by_sku("B")
    assert len(sleeps) >= 1
    assert sleeps[0] > 0.0
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_client.py::test_throttle_blocks_when_window_full -v`
Expected: FAIL — constructor doesn't accept `throttle_limit`.

- [ ] **Step 3: Add throttling to `src/core/bynder_client.py`**

Near the top of `src/core/bynder_client.py`, add:

```python
import time
from collections import deque
```

Extend the class. Replace the current `__init__` and add two helpers:

```python
class BynderClient:
    """... (keep existing docstring) ..."""

    SKU_PROPERTY_KEY = "property_SKUs"
    AMAZON_SAFE_EXTENSIONS = frozenset({"jpg", "jpeg", "png"})

    # Defaults: Bynder allows 4500/5min tenant-wide; stay 10% under.
    DEFAULT_THROTTLE_LIMIT = 4000
    DEFAULT_THROTTLE_WINDOW_SEC = 300.0

    def __init__(
        self,
        sdk,
        throttle_limit: int = DEFAULT_THROTTLE_LIMIT,
        throttle_window_sec: float = DEFAULT_THROTTLE_WINDOW_SEC,
    ):
        self._sdk = sdk
        self._throttle_limit = throttle_limit
        self._throttle_window_sec = throttle_window_sec
        self._call_times: deque[float] = deque()
```

Add a private method on the class:

```python
    def _throttle(self) -> None:
        now = time.monotonic()
        window_start = now - self._throttle_window_sec
        while self._call_times and self._call_times[0] < window_start:
            self._call_times.popleft()
        if len(self._call_times) >= self._throttle_limit:
            sleep_for = self._throttle_window_sec - (now - self._call_times[0]) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            window_start = now - self._throttle_window_sec
            while self._call_times and self._call_times[0] < window_start:
                self._call_times.popleft()
        self._call_times.append(now)
```

Inside `search_by_sku`, call `self._throttle()` immediately before each `media_list` call. The existing loop becomes:

```python
        for query in (
            {"tags": sku, "type": "image"},
            {self.SKU_PROPERTY_KEY: sku, "type": "image"},
        ):
            logger.debug("Bynder media_list query: %s", query)
            self._throttle()
            raw = self._sdk.asset_bank_client.media_list(query)
            logger.debug("  -> %d records", len(raw))
            for r in raw:
                if _matches_sku(r, sku, self.SKU_PROPERTY_KEY):
                    merged[r.get("id", "")] = r
```

- [ ] **Step 4: Run new and existing Bynder tests**

Run: `cd "C:/projects/bynder-image-tool" && pytest tests/test_bynder_client.py -v`
Expected: all Bynder tests pass (the existing ones don't supply throttle args, so defaults apply and the throttle never kicks in — they still pass).

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/core/bynder_client.py tests/test_bynder_client.py
git commit -m "feat(bynder): sliding-window throttle stays under 4500 req/5min"
```

---

## Task 10: Streamlit "Bulk Export" tab

**Files:**
- Create: `src/ui/bulk_export_tab.py`
- Modify: `src/ui/app.py`

This task has no automated test — Streamlit UI is manually tested per the parent spec's testing strategy. Structure the tab so all business logic is a call into `src/core/bulk_export.py` (already fully unit-tested above).

- [ ] **Step 1: Create `src/ui/bulk_export_tab.py`**

```python
import datetime as _dt

import streamlit as st

from src.config import load_config
from src.core.bulk_export import (
    export_filename,
    parse_sku_csv,
    parse_sku_input,
    run_export,
    to_csv_bytes,
)
from src.ui.deps import make_bynder_client


def render() -> None:
    st.header("Bulk Export")
    st.caption(
        "Paste a list of SKUs (one per line or comma-separated) — or upload a CSV "
        "whose first column is SKUs — and download a CSV with image names, links, "
        "tags, and UPC pulled from Bynder."
    )

    cfg = load_config()

    pasted = st.text_area(
        "Paste SKUs",
        key="bulk_paste",
        height=200,
        placeholder="806781\n806782\n806783",
    )
    st.markdown("**— OR —**")
    uploaded = st.file_uploader(
        "Upload CSV (first column used; header 'sku' optional)",
        type=["csv", "txt"],
        key="bulk_csv",
    )
    include_missing = st.checkbox(
        "Include missing-SKU rows (emit a blank-image row per SKU with no Bynder hits)",
        key="bulk_include_missing",
    )

    if not st.button("Generate CSV", key="bulk_generate", type="primary"):
        return

    try:
        skus = _collect_skus(pasted, uploaded)
    except ValueError as e:
        st.error(str(e))
        return

    if not skus:
        st.error("Paste at least one SKU or upload a CSV.")
        return

    try:
        client = make_bynder_client(cfg)
    except Exception as e:
        st.error(f"Bynder auth failed: {e}")
        return

    progress = st.progress(0, text=f"0 / {len(skus)} SKUs")

    def _on_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"{done} / {total} SKUs")

    result = run_export(
        skus=skus,
        client=client,
        derivative_key=cfg.bynder_csv_derivative_key,
        upc_keys=cfg.bynder_csv_upc_keys,
        include_missing=include_missing,
        on_progress=_on_progress,
    )

    _render_summary(result, len(skus))

    if not result.rows and not (include_missing and result.missing_skus):
        st.error("No rows to export. Check the SKU list or Bynder connection.")
        return

    st.download_button(
        label="Download CSV",
        data=to_csv_bytes(result),
        file_name=export_filename(_dt.datetime.now()),
        mime="text/csv",
        key="bulk_download",
    )


def _collect_skus(pasted: str, uploaded) -> list[str]:
    if pasted and pasted.strip():
        return parse_sku_input(pasted)
    if uploaded is not None:
        return parse_sku_csv(uploaded.getvalue())
    return []


def _render_summary(result, total: int) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("SKUs processed", total)
    col2.metric("Rows", len(result.rows))
    col3.metric("Missing", len(result.missing_skus))

    if result.missing_skus:
        with st.expander(f"{len(result.missing_skus)} SKUs with no Bynder matches"):
            st.write(", ".join(result.missing_skus))

    if result.failed_skus:
        with st.expander(f"{len(result.failed_skus)} SKUs errored during fetch"):
            for sku, err in result.failed_skus:
                st.write(f"- `{sku}`: {err}")
```

- [ ] **Step 2: Wire the tab into `src/ui/app.py`**

Change the `st.sidebar.radio` call in `src/ui/app.py` (currently around line 28-32) and the dispatching `if/elif/else` (currently around lines 34-42):

```python
    tab = st.sidebar.radio(
        "Navigate",
        ["Mapping Wizard", "Package SKU", "Library", "Bulk Export"],
        key="nav",
    )

    if tab == "Mapping Wizard":
        from src.ui.wizard_tab import render as render_wizard
        render_wizard()
    elif tab == "Package SKU":
        from src.ui.package_tab import render as render_package
        render_package()
    elif tab == "Library":
        from src.ui.library_tab import render as render_library
        render_library()
    else:
        from src.ui.bulk_export_tab import render as render_bulk
        render_bulk()
```

- [ ] **Step 3: Run the full test suite to confirm nothing regressed**

Run: `cd "C:/projects/bynder-image-tool" && pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Manual smoke test (local)**

With Docker and `.env` configured:

```bash
cd "C:/projects/bynder-image-tool"
docker compose up -d postgres
streamlit run src/ui/app.py
```

In browser at http://localhost:8501:
1. Log in
2. Click "Bulk Export" in sidebar
3. Paste 2-3 known SKUs (use SKUs you've tested with Package SKU previously)
4. Click "Generate CSV"
5. Watch progress bar advance
6. Click "Download CSV"
7. Open the downloaded file in Excel — confirm:
   - Header is `sku, image_name, image_link, tags, upc, asset_id`
   - Rows match what "Package SKU" shows for the same SKUs
   - `image_link` URLs open in browser and show the expected image (will be webimage quality until a derivative is configured in Bynder)

Also test:
- Paste a deliberately-missing SKU (e.g. `ZZZZ999`) — confirm it appears in the "missing" summary
- Upload a small CSV file with a `sku` header — confirm it produces the same output as paste
- Check the "Include missing-SKU rows" box, regenerate — confirm the CSV now contains a blank-image row for ZZZZ999

- [ ] **Step 5: Commit**

```bash
cd "C:/projects/bynder-image-tool"
git add src/ui/bulk_export_tab.py src/ui/app.py
git commit -m "feat(ui): add Bulk Export tab backed by core bulk_export module"
```

---

## Task 11: Full-suite regression + coverage

- [ ] **Step 1: Run full test suite with coverage**

```bash
cd "C:/projects/bynder-image-tool"
pytest -v --cov=src --cov-report=term-missing
```

Expected: all tests pass; `src/core/bulk_export.py` and `src/core/bynder_urls.py` both at ≥90% coverage.

- [ ] **Step 2: Push the branch**

```bash
cd "C:/projects/bynder-image-tool"
git push -u origin feat/phase-1-implementation
```

(Confirm with user before pushing — push is a shared-state action.)

---

## Self-Review

**Spec coverage check:**
- §4 CSV schema → Tasks 5, 7 ✓
- §5.1 SKU parsing including cap → Task 4 ✓
- §6 data flow → Task 6 ✓
- §7 URL fallback → Task 2 ✓
- §8 UPC resolution → Task 5 (`_first_non_empty` + Task 3 config) ✓
- §9 rate limiting → Task 9 ✓
- §10 error handling (auth, retry, per-SKU failure, empty input, over-cap, partial) → Task 6 (per-SKU) + Task 4 (over-cap) + Task 10 UI (auth, empty) ✓ *(Note: retry-once-with-backoff in spec §10 is NOT in Task 6 — see below)*
- §11 code extensions → Tasks 1, 3, 10 ✓
- §12 new modules → Tasks 2, 4–8, 10 ✓
- §13 testing → Tasks 2–9 unit tests; Task 10 manual ✓
- §14 file list → all covered ✓

**Deviation flagged:** Spec §10 says "retry once with 2s backoff on per-SKU exceptions." Task 6 currently catches and records the error without retrying. This was deliberately simplified because the new throttle in Task 9 should prevent most rate-limit errors in the first place, and retry-with-sleep makes unit tests brittle against real time. If retry behavior is required before shipping, add a Task 6.5 that wraps `client.search_by_sku(sku)` in a single retry with `time.sleep(2)` on exception, tested with a patched `time.sleep`.

**Placeholder scan:** no TBD/TODO; all code steps show full code; expected test outputs specified.

**Type consistency:** `BulkExportRow` fields match spec §4 columns; `run_export` signature matches spec §12.1; `resolve_csv_url` and `build_row` argument types are consistent across Tasks 2, 5, 6, 10.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-bulk-sku-csv-export.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
