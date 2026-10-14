"""Text normalization, token cleaning, and instrument spec extraction."""

import re
import unicodedata
from typing import Dict, Optional, Tuple, Set

from solotono.matching.brands import detect_brand

# Common store marketing fluff and stop words to strip
STOP_WORDS: Set[str] = {
    "guitarra", "guitarras", "electrica", "electricas", "acustica", "acusticas",
    "electroacustica", "electroacusticas", "clasica", "clasicas", "bajo", "bajos",
    "electrico", "electricos", "bateria", "baterias", "teclado", "teclados",
    "piano", "pianos", "sintetizador", "sintetizadores", "pedal", "pedales",
    "amplificador", "amplificadores", "microfono", "microfonos", "interfaz",
    "interfaces", "monitor", "monitores", "estudio", "oferta", "descuento",
    "despacho", "gratis", "nuevo", "nueva", "usado", "usada", "ano", "con",
    "para", "del", "las", "los", "una", "uno", "incluye", "funda", "estuche",
    "hardcase", "bag", "color", "edicion", "serie", "para", "zurdos", "zurdo",
    "tienda", "original", "chile", "en", "stock", "liquidacion", "cyber",
}

# Instrument finishes and colors (for variant grouping)
COLORS_AND_FINISHES = [
    "3-color sunburst", "3-tone sunburst", "3ts", "2-color sunburst", "sunburst",
    "butterscotch blonde", "butterscotch", "olympic white", "arctic white", "polar white",
    "vintage white", "aged white", "black", "negro", "noir", "ebony", "blanco",
    "candy apple red", "fiesta red", "tidepool", "lake placid blue", "daphne blue",
    "sonic blue", "surf green", "seafoam green", "sherwood green", "shell pink",
    "natural", "natburst", "koa", "tobacco sunburst", "cherry sunburst", "silverburst",
    "goldtop", "walnut", "mahogany", "maple", "rosewood", "pau ferro",
]


def strip_accents(text: str) -> str:
    """Strip accents and convert to ASCII characters."""
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def extract_finish(text: str) -> Tuple[str, Optional[str]]:
    """Extract finish/color variant from product title and return (cleaned_text, finish)."""
    lower = text.lower()
    for finish in COLORS_AND_FINISHES:
        pattern = r"\b" + re.escape(finish) + r"\b"
        if re.search(pattern, lower):
            cleaned = re.sub(pattern, "", lower, flags=re.IGNORECASE)
            return cleaned.strip(), finish.title()
    return text, None


def extract_part_number(text: str, sku: Optional[str] = None) -> Optional[str]:
    """Extract potential MPN / Part Number from title or SKU."""
    if sku and len(sku.strip()) >= 4 and not sku.startswith("http"):
        return sku.strip()
    
    # Check parenthesized or bracketed codes e.g. (PAC012) or (0144502500)
    match = re.search(r"[\(\[\{]([A-Za-z0-9\-\.\_]{4,20})[\)\]\}]", text)
    if match:
        candidate = match.group(1).strip()
        # Ensure it is not just words like "usado" or "nuevo"
        if not candidate.lower() in STOP_WORDS and any(c.isdigit() for c in candidate):
            return candidate

    return None


def normalize_title(title: str, brand: Optional[str] = None) -> str:
    """Normalize and clean product title for accurate token comparison."""
    if not title:
        return ""
    
    # Strip trademark and copyright symbols
    cleaned = title.replace("®", "").replace("™", "").replace("©", "")
    
    # Strip accents
    cleaned = strip_accents(cleaned).lower()
    
    # Strip special punctuation
    cleaned = re.sub(r"[\/\-\_\:\,\.\(\)\[\]\{\}\+\*\&]", " ", cleaned)
    
    # Tokenize
    tokens = cleaned.split()
    
    # Filter out stop words and brand if provided
    brand_tokens = set(strip_accents(brand.lower()).split()) if brand else set()
    filtered_tokens = []
    
    for t in tokens:
        if t in STOP_WORDS or t in brand_tokens:
            continue
        if len(t) <= 1 and not t.isdigit():
            continue
        filtered_tokens.append(t)
        
    return " ".join(filtered_tokens)


def analyze_product_string(title: str, raw_brand: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Comprehensive linguistic analysis of an instrument listing."""
    detected_b = raw_brand or detect_brand(title)
    cleaned_title, finish = extract_finish(title)
    mpn = extract_part_number(title, sku)
    normalized = normalize_title(cleaned_title, brand=detected_b)
    
    return {
        "brand": detected_b,
        "finish": finish,
        "part_number": mpn,
        "normalized_model": normalized,
    }
