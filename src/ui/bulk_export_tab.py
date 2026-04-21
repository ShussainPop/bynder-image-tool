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

    if result.failed_skus and not result.rows and not (include_missing and result.missing_skus):
        preview = "\n".join(f"- `{sku}`: {err}" for sku, err in result.failed_skus[:3])
        st.error(f"Bynder returned errors for every SKU:\n\n{preview}")
        return

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
    num_cols = 4 if result.failed_skus else 3
    cols = st.columns(num_cols)
    cols[0].metric("SKUs processed", total)
    cols[1].metric("Rows", len(result.rows))
    cols[2].metric("Missing", len(result.missing_skus))
    if result.failed_skus:
        cols[3].metric("Errors", len(result.failed_skus))

    if result.missing_skus:
        with st.expander(f"{len(result.missing_skus)} SKUs with no Bynder matches"):
            st.write(", ".join(result.missing_skus))

    if result.failed_skus:
        with st.expander(f"{len(result.failed_skus)} SKUs errored during fetch"):
            for sku, err in result.failed_skus:
                st.write(f"- `{sku}`: {err}")
