"""The demo's files and the numbers its texts quote come from one model.

static/demo.js plays a turn in which the agent calculates whether to buy or
keep renting a flat, shares a chart and a spreadsheet (static/demo/, written
by scripts/demo_assets.py) and its reviewers mark a mistake that flips the
result. Every number the answer and the notes quote must be the model's, and
the files the demo loads must be there.
"""
import importlib.util
import json
import sys
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.dom import minidom

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEMO = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
LANDING = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
HOME_GERMAN = json.loads((ROOT / "app" / "i18n" / "de" / "page-home.json").read_text(encoding="utf-8"))


def _assets():
    spec = importlib.util.spec_from_file_location("demo_assets", ROOT / "scripts" / "demo_assets.py")
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their module up while they are made.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_answer_and_the_notes_quote_the_model():
    assets = _assets()
    agent = assets.Inputs()
    rows = assets.years(agent)
    # The agent's calculation: purchase costs, loan, its monthly payments.
    assert round(assets.costs(agent)) == 17_050
    assert "€17,050 in total" in DEMO
    assert round(assets.loan(agent) * (agent.rate + agent.repay) / 12) == 1_200
    assert "€1,200 for the loan" in DEMO and "€1,320 a month" in DEMO and "the other €395" in DEMO
    # Buying pulls ahead in year 9 and leads by about €9,200 after 12 years.
    assert assets.ahead_from(rows) == 9
    assert round(rows[agent.stay].lead, -2) == 9_200
    assert "Buying pulls ahead in year 9, so over your 12 years it comes out about €9,200 in front." in DEMO
    assert abs(rows[agent.stay].lead) / rows[agent.stay].buying < 0.05
    # The wrong note: with Saxony's 5.5 % only from year 13.
    corrected = replace(agent, tax=0.055)
    assert round(assets.costs(corrected)) == 23_250
    assert assets.ahead_from(assets.years(corrected)) == 13
    assert "That makes the purchase costs €23,250, and buying only pulls ahead in year 13" in DEMO
    # The doubtful note: with 1 % a year from year 20.
    assert assets.ahead_from(assets.years(replace(agent, value_growth=0.01))) == 20
    assert "with 1% a year, buying only pulls ahead in year 20" in DEMO
    # The incomplete note: what is owed once the 15 fixed years end.
    assert round(rows[15].debt, -3) == 157_000
    assert "About €157,000 is still owed then" in DEMO


def test_the_files_the_demo_loads_are_there():
    folder = ROOT / "static" / "demo"
    for lang in ("en", "de"):
        for ending in ("png", "pdf", "xlsx"):
            path = folder / f"buy-vs-rent.{lang}.{ending}"
            assert path.is_file() and path.stat().st_size > 1000, path
            assert f"/static/demo/buy-vs-rent.${{lang}}.{ending}" in DEMO
        assert (folder / f"buy-vs-rent.{lang}.pdf").read_bytes().startswith(b"%PDF")
        # The chart's field keeps the PNG's shape until it arrives (has-size).
        with Image.open(folder / f"buy-vs-rent.{lang}.png") as chart:
            assert f"width: {chart.width}, height: {chart.height}," in DEMO
        # A real spreadsheet: every part is XML, the 30 years are formulas.
        with zipfile.ZipFile(folder / f"buy-vs-rent.{lang}.xlsx") as book:
            for name in book.namelist():
                minidom.parseString(book.read(name))
            years = book.read("xl/worksheets/sheet2.xml").decode("utf-8")
            assert years.count("<f>") > 200


def test_the_landing_page_draws_the_models_chart():
    """Scene 02 of the landing page draws the chart as markup. The partial is
    what the model writes, and each of its labels has the model's German."""
    assets = _assets()
    agent = assets.Inputs()
    rows = assets.years(agent)
    partial = (ROOT / "templates" / "partials" / "demo_chart_mockup.html").read_text(encoding="utf-8")
    assert partial == assets.mock_chart(agent), "run scripts/demo_assets.py"
    assert '{% include "partials/demo_chart_mockup.html" %}' in LANDING
    # The lines end where the picture's do, and cross in the model's year.
    assert f'data-crossing="{assets.ahead_from(rows) / assets.YEARS:.3f}"' in partial
    assert f'data-stay="{agent.stay / assets.YEARS:.3f}"' in partial
    english, german = assets.TEXT["en"], assets.TEXT["de"]
    labels = {english[key]: german[key] for key in ("buying", "renting")}
    labels[english["ahead"].format(year=9)] = german["ahead"].format(year=9)
    labels[english["stay"].format(years=agent.stay)] = german["stay"].format(years=agent.stay)
    labels[f"{assets.YEARS} {english['years'].lower()}"] = f"{assets.YEARS} {german['years']}"
    for value in (assets.MOCK_TOP // 2, assets.MOCK_TOP, rows[-1].buying, rows[-1].savings):
        labels[assets.thousands(value, "en")] = assets.thousands(value, "de")
    for label, translation in labels.items():
        assert f">{label}</div>" in partial, label
        assert HOME_GERMAN[label] == translation, label
    # The words beside the picture, for screen readers.
    assert (f"after {assets.YEARS} years buying stands at {assets.thousands(rows[-1].buying, 'en')}, "
            f"renting at {assets.thousands(rows[-1].savings, 'en')}.") in LANDING


def test_the_landing_page_prints_the_models_years():
    """The command of scene 02 prints years of the model, the ones the demo
    prints (DEMO_AGENT_YEARS), in the program's format."""
    rows = _assets().years(_assets().Inputs())
    for year in (9, 12, 30):
        buying, renting = round(rows[year].buying), round(rows[year].savings)
        assert f"[{year}, {buying}, {renting}]" in DEMO
        cells = (year, f"{buying:,}", f"{renting:,}", f"{buying - renting:,}")
        assert "".join(f"<span>{cell}</span>" for cell in cells) in LANDING, year
