"""Tests for SoloTono database models and active_registry pointer."""

from datetime import datetime
from decimal import Decimal
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solotono.db.models import Base, Store, Product, Entity, EntityHistory
from solotono.pipeline.sync import IngestionPipeline
from solotono.scrapers.base import ScrapedProduct


class TestDatabaseAndHistory(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Seed test store
        self.store = Store(
            name="Test Music",
            slug="testmusic",
            website_url="https://testmusic.cl",
            scraper_class="TestScraper",
            engine_type="Shopify",
        )
        self.session.add(self.store)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_entity_creation_and_active_registry(self):
        pipeline = IngestionPipeline(self.session, auto_match=True, auto_create_canonical=True)

        scraped = [
            ScrapedProduct(
                name="Fender Player Stratocaster MN Black",
                store_slug="testmusic",
                url="https://testmusic.cl/fender-player-strat-black",
                key="sku-12345",
                sku="0144502506",
                part_number="0144502506",
                brand="Fender",
                normal_price=Decimal("899990"),
                offer_price=Decimal("849990"),
                is_available=True,
            )
        ]

        stats = pipeline.process_scraped_products(scraped)
        self.assertEqual(stats["entities_created"], 1)
        self.assertEqual(stats["histories_created"], 1)

        ent = self.session.query(Entity).filter_by(key="sku-12345").first()
        self.assertIsNotNone(ent)
        self.assertIsNotNone(ent.active_registry_id)
        self.assertEqual(ent.active_registry.offer_price, Decimal("849990"))
        self.assertTrue(ent.is_associated)
        self.assertIsNotNone(ent.product_id)

    def test_delta_compression_skips_unchanged_prices(self):
        pipeline = IngestionPipeline(self.session, auto_match=True, auto_create_canonical=True)
        prod = ScrapedProduct(
            name="Boss DS-1 Distortion",
            store_slug="testmusic",
            url="https://testmusic.cl/boss-ds1",
            key="ds1-key",
            sku="DS-1",
            part_number="DS-1",
            brand="Boss",
            normal_price=Decimal("69990"),
            offer_price=Decimal("69990"),
            is_available=True,
        )

        # First run: should create 1 history
        s1 = pipeline.process_scraped_products([prod])
        self.assertEqual(s1["histories_created"], 1)

        # Second run with same price: should create 0 histories (delta compression)
        s2 = pipeline.process_scraped_products([prod])
        self.assertEqual(s2["histories_created"], 0)

        # Third run with price drop: should create 1 new history and update active_registry
        prod.offer_price = Decimal("59990")
        s3 = pipeline.process_scraped_products([prod])
        self.assertEqual(s3["histories_created"], 1)

        ent = self.session.query(Entity).filter_by(key="ds1-key").first()
        self.assertEqual(ent.active_registry.offer_price, Decimal("59990"))
        self.assertEqual(len(ent.histories), 2)


if __name__ == "__main__":
    unittest.main()
