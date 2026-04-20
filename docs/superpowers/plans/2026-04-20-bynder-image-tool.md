# Bynder Image Pipeline Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit standalone tool that pulls Bynder product images by SKU, maps them to Amazon image slots (MAIN + PT01..PT08) via per-product-line filename rules, splices reusable infographics, and exports rename-ready zip packages for Amazon upload.

**Architecture:** Streamlit UI + Python core modules (framework-agnostic) + SQLAlchemy 2.0 models + Alembic migrations against Postgres. Local Docker for dev, shared Supabase (`xjvwwwfpauazdzibclmc`) for prod. `src/core/` lifts verbatim into `popsockets-content-manager` in Phase 2.

**Tech Stack:** Python 3.11, Streamlit, SQLAlchemy 2.0, Alembic, Postgres 15, `bynder-sdk`, pandas + openpyxl, Pillow, Docker + docker-compose, pytest + pytest-cov.

**Reference spec:** `docs/superpowers/specs/2026-04-20-bynder-image-tool-design.md`

---

## File Structure

```
bynder-image-tool/
├── src/
│   ├── __init__.py
│   ├── config.py                    (env var loading)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bynder_client.py         (Bynder API wrapper)
│   │   ├── product_catalog.py       (Supabase + Excel lookup)
│   │   ├── mapping_engine.py        (regex parse + slot assignment)
│   │   ├── infographic_library.py   (DB CRUD + file storage)
│   │   └── amazon_packager.py       (validate + rename + zip)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                (SQLAlchemy ORM)
│   │   ├── session.py               (engine + session factory)
│   │   └── alembic/                 (migrations)
│   └── ui/
│       ├── __init__.py
│       ├── app.py                   (Streamlit entry + auth + routing)
│       ├── wizard_tab.py
│       ├── package_tab.py
│       ├── library_tab.py
│       └── components.py            (shared widgets)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── bynder_media_list.json
│   │   ├── sample_filenames.py
│   │   └── barcelona_sample.xlsx
│   ├── test_mapping_engine.py
│   ├── test_amazon_packager.py
│   ├── test_product_catalog.py
│   ├── test_bynder_client.py
│   └── test_infographic_library.py
├── infographics/                    (gitignored)
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/db/__init__.py`
- Create: `src/ui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/__init__.py`

- [ ] **Step 1: Write `.gitignore`**

Create `.gitignore`:

```
__pycache__/
*.pyc
.venv/
venv/
.env
.pytest_cache/
.coverage
htmlcov/
infographics/
*.zip
.streamlit/secrets.toml
*.sqlite
.vscode/
.idea/
```

- [ ] **Step 2: Write `requirements.txt`**

Create `requirements.txt`:

```
streamlit==1.40.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg2-binary==2.9.10
python-dotenv==1.0.1
pandas==2.2.3
openpyxl==3.1.5
pillow==11.0.0
bynder-sdk==2.0.2
supabase==2.10.0
requests==2.32.3
pytest==8.3.4
pytest-cov==6.0.0
pytest-mock==3.14.0
```

- [ ] **Step 3: Write `.env.example`**

Create `.env.example`:

```
# Database
DATABASE_URL=postgresql://bynder_user:bynder_pass@localhost:5432/bynder_tool

# Bynder API
BYNDER_DOMAIN=popsockets.bynder.com
BYNDER_PERMANENT_TOKEN=
BYNDER_CLIENT_ID=
BYNDER_CLIENT_SECRET=
BYNDER_REDIRECT_URI=

# Supabase (optional - falls back to Excel if unset)
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Paths
PRODUCT_CATALOG_XLSX_PATH=./data/barcelona.xlsx
INFOGRAPHICS_DIR=./infographics

# Streamlit auth (shared login for Phase 1)
STREAMLIT_USERNAME=admin
STREAMLIT_PASSWORD=change-me
```

- [ ] **Step 4: Write `docker-compose.yml`**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_USER: bynder_user
      POSTGRES_PASSWORD: bynder_pass
      POSTGRES_DB: bynder_tool
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bynder_user -d bynder_tool"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    restart: unless-stopped
    ports:
      - "8501:8501"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./infographics:/app/infographics
      - ./data:/app/data:ro

volumes:
  postgres_data:
```

- [ ] **Step 5: Create empty `__init__.py` files**

Create each of these as empty files:

- `src/__init__.py`
- `src/core/__init__.py`
- `src/db/__init__.py`
- `src/ui/__init__.py`
- `tests/__init__.py`
- `tests/fixtures/__init__.py`

- [ ] **Step 6: Verify Python environment works**

Run:

```bash
cd /c/projects/bynder-image-tool
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Expected: All packages install without error.

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements.txt .env.example docker-compose.yml src/ tests/
git commit -m "chore: scaffold project structure with deps and docker setup"
```

---

## Task 2: Configuration Loader

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest
from unittest.mock import patch


def test_config_loads_required_fields():
    env = {
        "DATABASE_URL": "postgresql://test",
        "BYNDER_DOMAIN": "popsockets.bynder.com",
        "BYNDER_PERMANENT_TOKEN": "tok",
        "STREAMLIT_USERNAME": "admin",
        "STREAMLIT_PASSWORD": "pw",
    }
    with patch.dict(os.environ, env, clear=True):
        from src.config import load_config
        cfg = load_config()
    assert cfg.database_url == "postgresql://test"
    assert cfg.bynder_domain == "popsockets.bynder.com"
    assert cfg.bynder_permanent_token == "tok"
    assert cfg.streamlit_username == "admin"
    assert cfg.streamlit_password == "pw"


def test_config_defaults_optional_fields():
    env = {
        "DATABASE_URL": "postgresql://test",
        "BYNDER_DOMAIN": "popsockets.bynder.com",
        "BYNDER_PERMANENT_TOKEN": "tok",
        "STREAMLIT_USERNAME": "admin",
        "STREAMLIT_PASSWORD": "pw",
    }
    with patch.dict(os.environ, env, clear=True):
        from src.config import load_config
        cfg = load_config()
    assert cfg.infographics_dir == "./infographics"
    assert cfg.product_catalog_xlsx_path == "./data/barcelona.xlsx"
    assert cfg.supabase_url is None


def test_config_raises_when_required_missing():
    with patch.dict(os.environ, {}, clear=True):
        from src.config import load_config
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            load_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`.

- [ ] **Step 3: Write implementation**

Create `src/config.py`:

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    database_url: str
    bynder_domain: str
    bynder_permanent_token: str
    streamlit_username: str
    streamlit_password: str
    bynder_client_id: str | None
    bynder_client_secret: str | None
    bynder_redirect_uri: str | None
    supabase_url: str | None
    supabase_service_key: str | None
    product_catalog_xlsx_path: str
    infographics_dir: str


_REQUIRED = (
    "DATABASE_URL",
    "BYNDER_DOMAIN",
    "BYNDER_PERMANENT_TOKEN",
    "STREAMLIT_USERNAME",
    "STREAMLIT_PASSWORD",
)


def load_config() -> Config:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Config(
        database_url=os.environ["DATABASE_URL"],
        bynder_domain=os.environ["BYNDER_DOMAIN"],
        bynder_permanent_token=os.environ["BYNDER_PERMANENT_TOKEN"],
        streamlit_username=os.environ["STREAMLIT_USERNAME"],
        streamlit_password=os.environ["STREAMLIT_PASSWORD"],
        bynder_client_id=os.environ.get("BYNDER_CLIENT_ID") or None,
        bynder_client_secret=os.environ.get("BYNDER_CLIENT_SECRET") or None,
        bynder_redirect_uri=os.environ.get("BYNDER_REDIRECT_URI") or None,
        supabase_url=os.environ.get("SUPABASE_URL") or None,
        supabase_service_key=os.environ.get("SUPABASE_SERVICE_KEY") or None,
        product_catalog_xlsx_path=os.environ.get(
            "PRODUCT_CATALOG_XLSX_PATH", "./data/barcelona.xlsx"
        ),
        infographics_dir=os.environ.get("INFOGRAPHICS_DIR", "./infographics"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): add env-driven config loader with required-field validation"
```

---

## Task 3: Database Models

**Files:**
- Create: `src/db/models.py`
- Create: `src/db/session.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write `conftest.py` with test DB fixture**

Create `tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_engine():
    """SQLite in-memory engine for unit tests.
    Production uses Postgres; SQLite is fine for model-level unit tests."""
    engine = create_engine("sqlite:///:memory:", future=True)
    from src.db.models import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
```

- [ ] **Step 2: Write the failing model test**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.models'`.

- [ ] **Step 4: Write model implementation**

Create `src/db/models.py`:

```python
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
```

- [ ] **Step 5: Write session factory**

Create `src/db/session.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import load_config

_engine = None
_Session = None


def get_engine():
    global _engine
    if _engine is None:
        cfg = load_config()
        _engine = create_engine(cfg.database_url, future=True, pool_pre_ping=True)
    return _engine


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine(), future=True, expire_on_commit=False)
    return _Session()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/db/ tests/conftest.py tests/test_models.py
git commit -m "feat(db): add SQLAlchemy models for 6 contentup_image_ tables"
```

---

## Task 4: Alembic Migration

**Files:**
- Create: `alembic.ini`
- Create: `src/db/alembic/env.py`
- Create: `src/db/alembic/script.py.mako`
- Create: `src/db/alembic/versions/` (directory)
- Create: `src/db/alembic/versions/<autogen>_initial.py` (generated)

- [ ] **Step 1: Initialize Alembic**

From project root run:

```bash
alembic init -t generic src/db/alembic
```

Expected: Creates `src/db/alembic/` directory + `alembic.ini`.

- [ ] **Step 2: Update `alembic.ini`**

Edit `alembic.ini` — set `script_location`:

```ini
[alembic]
script_location = src/db/alembic
sqlalchemy.url =
```

(Leave `sqlalchemy.url` blank — `env.py` will pull from our config.)

- [ ] **Step 3: Rewrite `src/db/alembic/env.py`**

Replace contents of `src/db/alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.config import load_config
from src.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", load_config().database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Start Postgres via docker-compose**

Run:

```bash
docker compose up -d postgres
```

Expected: Postgres container running on 5432.

Verify: `docker compose ps` shows `postgres` healthy.

- [ ] **Step 5: Create `.env` from template**

```bash
cp .env.example .env
```

Set at minimum `DATABASE_URL`, `BYNDER_DOMAIN`, `BYNDER_PERMANENT_TOKEN`, `STREAMLIT_USERNAME`, `STREAMLIT_PASSWORD` (dummy values fine for migration test).

- [ ] **Step 6: Generate initial migration**

Run:

```bash
alembic revision --autogenerate -m "initial contentup_image tables"
```

Expected: New file in `src/db/alembic/versions/` with all 6 `CREATE TABLE` ops.

- [ ] **Step 7: Apply migration and verify**

Run:

```bash
alembic upgrade head
```

Then verify in Postgres:

```bash
docker compose exec postgres psql -U bynder_user -d bynder_tool -c "\dt"
```

Expected: Lists 6 `contentup_image_*` tables + `alembic_version`.

- [ ] **Step 8: Commit**

```bash
git add alembic.ini src/db/alembic/
git commit -m "feat(db): add alembic with initial migration for contentup_image tables"
```

---

## Task 5: Mapping Engine

**Files:**
- Create: `src/core/mapping_engine.py`
- Create: `tests/test_mapping_engine.py`
- Create: `tests/fixtures/sample_filenames.py`

- [ ] **Step 1: Write filename fixtures**

Create `tests/fixtures/sample_filenames.py`:

```python
POPGRIP_SAMPLES = [
    "PCS_Derpy-and-Sussie_IP14_01_Front.png",
    "PCS_Derpy-and-Sussie_IP14_02_Back.png",
    "PCS_Derpy-and-Sussie_IP14_03_Side.png",
    "PCS_Derpy-and-Sussie_IP14_04_Lifestyle.png",
    "PCS_Derpy-and-Sussie_IP14_05_Scale.png",
]

WALLET_SAMPLES = [
    "PCW_Blue-Marble_Gen2_01_Hero.jpg",
    "PCW_Blue-Marble_Gen2_02_Open.jpg",
    "PCW_Blue-Marble_Gen2_03_CardSlots.jpg",
]
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_mapping_engine.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_mapping_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.mapping_engine'`.

- [ ] **Step 4: Write implementation**

Create `src/core/mapping_engine.py`:

```python
import re
from dataclasses import dataclass, field


AMAZON_SLOTS = ("MAIN", "PT01", "PT02", "PT03", "PT04", "PT05", "PT06", "PT07", "PT08")


@dataclass(frozen=True)
class ParsedAsset:
    asset_id: str
    filename: str
    position_number: str | None
    position_label: str | None
    extension: str | None


@dataclass(frozen=True)
class ProductLineRules:
    regex: str
    label_to_slot: dict[str, str]


@dataclass
class SlotAssignmentResult:
    assigned: dict[str, ParsedAsset] = field(default_factory=dict)
    unmapped: list[ParsedAsset] = field(default_factory=list)


SlotAssignment = SlotAssignmentResult  # alias to match test import


_DEFAULT_REGEX = r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$"


def infer_regex(sample_filenames: list[str]) -> str:
    """Return the default regex. Future enhancement: analyze samples to tune it."""
    pattern = re.compile(_DEFAULT_REGEX, re.IGNORECASE)
    if not all(pattern.search(s) for s in sample_filenames):
        raise ValueError(
            "Default regex does not match all samples. Edit the regex manually in the wizard."
        )
    return _DEFAULT_REGEX


def parse_filename(filename: str, regex: str) -> ParsedAsset | None:
    match = re.search(regex, filename, re.IGNORECASE)
    if not match:
        return None
    number, label, ext = match.group(1), match.group(2), match.group(3)
    return ParsedAsset(
        asset_id="",
        filename=filename,
        position_number=number,
        position_label=label,
        extension=ext.lower(),
    )


def assign_slots(
    assets: list[dict],
    rules: ProductLineRules,
) -> SlotAssignmentResult:
    result = SlotAssignmentResult()
    for raw in assets:
        parsed_core = parse_filename(raw["filename"], rules.regex)
        parsed = (
            ParsedAsset(
                asset_id=raw["asset_id"],
                filename=raw["filename"],
                position_number=parsed_core.position_number if parsed_core else None,
                position_label=parsed_core.position_label if parsed_core else None,
                extension=parsed_core.extension if parsed_core else None,
            )
            if parsed_core
            else ParsedAsset(
                asset_id=raw["asset_id"],
                filename=raw["filename"],
                position_number=None,
                position_label=None,
                extension=None,
            )
        )

        if parsed.position_label is None:
            result.unmapped.append(parsed)
            continue

        slot = rules.label_to_slot.get(parsed.position_label)
        if slot is None:
            result.unmapped.append(parsed)
            continue

        if slot in result.assigned:
            result.unmapped.append(parsed)
            continue

        result.assigned[slot] = parsed
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_mapping_engine.py -v`
Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/mapping_engine.py tests/test_mapping_engine.py tests/fixtures/sample_filenames.py
git commit -m "feat(core): add mapping engine for filename-to-Amazon-slot assignment"
```

---

## Task 6: Amazon Packager

**Files:**
- Create: `src/core/amazon_packager.py`
- Create: `tests/test_amazon_packager.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_amazon_packager.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_amazon_packager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.amazon_packager'`.

- [ ] **Step 3: Write implementation**

Create `src/core/amazon_packager.py`:

```python
import io
import zipfile
from dataclasses import dataclass, field
from PIL import Image


MAX_FILE_BYTES = 10 * 1024 * 1024
MIN_DIMENSION = 1000
ALLOWED_FORMATS = {"JPEG", "PNG"}
EXT_MAP = {"JPEG": "jpg", "PNG": "png"}


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

    img = Image.open(io.BytesIO(content))
    fmt = img.format or ""
    if fmt not in ALLOWED_FORMATS:
        errors.append(f"Unsupported format '{fmt}'. Only JPEG and PNG are allowed.")

    w, h = img.size
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_amazon_packager.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/amazon_packager.py tests/test_amazon_packager.py
git commit -m "feat(core): add Amazon packager with validation and zip output"
```

---

## Task 7: Product Catalog (Excel + Supabase)

**Files:**
- Create: `src/core/product_catalog.py`
- Create: `tests/test_product_catalog.py`
- Create: `tests/fixtures/barcelona_sample.xlsx` (generated via script)
- Create: `tests/fixtures/make_barcelona_sample.py` (one-time generator)

- [ ] **Step 1: Create sample Excel fixture generator**

Create `tests/fixtures/make_barcelona_sample.py`:

```python
"""Run once: python tests/fixtures/make_barcelona_sample.py"""
import pandas as pd
from pathlib import Path


def make_sample():
    df = pd.DataFrame(
        [
            {
                "SKU": "PGR-001",
                "Global ASIN": "B00001",
                "SEO Cluster 1": "PopGrip Standard",
                "Tier for Forecasting - US": "A",
                "Collection": "Classic",
                "Item Description": "PopGrip Classic Black",
            },
            {
                "SKU": "PGR-002",
                "Global ASIN": "B00002",
                "SEO Cluster 1": "PopGrip Standard",
                "Tier for Forecasting - US": "B",
                "Collection": "Classic",
                "Item Description": "PopGrip Classic White",
            },
            {
                "SKU": "WLT-001",
                "Global ASIN": "B00003",
                "SEO Cluster 1": "Wallet",
                "Tier for Forecasting - US": "A",
                "Collection": "Wallet+",
                "Item Description": "Wallet Blue Marble",
            },
        ]
    )
    out = Path(__file__).parent / "barcelona_sample.xlsx"
    with pd.ExcelWriter(out) as writer:
        df.to_excel(writer, sheet_name="All Products", index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    make_sample()
```

Run it:

```bash
python tests/fixtures/make_barcelona_sample.py
```

Expected: File `tests/fixtures/barcelona_sample.xlsx` created.

- [ ] **Step 2: Write the failing test**

Create `tests/test_product_catalog.py`:

```python
from pathlib import Path
import pytest
from src.core.product_catalog import ProductCatalog, SkuInfo

FIXTURE = Path(__file__).parent / "fixtures" / "barcelona_sample.xlsx"


def test_excel_lookup_returns_sku_info():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    info = cat.lookup("PGR-001")
    assert info.sku == "PGR-001"
    assert info.product_line == "PopGrip Standard"
    assert info.tier == "A"
    assert info.description == "PopGrip Classic Black"


def test_excel_lookup_returns_none_for_missing_sku():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    assert cat.lookup("DOES-NOT-EXIST") is None


def test_list_product_lines():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    lines = cat.list_product_lines()
    assert set(lines) == {"PopGrip Standard", "Wallet"}


def test_list_tiers():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    tiers = cat.list_tiers()
    assert set(tiers) == {"A", "B"}


def test_supabase_takes_precedence_over_excel(mocker):
    supabase_stub = mocker.Mock()
    supabase_stub.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "sku": "PGR-001",
            "seo_cluster_1": "OverrideLine",
            "tier": "Z",
            "item_description": "Overridden",
        }
    ]
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=supabase_stub)
    info = cat.lookup("PGR-001")
    assert info.product_line == "OverrideLine"
    assert info.tier == "Z"


def test_supabase_falls_back_to_excel_on_miss(mocker):
    supabase_stub = mocker.Mock()
    supabase_stub.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=supabase_stub)
    info = cat.lookup("PGR-001")
    assert info.product_line == "PopGrip Standard"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_product_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.product_catalog'`.

- [ ] **Step 4: Write implementation**

Create `src/core/product_catalog.py`:

```python
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import pandas as pd


@dataclass(frozen=True)
class SkuInfo:
    sku: str
    product_line: str | None
    tier: str | None
    description: str | None


_SUPABASE_TABLE = "contentup_products"  # adjust if content_manager uses a different name


class ProductCatalog:
    """Resolve SKU -> (product_line, tier, description).
    Supabase is primary; Excel is fallback."""

    def __init__(self, xlsx_path: str, supabase_client: Any | None):
        self._xlsx_path = xlsx_path
        self._supabase = supabase_client

    def lookup(self, sku: str) -> SkuInfo | None:
        if self._supabase is not None:
            try:
                resp = (
                    self._supabase.table(_SUPABASE_TABLE)
                    .select("*")
                    .eq("sku", sku)
                    .execute()
                )
                rows = resp.data or []
                if rows:
                    row = rows[0]
                    return SkuInfo(
                        sku=sku,
                        product_line=row.get("seo_cluster_1"),
                        tier=row.get("tier"),
                        description=row.get("item_description"),
                    )
            except Exception:
                pass

        df = self._load_excel()
        rows = df[df["SKU"] == sku]
        if rows.empty:
            return None
        row = rows.iloc[0]
        return SkuInfo(
            sku=sku,
            product_line=_none_if_nan(row.get("SEO Cluster 1")),
            tier=_none_if_nan(row.get("Tier for Forecasting - US")),
            description=_none_if_nan(row.get("Item Description")),
        )

    def list_product_lines(self) -> list[str]:
        df = self._load_excel()
        vals = df["SEO Cluster 1"].dropna().unique().tolist()
        return sorted(str(v) for v in vals)

    def list_tiers(self) -> list[str]:
        df = self._load_excel()
        vals = df["Tier for Forecasting - US"].dropna().unique().tolist()
        return sorted(str(v) for v in vals)

    def _load_excel(self) -> pd.DataFrame:
        return _cached_excel(self._xlsx_path)


@lru_cache(maxsize=4)
def _cached_excel(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Product catalog Excel not found: {path}")
    return pd.read_excel(p, sheet_name="All Products")


def _none_if_nan(v):
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    return str(v)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_product_catalog.py -v`
Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/product_catalog.py tests/test_product_catalog.py tests/fixtures/
git commit -m "feat(core): add product catalog with Supabase primary + Excel fallback"
```

---

## Task 8: Bynder Client

**Note:** The project uses `bynder-sdk==2.0.2` (v2.x). The implementer must verify v2 import paths and API surface in `bynder_sdk/asset_bank_client.py`. If the v2 SDK shape differs materially from what this task assumes (`bynder_sdk.BynderClient`, `asset_bank_client.media_list({...})`), adapt the wrapper to the actual v2 API and report the adaptation.

**Files:**
- Create: `src/core/bynder_client.py`
- Create: `tests/test_bynder_client.py`
- Create: `tests/fixtures/bynder_media_list.json`

- [ ] **Step 1: Write mock Bynder response fixture**

Create `tests/fixtures/bynder_media_list.json`:

```json
[
  {
    "id": "asset-001",
    "name": "PCS_Derpy-and-Sussie_IP14_01_Front",
    "original": "https://popsockets.bynder.com/m/asset-001/original/PCS_Derpy-and-Sussie_IP14_01_Front.png",
    "property_sku": "PGR-001",
    "extension": ["png"]
  },
  {
    "id": "asset-002",
    "name": "PCS_Derpy-and-Sussie_IP14_02_Back",
    "original": "https://popsockets.bynder.com/m/asset-002/original/PCS_Derpy-and-Sussie_IP14_02_Back.png",
    "property_sku": "PGR-001",
    "extension": ["png"]
  }
]
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_bynder_client.py`:

```python
import json
from pathlib import Path
import pytest
from src.core.bynder_client import BynderClient, BynderAsset

FIXTURE = Path(__file__).parent / "fixtures" / "bynder_media_list.json"


def _fake_media_list_response():
    return json.loads(FIXTURE.read_text())


def test_search_by_sku_returns_assets(mocker):
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = _fake_media_list_response()
    client = BynderClient(sdk=fake_sdk)

    assets = client.search_by_sku("PGR-001")
    assert len(assets) == 2
    assert assets[0].asset_id == "asset-001"
    assert assets[0].filename == "PCS_Derpy-and-Sussie_IP14_01_Front.png"
    assert assets[0].sku == "PGR-001"


def test_search_by_sku_returns_empty_on_miss(mocker):
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = []
    client = BynderClient(sdk=fake_sdk)
    assert client.search_by_sku("NOPE") == []


def test_download_asset_streams_to_path(mocker, tmp_path):
    fake_sdk = mocker.Mock()
    client = BynderClient(sdk=fake_sdk)

    fake_resp = mocker.Mock()
    fake_resp.iter_content.return_value = [b"\x89PNG", b"\x00\x00"]
    fake_resp.raise_for_status = mocker.Mock()
    mocker.patch("src.core.bynder_client.requests.get", return_value=fake_resp)

    asset = BynderAsset(
        asset_id="a",
        filename="x.png",
        original_url="https://example/x.png",
        sku="PGR-001",
        extension="png",
    )
    dest = tmp_path / "x.png"
    client.download_asset(asset, dest)
    assert dest.read_bytes() == b"\x89PNG\x00\x00"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_bynder_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.bynder_client'`.

- [ ] **Step 4: Write implementation**

Create `src/core/bynder_client.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import requests


@dataclass(frozen=True)
class BynderAsset:
    asset_id: str
    filename: str
    original_url: str
    sku: str | None
    extension: str


class BynderClient:
    """Thin wrapper around the bynder-sdk. Accepts an injected SDK for testability."""

    def __init__(self, sdk: Any):
        self._sdk = sdk

    @classmethod
    def from_permanent_token(cls, domain: str, token: str) -> "BynderClient":
        from bynder_sdk import BynderClient as SDK
        sdk = SDK(domain=domain, permanent_token=token)
        return cls(sdk=sdk)

    def search_by_sku(self, sku: str) -> list[BynderAsset]:
        """Query Bynder for all assets with metaproperty sku=<sku>.
        The exact metaproperty key is set in the Bynder portal; we pass it as
        a generic search and filter client-side for robustness."""
        raw = self._sdk.asset_bank_client.media_list({"propertyOptionId": sku})
        return [_to_asset(r) for r in raw if _matches_sku(r, sku)]

    def download_asset(self, asset: BynderAsset, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(asset.original_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)


def _matches_sku(raw: dict, sku: str) -> bool:
    if raw.get("property_sku") == sku:
        return True
    return False


def _to_asset(raw: dict) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower() or _ext_from_url(raw.get("original", ""))
    name = raw.get("name") or ""
    filename = name if name.lower().endswith(f".{ext}") else f"{name}.{ext}"
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=raw.get("property_sku"),
        extension=ext,
    )


def _ext_from_url(url: str) -> str:
    if "." not in url:
        return ""
    return url.rsplit(".", 1)[-1].split("?")[0].lower()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_bynder_client.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/bynder_client.py tests/test_bynder_client.py tests/fixtures/bynder_media_list.json
git commit -m "feat(core): add Bynder client with SKU search and streaming download"
```

---

## Task 9: Infographic Library Module

**Files:**
- Create: `src/core/infographic_library.py`
- Create: `tests/test_infographic_library.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_infographic_library.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_infographic_library.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.infographic_library'`.

- [ ] **Step 3: Write implementation**

Create `src/core/infographic_library.py`:

```python
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session

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
        line = self._session.get(ProductLine, inp.product_line_id)
        if line is None:
            raise ValueError(f"ProductLine {inp.product_line_id} not found")

        ext = Path(inp.filename).suffix.lstrip(".").lower() or "jpg"
        slug = _slug(line.name)
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
        self._session.add(row)
        self._session.commit()
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
        if path.exists():
            path.unlink()
        self._session.delete(row)
        self._session.commit()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_infographic_library.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/infographic_library.py tests/test_infographic_library.py
git commit -m "feat(core): add infographic library with file+DB persistence"
```

---

## Task 10: Streamlit App Shell

**Files:**
- Create: `src/ui/app.py`
- Create: `src/ui/components.py`

- [ ] **Step 1: Write shared components**

Create `src/ui/components.py`:

```python
import streamlit as st


def require_auth(username: str, password: str) -> bool:
    """Shared basic auth. Returns True when logged in; blocks rendering otherwise."""
    if st.session_state.get("authed"):
        return True

    st.title("Bynder Image Tool")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log in")
    if submit:
        if u == username and p == password:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    return False
```

- [ ] **Step 2: Write app entry**

Create `src/ui/app.py`:

```python
import streamlit as st

from src.config import load_config
from src.ui.components import require_auth


def main() -> None:
    st.set_page_config(
        page_title="Bynder Image Tool",
        page_icon="📦",
        layout="wide",
    )

    cfg = load_config()
    if not require_auth(cfg.streamlit_username, cfg.streamlit_password):
        return

    st.sidebar.title("Bynder Image Tool")
    tab = st.sidebar.radio(
        "Navigate",
        ["Mapping Wizard", "Package SKU", "Library"],
        key="nav",
    )

    if tab == "Mapping Wizard":
        from src.ui.wizard_tab import render as render_wizard
        render_wizard()
    elif tab == "Package SKU":
        from src.ui.package_tab import render as render_package
        render_package()
    else:
        from src.ui.library_tab import render as render_library
        render_library()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create stub tab modules so imports work**

Create `src/ui/wizard_tab.py`:

```python
import streamlit as st


def render() -> None:
    st.header("Mapping Wizard")
    st.info("Not yet implemented.")
```

Create `src/ui/package_tab.py`:

```python
import streamlit as st


def render() -> None:
    st.header("Package SKU")
    st.info("Not yet implemented.")
```

Create `src/ui/library_tab.py`:

```python
import streamlit as st


def render() -> None:
    st.header("Library")
    st.info("Not yet implemented.")
```

- [ ] **Step 4: Run the app to verify boot**

Run (from project root with `.env` configured):

```bash
streamlit run src/ui/app.py
```

Expected: Browser opens to `http://localhost:8501`. Login form appears. After login with env credentials, sidebar shows 3 tabs each rendering their "Not yet implemented" stub.

- [ ] **Step 5: Commit**

```bash
git add src/ui/
git commit -m "feat(ui): add Streamlit shell with auth and tab routing"
```

---

## Task 11: Wizard Tab — Step 1 (Filename Rules)

**Files:**
- Modify: `src/ui/wizard_tab.py`

- [ ] **Step 1: Rewrite `src/ui/wizard_tab.py` with Step 1 flow**

Replace contents of `src/ui/wizard_tab.py`:

```python
import streamlit as st

from src.core.mapping_engine import AMAZON_SLOTS, infer_regex, parse_filename
from src.core.product_catalog import ProductCatalog
from src.db.models import ProductLine, FilenamePattern, FilenameRule
from src.db.session import get_session
from src.config import load_config


def render() -> None:
    st.header("Mapping Wizard")

    cfg = load_config()
    session = get_session()
    catalog = ProductCatalog(xlsx_path=cfg.product_catalog_xlsx_path, supabase_client=None)

    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.subheader("Product lines")
        existing_names = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
        catalog_lines = catalog.list_product_lines()
        all_lines = sorted(set(existing_names) | set(catalog_lines))
        options = ["+ New product line"] + all_lines
        choice = st.radio("Select a line", options, key="wiz_line_choice")

        if choice == "+ New product line":
            new_name = st.text_input("New product line name")
            if st.button("Create") and new_name.strip():
                pl = ProductLine(name=new_name.strip())
                session.add(pl)
                session.commit()
                st.success(f"Created '{new_name}'. Select it from the list.")
                st.rerun()
            return

        pl = session.query(ProductLine).filter_by(name=choice).first()
        if pl is None:
            pl = ProductLine(name=choice)
            session.add(pl)
            session.commit()

    with col_right:
        st.subheader(f"Configure: {pl.name}")
        _render_step1(session, pl)


def _render_step1(session, pl: ProductLine) -> None:
    st.markdown("### Step 1: Filename rules")

    existing_pattern = (
        session.query(FilenamePattern).filter_by(product_line_id=pl.id).order_by(FilenamePattern.id.desc()).first()
    )
    default_samples = existing_pattern.sample_filename if existing_pattern else ""

    samples_raw = st.text_area(
        "Paste 3-5 example Bynder filenames (one per line)",
        value=default_samples,
        height=120,
        key=f"samples_{pl.id}",
    )
    samples = [s.strip() for s in samples_raw.splitlines() if s.strip()]

    if not samples:
        st.info("Paste filenames above to infer a regex.")
        return

    try:
        regex = infer_regex(samples)
    except ValueError as e:
        st.error(str(e))
        regex = existing_pattern.regex if existing_pattern else r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$"

    regex = st.text_input("Regex (edit if needed)", value=regex, key=f"regex_{pl.id}")

    labels = sorted({
        parse_filename(s, regex).position_label
        for s in samples
        if parse_filename(s, regex) is not None
    })

    if not labels:
        st.warning("Regex did not extract any labels from your samples.")
        return

    st.markdown("#### Map each position label to an Amazon slot")
    existing_rules = {
        r.position_label: r.amazon_slot
        for r in session.query(FilenameRule).filter_by(product_line_id=pl.id).all()
    }

    label_to_slot: dict[str, str] = {}
    for label in labels:
        default = existing_rules.get(label, "MAIN")
        label_to_slot[label] = st.selectbox(
            f"{label}",
            AMAZON_SLOTS,
            index=AMAZON_SLOTS.index(default) if default in AMAZON_SLOTS else 0,
            key=f"slot_{pl.id}_{label}",
        )

    if st.button("Save filename rules", key=f"save_rules_{pl.id}"):
        session.query(FilenamePattern).filter_by(product_line_id=pl.id).delete()
        session.add(FilenamePattern(
            product_line_id=pl.id,
            regex=regex,
            sample_filename="\n".join(samples),
        ))
        session.query(FilenameRule).filter_by(product_line_id=pl.id).delete()
        for label, slot in label_to_slot.items():
            session.add(FilenameRule(
                product_line_id=pl.id,
                position_label=label,
                amazon_slot=slot,
            ))
        session.commit()
        st.success("Filename rules saved.")
    st.session_state[f"wizard_pl_id"] = pl.id
```

- [ ] **Step 2: Manual verification**

Run: `streamlit run src/ui/app.py`

Steps:
1. Log in
2. Open "Mapping Wizard" tab
3. Select or create "PopGrip Standard"
4. Paste samples:
   ```
   PCS_Derpy-and-Sussie_IP14_01_Front.png
   PCS_Derpy-and-Sussie_IP14_02_Back.png
   PCS_Derpy-and-Sussie_IP14_03_Side.png
   ```
5. Verify regex is inferred; labels `Front`, `Back`, `Side` appear
6. Map Front→MAIN, Back→PT01, Side→PT02
7. Click "Save filename rules"
8. Verify in Postgres:
   ```bash
   docker compose exec postgres psql -U bynder_user -d bynder_tool -c "SELECT * FROM contentup_image_filename_rules;"
   ```
   Expected: 3 rows.

- [ ] **Step 3: Commit**

```bash
git add src/ui/wizard_tab.py
git commit -m "feat(ui): add wizard Step 1 filename-rule editor"
```

---

## Task 12: Wizard Tab — Step 2 (Infographic Upload)

**Files:**
- Modify: `src/ui/wizard_tab.py`

- [ ] **Step 1: Add Step 2 function to wizard_tab.py**

Append to `src/ui/wizard_tab.py` (before the final `return` of `_render_step1` won't work — restructure so both steps render sequentially).

Replace the body of `render()` to call both steps. The full updated file:

```python
import streamlit as st
from pathlib import Path

from src.core.mapping_engine import AMAZON_SLOTS, infer_regex, parse_filename
from src.core.product_catalog import ProductCatalog
from src.core.infographic_library import InfographicLibrary, InfographicInput
from src.db.models import ProductLine, FilenamePattern, FilenameRule, Infographic
from src.db.session import get_session
from src.config import load_config


def render() -> None:
    st.header("Mapping Wizard")
    cfg = load_config()
    session = get_session()
    catalog = ProductCatalog(xlsx_path=cfg.product_catalog_xlsx_path, supabase_client=None)
    lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.subheader("Product lines")
        existing_names = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
        catalog_lines = catalog.list_product_lines()
        all_lines = sorted(set(existing_names) | set(catalog_lines))
        options = ["+ New product line"] + all_lines
        choice = st.radio("Select a line", options, key="wiz_line_choice")

        if choice == "+ New product line":
            new_name = st.text_input("New product line name")
            if st.button("Create") and new_name.strip():
                session.add(ProductLine(name=new_name.strip()))
                session.commit()
                st.rerun()
            return

        pl = session.query(ProductLine).filter_by(name=choice).first()
        if pl is None:
            pl = ProductLine(name=choice)
            session.add(pl)
            session.commit()

    with col_right:
        st.subheader(f"Configure: {pl.name}")
        step = st.radio("Step", ["1. Filename rules", "2. Infographics", "3. Review"],
                        horizontal=True, key=f"step_{pl.id}")
        if step.startswith("1"):
            _render_step1(session, pl)
        elif step.startswith("2"):
            _render_step2(session, pl, lib, catalog)
        else:
            _render_step3(session, pl)


def _render_step1(session, pl: ProductLine) -> None:
    st.markdown("### Step 1: Filename rules")

    existing_pattern = (
        session.query(FilenamePattern).filter_by(product_line_id=pl.id).order_by(FilenamePattern.id.desc()).first()
    )
    default_samples = existing_pattern.sample_filename if existing_pattern else ""

    samples_raw = st.text_area(
        "Paste 3-5 example Bynder filenames (one per line)",
        value=default_samples,
        height=120,
        key=f"samples_{pl.id}",
    )
    samples = [s.strip() for s in samples_raw.splitlines() if s.strip()]
    if not samples:
        st.info("Paste filenames above to infer a regex.")
        return

    try:
        regex = infer_regex(samples)
    except ValueError as e:
        st.error(str(e))
        regex = existing_pattern.regex if existing_pattern else r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$"

    regex = st.text_input("Regex (edit if needed)", value=regex, key=f"regex_{pl.id}")

    labels = sorted({
        parse_filename(s, regex).position_label
        for s in samples
        if parse_filename(s, regex) is not None
    })

    if not labels:
        st.warning("Regex did not extract any labels from your samples.")
        return

    existing_rules = {
        r.position_label: r.amazon_slot
        for r in session.query(FilenameRule).filter_by(product_line_id=pl.id).all()
    }

    label_to_slot: dict[str, str] = {}
    st.markdown("#### Map each position label to an Amazon slot")
    for label in labels:
        default = existing_rules.get(label, "MAIN")
        label_to_slot[label] = st.selectbox(
            f"{label}",
            AMAZON_SLOTS,
            index=AMAZON_SLOTS.index(default) if default in AMAZON_SLOTS else 0,
            key=f"slot_{pl.id}_{label}",
        )

    if st.button("Save filename rules", key=f"save_rules_{pl.id}"):
        session.query(FilenamePattern).filter_by(product_line_id=pl.id).delete()
        session.add(FilenamePattern(
            product_line_id=pl.id,
            regex=regex,
            sample_filename="\n".join(samples),
        ))
        session.query(FilenameRule).filter_by(product_line_id=pl.id).delete()
        for label, slot in label_to_slot.items():
            session.add(FilenameRule(
                product_line_id=pl.id,
                position_label=label,
                amazon_slot=slot,
            ))
        session.commit()
        st.success("Filename rules saved.")


def _render_step2(session, pl: ProductLine, lib: InfographicLibrary, catalog: ProductCatalog) -> None:
    st.markdown("### Step 2: Infographics for this product line")

    tiers = catalog.list_tiers() or ["A", "B", "C"]

    with st.form(f"infographic_upload_{pl.id}", clear_on_submit=True):
        uploaded = st.file_uploader(
            "Upload infographic (JPEG or PNG)",
            type=["jpg", "jpeg", "png"],
        )
        tier = st.selectbox("Tier", tiers)
        slot = st.selectbox("Amazon slot", AMAZON_SLOTS)
        desc = st.text_input("Description (optional)")
        submit = st.form_submit_button("Save infographic")

        if submit:
            if uploaded is None:
                st.error("Pick a file to upload.")
            else:
                lib.save(InfographicInput(
                    product_line_id=pl.id,
                    tier=tier,
                    amazon_slot=slot,
                    filename=uploaded.name,
                    content=uploaded.getvalue(),
                    description=desc or None,
                ))
                st.success(f"Saved {uploaded.name} ({tier}, {slot})")

    st.markdown("#### Existing infographics for this line")
    rows = lib.list_by_product_line(pl.id)
    if not rows:
        st.info("No infographics uploaded yet.")
        return
    for r in rows:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(f"`{Path(r.file_path).name}` — {r.description or ''}")
        cols[1].write(r.tier)
        cols[2].write(r.amazon_slot)
        if cols[3].button("Delete", key=f"del_{r.id}"):
            lib.delete(r.id)
            st.rerun()


def _render_step3(session, pl: ProductLine) -> None:
    st.markdown("### Step 3: Review")
    rules = session.query(FilenameRule).filter_by(product_line_id=pl.id).order_by(FilenameRule.amazon_slot).all()
    infographics = session.query(Infographic).filter_by(product_line_id=pl.id).all()

    st.markdown("**Filename rules**")
    if rules:
        st.table([{"Label": r.position_label, "Slot": r.amazon_slot} for r in rules])
    else:
        st.warning("No filename rules defined.")

    st.markdown("**Infographic coverage**")
    if not infographics:
        st.warning("No infographics uploaded.")
        return

    tiers = sorted({ig.tier for ig in infographics})
    coverage = {t: {slot: 0 for slot in AMAZON_SLOTS} for t in tiers}
    for ig in infographics:
        coverage[ig.tier][ig.amazon_slot] += 1

    st.table([
        {"Tier": t, **{slot: coverage[t][slot] for slot in AMAZON_SLOTS}}
        for t in tiers
    ])
```

- [ ] **Step 2: Manual verification**

Run: `streamlit run src/ui/app.py`

Steps:
1. Navigate to Mapping Wizard → PopGrip Standard → Step 2
2. Upload a JPEG, pick Tier A + slot PT07, save
3. Verify success message
4. Check file exists: `ls infographics/popgrip-standard/A/`
5. Verify DB row:
   ```bash
   docker compose exec postgres psql -U bynder_user -d bynder_tool -c "SELECT tier, amazon_slot, file_path FROM contentup_image_infographics;"
   ```
6. Go to Step 3, verify coverage matrix shows 1 in (A, PT07)

- [ ] **Step 3: Commit**

```bash
git add src/ui/wizard_tab.py
git commit -m "feat(ui): add wizard Steps 2 (infographic upload) and 3 (review)"
```

---

## Task 13: Package SKU Tab — Fetch & Preview

**Files:**
- Modify: `src/ui/package_tab.py`
- Create: `src/ui/package_helpers.py`

- [ ] **Step 1: Write `package_helpers.py`**

Create `src/ui/package_helpers.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.bynder_client import BynderClient, BynderAsset
from src.core.mapping_engine import (
    AMAZON_SLOTS,
    ProductLineRules,
    assign_slots,
    ParsedAsset,
)
from src.core.infographic_library import InfographicLibrary
from src.db.models import ProductLine, FilenamePattern, FilenameRule, Infographic
from sqlalchemy.orm import Session


@dataclass
class SlotView:
    slot: str
    source: str   # 'bynder' | 'infographic' | 'empty' | 'override'
    filename: str | None
    asset_id: str | None  # Bynder asset id or infographic id as str
    local_path: str | None  # only for infographics / uploads


@dataclass
class PackageContext:
    sku: str
    product_line: ProductLine | None
    tier: str | None
    slot_views: dict[str, SlotView]
    unmapped_assets: list[ParsedAsset]
    bynder_assets: dict[str, BynderAsset]


def build_package_context(
    session: Session,
    sku: str,
    product_line: ProductLine,
    tier: str,
    bynder_client: BynderClient,
    infographic_lib: InfographicLibrary,
) -> PackageContext:
    assets = bynder_client.search_by_sku(sku)
    asset_map = {a.asset_id: a for a in assets}

    pattern_row = (
        session.query(FilenamePattern)
        .filter_by(product_line_id=product_line.id)
        .order_by(FilenamePattern.id.desc())
        .first()
    )
    rule_rows = session.query(FilenameRule).filter_by(product_line_id=product_line.id).all()

    slot_views: dict[str, SlotView] = {
        slot: SlotView(slot=slot, source="empty", filename=None, asset_id=None, local_path=None)
        for slot in AMAZON_SLOTS
    }

    unmapped: list[ParsedAsset] = []

    if pattern_row and rule_rows:
        rules = ProductLineRules(
            regex=pattern_row.regex,
            label_to_slot={r.position_label: r.amazon_slot for r in rule_rows},
        )
        raw_assets = [{"asset_id": a.asset_id, "filename": a.filename} for a in assets]
        result = assign_slots(raw_assets, rules)
        for slot, parsed in result.assigned.items():
            slot_views[slot] = SlotView(
                slot=slot,
                source="bynder",
                filename=parsed.filename,
                asset_id=parsed.asset_id,
                local_path=None,
            )
        unmapped = result.unmapped

    for slot, view in slot_views.items():
        if view.source != "empty":
            continue
        ig = infographic_lib.find_for_slot(product_line.id, tier, slot)
        if ig is not None:
            slot_views[slot] = SlotView(
                slot=slot,
                source="infographic",
                filename=Path(ig.file_path).name,
                asset_id=str(ig.id),
                local_path=ig.file_path,
            )

    return PackageContext(
        sku=sku,
        product_line=product_line,
        tier=tier,
        slot_views=slot_views,
        unmapped_assets=unmapped,
        bynder_assets=asset_map,
    )
```

- [ ] **Step 2: Rewrite `package_tab.py` with fetch + preview**

Replace contents of `src/ui/package_tab.py`:

```python
from pathlib import Path

import streamlit as st

from src.config import load_config
from src.core.bynder_client import BynderClient
from src.core.infographic_library import InfographicLibrary
from src.core.product_catalog import ProductCatalog
from src.db.models import ProductLine
from src.db.session import get_session
from src.ui.package_helpers import build_package_context


def render() -> None:
    st.header("Package SKU")

    cfg = load_config()
    session = get_session()
    catalog = ProductCatalog(xlsx_path=cfg.product_catalog_xlsx_path, supabase_client=None)
    infographic_lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    sku = st.text_input("SKU", key="pkg_sku").strip()
    if not sku:
        st.info("Enter a SKU to begin.")
        return

    info = catalog.lookup(sku)
    if info is None:
        st.warning(f"SKU '{sku}' not found in catalog. Pick product line + tier manually.")
        lines_in_db = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
        product_line_name = st.selectbox("Product line", lines_in_db, key="pkg_line_manual")
        tier = st.selectbox("Tier", catalog.list_tiers() or ["A", "B", "C"], key="pkg_tier_manual")
    else:
        st.success(f"Found: {info.description}")
        col1, col2 = st.columns(2)
        col1.metric("Product line", info.product_line or "—")
        col2.metric("Tier", info.tier or "—")
        product_line_name = info.product_line
        tier = info.tier

    if not product_line_name or not tier:
        st.error("Product line and tier must be set.")
        return

    pl = session.query(ProductLine).filter_by(name=product_line_name).first()
    if pl is None:
        st.error(f"No wizard config for '{product_line_name}'. Configure it in the Mapping Wizard first.")
        return

    if not st.button("Fetch Bynder assets", key="pkg_fetch"):
        return

    try:
        bynder = BynderClient.from_permanent_token(
            domain=cfg.bynder_domain,
            token=cfg.bynder_permanent_token,
        )
    except Exception as e:
        st.error(f"Bynder auth failed: {e}")
        return

    with st.spinner("Querying Bynder..."):
        ctx = build_package_context(
            session=session,
            sku=sku,
            product_line=pl,
            tier=tier,
            bynder_client=bynder,
            infographic_lib=infographic_lib,
        )

    st.session_state["pkg_ctx"] = ctx
    _render_preview(ctx)


def _render_preview(ctx) -> None:
    st.subheader("Preview")
    cols_per_row = 3
    slots = list(ctx.slot_views.keys())
    for i in range(0, len(slots), cols_per_row):
        row = st.columns(cols_per_row)
        for j, slot in enumerate(slots[i : i + cols_per_row]):
            view = ctx.slot_views[slot]
            with row[j]:
                st.markdown(f"**{slot}** — `{view.source}`")
                if view.filename:
                    st.caption(view.filename)
                else:
                    st.caption("_empty_")

    if ctx.unmapped_assets:
        st.markdown("#### Unmapped Bynder assets")
        for a in ctx.unmapped_assets:
            st.write(f"• `{a.filename}`")
```

- [ ] **Step 3: Manual verification**

Run: `streamlit run src/ui/app.py`

Steps:
1. Navigate to Package SKU tab
2. Enter a real SKU with Bynder assets tagged
3. Click "Fetch Bynder assets"
4. Verify 9 slot tiles render with source badges (`bynder` / `infographic` / `empty`)
5. Unmapped section lists filenames that did not match the regex

- [ ] **Step 4: Commit**

```bash
git add src/ui/package_tab.py src/ui/package_helpers.py
git commit -m "feat(ui): add package tab SKU fetch + 9-slot preview"
```

---

## Task 14: Package SKU Tab — Manual Override & Zip Export

**Files:**
- Modify: `src/ui/package_tab.py`

- [ ] **Step 1: Extend `_render_preview` to support overrides and a Package button**

Replace contents of `src/ui/package_tab.py`:

```python
from pathlib import Path
import io
import tempfile

import streamlit as st

from src.config import load_config
from src.core.amazon_packager import SlotFile, build_zip, validate_image
from src.core.bynder_client import BynderClient
from src.core.infographic_library import InfographicLibrary
from src.core.mapping_engine import AMAZON_SLOTS
from src.core.product_catalog import ProductCatalog
from src.db.models import ProductLine, PackageHistory, SkuOverride
from src.db.session import get_session
from src.ui.package_helpers import build_package_context, SlotView


def render() -> None:
    st.header("Package SKU")

    cfg = load_config()
    session = get_session()
    catalog = ProductCatalog(xlsx_path=cfg.product_catalog_xlsx_path, supabase_client=None)
    infographic_lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    sku = st.text_input("SKU", key="pkg_sku").strip()
    if not sku:
        st.info("Enter a SKU to begin.")
        return

    info = catalog.lookup(sku)
    if info is None:
        st.warning(f"SKU '{sku}' not found in catalog. Pick product line + tier manually.")
        lines_in_db = [pl.name for pl in session.query(ProductLine).order_by(ProductLine.name).all()]
        product_line_name = st.selectbox("Product line", lines_in_db, key="pkg_line_manual")
        tier = st.selectbox("Tier", catalog.list_tiers() or ["A", "B", "C"], key="pkg_tier_manual")
    else:
        st.success(f"Found: {info.description}")
        col1, col2 = st.columns(2)
        col1.metric("Product line", info.product_line or "—")
        col2.metric("Tier", info.tier or "—")
        product_line_name = info.product_line
        tier = info.tier

    if not product_line_name or not tier:
        st.error("Product line and tier must be set.")
        return

    pl = session.query(ProductLine).filter_by(name=product_line_name).first()
    if pl is None:
        st.error(f"No wizard config for '{product_line_name}'. Configure it in the Mapping Wizard first.")
        return

    if st.button("Fetch Bynder assets", key="pkg_fetch"):
        try:
            bynder = BynderClient.from_permanent_token(
                domain=cfg.bynder_domain,
                token=cfg.bynder_permanent_token,
            )
        except Exception as e:
            st.error(f"Bynder auth failed: {e}")
            return

        with st.spinner("Querying Bynder..."):
            ctx = build_package_context(
                session=session,
                sku=sku,
                product_line=pl,
                tier=tier,
                bynder_client=bynder,
                infographic_lib=infographic_lib,
            )
        st.session_state["pkg_ctx"] = ctx
        st.session_state["pkg_bynder_client"] = bynder

    ctx = st.session_state.get("pkg_ctx")
    if ctx is None:
        return

    _render_preview_and_overrides(session, ctx, infographic_lib)
    _render_package_button(session, ctx, st.session_state.get("pkg_bynder_client"))


def _render_preview_and_overrides(session, ctx, infographic_lib: InfographicLibrary) -> None:
    st.subheader("Preview")
    cols_per_row = 3
    slots = list(AMAZON_SLOTS)

    for i in range(0, len(slots), cols_per_row):
        row = st.columns(cols_per_row)
        for j, slot in enumerate(slots[i : i + cols_per_row]):
            view = ctx.slot_views[slot]
            with row[j]:
                st.markdown(f"**{slot}** — `{view.source}`")
                st.caption(view.filename or "_empty_")

                with st.expander("Override"):
                    uploaded = st.file_uploader(
                        f"Upload custom for {slot}",
                        type=["jpg", "jpeg", "png"],
                        key=f"ovr_{slot}",
                    )
                    if uploaded is not None and st.button(f"Save override {slot}", key=f"save_ovr_{slot}"):
                        dest = Path("overrides") / ctx.sku / f"{slot}{Path(uploaded.name).suffix}"
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(uploaded.getvalue())
                        session.query(SkuOverride).filter_by(sku=ctx.sku, amazon_slot=slot).delete()
                        session.add(SkuOverride(
                            sku=ctx.sku,
                            amazon_slot=slot,
                            source="upload",
                            uploaded_file_path=str(dest),
                        ))
                        session.commit()
                        ctx.slot_views[slot] = SlotView(
                            slot=slot,
                            source="override",
                            filename=dest.name,
                            asset_id=None,
                            local_path=str(dest),
                        )
                        st.success(f"Override saved for {slot}")

    if ctx.unmapped_assets:
        st.markdown("#### Unmapped Bynder assets")
        for a in ctx.unmapped_assets:
            assign_cols = st.columns([3, 1, 1])
            assign_cols[0].write(f"`{a.filename}`")
            target = assign_cols[1].selectbox(
                "Slot",
                AMAZON_SLOTS,
                key=f"unmap_slot_{a.asset_id}",
            )
            if assign_cols[2].button("Assign", key=f"unmap_btn_{a.asset_id}"):
                ba = ctx.bynder_assets[a.asset_id]
                ctx.slot_views[target] = SlotView(
                    slot=target,
                    source="bynder",
                    filename=ba.filename,
                    asset_id=ba.asset_id,
                    local_path=None,
                )
                st.success(f"Assigned to {target}")


def _render_package_button(session, ctx, bynder) -> None:
    st.divider()
    if not st.button("Package + Download", key="pkg_build", type="primary"):
        return

    slot_files: list[SlotFile] = []
    manifest: dict[str, dict] = {}

    for slot, view in ctx.slot_views.items():
        if view.source == "empty":
            continue

        if view.source == "bynder":
            asset = ctx.bynder_assets[view.asset_id]
            tmp = Path(tempfile.gettempdir()) / f"{ctx.sku}_{slot}.{asset.extension}"
            bynder.download_asset(asset, tmp)
            content = tmp.read_bytes()
            ext = asset.extension or Path(asset.filename).suffix.lstrip(".")
        else:
            content = Path(view.local_path).read_bytes()
            ext = Path(view.local_path).suffix.lstrip(".") or "jpg"

        result = validate_image(content, view.filename or slot)
        if not result.ok:
            st.error(f"{slot} validation failed: {'; '.join(result.errors)}")
            return
        for w in result.warnings:
            st.warning(f"{slot}: {w}")

        slot_files.append(SlotFile(amazon_slot=slot, content=content, extension=ext))
        manifest[slot] = {
            "source": view.source,
            "filename": view.filename,
            "asset_id": view.asset_id,
        }

    if not slot_files:
        st.error("No files to package.")
        return

    zip_bytes = build_zip(sku=ctx.sku, slots=slot_files)

    history = PackageHistory(
        sku=ctx.sku,
        packaged_by=st.session_state.get("user", "admin"),
        slot_manifest=manifest,
        zip_filename=f"{ctx.sku}_images.zip",
    )
    session.add(history)
    session.commit()

    st.download_button(
        label="Download zip",
        data=zip_bytes,
        file_name=f"{ctx.sku}_images.zip",
        mime="application/zip",
    )
```

- [ ] **Step 2: Manual verification**

1. Fetch a SKU in the Package tab
2. Upload a custom override for one slot
3. Assign one "Unmapped" asset to a specific slot
4. Click "Package + Download"
5. Verify:
   - Zip downloads with correct filenames
   - `contentup_image_package_history` has a new row:
     ```bash
     docker compose exec postgres psql -U bynder_user -d bynder_tool -c "SELECT sku, slot_manifest FROM contentup_image_package_history ORDER BY id DESC LIMIT 1;"
     ```
   - Opening the zip shows `<SKU>.MAIN.<ext>`, `<SKU>.PT01.<ext>`, etc.

- [ ] **Step 3: Commit**

```bash
git add src/ui/package_tab.py
git commit -m "feat(ui): add override, unmapped-assign, and zip packaging to package tab"
```

---

## Task 15: Library Tab

**Files:**
- Modify: `src/ui/library_tab.py`

- [ ] **Step 1: Implement library tab**

Replace contents of `src/ui/library_tab.py`:

```python
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.core.infographic_library import InfographicLibrary
from src.core.mapping_engine import AMAZON_SLOTS
from src.db.models import ProductLine
from src.db.session import get_session


def render() -> None:
    st.header("Infographic Library")
    cfg = load_config()
    session = get_session()
    lib = InfographicLibrary(session=session, storage_dir=Path(cfg.infographics_dir))

    lines = session.query(ProductLine).order_by(ProductLine.name).all()
    line_names = ["All"] + [pl.name for pl in lines]
    filter_line = st.selectbox("Product line", line_names)
    filter_slot = st.selectbox("Slot", ["All"] + list(AMAZON_SLOTS))
    filter_tier = st.text_input("Tier filter (exact match, blank = all)")

    if filter_line == "All":
        rows = lib.list_all()
    else:
        pl = next(pl for pl in lines if pl.name == filter_line)
        rows = lib.list_by_product_line(pl.id)

    if filter_slot != "All":
        rows = [r for r in rows if r.amazon_slot == filter_slot]
    if filter_tier.strip():
        rows = [r for r in rows if r.tier == filter_tier.strip()]

    if not rows:
        st.info("No infographics match these filters.")
        return

    for r in rows:
        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].write(f"`{Path(r.file_path).name}`")
        cols[1].write(r.tier)
        cols[2].write(r.amazon_slot)
        cols[3].write(r.description or "")
        if cols[4].button("Delete", key=f"lib_del_{r.id}"):
            lib.delete(r.id)
            st.rerun()
```

- [ ] **Step 2: Manual verification**

1. Navigate to Library tab
2. Apply filters, verify subset
3. Delete an item, verify row + file gone

- [ ] **Step 3: Commit**

```bash
git add src/ui/library_tab.py
git commit -m "feat(ui): implement library tab with filters + delete"
```

---

## Task 16: Dockerfile + Deployment Readiness

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `docker-compose.yml` (verify app service builds)

- [ ] **Step 1: Write `.dockerignore`**

Create `.dockerignore`:

```
.venv/
venv/
.git/
.gitignore
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
tests/
docs/
.env
*.zip
.vscode/
.idea/
```

- [ ] **Step 2: Write `Dockerfile`**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY alembic.ini .

RUN mkdir -p /app/infographics /app/data

EXPOSE 8501

CMD ["sh", "-c", "alembic upgrade head && streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"]
```

- [ ] **Step 3: Build and run**

```bash
docker compose up --build -d
```

Wait ~30s, then:

```bash
docker compose ps
curl -sI http://localhost:8501/
```

Expected: `HTTP/1.1 200 OK` (Streamlit serves its HTML shell).

- [ ] **Step 4: Verify migrations auto-applied on container start**

```bash
docker compose exec postgres psql -U bynder_user -d bynder_tool -c "\dt"
```

Expected: 6 `contentup_image_*` tables present.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat(deploy): add Dockerfile with alembic-on-start + streamlit server"
```

---

## Task 17: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Create `README.md`:

```markdown
# Bynder Image Tool

Streamlit app that pulls product images from Bynder by SKU, maps them to Amazon
image slots via per-product-line filename rules, splices reusable infographics,
and exports rename-ready zip packages for Amazon upload.

## Quickstart (local)

```bash
cp .env.example .env
# edit .env: set BYNDER_PERMANENT_TOKEN, STREAMLIT_PASSWORD at minimum

docker compose up --build -d
```

Open http://localhost:8501

## Development

```bash
python -m venv .venv
source .venv/Scripts/activate  # or .venv/bin/activate on *nix
pip install -r requirements.txt

docker compose up -d postgres   # just the database
alembic upgrade head

streamlit run src/ui/app.py
```

## Tests

```bash
pytest tests/ -v --cov=src
```

## Architecture

- `src/core/` — framework-agnostic business logic. Ports to `popsockets-content-manager` in Phase 2.
- `src/db/` — SQLAlchemy models + Alembic migrations. Tables use `contentup_image_` prefix.
- `src/ui/` — Streamlit tabs. Discarded when we port to content_manager's React frontend.

## Workflow

1. **Mapping Wizard** (per product line, once)
   - Step 1: Paste sample filenames → regex → position → Amazon slot map
   - Step 2: Upload infographics tagged by tier + slot
   - Step 3: Review coverage

2. **Package SKU** (per SKU, daily)
   - Enter SKU
   - Tool fetches from Bynder + applies rules + splices infographics
   - Manual overrides per slot if needed
   - Click Package → renamed zip downloads

3. **Library** — browse/delete infographics across all lines.

## Deployment (Coolify/Vultr)

- Point Coolify at this repo
- Set env vars: `DATABASE_URL` (Supabase), `BYNDER_PERMANENT_TOKEN`, `STREAMLIT_USERNAME`, `STREAMLIT_PASSWORD`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Mount persistent volume at `/app/infographics`
- Expose port 8501 behind Coolify's reverse proxy

## Phase 2 migration to popsockets-content-manager

See `docs/superpowers/specs/2026-04-20-bynder-image-tool-design.md` section 16.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quickstart, dev, and deployment instructions"
```

---

## Task 18: Final Coverage Check

**Files:** none (verification-only task)

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest tests/ -v --cov=src/core --cov=src/db --cov-report=term-missing
```

Expected:
- All tests pass
- `src/core/` coverage ≥ 80%
- `src/db/` coverage ≥ 70% (models are mostly declarative)

- [ ] **Step 2: Fix any gaps**

For any file < 80% coverage in `src/core/`, add tests targeting the uncovered lines. UI modules (`src/ui/`) are excluded — they're validated manually.

- [ ] **Step 3: Commit coverage fixes if any**

```bash
git add tests/
git commit -m "test: raise coverage on core modules to ≥80%"
```

- [ ] **Step 4: Final sanity run**

```bash
docker compose down
docker compose up --build -d
sleep 20
curl -sI http://localhost:8501/
docker compose exec postgres psql -U bynder_user -d bynder_tool -c "\dt"
```

Expected: Clean rebuild, app responds, tables present.

---

## Done Criteria

- [ ] All 18 tasks complete
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Coverage ≥ 80% on `src/core/`
- [ ] `docker compose up` produces a working Streamlit at `localhost:8501`
- [ ] End-to-end smoke: configure one product line in Wizard → package one real SKU → download zip → unzip → verify filenames match `<SKU>.<SLOT>.<ext>` convention
- [ ] `git log` shows atomic commits per task (roughly 18 commits)
