from src.db.models import (
    ProductLine,
    FilenamePattern,
    FilenameRule,
    Infographic,
    SkuOverride,
    PackageHistory,
)


def test_product_line_crud(db_session):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()
    fetched = db_session.query(ProductLine).filter_by(name="PopGrip Standard").one()
    assert fetched.id == line.id


def test_filename_rule_cascades_on_line_delete(db_session):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.flush()
    rule = FilenameRule(
        product_line_id=line.id,
        position_label="Front",
        amazon_slot="PT01",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.delete(line)
    db_session.commit()
    assert db_session.query(FilenameRule).count() == 0


def test_sku_override_unique_per_slot(db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db_session.add(SkuOverride(sku="ABC", amazon_slot="MAIN", source="bynder", bynder_asset_id="x"))
    db_session.commit()
    db_session.add(SkuOverride(sku="ABC", amazon_slot="MAIN", source="upload", uploaded_file_path="/tmp/y"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_package_history_stores_manifest(db_session):
    import json
    h = PackageHistory(
        sku="ABC",
        packaged_by="admin",
        slot_manifest={"MAIN": {"source": "bynder", "file": "x.jpg"}},
        zip_filename="ABC_images.zip",
    )
    db_session.add(h)
    db_session.commit()
    fetched = db_session.query(PackageHistory).one()
    assert fetched.slot_manifest["MAIN"]["source"] == "bynder"
