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
    "sigma": "mathematics, proofs, equations, open problems",
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

# The drawings (24x24, stroke), the same strings as SYMBOL_ICONS in
# static/js/watch-dashboard.js -- public pages render them without script
# (Topic pages, 2026-10-15). A test keeps both identical.
SYMBOL_PATHS = {
    "briefcase": "<rect x=\"3\" y=\"7\" width=\"18\" height=\"13\" rx=\"2\"/><path d=\"M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 12.5h18\"/>",
    "graduation": "<path d=\"M2 9l10-5 10 5-10 5z\"/><path d=\"M6 11v4.5c0 1.5 2.7 3 6 3s6-1.5 6-3V11M22 9v5\"/>",
    "trophy": "<path d=\"M7 4h10v5a5 5 0 0 1-10 0z\"/><path d=\"M7 5.5H4v1A3.5 3.5 0 0 0 7.5 10M17 5.5h3v1a3.5 3.5 0 0 1-3.5 3.5M12 14v3.5M8 20.5h8M9.5 17.5h5\"/>",
    "heart": "<path d=\"M12 20.5l-7.4-7.3a4.6 4.6 0 0 1 6.5-6.5l.9.9.9-.9a4.6 4.6 0 0 1 6.5 6.5z\"/>",
    "pulse": "<path d=\"M3 12h4l2.5-6 4 12 2.5-6H21\"/>",
    "flask": "<path d=\"M9 3h6M10 3v6.2l-5.2 9.1A1.8 1.8 0 0 0 6.4 21h11.2a1.8 1.8 0 0 0 1.6-2.7L14 9.2V3M7.3 15h9.4\"/>",
    "sigma": "<path d=\"M17.5 5H6.5l6.5 7-6.5 7h11\"/>",
    "chip": "<rect x=\"7\" y=\"7\" width=\"10\" height=\"10\" rx=\"1.5\"/><rect x=\"10\" y=\"10\" width=\"4\" height=\"4\"/><path d=\"M10 4v3M14 4v3M10 17v3M14 17v3M4 10h3M4 14h3M17 10h3M17 14h3\"/>",
    "phone": "<rect x=\"7\" y=\"2.5\" width=\"10\" height=\"19\" rx=\"2.2\"/><path d=\"M11 18.5h2\"/>",
    "code": "<path d=\"M8.5 7l-5 5 5 5M15.5 7l5 5-5 5M13.5 5l-3 14\"/>",
    "sparkle": "<path d=\"M11 5Q12 12 19 13Q12 14 11 21Q10 14 3 13Q10 12 11 5z\"/><path d=\"M18.5 3v4M16.5 5h4\"/>",
    "scale": "<path d=\"M12 4v16M8 20.5h8M5 7h14M2.5 13L5 7l2.5 6M16.5 13L19 7l2.5 6M2.5 13a2.5 2.5 0 0 0 5 0M16.5 13a2.5 2.5 0 0 0 5 0\"/>",
    "coins": "<circle cx=\"9\" cy=\"9\" r=\"6\"/><path d=\"M15 9a6 6 0 1 1-6 6M9 6.5v5\"/>",
    "chart": "<path d=\"M4 4v16h16M7.5 14.5l3.5-4 3 2.5 5-6M16 7h3v3\"/>",
    "tag": "<path d=\"M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7a1 1 0 0 1 .7.3l7.6 7.6a1 1 0 0 1 0 1.4l-7.7 7.7a1 1 0 0 1-1.4 0l-7.6-7.6a1 1 0 0 1-.3-.7z\"/><circle cx=\"8\" cy=\"8\" r=\"1.5\"/>",
    "car": "<path d=\"M5 16.5H4a1 1 0 0 1-1-1V13l2-5a2 2 0 0 1 1.9-1.3h10.2A2 2 0 0 1 19 8l2 5v2.5a1 1 0 0 1-1 1h-1M9 16.5h6M3.5 12.5h17\"/><circle cx=\"7\" cy=\"16.5\" r=\"2\"/><circle cx=\"17\" cy=\"16.5\" r=\"2\"/>",
    "plane": "<path d=\"M12 2.5c.83 0 1.5.67 1.5 1.5v5l7 4v2l-7-2v4.5l2.5 1.8V21L12 20l-4 1v-1.7l2.5-1.8V13l-7 2v-2l7-4V4c0-.83.67-1.5 1.5-1.5z\"/>",
    "home": "<path d=\"M3.5 11L12 4l8.5 7M5.5 9.5V20h13V9.5M10 20v-5.5h4V20\"/>",
    "bolt": "<path d=\"M13 2.5L4.5 13.5H11l-1 8 8.5-11H12z\"/>",
    "cloud": "<path d=\"M7 18.5a4.5 4.5 0 0 1-.6-8.96 6 6 0 0 1 11.4-.94A5 5 0 0 1 17.5 18.5z\"/>",
    "film": "<rect x=\"3\" y=\"4\" width=\"18\" height=\"16\" rx=\"2\"/><path d=\"M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4\"/>",
    "music": "<path d=\"M9 18V5.5l11-2V16\"/><circle cx=\"6.5\" cy=\"18\" r=\"2.5\"/><circle cx=\"17.5\" cy=\"16\" r=\"2.5\"/>",
    "game": "<path d=\"M7 8h10a4 4 0 0 1 4 4v1.5a3.5 3.5 0 0 1-6.3 2.1L14 14.5h-4l-.7 1.1A3.5 3.5 0 0 1 3 13.5V12a4 4 0 0 1 4-4z\"/><path d=\"M7 11v3M5.5 12.5h3M15.5 11.5h.01M17.5 13.5h.01\"/>",
    "book": "<path d=\"M12 6.5C10.5 5 8 4.5 3.5 4.5v14c4.5 0 7 .5 8.5 2 1.5-1.5 4-2 8.5-2v-14c-4.5 0-7 .5-8.5 2zM12 6.5v14\"/>",
    "globe": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18\"/>",
    "eye": "<path d=\"M2.5 12C4.5 8 8 5.5 12 5.5s7.5 2.5 9.5 6.5c-2 4-5.5 6.5-9.5 6.5S4.5 16 2.5 12z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/>",
}


def clean_symbol(value) -> str:
    """Ein bekannter Symbolname, sonst das Standardsymbol."""
    return value if isinstance(value, str) and value in SYMBOLS else DEFAULT_SYMBOL
