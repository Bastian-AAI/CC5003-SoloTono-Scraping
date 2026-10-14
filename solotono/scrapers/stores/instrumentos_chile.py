"""Instrumentos Chile store scraper."""

from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class InstrumentosChileScraper(BaseStore):
    store_slug = "instrumentoschile"
    store_name = "Instrumentos Chile"
    website_url = "https://instrumentoschile.cl"
    engine_type = "Magento"

    category_paths = [
        "/collection/guitarra-electrica",
        "/collection/guitarra-acustica",
        "/collection/guitarra-electroacustica",
        "/collection/bajos",
        "/collection/amplificadores",
    ]

    @classmethod
    def categories(cls) -> List[str]:
        return ["Guitarras", "Bajos", "Amplificadores"]

    @classmethod
    def discover_product_urls(cls, category: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        session = get_scraper_session()
        urls: List[str] = []

        for path in cls.category_paths:
            cat_url = urljoin(cls.website_url, path)
            try:
                r = session.get(cat_url, timeout=15)
                if r.status_code != 200:
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a[href*='/product/']"):
                    href = urljoin(cls.website_url, a["href"])
                    if href not in urls:
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
            h1 = soup.select_one("h1, .product-title, .title")
            if not h1:
                return None
            name = h1.get_text().strip()

            price_tag = soup.select_one(".bs-product__final-price, .price, .product-price, [data-price]")
            price = cls.clean_price(price_tag.get_text()) if price_tag else Decimal("0")

            # Extract SKU from URL or DOM
            key = url.rstrip("/").split("/")[-1]
            sku = None
            if "sku-" in key:
                sku = key.split("sku-")[-1]

            return ScrapedProduct(
                name=name,
                store_slug=cls.store_slug,
                url=url,
                key=key,
                sku=sku,
                part_number=sku,
                brand="Instrumentos Chile",
                category="Guitarras y Bajos",
                normal_price=price,
                offer_price=price,
                currency="CLP",
                is_available=price > 0,
            )
        except Exception:
            return None
