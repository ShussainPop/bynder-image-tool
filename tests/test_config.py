import os
import pytest
from unittest.mock import patch


def test_config_loads_required_fields():
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
    assert cfg.database_url == "postgresql://test"
    assert cfg.bynder_domain == "popsockets.bynder.com"
    assert cfg.bynder_permanent_token == "tok"
    assert cfg.streamlit_username == "admin"
    assert cfg.streamlit_password == "pw"


def test_config_defaults_optional_fields():
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
    assert cfg.infographics_dir == "./infographics"
    assert cfg.product_catalog_xlsx_path == "./data/barcelona.xlsx"
    assert cfg.supabase_url is None


def test_config_raises_when_required_missing():
    with patch.dict(os.environ, {}, clear=True), \
         patch("src.config.load_dotenv", lambda: None):
        from src.config import load_config
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            load_config()
