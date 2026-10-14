"""Taxonomic Classifier for SoloTono, mapping store products to Canonical Categories and Subcategory params."""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Tuple
import unicodedata
from sqlalchemy.orm import Session

from solotono.db.models import Category, Subcategory


@dataclass
class TaxonomyResult:
    category_slug: str
    confidence: float
    matched_rule: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    detected_params: Dict[str, str] = field(default_factory=dict)
    suggested_subcategories: List[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Lowercase and strip accents for keyword matching."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return cleaned.lower()


# Keyword and regex patterns mapped to canonical Category slugs
CATEGORY_RULES: List[Tuple[str, List[str], List[str], float]] = [
    # (slug, positive_keywords, negative_keywords, base_confidence)
    (
        "guitarras-electricas",
        ["guitarra electrica", "guitarra electrico", "electric guitar", "stratocaster", "telecaster", "les paul", "superstrat", "ibanez rg", "schecter", "epiphone sg", "es-335", "prs custom", "dinky", "soloist"],
        ["bajo", "bass", "amplificador", "juego de cuerdas", "set de cuerdas", "encordado", "funda", "pastilla", "capsula", "strap", "uneta"],
        0.95,
    ),
    (
        "guitarras-acusticas",
        ["guitarra acustica", "acoustic guitar", "dreadnought", "electroacustica", "electro-acustica", "guitarra folk"],
        ["electrica", "bajo", "juego de cuerdas", "encordado", "amplificador", "clasica", "nylon"],
        0.90,
    ),
    (
        "guitarras-clasicas",
        ["guitarra clasica", "guitarra espanola", "guitarra de concierto", "guitarra criolla", "cuerdas de nylon"],
        ["electrica", "acustica", "bajo", "cuerdas"],
        0.90,
    ),
    (
        "bajos-electricos",
        ["bajo electrico", "electric bass", "jazz bass", "precision bass", "stingray", "sire marcus miller", "warwick", "bajo 4 cuerdas", "bajo 5 cuerdas"],
        ["amplificador", "cuerdas", "guitarra", "pastilla", "funda"],
        0.95,
    ),
    (
        "violines",
        ["violin", "viola", "violoncello", "chelo", "contrabajo acustico"],
        ["guitarra", "electrica", "cuerdas"],
        0.90,
    ),
    (
        "ukeleles",
        ["ukelele", "ukulele", "soprano ukulele", "concert ukulele", "tenor ukulele"],
        ["guitarra", "cuerdas"],
        0.95,
    ),
    (
        "flautas-traversas",
        ["flauta traversa", "flauta traversera", "flauta dulce", "piccolo"],
        [],
        0.90,
    ),
    (
        "saxofones",
        ["saxofon", "saxo alto", "saxo tenor", "saxo soprano", "saxo baritono"],
        [],
        0.95,
    ),
    (
        "trompetas",
        ["trompeta", "cornetin", "fliscorno"],
        [],
        0.95,
    ),
    (
        "clarinetes",
        ["clarinete"],
        [],
        0.95,
    ),
    (
        "armonicas",
        ["armonica", "harmonica", "blues harp"],
        [],
        0.95,
    ),
    (
        "baterias-acusticas",
        ["bateria acustica", "acoustic drum kit", "drum set", "bateria 5 piezas"],
        ["electronica", "platillo", "caja", "redoblante"],
        0.90,
    ),
    (
        "baterias-electronicas",
        ["bateria electronica", "electronic drum", "v-drums", "alesis nitro", "dtx"],
        ["acustica", "parche", "baquetas"],
        0.95,
    ),
    (
        "cajas-y-redoblantes",
        ["caja redoblante", "redoblante", "snare drum"],
        ["bateria acustica", "bateria electronica"],
        0.90,
    ),
    (
        "platillos",
        ["platillo", "platillos", "cymbal", "cymbals", "hi-hat", "crash", "ride", "splash", "zildjian", "sabian", "paiste", "meinl"],
        ["bateria acustica", "soporte", "stand"],
        0.90,
    ),
    (
        "percusion-latina",
        ["conga", "congas", "bongo", "bongos", "timbal", "timbales", "cajon peruano", "cajon flamenco", "guiro", "maracas"],
        [],
        0.90,
    ),
    (
        "pianos-digitales",
        ["piano digital", "digital piano", "clavinova", "privia", "yamaha p-", "roland fp-", "kawai es"],
        ["sintetizador", "controlador"],
        0.95,
    ),
    (
        "sintetizadores",
        ["sintetizador", "synthesizer", "minilogue", "microkorg", "moog", "hydrasynth", "analogo", "wavetable"],
        ["piano digital", "controlador midi"],
        0.90,
    ),
    (
        "teclados-controladores-midi",
        ["controlador midi", "midi controller", "keylab", "launchkey", "mpk mini", "keystation"],
        ["piano digital", "sintetizador"],
        0.95,
    ),
    (
        "amplificadores-de-guitarra",
        ["amplificador para guitarra", "guitar amp", "combo guitarra", "marshall", "katana", "blues junior", "hot rod", "spark 40", "line 6 spider"],
        ["bajo", "cable", "cuerdas", "pedal"],
        0.90,
    ),
    (
        "amplificadores-de-bajo",
        ["amplificador para bajo", "bass amp", "combo bajo", "fender rumble", "ampeg", "hartke", "markbass"],
        ["guitarra", "cable"],
        0.90,
    ),
    (
        "cabezales-y-cajas",
        ["cabezal", "gabinete", "pantalla 4x12", "pantalla 2x12", "caja 1x12", "guitar cabinet"],
        ["combo"],
        0.85,
    ),
    (
        "pedales-de-efectos",
        ["pedal", "overdrive", "distorsion", "distortion", "fuzz", "delay", "reverb", "chorus", "phaser", "flanger", "wah wah", "compressor pedal", "booster"],
        ["multiefecto", "multiefectos", "amplificador"],
        0.90,
    ),
    (
        "pedaleras-multiefectos",
        ["multiefecto", "multiefectos", "multi-effects", "pedalera", "helix", "quad cortex", "kemper", "gt-1000", "ge300", "valeton gp"],
        ["analogico"],
        0.95,
    ),
    (
        "preamps",
        ["preamp", "preamplificador", "previo"],
        ["pastilla"],
        0.85,
    ),
    (
        "interfaces-de-audio",
        ["interfaz de audio", "audio interface", "focusrite scarlett", "universal audio volt", "apollo", "motu", "audient", "presonus audiobox"],
        ["cable", "microfono", "monitores"],
        0.95,
    ),
    (
        "microfonos-de-estudio",
        ["microfono", "microphone", "condensador", "sm58", "sm7b", "at2020", "nt1-a", "c414", "dinamico vocal"],
        ["soporte", "cable", "parlante", "audifonos"],
        0.90,
    ),
    (
        "monitores-de-audio",
        ["monitor de estudio", "studio monitor", "monitores activos", "yamaha hs5", "yamaha hs7", "yamaha hs8", "krk rokit", "adam audio t", "kali lp"],
        ["audifonos", "interfaz"],
        0.90,
    ),
    (
        "audifonos-de-monitoreo",
        ["audifonos de monitoreo", "studio headphones", "auriculares de estudio", "ath-m50x", "dt 770 pro", "dt 990", "mdr-7506", "hd 280 pro"],
        ["microfono", "interfaz"],
        0.95,
    ),
    (
        "parlantes-activos-pa",
        ["parlante activo", "caja activa", "subwoofer", "caja acustica", "altavoz pa", "columna pa", "sistema pa", "qsc k", "electro-voice", "jbl eon"],
        ["guitarra", "bajo"],
        0.90,
    ),
    (
        "consolas-y-mezcladoras",
        ["consola de sonido", "mezcladora", "mixer analogo", "mixer digital", "behringer x32", "soundcraft", "yamaha mg", "mixer", "consola"],
        ["interfaz", "soporte"],
        0.90,
    ),
    (
        "cables-y-conectores",
        ["cable de instrumento", "cable plug", "cable xlr", "cable canon", "cable dmx", "conector neutrik", "cable para guitarra", "cable balanceado", "conector", "cable"],
        [],
        0.85,
    ),
    (
        "cuerdas-guitarra-y-bajo",
        ["juego de cuerdas", "set de cuerdas", "encordado", "encordados", "cuerdas para guitarra", "cuerdas para bajo", "cuerdas ernie ball", "cuerdas d'addario", "cuerdas elixir", "calibre 09", "calibre 10", "cuerdas bajo", "cuerdas"],
        ["guitarra electrica", "guitarra acustica", "bajo electrico", "ibanez rg", "stratocaster", "telecaster", "les paul", "afinador"],
        0.90,
    ),
    (
        "clavijeros-y-afinadores",
        ["clavijero", "clavijas", "afinador", "clip tuner", "locking tuners"],
        ["pedal"],
        0.85,
    ),
    (
        "puentes-y-cejuelas",
        ["puente floyd rose", "cejuela", "nut", "saddles", "tune-o-matic"],
        [],
        0.90,
    ),
    (
        "pastillas-capsulas",
        ["pastilla", "pastillas", "capsula", "capsulas", "pickups", "humbucker", "single coil", "seymour duncan", "dimarzio", "emg"],
        ["guitarra", "bajo"],
        0.90,
    ),
    (
        "potenciometros-y-switches",
        ["potenciometro", "switches", "switch 3 posiciones", "switch 5 posiciones", "selector pastillas", "knob", "perilla"],
        [],
        0.90,
    ),
    (
        "jacks-y-placas",
        ["jack hembra", "jack input", "jackplate", "placa jack"],
        [],
        0.90,
    ),
    (
        "correas-straps",
        ["correa", "guitar strap", "bass strap", "straplock", "tali", "tahali"],
        [],
        0.90,
    ),
    (
        "fundas-y-estuches",
        ["funda", "gig bag", "estuche rigido", "hardcase", "case guitarra", "estuche", "cover"],
        [],
        0.90,
    ),
    (
        "soportes-stands",
        ["soporte para guitarra", "guitar stand", "soporte de teclado", "soporte de microfono", "atril", "pie de microfono", "stand"],
        [],
        0.90,
    ),
    (
        "picks-unetas",
        ["uneta", "unetas", "guitar pick", "picks", "plumilla", "tortex", "jazz iii"],
        [],
        0.95,
    ),
    (
        "kits-de-limpieza",
        ["kit de limpieza", "limpiador", "panos de limpieza", "polish", "lemon oil"],
        [],
        0.90,
    ),
]


def classify_product(
    title: str,
    raw_category: Optional[str] = None,
    brand: Optional[str] = None,
    session: Optional[Session] = None,
) -> TaxonomyResult:
    """Classifies a product into a canonical Category and detects subcategory parameters."""
    text_corpus = f"{title} {raw_category or ''} {brand or ''}"
    norm = normalize_text(text_corpus)

    best_match = None
    best_score = 0.0
    matched_rule = "none"

    # Evaluate against rules
    for slug, positives, negatives, base_conf in CATEGORY_RULES:
        # Check negative keywords
        if any(neg in norm for neg in negatives):
            continue

        for pos in positives:
            if pos in norm:
                score = base_conf
                # Exact category substring in raw category gives a boost
                if raw_category and pos in normalize_text(raw_category):
                    score = min(1.0, score + 0.05)
                if score > best_score:
                    best_score = score
                    best_match = slug
                    matched_rule = pos

    if not best_match:
        if "guitarra" in norm:
            best_match = "guitarras-electricas"
            best_score = 0.50
            matched_rule = "guitarra fallback"
        else:
            best_match = None
            best_score = 0.0
            matched_rule = "unclassified"

    # Detect subcategory params (facets)
    detected_params: Dict[str, str] = {}
    suggested_subcats: List[str] = []

    # Electric Guitars facets
    if "7 cuerdas" in norm or "7-string" in norm or "8 cuerdas" in norm:
        detected_params["strings_min"] = "7"
        suggested_subcats.append("7 o más cuerdas")
    if "zurdo" in norm or "left-hand" in norm or "lefty" in norm:
        detected_params["is_left_handed"] = "1"
        suggested_subcats.append("Para Zurdos")
    if "strat" in norm:
        detected_params["body_shape"] = "stratocaster"
        suggested_subcats.append("Stratocaster")
    elif "tele" in norm:
        detected_params["body_shape"] = "telecaster"
        suggested_subcats.append("Telecaster")
    elif "les paul" in norm or "singlecut" in norm:
        detected_params["body_shape"] = "les_paul"
        suggested_subcats.append("Les Paul / Singlecut")

    # Amps facets
    if any(k in norm for k in ["valvular", "tubos", "tube amp", "valvula"]):
        detected_params["tech"] = "tubes"
        suggested_subcats.append("Valvulares (Tubes)")
    elif any(k in norm for k in ["digital", "modelado", "modeling"]):
        detected_params["tech"] = "digital"
        suggested_subcats.append("Digitales / Modelado")

    cat_id = None
    cat_name = None
    if session and best_match:
        cat_obj = session.query(Category).filter(Category.slug == best_match).first()
        if cat_obj:
            cat_id = cat_obj.id
            cat_name = cat_obj.name

    return TaxonomyResult(
        category_slug=best_match,
        confidence=best_score,
        matched_rule=matched_rule,
        category_id=cat_id,
        category_name=cat_name,
        detected_params=detected_params,
        suggested_subcategories=suggested_subcats,
    )
