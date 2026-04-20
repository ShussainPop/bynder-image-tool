import streamlit as st
from pathlib import Path

from src.core.mapping_engine import AMAZON_SLOTS, infer_regex, parse_filename
from src.core.product_catalog import ProductCatalog
from src.core.infographic_library import InfographicLibrary, InfographicInput
from src.db.models import ProductLine, FilenamePattern, FilenameRule, Infographic
from src.db.session import get_session
from src.config import load_config


def render() -> None:
    st.header("Mapping Wizard")
    cfg = load_config()
    session = get_session()
    catalog = ProductCatalog(xlsx_path=cfg.product_catalog_xlsx_path, supabase_client=None)
    lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.subheader("Product lines")
        existing_names = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
        try:
            catalog_lines = catalog.list_product_lines()
        except FileNotFoundError:
            catalog_lines = []
        all_lines = sorted(set(existing_names) | set(catalog_lines))
        options = ["+ New product line"] + all_lines
        choice = st.radio("Select a line", options, key="wiz_line_choice")

        if choice == "+ New product line":
            new_name = st.text_input("New product line name")
            if st.button("Create") and new_name.strip():
                session.add(ProductLine(name=new_name.strip()))
                session.commit()
                st.rerun()
            return

        pl = session.query(ProductLine).filter_by(name=choice).first()
        if pl is None:
            pl = ProductLine(name=choice)
            session.add(pl)
            session.commit()

    with col_right:
        st.subheader(f"Configure: {pl.name}")
        step = st.radio(
            "Step",
            ["1. Filename rules", "2. Infographics", "3. Review"],
            horizontal=True,
            key=f"step_{pl.id}",
        )
        if step.startswith("1"):
            _render_step1(session, pl)
        elif step.startswith("2"):
            _render_step2(session, pl, lib, catalog)
        else:
            _render_step3(session, pl)


def _render_step1(session, pl: ProductLine) -> None:
    st.markdown("### Step 1: Filename rules")

    existing_pattern = (
        session.query(FilenamePattern)
        .filter_by(product_line_id=pl.id)
        .order_by(FilenamePattern.id.desc())
        .first()
    )
    default_samples = existing_pattern.sample_filename if existing_pattern else ""

    samples_raw = st.text_area(
        "Paste 3-5 example Bynder filenames (one per line)",
        value=default_samples,
        height=120,
        key=f"samples_{pl.id}",
    )
    samples = [s.strip() for s in samples_raw.splitlines() if s.strip()]
    if not samples:
        st.info("Paste filenames above to infer a regex.")
        return

    try:
        regex = infer_regex(samples)
    except ValueError as e:
        st.error(str(e))
        regex = (
            existing_pattern.regex
            if existing_pattern
            else r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$"
        )

    regex = st.text_input("Regex (edit if needed)", value=regex, key=f"regex_{pl.id}")

    labels = sorted(
        {
            parse_filename(s, regex).position_label
            for s in samples
            if parse_filename(s, regex) is not None
        }
    )

    if not labels:
        st.warning("Regex did not extract any labels from your samples.")
        return

    existing_rules = {
        r.position_label: r.amazon_slot
        for r in session.query(FilenameRule).filter_by(product_line_id=pl.id).all()
    }

    label_to_slot: dict[str, str] = {}
    st.markdown("#### Map each position label to an Amazon slot")
    for label in labels:
        default = existing_rules.get(label, "MAIN")
        label_to_slot[label] = st.selectbox(
            f"{label}",
            AMAZON_SLOTS,
            index=AMAZON_SLOTS.index(default) if default in AMAZON_SLOTS else 0,
            key=f"slot_{pl.id}_{label}",
        )

    if st.button("Save filename rules", key=f"save_rules_{pl.id}"):
        session.query(FilenamePattern).filter_by(product_line_id=pl.id).delete()
        session.add(
            FilenamePattern(
                product_line_id=pl.id,
                regex=regex,
                sample_filename="\n".join(samples),
            )
        )
        session.query(FilenameRule).filter_by(product_line_id=pl.id).delete()
        for label, slot in label_to_slot.items():
            session.add(
                FilenameRule(
                    product_line_id=pl.id,
                    position_label=label,
                    amazon_slot=slot,
                )
            )
        session.commit()
        st.success("Filename rules saved.")


def _render_step2(
    session,
    pl: ProductLine,
    lib: InfographicLibrary,
    catalog: ProductCatalog,
) -> None:
    st.markdown("### Step 2: Infographics for this product line")

    try:
        tiers = catalog.list_tiers()
    except FileNotFoundError:
        tiers = []
    if not tiers:
        tiers = ["A", "B", "C"]

    with st.form(f"infographic_upload_{pl.id}", clear_on_submit=True):
        uploaded = st.file_uploader(
            "Upload infographic (JPEG or PNG)",
            type=["jpg", "jpeg", "png"],
        )
        tier = st.selectbox("Tier", tiers)
        slot = st.selectbox("Amazon slot", AMAZON_SLOTS)
        desc = st.text_input("Description (optional)")
        submit = st.form_submit_button("Save infographic")

        if submit:
            if uploaded is None:
                st.error("Pick a file to upload.")
            else:
                lib.save(
                    InfographicInput(
                        product_line_id=pl.id,
                        tier=tier,
                        amazon_slot=slot,
                        filename=uploaded.name,
                        content=uploaded.getvalue(),
                        description=desc or None,
                    )
                )
                st.success(f"Saved {uploaded.name} ({tier}, {slot})")

    st.markdown("#### Existing infographics for this line")
    rows = lib.list_by_product_line(pl.id)
    if not rows:
        st.info("No infographics uploaded yet.")
        return
    for r in rows:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(f"`{Path(r.file_path).name}` — {r.description or ''}")
        cols[1].write(r.tier)
        cols[2].write(r.amazon_slot)
        if cols[3].button("Delete", key=f"del_{r.id}"):
            lib.delete(r.id)
            st.rerun()


def _render_step3(session, pl: ProductLine) -> None:
    st.markdown("### Step 3: Review")
    rules = (
        session.query(FilenameRule)
        .filter_by(product_line_id=pl.id)
        .order_by(FilenameRule.amazon_slot)
        .all()
    )
    infographics = session.query(Infographic).filter_by(product_line_id=pl.id).all()

    st.markdown("**Filename rules**")
    if rules:
        st.table([{"Label": r.position_label, "Slot": r.amazon_slot} for r in rules])
    else:
        st.warning("No filename rules defined.")

    st.markdown("**Infographic coverage**")
    if not infographics:
        st.warning("No infographics uploaded.")
        return

    tiers = sorted({ig.tier for ig in infographics})
    coverage = {t: {slot: 0 for slot in AMAZON_SLOTS} for t in tiers}
    for ig in infographics:
        coverage[ig.tier][ig.amazon_slot] += 1

    st.table(
        [
            {"Tier": t, **{slot: coverage[t][slot] for slot in AMAZON_SLOTS}}
            for t in tiers
        ]
    )
