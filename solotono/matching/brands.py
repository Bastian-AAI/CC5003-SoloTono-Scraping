"""Gazetteer of known musical instrument, audio equipment, and gear brands."""

from typing import List, Optional

KNOWN_BRANDS = [
    # Guitars & Basses
    "Fender", "Gibson", "Ibanez", "Squier", "Epiphone", "Yamaha", "PRS", "Paul Reed Smith",
    "ESP", "LTD", "Jackson", "Gretsch", "Schecter", "Cort", "Charvel", "Music Man",
    "Sterling", "Rickenbacker", "Kramer", "D'Angelico", "Sire", "G&L", "Strandberg",
    "Solar Guitars", "B.C. Rich", "Dean", "Washburn", "Godin", "Seagull", "Martin",
    "Taylor", "Takamine", "Sigma", "Almansa", "Alhambra", "Cordoba", "Valencia",
    # Pedals & Effects
    "Boss", "Electro-Harmonix", "EHX", "MXR", "TC Electronic", "Strymon", "Dunlop",
    "Jim Dunlop", "Cry Baby", "JHS Pedals", "JHS", "Wampler", "Way Huge", "DigiTech",
    "Line 6", "Neural DSP", "Walrus Audio", "Keeley", "EarthQuaker Devices", "EQD",
    "Joyo", "Mooer", "NUX", "Behringer", "Darkglass", "Tech 21", "SansAmp",
    # Amplifiers
    "Marshall", "Orange", "Vox", "Blackstar", "Mesa Boogie", "Peavey", "Roland",
    "Positive Grid", "Laney", "Ampeg", "Fender", "Boss", "Yamaha", "Aguilar",
    "Hartke", "Markbass", "Gallien-Krueger", "Bugera", "Fisheman", "AER",
    # Microphones & Studio Recording
    "Shure", "Sennheiser", "Audio-Technica", "AKG", "Rode", "RØDE", "Neumann",
    "Blue", "Lewitt", "Aston", "Warm Audio", "Mojave", "Telefunken", "Beyerdynamic",
    "Golden Age", "Samson",
    # Audio Interfaces & Studio Monitors
    "Focusrite", "Universal Audio", "UAD", "Presonus", "PreSonus", "Solid State Logic",
    "SSL", "Motu", "Audient", "M-Audio", "Antelope Audio", "RME", "Behringer", "Tascam",
    "Yamaha", "KRK", "Genelec", "Adam Audio", "JBL", "Mackie", "Kali Audio", "Dynaudio",
    # Keyboards & Synthesizers
    "Korg", "Nord", "Moog", "Arturia", "Novation", "Casio", "Akai", "Akai Professional",
    "Sequential", "Dave Smith", "Kurzweil", "Elektron", "Teenage Engineering", "Waldorf",
    "Behringer", "Yamaha", "Roland",
    # Drums & Percussion
    "Pearl", "Tama", "DW", "Drum Workshop", "Ludwig", "Mapex", "Sonor", "Gretsch Drums",
    "Zildjian", "Sabian", "Paiste", "Meinl", "Vic Firth", "Promark", "Evans", "Remo",
    "Alesis",
    # DJ & Lighting
    "Pioneer DJ", "Pioneer", "Denon DJ", "Numark", "Hercules", "Chauvet", "Eastman", "Tecshow",
]


def detect_brand(text: str) -> Optional[str]:
    """Detect and return canonical brand name from title or description."""
    if not text:
        return None
    lower_text = f" {text.lower()} "
    for brand in KNOWN_BRANDS:
        # Check whole word boundary
        pattern = f" {brand.lower()} "
        if pattern in lower_text or lower_text.startswith(f"{brand.lower()} ") or lower_text.endswith(f" {brand.lower()}"):
            return brand
    return None
