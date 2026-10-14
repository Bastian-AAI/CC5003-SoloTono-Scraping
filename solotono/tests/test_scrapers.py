"""Tests for scraper registry, data normalization, and BaseStore utilities."""

import unittest
from decimal import Decimal
from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.stores import SCRAPER_REGISTRY, get_scraper_by_slug


class TestScrapers(unittest.TestCase):
    def test_all_11_stores_registered(self):
        expected_slugs = {
            "audiomusica", "promusic", "rdmusico", "fatstore", "fender",
            "casamarilla", "musicchile", "instrumentoschile", "epicmusic",
            "factorysound", "overdrive"
        }
        self.assertEqual(set(SCRAPER_REGISTRY.keys()), expected_slugs)

    def test_clean_price(self):
        self.assertEqual(BaseStore.clean_price("$1.299.990"), Decimal("1299990"))
        self.assertEqual(BaseStore.clean_price("849900.00"), Decimal("849900"))
        self.assertEqual(BaseStore.clean_price(" 45.000 "), Decimal("45000"))
        self.assertEqual(BaseStore.clean_price(None), Decimal("0"))

    def test_scraped_product_validation(self):
        prod = ScrapedProduct(
            name="Ibanez RG550 Genesis",
            store_slug="promusic",
            url="https://promusic.cl/rg550",
            key="var-1",
            normal_price=Decimal("999990"),
            offer_price=Decimal("899990"),
        )
        self.assertEqual(prod.currency, "CLP")
        self.assertLessEqual(prod.offer_price, prod.normal_price)


if __name__ == "__main__":
    unittest.main()
