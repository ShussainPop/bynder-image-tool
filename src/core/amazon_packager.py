import io
import zipfile
from dataclasses import dataclass, field
from PIL import Image


MAX_FILE_BYTES = 10 * 1024 * 1024
MIN_DIMENSION = 1000
ALLOWED_FORMATS = {"JPEG", "PNG"}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class SlotFile:
    amazon_slot: str
    content: bytes
    extension: str


def validate_image(content: bytes, filename: str) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if len(content) > MAX_FILE_BYTES:
        errors.append(f"File exceeds 10MB limit: {len(content)} bytes")

    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception as e:
        errors.append(f"Invalid image: {e}")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    try:
        img = Image.open(io.BytesIO(content))
        fmt = img.format or ""
        w, h = img.size
    except Exception as e:
        errors.append(f"Invalid image: {e}")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    if fmt not in ALLOWED_FORMATS:
        errors.append(f"Unsupported format '{fmt}'. Only JPEG and PNG are allowed.")

    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        warnings.append(f"Image below recommended 1000x1000 ({w}x{h})")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def build_zip(sku: str, slots: list[SlotFile]) -> bytes:
    seen_slots: set[str] = set()
    for s in slots:
        if s.amazon_slot in seen_slots:
            raise ValueError(f"duplicate slot in manifest: {s.amazon_slot}")
        seen_slots.add(s.amazon_slot)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for s in slots:
            arcname = f"{sku}.{s.amazon_slot}.{s.extension}"
            zf.writestr(arcname, s.content)
    return buf.getvalue()
