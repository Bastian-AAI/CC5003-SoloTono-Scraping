"""Audiomusica store scraper (VTEX platform)."""

from decimal import Decimal
from typing import List, Optional
import requests

from solotono.scrapers.base import BaseStore, ScrapedProduct
from solotono.scrapers.session import get_scraper_session


class AudiomusicaScraper(BaseStore):
    store_slug = "audiomusica"
    store_name = "Audiomusica"
    website_url = "https://www.audiomusica.com"
    engine_type = "VTEX"

    @classmethod
    def categories(cls) -> List[str]:
        return [
            "Guitarras y Bajos",
            "Baterías y Percusión",
            "Teclados y Pianos",
            "Audio Profesional",
            "Amplificadores y Efectos",
        ]

    @classmethod
    def discover_product_urls(cls, category: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        """Discovers product URLs from Audiomusica's VTEX Search API."""
        session = get_scraper_session()
        urls = []
        page_size = min(limit or 50, 50)
        
        # VTEX search endpoint
        api_url = f"{cls.website_url}/api/catalog_system/pub/products/search"
        params = {"_from": 0, "_to": page_size - 1}
        if category:
            params["ft"] = category

        try:
            r = session.get(api_url, params=params, timeout=15)
            if r.status_code in (200, 206):
                data = r.json()
                for item in data:
                    link = item.get("link")
                    if link:
                        urls.append(link)
                        if limit and len(urls) >= limit:
                            break
        except Exception:
            pass

        return urls

    @classmethod
    def scrape_product(cls, url: str) -> Optional[ScrapedProduct]:
        """Scrapes product using VTEX product search by URL path."""
        session = get_scraper_session()
        
        # VTEX allows searching by slug / linkText
        slug = url.rstrip("/").split("/")[-1].replace(".html", "")
        api_url = f"{cls.website_url}/api/catalog_system/pub/products/search/{slug}/p"
        
        try:
            r = session.get(api_url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list):
                    item = data[0]
                    name = item.get("productName", "")
                    brand = item.get("brand", "")
                    cat_tree = item.get("categories", ["Instrumentos"])
                    category = cat_tree[0].strip("/") if cat_tree else "Instrumentos"
                    
                    # Extract from first SKU variation
                    skus = item.get("items", [])
                    if not skus:
                        return None
                    
                    sku_data = skus[0]
                    sku_id = str(sku_data.get("itemId", ""))
                    ean = sku_data.get("ean") or None
                    
                    # Extract reference ID / MPN
                    part_no = None
                    ref_ids = sku_data.get("referenceId", [])
                    if ref_ids and isinstance(ref_ids, list):
                        part_no = ref_ids[0].get("Value")

                    # Extract price & availability from sellers
                    sellers = sku_data.get("sellers", [])
                    normal_price = Decimal("0")
                    offer_price = Decimal("0")
                    is_available = False
                    stock = 0

                    if sellers:
                        comm = sellers[0].get("commertialOffer", {})
                        price = comm.get("Price", 0)
                        list_price = comm.get("ListPrice", price)
                        stock = comm.get("AvailableQuantity", 0)
                        is_available = stock > 0
                        
                        normal_price = cls.clean_price(list_price if list_price > price else price)
                        offer_price = cls.clean_price(price)

                    pictures = [img.get("imageUrl") for img in sku_data.get("images", []) if img.get("imageUrl")]

                    return ScrapedProduct(
                        name=name,
                        store_slug=cls.store_slug,
                        url=item.get("link", url),
                        key=sku_id or slug,
                        sku=sku_id,
                        part_number=part_no,
                        ean=ean,
                        brand=brand,
                        category=category,
                        normal_price=normal_price,
                        offer_price=offer_price,
                        currency="CLP",
                        stock=stock,
                        is_available=is_available,
                        condition="New",
                        picture_urls=pictures,
                        description=item.get("description", ""),
                    )
        except Exception:
            pass
        return None

    @classmethod
    def scrape_all(cls, limit: Optional[int] = None, category: Optional[str] = None) -> List[ScrapedProduct]:
        """Fast bulk scraping directly via VTEX Catalog API."""
        session = get_scraper_session()
        products: List[ScrapedProduct] = []
        batch_size = min(limit or 50, 50)
        offset = 0

        while True:
            api_url = f"{cls.website_url}/api/catalog_system/pub/products/search"
            params = {"_from": offset, "_to": offset + batch_size - 1}
            if category:
                params["ft"] = category

            try:
                r = session.get(api_url, params=params, timeout=15)
                if r.status_code not in (200, 206):
                    break
                data = r.json()
                if not data:
                    break

                for item in data:
                    skus = item.get("items", [])
                    if not skus:
                        continue
                    sku_data = skus[0]
                    sku_id = str(sku_data.get("itemId", ""))
                    name = item.get("productName", "")
                    brand = item.get("brand", "")
                    cat_tree = item.get("categories", ["Instrumentos"])
                    cat_name = cat_tree[0].strip("/") if cat_tree else "Instrumentos"
                    
                    sellers = sku_data.get("sellers", [])
                    normal_price = Decimal("0")
                    offer_price = Decimal("0")
                    stock = 0
                    is_available = False
                    if sellers:
                        comm = sellers[0].get("commertialOffer", {})
                        price = comm.get("Price", 0)
                        list_price = comm.get("ListPrice", price)
                        stock = comm.get("AvailableQuantity", 0)
                        is_available = stock > 0
                        normal_price = cls.clean_price(list_price if list_price > price else price)
                        offer_price = cls.clean_price(price)

                    part_no = None
                    ref_ids = sku_data.get("referenceId", [])
                    if ref_ids and isinstance(ref_ids, list):
                        part_no = ref_ids[0].get("Value")

                    pictures = [img.get("imageUrl") for img in sku_data.get("images", []) if img.get("imageUrl")]

                    prod = ScrapedProduct(
                        name=name,
                        store_slug=cls.store_slug,
                        url=item.get("link", ""),
                        key=sku_id or item.get("linkText", name),
                        sku=sku_id,
                        part_number=part_no,
                        ean=sku_data.get("ean") or None,
                        brand=brand,
                        category=cat_name,
                        normal_price=normal_price,
                        offer_price=offer_price,
                        currency="CLP",
                        stock=stock,
                        is_available=is_available,
                        condition="New",
                        picture_urls=pictures,
                        description=item.get("description", ""),
                    )
                    products.append(prod)
                    if limit and len(products) >= limit:
                        return products

                offset += batch_size
                if limit and offset >= limit:
                    break
            except Exception:
                break

        return products
