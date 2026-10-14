"""Base scraper implementation for Jumpseller-based music stores."""

from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import json

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class JumpsellerBaseStore(BaseStore):
    """Reusable scraper for Jumpseller e-commerce platforms."""

    engine_type = "Jumpseller"
    category_paths: List[str] = []

    @classmethod
    def categories(cls) -> List[str]:
        return ["Guitarras", "Bajos", "Baterías", "Teclados", "Audio"]

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
                    cards = soup.select(".product-block a[href], .product-title a, article a[href], .product-item a[href]")
                    if not cards:
                        break

                    new_on_page = 0
                    for a in cards:
                        href = a.get("href")
                        if href and not href.startswith("http"):
                            href = urljoin(cls.website_url, href)
                        if href and href not in urls and not any(x in href for x in ["customer", "cart", "checkout"]):
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
            h1 = soup.select_one("h1")
            if not h1:
                return None
            name = h1.get_text().strip()

            normal_price = Decimal("0")
            offer_price = Decimal("0")
            is_avail = True
            key = url.rstrip("/").split("/")[-1]

            # Jumpseller injects clean JSON right into .product-price-json
            price_json_elem = soup.select_one(".product-price-json")
            if price_json_elem and price_json_elem.string:
                try:
                    pdata = json.loads(price_json_elem.string).get("info", {}).get("product", {})
                    regular = pdata.get("price", 0)
                    discount = pdata.get("discount", 0)
                    normal_price = cls.clean_price(regular)
                    offer_price = cls.clean_price(regular - discount if discount else regular)
                    is_avail = pdata.get("status") == "available"
                    if pdata.get("id"):
                        key = str(pdata.get("id"))
                except Exception:
                    pass

            if offer_price == 0:
                price_tag = soup.select_one(".product-block__price--new, .product-block__price, .price")
                if price_tag:
                    offer_price = cls.clean_price(price_tag.get_text())
                    normal_price = offer_price

            # Extract images (OG image, gallery, jumpseller CDN)
            imgs: List[str] = []
            og_img = soup.select_one("meta[property='og:image'], meta[name='og:image']")
            if og_img and og_img.get("content"):
                c = og_img["content"].strip()
                if c.startswith("http") and not any(x in c.lower() for x in ["cover/", "epic_32x32", "logo", "sin_t_tulo", "banner"]):
                    imgs.append(c)

            for img in soup.select(".product-gallery img, .product-images img, .carousel-item img, img.product-image, img.product-gallery__image, [data-zoom-image], a.product-gallery__link"):
                src = img.get("data-zoom-image") or img.get("href") or img.get("src") or img.get("data-src")
                if src:
                    full_src = urljoin(cls.website_url, src)
                    if full_src not in imgs and not any(x in full_src.lower() for x in ["thumb/84/", "thumb/80/", "thumb/45/", "logo", "icon", "cover/"]):
                        imgs.append(full_src)

            # Infer brand
            brand = cls.store_name
            for b in ["Fender", "Gibson", "Ibanez", "Yamaha", "Epiphone", "Cort", "Almansa", "Takamine", "Taylor", "Martin", "Boss", "Roland", "Shure", "Behringer", "Focusrite"]:
                if b.lower() in name.lower():
                    brand = b
                    break

            return ScrapedProduct(
                name=name,
                store_slug=cls.store_slug,
                url=url,
                key=key,
                sku=key,
                part_number=key,
                brand=brand,
                category="Instrumentos",
                normal_price=normal_price,
                offer_price=offer_price,
                currency="CLP",
                is_available=is_avail,
                picture_urls=imgs,
            )
        except Exception:
            return None
