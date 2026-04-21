import datetime as dt
from src.core.bulk_export import export_filename


def test_export_filename_format():
    when = dt.datetime(2026, 4, 21, 14, 30, 22)
    assert export_filename(when) == "bynder_export_2026-04-21_143022.csv"


def test_export_filename_defaults_to_now(monkeypatch):
    # sanity check — uses datetime.now() and matches the format
    name = export_filename()
    assert name.startswith("bynder_export_")
    assert name.endswith(".csv")
    assert len(name) == len("bynder_export_2026-04-21_143022.csv")
