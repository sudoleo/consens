"""The benchmark charts and the tables that speak for them (a11y audit P1).

The bars draw their numbers from CSS variables and name their models in a
separate row, so a screen reader got neither. Each chart is aria-hidden now
and a visually hidden table carries the same numbers. This test keeps the two
from drifting apart when the numbers change.
"""

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def text_of(fragment: str) -> str:
    return " ".join(re.sub(r"<br\s*/?>", " ", re.sub(r"<(?!br)[^>]+>", "", fragment)).split())


def table_rows(table: str) -> list[tuple[str, list[str]]]:
    rows = []
    for row in re.findall(r"<tr>(.*?)</tr>", table, flags=re.S):
        head = re.search(r'<th scope="row">(.*?)</th>', row)
        if head:
            rows.append((text_of(head.group(1)), [text_of(cell) for cell in re.findall(r"<td>(.*?)</td>", row)]))
    return rows


def labelled_table(page: str, title_id: str) -> str:
    match = re.search(r'<div class="bench-sr"><table aria-labelledby="' + title_id + r'">(.*?)</table></div>', page, flags=re.S)
    assert match, title_id
    return match.group(1)


@pytest.mark.parametrize("title_id", ["benchOverallTitle", "benchSplitTitle"])
def test_each_chart_reads_as_a_table_with_its_own_numbers(title_id):
    page = (TEMPLATES / "benchmark.html").read_text(encoding="utf-8")
    start = page.index(f'id="{title_id}"')
    chart = page[page.rindex('<div class="bench-chart', 0, start):page.index("</table>", start)]
    assert f'aria-labelledby="{title_id}"' in chart.split(">", 1)[0]
    for part in ("bench-plot", "bench-xrow", "bench-legend"):
        assert f'<div class="{part}" aria-hidden="true">' in chart, part
    bars = re.findall(r'--val:([\d.]+); --lo:([\d.]+); --hi:([\d.]+)', chart)
    # The majority vote's label starts with its Σ glyph.
    labels = [text_of(re.sub(r'<span class="bench-vote">.*?</span>', "", label))
              for label in re.findall(r'<div class="bench-xlabel[^"]*">(.*?)</div>', chart, flags=re.S)]
    rows = table_rows(labelled_table(page, title_id))
    assert len(bars) == len(labels) == len(rows) == 8
    for (value, low, high), label, (name, cells) in zip(bars, labels, rows):
        assert name.startswith(label), (name, label)
        assert cells == [f"{value}%", f"{low}–{high}%"], (name, cells)


@pytest.mark.parametrize("template,title_id", [("benchmark.html", "benchMiniTitle"), ("landing.html", "lpBenchMiniTitle")])
def test_the_small_chart_reads_as_a_table_too(template, title_id):
    page = (TEMPLATES / template).read_text(encoding="utf-8")
    start = page.index(f'id="{title_id}"')
    chart = page[start:page.index("</table>", start)]
    assert '<div class="bench-mini-plot" aria-hidden="true">' in chart
    assert '<div class="bench-mini-icons" aria-hidden="true">' in chart
    values = re.findall(r"--v:([\d.]+)", chart)
    models = re.findall(r'<img [^>]*alt="([^"]+)"', chart)
    rows = table_rows(labelled_table(page, title_id))
    assert len(values) == len(models) == len(rows) == 7
    for value, model, (name, cells) in zip(values, models, rows):
        assert name.startswith(model), (name, model)
        assert cells == [f"{value}%"], (name, cells)
