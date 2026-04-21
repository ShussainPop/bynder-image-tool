def resolve_csv_url(raw_asset: dict, derivative_key: str | None) -> str:
    """Return the best available public CDN URL for this Bynder asset.

    Precedence:
      1. Configured custom derivative (admin-defined, e.g. 'amazon_full')
      2. `original` field (if tenant has public-originals enabled)
      3. `webimage` (always present but ~800px - lower quality fallback)
    Empty string if none of these is populated.
    """
    thumbs = raw_asset.get("thumbnails") or {}
    if derivative_key and thumbs.get(derivative_key):
        return thumbs[derivative_key]
    original = raw_asset.get("original")
    if original:
        return original
    return thumbs.get("webimage", "")
