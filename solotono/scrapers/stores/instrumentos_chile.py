"""Instrumentos Chile store scraper (Bsale platform with sitemap discovery)."""

from decimal import Decimal
import logging
from typing import List, Optional
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session

logger = logging.getLogger(__name__)


class InstrumentosChileScraper(BaseStore):
    store_slug = "instrumentoschile"
    store_name = "Instrumentos Chile"
    website_url = "https://instrumentoschile.cl"
    engine_type = "Bsale"

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

        # 1. Primary discovery: parse Bsale XML sitemap
        try:
            sitemap_url = urljoin(cls.website_url, "/sitemap.xml")
            r = session.get(sitemap_url, timeout=25)
            if r.status_code == 200 and r.content:
                root = ET.fromstring(r.content)
                for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    u = (loc.text or "").strip()
                    if u and "/product/" in u:
                        if u not in urls:
                            urls.append(u)
                            if limit and len(urls) >= limit:
                                return urls
        except Exception as e:
            logger.warning(f"Error fetching Instrumentos Chile sitemap: {e}")

        if urls:
            return urls

        # 2. Secondary fallback: crawl category collections
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
            if not name:
                return None

            price_tag = soup.select_one(".bs-product__final-price, .price, .product-price, [data-price]")
            price = cls.clean_price(price_tag.get_text()) if price_tag else Decimal("0")
            if price <= 0:
                return None

            # Extract SKU from URL or DOM
            key = url.rstrip("/").split("/")[-1]
            sku = None
            if "sku-" in key:
                sku = key.split("sku-")[-1]

            # Extract brand from Bsale brand markup, or infer from title
            brand = cls.store_name
            brand_el = soup.select_one(".bs-product-brand a, .product-brand a")
            if brand_el:
                brand_cand = brand_el.get("title") or brand_el.get_text().strip()
                if not brand_cand and brand_el.find("img"):
                    brand_cand = brand_el.find("img").get("alt") or brand_el.find("img").get("title")
                if brand_cand:
                    brand = brand_cand.strip()

            if brand == cls.store_name:
                for b in ["Fender", "Gibson", "Ibanez", "Yamaha", "Epiphone", "Cort", "Tagima", "Roland", "Boss", "Marshall", "Takamine", "Taylor", "Martin", "Casio", "Hohner", "Mollenhauer"]:
                    if b.lower() in name.lower():
                        brand = b
                        break

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
                brand=brand,
                category="Guitarras y Bajos",
                normal_price=price,
                offer_price=price,
                currency="CLP",
                is_available=True,
                picture_urls=imgs,
            )
        except Exception:
            return None
