"""Watch-Seiten führen direkt zu den Quellen (source_links.py, seit 2026-10-12).

Direktlinks über der Antwort und die Namen der Quellen im Text als Links:
Navigation, kein Satz-für-Satz-Beleg -- die Synthese schreibt bewusst keine
S-Verweise (docs/source-verification.md).
"""

import re
import unittest
from unittest.mock import patch

from app.services import source_links
from app.services.public_markdown import render_public_markdown

REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZ"


def source(url, title, domain, site, direct=True):
    return {"url": url, "title": title, "domain": domain, "site": site, "is_direct": direct}


SHOE_SOURCES = [
    source("https://www.idealo.de/preisvergleich/OffersOfProduct/205798312",
           "Adidas Adizero Adios Pro 4 ab 149,95 € - idealo", "idealo.de", "idealo"),
    source(REDIRECT + "1", "idealo.de", "idealo.de", "idealo", direct=False),
    source(REDIRECT + "2", "billiger.de", "billiger.de", "billiger", direct=False),
    source(REDIRECT + "3", "adidas.com", "adidas.com", "adidas", direct=False),
    source("https://geizhals.de/adidas-adizero-adios-pro-4-herren-v189512.html",
           "adidas Adizero Adios Pro 4 (Herren) ab € 124,95", "geizhals.de", "geizhals"),
    source("https://mode.ladendirekt.de/herren/produkte/adizero-adios-pro",
           "Preisvergleich für Adizero Adios Pro 4 Laufschuh", "mode.ladendirekt.de", "ladendirekt"),
    source("https://top4running.de/p/adidas-adizero-adios-pro-4-m-kj0803",
           "Laufschuhe adidas Adizero Adios Pro 4 - Top4Running.de", "top4running.de", "top4running"),
    source("https://21run.com/adidas-adizero-adios-pro-4-herren-kj6244",
           "adidas Adizero Adios Pro 4 Herren", "21run.com", "21run"),
    source("https://www.example.org/", "Example", "example.org", "example"),
]
SHOE_ANSWER = (
    "Für einen neuen **Adidas Adizero Adios Pro 4** ist das schwierig; billiger wird es selten.\n\n"
    "1. **Preisalarme bei Idealo und Geizhals** setzen.\n"
    "2. Regelmäßig bei 21run, Top4Running und adidas prüfen.\n"
)


class KeyLinkTests(unittest.TestCase):
    def test_named_shops_first_one_page_per_domain(self):
        links = source_links.key_links(SHOE_SOURCES, SHOE_ANSWER)
        self.assertEqual([link["domain"] for link in links],
                         ["idealo.de", "geizhals.de", "top4running.de", "21run.com"])
        # The product page, not the bare redirect of the same shop.
        self.assertTrue(links[0]["url"].startswith("https://www.idealo.de/preisvergleich/"))
        # The site name the domain line already shows is cut from the title.
        self.assertEqual(links[2]["title"], "Laufschuhe adidas Adizero Adios Pro 4")
        self.assertEqual(SHOE_SOURCES[6]["title"], "Laufschuhe adidas Adizero Adios Pro 4 - Top4Running.de")

    def test_a_deep_page_with_a_real_title_counts_even_unnamed(self):
        job = [
            source("https://www.uni-hannover.de/jobs/id/8689",
                   "Wissenschaftliche Mitarbeit (Promotionsstelle) in der Fachgruppe",
                   "uni-hannover.de", "uni-hannover"),
            source("https://www.hs-hannover.de/", "Hochschule Hannover", "hs-hannover.de", "hs-hannover"),
            source(REDIRECT + "9", "stepstone.de", "stepstone.de", "stepstone", direct=False),
        ]
        links = source_links.key_links(job, "Die Leibniz Universität Hannover sucht eine Promotionsstelle.")
        # A homepage or a redirect only comes when the answer names it.
        self.assertEqual([link["domain"] for link in links], ["uni-hannover.de"])
        self.assertEqual(source_links.key_links([], "text"), [])

    def test_titles_lose_only_the_site_name(self):
        title = source_links.display_title
        self.assertEqual(title({"title": "Results - NBC Sports", "site": "nbcsports", "domain": "nbcsports.com"}), "Results")
        self.assertEqual(title({"title": "Stellen | Bewerbungsportal Hochschule Hannover", "site": "hs-hannover",
                                "domain": "karriere.hs-hannover.de"}), "Stellen | Bewerbungsportal Hochschule Hannover")
        self.assertEqual(title({"title": "Plan - A", "site": "idealo", "domain": "idealo.de"}), "Plan - A")
        self.assertEqual(title({"title": '"Wissenschaftliche Mitarbeit', "site": "x", "domain": "x.de"}),
                         "Wissenschaftliche Mitarbeit")
        self.assertEqual(title({"title": "", "site": "x", "domain": "x.de"}), "x.de")


class MentionTests(unittest.TestCase):
    def test_names_in_the_answer_with_their_best_page(self):
        mentions = source_links.site_mentions(SHOE_SOURCES, SHOE_ANSWER)
        self.assertEqual([(m["name"], m["domain"]) for m in mentions], [
            ("Idealo", "idealo.de"), ("Geizhals", "geizhals.de"),
            ("21run", "21run.com"), ("Top4Running", "top4running.de"),
        ])
        self.assertTrue(mentions[0]["url"].startswith("https://www.idealo.de/preisvergleich/"))

    def test_common_words_redirects_and_word_chains_are_no_mention(self):
        # "billiger" is a word here, adidas.com only a redirect, "Adidas-Größe" a chain.
        self.assertEqual(source_links.site_mentions(SHOE_SOURCES, "Es wird billiger. Adidas-Größe 44."), [])
        lower = [source("https://www.idealo.de/p/1", "Product page title", "idealo.de", "idealo")]
        self.assertEqual(source_links.site_mentions(lower, "ein idealo ist kein Name"), [])
        self.assertEqual(source_links.site_mentions(lower, "Siehe idealo.de dazu.")[0]["name"], "idealo.de")


class RenderTests(unittest.TestCase):
    def render(self, md, links=()):
        return render_public_markdown(md, [], site_links=list(links))

    def test_the_first_mention_becomes_a_link_with_its_favicon(self):
        html = self.render(SHOE_ANSWER, source_links.site_mentions(SHOE_SOURCES, SHOE_ANSWER))
        refs = re.findall(r'<a href="([^"]+)" class="wp-ref" target="_blank" rel="[^"]+">'
                          r'<img class="wp-ref-icon" src="/api/topics/favicon\?d=([^"]+)"[^>]*>([^<]+)</a>', html)
        self.assertEqual([(domain, name) for _url, domain, name in refs], [
            ("idealo.de", "Idealo"), ("geizhals.de", "Geizhals"),
            ("21run.com", "21run"), ("top4running.de", "Top4Running"),
        ])
        # The prose is untouched apart from the links.
        self.assertIn("Preisalarme bei ", html)
        self.assertEqual(html.count("Idealo"), 1)

    def test_only_text_outside_links_and_code_and_only_once(self):
        link = {"name": "Idealo", "url": "https://www.idealo.de/p/1", "domain": "idealo.de"}
        html = self.render("`Idealo` und [Idealo hier](https://idealo.de/x), dann Idealo und Idealo.", [link])
        self.assertIn("<code>Idealo</code>", html)
        self.assertEqual(html.count('href="https://www.idealo.de/p/1"'), 1)

    def test_outbound_links_of_the_answer_share_the_look(self):
        html = self.render("**Link:** [uni-hannover.de/jobs/id/8689](https://www.uni-hannover.de/jobs/id/8689) "
                           "und [Google](" + REDIRECT + ") und [Quelle](#src-1).")
        self.assertIn('class="wp-ref" target="_blank"', html)
        self.assertIn('favicon?d=uni-hannover.de', html)
        # A redirect shows no foreign favicon; anchors stay plain.
        self.assertNotIn("favicon?d=vertexaisearch", html)
        self.assertEqual(html.count('class="wp-ref"'), 1)

    def test_share_pages_without_site_links_are_unchanged(self):
        html = render_public_markdown("Bei Idealo, siehe [Seite](https://www.idealo.de/p/1).", [])
        self.assertNotIn("wp-ref", html)
        self.assertNotIn("<img", html)

    def test_markdown_cannot_smuggle_attributes(self):
        html = self.render('<a class="wp-ref" href="javascript:alert(1)">x</a> <img src=x onerror=alert(1)>')
        # Raw HTML in the answer stays text (html=False); no tag gets through.
        self.assertNotIn("<a class", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img src=x onerror", html)


class RedirectTests(unittest.TestCase):
    def test_redirects_become_the_pages_they_point_to(self):
        from app.services import source_redirects

        sources = [
            {"id": "S1", "url": REDIRECT + "1", "title": "billiger.de"},
            {"id": "S2", "url": REDIRECT + "2", "title": "adidas.com"},
            {"id": "S3", "url": "https://geizhals.de/p", "title": "Geizhals"},
        ]
        targets = {REDIRECT + "1": "https://www.billiger.de/baseproducts/119030-adidas-adizero-adios-pro-4",
                   REDIRECT + "2": ""}  # expired: Google answers 404
        resolved = source_redirects.resolve_sources(sources, fetch=lambda url: targets.get(url, ""))
        self.assertEqual(resolved[0]["url"], targets[REDIRECT + "1"])
        self.assertEqual(resolved[1]["url"], REDIRECT + "2")  # kept, nothing lost
        self.assertIs(resolved[2], sources[2])
        self.assertEqual(sources[0]["url"], REDIRECT + "1")  # the input is not changed

    def test_only_googles_host_and_never_another_redirect(self):
        from app.services import source_redirects

        asked = []

        def fetch(url):
            asked.append(url)
            return REDIRECT + "loop"

        self.assertEqual(source_redirects.resolve_urls(
            ["https://evil.example/r", "http://vertexaisearch.cloud.google.com/x", REDIRECT + "a"], fetch=fetch,
        ), {})
        self.assertEqual(asked, [REDIRECT + "a"])
        # Without a test fetch nothing goes out in unit tests.
        self.assertEqual(source_redirects.resolve_urls([REDIRECT + "b"]), {})

    def test_nested_evidence_is_rewritten_too(self):
        from app.services import source_redirects

        value = {"history_points": [{"evidence_sources": [{"url": REDIRECT + "1", "title": "x"}]}],
                 "note": REDIRECT + "1"}
        self.assertEqual(source_redirects.collect_redirects(value), [REDIRECT + "1"])
        new, changed = source_redirects.replace_urls(value, {REDIRECT + "1": "https://x.de/a"})
        self.assertTrue(changed)
        self.assertEqual(new["history_points"][0]["evidence_sources"][0]["url"], "https://x.de/a")
        self.assertEqual(new["note"], REDIRECT + "1")  # only url fields
        self.assertEqual(source_redirects.replace_urls(value, {}), (value, False))


class ExpiredTests(unittest.TestCase):
    def test_only_a_definite_404_counts_as_expired(self):
        from app.services import source_redirects

        codes = {REDIRECT + "dead": 404, REDIRECT + "gone": 410, REDIRECT + "busy": 429, REDIRECT + "down": 503}

        def status(url):
            if url == REDIRECT + "timeout":
                raise TimeoutError("slow")
            return codes[url]

        expired = source_redirects.expired_urls([*codes, REDIRECT + "timeout", "https://x.de/404"], status=status)
        self.assertEqual(expired, {REDIRECT + "dead", REDIRECT + "gone"})
        self.assertEqual(source_redirects.expired_urls([REDIRECT + "dead"]), set())  # no network in tests

    def test_dead_links_are_dropped_with_their_numbers(self):
        from app.services import source_redirects

        value = {
            "sources": [{"id": "S1", "url": REDIRECT + "dead"}, {"id": "S2", "url": "https://x.de/a"}],
            "history_points": [{"evidence_sources": [{"url": REDIRECT + "dead", "title": "t"}]}],
        }
        new, changed, removed = source_redirects.drop_urls(value, {REDIRECT + "dead"})
        self.assertTrue(changed)
        self.assertEqual(new["sources"], [{"id": "S2", "url": "https://x.de/a"}])
        self.assertEqual(new["history_points"][0]["evidence_sources"], [])
        self.assertEqual(removed, ["S1"])
        self.assertEqual(source_redirects.drop_urls(value, set()), (value, False, []))

    def test_references_to_removed_sources_disappear_from_the_text(self):
        from app.services import share_snapshots

        payload = share_snapshots.public_share_payload({
            "consensus_md": "Der Preis fiel. [S1] Weiter bei [S2].",
            "sources": [{"id": "S2", "url": "https://x.de/a", "title": "x"}],
            "expired_source_ids": ["S1", "junk", "S1"],
        })
        self.assertEqual(payload["expired_sources"], [{"id": "S1"}])
        html = render_public_markdown(payload["consensus_md"], payload["sources"],
                                      excluded_sources=payload["expired_sources"])
        self.assertNotIn("[S1]", html)
        self.assertIn('href="#src-2"', html)
        version = share_snapshots._watch_version_payload("run1", {"consensus_md": "x", "expired_source_ids": ["S4"]})
        self.assertEqual(version["expired_source_ids"], ["S4"])

    def test_a_redirect_is_never_a_direct_link_even_when_named(self):
        named = [source(REDIRECT + "1", "Adidas product page title", "adidas.com", "adidas", direct=False)]
        self.assertEqual(source_links.key_links(named, "Bei Adidas schauen."), [])


class ShareCleanupTests(unittest.TestCase):
    def setUp(self):
        from tests.test_watch_feature import FakeDb

        self.db = FakeDb()
        self.db.stores["shares"]["S" * 16] = {
            "status": "active",
            "consensus_md": "Siehe [S1] und [S2].",
            "sources": [
                {"id": "S1", "url": REDIRECT + "live", "title": "idealo.de"},
                {"id": "S2", "url": REDIRECT + "dead", "title": "billiger.de"},
                {"id": "S3", "url": "https://geizhals.de/p", "title": "Geizhals"},
            ],
            "source_verification": {"documents": [{"source_id": "D1", "url": REDIRECT + "live",
                                                   "source_url": REDIRECT + "live"}]},
        }

    def clean(self, **kwargs):
        from app.services import share_snapshots, source_redirects

        target = "https://www.idealo.de/preisvergleich/OffersOfProduct/1"
        with patch.object(source_redirects, "_enabled", return_value=True), \
                patch("app.services.agent_read_source.resolve_redirect",
                      side_effect=lambda url: target if url.endswith("live") else ""), \
                patch.object(source_redirects, "_status", side_effect=lambda url: 404 if url.endswith("dead") else 200), \
                patch.object(share_snapshots, "invalidate_share_cache") as invalidate:
            stats = share_snapshots.clean_share_sources("S" * 16, db=self.db, **kwargs)
        return stats, invalidate, target

    def test_resolves_sources_and_the_source_check_alike(self):
        stats, invalidate, target = self.clean()
        share = self.db.stores["shares"]["S" * 16]
        self.assertEqual(stats, {"redirects": 2, "resolved": 1, "expired": 0, "changed": True})
        self.assertEqual(share["sources"][0]["url"], target)
        self.assertEqual(share["sources"][1]["url"], REDIRECT + "dead")  # no expiry check at share time
        self.assertEqual(share["source_verification"]["documents"][0]["url"], target)
        self.assertEqual(share["source_verification"]["documents"][0]["source_url"], target)
        invalidate.assert_called_once_with("S" * 16)

    def test_the_backfill_drops_dead_links_and_keeps_their_numbers(self):
        stats, _invalidate, _target = self.clean(check_expired=True)
        share = self.db.stores["shares"]["S" * 16]
        self.assertEqual(stats["expired"], 1)
        self.assertEqual([source["id"] for source in share["sources"]], ["S1", "S3"])
        self.assertEqual(share["expired_source_ids"], ["S2"])

    def test_a_dry_run_writes_nothing(self):
        before = dict(self.db.stores["shares"]["S" * 16])
        stats, invalidate, _target = self.clean(check_expired=True, apply=False)
        self.assertTrue(stats["changed"])
        self.assertEqual(self.db.stores["shares"]["S" * 16], before)
        invalidate.assert_not_called()

    def test_sharing_starts_the_cleanup_but_never_in_tests(self):
        from app.services import share_snapshots

        self.assertFalse(share_snapshots.schedule_share_cleanup("S" * 16))


class CardLinkTests(unittest.TestCase):
    def test_compact_links_for_the_dashboard(self):
        stored = [
            {"url": "https://www.idealo.de/preisvergleich/OffersOfProduct/1", "title": "Adios Pro 4 - idealo"},
            {"url": "https://www.billiger.de/baseproducts/119030-adidas-adizero-adios-pro-4", "title": "billiger.de"},
            {"url": REDIRECT + "x", "title": "adidas.com"},
        ]
        links = source_links.card_links(stored, "Preisalarm bei Idealo setzen.")
        self.assertEqual(links[0], {"url": stored[0]["url"], "title": "Adios Pro 4", "domain": "idealo.de"})
        # A resolved redirect titled only by its domain speaks through its path.
        self.assertEqual(links[1]["title"], "Adidas adizero adios pro 4")
        self.assertEqual([link["domain"] for link in links], ["idealo.de", "billiger.de"])
        self.assertEqual(source_links.card_links(None, None), [])

    def test_a_real_title_beats_one_read_from_the_path(self):
        stored = [
            {"url": "https://geizhals.de/adidas-adizero-adios-pro-4-herren-v189512.html", "title": "geizhals.de"},
            {"url": "https://geizhals.de/adidas-adizero-adios-pro-4-herren-v189512.html?x=1",
             "title": "adidas Adizero Adios Pro 4 (Herren) ab € 124,95"},
        ]
        self.assertEqual(source_links.card_links(stored, "Bei Geizhals schauen.")[0]["title"],
                         "adidas Adizero Adios Pro 4 (Herren) ab € 124,95")


if __name__ == "__main__":
    unittest.main()
