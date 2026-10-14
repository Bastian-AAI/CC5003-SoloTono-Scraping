"""SoloTono: Motor de Scraping, Product Matching e Historial de Precios para Instrumentos Musicales en Chile."""

from solotono.db.models import Product, Entity, EntityHistory, Store
from solotono.db.session import init_db, get_db_session
from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.stores import SCRAPER_REGISTRY, get_scraper_by_slug
from solotono.matching.matcher import ProductMatcher, MatchResult
from solotono.pipeline.sync import IngestionPipeline

__version__ = "1.0.0"

__all__ = [
    "Product",
    "Entity",
    "EntityHistory",
    "Store",
    "init_db",
    "get_db_session",
    "BaseStore",
    "ScrapedProduct",
    "SCRAPER_REGISTRY",
    "get_scraper_by_slug",
    "ProductMatcher",
    "MatchResult",
    "IngestionPipeline",
]
