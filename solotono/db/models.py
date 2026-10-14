"""SQLAlchemy database models for SoloTono, mirroring SoloTodo's Entity-Product-EntityHistory and Section-Category-Subcategory architecture."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Section(Base):
    """Represents a top-level website section (e.g. 'Categorías en Instrumentos', 'Equipos de Sonido', 'Piezas y Repuestos')."""

    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    ordering = Column(Integer, default=0, nullable=False)

    groups = relationship("CategoryGroup", back_populates="section", cascade="all, delete-orphan", order_by="CategoryGroup.ordering")

    def __repr__(self) -> str:
        return f"<Section {self.name} ({self.slug})>"


class CategoryGroup(Base):
    """Represents a column / family grouping within a section (e.g. 'Cuerda', 'Amplificación', 'Efectos')."""

    __tablename__ = "category_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    ordering = Column(Integer, default=0, nullable=False)

    section = relationship("Section", back_populates="groups")
    categories = relationship("Category", back_populates="group", cascade="all, delete-orphan", order_by="Category.ordering")

    def __repr__(self) -> str:
        return f"<CategoryGroup {self.name} ({self.slug})>"


class Category(Base):
    """Represents a canonical, spec-defining product category (mirroring SoloTodo's Category)."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("category_groups.id"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    ordering = Column(Integer, default=0, nullable=False)
    short_description_template = Column(Text, nullable=True)
    browse_result_template = Column(Text, nullable=True)
    detail_template = Column(Text, nullable=True)
    meta_tag_description = Column(Text, nullable=True)

    group = relationship("CategoryGroup", back_populates="categories")
    subcategories = relationship("Subcategory", back_populates="category", cascade="all, delete-orphan", order_by="Subcategory.ordering")
    products = relationship("Product", back_populates="category_obj")
    entities = relationship("Entity", back_populates="category_obj")

    def __repr__(self) -> str:
        return f"<Category {self.name} ({self.slug})>"


class Subcategory(Base):
    """Virtual view / parameterized facet on a Category (mirroring SoloTodo's Subcategory)."""

    __tablename__ = "subcategories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    params = Column(String(256), default="", nullable=False)  # e.g. "strings_min=7" or "technology=tubes"
    ordering = Column(Integer, default=0, nullable=False)
    meta_tag_description = Column(Text, nullable=True)

    category = relationship("Category", back_populates="subcategories")

    def __repr__(self) -> str:
        return f"<Subcategory {self.name} ({self.slug}): params='{self.params}'>"


class Store(Base):
    """Represents an e-commerce retail store (e.g. Audiomusica, Fender Chile, ProMusic)."""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    website_url = Column(String(256), nullable=False)
    scraper_class = Column(String(64), nullable=False)
    engine_type = Column(String(32), nullable=False)  # Shopify, VTEX, Magento, Prestashop, WooCommerce
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    entities = relationship("Entity", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Store {self.name} ({self.slug})>"


class Product(Base):
    """Represents a canonical, catalog-level product (e.g. 'Fender Player Stratocaster MN Black')."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    category = Column(String(128), nullable=True, index=True)  # Legacy string representation / quick access
    name = Column(String(256), nullable=False, index=True)
    brand = Column(String(128), nullable=False, index=True)
    family = Column(String(128), nullable=True)  # e.g. Stratocaster, Les Paul, SM58, Scarlett
    part_number = Column(String(64), nullable=True, index=True)  # Manufacturer Part Number (MPN)
    ean = Column(String(32), nullable=True, index=True)  # Barcode (EAN-13 / GTIN)
    description = Column(Text, nullable=True)
    picture_url = Column(String(512), nullable=True)
    specs_json = Column(Text, nullable=True)  # JSON-encoded technical specifications
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    category_obj = relationship("Category", back_populates="products")
    entities = relationship("Entity", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product {self.id}: {self.brand} {self.name}>"


class Entity(Base):
    """Represents a store-specific SKU listing (e.g. Product #910458 on Audiomusica).
    
    Mirrors SoloTodo's Entity model:
    - Many-to-one relationship with canonical Product.
    - O(1) active_registry pointer to the latest active EntityHistory record.
    - Unique constraint on (store_id, key).
    """

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)

    # Identifiers from store
    key = Column(String(256), nullable=False)  # Store internal unique product/variant key
    sku = Column(String(128), nullable=True)
    name = Column(String(256), nullable=False)  # Raw scraped title
    url = Column(String(512), nullable=False)
    brand = Column(String(128), nullable=True)
    category = Column(String(128), nullable=True)  # Raw category string from store
    part_number = Column(String(128), nullable=True, index=True)
    ean = Column(String(32), nullable=True, index=True)
    condition = Column(String(64), default="New", nullable=False)  # New, Used, Refurbished, OpenBox
    picture_urls = Column(Text, nullable=True)  # Comma-separated or JSON list of URLs

    # Status flags
    is_active = Column(Boolean, default=True, nullable=False)
    is_associated = Column(Boolean, default=False, nullable=False, index=True)

    # O(1) pointer to the latest active EntityHistory record (SoloTodo optimization)
    active_registry_id = Column(Integer, ForeignKey("entity_histories.id", use_alter=True, name="fk_active_registry"), nullable=True)

    # Timestamps
    creation_date = Column(DateTime, default=utc_now, nullable=False)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    last_pricing_update = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    store = relationship("Store", back_populates="entities")
    product = relationship("Product", back_populates="entities")
    category_obj = relationship("Category", back_populates="entities")
    histories = relationship("EntityHistory", foreign_keys="EntityHistory.entity_id", back_populates="entity", cascade="all, delete-orphan")
    active_registry = relationship("EntityHistory", foreign_keys=[active_registry_id], post_update=True)

    __table_args__ = (
        UniqueConstraint("store_id", "key", name="uix_store_key"),
        Index("idx_entity_association", "is_associated", "store_id"),
    )

    def __repr__(self) -> str:
        return f"<Entity {self.id}: {self.name} ({self.store_id})>"


class EntityHistory(Base):
    """Time-series record of price and stock availability for an Entity.
    
    Mirrors SoloTodo's EntityHistory:
    - Logged on every detected price or availability change.
    - Periodic baseline snapshot (e.g. daily) if unchanged.
    - Tracks Chilean dual pricing: normal_price (tarjeta/lista) and offer_price (efectivo/transferencia).
    """

    __tablename__ = "entity_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)

    is_available = Column(Boolean, default=True, nullable=False)
    normal_price = Column(Numeric(12, 2), nullable=False)  # Regular price / credit card price
    offer_price = Column(Numeric(12, 2), nullable=False)   # Cash / bank transfer price
    currency = Column(String(8), default="CLP", nullable=False)
    stock = Column(Integer, nullable=True)

    entity = relationship("Entity", foreign_keys=[entity_id], back_populates="histories")

    __table_args__ = (
        Index("idx_history_entity_time", "entity_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<EntityHistory {self.id}: Ent {self.entity_id} - Offer: ${self.offer_price} at {self.timestamp}>"
