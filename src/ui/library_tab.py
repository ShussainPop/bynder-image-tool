from pathlib import Path
import streamlit as st

from src.config import load_config
from src.core.infographic_library import InfographicLibrary
from src.core.mapping_engine import AMAZON_SLOTS
from src.db.models import ProductLine
from src.db.session import get_session


def render() -> None:
    st.header("Infographic Library")
    cfg = load_config()
    session = get_session()
    lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    lines = session.query(ProductLine).order_by(ProductLine.name).all()
    line_names = ["All"] + [pl.name for pl in lines]
    filter_line = st.selectbox("Product line", line_names)
    filter_slot = st.selectbox("Slot", ["All"] + list(AMAZON_SLOTS))
    filter_tier = st.text_input("Tier filter (exact match, blank = all)")

    if filter_line == "All":
        rows = lib.list_all()
    else:
        pl = next(pl for pl in lines if pl.name == filter_line)
        rows = lib.list_by_product_line(pl.id)

    if filter_slot != "All":
        rows = [r for r in rows if r.amazon_slot == filter_slot]
    if filter_tier.strip():
        rows = [r for r in rows if r.tier == filter_tier.strip()]

    if not rows:
        st.info("No infographics match these filters.")
        return

    for r in rows:
        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].write(f"`{Path(r.file_path).name}`")
        cols[1].write(r.tier)
        cols[2].write(r.amazon_slot)
        cols[3].write(r.description or "")
        if cols[4].button("Delete", key=f"lib_del_{r.id}"):
            lib.delete(r.id)
            st.rerun()
