"""Epic Music store scraper (Jumpseller platform)."""

from solotono.scrapers.stores.jumpseller_base import JumpsellerBaseStore


class EpicMusicScraper(JumpsellerBaseStore):
    store_slug = "epicmusic"
    store_name = "Epic Music"
    website_url = "https://epicmusic.cl"
    category_paths = [
        "/guitarras/electricas",
        "/guitarras/acusticas",
        "/guitarras/electroacusticas",
        "/bajos/bajos-electricos",
        "/bajos/acusticos-electroacusticos",
        "/percusion-y-baterias",
    ]
