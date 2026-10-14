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
            page = 1
            while True:
                cat_url = urljoin(cls.website_url, f"{path}?page={page}") if page > 1 else urljoin(cls.website_url, path)
                try:
                    r = session.get(cat_url, timeout=15)
                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, "html.parser")
                    cards = soup.select(".product-miniature a.product-thumbnail, .product-title a, article.product-miniature a[href]")
                    if not cards:
                        break

                    new_on_page = 0
                    for a in cards:
                        href = a.get("href")
                        if href and href.startswith("http") and href not in urls:
                            if any(x in href for x in ["order", "cart", "controller"]):
                                continue
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

            # Extract images (og:image, JSON-LD, DOM)
            images: List[str] = []
            og_img = soup.select_one("meta[property='og:image'], meta[name='og:image']")
            if og_img and og_img.get("content"):
                c = og_img["content"].strip()
                if c.startswith("http") and not any(x in c.lower() for x in ["logo", "icon", "banner"]):
                    images.append(c)

            # Try JSON-LD first
            json_ld = cls.parse_json_ld(soup)
            if json_ld:
                name = json_ld.get("name", "")
                sku = json_ld.get("sku")
                offers = json_ld.get("offers", {})
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                price = cls.clean_price(offers.get("price", "0")) if isinstance(offers, dict) else Decimal("0")
                
                ld_img = json_ld.get("image")
                if isinstance(ld_img, str) and ld_img.startswith("http") and ld_img not in images:
                    images.append(ld_img)
                elif isinstance(ld_img, list):
                    for im in ld_img:
                        if isinstance(im, str) and im.startswith("http") and im not in images:
                            images.append(im)

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
                        picture_urls=images,
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

            for img in soup.select(".product-cover img, .js-qv-product-cover, img[src*='product_zoom'], img[src*='home_default']"):
                src = img.get("src") or img.get("data-src")
                if src:
                    full_src = urljoin(cls.website_url, src)
                    if full_src not in images and not any(x in full_src.lower() for x in ["logo", "icon"]):
                        images.append(full_src)

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
