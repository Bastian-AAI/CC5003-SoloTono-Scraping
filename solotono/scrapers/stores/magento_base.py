"""Base scraper implementation for Magento 2-based music stores."""

from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class MagentoBaseStore(BaseStore):
    """Reusable scraper for Magento 2 e-commerce platforms."""

    engine_type = "Magento"
    category_paths: List[str] = []

    @classmethod
    def categories(cls) -> List[str]:
        return [
            "Guitarras",
            "Bajos",
            "Baterías",
            "Teclados",
            "Audio",
            "Amplificadores",
        ]

    @classmethod
    def discover_product_urls(cls, category: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        session = get_scraper_session()
        urls: List[str] = []
        paths_to_crawl = cls.category_paths

        for path in paths_to_crawl:
            cat_url = urljoin(cls.website_url, path)
            try:
                r = session.get(cat_url, timeout=15)
                if r.status_code != 200:
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                # Common Magento 1 and 2 product item selectors
                items = soup.select(".product-item-link, a.product.photo, .product-item a[href], h2.product-name a, .product-name a, a.product-image")
                for item in items:
                    href = item.get("href")
                    if href and href.startswith("http") and href not in urls:
                        # Avoid cart/checkout/wishlist links
                        if any(x in href for x in ["checkout", "cart", "customer", "wishlist", "#"]):
                            continue
                        urls.append(href)
                        if limit and len(urls) >= limit:
                            return urls
            except Exception:
                continue

        return urls

    @classmethod
    def scrape_product(cls, url: str) -> Optional[ScrapedProduct]:
        session = get_scraper_session()
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, "html.parser")
            
            # 1. Try JSON-LD first (standard in Magento 2)
            json_ld = cls.parse_json_ld(soup)
            if json_ld:
                name = json_ld.get("name", "")
                sku = json_ld.get("sku")
                brand_data = json_ld.get("brand", {})
                brand = brand_data.get("name") if isinstance(brand_data, dict) else str(brand_data)
                
                offers = json_ld.get("offers", {})
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                    
                price_val = offers.get("price", "0") if isinstance(offers, dict) else "0"
                avail = offers.get("availability", "") if isinstance(offers, dict) else ""
                is_avail = "InStock" in avail or not avail
                
                price = cls.clean_price(price_val)
                images = json_ld.get("image", [])
                if isinstance(images, str):
                    images = [images]

                if name and price > 0:
                    return ScrapedProduct(
                        name=name,
                        store_slug=cls.store_slug,
                        url=url,
                        key=sku or url.split("/")[-1].replace(".html", ""),
                        sku=sku,
                        part_number=sku,
                        ean=json_ld.get("gtin13") or json_ld.get("gtin") or None,
                        brand=brand or cls.store_name,
                        category="Instrumentos",
                        normal_price=price,
                        offer_price=price,
                        currency="CLP",
                        stock=1 if is_avail else 0,
                        is_available=is_avail,
                        condition="New",
                        picture_urls=images,
                        description=json_ld.get("description", ""),
                    )

            # 2. Fallback to HTML DOM parsing
            title_tag = soup.select_one("h1.page-title, .product-info-main h1, .product-name h1, h1")
            if not title_tag:
                return None
            name = title_tag.get_text().strip()

            # Prices
            price_tag = soup.select_one(".special-price .price, .price-box .price, [data-price-type='finalPrice'] .price, .regular-price .price")
            old_price_tag = soup.select_one(".old-price .price")
            
            price = cls.clean_price(price_tag.get_text()) if price_tag else Decimal("0")
            old_price = cls.clean_price(old_price_tag.get_text()) if old_price_tag else price
            
            normal_price = old_price if old_price > price else price
            offer_price = price

            # SKU
            sku_tag = soup.select_one(".product.attribute.sku .value, [itemprop='sku']")
            sku = sku_tag.get_text().strip() if sku_tag else None

            # Stock
            stock_tag = soup.select_one(".stock.available, .stock.unavailable")
            is_avail = True
            if stock_tag and "unavailable" in stock_tag.get("class", []):
                is_avail = False

            # Images
            imgs = [img["src"] for img in soup.select(".gallery-placeholder img, .fotorama__img") if img.get("src")]

            return ScrapedProduct(
                name=name,
                store_slug=cls.store_slug,
                url=url,
                key=sku or url.split("/")[-1].replace(".html", ""),
                sku=sku,
                part_number=sku,
                brand=cls.store_name,
                category="Instrumentos",
                normal_price=normal_price,
                offer_price=offer_price,
                currency="CLP",
                stock=1 if is_avail else 0,
                is_available=is_avail,
                condition="New",
                picture_urls=imgs,
            )
        except Exception:
            return None
