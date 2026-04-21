import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkuInfo:
    sku: str
    product_line: str | None
    tier: str | None
    description: str | None


_SUPABASE_TABLE = "contentup_products"


class ProductCatalog:
    """Resolve SKU -> (product_line, tier, description).
    Supabase is primary; Excel is fallback."""

    def __init__(self, xlsx_path: str, supabase_client: Any | None):
        self._xlsx_path = xlsx_path
        self._supabase = supabase_client

    def lookup(self, sku: str) -> SkuInfo | None:
        if self._supabase is not None:
            try:
                resp = (
                    self._supabase.table(_SUPABASE_TABLE)
                    .select("*")
                    .eq("sku", sku)
                    .execute()
                )
                rows = resp.data or []
                if rows:
                    row = rows[0]
                    return SkuInfo(
                        sku=sku,
                        product_line=row.get("seo_cluster_1"),
                        tier=row.get("tier"),
                        description=row.get("item_description"),
                    )
            except Exception as e:
                logger.warning(
                    "Supabase lookup failed for sku=%s, falling back to Excel: %s", sku, e
                )

        df = self._load_excel()
        rows = df[df["SKU"] == sku]
        if rows.empty:
            return None
        row = rows.iloc[0]
        return SkuInfo(
            sku=sku,
            product_line=_none_if_nan(row.get("SEO Cluster 1")),
            tier=_none_if_nan(row.get("Tier for Forecasting - US")),
            description=_none_if_nan(row.get("Item Description")),
        )

    def list_product_lines(self) -> list[str]:
        df = self._load_excel()
        vals = df["SEO Cluster 1"].dropna().unique().tolist()
        return sorted(str(v) for v in vals)

    def list_tiers(self) -> list[str]:
        df = self._load_excel()
        vals = df["Tier for Forecasting - US"].dropna().unique().tolist()
        return sorted(str(v) for v in vals)

    def list_skus_for_product_line(
        self, name: str, limit: int | None = None
    ) -> list[str]:
        df = self._load_excel()
        mask = df["SEO Cluster 1"].astype(str) == name
        skus = df.loc[mask, "SKU"].dropna().astype(str).tolist()
        if limit is not None:
            skus = skus[:limit]
        return skus

    def _load_excel(self) -> pd.DataFrame:
        return _cached_excel(self._xlsx_path)


@lru_cache(maxsize=4)
def _cached_excel(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Product catalog Excel not found: {path}")
    return pd.read_excel(p, sheet_name="All Products")


def _none_if_nan(v):
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    return str(v)
