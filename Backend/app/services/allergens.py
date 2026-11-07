"""Los 14 alérgenos de declaración obligatoria (Anexo II del Reglamento UE 1169/2011).

En España, para comida sin envasar, el RD 126/2015 obliga a informar de ellos
antes de la compra. El picante NO es un alérgeno: va como etiqueta («spicy»).
"""
from __future__ import annotations

ALLERGENS: dict[str, dict[str, str]] = {
    "gluten": {"icon": "🌾", "es": "Gluten", "en": "Gluten", "fr": "Gluten"},
    "crustaceans": {"icon": "🦐", "es": "Crustáceos", "en": "Crustaceans", "fr": "Crustacés"},
    "eggs": {"icon": "🥚", "es": "Huevo", "en": "Eggs", "fr": "Œufs"},
    "fish": {"icon": "🐟", "es": "Pescado", "en": "Fish", "fr": "Poisson"},
    "peanuts": {"icon": "🥜", "es": "Cacahuetes", "en": "Peanuts", "fr": "Arachides"},
    "soy": {"icon": "🫘", "es": "Soja", "en": "Soy", "fr": "Soja"},
    "milk": {"icon": "🥛", "es": "Lácteos", "en": "Milk", "fr": "Lait"},
    "nuts": {"icon": "🌰", "es": "Frutos de cáscara", "en": "Tree nuts", "fr": "Fruits à coque"},
    "celery": {"icon": "🥬", "es": "Apio", "en": "Celery", "fr": "Céleri"},
    "mustard": {"icon": "🟡", "es": "Mostaza", "en": "Mustard", "fr": "Moutarde"},
    "sesame": {"icon": "⚪", "es": "Sésamo", "en": "Sesame", "fr": "Sésame"},
    "sulphites": {"icon": "🍷", "es": "Sulfitos", "en": "Sulphites", "fr": "Sulfites"},
    "lupin": {"icon": "🌼", "es": "Altramuces", "en": "Lupin", "fr": "Lupin"},
    "molluscs": {"icon": "🐚", "es": "Moluscos", "en": "Molluscs", "fr": "Mollusques"},
}

ALLERGEN_CODES = tuple(ALLERGENS.keys())

# Palabras con las que suelen escribirse en cartas y en otros sistemas
_ALIASES = {
    "gluten": "gluten", "trigo": "gluten", "cereales": "gluten",
    "crustaceos": "crustaceans", "crustáceos": "crustaceans", "marisco": "crustaceans",
    "huevo": "eggs", "huevos": "eggs", "egg": "eggs",
    "pescado": "fish", "atun": "fish", "atún": "fish",
    "cacahuete": "peanuts", "cacahuetes": "peanuts", "mani": "peanuts",
    "soja": "soy", "soya": "soy",
    "leche": "milk", "lacteos": "milk", "lácteos": "milk", "lactosa": "milk", "dairy": "milk",
    "frutos secos": "nuts", "frutos de cascara": "nuts", "frutos de cáscara": "nuts",
    "apio": "celery", "mostaza": "mustard", "sesamo": "sesame", "sésamo": "sesame",
    "sulfitos": "sulphites", "sulfites": "sulphites", "altramuces": "lupin", "altramuz": "lupin",
    "moluscos": "molluscs",
}


def normalize_allergens(values) -> list[str]:
    """Convierte una lista libre («Lácteos», "gluten", "GLUTEN") a códigos válidos, sin repetir."""
    out: list[str] = []
    for value in values or []:
        key = str(value).strip().lower()
        code = key if key in ALLERGENS else _ALIASES.get(key)
        if code and code not in out:
            out.append(code)
    return out


def allergen_label(code: str, lang: str = "es") -> str:
    data = ALLERGENS.get(code)
    if not data:
        return code
    return data.get(lang) or data["es"]


def catalog(lang: str = "es") -> list[dict]:
    return [{"code": c, "icon": d["icon"], "name": d.get(lang) or d["es"]} for c, d in ALLERGENS.items()]
