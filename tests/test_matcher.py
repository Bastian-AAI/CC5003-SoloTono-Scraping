"""Unit and integration tests for SoloTono matching engine and spec normalizer."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solotono.db.models import Base, Store, Product, Entity
from solotono.matching.matcher import ProductMatcher
from solotono.matching.normalizer import (
    analyze_product_string,
    clean_canonical_name,
    extract_finish,
    extract_series_tokens,
    extract_year_markers,
    extract_fretboard_wood,
    extract_pickup_config,
    extract_size_spec,
    extract_model_codes,
)


class TestProductMatcherAndNormalizer(unittest.TestCase):

    def test_series_extraction_and_conflict(self):
        v57 = "Fender American Vintage II 1957 Stratocaster, Maple Fingerboard, 2-Color Sunburst"
        u2 = "Fender American Ultra II Stratocaster, Maple Fingerboard, Sinister Red"
        
        s_v57 = extract_series_tokens(v57)
        s_u2 = extract_series_tokens(u2)
        
        self.assertIn("vintage", s_v57)
        self.assertIn("ultra", s_u2)
        self.assertEqual(len(s_v57.intersection(s_u2)), 0)

    def test_year_extraction_and_conflict(self):
        v57 = "Fender American Vintage II 1957 Stratocaster"
        u2 = "Fender American Ultra II Stratocaster"
        v60 = "Fender American Vintage II 1960 Stratocaster"
        
        y_v57 = extract_year_markers(v57)
        y_u2 = extract_year_markers(u2)
        y_v60 = extract_year_markers(v60)
        
        self.assertEqual(y_v57, {"1957"})
        self.assertEqual(y_u2, set())
        self.assertEqual(y_v60, {"1960"})
        self.assertNotEqual(y_v57, y_u2)
        self.assertNotEqual(y_v57, y_v60)

    def test_finish_extraction_and_aliases(self):
        t1 = "Fender Stratocaster American Ultra II MN SRD"
        t2 = "Fender American Ultra II Stratocaster Sinister Red"
        t3 = "Fender American Ultra II Stratocaster Solar Flare"
        
        _, f1 = extract_finish(t1)
        _, f2 = extract_finish(t2)
        _, f3 = extract_finish(t3)
        
        self.assertEqual(f1, "Sinister Red")
        self.assertEqual(f2, "Sinister Red")
        self.assertEqual(f3, "Solar Flare")
        self.assertEqual(f1, f2)
        self.assertNotEqual(f1, f3)

    def test_model_code_conflict(self):
        # M50X vs M20X -> conflict
        c_m50 = extract_model_codes("Audio-Technica ATH-M50X")
        c_m20 = extract_model_codes("Audio-Technica ATH-M20X")
        self.assertTrue(bool(c_m50 and c_m20 and not c_m50.intersection(c_m20)))

        # UM2 vs UMC22 -> conflict
        c_um2 = extract_model_codes("Behringer U-Phoria UM2")
        c_umc22 = extract_model_codes("Behringer U-Phoria UMC22")
        self.assertTrue(bool(c_um2 and c_umc22 and not c_um2.intersection(c_umc22)))

        # CT-S400 vs CT-S100 -> conflict
        c_s400 = extract_model_codes("Casio CT-S400")
        c_s100 = extract_model_codes("Casio CT-S100")
        self.assertTrue(bool(c_s400 and c_s100 and not c_s400.intersection(c_s100)))

        # XS-1 vs XS-1 -> match
        c_xs1_a = extract_model_codes("Sennheiser XS-1 Micrófono Dinámico Vocal")
        c_xs1_b = extract_model_codes("Sennheiser XS-1 Micrófono Dinámico Vocal Cardioide")
        self.assertTrue(bool(c_xs1_a and c_xs1_b and c_xs1_a.intersection(c_xs1_b)))

    def test_fretboard_wood_conflict(self):
        w_maple = extract_fretboard_wood("Fender Stratocaster American Professional II Miami Blue Maple")
        w_rosewood = extract_fretboard_wood("Fender Stratocaster American Professional II Miami Blue Rosewood")
        self.assertEqual(w_maple, "Maple")
        self.assertEqual(w_rosewood, "Rosewood")
        self.assertNotEqual(w_maple, w_rosewood)

    def test_pickup_config_conflict(self):
        pu_hss = extract_pickup_config("Fender Player II Stratocaster HSS Aged Cherry Burst")
        pu_sss = extract_pickup_config("Fender Player II Stratocaster SSS Aged Cherry Burst")
        self.assertEqual(pu_hss, "HSS")
        self.assertEqual(pu_sss, "SSS")
        self.assertNotEqual(pu_hss, pu_sss)

    def test_size_spec_conflict(self):
        s_violin_75 = extract_size_spec("Cremona SV-75 3/4")
        s_violin_50 = extract_size_spec("Cremona SV-50 4/4")
        self.assertEqual(s_violin_75, "3/4")
        self.assertEqual(s_violin_50, "4/4")
        self.assertNotEqual(s_violin_75, s_violin_50)

        s_spk_8 = extract_size_spec('Wharfedale EZ-8A 8" Bluetooth')
        s_spk_6 = extract_size_spec('Wharfedale EZ-6A 6.5" Bluetooth')
        self.assertEqual(s_spk_8, '8"')
        self.assertEqual(s_spk_6, '6.5"')
        self.assertNotEqual(s_spk_8, s_spk_6)

    def test_store_exclusivity_and_cross_store_matching(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        s1 = Store(name="Fender Chile", slug="fender", website_url="https://fender.cl", scraper_class="FenderChileScraper", engine_type="Magento")
        s2 = Store(name="Audiomusica", slug="audiomusica", website_url="https://audiomusica.com", scraper_class="AudiomusicaScraper", engine_type="VTEX")
        db.add_all([s1, s2])
        db.commit()

        matcher = ProductMatcher(db)

        # 1. Store 1 adds guitar (Miami Blue Maple)
        e1 = Entity(store_id=s1.id, key="e1", name="Fender Stratocaster American Professional II Miami Blue Maple", brand="Fender", url="http://fender.cl/e1")
        db.add(e1)
        db.commit()
        res1 = matcher.match_entity(e1, auto_create_canonical=True)
        db.commit()
        self.assertEqual(res1.match_strategy, "created_new")
        prod1_id = res1.matched_product_id

        # 2. Store 1 adds a second guitar (Miami Blue Rosewood). Store 1 MUST NOT match its own Product 1!
        e2 = Entity(store_id=s1.id, key="e2", name="Fender Stratocaster American Professional II Miami Blue Rosewood", brand="Fender", url="http://fender.cl/e2")
        db.add(e2)
        db.commit()
        res2 = matcher.match_entity(e2, auto_create_canonical=True)
        db.commit()
        self.assertEqual(res2.match_strategy, "created_new")
        self.assertNotEqual(res2.matched_product_id, prod1_id, "Store 1 must not match against its own product")

        # 3. Store 2 adds the exact same guitar as E1. Store 2 MUST match Product 1 across stores!
        e3 = Entity(store_id=s2.id, key="e3", name="Guitarra Fender Stratocaster American Professional II Miami Blue Maple", brand="Fender", url="http://audiomusica.com/e3")
        db.add(e3)
        db.commit()
        res3 = matcher.match_entity(e3, auto_create_canonical=True)
        db.commit()
        self.assertEqual(res3.matched_product_id, prod1_id, "Store 2 must match Store 1 product across stores")
        self.assertEqual(res3.match_strategy, "fuzzy_token")


if __name__ == "__main__":
    unittest.main()
