"""Unit tests for SoloTono's SoloTodo-style taxonomy models, fixtures, and classifier."""

import unittest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solotono.db.models import Base, Section, CategoryGroup, Category, Subcategory, Store, Entity
from solotono.db.fixtures import seed_taxonomy
from solotono.matching.taxonomy import classify_product
from solotono.pipeline.sync import IngestionPipeline
from solotono.scrapers.base import ScrapedProduct


class TestTaxonomy(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()

    def test_seed_taxonomy_creates_full_menu(self):
        stats = seed_taxonomy(self.session)
        self.assertEqual(stats["sections"], 3)
        self.assertEqual(stats["groups"], 12)
        self.assertGreaterEqual(stats["categories"], 38)
        self.assertGreaterEqual(stats["subcategories"], 15)

        # Verify sections
        instrumentos = self.session.query(Section).filter(Section.slug == "instrumentos").first()
        self.assertIsNotNone(instrumentos)
        self.assertEqual(instrumentos.name, "Categorías en Instrumentos")
        self.assertEqual(len(instrumentos.groups), 4)

        equipos = self.session.query(Section).filter(Section.slug == "equipos-de-sonido").first()
        self.assertIsNotNone(equipos)
        self.assertEqual(len(equipos.groups), 4)

        repuestos = self.session.query(Section).filter(Section.slug == "piezas-y-repuestos").first()
        self.assertIsNotNone(repuestos)
        self.assertEqual(len(repuestos.groups), 4)

    def test_category_and_subcategory_views(self):
        seed_taxonomy(self.session)

        # Check Guitarras Electricas
        cat = self.session.query(Category).filter(Category.slug == "guitarras-electricas").first()
        self.assertIsNotNone(cat)
        self.assertIsNotNone(cat.browse_result_template)
        subcat_names = [s.name for s in cat.subcategories]
        self.assertIn("7 o más cuerdas", subcat_names)
        self.assertIn("Stratocaster", subcat_names)
        self.assertIn("Les Paul / Singlecut", subcat_names)

        # Check subcategory params
        sub_7 = self.session.query(Subcategory).filter(Subcategory.slug == "guitarras-electricas-7-cuerdas").first()
        self.assertIn("strings_min=7", sub_7.params)

    def test_taxonomic_classifier_rules(self):
        seed_taxonomy(self.session)

        # 1. Stratocaster
        res = classify_product("Fender Player II Stratocaster Rosewood Polar White", session=self.session)
        self.assertEqual(res.category_slug, "guitarras-electricas")
        self.assertGreaterEqual(res.confidence, 0.90)
        self.assertIn("Stratocaster", res.suggested_subcategories)

        # 2. 7-string guitar
        res = classify_product("Ibanez RG7421 Standard 7 Cuerdas Walnut Flat", session=self.session)
        self.assertEqual(res.category_slug, "guitarras-electricas")
        self.assertIn("7 o más cuerdas", res.suggested_subcategories)

        # 3. Tube amp
        res = classify_product("Fender Blues Junior IV 15W 1x12 Tube Amp Valvular", session=self.session)
        self.assertEqual(res.category_slug, "amplificadores-de-guitarra")
        self.assertIn("Valvulares (Tubes)", res.suggested_subcategories)

        # 4. Distortion pedal
        res = classify_product("Boss DS-1 Distortion Pedal Naranja", session=self.session)
        self.assertEqual(res.category_slug, "pedales-de-efectos")

        # 5. Audio interface
        res = classify_product("Focusrite Scarlett 2i2 4th Gen USB Audio Interface", session=self.session)
        self.assertEqual(res.category_slug, "interfaces-de-audio")

        # 6. Studio mic
        res = classify_product("Shure SM7B Microfono Dinamico Vocal para Estudio", session=self.session)
        self.assertEqual(res.category_slug, "microfonos-de-estudio")

        # 7. Strings
        res = classify_product("Ernie Ball Regular Slinky 2221 Cuerdas para Guitarra", session=self.session)
        self.assertEqual(res.category_slug, "cuerdas-guitarra-y-bajo")

    def test_pipeline_assigns_category_id(self):
        seed_taxonomy(self.session)

        store = Store(
            name="Audiomusica",
            slug="audiomusica",
            website_url="https://www.audiomusica.com",
            scraper_class="AudiomusicaScraper",
            engine_type="VTEX",
        )
        self.session.add(store)
        self.session.commit()

        scraped = [
            ScrapedProduct(
                name="Fender Player Stratocaster Electric Guitar",
                store_slug="audiomusica",
                url="https://www.audiomusica.com/p/123",
                key="AM-123",
                normal_price=Decimal("849900"),
                offer_price=Decimal("799900"),
                category="Guitarras y Bajos/Guitarras Eléctricas",
            )
        ]

        pipeline = IngestionPipeline(self.session, auto_match=False)
        stats = pipeline.process_scraped_products(scraped)
        self.assertEqual(stats["entities_created"], 1)

        entity = self.session.query(Entity).filter(Entity.key == "AM-123").first()
        self.assertIsNotNone(entity.category_id)
        self.assertEqual(entity.category_obj.slug, "guitarras-electricas")


if __name__ == "__main__":
    unittest.main()
