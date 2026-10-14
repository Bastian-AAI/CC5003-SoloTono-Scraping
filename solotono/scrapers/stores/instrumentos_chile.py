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
            page = 1
            while True:
                cat_url = urljoin(cls.website_url, f"{path}?page={page}") if page > 1 else urljoin(cls.website_url, path)
                try:
                    r = session.get(cat_url, timeout=15)
                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, "html.parser")
                    links = soup.select("a[href*='/product/']")
                    if not links:
                        break

                    new_on_page = 0
                    for a in links:
                        href = urljoin(cls.website_url, a["href"])
                        if href not in urls:
                            urls.append(href)
                            new_on_page += 1
                            if limit and len(urls) >= limit:
                                return urls

                    if new_on_page == 0 or (limit and len(urls) >= limit):
                        break
                    page += 1
                except Exception:
                    break

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

            # Extract images (og:image, gallery, product images)
            imgs = []
            og_img = soup.select_one("meta[property='og:image'], meta[name='og:image']")
            if og_img and og_img.get("content"):
                c = og_img["content"].strip()
                if c.startswith("http") and not any(x in c.lower() for x in ["logo", "icon", "banner"]):
                    imgs.append(c)

            for img in soup.select(".bs-product-gallery img, .product-images img, img[src*='/product/']"):
                src = img.get("src") or img.get("data-src")
                if src:
                    full_src = urljoin(cls.website_url, src)
                    if full_src not in imgs and not any(x in full_src.lower() for x in ["logo", "icon", "placeholder"]):
                        imgs.append(full_src)

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
                picture_urls=imgs,
            )
        except Exception:
            return None
