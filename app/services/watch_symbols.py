"""Das Symbol einer Watch: woran man sie ohne Bild wiedererkennt (seit 2026-10-12).

Hat eine Watch weder Foto noch Logo (``watch_images``), zeigt das Dashboard
ein schlichtes Symbol. Welches, wählt der günstige Judge einmal pro Watch aus
dieser festen Liste (``watch_scheduler.pick_visual``); bis dahin oder wenn er
ausfällt, steht ``DEFAULT_SYMBOL``. Die Zeichnungen liegen unter denselben
Namen in ``static/js/watch-dashboard.js`` (``SYMBOL_ICONS``) -- ein Test hält
beide Listen gleich.
"""

from __future__ import annotations

# Name -> wofür es steht (so liest es auch das Modell).
SYMBOLS = {
    "briefcase": "jobs, job openings, careers, applications",
    "graduation": "universities, studying, schools, exams, doctorates",
    "trophy": "sport results, competitions, championships, awards, who wins",
    "heart": "relationships, weddings, celebrities' private lives, family",
    "pulse": "health, medicine, diseases, treatments",
    "flask": "science, research, studies, space",
    "chip": "computer hardware, chips, memory, SSDs, graphics cards",
    "phone": "smartphones and other mobile devices",
    "code": "software, programming, developer tools, coding agents",
    "sparkle": "AI models, chatbots and AI companies",
    "scale": "laws, regulation, courts, government policy, elections",
    "coins": "money, income, salaries, taxes, savings, crypto",
    "chart": "stock markets, the economy, statistics, price trends",
    "tag": "buying something, prices, deals, discounts",
    "car": "cars, vehicles, mobility",
    "plane": "travel, flights, holidays",
    "home": "housing, rent, real estate",
    "bolt": "energy, electricity, fuel, utilities",
    "cloud": "weather and climate",
    "film": "films, series, TV, streaming",
    "music": "music, concerts, albums",
    "game": "video games",
    "book": "books, documentation, guides, manuals",
    "globe": "world news, countries, international affairs",
    "eye": "anything else",
}
DEFAULT_SYMBOL = "eye"


def clean_symbol(value) -> str:
    """Ein bekannter Symbolname, sonst das Standardsymbol."""
    return value if isinstance(value, str) and value in SYMBOLS else DEFAULT_SYMBOL
