import io
import zipfile
import pytest
from PIL import Image
from src.core.amazon_packager import (
    validate_image,
    build_zip,
    ValidationResult,
    SlotFile,
)


def _make_image_bytes(size=(1200, 1200), fmt="JPEG"):
    img = Image.new("RGB", size, color="white")
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def test_validate_image_accepts_1200_jpeg():
    result = validate_image(_make_image_bytes(), "x.jpg")
    assert result.ok is True
    assert result.warnings == []


def test_validate_image_warns_on_small_image():
    result = validate_image(_make_image_bytes(size=(500, 500)), "x.jpg")
    assert result.ok is True
    assert any("1000" in w for w in result.warnings)


def test_validate_image_blocks_unsupported_format():
    img = Image.new("RGB", (1200, 1200))
    buf = io.BytesIO()
    img.save(buf, "GIF")
    result = validate_image(buf.getvalue(), "x.gif")
    assert result.ok is False
    assert any("format" in e.lower() for e in result.errors)


def test_validate_image_blocks_over_10mb():
    big = b"\x00" * (11 * 1024 * 1024)
    result = validate_image(big, "x.jpg")
    assert result.ok is False
    assert any("10" in e for e in result.errors)


def test_build_zip_renames_files():
    slots = [
        SlotFile(amazon_slot="MAIN", content=_make_image_bytes(), extension="jpg"),
        SlotFile(amazon_slot="PT01", content=_make_image_bytes(), extension="jpg"),
    ]
    zip_bytes = build_zip(sku="ABC123", slots=slots)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = sorted(zf.namelist())
    assert names == ["ABC123.MAIN.jpg", "ABC123.PT01.jpg"]


def test_build_zip_rejects_duplicate_slots():
    slots = [
        SlotFile(amazon_slot="MAIN", content=_make_image_bytes(), extension="jpg"),
        SlotFile(amazon_slot="MAIN", content=_make_image_bytes(), extension="jpg"),
    ]
    with pytest.raises(ValueError, match="duplicate"):
        build_zip(sku="ABC", slots=slots)
