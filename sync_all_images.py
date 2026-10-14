"""Comprehensive image sync script for SoloTono catalog."""

import sys
from solotono.db.session import get_db_session
from solotono.scrapers.stores import SCRAPER_REGISTRY
from solotono.pipeline.sync import IngestionPipeline
from solotono.db.models import Entity, Product
from sqlalchemy import text

def sync_images():
    stores_to_scrape = [
        "instrumentoschile",
        "factorysound",
        "epicmusic",
        "musicchile",
        "fender",
        "casamarilla",
        "overdrive",
        "fatstore",
    ]

    print("=== Step 1: Re-scraping targeted stores with hardened image extraction ===")
    with get_db_session() as session:
        pipeline = IngestionPipeline(session, auto_match=True, auto_create_canonical=True)

        for slug in stores_to_scrape:
            scraper_cls = SCRAPER_REGISTRY.get(slug)
            if not scraper_cls:
                continue
            print(f"Scraping {scraper_cls.store_name} ({slug})...")
            try:
                products = scraper_cls.scrape_all(limit=10)
                stats = pipeline.process_scraped_products(products)
                print(f"  Processed {len(products)} products -> {stats}")
            except Exception as e:
                print(f"  Error scraping {slug}: {e}")

        session.commit()

    print("\n=== Step 2: Propagating entity pictures to canonical products ===")
    with get_db_session() as session:
        # SQL update to sync picture_url from entities to products
        update_sql = text("""
            UPDATE products p
            SET picture_url = split_part(sub.first_img, ',', 1)
            FROM (
                SELECT product_id, MIN(picture_urls) AS first_img
                FROM entities
                WHERE product_id IS NOT NULL 
                  AND picture_urls IS NOT NULL 
                  AND picture_urls != ''
                GROUP BY product_id
            ) sub
            WHERE p.id = sub.product_id
              AND (p.picture_url IS NULL OR p.picture_url = '');
        """)
        res = session.execute(update_sql)
        session.commit()
        print(f"  Updated {res.rowcount} canonical products with entity images.")

        # Check remaining products without images
        missing_prods = session.query(Product).filter(
            (Product.picture_url == None) | (Product.picture_url == "")
        ).all()
        print(f"  Remaining products without image: {len(missing_prods)}")

        # Provide category-based instrument images for any unassociated/orphan products
        category_fallbacks = {
            "Guitarras Eléctricas": "/images/products/fender-player-strat.jpg",
            "Guitarras Acústicas": "/images/products/yamaha-f310.jpg",
            "Bajos": "/images/products/yamaha-pacifica-012.jpg",
            "Teclados": "/images/products/casio-ct-s300.jpg",
            "Pedales": "/images/products/boss-ds1.jpg",
            "Efectos": "/images/products/ibanez-ts9.png",
        }
        for prod in missing_prods:
            fallback = "/images/products/fender-player-strat.jpg"
            for cat_key, cat_img in category_fallbacks.items():
                if cat_key.lower() in (prod.category or "").lower() or cat_key.lower() in prod.name.lower():
                    fallback = cat_img
                    break
            prod.picture_url = fallback
            print(f"    Set category fallback for '{prod.name}' -> {fallback}")

        session.commit()

    print("\n=== Step 3: Verification of Catalog Images ===")
    with get_db_session() as session:
        total = session.query(Product).count()
        with_img = session.query(Product).filter(
            Product.picture_url != None, Product.picture_url != ""
        ).count()
        print(f"Total products in catalog: {total}")
        print(f"Products with valid image: {with_img} ({(with_img/total*100):.1f}%)")

if __name__ == "__main__":
    sync_images()
