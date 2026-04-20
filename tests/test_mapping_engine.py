import pytest
from src.core.mapping_engine import (
    infer_regex,
    parse_filename,
    assign_slots,
    ParsedAsset,
    ProductLineRules,
    SlotAssignment,
)
from tests.fixtures.sample_filenames import POPGRIP_SAMPLES, WALLET_SAMPLES


def test_infer_regex_from_popgrip_samples():
    regex = infer_regex(POPGRIP_SAMPLES)
    import re
    pattern = re.compile(regex)
    for sample in POPGRIP_SAMPLES:
        assert pattern.search(sample), f"Regex did not match {sample}"


def test_parse_filename_extracts_label():
    parsed = parse_filename(
        "PCS_Derpy-and-Sussie_IP14_01_Front.png",
        regex=r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$",
    )
    assert parsed.position_number == "01"
    assert parsed.position_label == "Front"
    assert parsed.extension == "png"


def test_parse_filename_returns_none_on_mismatch():
    parsed = parse_filename(
        "random_garbage.png",
        regex=r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$",
    )
    assert parsed is None


def test_assign_slots_maps_rules():
    rules = ProductLineRules(
        regex=r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$",
        label_to_slot={"Front": "MAIN", "Back": "PT01", "Side": "PT02"},
    )
    assets = [
        {"filename": "X_01_Front.png", "asset_id": "a"},
        {"filename": "X_02_Back.png", "asset_id": "b"},
        {"filename": "X_03_Side.png", "asset_id": "c"},
    ]
    result = assign_slots(assets, rules)
    assert result.assigned["MAIN"].asset_id == "a"
    assert result.assigned["PT01"].asset_id == "b"
    assert result.assigned["PT02"].asset_id == "c"
    assert result.unmapped == []


def test_assign_slots_flags_unmapped():
    rules = ProductLineRules(
        regex=r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$",
        label_to_slot={"Front": "MAIN"},
    )
    assets = [
        {"filename": "X_01_Front.png", "asset_id": "a"},
        {"filename": "X_99_Unknown.png", "asset_id": "b"},
        {"filename": "garbage.tif", "asset_id": "c"},
    ]
    result = assign_slots(assets, rules)
    assert result.assigned["MAIN"].asset_id == "a"
    assert len(result.unmapped) == 2
    assert {a.asset_id for a in result.unmapped} == {"b", "c"}


def test_assign_slots_deterministic_on_collision():
    """When two assets map to the same slot, first one wins; second goes to unmapped."""
    rules = ProductLineRules(
        regex=r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$",
        label_to_slot={"Front": "MAIN"},
    )
    assets = [
        {"filename": "X_01_Front.png", "asset_id": "a"},
        {"filename": "X_99_Front.png", "asset_id": "b"},
    ]
    result = assign_slots(assets, rules)
    assert result.assigned["MAIN"].asset_id == "a"
    assert len(result.unmapped) == 1
    assert result.unmapped[0].asset_id == "b"
