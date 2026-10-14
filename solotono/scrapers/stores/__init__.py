"""Store scrapers registry and exports."""

from typing import Dict, Type
from solotono.scrapers.base import BaseStore
from solotono.scrapers.stores.audiomusica import AudiomusicaScraper
from solotono.scrapers.stores.promusic import PromusicScraper
from solotono.scrapers.stores.rdmusico import RdMusicoScraper
from solotono.scrapers.stores.fatstore import FatStoreScraper
from solotono.scrapers.stores.fender_chile import FenderChileScraper
from solotono.scrapers.stores.casamarilla import CasaAmarillaScraper
from solotono.scrapers.stores.musicchile import MusicChileScraper
from solotono.scrapers.stores.instrumentos_chile import InstrumentosChileScraper
from solotono.scrapers.stores.epicmusic import EpicMusicScraper
from solotono.scrapers.stores.factorysound import FactorySoundScraper
from solotono.scrapers.stores.overdrive import OverdriveScraper

SCRAPER_REGISTRY: Dict[str, Type[BaseStore]] = {
    "audiomusica": AudiomusicaScraper,
    "promusic": PromusicScraper,
    "rdmusico": RdMusicoScraper,
    "fatstore": FatStoreScraper,
    "fender": FenderChileScraper,
    "casamarilla": CasaAmarillaScraper,
    "musicchile": MusicChileScraper,
    "instrumentoschile": InstrumentosChileScraper,
    "epicmusic": EpicMusicScraper,
    "factorysound": FactorySoundScraper,
    "overdrive": OverdriveScraper,
}


def get_scraper_by_slug(slug: str) -> Type[BaseStore]:
    """Retrieve scraper class by store slug."""
    if slug not in SCRAPER_REGISTRY:
        raise ValueError(f"Unknown store slug '{slug}'. Available: {list(SCRAPER_REGISTRY.keys())}")
    return SCRAPER_REGISTRY[slug]
