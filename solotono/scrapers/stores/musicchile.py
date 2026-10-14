"""Music Chile store scraper (Jumpseller platform)."""

from solotono.scrapers.stores.jumpseller_base import JumpsellerBaseStore


class MusicChileScraper(JumpsellerBaseStore):
    store_slug = "musicchile"
    store_name = "Music Chile"
    website_url = "https://musicchile.cl"
    category_paths = [
        "/cuerdas/guitarras/guitarras-acusticas",
        "/cuerdas/guitarras/guitarra-acustica-metal",
        "/cuerdas/guitarras/guitarras-electroacusticas",
        "/instrumentos-de-cuerda/guitarras/guitarras-electricas",
        "/cuerdas/bajos/bajos-electricos",
        "/cuerdas/bajos/bajos-electroacusticos-1",
        "/percusion/baterias-acusticas",
        "/teclados/sintetizadores",
    ]
