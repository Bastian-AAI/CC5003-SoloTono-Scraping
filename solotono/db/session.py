"""Database session and initialization utilities."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from solotono.config import DATABASE_URL
from solotono.db.models import Base, Store

# Connection URL normalization and args
db_url = DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif db_url.startswith("postgresql://"):
    try:
        import psycopg2
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    except ImportError:
        pass

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


STORE_DEFINITIONS = [
    {
        "name": "Audiomusica",
        "slug": "audiomusica",
        "website_url": "https://www.audiomusica.com",
        "scraper_class": "AudiomusicaScraper",
        "engine_type": "VTEX",
    },
    {
        "name": "ProMusic",
        "slug": "promusic",
        "website_url": "https://promusic.cl",
        "scraper_class": "PromusicScraper",
        "engine_type": "Shopify",
    },
    {
        "name": "RD Músico",
        "slug": "rdmusico",
        "website_url": "https://rdmusico.cl",
        "scraper_class": "RdMusicoScraper",
        "engine_type": "Shopify",
    },
    {
        "name": "Fat Store",
        "slug": "fatstore",
        "website_url": "https://fatstore.cl",
        "scraper_class": "FatStoreScraper",
        "engine_type": "Shopify",
    },
    {
        "name": "Fender Chile",
        "slug": "fender",
        "website_url": "https://fender.cl",
        "scraper_class": "FenderChileScraper",
        "engine_type": "Magento",
    },
    {
        "name": "Casa Amarilla",
        "slug": "casamarilla",
        "website_url": "https://casamarilla.cl",
        "scraper_class": "CasaAmarillaScraper",
        "engine_type": "Magento",
    },
    {
        "name": "Music Chile",
        "slug": "musicchile",
        "website_url": "https://musicchile.cl",
        "scraper_class": "MusicChileScraper",
        "engine_type": "Magento",
    },
    {
        "name": "Instrumentos Chile",
        "slug": "instrumentoschile",
        "website_url": "https://instrumentoschile.cl",
        "scraper_class": "InstrumentosChileScraper",
        "engine_type": "Magento",
    },
    {
        "name": "Epic Music",
        "slug": "epicmusic",
        "website_url": "https://epicmusic.cl",
        "scraper_class": "EpicMusicScraper",
        "engine_type": "Magento",
    },
    {
        "name": "Factory Sound",
        "slug": "factorysound",
        "website_url": "https://factorysound.cl",
        "scraper_class": "FactorySoundScraper",
        "engine_type": "Prestashop",
    },
    {
        "name": "Overdrive",
        "slug": "overdrive",
        "website_url": "https://overdrive.cl",
        "scraper_class": "OverdriveScraper",
        "engine_type": "WooCommerce",
    },
]


def init_db(prepopulate_stores: bool = True, prepopulate_taxonomy: bool = True, drop_first: bool = False):
    """Create all tables and optionally seed store and taxonomy definitions."""
    if drop_first:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with get_db_session() as session:
        if prepopulate_stores:
            for s_def in STORE_DEFINITIONS:
                existing = session.query(Store).filter_by(slug=s_def["slug"]).first()
                if not existing:
                    store = Store(
                        name=s_def["name"],
                        slug=s_def["slug"],
                        website_url=s_def["website_url"],
                        scraper_class=s_def["scraper_class"],
                        engine_type=s_def["engine_type"],
                    )
                    session.add(store)

        if prepopulate_taxonomy:
            from solotono.db.fixtures import seed_taxonomy
            seed_taxonomy(session)

