"""Data ingestion pipeline: maps ScrapedProduct into Entity, manages active_registry, and records EntityHistory."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from solotono.db.models import Entity, EntityHistory, Store
from solotono.scrapers.base import ScrapedProduct
from solotono.matching.matcher import ProductMatcher
from solotono.matching.taxonomy import classify_product


class IngestionPipeline:
    """Synchronizes scraped products into the database with delta history compression and active_registry."""

    def __init__(self, session: Session, auto_match: bool = True, auto_create_canonical: bool = False):
        self.session = session
        self.auto_match = auto_match
        self.auto_create_canonical = auto_create_canonical
        self.matcher = ProductMatcher(session)

    def process_scraped_products(self, products: List[ScrapedProduct]) -> Dict[str, int]:
        """Ingests a list of ScrapedProduct objects into Entity and EntityHistory."""
        stats = {
            "total_processed": len(products),
            "entities_created": 0,
            "entities_updated": 0,
            "histories_created": 0,
            "matched_entities": 0,
        }

        # Cache stores by slug
        stores_cache: Dict[str, Store] = {}

        for p in products:
            if p.store_slug not in stores_cache:
                store = self.session.query(Store).filter(Store.slug == p.store_slug).first()
                if not store:
                    # Auto-provision store if missing
                    store = Store(
                        name=p.store_slug.title(),
                        slug=p.store_slug,
                        website_url=f"https://{p.store_slug}.cl",
                        scraper_class=f"{p.store_slug.title()}Scraper",
                        engine_type="Generic",
                    )
                    self.session.add(store)
                    self.session.flush()
                stores_cache[p.store_slug] = store

            store = stores_cache[p.store_slug]

            # Look up Entity by (store_id, key)
            entity = (
                self.session.query(Entity)
                .filter(Entity.store_id == store.id, Entity.key == p.key)
                .first()
            )

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            is_new_entity = False

            # Classify into Canonical Category
            tax_res = classify_product(p.name, raw_category=p.category, brand=p.brand, session=self.session)

            if not entity:
                is_new_entity = True
                entity = Entity(
                    store_id=store.id,
                    key=p.key,
                    sku=p.sku,
                    name=p.name,
                    url=p.url,
                    brand=p.brand,
                    category=p.category,
                    category_id=tax_res.category_id,
                    part_number=p.part_number,
                    ean=p.ean,
                    condition=p.condition,
                    picture_urls=",".join(p.picture_urls) if p.picture_urls else None,
                    is_active=True,
                    is_associated=False,
                    creation_date=now,
                    last_updated=now,
                    last_pricing_update=now,
                )
                self.session.add(entity)
                self.session.flush()
                stats["entities_created"] += 1
            else:
                stats["entities_updated"] += 1
                # Update mutable store metadata
                entity.name = p.name
                entity.url = p.url
                if p.brand:
                    entity.brand = p.brand
                if p.category:
                    entity.category = p.category
                if tax_res.category_id:
                    entity.category_id = tax_res.category_id
                if p.part_number:
                    entity.part_number = p.part_number
                if p.ean:
                    entity.ean = p.ean
                if p.picture_urls:
                    entity.picture_urls = ",".join(p.picture_urls)
                entity.last_updated = now

            # Propagate picture to canonical product if missing
            if entity.product_id and entity.picture_urls:
                from solotono.db.models import Product
                prod = self.session.query(Product).filter(Product.id == entity.product_id).first()
                if prod and (not prod.picture_url or prod.picture_url.strip() == ""):
                    first_img = entity.picture_urls.split(",")[0].strip()
                    if first_img:
                        prod.picture_url = first_img

            # =========================================================================
            # Price History & active_registry Logic (SoloTodo Delta & Snapshot strategy)
            # =========================================================================
            active_hist = entity.active_registry
            record_history = False

            if active_hist is None:
                # First time seeing this entity or was previously out-of-stock
                record_history = True
            else:
                # 1. Did normal price or offer price change?
                price_changed = (
                    active_hist.normal_price != p.normal_price
                    or active_hist.offer_price != p.offer_price
                )
                # 2. Did availability change?
                availability_changed = active_hist.is_available != p.is_available
                # 3. Has more than 24 hours passed since the last price log (heartbeat)?
                heartbeat_due = (now - active_hist.timestamp) >= timedelta(hours=24)

                if price_changed or availability_changed or heartbeat_due:
                    record_history = True

            if record_history:
                new_hist = EntityHistory(
                    entity_id=entity.id,
                    timestamp=now,
                    is_available=p.is_available,
                    normal_price=p.normal_price,
                    offer_price=p.offer_price,
                    currency=p.currency,
                    stock=p.stock,
                )
                self.session.add(new_hist)
                self.session.flush()

                # Update active_registry pointer (O(1) current price lookup)
                if p.is_available:
                    entity.active_registry_id = new_hist.id
                else:
                    # If out of stock, active_registry pointer is cleared
                    entity.active_registry_id = None

                entity.last_pricing_update = now
                stats["histories_created"] += 1

            # =========================================================================
            # Product Matching
            # =========================================================================
            if self.auto_match and (not entity.is_associated or not entity.product_id):
                match_res = self.matcher.match_entity(entity, auto_create_canonical=self.auto_create_canonical)
                if match_res.matched_product_id:
                    stats["matched_entities"] += 1

        self.session.commit()
        return stats
