"""Factory Sound store scraper (Prestashop platform)."""

from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class FactorySoundScraper(BaseStore):
    store_slug = "factorysound"
    store_name = "Factory Sound"
    website_url = "https://factorysound.cl"
    engine_type = "Prestashop"

    category_paths = [
        "/54-guitarras-instrumento-musical",
        "/233-guitarras-electricas",
        "/11-bajos",
        "/12-baterias-y-percusion",
        "/13-teclados-y-pianos",
        "/14-audio-profesional",
    ]

    @classmethod
    def categories(cls) -> List[str]:
        return [
            "Guitarras",
            "Bajos",
            "Baterías",
            "Teclados",
            "Audio",
        ]

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
                # Prestashop 1.7 / 8 product card selectors
                cards = soup.select(".product-miniature a.product-thumbnail, .product-title a, article.product-miniature a[href]")
                for a in cards:
                    href = a.get("href")
                    if href and href.startswith("http") and href not in urls:
                        if any(x in href for x in ["order", "cart", "controller"]):
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

            # Try JSON-LD first
            json_ld = cls.parse_json_ld(soup)
            if json_ld:
                name = json_ld.get("name", "")
                sku = json_ld.get("sku")
                offers = json_ld.get("offers", {})
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                price = cls.clean_price(offers.get("price", "0")) if isinstance(offers, dict) else Decimal("0")
                if name and price > 0:
                    return ScrapedProduct(
                        name=name,
                        store_slug=cls.store_slug,
                        url=url,
                        key=sku or url.split("/")[-1].replace(".html", ""),
                        sku=sku,
                        part_number=sku,
                        brand="Factory Sound",
                        category="Instrumentos",
                        normal_price=price,
                        offer_price=price,
                        currency="CLP",
                        stock=1,
                        is_available=True,
                    )

            # Fallback to DOM
            h1 = soup.select_one("h1[itemprop='name'], h1.h1, .product-detail-name")
            if not h1:
                return None
            name = h1.get_text().strip()

            price_tag = soup.select_one(".current-price span[content], .current-price-value, span[itemprop='price'], .product-price")
            raw_price = price_tag.get("content") or price_tag.get_text() if price_tag else "0"
            price = cls.clean_price(raw_price)

            ref_tag = soup.select_one(".product-reference span, span[itemprop='sku']")
            sku = ref_tag.get_text().strip() if ref_tag else None

            images = [img["src"] for img in soup.select(".product-cover img, .js-qv-product-cover") if img.get("src")]

            return ScrapedProduct(
                name=name,
                store_slug=cls.store_slug,
                url=url,
                key=sku or url.split("/")[-1],
                sku=sku,
                part_number=sku,
                brand="Factory Sound",
                category="Instrumentos",
                normal_price=price,
                offer_price=price,
                currency="CLP",
                stock=1,
                is_available=price > 0,
                picture_urls=images,
            )
        except Exception:
            return None
