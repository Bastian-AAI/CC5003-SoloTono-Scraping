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
            page = 1
            while True:
                cat_url = urljoin(cls.website_url, f"{path}?p={page}") if page > 1 else urljoin(cls.website_url, path)
                try:
                    r = session.get(cat_url, timeout=15)
                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, "html.parser")
                    items = soup.select(".product-item-link, a.product.photo, .product-item a[href], h2.product-name a, .product-name a, a.product-image")
                    if not items:
                        break

                    new_on_page = 0
                    for item in items:
                        href = item.get("href")
                        if href and href.startswith("http") and href not in urls:
                            if any(x in href for x in ["checkout", "cart", "customer", "wishlist", "#"]):
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
            
            # Extract specs table / attributes if present (common in Magento)
            specs = {}
            for tr in soup.select("table tr"):
                tds = tr.find_all(["th", "td"])
                if len(tds) >= 2:
                    k = tds[0].get_text(strip=True).rstrip(":").lower()
                    v = tds[1].get_text(strip=True)
                    if k and v and k not in specs:
                        specs[k] = v
            for dl in soup.select("dl"):
                for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                    k = dt.get_text(strip=True).rstrip(":").lower()
                    v = dd.get_text(strip=True)
                    if k and v and k not in specs:
                        specs[k] = v

            spec_model = specs.get("nombre del modelo") or specs.get("modelo") or specs.get("product name")
            spec_mpn = specs.get("número del modelo") or specs.get("numero del modelo") or specs.get("part number") or specs.get("mpn") or specs.get("código") or specs.get("codigo")
            spec_color = specs.get("color") or specs.get("acabado")

            # 1. Try JSON-LD first (standard in Magento 2)
            json_ld = cls.parse_json_ld(soup)
            if json_ld:
                name = json_ld.get("name", "")
                sku = json_ld.get("sku") or spec_mpn
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
                if not images:
                    og_img = soup.select_one("meta[property='og:image'], meta[name='og:image']")
                    if og_img and og_img.get("content"):
                        images = [og_img["content"].strip()]

                final_brand = brand or cls.store_name
                if final_brand.endswith(" Chile"):
                    final_brand = final_brand[:-6].strip()
                final_name = name
                if spec_model:
                    final_name = spec_model
                    if final_brand and not final_name.lower().startswith(final_brand.lower()):
                        final_name = f"{final_brand} {final_name}"
                elif spec_color and spec_color.lower() not in final_name.lower():
                    final_name = f"{final_name} {spec_color}"

                if final_name and price > 0:
                    return ScrapedProduct(
                        name=final_name,
                        store_slug=cls.store_slug,
                        url=url,
                        key=spec_mpn or sku or url.split("/")[-1].replace(".html", ""),
                        sku=sku or spec_mpn,
                        part_number=spec_mpn or sku,
                        ean=json_ld.get("gtin13") or json_ld.get("gtin") or None,
                        brand=final_brand,
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
            if not title_tag and not spec_model:
                return None
            name = spec_model or (title_tag.get_text().strip() if title_tag else "")
            brand = cls.store_name
            if brand.endswith(" Chile"):
                brand = brand[:-6].strip()
            if brand and not name.lower().startswith(brand.lower()):
                name = f"{brand} {name}"
            if spec_color and spec_color.lower() not in name.lower():
                name = f"{name} {spec_color}"

            # Prices
            price_tag = soup.select_one(".special-price .price, .price-box .price, [data-price-type='finalPrice'] .price, .regular-price .price")
            old_price_tag = soup.select_one(".old-price .price")
            
            price = cls.clean_price(price_tag.get_text()) if price_tag else Decimal("0")
            old_price = cls.clean_price(old_price_tag.get_text()) if old_price_tag else price
            
            normal_price = old_price if old_price > price else price
            offer_price = price

            # SKU
            sku_tag = soup.select_one(".product.attribute.sku .value, [itemprop='sku']")
            sku = spec_mpn or (sku_tag.get_text().strip() if sku_tag else None)

            # Stock
            stock_tag = soup.select_one(".stock.available, .stock.unavailable")
            is_avail = True
            if stock_tag and "unavailable" in stock_tag.get("class", []):
                is_avail = False

            # Images (Magento 1 and 2: OG, fotorama, gallery, product-image, catalog/product)
            imgs: List[str] = []
            og_img = soup.select_one("meta[property='og:image'], meta[name='og:image']")
            if og_img and og_img.get("content"):
                c = og_img["content"].strip()
                if c.startswith("http") and not any(x in c.lower() for x in ["logo", "banner"]):
                    imgs.append(c)

            for img in soup.select(".product-image img, .product-img-box img, .product-media img, #image, #image-main, img[src*='/media/catalog/product/'], .gallery-placeholder img, .fotorama__img"):
                src = img.get("src") or img.get("data-src")
                if src:
                    full_src = urljoin(cls.website_url, src)
                    if full_src not in imgs and not any(x in full_src.lower() for x in ["thumbnail/56x56", "thumbnail/80x80", "logo", "icon"]):
                        imgs.append(full_src)

            if not imgs:
                found = re.findall(r'https?://[^\s\"\'<>]*/media/catalog/product/(?:cache/1/image/[^\s\"\'<>]+|[^/]+/[^/]+/[^\s\"\'<>]+)', r.text)
                for f_url in set(found):
                    if not any(x in f_url for x in ["56x56", "80x80"]):
                        imgs.append(f_url)

            return ScrapedProduct(
                name=name,
                store_slug=cls.store_slug,
                url=url,
                key=spec_mpn or sku or url.split("/")[-1].replace(".html", ""),
                sku=sku or spec_mpn,
                part_number=spec_mpn or sku,
                brand=brand,
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
