"""Run once: python tests/fixtures/make_barcelona_sample.py"""
import pandas as pd
from pathlib import Path


def make_sample():
    df = pd.DataFrame(
        [
            {
                "SKU": "PGR-001",
                "Global ASIN": "B00001",
                "SEO Cluster 1": "PopGrip Standard",
                "Tier for Forecasting - US": "A",
                "Collection": "Classic",
                "Item Description": "PopGrip Classic Black",
            },
            {
                "SKU": "PGR-002",
                "Global ASIN": "B00002",
                "SEO Cluster 1": "PopGrip Standard",
                "Tier for Forecasting - US": "B",
                "Collection": "Classic",
                "Item Description": "PopGrip Classic White",
            },
            {
                "SKU": "WLT-001",
                "Global ASIN": "B00003",
                "SEO Cluster 1": "Wallet",
                "Tier for Forecasting - US": "A",
                "Collection": "Wallet+",
                "Item Description": "Wallet Blue Marble",
            },
        ]
    )
    out = Path(__file__).parent / "barcelona_sample.xlsx"
    with pd.ExcelWriter(out) as writer:
        df.to_excel(writer, sheet_name="All Products", index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    make_sample()
