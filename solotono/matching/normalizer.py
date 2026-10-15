"""Text normalization, token cleaning, and instrument spec extraction."""

import re
import unicodedata
from typing import Dict, Optional, Tuple, Set, List, Any

from solotono.matching.brands import detect_brand

# Common store marketing fluff, audio descriptors, and stop words to strip from normalized tokens
STOP_WORDS: Set[str] = {
    "guitarra", "guitarras", "electrica", "electricas", "acustica", "acusticas",
    "electroacustica", "electroacusticas", "clasica", "clasicas", "bajo", "bajos",
    "electrico", "electricos", "bateria", "baterias", "teclado", "teclados",
    "piano", "pianos", "sintetizador", "sintetizadores", "pedal", "pedales",
    "amplificador", "amplificadores", "microfono", "microfonos", "interfaz",
    "interfaces", "monitor", "monitores", "estudio", "oferta", "descuento",
    "despacho", "gratis", "nuevo", "nueva", "usado", "usada", "ano", "con",
    "para", "del", "las", "los", "una", "uno", "incluye", "funda", "estuche",
    "hardcase", "bag", "color", "edicion", "serie", "zurdos", "zurdo",
    "tienda", "original", "chile", "en", "stock", "liquidacion", "cyber",
    "fingerboard", "fretboard", "diapason", "neck", "mastil",
    # Audio & pro gear generic descriptors (so genuine cross-store matches don't get penalized)
    "cardioide", "supercardioide", "hipercardioide", "dinamico", "dinamica",
    "condensador", "vocal", "lavalier", "solapa", "cintillo", "mano",
    "inalambrico", "inalambrica", "uhf", "portatil", "analogo", "analoga",
    "digital", "mezclador", "mixer", "consola", "pack", "set", "combo", "kit",
    "sistema", "atril", "soporte", "cable", "bluetooth", "potenciado",
    "activo", "activa", "pasivo", "pasiva", "caja", "de", "y", "con", "multiproposito",
    "parlante", "parlantes", "pulgadas", "pulgada", "pa", "entradas",
}

# Critical product series keywords (a mismatch between these indicates different product lines)
SERIES_KEYWORDS: Set[str] = {
    "ultra", "vintage", "professional", "standard", "player", "performer",
    "special", "deluxe", "custom", "vintera", "classic", "traditional",
    "junior", "studio", "tribute", "affinity", "bullet", "contemporary",
    "paranormal", "silversky", "core", "s2", "se", "prestige", "premium",
    "ironlabel", "genesis", "pacifica", "revstar", "broadcaster", "avri",
    "elite", "plus", "highway", "roadworn", "original", "tweed",
}

FRETBOARD_MAP: Dict[str, str] = {
    "maple": "Maple", "arce": "Maple", "mn": "Maple",
    "rosewood": "Rosewood", "palo de rosa": "Rosewood", "palorosa": "Rosewood",
    "palisandro": "Rosewood", "rw": "Rosewood",
    "ebony": "Ebony", "ebano": "Ebony", "ébano": "Ebony",
    "pau ferro": "Pau Ferro", "pauferro": "Pau Ferro", "pf": "Pau Ferro",
    "laurel": "Laurel",
}

FINISH_ALIASES: Dict[str, str] = {
    "mn srd": "Sinister Red",
    "srd": "Sinister Red",
    "mn sfl": "Solar Flare",
    "sfl": "Solar Flare",
    "3ts": "3-Color Sunburst",
    "3-tone sunburst": "3-Color Sunburst",
    "2ts": "2-Color Sunburst",
    "2-tone sunburst": "2-Color Sunburst",
    "candy apple red": "Candy Apple Red",
    "car": "Candy Apple Red",
    "olympic white": "Olympic White",
    "owt": "Olympic White",
    "lake placid blue": "Lake Placid Blue",
    "lpb": "Lake Placid Blue",
    "butterscotch blonde": "Butterscotch Blonde",
    "btb": "Butterscotch Blonde",
    "surf green": "Surf Green",
    "sfg": "Surf Green",
    "sonic blue": "Sonic Blue",
    "sbl": "Sonic Blue",
}

# Instrument finishes and colors (for distinct variant identification)
COLORS_AND_FINISHES = [
    # Multi-word finishes
    "3-color sunburst", "3-tone sunburst", "3ts", "2-color sunburst", "2-tone sunburst", "2ts",
    "butterscotch blonde", "butterscotch", "olympic white", "arctic white", "polar white",
    "vintage white", "aged white", "candy apple red", "fiesta red", "tidepool",
    "lake placid blue", "daphne blue", "sonic blue", "surf green", "seafoam green",
    "sherwood green", "shell pink", "tobacco sunburst", "cherry sunburst", "silverburst",
    "sinister red", "solar red", "solar flare", "sinister flare", "texas tea", "cobra blue",
    "mocha burst", "arctic pearl", "dark night", "miami blue", "mystic surf green",
    "bourbon burst", "aged cherry burst", "aged cognac burst", "vintage blonde",
    "sienna sunburst", "aged natural", "car", "owt", "lpb", "btb", "sfg", "sbl",
    # Single-word finishes
    "sunburst", "black", "negro", "noir", "ebony", "blanco", "white", "natural", "natburst",
    "koa", "goldtop", "walnut", "mahogany", "rosewood", "pau ferro",
    # Acronyms & fingerboard markers
    "mn srd", "mn sfl", "srd", "sfl",
]


def clean_trademark_symbols(text: str) -> str:
    """Remove legal and trademark noise symbols and redundant whitespace."""
    if not text:
        return ""
    cleaned = text.replace("®", "").replace("™", "").replace("©", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def strip_accents(text: str) -> str:
    """Strip accents and convert to ASCII characters."""
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def extract_finish(text: str) -> Tuple[str, Optional[str]]:
    """Extract finish/color variant from product title and return (cleaned_text, finish)."""
    clean_txt = clean_trademark_symbols(text)
    lower = clean_txt.lower()
    for finish in COLORS_AND_FINISHES:
        pattern = r"\b" + re.escape(finish) + r"\b"
        if re.search(pattern, lower):
            cleaned = re.sub(pattern, "", clean_txt, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-")
            canonical_finish = FINISH_ALIASES.get(finish.lower(), finish.title())
            return cleaned, canonical_finish
    return clean_txt, None


def extract_series_tokens(text: str) -> Set[str]:
    """Extract set of series keywords present in title."""
    clean = strip_accents(clean_trademark_symbols(text)).lower()
    tokens = set(re.findall(r"\b[a-z0-9]+\b", clean))
    return tokens.intersection(SERIES_KEYWORDS)


def extract_year_markers(text: str) -> Set[str]:
    """Extract vintage/reissue year markers (e.g. '1957', '1960', '50s', '60s')."""
    clean = strip_accents(clean_trademark_symbols(text)).lower()
    matches = re.findall(r"\b(19[3-9][0-9]|[5-9]0s|20[0-2][0-9])\b", clean)
    return set(matches)


def extract_part_number(text: str, sku: Optional[str] = None) -> Optional[str]:
    """Extract potential MPN / Part Number from title or SKU."""
    if sku and len(sku.strip()) >= 4 and not sku.startswith("http"):
        return sku.strip()
    
    # Check parenthesized or bracketed codes e.g. (PAC012) or (0144502500)
    match = re.search(r"[\(\[\{]([A-Za-z0-9\-\.\_]{4,20})[\)\]\}]", text)
    if match:
        candidate = match.group(1).strip()
        if not candidate.lower() in STOP_WORDS and any(c.isdigit() for c in candidate):
            return candidate

    return None


def extract_fretboard_wood(text: str) -> Optional[str]:
    """Extract fretboard wood species (e.g. Maple, Rosewood, Ebony, Pau Ferro)."""
    t = strip_accents(clean_trademark_symbols(text)).lower()
    for k, v in FRETBOARD_MAP.items():
        if re.search(r"\b" + re.escape(k) + r"\b", t):
            return v
    return None


def extract_pickup_config(text: str) -> Optional[str]:
    """Extract pickup layout (e.g. SSS, HSS, HSH, HH, SS, PJ)."""
    t = clean_trademark_symbols(text).lower()
    m = re.search(r"\b(hss|sss|hsh|hh|ss|pj)\b", t)
    return m.group(1).upper() if m else None


def extract_size_spec(text: str) -> Optional[str]:
    """Extract instrument fractions (4/4, 3/4) or speaker/drum diameter inches (15\", 12\", 8\")."""
    t = clean_trademark_symbols(text).lower()
    m_frac = re.search(r"\b([1-4]\/[1248])\b", t)
    if m_frac:
        return m_frac.group(1)
    m_inch = re.search(r"(\d+(?:\.\d+)?)\s*(?:[\"\'\”\″]|pulg(?:adas?)?|inch(?:es)?)", t)
    if m_inch:
        return f"{m_inch.group(1)}\""
    return None


SPANISH_PREPOSITIONS: Set[str] = {"de", "el", "la", "en", "con", "sin", "por", "para", "un", "una", "del", "los", "las"}


def extract_pack_quantity(text: str) -> Optional[int]:
    """Extract multi-pack quantity (e.g. 'Pack 5 Juegos' -> 5, 'Pack de 3' -> 3)."""
    t = clean_trademark_symbols(text).lower()
    m = re.search(r"\b(?:pack|sets?|juegos?)\s+(?:de\s+)?(\d+)\b", t)
    if m:
        return int(m.group(1))
    m2 = re.search(r"\b(\d+)\s*(?:pack|sets?|juegos?)\b", t)
    if m2:
        return int(m2.group(1))
    return None


def extract_model_codes(text: str) -> Set[str]:
    """Extract critical alphanumeric model identifiers (e.g. m50x, 1204usb, xs1, umc22, 114ce, p45, cts400)."""
    t = clean_trademark_symbols(text).lower()
    # Strip fractions like 3/4, 1/2
    t = re.sub(r"\b[1-4]\/[1248]\b", "", t)
    # Strip dimensional units: inches, watts, channels, keys, meters, etc.
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:[\"\'\”\″]|pulg(?:adas?)?|inch(?:es)?)", "", t)
    t = re.sub(r"\b\d+\s*(?:w|watt|watts|ch|canales|teclas|cuerdas|hz|khz|mhz|mm|cm|kg|g|ohm|ohms|bits?|bit|metros?|mts?|m)\b", "", t)
    # Strip pack statements: 'pack de 3', 'pack 5 juegos', '5 pack'
    t = re.sub(r"\b(?:pack|sets?|juegos?)\s+(?:de\s+)?\d+\b", "", t)
    t = re.sub(r"\b\d+\s*(?:pack|sets?|juegos?)\b", "", t)
    
    # Strip prepositions before merging letter+number sequences (prevent 'de 3' -> 'de3')
    words = t.split()
    cleaned_words = [w for w in words if w not in SPANISH_PREPOSITIONS]
    t = " ".join(cleaned_words)
    
    # Normalize hyphens/slashes between alphanumeric chars: 'xs-1' -> 'xs1', 'ct-s400' -> 'cts400', '1204-usb' -> '1204usb'
    t = re.sub(r"([a-z])[\-\/]+([a-z0-9])", r"\1\2", t)
    t = re.sub(r"([0-9])[\-\/]+([a-z0-9])", r"\1\2", t)
    
    # Merge letter prefix with numbers: 'ct s400' -> 'cts400', 'mk 61' -> 'mk61', 'p 45' -> 'p45', 'xsw 1' -> 'xsw1'
    t = re.sub(r"\b([a-z]{1,4})\s+(\d{1,4}[a-z0-9]*)\b", r"\1\2", t)
    
    tokens = re.findall(r"\b[a-z0-9]{2,15}\b", t)
    codes = set()
    for tok in tokens:
        if any(c.isdigit() for c in tok):
            has_letter = any(c.isalpha() for c in tok)
            if tok in {"2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"}:
                continue
            # Pure digits must have length >= 4 (and not be a generic year) to be considered a model number
            if not has_letter and len(tok) < 4:
                continue
            codes.add(tok)
    return codes


def normalize_title(title: str, brand: Optional[str] = None) -> str:
    """Normalize and clean product title for accurate token comparison."""
    if not title:
        return ""
    
    cleaned = clean_trademark_symbols(title)
    cleaned = strip_accents(cleaned).lower()
    
    # Strip fractions and dimensional units: inches, watts, channels, keys, meters, etc.
    cleaned = re.sub(r"\b[1-4]\/[1248]\b", "", cleaned)
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*(?:[\"\'\”\″]|pulg(?:adas?)?|inch(?:es)?)", "", cleaned)
    cleaned = re.sub(r"\b\d+\s*(?:w|watt|watts|ch|canales|teclas|cuerdas|hz|khz|mhz|mm|cm|kg|g|ohm|ohms|bits?|bit|metros?|mts?|m)\b", "", cleaned)

    # Strip Spanish prepositions before merging letter+digit compound sequences (prevent 'de 15' -> 'de15')
    words = cleaned.split()
    cleaned = " ".join([w for w in words if w not in SPANISH_PREPOSITIONS])

    # Normalize letter+digit compound sequences
    cleaned = re.sub(r"([a-z])[\-\/]+([a-z0-9])", r"\1\2", cleaned)
    cleaned = re.sub(r"([0-9])[\-\/]+([a-z0-9])", r"\1\2", cleaned)
    cleaned = re.sub(r"\b([a-z]{1,4})\s+(\d{1,4}[a-z0-9]*)\b", r"\1\2", cleaned)
    
    cleaned = re.sub(r"[\/\-\_\:\,\.\(\)\[\]\{\}\+\*\&]", " ", cleaned)
    tokens = cleaned.split()
    
    brand_tokens = set(strip_accents(brand.lower()).split()) if brand else set()
    filtered_tokens = []
    
    for t in tokens:
        if t in STOP_WORDS or t in brand_tokens:
            continue
        if brand and len(brand) >= 4 and t.startswith(strip_accents(brand.lower())):
            continue
        if len(t) <= 1 and not t.isdigit():
            continue
        filtered_tokens.append(t)
        
    return " ".join(filtered_tokens)


def clean_canonical_name(raw_name: str, brand: Optional[str] = None, finish: Optional[str] = None, fretboard: Optional[str] = None, pickup: Optional[str] = None) -> str:
    """Generates a standardized, elegant canonical title: [Brand] [Model / Series] [Specs] [Finish]."""
    name = clean_trademark_symbols(raw_name)
    
    # Remove generic used/condition noise
    name = re.sub(r"\b(usada|usado|open box|ano \d{4}|año \d{4}|incluye [^,\-]+)\b", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" ,-")
    
    # Ensure brand is properly capitalized and prefixed
    if brand:
        b_clean = clean_trademark_symbols(brand).strip()
        if not name.lower().startswith(b_clean.lower()):
            name = f"{b_clean} {name}"
            
    # If pickup config known and not in name, append
    if pickup and pickup.lower() not in name.lower():
        name = f"{name} {pickup}"

    # If fretboard known and not in name, append
    if fretboard and fretboard.lower() not in name.lower():
        name = f"{name} {fretboard}"

    # If finish is known and not in title, append it
    if finish and finish.lower() not in name.lower():
        name = f"{name} {finish}"
        
    return re.sub(r"\s+", " ", name).strip()


def analyze_product_string(title: str, raw_brand: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
    """Comprehensive linguistic analysis of an instrument listing."""
    detected_b = (detect_brand(raw_brand) if raw_brand else None) or detect_brand(title) or raw_brand
    cleaned_title, finish = extract_finish(title)
    mpn = extract_part_number(title, sku)
    fretboard = extract_fretboard_wood(title)
    pickup = extract_pickup_config(title)
    size = extract_size_spec(title)
    model_codes = extract_model_codes(title)
    normalized = normalize_title(cleaned_title, brand=detected_b)
    series = extract_series_tokens(title)
    years = extract_year_markers(title)
    
    pack_qty = extract_pack_quantity(title)
    clean_title = clean_canonical_name(
        cleaned_title if finish else title,
        brand=detected_b,
        finish=finish,
        fretboard=fretboard,
        pickup=pickup,
    )
    
    return {
        "brand": detected_b,
        "finish": finish,
        "fretboard": fretboard,
        "pickup_config": pickup,
        "size_spec": size,
        "pack_qty": pack_qty,
        "model_codes": model_codes,
        "part_number": mpn,
        "normalized_model": normalized,
        "series_tokens": series,
        "year_tokens": years,
        "clean_title": clean_title,
    }
