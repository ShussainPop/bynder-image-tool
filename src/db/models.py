from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class ProductLine(Base):
    __tablename__ = "contentup_image_product_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patterns: Mapped[list["FilenamePattern"]] = relationship(
        back_populates="product_line",
        cascade="all, delete-orphan",
    )
    rules: Mapped[list["FilenameRule"]] = relationship(
        back_populates="product_line",
        cascade="all, delete-orphan",
    )
    infographics: Mapped[list["Infographic"]] = relationship(
        back_populates="product_line",
        cascade="all, delete-orphan",
    )


class FilenamePattern(Base):
    __tablename__ = "contentup_image_filename_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_line_id: Mapped[int] = mapped_column(
        ForeignKey("contentup_image_product_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    regex: Mapped[str] = mapped_column(Text, nullable=False)
    sample_filename: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product_line: Mapped[ProductLine] = relationship(back_populates="patterns")


class FilenameRule(Base):
    __tablename__ = "contentup_image_filename_rules"
    __table_args__ = (
        UniqueConstraint("product_line_id", "position_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_line_id: Mapped[int] = mapped_column(
        ForeignKey("contentup_image_product_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_label: Mapped[str] = mapped_column(Text, nullable=False)
    amazon_slot: Mapped[str] = mapped_column(String(8), nullable=False)

    product_line: Mapped[ProductLine] = relationship(back_populates="rules")


class Infographic(Base):
    __tablename__ = "contentup_image_infographics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_line_id: Mapped[int] = mapped_column(
        ForeignKey("contentup_image_product_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    amazon_slot: Mapped[str] = mapped_column(String(8), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product_line: Mapped[ProductLine] = relationship(back_populates="infographics")


class SkuOverride(Base):
    __tablename__ = "contentup_image_sku_overrides"
    __table_args__ = (
        UniqueConstraint("sku", "amazon_slot"),
        CheckConstraint("source IN ('bynder', 'upload')", name="source_check"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    amazon_slot: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    bynder_asset_id: Mapped[str | None] = mapped_column(Text)
    uploaded_file_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PackageHistory(Base):
    __tablename__ = "contentup_image_package_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    packaged_by: Mapped[str | None] = mapped_column(Text)
    slot_manifest: Mapped[dict | None] = mapped_column(JSON)
    zip_filename: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BynderAssetCacheEntry(Base):
    __tablename__ = "contentup_image_bynder_asset_cache"

    sku: Mapped[str] = mapped_column(Text, primary_key=True)
    assets_json: Mapped[list] = mapped_column(JSON, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
