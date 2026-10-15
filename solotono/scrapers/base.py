"""Base classes and data models for store scrapers, mirroring SoloTodo's storescraper."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional
import json


@dataclass
class ScrapedProduct:
    """Normalized product data extracted by a store scraper."""

    name: str
    store_slug: str
    url: str
    key: str  # Store-unique product or variant ID
    normal_price: Decimal
    offer_price: Decimal
    currency: str = "CLP"
    sku: Optional[str] = None
    part_number: Optional[str] = None
    ean: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    is_available: bool = True
    condition: str = "New"
    picture_urls: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def __post_init__(self):
        # Ensure clean numbers
        if not isinstance(self.normal_price, Decimal):
            self.normal_price = Decimal(str(self.normal_price))
        if not isinstance(self.offer_price, Decimal):
            self.offer_price = Decimal(str(self.offer_price))
        # Chilean price sanity: offer price should not exceed normal price
        if self.offer_price > self.normal_price:
            self.normal_price = self.offer_price

        # Sanitize and normalize picture URLs
        clean_pics: List[str] = []
        for pic in self.picture_urls:
            if not pic:
                continue
            pic_str = str(pic).strip()
            if pic_str.startswith("//"):
                pic_str = f"https:{pic_str}"
            elif pic_str.startswith("http://") and "localhost" not in pic_str:
                # Upgrade insecure HTTP images to HTTPS for mixed content security
                pic_str = pic_str.replace("http://", "https://", 1)
            if (pic_str.startswith("https://") or pic_str.startswith("/")) and pic_str not in clean_pics:
                clean_pics.append(pic_str)
        self.picture_urls = clean_pics


class BaseStore(ABC):
    """Abstract base class for all SoloTono store scrapers."""

    store_slug: str = ""
    store_name: str = ""
    website_url: str = ""
    engine_type: str = "Generic"

    @classmethod
    @abstractmethod
    def categories(cls) -> List[str]:
        """List of standard instrument categories supported by this store."""
        pass

    @classmethod
    @abstractmethod
    def discover_product_urls(cls, category: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
        """Discover product URLs for a category or across the store."""
        pass

    @classmethod
    @abstractmethod
    def scrape_product(cls, url: str) -> Optional[ScrapedProduct]:
        """Scrape a single product URL and return a normalized ScrapedProduct."""
        pass

    @classmethod
    def scrape_all(cls, limit: Optional[int] = None, category: Optional[str] = None) -> List[ScrapedProduct]:
        """Scrapes multiple products up to limit using parallel execution for DOM stores."""
        urls = cls.discover_product_urls(category=category, limit=limit)
        if not urls:
            return []

        products: List[ScrapedProduct] = []
        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_workers = min(8, max(1, len(urls)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(cls.scrape_product, url): url for url in urls}
            for future in as_completed(future_to_url):
                try:
                    prod = future.result()
                    if prod:
                        products.append(prod)
                        if limit and len(products) >= limit:
                            break
                except Exception:
                    continue
        return products

    # Utility helpers for all store scrapers
    @staticmethod
    def clean_price(price_val: Any) -> Decimal:
        """Parse Chilean CLP prices (e.g. '$1.299.990', '1299990.00', etc.)."""
        if price_val is None or price_val == "":
            return Decimal("0")
        if isinstance(price_val, (int, Decimal)):
            return Decimal(str(int(price_val)))
        if isinstance(price_val, float):
            return Decimal(str(int(price_val)))

        val_str = str(price_val).strip()
        # Handle decimal cents representation e.g. "849900.00" or "849900.0"
        if re.search(r"\.\d{1,2}$", val_str):
            val_str = re.sub(r"\.\d{1,2}$", "", val_str)

        # Remove currency symbols, dots, spaces
        cleaned = re.sub(r"[^\d]", "", val_str)
        return Decimal(cleaned) if cleaned else Decimal("0")

    @staticmethod
    def parse_json_ld(soup: Any) -> Optional[Dict[str, Any]]:
        """Extract schema.org JSON-LD from page if present."""
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                if not s.string:
                    continue
                data = json.loads(s.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") in ["Product", "IndividualProduct"]:
                            return item
                elif isinstance(data, dict):
                    if data.get("@type") in ["Product", "IndividualProduct"]:
                        return data
                    if "@graph" in data:
                        for item in data["@graph"]:
                            if item.get("@type") in ["Product", "IndividualProduct"]:
                                return item
            except Exception:
                continue
        return None
