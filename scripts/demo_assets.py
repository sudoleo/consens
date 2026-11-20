"""Write the files the demo's agent shares: its chart and its spreadsheet.

The demo (static/demo.js) plays a turn in which the agent calculates whether
a couple should buy the flat they rent in Leipzig or keep renting and invest
the difference. In its workspace it writes a chart and a spreadsheet; the
answer shows the chart in its text and the spreadsheet as a row with its
preview (agent-workspace.js `demo`). They are real files, made here from one
model, so every number in the answer, the chart, the preview and the
download agrees:

    venv/Scripts/python.exe scripts/demo_assets.py

writes, in English and German, static/demo/buy-vs-rent.<lang>.png (the
chart), .pdf (the spreadsheet as the shared converter would show it) and
.xlsx (the spreadsheet itself: its 30 years are formulas over the
assumptions, so a changed assumption recalculates), and prints the numbers
the demo's texts quote.

The agent's calculation keeps one mistake on purpose, the one its reviewers
mark: Saxony's property transfer tax has been 5.5 % since 2023, the agent
still uses the old 3.5 %. The files carry the agent's numbers; the printout
also gives the corrected ones the reviewer's note quotes.
"""
from __future__ import annotations

import sys
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "demo"
FONT = ROOT / "static" / "fonts" / "Inter-Variable.ttf"
YEARS = 30


@dataclass(frozen=True)
class Inputs:
    price: float = 310_000
    equity: float = 70_000
    tax: float = 0.035          # the agent's mistake: Saxony charges 0.055 since 2023
    notary: float = 0.02
    rate: float = 0.036
    repay: float = 0.02
    rent: float = 925
    rent_growth: float = 0.025
    upkeep: float = 120         # management and repair reserve, a month
    upkeep_growth: float = 0.02
    returns: float = 0.05
    value_growth: float = 0.015
    stay: int = 12


@dataclass(frozen=True)
class Year:
    year: int
    value: float
    debt: float
    payment: float
    owner: float
    rent: float
    savings: float

    @property
    def buying(self) -> float:
        return self.value - self.debt

    @property
    def lead(self) -> float:
        return self.buying - self.savings


def costs(i: Inputs) -> float:
    return i.price * (i.tax + i.notary)


def loan(i: Inputs) -> float:
    return i.price + costs(i) - i.equity


def years(i: Inputs) -> list[Year]:
    """The spreadsheet's 30 years, row by row as its formulas compute them.

    Both households spend the same each year: the owners pay the loan and the
    upkeep a tenant would not pay; the tenants pay the rent and invest the
    rest (or take it out once the rent costs more than owning)."""
    annuity = loan(i) * (i.rate + i.repay)
    rows = [Year(0, i.price, loan(i), 0, 0, 0, i.equity)]
    for year in range(1, YEARS + 1):
        last = rows[-1]
        payment = min(annuity, last.debt * (1 + i.rate))
        debt = last.debt * (1 + i.rate) - payment
        owner = payment + i.upkeep * 12 * (1 + i.upkeep_growth) ** (year - 1)
        rent = i.rent * 12 * (1 + i.rent_growth) ** (year - 1)
        savings = last.savings * (1 + i.returns) + owner - rent
        rows.append(Year(year, last.value * (1 + i.value_growth), debt, payment, owner, rent, savings))
    return rows


def ahead_from(rows: list[Year]) -> int | None:
    """The first year from which buying stays ahead."""
    for row in rows:
        if all(later.lead > 0 for later in rows[row.year:]):
            return row.year
    return None


# ---- words ---------------------------------------------------------------
TEXT = {
    "en": {
        "title": "Buying vs. renting over 30 years",
        "subtitle": "What you own at the end of each year",
        "buying": "Buying: flat minus loan",
        "renting": "Renting: invested savings",
        "ahead": "Buying pulls ahead in year {year}",
        "stay": "Your {years} years",
        "years": "Years",
        "sheet1": "Assumptions",
        "sheet2": "30 years",
        "heading": "Buy or rent: Leipzig, 82 m²",
        "inputs": "Inputs",
        "results": "Results",
        "rows": [
            ("Purchase price", "price", "eur"),
            ("Equity", "equity", "eur"),
            ("Property transfer tax", "tax", "pct"),
            ("Notary and land registry", "notary", "pct"),
            ("Loan rate (fixed for 15 years)", "rate", "pct"),
            ("Initial repayment", "repay", "pct"),
            ("Rent (cold) a month", "rent", "eur"),
            ("Rent increase a year", "rent_growth", "pct"),
            ("Management and repairs a month", "upkeep", "eur"),
            ("Their increase a year", "upkeep_growth", "pct"),
            ("Return on savings a year", "returns", "pct"),
            ("Value increase a year", "value_growth", "pct"),
            ("Years you plan to stay", "stay", "int"),
        ],
        "result_rows": [
            "Purchase costs", "Loan", "Loan payment a month", "Owners pay a month (year 1)",
            "Tenants invest a month (year 1)", "Buying pulls ahead in year", "Lead of buying after your years",
        ],
        "columns": ["Year", "Flat value", "Loan left", "Loan payment", "Owner costs", "Rent",
                    "Savings (renting)", "Buying (flat minus loan)", "Lead of buying"],
        "never": "never",
    },
    "de": {
        "title": "Kaufen oder mieten: 30 Jahre",
        "subtitle": "Was euch am Ende jedes Jahres gehört",
        "buying": "Kaufen: Wohnung minus Kredit",
        "renting": "Mieten: angelegte Ersparnis",
        "ahead": "Kaufen liegt ab Jahr {year} vorn",
        "stay": "Eure {years} Jahre",
        "years": "Jahre",
        "sheet1": "Annahmen",
        "sheet2": "30 Jahre",
        "heading": "Kaufen oder mieten: Leipzig, 82 m²",
        "inputs": "Eingaben",
        "results": "Ergebnis",
        "rows": [
            ("Kaufpreis", "price", "eur"),
            ("Eigenkapital", "equity", "eur"),
            ("Grunderwerbsteuer", "tax", "pct"),
            ("Notar und Grundbuch", "notary", "pct"),
            ("Zins (15 Jahre fest)", "rate", "pct"),
            ("Anfängliche Tilgung", "repay", "pct"),
            ("Kaltmiete im Monat", "rent", "eur"),
            ("Mietsteigerung im Jahr", "rent_growth", "pct"),
            ("Verwaltung und Rücklage im Monat", "upkeep", "eur"),
            ("Deren Steigerung im Jahr", "upkeep_growth", "pct"),
            ("Rendite der Ersparnis im Jahr", "returns", "pct"),
            ("Wertsteigerung im Jahr", "value_growth", "pct"),
            ("Geplante Jahre in der Wohnung", "stay", "int"),
        ],
        "result_rows": [
            "Kaufnebenkosten", "Kredit", "Kreditrate im Monat", "Eigentümer zahlen im Monat (Jahr 1)",
            "Mieter legen an im Monat (Jahr 1)", "Kaufen liegt vorn ab Jahr", "Vorsprung Kaufen nach euren Jahren",
        ],
        "columns": ["Jahr", "Wert der Wohnung", "Restschuld", "Kreditrate", "Kosten Eigentum", "Miete",
                    "Ersparnis (mieten)", "Kaufen (Wohnung minus Kredit)", "Vorsprung Kaufen"],
        "never": "nie",
    },
}


def money(value: float, lang: str) -> str:
    sign = "-" if round(value) < 0 else ""
    digits = f"{abs(round(value)):,}"
    return f"{sign}€{digits}" if lang == "en" else f"{sign}{digits.replace(',', '.')} €"


def percent(value: float, lang: str) -> str:
    text = f"{value * 100:.1f}%"
    return text if lang == "en" else text.replace(".", ",")


def thousands(value: float, lang: str) -> str:
    k = round(value / 1000)
    if not k:
        return "€0" if lang == "en" else "0 €"
    return f"€{k}k" if lang == "en" else f"{k} Tsd. €"


# ---- the chart -------------------------------------------------------------
INK, INK_2, INK_3 = (11, 11, 11), (82, 81, 78), (128, 127, 121)
GRID, SURFACE = (232, 231, 227), (255, 255, 255)
BLUE, ORANGE = (42, 120, 214), (235, 104, 52)
WIDTH, HEIGHT, SS = 1600, 1000, 2


def font(size: float, weight: bytes = b"Regular") -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), round(size * SS))
    face.set_variation_by_name(weight)
    return face


def chart(i: Inputs, lang: str) -> Image.Image:
    words = TEXT[lang]
    rows = years(i)
    image = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), SURFACE)
    draw = ImageDraw.Draw(image)
    s = lambda v: round(v * SS)  # noqa: E731
    left, right, top, bottom = 150, 1430, 240, 880
    top_value = 500_000
    x = lambda year: left + (right - left) * year / YEARS  # noqa: E731
    y = lambda value: bottom - (bottom - top) * value / top_value  # noqa: E731

    draw.text((s(64), s(52)), words["title"], font=font(42, b"SemiBold"), fill=INK)
    draw.text((s(64), s(108)), words["subtitle"], font=font(27), fill=INK_2)
    legend_x = 64
    for colour, label in ((BLUE, words["buying"]), (ORANGE, words["renting"])):
        draw.line([(s(legend_x), s(172)), (s(legend_x + 30), s(172))], fill=colour, width=s(6))
        draw.text((s(legend_x + 42), s(172)), label, font=font(25, b"Medium"), fill=INK, anchor="lm")
        legend_x += 42 + draw.textlength(label, font=font(25, b"Medium")) / SS + 44

    tick_font = font(23)
    for value in range(0, top_value + 1, 100_000):
        draw.line([(s(left), s(y(value))), (s(right), s(y(value)))], fill=GRID, width=s(1.5))
        draw.text((s(left - 18), s(y(value))), thousands(value, lang), font=tick_font, fill=INK_3, anchor="rm")
    for year in range(0, YEARS + 1, 5):
        draw.text((s(x(year)), s(bottom + 22)), str(year), font=tick_font, fill=INK_3, anchor="mt")
    draw.text((s(right), s(bottom + 58)), words["years"], font=tick_font, fill=INK_3, anchor="rt")

    # The years the couple plans to stay: a quiet dashed line with its words.
    stay_x = x(i.stay)
    dash = 12
    for start in range(top, bottom, dash * 2):
        draw.line([(s(stay_x), s(start)), (s(stay_x), s(min(start + dash, bottom)))], fill=INK_3, width=s(2))
    draw.text((s(stay_x + 12), s(top + 4)), words["stay"].format(years=i.stay), font=font(23, b"Medium"),
              fill=INK_2, anchor="lt")

    for colour, values in ((ORANGE, [row.savings for row in rows]), (BLUE, [row.buying for row in rows])):
        points = [(s(x(year)), s(y(value))) for year, value in enumerate(values)]
        draw.line(points, fill=colour, width=s(5), joint="curve")
        end = points[-1]
        r = s(4)
        draw.ellipse([end[0] - r, end[1] - r, end[0] + r, end[1] + r], fill=colour)
        draw.text((end[0] + s(14), end[1]), thousands(values[-1], lang), font=font(24, b"SemiBold"),
                  fill=INK, anchor="lm")

    year = ahead_from(rows)
    if year:
        cx, cy = s(x(year)), s(y(rows[year].buying))
        draw.ellipse([cx - s(11), cy - s(11), cx + s(11), cy + s(11)], fill=SURFACE)
        draw.ellipse([cx - s(8), cy - s(8), cx + s(8), cy + s(8)], fill=BLUE)
        label = words["ahead"].format(year=year)
        draw.text((cx - s(20), cy - s(34)), label, font=font(24, b"SemiBold"), fill=INK, anchor="rb")
    return image.resize((WIDTH, HEIGHT), Image.LANCZOS)


# ---- the spreadsheet as its preview shows it --------------------------------
def pdf_font() -> None:
    if "Inter" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Inter", str(FONT)))


def pdf_text(c: canvas.Canvas, x: float, y: float, text: str, size: float = 9, bold: bool = False,
             colour: tuple[float, float, float] = (0.04, 0.04, 0.04), align: str = "left") -> None:
    width = pdfmetrics.stringWidth(text, "Inter", size)
    x = x - width if align == "right" else x
    # Each text in a state of its own: the render mode is part of the PDF's
    # graphics state and outlived its text object, so every later text was bold.
    c.saveState()
    t = c.beginText(x, y)
    t.setFont("Inter", size)
    # The variable font's one instance; bold is its outline drawn as well.
    if bold:
        t.setTextRenderMode(2)
        c.setLineWidth(0.35)
    c.setFillColorRGB(*colour)
    c.setStrokeColorRGB(*colour)
    t.textOut(text)
    c.drawText(t)
    c.restoreState()


def value_text(i: Inputs, key: str, kind: str, lang: str) -> str:
    value = getattr(i, key)
    return money(value, lang) if kind == "eur" else percent(value, lang) if kind == "pct" else str(value)


def results(i: Inputs, rows: list[Year], lang: str) -> list[str]:
    annuity = loan(i) * (i.rate + i.repay) / 12
    owner = annuity + i.upkeep
    year = ahead_from(rows)
    return [money(costs(i), lang), money(loan(i), lang), money(annuity, lang), money(owner, lang),
            money(owner - i.rent, lang), str(year) if year else TEXT[lang]["never"], money(rows[i.stay].lead, lang)]


def spreadsheet_pdf(i: Inputs, lang: str, chart_png: Path, target: Path) -> None:
    pdf_font()
    words = TEXT[lang]
    rows = years(i)
    width, height = landscape(A4)
    c = canvas.Canvas(str(target), pagesize=(width, height), invariant=1)
    c.setTitle(words["heading"])
    c.setAuthor("consens.io demo")
    line = (0.85, 0.85, 0.84)
    head_fill = (0.95, 0.95, 0.94)

    # Sheet 1: assumptions and results, the chart beside them.
    margin, row_h = 40, 17
    pdf_text(c, margin, height - 52, words["heading"], 15, bold=True)
    y = height - 88
    for title, entries in ((words["inputs"], [(label, value_text(i, key, kind, lang))
                                              for label, key, kind in words["rows"]]),
                           (words["results"], list(zip(words["result_rows"], results(i, rows, lang))))):
        c.setFillColorRGB(*head_fill)
        c.rect(margin, y - 5, 300, row_h, stroke=0, fill=1)
        pdf_text(c, margin + 6, y, title, 9.5, bold=True)
        y -= row_h
        for label, value in entries:
            pdf_text(c, margin + 6, y, label, 9)
            pdf_text(c, margin + 294, y, value, 9, align="right")
            c.setStrokeColorRGB(*line)
            c.setLineWidth(0.4)
            c.line(margin, y - 5, margin + 300, y - 5)
            y -= row_h
        y -= 14
    chart_width = width - margin - 370
    c.drawImage(ImageReader(str(chart_png)), 370, height - 88 - chart_width * HEIGHT / WIDTH + 12,
                width=chart_width, height=chart_width * HEIGHT / WIDTH)
    c.showPage()

    # Sheet 2: the 30 years.
    pdf_text(c, margin, height - 52, words["sheet2"], 15, bold=True)
    widths = [44, 82, 82, 82, 82, 82, 96, 120, 92]
    top = height - 84
    row_h = 14.2
    c.setFillColorRGB(*head_fill)
    c.rect(margin, top - 5, sum(widths), row_h + 4, stroke=0, fill=1)
    x = margin
    for index, (label, w) in enumerate(zip(words["columns"], widths)):
        if index == 0:
            pdf_text(c, x + 6, top, label, 8.5, bold=True)
        else:
            pdf_text(c, x + w - 6, top, label, 8.5, bold=True, align="right")
        x += w
    y = top - row_h - 4
    for row in rows:
        cells = [str(row.year), money(row.value, lang), money(row.debt, lang),
                 money(row.payment, lang) if row.year else "", money(row.owner, lang) if row.year else "",
                 money(row.rent, lang) if row.year else "", money(row.savings, lang), money(row.buying, lang),
                 money(row.lead, lang)]
        x = margin
        for index, (cell, w) in enumerate(zip(cells, widths)):
            if index == 0:
                pdf_text(c, x + 6, y, cell, 8.5)
            else:
                pdf_text(c, x + w - 6, y, cell, 8.5, align="right")
            x += w
        c.setStrokeColorRGB(*line)
        c.setLineWidth(0.3)
        c.line(margin, y - 4, margin + sum(widths), y - 4)
        y -= row_h
    c.showPage()
    c.save()


# ---- the spreadsheet itself ---------------------------------------------------
# Hand-written SpreadsheetML: two sheets, the second all formulas over the
# first, each with the value Python computed cached, so it shows before a
# program recalculates (fullCalcOnLoad makes it recalculate on opening).
INPUT_ROW = 4           # first input row on sheet 1
STAY_ROW = INPUT_ROW + 12
RESULT_ROW = STAY_ROW + 3
FIRST, LAST = 2, 2 + YEARS   # year 0 and year 30 on sheet 2


def col(index: int) -> str:
    return "ABCDEFGHI"[index]


def cell(ref: str, value=None, formula: str | None = None, style: int = 0) -> str:
    attrs = f' r="{ref}"' + (f' s="{style}"' if style else "")
    if isinstance(value, str) and formula is None:
        return f'<c{attrs} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    if isinstance(value, str):
        return f'<c{attrs} t="str"><f>{escape(formula)}</f><v>{escape(value)}</v></c>'
    body = (f"<f>{escape(formula)}</f>" if formula else "") + (f"<v>{value!r}</v>" if value is not None else "")
    return f"<c{attrs}>{body}</c>"


def sheet_xml(rows_xml: list[str], widths: list[float], freeze: bool = False) -> str:
    cols = "".join(f'<col min="{n + 1}" max="{n + 1}" width="{w}" customWidth="1"/>' for n, w in enumerate(widths))
    pane = ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
            'state="frozen"/></sheetView></sheetViews>') if freeze else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{pane}<cols>{cols}</cols><sheetData>{''.join(rows_xml)}</sheetData></worksheet>")


def xf(number: int = 0, font: int = 0, fill: int = 0, border: int = 0, align: str = "") -> str:
    applied = "".join(f' {name}="1"' for name, used in (("applyNumberFormat", number), ("applyFont", font),
                                                       ("applyFill", fill), ("applyBorder", border),
                                                       ("applyAlignment", align)) if used)
    attrs = f'numFmtId="{number}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="0"{applied}'
    return f'<xf {attrs}><alignment horizontal="{align}" wrapText="1"/></xf>' if align else f"<xf {attrs}/>"


def row_xml(number: int, cells: list[str]) -> str:
    return f'<row r="{number}">{"".join(cells)}</row>'


def workbook(i: Inputs, lang: str, target: Path) -> None:
    words = TEXT[lang]
    rows = years(i)
    s1, s2 = words["sheet1"], words["sheet2"]
    ref1 = lambda r: f"'{s1}'!$B${r}"  # noqa: E731
    key_row = {key: INPUT_ROW + n for n, (_, key, _) in enumerate(words["rows"])}
    k = lambda key: ref1(key_row[key])  # noqa: E731
    # Styles: 1 bold, 2 title, 3 money, 4 percent, 5 header, 6 whole number, 7 header right.
    sheet1 = [row_xml(1, [cell("A1", words["heading"], style=2)]),
              row_xml(INPUT_ROW - 1, [cell(f"A{INPUT_ROW - 1}", words["inputs"], style=5),
                                      cell(f"B{INPUT_ROW - 1}", "", style=5)])]
    for label, key, kind in words["rows"]:
        r = key_row[key]
        style = 3 if kind == "eur" else 4 if kind == "pct" else 6
        sheet1.append(row_xml(r, [cell(f"A{r}", label), cell(f"B{r}", getattr(i, key), style=style)]))
    annuity_month = loan(i) * (i.rate + i.repay) / 12
    owner = annuity_month + i.upkeep
    year = ahead_from(rows)
    p = lambda key: f"B{key_row[key]}"  # noqa: E731
    r0 = RESULT_ROW
    formulas = [
        (costs(i), f"{p('price')}*({p('tax')}+{p('notary')})", 3),
        (loan(i), f"{p('price')}+B{r0 + 1}-{p('equity')}", 3),
        (annuity_month, f"B{r0 + 2}*({p('rate')}+{p('repay')})/12", 3),
        (owner, f"B{r0 + 3}+{p('upkeep')}", 3),
        (owner - i.rent, f"B{r0 + 4}-{p('rent')}", 3),
        # The years buying is not yet ahead, counted: the year it pulls ahead
        # while the lead only grows (it does here). SUMPRODUCT, not an array
        # MATCH, so every spreadsheet program computes it the same.
        (year if year else words["never"],
         f"IF(SUMPRODUCT(--('{s2}'!I{FIRST}:I{LAST}<=0))>{YEARS},\"{words['never']}\","
         f"SUMPRODUCT(--('{s2}'!I{FIRST}:I{LAST}<=0)))", 6),
        (rows[i.stay].lead, f"INDEX('{s2}'!I{FIRST}:I{LAST},{p('stay')}+1)", 3),
    ]
    sheet1.append(row_xml(r0, [cell(f"A{r0}", words["results"], style=5), cell(f"B{r0}", "", style=5)]))
    for n, (label, (value, formula, style)) in enumerate(zip(words["result_rows"], formulas), start=1):
        sheet1.append(row_xml(r0 + n, [cell(f"A{r0 + n}", label, style=1 if n >= 6 else 0),
                                       cell(f"B{r0 + n}", value, formula, style)]))

    head = [cell(f"{col(n)}1", label, style=5 if n == 0 else 7) for n, label in enumerate(words["columns"])]
    sheet2 = [row_xml(1, head)]
    for row in rows:
        r = FIRST + row.year
        if row.year == 0:
            cells = [cell(f"A{r}", 0, style=6), cell(f"B{r}", row.value, f"{k('price')}", 3),
                     cell(f"C{r}", row.debt, f"'{s1}'!$B${r0 + 2}", 3),
                     cell(f"G{r}", row.savings, f"{k('equity')}", 3)]
        else:
            q = r - 1
            cells = [
                cell(f"A{r}", row.year, f"A{q}+1", 6),
                cell(f"B{r}", row.value, f"B{q}*(1+{k('value_growth')})", 3),
                cell(f"C{r}", row.debt, f"C{q}*(1+{k('rate')})-D{r}", 3),
                cell(f"D{r}", row.payment, f"MIN('{s1}'!$B${r0 + 2}*({k('rate')}+{k('repay')}),C{q}*(1+{k('rate')}))", 3),
                cell(f"E{r}", row.owner, f"D{r}+{k('upkeep')}*12*(1+{k('upkeep_growth')})^(A{r}-1)", 3),
                cell(f"F{r}", row.rent, f"{k('rent')}*12*(1+{k('rent_growth')})^(A{r}-1)", 3),
                cell(f"G{r}", row.savings, f"G{q}*(1+{k('returns')})+E{r}-F{r}", 3),
            ]
        cells += [cell(f"H{r}", row.buying, f"B{r}-C{r}", 3), cell(f"I{r}", row.lead, f"H{r}-G{r}", 3)]
        cells.sort(key=lambda text: text.split('r="', 1)[1][0])
        sheet2.append(row_xml(r, cells))

    eur = '"€"#,##0' if lang == "en" else '#,##0 "€"'
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              f'<numFmts count="2"><numFmt numFmtId="164" formatCode="{escape(eur, {chr(34): "&quot;"})}"/>'
              '<numFmt numFmtId="165" formatCode="0.0%"/></numFmts>'
              '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="14"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F0"/></patternFill></fill></fills>'
              '<borders count="2"><border/><border><bottom style="thin"><color rgb="FFBFBFBF"/></bottom></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              f'<cellXfs count="8">{xf()}'
              f'{xf(font=1)}'
              f'{xf(font=2)}'
              f'{xf(number=164)}'
              f'{xf(number=165)}'
              f'{xf(font=1, fill=2, border=1)}'
              f'{xf(number=1)}'
              f'{xf(font=1, fill=2, border=1, align="right")}'
              '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              '</styleSheet>')
    book = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(s1)}" sheetId="1" r:id="rId1"/><sheet name="{escape(s2)}" sheetId="2" r:id="rId2"/></sheets>'
            '<calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
             '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             '</Types>')
    parts = {
        "[Content_Types].xml": types, "_rels/.rels": root_rels, "xl/workbook.xml": book,
        "xl/_rels/workbook.xml.rels": rels, "xl/styles.xml": styles,
        "xl/worksheets/sheet1.xml": sheet_xml(sheet1, [38, 14]),
        "xl/worksheets/sheet2.xml": sheet_xml(sheet2, [7, 14, 14, 14, 14, 13, 16, 18, 15], freeze=True),
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            # A fixed date keeps the file's bytes, and its ETag, the same on every run.
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    agent = Inputs()
    for lang in ("en", "de"):
        png = OUT / f"buy-vs-rent.{lang}.png"
        chart(agent, lang).save(png, optimize=True)
        spreadsheet_pdf(agent, lang, png, OUT / f"buy-vs-rent.{lang}.pdf")
        workbook(agent, lang, OUT / f"buy-vs-rent.{lang}.xlsx")
    for name, inputs in (("agent (3.5 %)", agent), ("corrected (5.5 %)", replace(agent, tax=0.055)),
                         ("value +1.0 %", replace(agent, value_growth=0.01))):
        rows = years(inputs)
        print(f"{name}: purchase costs {costs(inputs):,.0f}, loan {loan(inputs):,.0f}, "
              f"loan a month {loan(inputs) * (inputs.rate + inputs.repay) / 12:,.2f}, ahead from year {ahead_from(rows)}, "
              f"lead at {inputs.stay} {rows[inputs.stay].lead:,.0f}, debt at 15 {rows[15].debt:,.0f}")
    for row in years(agent):
        if row.year in (0, 5, 9, 12, 20, 30):
            print(f"  {row.year:>2} buying {row.buying:>10,.0f} renting {row.savings:>10,.0f} lead {row.lead:>9,.0f}")
    for path in sorted(OUT.iterdir()):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
