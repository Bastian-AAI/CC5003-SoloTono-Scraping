from solotono.matching.brands import KNOWN_BRANDS, detect_brand
from solotono.matching.normalizer import (
    normalize_title,
    analyze_product_string,
    extract_finish,
    extract_part_number,
)
from solotono.matching.matcher import ProductMatcher, MatchResult

__all__ = [
    "KNOWN_BRANDS",
    "detect_brand",
    "normalize_title",
    "analyze_product_string",
    "extract_finish",
    "extract_part_number",
    "ProductMatcher",
    "MatchResult",
]
