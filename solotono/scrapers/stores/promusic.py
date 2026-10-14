"""ProMusic store scraper (Shopify)."""

from solotono.scrapers.stores.shopify_base import ShopifyBaseStore


class PromusicScraper(ShopifyBaseStore):
    store_slug = "promusic"
    store_name = "ProMusic"
    website_url = "https://promusic.cl"
