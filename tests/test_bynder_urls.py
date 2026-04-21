from src.core.bynder_urls import resolve_csv_url


def test_prefers_configured_derivative_when_present():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {
            "webimage": "https://cdn/web.jpg",
            "amazon_full": "https://cdn/full.jpg",
        },
    }
    assert resolve_csv_url(raw, "amazon_full") == "https://cdn/full.jpg"


def test_falls_back_to_original_when_derivative_missing():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, "amazon_full") == "https://cdn/orig.jpg"


def test_falls_back_to_original_when_derivative_key_none():
    raw = {
        "original": "https://cdn/orig.jpg",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, None) == "https://cdn/orig.jpg"


def test_falls_back_to_webimage_when_original_empty():
    raw = {
        "original": "",
        "thumbnails": {"webimage": "https://cdn/web.jpg"},
    }
    assert resolve_csv_url(raw, None) == "https://cdn/web.jpg"


def test_returns_empty_string_when_nothing_available():
    raw = {"thumbnails": {}}
    assert resolve_csv_url(raw, None) == ""


def test_handles_missing_thumbnails_dict():
    raw = {}
    assert resolve_csv_url(raw, "amazon_full") == ""
