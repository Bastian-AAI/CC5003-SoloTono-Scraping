"""RD Músico store scraper (Shopify)."""

from solotono.scrapers.stores.shopify_base import ShopifyBaseStore


class RdMusicoScraper(ShopifyBaseStore):
    store_slug = "rdmusico"
    store_name = "RD Músico"
    website_url = "https://rdmusico.cl"
