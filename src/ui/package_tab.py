from pathlib import Path
import tempfile

import streamlit as st

from src.config import load_config
from src.core.amazon_packager import SlotFile, build_zip, validate_image
from src.core.bynder_client import BynderClient
from src.core.infographic_library import InfographicLibrary
from src.core.mapping_engine import AMAZON_SLOTS
from src.core.product_catalog import ProductCatalog
from src.db.models import ProductLine, PackageHistory, SkuOverride
from src.ui.deps import build_supabase_client, session_scope
from src.ui.package_helpers import build_package_context, SlotView


def _make_bynder_client(cfg) -> BynderClient:
    """Pick the auth mode based on which env vars are set.

    Priority: client_credentials (preferred, auto-refresh) → permanent_token.
    """
    if cfg.bynder_client_id and cfg.bynder_client_secret:
        return BynderClient.from_client_credentials(
            domain=cfg.bynder_domain,
            client_id=cfg.bynder_client_id,
            client_secret=cfg.bynder_client_secret,
        )
    return BynderClient.from_permanent_token(
        domain=cfg.bynder_domain,
        token=cfg.bynder_permanent_token,
    )


def render() -> None:
    st.header("Package SKU")

    cfg = load_config()
    with session_scope() as session:
        catalog = ProductCatalog(
            xlsx_path=cfg.product_catalog_xlsx_path,
            supabase_client=build_supabase_client(cfg),
        )
        infographic_lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

        sku = st.text_input("SKU", key="pkg_sku").strip()
        if not sku:
            st.info("Enter a SKU to begin.")
            return

        try:
            info = catalog.lookup(sku)
        except FileNotFoundError:
            info = None

        if info is None:
            st.warning(f"SKU '{sku}' not found in catalog. Pick product line + tier manually.")
            lines_in_db = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
            if not lines_in_db:
                st.error("No product lines configured. Visit the Mapping Wizard first.")
                return
            product_line_name = st.selectbox("Product line", lines_in_db, key="pkg_line_manual")
            try:
                tier_options = catalog.list_tiers() or ["A", "B", "C"]
            except FileNotFoundError:
                tier_options = ["A", "B", "C"]
            tier = st.selectbox("Tier", tier_options, key="pkg_tier_manual")
        else:
            st.success(f"Found: {info.description}")
            col1, col2 = st.columns(2)
            col1.metric("Product line", info.product_line or "—")
            col2.metric("Tier", info.tier or "—")
            product_line_name = info.product_line
            tier = info.tier

        if not product_line_name or not tier:
            st.error("Product line and tier must be set.")
            return

        pl = session.query(ProductLine).filter_by(name=product_line_name).first()
        if pl is None:
            st.error(f"No wizard config for '{product_line_name}'. Configure it in the Mapping Wizard first.")
            return

        if st.button("Fetch Bynder assets", key="pkg_fetch"):
            try:
                bynder = _make_bynder_client(cfg)
            except Exception as e:
                st.error(f"Bynder auth failed: {e}")
                return

            try:
                with st.spinner("Querying Bynder..."):
                    ctx = build_package_context(
                        session=session,
                        sku=sku,
                        product_line=pl,
                        tier=tier,
                        bynder_client=bynder,
                        infographic_lib=infographic_lib,
                    )
            except Exception as e:
                st.error(f"Bynder fetch failed: {e}")
                return
            st.session_state["pkg_ctx"] = ctx
            st.session_state["pkg_bynder_client"] = bynder

        ctx = st.session_state.get("pkg_ctx")
        if ctx is None:
            return

        _render_preview_and_overrides(session, ctx, infographic_lib, cfg)
        _render_package_button(session, ctx, st.session_state.get("pkg_bynder_client"))


def _render_preview_and_overrides(session, ctx, infographic_lib: InfographicLibrary, cfg) -> None:
    st.subheader("Preview")
    cols_per_row = 3
    slots = list(AMAZON_SLOTS)
    overrides_root = Path(cfg.infographics_dir).parent / "overrides"

    for i in range(0, len(slots), cols_per_row):
        row = st.columns(cols_per_row)
        for j, slot in enumerate(slots[i : i + cols_per_row]):
            view = ctx.slot_views[slot]
            with row[j]:
                st.markdown(f"**{slot}** — `{view.source}`")
                st.caption(view.filename or "_empty_")

                with st.expander("Override"):
                    uploaded = st.file_uploader(
                        f"Upload custom for {slot}",
                        type=["jpg", "jpeg", "png"],
                        key=f"ovr_{slot}",
                    )
                    if uploaded is not None and st.button(f"Save override {slot}", key=f"save_ovr_{slot}"):
                        dest = overrides_root / ctx.sku / f"{slot}{Path(uploaded.name).suffix}"
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(uploaded.getvalue())
                        session.query(SkuOverride).filter_by(sku=ctx.sku, amazon_slot=slot).delete()
                        session.add(SkuOverride(
                            sku=ctx.sku,
                            amazon_slot=slot,
                            source="upload",
                            uploaded_file_path=str(dest),
                        ))
                        session.commit()
                        ctx.slot_views[slot] = SlotView(
                            slot=slot,
                            source="override",
                            filename=dest.name,
                            asset_id=None,
                            local_path=str(dest),
                        )
                        st.success(f"Override saved for {slot}")

    if ctx.unmapped_assets:
        st.markdown("#### Unmapped Bynder assets")
        for a in list(ctx.unmapped_assets):
            assign_cols = st.columns([3, 1, 1])
            assign_cols[0].write(f"`{a.filename}`")
            target = assign_cols[1].selectbox(
                "Slot",
                AMAZON_SLOTS,
                key=f"unmap_slot_{a.asset_id}",
            )
            if assign_cols[2].button("Assign", key=f"unmap_btn_{a.asset_id}"):
                existing = ctx.slot_views[target]
                if existing.source != "empty":
                    st.warning(f"{target} was already filled by {existing.source} — overwriting.")
                ba = ctx.bynder_assets[a.asset_id]
                ctx.slot_views[target] = SlotView(
                    slot=target,
                    source="bynder",
                    filename=ba.filename,
                    asset_id=ba.asset_id,
                    local_path=None,
                )
                ctx.unmapped_assets = [u for u in ctx.unmapped_assets if u.asset_id != a.asset_id]
                st.success(f"Assigned to {target}")
                st.rerun()


def _render_package_button(session, ctx, bynder) -> None:
    st.divider()
    if not st.button("Package + Download", key="pkg_build", type="primary"):
        return

    slot_files: list[SlotFile] = []
    manifest: dict[str, dict] = {}

    for slot, view in ctx.slot_views.items():
        if view.source == "empty":
            continue

        if view.source == "bynder":
            asset = ctx.bynder_assets[view.asset_id]
            tmp = Path(tempfile.gettempdir()) / f"{ctx.sku}_{slot}.{asset.extension}"
            bynder.download_asset(asset, tmp)
            content = tmp.read_bytes()
            ext = asset.extension or Path(asset.filename).suffix.lstrip(".")
        else:
            content = Path(view.local_path).read_bytes()
            ext = Path(view.local_path).suffix.lstrip(".") or "jpg"

        result = validate_image(content, view.filename or slot)
        if not result.ok:
            st.error(f"{slot} validation failed: {'; '.join(result.errors)}")
            return
        for w in result.warnings:
            st.warning(f"{slot}: {w}")

        slot_files.append(SlotFile(amazon_slot=slot, content=content, extension=ext))
        manifest[slot] = {
            "source": view.source,
            "filename": view.filename,
            "asset_id": view.asset_id,
        }

    if not slot_files:
        st.error("No files to package.")
        return

    zip_bytes = build_zip(sku=ctx.sku, slots=slot_files)

    history = PackageHistory(
        sku=ctx.sku,
        packaged_by=st.session_state.get("user", "admin"),
        slot_manifest=manifest,
        zip_filename=f"{ctx.sku}_images.zip",
    )
    session.add(history)
    session.commit()

    st.download_button(
        label="Download zip",
        data=zip_bytes,
        file_name=f"{ctx.sku}_images.zip",
        mime="application/zip",
    )
