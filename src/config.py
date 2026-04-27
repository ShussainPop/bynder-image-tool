import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

_DEFAULT_UPC_KEYS = ["property_UPC", "property_GTIN", "property_Barcode"]


@dataclass(frozen=True)
class Config:
    database_url: str
    bynder_domain: str
    bynder_permanent_token: str | None
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
        default_factory=lambda: list(_DEFAULT_UPC_KEYS)
    )
    bynder_cache_ttl_days: int = 7


_REQUIRED = (
    "DATABASE_URL",
    "BYNDER_DOMAIN",
    "STREAMLIT_USERNAME",
    "STREAMLIT_PASSWORD",
)


def load_config() -> Config:
    load_dotenv()
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    # Bynder auth: either a permanent token, or client_id + client_secret.
    # make_bynder_client() prefers client credentials (auto-refresh) when both
    # are set.
    has_token = bool(os.environ.get("BYNDER_PERMANENT_TOKEN"))
    has_client_creds = bool(
        os.environ.get("BYNDER_CLIENT_ID")
        and os.environ.get("BYNDER_CLIENT_SECRET")
    )
    if not (has_token or has_client_creds):
        raise RuntimeError(
            "Missing Bynder credentials: set either BYNDER_PERMANENT_TOKEN, "
            "or both BYNDER_CLIENT_ID and BYNDER_CLIENT_SECRET."
        )

    upc_keys_raw = os.environ.get("BYNDER_CSV_UPC_KEYS", "")
    upc_keys = (
        [k.strip() for k in upc_keys_raw.split(",") if k.strip()]
        if upc_keys_raw
        else list(_DEFAULT_UPC_KEYS)
    )

    ttl_raw = os.environ.get("BYNDER_CACHE_TTL_DAYS", "").strip()
    if ttl_raw:
        try:
            ttl_days = int(ttl_raw)
        except ValueError as e:
            raise RuntimeError(
                f"BYNDER_CACHE_TTL_DAYS must be an integer, got {ttl_raw!r}"
            ) from e
        if ttl_days < 0:
            raise RuntimeError("BYNDER_CACHE_TTL_DAYS must be >= 0")
    else:
        ttl_days = 7

    return Config(
        database_url=os.environ["DATABASE_URL"],
        bynder_domain=os.environ["BYNDER_DOMAIN"],
        bynder_permanent_token=os.environ.get("BYNDER_PERMANENT_TOKEN") or None,
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
        bynder_cache_ttl_days=ttl_days,
    )
