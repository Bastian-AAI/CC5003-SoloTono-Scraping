"""Fat Store scraper (Shopify)."""

from solotono.scrapers.stores.shopify_base import ShopifyBaseStore


class FatStoreScraper(ShopifyBaseStore):
    store_slug = "fatstore"
    store_name = "Fat Store"
    website_url = "https://fatstore.cl"
