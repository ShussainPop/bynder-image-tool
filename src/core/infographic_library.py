import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy.orm import Session

from src.core.mapping_engine import AMAZON_SLOTS
from src.db.models import Infographic, ProductLine


@dataclass
class InfographicInput:
    product_line_id: int
    tier: str
    amazon_slot: str
    filename: str
    content: bytes
    description: str | None = None


class InfographicLibrary:
    def __init__(self, session: Session, storage_dir: Path):
        self._session = session
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, inp: InfographicInput) -> Infographic:
        if inp.amazon_slot not in AMAZON_SLOTS:
            raise ValueError(f"invalid amazon_slot: {inp.amazon_slot!r}")

        line = self._session.get(ProductLine, inp.product_line_id)
        if line is None:
            raise ValueError(f"ProductLine {inp.product_line_id} not found")

        ext = Path(inp.filename).suffix.lstrip(".").lower() or "jpg"
        slug = _slug(line.name) or f"pl-{inp.product_line_id}"
        subdir = self._storage_dir / slug / inp.tier
        subdir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = subdir / unique_name
        file_path.write_bytes(inp.content)

        row = Infographic(
            product_line_id=inp.product_line_id,
            tier=inp.tier,
            amazon_slot=inp.amazon_slot,
            file_path=str(file_path),
            description=inp.description,
        )
        try:
            self._session.add(row)
            self._session.commit()
        except Exception:
            self._session.rollback()
            file_path.unlink(missing_ok=True)
            raise
        self._session.refresh(row)
        return row

    def find_for_slot(
        self, product_line_id: int, tier: str, amazon_slot: str
    ) -> Infographic | None:
        return (
            self._session.query(Infographic)
            .filter_by(
                product_line_id=product_line_id,
                tier=tier,
                amazon_slot=amazon_slot,
            )
            .order_by(Infographic.id.desc())
            .first()
        )

    def list_by_product_line(self, product_line_id: int) -> list[Infographic]:
        return (
            self._session.query(Infographic)
            .filter_by(product_line_id=product_line_id)
            .order_by(Infographic.tier, Infographic.amazon_slot)
            .all()
        )

    def list_all(self) -> list[Infographic]:
        return self._session.query(Infographic).order_by(Infographic.id).all()

    def delete(self, infographic_id: int) -> None:
        row = self._session.get(Infographic, infographic_id)
        if row is None:
            return
        path = Path(row.file_path)
        self._session.delete(row)
        self._session.commit()
        path.unlink(missing_ok=True)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
