"""Tests for Product Matching engine, normalizer, and pending queue."""

import unittest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solotono.db.models import Base, Entity, Product, Store
from solotono.matching.brands import detect_brand
from solotono.matching.normalizer import (
    analyze_product_string,
    extract_finish,
    normalize_title,
)
from solotono.matching.matcher import ProductMatcher


class TestProductMatching(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Seed a store
        self.store = Store(name="Audiomusica", slug="audiomusica", website_url="https://audiomusica.com", scraper_class="A", engine_type="VTEX")
        self.session.add(self.store)

        # Seed canonical products
        self.p1 = Product(
            name="Fender Player Stratocaster",
            brand="Fender",
            category="Guitarras",
            part_number="0144502500",
        )
        self.p2 = Product(
            name="Shure SM58 Micrófono Vocal",
            brand="Shure",
            category="Audio",
            part_number="SM58-LC",
        )
        self.session.add_all([self.p1, self.p2])
        self.session.commit()

        self.matcher = ProductMatcher(self.session, fuzzy_threshold=0.85)

    def tearDown(self):
        self.session.close()

    def test_brand_detection(self):
        self.assertEqual(detect_brand("Guitarra Eléctrica Ibanez RG350DXZ"), "Ibanez")
        self.assertEqual(detect_brand("Fender Stratocaster American Vintage"), "Fender")
        self.assertEqual(detect_brand("Interface Focusrite Scarlett 2i2 4th Gen"), "Focusrite")

    def test_finish_extraction(self):
        title1, finish1 = extract_finish("Fender Player Stratocaster 3-Color Sunburst")
        self.assertEqual(finish1, "3-Color Sunburst")
        self.assertNotIn("sunburst", title1.lower())

        title2, finish2 = extract_finish("Yamaha Pacifica 112V Black")
        self.assertEqual(finish2, "Black")

    def test_stage1_exact_mpn_match(self):
        ent = Entity(
            store_id=self.store.id,
            key="sku-sm58",
            name="Microfono Dinamico Shure SM58 para Voz",
            url="http://test.cl/sm58",
            brand="Shure",
            part_number="SM58-LC",
        )
        self.session.add(ent)
        self.session.commit()

        res = self.matcher.match_entity(ent)
        self.assertEqual(res.match_strategy, "exact_mpn")
        self.assertEqual(res.matched_product_id, self.p2.id)
        self.assertTrue(ent.is_associated)

    def test_stage2_fuzzy_token_match(self):
        # Slightly different phrasing without MPN
        ent = Entity(
            store_id=self.store.id,
            key="sku-fender-strat",
            name="Guitarra Eléctrica Fender Player Stratocaster Olympic White Nueva en Caja",
            url="http://test.cl/strat",
            brand="Fender",
        )
        self.session.add(ent)
        self.session.commit()

        res = self.matcher.match_entity(ent)
        self.assertEqual(res.match_strategy, "fuzzy_token")
        self.assertEqual(res.matched_product_id, self.p1.id)
        self.assertGreaterEqual(res.confidence, 0.85)
        self.assertTrue(ent.is_associated)

    def test_stage3_ambiguous_goes_to_pending(self):
        # Unrelated or unknown product
        ent = Entity(
            store_id=self.store.id,
            key="sku-unknown",
            name="Custom Handcrafted Luthier Guitar Prototype XYZ",
            url="http://test.cl/custom",
            brand="Custom",
        )
        self.session.add(ent)
        self.session.commit()

        res = self.matcher.match_entity(ent, auto_create_canonical=False)
        self.assertEqual(res.match_strategy, "pending_review")
        self.assertIsNone(res.matched_product_id)
        self.assertFalse(ent.is_associated)


if __name__ == "__main__":
    unittest.main()
