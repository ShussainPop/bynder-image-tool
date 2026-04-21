import sys
from pathlib import Path

# Streamlit invokes this file directly; ensure the project root is importable
# so `from src....` resolves without requiring PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from src.config import load_config
from src.ui.components import require_auth


def main() -> None:
    st.set_page_config(
        page_title="Bynder Image Tool",
        page_icon="📦",
        layout="wide",
    )

    cfg = load_config()
    if not require_auth(cfg.streamlit_username, cfg.streamlit_password):
        return

    st.sidebar.title("Bynder Image Tool")
    tab = st.sidebar.radio(
        "Navigate",
        ["Mapping Wizard", "Package SKU", "Library"],
        key="nav",
    )

    if tab == "Mapping Wizard":
        from src.ui.wizard_tab import render as render_wizard
        render_wizard()
    elif tab == "Package SKU":
        from src.ui.package_tab import render as render_package
        render_package()
    else:
        from src.ui.library_tab import render as render_library
        render_library()


if __name__ == "__main__":
    main()
