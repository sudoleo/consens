"""Watch-Seiten führen direkt zu den Quellen (source_links.py, seit 2026-10-12).

Direktlinks über der Antwort und die Namen der Quellen im Text als Links:
Navigation, kein Satz-für-Satz-Beleg -- die Synthese schreibt bewusst keine
S-Verweise (docs/source-verification.md).
"""

import re
import unittest

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


if __name__ == "__main__":
    unittest.main()
