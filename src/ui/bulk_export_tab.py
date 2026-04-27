import datetime as _dt
from datetime import timedelta

import streamlit as st

from src.config import load_config
from src.core.bulk_export import (
    BulkExportResult,
    export_filename,
    parse_sku_csv,
    parse_sku_input,
    run_export,
    to_csv_bytes,
)
from src.core.bynder_asset_cache import BynderAssetCache
from src.core.bynder_urls import resolve_csv_url
from src.core.sku_bundle import build_sku_zip
from src.ui.deps import make_bynder_client, session_scope


INLINE_PAGE_SIZE = 25
GRID_COLUMNS = 4


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
    force_refresh = st.checkbox(
        "Force refresh from Bynder (ignore cache)",
        key="bulk_force_refresh",
        help=(
            f"Bynder responses are cached for {cfg.bynder_cache_ttl_days} days "
            "to skip re-querying SKUs we already have. Tick this to bypass."
        ),
    )

    if st.button("Generate CSV", key="bulk_generate", type="primary"):
        _run_and_store(cfg, pasted, uploaded, include_missing, force_refresh)

    state = st.session_state.get("bulk_export_state")
    if state is None:
        return

    result: BulkExportResult = state["result"]
    total: int = state["total"]
    derivative_key: str | None = state["derivative_key"]
    generated_at: _dt.datetime = state["generated_at"]
    include_missing_used: bool = state["include_missing"]

    _render_summary(result, total)

    if result.failed_skus and not result.rows and not (
        include_missing_used and result.missing_skus
    ):
        preview = "\n".join(f"- `{sku}`: {err}" for sku, err in result.failed_skus[:3])
        st.error(f"Bynder returned errors for every SKU:\n\n{preview}")
        return

    if not result.rows and not (include_missing_used and result.missing_skus):
        st.error("No rows to export. Check the SKU list or Bynder connection.")
        return

    st.download_button(
        label="Download CSV",
        data=to_csv_bytes(result),
        file_name=export_filename(generated_at),
        mime="text/csv",
        key="bulk_download",
    )

    _render_grouped_view(result, derivative_key)


def _run_and_store(cfg, pasted: str, uploaded, include_missing: bool, force_refresh: bool) -> None:
    """Validate inputs, run the export, and stash the result in session_state."""
    try:
        skus = _collect_skus(pasted, uploaded)
    except ValueError as e:
        st.session_state.pop("bulk_export_state", None)
        st.error(str(e))
        return

    if not skus:
        st.session_state.pop("bulk_export_state", None)
        st.error("Paste at least one SKU or upload a CSV.")
        return

    try:
        client = make_bynder_client(cfg)
    except Exception as e:
        st.session_state.pop("bulk_export_state", None)
        st.error(f"Bynder auth failed: {e}")
        return

    progress = st.progress(0, text=f"0 / {len(skus)} SKUs")

    def _on_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"{done} / {total} SKUs")

    with session_scope() as session:
        cache = BynderAssetCache(
            session=session,
            ttl=timedelta(days=cfg.bynder_cache_ttl_days),
        )
        result = run_export(
            skus=skus,
            client=client,
            derivative_key=cfg.bynder_csv_derivative_key,
            upc_keys=cfg.bynder_csv_upc_keys,
            include_missing=include_missing,
            on_progress=_on_progress,
            cache=cache,
            force_refresh=force_refresh,
        )

    st.session_state["bulk_export_state"] = {
        "result": result,
        "total": len(skus),
        "derivative_key": cfg.bynder_csv_derivative_key,
        "generated_at": _dt.datetime.now(),
        "include_missing": include_missing,
    }
    st.session_state["bulk_export_page"] = 0


def _collect_skus(pasted: str, uploaded) -> list[str]:
    if pasted and pasted.strip():
        return parse_sku_input(pasted)
    if uploaded is not None:
        return parse_sku_csv(uploaded.getvalue())
    return []


def _render_summary(result, total: int) -> None:
    fresh = total - result.cache_hits - len(result.failed_skus)
    num_cols = 5 if result.failed_skus else 4
    cols = st.columns(num_cols)
    cols[0].metric("SKUs processed", total)
    cols[1].metric("Rows", len(result.rows))
    cols[2].metric("Cached", result.cache_hits, help="Returned from local cache; no Bynder call.")
    cols[3].metric("Missing", len(result.missing_skus))
    if result.failed_skus:
        cols[4].metric("Errors", len(result.failed_skus))

    if result.missing_skus:
        with st.expander(f"{len(result.missing_skus)} SKUs with no Bynder matches"):
            st.write(", ".join(result.missing_skus))

    if result.failed_skus:
        with st.expander(f"{len(result.failed_skus)} SKUs errored during fetch"):
            for sku, err in result.failed_skus:
                st.write(f"- `{sku}`: {err}")


def _render_grouped_view(result: BulkExportResult, derivative_key: str | None) -> None:
    skus = list(result.assets_by_sku.keys())
    if not skus:
        return

    st.divider()
    st.subheader(f"Browse by SKU — {len(skus)} matched")

    page = st.session_state.get("bulk_export_page", 0)
    total_pages = (len(skus) + INLINE_PAGE_SIZE - 1) // INLINE_PAGE_SIZE
    if page >= total_pages:
        page = 0
        st.session_state["bulk_export_page"] = 0

    if total_pages > 1:
        nav_prev, nav_label, nav_next = st.columns([1, 2, 1])
        with nav_prev:
            if st.button("← Prev", key="bulk_prev", disabled=page == 0):
                st.session_state["bulk_export_page"] = max(0, page - 1)
                st.rerun()
        with nav_label:
            start = page * INLINE_PAGE_SIZE + 1
            end = min(len(skus), (page + 1) * INLINE_PAGE_SIZE)
            st.markdown(
                f"<div style='text-align:center;padding-top:6px;'>"
                f"Page {page + 1} of {total_pages} · SKUs {start}–{end}</div>",
                unsafe_allow_html=True,
            )
        with nav_next:
            if st.button("Next →", key="bulk_next", disabled=page >= total_pages - 1):
                st.session_state["bulk_export_page"] = min(total_pages - 1, page + 1)
                st.rerun()

    page_skus = skus[page * INLINE_PAGE_SIZE : (page + 1) * INLINE_PAGE_SIZE]
    for sku in page_skus:
        _render_sku_block(sku, result.assets_by_sku[sku], derivative_key)


def _render_sku_block(sku: str, assets, derivative_key: str | None) -> None:
    with st.expander(f"{sku} — {len(assets)} image{'s' if len(assets) != 1 else ''}", expanded=True):
        cols = st.columns(GRID_COLUMNS)
        for i, asset in enumerate(assets):
            col = cols[i % GRID_COLUMNS]
            with col:
                thumb = asset.thumbnail_url or resolve_csv_url(asset.raw, derivative_key)
                if thumb:
                    st.image(thumb, width=180)
                st.caption(asset.filename)
                full_url = resolve_csv_url(asset.raw, derivative_key)
                if full_url:
                    st.link_button("Download ↗", url=full_url, use_container_width=True)

        bundle_key = f"bulk_zip_{sku}"
        if st.button(
            f"📦 Build .zip for all {len(assets)} images",
            key=f"bulk_zip_build_{sku}",
        ):
            with st.spinner(f"Fetching {len(assets)} images for {sku}…"):
                try:
                    st.session_state[bundle_key] = build_sku_zip(sku, assets, derivative_key)
                except Exception as e:
                    st.error(f"Failed to build zip: {e}")
                    st.session_state.pop(bundle_key, None)

        zip_bytes = st.session_state.get(bundle_key)
        if zip_bytes:
            st.download_button(
                label=f"⬇ Download {sku}.zip",
                data=zip_bytes,
                file_name=f"{sku}.zip",
                mime="application/zip",
                key=f"bulk_zip_dl_{sku}",
            )
