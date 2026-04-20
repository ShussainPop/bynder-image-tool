from pathlib import Path
from src.db.models import ProductLine, Infographic
from src.core.infographic_library import (
    InfographicLibrary,
    InfographicInput,
)


def test_save_infographic_writes_file_and_row(db_session, tmp_path):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()

    lib = InfographicLibrary(session=db_session, storage_dir=tmp_path)
    record = lib.save(
        InfographicInput(
            product_line_id=line.id,
            tier="A",
            amazon_slot="MAIN",
            filename="how-to-use.jpg",
            content=b"FAKEIMAGE",
            description="How to use the grip",
        )
    )
    assert Path(record.file_path).exists()
    assert Path(record.file_path).read_bytes() == b"FAKEIMAGE"
    assert db_session.query(Infographic).count() == 1


def test_find_for_slot_returns_matching(db_session, tmp_path):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()

    lib = InfographicLibrary(session=db_session, storage_dir=tmp_path)
    lib.save(InfographicInput(
        product_line_id=line.id, tier="A", amazon_slot="PT07",
        filename="a.jpg", content=b"x"
    ))
    lib.save(InfographicInput(
        product_line_id=line.id, tier="B", amazon_slot="PT07",
        filename="b.jpg", content=b"y"
    ))

    result = lib.find_for_slot(product_line_id=line.id, tier="A", amazon_slot="PT07")
    assert result is not None
    assert Path(result.file_path).read_bytes() == b"x"


def test_find_for_slot_returns_none_when_no_match(db_session, tmp_path):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()

    lib = InfographicLibrary(session=db_session, storage_dir=tmp_path)
    assert lib.find_for_slot(line.id, "A", "MAIN") is None


def test_list_by_product_line(db_session, tmp_path):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()

    lib = InfographicLibrary(session=db_session, storage_dir=tmp_path)
    lib.save(InfographicInput(line.id, "A", "MAIN", "a.jpg", b"x"))
    lib.save(InfographicInput(line.id, "B", "PT08", "b.jpg", b"y"))

    rows = lib.list_by_product_line(line.id)
    assert len(rows) == 2


def test_delete_removes_row_and_file(db_session, tmp_path):
    line = ProductLine(name="PopGrip Standard")
    db_session.add(line)
    db_session.commit()

    lib = InfographicLibrary(session=db_session, storage_dir=tmp_path)
    rec = lib.save(InfographicInput(line.id, "A", "MAIN", "a.jpg", b"x"))
    file_path = Path(rec.file_path)

    lib.delete(rec.id)
    assert db_session.query(Infographic).count() == 0
    assert not file_path.exists()
