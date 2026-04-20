from dataclasses import dataclass
from pathlib import Path

from src.core.bynder_client import BynderClient, BynderAsset
from src.core.mapping_engine import (
    AMAZON_SLOTS,
    ProductLineRules,
    assign_slots,
    ParsedAsset,
)
from src.core.infographic_library import InfographicLibrary
from src.db.models import ProductLine, FilenamePattern, FilenameRule
from sqlalchemy.orm import Session


@dataclass
class SlotView:
    slot: str
    source: str   # 'bynder' | 'infographic' | 'empty' | 'override'
    filename: str | None
    asset_id: str | None
    local_path: str | None


@dataclass
class PackageContext:
    sku: str
    product_line: ProductLine | None
    tier: str | None
    slot_views: dict[str, SlotView]
    unmapped_assets: list[ParsedAsset]
    bynder_assets: dict[str, BynderAsset]


def build_package_context(
    session: Session,
    sku: str,
    product_line: ProductLine,
    tier: str,
    bynder_client: BynderClient,
    infographic_lib: InfographicLibrary,
) -> PackageContext:
    assets = bynder_client.search_by_sku(sku)
    asset_map = {a.asset_id: a for a in assets}

    pattern_row = (
        session.query(FilenamePattern)
        .filter_by(product_line_id=product_line.id)
        .order_by(FilenamePattern.id.desc())
        .first()
    )
    rule_rows = session.query(FilenameRule).filter_by(product_line_id=product_line.id).all()

    slot_views: dict[str, SlotView] = {
        slot: SlotView(slot=slot, source="empty", filename=None, asset_id=None, local_path=None)
        for slot in AMAZON_SLOTS
    }

    unmapped: list[ParsedAsset] = []

    if pattern_row and rule_rows:
        rules = ProductLineRules(
            regex=pattern_row.regex,
            label_to_slot={r.position_label: r.amazon_slot for r in rule_rows},
        )
        raw_assets = [{"asset_id": a.asset_id, "filename": a.filename} for a in assets]
        result = assign_slots(raw_assets, rules)
        for slot, parsed in result.assigned.items():
            slot_views[slot] = SlotView(
                slot=slot,
                source="bynder",
                filename=parsed.filename,
                asset_id=parsed.asset_id,
                local_path=None,
            )
        unmapped = result.unmapped

    for slot, view in slot_views.items():
        if view.source != "empty":
            continue
        ig = infographic_lib.find_for_slot(product_line.id, tier, slot)
        if ig is not None:
            slot_views[slot] = SlotView(
                slot=slot,
                source="infographic",
                filename=Path(ig.file_path).name,
                asset_id=str(ig.id),
                local_path=ig.file_path,
            )

    return PackageContext(
        sku=sku,
        product_line=product_line,
        tier=tier,
        slot_views=slot_views,
        unmapped_assets=unmapped,
        bynder_assets=asset_map,
    )
