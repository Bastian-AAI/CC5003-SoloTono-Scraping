"""Base scraper implementation for Shopify-based music stores."""

from decimal import Decimal
from typing import List, Optional
import html

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class ShopifyBaseStore(BaseStore):
    """Reusable scraper for Shopify stores using native /products.json API."""

    engine_type = "Shopify"

    @classmethod
    def categories(cls) -> List[str]:
        return [
            "Guitarras",
            "Bajos",
            "Baterías",
            "Teclados",
            "Audio Profesional",
            "Efectos y Pedales",
            "Amplificadores",
        ]

    @classmethod
    def discover_product_urls(cls, category: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        session = get_scraper_session()
        urls = []
        page = 1
        page_size = 50

        while True:
            api_url = f"{cls.website_url}/products.json"
            params = {"page": page, "limit": page_size}
            try:
                r = session.get(api_url, params=params, timeout=15)
                if r.status_code != 200:
                    break
                data = r.json()
                products = data.get("products", [])
                if not products:
                    break

                for p in products:
                    handle = p.get("handle")
                    if handle:
                        urls.append(f"{cls.website_url}/products/{handle}")
                        if limit and len(urls) >= limit:
                            return urls

                page += 1
            except Exception:
                break

        return urls

    @classmethod
    def scrape_product(cls, url: str) -> Optional[ScrapedProduct]:
        session = get_scraper_session()
        handle = url.rstrip("/").split("/")[-1]
        api_url = f"{cls.website_url}/products/{handle}.json"

        try:
            r = session.get(api_url, timeout=15)
            if r.status_code == 200:
                data = r.json().get("product", {})
                return cls._parse_shopify_product(data, url)
        except Exception:
            pass
        return None

    @classmethod
    def scrape_all(cls, limit: Optional[int] = None, category: Optional[str] = None) -> List[ScrapedProduct]:
        session = get_scraper_session()
        results: List[ScrapedProduct] = []
        page = 1
        page_size = min(limit or 250, 250)

        while True:
            api_url = f"{cls.website_url}/products.json"
            params = {"page": page, "limit": page_size}
            try:
                r = session.get(api_url, params=params, timeout=15)
                if r.status_code != 200:
                    break
                data = r.json()
                products = data.get("products", [])
                if not products:
                    break

                for p in products:
                    scraped = cls._parse_shopify_product(p)
                    if scraped:
                        results.append(scraped)
                        if limit and len(results) >= limit:
                            return results

                page += 1
            except Exception:
                break

        return results

    @classmethod
    def _parse_shopify_product(cls, p: dict, fallback_url: str = "") -> Optional[ScrapedProduct]:
        if not p:
            return None
        
        handle = p.get("handle", "")
        product_url = f"{cls.website_url}/products/{handle}" if handle else fallback_url
        title = html.unescape(p.get("title", ""))
        vendor = p.get("vendor", "")
        product_type = p.get("product_type", "Instrumentos")
        
        variants = p.get("variants", [])
        if not variants:
            return None
            
        first_variant = variants[0]
        variant_id = str(first_variant.get("id", p.get("id", "")))
        sku = first_variant.get("sku") or None
        barcode = first_variant.get("barcode") or None
        
        price = cls.clean_price(first_variant.get("price", "0"))
        compare_price = cls.clean_price(first_variant.get("compare_at_price", "0"))
        
        # Chilean dual pricing: normal price (lista) vs offer price
        normal_price = compare_price if compare_price > price else price
        offer_price = price

        is_available = first_variant.get("available", True)
        stock = 1 if is_available else 0

        images = [img.get("src") for img in p.get("images", []) if isinstance(img, dict) and img.get("src")]
        if not images and isinstance(p.get("image"), dict) and p["image"].get("src"):
            images = [p["image"]["src"]]
        elif not images and isinstance(p.get("image"), str) and p["image"].startswith("http"):
            images = [p["image"]]

        return ScrapedProduct(
            name=title,
            store_slug=cls.store_slug,
            url=product_url,
            key=variant_id,
            sku=sku,
            part_number=sku,
            ean=barcode,
            brand=vendor,
            category=product_type or "Instrumentos",
            normal_price=normal_price,
            offer_price=offer_price,
            currency="CLP",
            stock=stock,
            is_available=is_available,
            condition="New",
            picture_urls=images,
            description=html.unescape(p.get("body_html", "") or ""),
        )
