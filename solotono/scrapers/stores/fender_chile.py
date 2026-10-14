"""Fender Chile store scraper (Magento platform)."""

from solotono.scrapers.stores.magento_base import MagentoBaseStore


class FenderChileScraper(MagentoBaseStore):
    store_slug = "fender"
    store_name = "Fender Chile"
    website_url = "https://www.fender.cl"
    category_paths = [
        "/guitarras-electricas/fender/stratocaster.html",
        "/guitarras-electricas/fender/telecaster.html",
        "/guitarras-acusticas.html",
        "/bajos-electricos.html",
        "/amplificadores.html",
    ]
