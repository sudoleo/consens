"""Watch, share and hub pages after the Apple audit (2026-10-20).

Each test names its finding; each would fail on the code before it.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import share as share_router
from app.core.rate_limit import limiter
from app.services import check_page, og_image, source_links
from app.services import share_snapshots as snapshots
from app.services.public_markdown import render_public_markdown
from test_share_feature import make_pending

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(share_router.router)
    snapshots.invalidate_share_cache()
    with patch.object(share_router.snapshots, "list_related_shares", return_value=[]), \
            patch.object(share_router.snapshots, "find_canonical_share", return_value=None):
        yield TestClient(app)
    snapshots.invalidate_share_cache()


SHARE_ID = snapshots.generate_share_id()


def page(client, doc, *, meta=None, points=(), version=None):
    with patch.object(share_router.snapshots, "get_share", return_value=doc), \
            patch.object(share_router.snapshots, "list_watch_history", return_value=list(points)), \
            patch.object(share_router.watch_service, "get_public_watch_meta", return_value=meta), \
            patch.object(share_router.snapshots, "get_watch_version", return_value=version):
        response = client.get("/s/%s-%s" % (doc["slug"], SHARE_ID))
    assert response.status_code == 200, response.text
    return response.text


def point(day, score, run_id, month=9, **extra):
    return {"run_id": run_id, "ts": datetime(2026, month, day, 8, tzinfo=UTC), "agreement_score": score,
            "changed": False, "severity": "", "change_summary": "", "evidence_sources": [],
            "has_snapshot": False, **extra}


def doc(**overrides):
    data = make_pending()
    data.update({"status": "active", "slug": "slug"})
    data.update(overrides)
    return data


PAUSED = {"status": "paused", "interval": "weekly", "last_run_at": datetime(2026, 10, 1, 8, tzinfo=UTC),
          "created_at": datetime(2026, 7, 28, tzinfo=UTC), "accepted_run_id": "r2"}
VERSION = {"consensus_md": "The standing answer.", "sources": []}


# --- L2: a paused Watch says so ------------------------------------------

def test_a_paused_watch_leads_with_paused_not_with_a_green_unchanged(client):
    body = page(client, doc(), meta=PAUSED, points=[point(24, 64, "r1"), point(1, 66, "r2", month=10)],
                version=VERSION)
    assert "Watch · paused" in body and "checked weekly" not in body
    assert 'class="wp-state is-paused"' in body
    assert "Paused · last checked Oct 1" in body
    assert "Unchanged since" not in body
    # The facts no longer repeat it.
    assert "Checked 2 times since Sep 24</p>" in body


def test_a_paused_watch_neither_waits_nor_scores_in_its_search_line(client):
    # Zweitprüfung 16: nobody is checking, so the goal is what it WAS waiting
    # for, and the description leads with the state, never with a score.
    differences = {"differences": [{"claim": "When", "type": "contradiction", "positions": [
        {"stance": "May", "models": ["OpenAI"]}, {"stance": "June", "models": ["Gemini"]}]}],
        "models_compared": ["OpenAI", "Gemini"], "agreement": {"score": 64}}
    meta = {**PAUSED, "condition": "A launch date is announced"}
    body = page(client, doc(differences_data=differences), meta=meta,
                points=[point(24, 64, "r1"), point(1, 66, "r2", month=10)], version=VERSION)
    assert '<p class="wp-goal"><span>Was waiting for</span> A launch date is announced</p>' in body
    assert ">Waiting for<" not in body
    description = re.search(r'<meta name="description" content="([^"]*)"', body).group(1)
    assert description.startswith("Paused · last checked Oct 1 · 2 AI models answered independently")
    assert "/100" not in description and "contradiction" not in description
    # Running again, it waits again.
    active = {**meta, "status": "active", "next_run_at": datetime(2026, 10, 8, 8, tzinfo=UTC)}
    body = page(client, doc(differences_data=differences), meta=active,
                points=[point(24, 64, "r1"), point(1, 66, "r2", month=10)], version=VERSION)
    assert '<p class="wp-goal"><span>Waiting for</span> A launch date is announced</p>' in body
    description = re.search(r'<meta name="description" content="([^"]*)"', body).group(1)
    assert "/100" not in description


def test_an_active_watch_keeps_its_state_line():
    page_meta = {"is_active": True, "status": "active", "next_run": {"day": "Oct 22"},
                 "status_label": "Active", "resolution": None, "last_run": {"day": "Oct 15"}}
    points = [point(24, 64, "r1"), point(29, 66, "r2")]
    from app.services.history_view import build_history_view
    state = check_page.state_view(page_meta, build_history_view(points), check_page.drift_view(points),
                                  awaiting=False, version_kind="current", selected_run_id="")
    assert state["headline"] == "Unchanged since Sep 24" and state["tone"] == "steady"


def test_watch_summary_is_the_page_headline_for_list_and_card():
    points = [point(24, 64, "r1"), point(29, 66, "r2")]
    assert check_page.watch_summary("paused", points, last_run=datetime(2026, 10, 1, tzinfo=UTC)) == {
        "tone": "paused", "headline": "Paused · last checked Oct 1", "active": False}
    assert check_page.watch_summary("active", points)["headline"] == "Unchanged since Sep 24"
    assert check_page.watch_summary("resolved", points, resolved_at=datetime(2026, 10, 2, tzinfo=UTC))[
        "headline"] == "Resolved on Oct 2"


# --- L4: no self-citations -------------------------------------------------

OWN = "https://www.consens.io/s/what-models-b1kPgI7ycak4oLjC"


def test_a_link_back_to_consens_io_is_no_source(client):
    sources = [
        {"id": "S1", "url": "https://ampcode.com/manual", "title": "Owner's Manual - Amp"},
        {"id": "S2", "url": OWN, "title": "What models does Amp include? | consens.io"},
    ]
    body = page(client, doc(consensus_md="Amp names both models [S1]. See the Watch [S2].", sources=sources),
                meta={"status": "active", "interval": "weekly"})
    assert "consens.io/s/what-models" not in body.split("<main", 1)[1]
    # Its marker drops instead of standing as raw text.
    assert "[S2]" not in body and "#src-2" not in body
    assert 'href="#src-1"' in body


def test_own_pages_never_reach_direct_links_or_names_in_the_text():
    entries = source_links.source_entries([
        {"url": OWN, "title": "Does Gemini CLI's 1M-token context improve large repository work?"},
        {"url": "https://docs.example.com/guide/install", "title": "Install guide for the CLI tool"},
    ])
    links = source_links.key_links(entries, "As consens.io and the Example docs say ...")
    assert [link["domain"] for link in links] == ["docs.example.com"]
    assert source_links.site_mentions(entries, "consens.io says so") == []
    assert source_links.is_own_page("https://consens.io/x") and not source_links.is_own_page("https://notconsens.io/")


def test_the_watch_judge_never_sees_own_pages():
    scheduler = read("app/services/watch_scheduler.py")
    assert "evidence = source_links.without_own_pages(sources)" in scheduler
    assert "new_sources=sources" not in scheduler


# --- L12: direct links without doubles and signatures -------------------------

def test_direct_links_drop_site_signatures_and_doubled_titles():
    entries = source_links.source_entries([
        {"url": "https://www.anthropic.com/news/claude-opus-5-5", "title": "Introducing Claude Opus 5.5 \\ Anthropic"},
        {"url": "https://help.openai.com/en/articles/linked-apps", "title": "Using linked apps with your plan - ChatGPT"},
        {"url": "https://ampcode.com/manual", "title": "Owner's Manual - Amp"},
        {"url": "https://github.com/sourcegraph/amp/blob/main/CHANGELOG.md", "title": "amp/CHANGELOG.md at main · sourcegraph/amp · GitHub"},
        {"url": "https://gitlab.com/mirror/amp/blob/main/CHANGELOG.md", "title": "amp/CHANGELOG.md at main · sourcegraph/amp"},
    ])
    titles = [link["title"] for link in source_links.key_links(entries, "", limit=8)]
    assert "Introducing Claude Opus 5.5" in titles
    assert "Using linked apps with your plan" in titles
    assert "Owner's Manual" in titles
    assert titles.count("amp/CHANGELOG.md at main · sourcegraph/amp") == 1


# --- L8: titles at a word boundary -----------------------------------------------

def test_titles_end_at_a_word_and_say_they_were_cut(client):
    question = "Does the new ChatGPT-linked Amp subscription actually include GPT-6 Astra in High mode for agents?"
    body = page(client, doc(question=question))
    title = body.split("<title>", 1)[1].split("</title>", 1)[0]
    assert title.endswith("… | consens.io")
    assert "includ |" not in title and len(title.split(" | ")[0]) <= 70
    assert share_router.clip_words("short question", 70) == "short question"
    assert share_router.clip_words("a" * 30 + " " + "b" * 50, 60) == "a" * 30 + "…"


# --- I11, L15: model names ------------------------------------------------------------

def test_the_consensus_chip_names_the_model_not_its_id():
    view = snapshots.consensus_model_view("gpt-5.6-luna")
    assert view["model"] == "GPT-5.6 Luna" and view["provider"] == "OpenAI"


def test_a_model_name_that_carries_its_family_is_not_prefixed_twice():
    view = snapshots.consulted_models_view(["Google Gemini: gemini-3.5-flash-lite", "OpenAI: gpt-5.6-luna"])
    assert [entry["display"] for entry in view] == ["Gemini 3.5 Flash-Lite", "OpenAI GPT-5.6 Luna"]


def test_judge_letters_become_the_families_the_page_names():
    differences = [{
        "claim": "Model C claims GPT-6 Astra, whereas Models A and B say GPT-5.6 Sol",
        "type": "contradiction",
        "positions": [
            {"stance": "Model C states High mode uses GPT-6 Astra.", "models": ["DeepSeek"]},
            {"stance": "Models A and B state High mode uses GPT-5.6 Sol.", "models": ["OpenAI", "Gemini"]},
        ],
        "verify": "Ask Model D.",
    }]
    named = check_page.named_differences(differences)[0]
    assert named["claim"] == "DeepSeek claims GPT-6 Astra, whereas OpenAI and Gemini say GPT-5.6 Sol"
    assert named["positions"][0]["stance"] == "DeepSeek states High mode uses GPT-6 Astra."
    # The family line would only repeat the stance.
    assert named["positions"][0]["models"] == [] and named["positions"][1]["models"] == []
    # A letter nobody can place keeps its text.
    assert named["verify"] == "Ask Model D."


def test_judge_letters_are_never_paired_by_list_order():
    # Zweitprüfung 14: the judge listed A=DeepSeek and B=OpenAI as
    # ["OpenAI", "DeepSeek"]; pairing by order made the next difference say
    # "DeepSeek claims it ships in May" although OpenAI did.
    differences = [
        {"claim": "Models A and B say June, Model C says May", "positions": [
            {"stance": "Models A and B say it ships in June.", "models": ["OpenAI", "DeepSeek"]},
            {"stance": "Model C says it ships in May.", "models": ["Gemini"]},
        ]},
        {"claim": "Model B alone names a date", "positions": [
            {"stance": "Model B claims it ships in May.", "models": ["OpenAI"]},
            {"stance": "Model A gives no date, unlike Model B.", "models": ["DeepSeek"]},
        ], "verify": "Compare Model A with Model C."},
    ]
    first, second = check_page.named_differences(differences)
    assert second["positions"][0]["stance"] == "OpenAI claims it ships in May."
    assert second["positions"][1]["stance"] == "DeepSeek gives no date, unlike OpenAI."
    assert second["verify"] == "Compare DeepSeek with Gemini."
    # Each letter is known on its own now, so each gets its own family.
    assert first["positions"][0]["stance"] == "DeepSeek and OpenAI say it ships in June."

    # Only the pair is known: the pair is named, a single letter of it is not.
    pair = [{"claim": "Ask Model A", "positions": [
        {"stance": "Models A and B say June.", "models": ["OpenAI", "DeepSeek"]},
    ]}]
    named = check_page.named_differences(pair)[0]
    assert named["positions"][0]["stance"] == "OpenAI and DeepSeek say June."
    assert named["claim"] == "Ask Model A"

    # Evidence that contradicts itself names nobody; a label later in a
    # stance ("unlike Model B") is about the other side and no evidence.
    conflict = [{"claim": "Model B says May", "positions": [
        {"stance": "Model B says May.", "models": ["OpenAI"]},
        {"stance": "Model B says June.", "models": ["Gemini"]},
        {"stance": "It says July, unlike Model C.", "models": ["Grok"]},
    ]}]
    named = check_page.named_differences(conflict)[0]
    assert named["claim"] == "Model B says May"
    assert named["positions"][2]["stance"] == "It says July, unlike Model C."


# --- L13: the card of a Watch -----------------------------------------------------------

def test_a_watch_card_tells_its_state_not_a_score(monkeypatch):
    drawn = {}

    def card(cache_id, **kwargs):
        drawn.update(kwargs, cache_id=cache_id)
        return b"png"

    monkeypatch.setattr(og_image, "card_png", card)
    assert og_image.watch_card_png("abc", question="Q?", state_line="Paused · last checked Oct 1",
                                   model_count=3) == b"png"
    assert drawn["dateline"] == "Watch · Paused · last checked Oct 1"
    assert "score" not in drawn and drawn["facts"] == ["3 AI models"]


# --- markers at the end of a sentence ----------------------------------------------------

def test_a_group_of_markers_moves_behind_the_point_as_one():
    sources = [{"id": "S1", "url": "https://a.example/x", "title": "A"},
               {"id": "S2", "url": "https://b.example/y", "title": "B"}]
    html = render_public_markdown("Claim [S1][S2].", sources)
    assert "Claim.<a" in html and "</a>.<a" not in html
    # "!" before a link would make it a Markdown image.
    html = render_public_markdown("Wow [S1]!", sources)
    assert "<img" not in html and "Wow!<a" in html


# --- templates: folded from the server, one disclosure, one colour --------------------------

def test_long_questions_and_source_lists_arrive_folded():
    parts = read("templates/partials/check_page.html")
    assert 'class="wp-question share-question{% if clamp %} is-clamped{% endif %}' in parts
    assert '{% set folded = sources | length > 5 %}' in parts
    assert 'share-sources{% if folded %} is-collapsed is-short{% endif %}' in parts
    share = read("templates/share.html")
    assert 'class="share-sources{% if sources | length > 8 %} is-collapsed{% endif %}"' in share
    assert "asset_url('/static/js/check-page.js')" in share
    # The duplicated inline copies are gone from the share page.
    assert "function measure()" not in share and ".share-source-favicon\").forEach" not in share


def test_every_fold_is_the_same_disclosure_and_the_curve_has_one_amber():
    parts = read("templates/partials/check_page.html")
    assert parts.count('class="wp-disclosure') >= 3
    assert '<details class="wp-more wp-disclosure">' in parts
    assert 'watch-chart-point{% if changed %} is-change{% endif %}{% if not scored %} is-unscored{% endif %}' in parts
    css = read("static/css/public-pages.css")
    assert ".watch-chart-point.is-change { fill: var(--partial)" in css
    assert ".wp-event.is-quiet::after { border: 2px solid var(--muted)" in css


def test_the_newest_change_is_not_printed_twice(client):
    move = "The answer now says High mode runs GPT-6 Astra."
    points = [point(24, 64, "r1"), point(29, 41, "r2", changed=True, severity="major", cause="new_evidence",
                                         change_summary=move)]
    meta = {"status": "active", "interval": "weekly", "accepted_run_id": "r2", "last_successful_run_id": "r2"}
    with patch.object(share_router.snapshots, "get_watch_version",
                      return_value={"consensus_md": "New", "sources": []}):
        with patch.object(share_router.snapshots, "get_share", return_value=doc()), \
                patch.object(share_router.snapshots, "list_watch_history", return_value=points), \
                patch.object(share_router.watch_service, "get_public_watch_meta", return_value=meta):
            body = client.get("/s/slug-%s" % SHARE_ID).text
    assert 'class="wp-state is-moved"' in body
    # Once as text (the chart point names it for screen readers only).
    assert body.count(">" + move + "<") == 1


def test_the_phone_layout_puts_direct_links_in_a_row_and_targets_at_44px():
    css = read("static/css/public-pages.css")
    phone = css.split("Watch, Topic and share pages after the Apple audit", 1)[1]
    assert ".wp-shell .wp-links-list {\n    display: flex;" in phone
    assert "min-height: 44px;" in phone
    assert ".topic-shell .wp-links-list" not in css


# --- L17: a live Watch from the landing, only if there is one ----------------------

class _Snap:
    def __init__(self, data):
        self._data, self.exists = data, data is not None

    def to_dict(self):
        return dict(self._data or {})


class _Query:
    def __init__(self, rows, filters=()):
        self.rows, self.filters = rows, filters

    def where(self, field, op, value):
        return _Query(self.rows, self.filters + ((field, value),))

    def limit(self, _n):
        return self

    def stream(self):
        return [_Snap(row) for row in self.rows if all(row.get(f) == v for f, v in self.filters)]

    def document(self, doc_id):
        rows = {row.get("_id"): row for row in self.rows}
        return type("Ref", (), {"get": lambda _self: _Snap(rows.get(doc_id))})()


class _Db:
    def __init__(self, watches, shares):
        self.tables = {snapshots.WATCHES_COLLECTION: watches, snapshots.SHARES_COLLECTION: shares}

    def collection(self, name):
        return _Query(self.tables[name])


def test_the_landing_links_a_live_watch_and_never_a_paused_one():
    live, paused = snapshots.generate_share_id(), snapshots.generate_share_id()
    shares = [
        {"_id": live, "status": "active", "visibility": "public", "slug": "live-question", "indexed": True},
        {"_id": paused, "status": "active", "visibility": "public", "slug": "paused-question", "indexed": True},
    ]
    watches = [
        {"share_id": paused, "status": "paused", "visibility": "public",
         "last_run_at": datetime(2026, 10, 19, tzinfo=UTC)},
        {"share_id": live, "status": "active", "visibility": "public",
         "last_run_at": datetime(2026, 10, 15, tzinfo=UTC)},
    ]
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == snapshots.share_path("live-question", live)
    # All paused, as right now: no link at all, no stand-in.
    watches[1]["status"] = "paused"
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == ""

    landing = read("templates/landing.html")
    assert '{% if live_watch_path %}<a class="lp-watch-live" href="{{ live_watch_path }}"' in landing


def test_the_landing_never_links_a_watch_page_nobody_curated():
    # "Public" means anyone with the link; only an indexed page may stand on
    # the start page (Zweitprüfung B1). An uncurated live Watch is no stand-in.
    curated, uncurated = snapshots.generate_share_id(), snapshots.generate_share_id()
    shares = [
        {"_id": curated, "status": "active", "visibility": "public", "slug": "curated-question", "indexed": True},
        {"_id": uncurated, "status": "active", "visibility": "public", "slug": "someones-own-question"},
    ]
    watches = [
        {"share_id": uncurated, "status": "active", "visibility": "public",
         "last_run_at": datetime(2026, 10, 20, tzinfo=UTC)},
        {"share_id": curated, "status": "paused", "visibility": "public",
         "last_run_at": datetime(2026, 10, 15, tzinfo=UTC)},
    ]
    # The curated Watch is paused, the only live one is nobody's showcase.
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == ""
    shares[1]["indexed"] = False
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == ""
    # A curated live Watch wins although the uncurated one ran later.
    watches[1]["status"] = "active"
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == snapshots.share_path("curated-question", curated)
    # Unindexed after curation (or blocked): gone from the landing as well.
    shares[0]["indexed"] = False
    assert snapshots.live_watch_path(db=_Db(watches, shares)) == ""


# --- I14, I4: one grid, one material, no sideways panning ---------------------------

def test_every_public_page_sits_on_one_grid_of_one_material():
    tokens = read("static/css/public-tokens.css")
    assert "--page-width: min(var(--maxw), calc(100% - 2 * var(--page-gutter)));" in tokens
    assert ":root { --page-gutter: 16px; }" in read("static/css/public-nav.css")
    pages, landing = read("static/css/public-pages.css"), read("static/css/landing.css")
    for rule in (".page-shell {\n  width: var(--page-width);", ".footer-inner {\n  width: var(--page-width);",
                 ".wp-shell { width: var(--page-width);"):
        assert rule in pages, rule
    assert ".lp-shell {\n  width: var(--page-width);" in landing
    assert "calc(100% - 44px)" not in landing and "min(860px, calc(100% - 48px))" not in pages
    shell = read("static/css/public-shell.css")
    flat = shell.split(".legal-panel {\n  border: 0;\n  border-top: 1px solid var(--line-soft);", 1)
    assert len(flat) == 2 and "background: transparent;" in flat[1].split("}", 1)[0]
    notice = shell.split(".notice {", 1)[1].split("}", 1)[0]
    assert "border-left: 0;" in notice and "background: transparent;" in notice
    assert "body { overflow-x: clip; }" in tokens


def test_share_page_differences_are_the_apps_cards():
    # check_page.difference_cards mirrors buildDifferenceCards (2026-10-16):
    # critical first, two or more smaller ones folded behind them, the
    # answer's side first, one side per claim, Markdown rendered.
    from app.services.public_markdown import render_inline_markdown

    def side(stance, models, **extra):
        return {"stance": stance, "models": models, **extra}

    differences = [
        {"claim": "Board size", "type": "contradiction", "severity": "minor",
         "positions": [side("Four members.", ["OpenAI"]), side("Five members.", ["Kimi"])]},
        {"claim": "Who leads", "type": "contradiction", "severity": "major", "verify": "Check the imprint.",
         "positions": [side("Weber leads.", ["DeepSeek"], quote="**Prof. Weber** leads"),
                       side("Schneider leads.", ["Gemini", "Qwen"], in_answer=True),
                       side("schneider leads", ["GLM"])]},
        {"claim": "Focus", "type": "emphasis", "positions": [side("Risk first.", ["Grok"])]},
    ]
    view = check_page.difference_cards(differences, snapshots.PROVIDERS_BY_LABEL, render_inline_markdown)

    [critical] = view["cards"]
    assert critical["tag"] == "Critical" and critical["dot"] == "is-crit" and critical["versus"]
    assert [s["stance_html"] for s in critical["sides"]] == ["Schneider leads.", "Weber leads."]
    assert critical["sides"][0]["in_answer"] and [m["name"] for m in critical["sides"][0]["models"]] == ["Gemini", "Qwen", "GLM"]
    assert critical["sides"][1]["quote_html"] == "<strong>Prof. Weber</strong> leads"
    assert critical["sides"][1]["models"][0]["icon"].startswith("/static/icons/chat_icons/deepseek")
    assert [card["tag"] for card in view["smaller"]] == ["Minor", "Emphasis"]
    assert not view["smaller"][1]["versus"]

    # One smaller difference does not fold.
    single = check_page.difference_cards(differences[:2], snapshots.PROVIDERS_BY_LABEL, render_inline_markdown)
    assert [card["tag"] for card in single["cards"]] == ["Critical", "Minor"] and single["smaller"] == []


def test_a_quote_cut_from_a_bold_run_shows_no_stray_stars():
    # Live 2026-10-22: "Dr. Sebastian Reddemann**, CEO" -- the judge cut the
    # quote inside "**…**", and the closing mark stood in the card.
    from app.services.public_markdown import render_inline_markdown

    assert render_inline_markdown("Dr. Sebastian Reddemann**, CEO") == "Dr. Sebastian Reddemann, CEO"
    assert render_inline_markdown("**Board** of four") == "<strong>Board</strong> of four"
    assert render_inline_markdown("`a**b`") == "<code>a**b</code>"
