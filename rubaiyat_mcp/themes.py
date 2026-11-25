"""Hand-curated theme vocabulary for finding quatrains by subject.

Theme lookup is keyword-based, not semantic: a quatrain matches a theme when
one of its lines contains one of the theme's words. Every word listed here
occurs at least once in the corresponding text, so each theme returns results
in both languages. Persian entries are written in normalised form (Persian
yeh/kaf, no diacritics) to match the corpus index.
"""

from __future__ import annotations

THEMES: dict[str, dict[str, object]] = {
    "wine": {
        "description": "Wine, the cup and the tavern: Khayyam's central image of living in the moment.",
        "english": ["wine", "cup", "grape", "vine", "tavern", "drink", "bowl", "vintage"],
        "persian": ["می", "باده", "جام", "شراب", "پیاله", "قدح", "خرابات", "میخانه", "ساقی", "بنوش"],
    },
    "mortality": {
        "description": "Death, dust and the grave; what becomes of us.",
        "english": ["death", "die", "dead", "dust", "clay", "perish", "departed"],
        "persian": ["خاک", "گور", "مرده", "اجل"],
    },
    "time": {
        "description": "Yesterday and tomorrow, dawn and night, the passing of days.",
        "english": ["time", "yesterday", "morn", "morning", "dawn", "night", "hour", "moment", "day", "year"],
        "persian": ["امروز", "فردا", "دی", "دوش", "دم", "سحر", "صبح", "شب", "روز", "وقت", "عمر"],
    },
    "fate": {
        "description": "Fate, the turning sky and the hand that writes.",
        "english": ["fate", "heaven", "finger"],
        "persian": ["قضا", "تقدیر", "فلک", "چرخ"],
    },
    "love": {
        "description": "The beloved, lips and cheeks, the friend.",
        "english": ["beloved", "lip", "cheek", "friend"],
        "persian": ["عشق", "دلبر", "معشوق", "دل", "بوسه", "لب", "دوست"],
    },
    "nature": {
        "description": "Rose, garden, spring, nightingale and river.",
        "english": ["rose", "garden", "spring", "nightingale", "bough", "flower", "river"],
        "persian": ["گل", "گلزار", "بهار", "بلبل", "باغ", "سبزه"],
    },
    "joy": {
        "description": "Be merry, live now.",
        "english": ["live", "merry"],
        "persian": ["خوش", "شاد"],
    },
    "faith": {
        "description": "God, paradise and hell, temple and creed.",
        "english": ["god", "lord", "paradise", "hell", "temple", "soul", "repentance"],
        "persian": ["خدا", "یزدان", "بهشت", "دین", "توبه"],
    },
    "potter": {
        "description": "The potter and the clay vessel: humanity shaped and broken.",
        "english": ["potter", "vessel", "clay"],
        "persian": ["کوزه", "سبو"],
    },
    "kings": {
        "description": "Vanished kings and their thrones: Jamshyd, Kaikobad, Bahram.",
        "english": ["sultan", "jamshyd", "kaikobad", "bahram", "throne"],
        "persian": ["جم", "کیخسرو", "جمشید", "بهرام"],
    },
    "mystery": {
        "description": "The veil, the secret, the door with no key; the limits of learning.",
        "english": ["secret", "veil", "door", "key", "saint", "doctor", "learn"],
        "persian": ["راز", "پرده", "اسرار", "عقل", "دانش"],
    },
    "cosmos": {
        "description": "Earth, sky, sun and stars.",
        "english": ["earth", "sky", "stars", "sun"],
        "persian": ["زمین", "آسمان", "خورشید", "ماه", "مه", "جهان"],
    },
    "sorrow": {
        "description": "Grief, tears and sleep.",
        "english": ["tears", "sleep"],
        "persian": ["غم", "خواب"],
    },
}


def theme_words(theme: str, language: str) -> list[str]:
    key = theme.strip().lower()
    if key not in THEMES:
        raise KeyError(f"unknown theme {theme!r}; available: {', '.join(sorted(THEMES))}")
    return list(THEMES[key][language])  # type: ignore[arg-type]
