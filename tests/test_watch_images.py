"""Watch-Bilder: ein echtes Bild des Gegenstands aus den Quellen -- oder keins.

Produktentscheidung 2026-10-10: kein KI-Bild, kein Stockfoto, kein Artikel-
Aufmacher, kein Logo. Abstrakte Watches bekommen gar kein Bild.
"""

import functools
import io
import random
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routers import share as share_router
from app.api.routers import watch as watch_router
from app.core.rate_limit import limiter
from app.services import persistence_guard, watch_images, watch_service
from tests.test_watch_feature import FakeDb, share


QUESTION = "Ich will den Adidas Adizero Adios Pro 4 in Größe 44,5 für unter 140€ kaufen."
GOAL = "Der Adidas Adizero Adios Pro 4 ist in Größe 44,5 für unter 140 € erhältlich"
WATCH_ID = "WatchImage0001"


@functools.lru_cache(maxsize=None)
def photo_bytes(size=(800, 600), fmt="JPEG", seed=7):
    """Noisy pixels: decodes like a photo (many colours), unlike a logo."""
    raw = random.Random(seed).randbytes(size[0] * size[1] * 3)
    buffer = io.BytesIO()
    Image.frombytes("RGB", size, raw).save(buffer, fmt)
    return buffer.getvalue()


def flat_bytes(size=(800, 600)):
    image = Image.new("RGB", size, (20, 30, 200))
    image.paste((255, 255, 255), (100, 100, 400, 300))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def product_page(name, image="https://cdn.shop.test/p/adios-pro-4.jpg", kind="Product"):
    return f"""<html><head>
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://cdn.shop.test/brand/share.jpg">
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}}
    </script>
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "ProductGroup", "name": "{name}",
      "hasVariant": [{{"@type": "{kind}", "name": "{name}", "image": ["{image}"]}}]}}
    </script></head><body>Shop</body></html>"""


ARTICLE_PAGE = """<html><head>
<meta property="og:type" content="article">
<meta property="og:title" content="Adidas Adizero Adios Pro 4 review">
<meta property="og:image" content="https://news.test/hero.jpg">
<script type="application/ld+json">{"@type": "NewsArticle", "headline": "Adidas Adizero Adios Pro 4 review",
 "image": "https://news.test/hero.jpg"}</script></head><body></body></html>"""


class FakeFetch:
    def __init__(self, pages=None, images=None):
        self.pages = pages or {}
        self.images = images or {}
        self.calls = []

    async def __call__(self, url, purpose):
        self.calls.append((purpose, url))
        table = self.pages if purpose == "page" else self.images
        if url not in table:
            raise ValueError("status_403")
        return url, table[url], "text/html" if purpose == "page" else "image/jpeg", False


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.shoe = watch_images.Question(QUESTION, GOAL)

    def score(self, name, question=None):
        return watch_images.match_score(name, question or self.shoe)

    def test_the_shop_name_of_the_watched_shoe_matches(self):
        for name in (
            "adidas Adizero Adios Pro 4 Laufschuhe für Herren - SS26",
            "ADIZERO ADIOS PRO 4 SCHUH",
            "adidas Adizero Adios Pro 4 Carbon Run White JR1094 | eBay",
            "Adizero Adios Pro 4",
            # Another size of the same shoe is the same picture.
            "adidas Adizero Adios Pro 4 – Herren – 42 2/3",
            "adidas Adizero Adios Pro 4 Gr. 42",
            "Adidas Adizero Adios Pro 4 (2026)",
        ):
            self.assertGreater(self.score(name), 0, name)

    def test_another_model_a_sibling_or_an_accessory_does_not(self):
        for name in (
            "adidas Adizero Adios Pro 3 Laufschuhe",
            "Nike Vaporfly 3",
            "adidas Laufschuhe Herren",
            "adidas Adizero Socken",
            "Adizero Pro Shorts",
            "adidas Adizero Evo SL",
            "Adios Pro 4 Schnürsenkel",
        ):
            self.assertEqual(self.score(name), 0, name)

    def test_storage_and_size_numbers_do_not_exclude_but_a_model_number_does(self):
        iphone = watch_images.Question("Wann kommt das iPhone 17 Pro nach Deutschland?")
        self.assertGreater(self.score("Apple iPhone 17 Pro 256 GB", iphone), 0)
        self.assertEqual(self.score("Apple iPhone 16 Pro 256 GB", iphone), 0)
        self.assertEqual(self.score("iPhone 17 Pro Hülle Silikon", iphone), 0)
        macbook = watch_images.Question("Is the MacBook Air M4 under 900 euros?")
        self.assertGreater(self.score("Apple MacBook Air 13 M4 16GB 512GB", macbook), 0)
        dated = watch_images.Question("Is the MacBook Air M4 2025 under 900 euros?")
        self.assertEqual(self.score("MacBook Air M4 2024", dated), 0)
        self.assertGreater(self.score("MacBook Air M4 2025", dated), 0)
        sony = watch_images.Question("Sinkt der Preis der Sony WH-1000XM6 unter 300 Euro?")
        self.assertEqual(self.score("Sony WH-1000XM6 Ohrpolster Ersatz", sony), 0)
        tesla = watch_images.Question("Wann wird das Tesla Model Y Juniper günstiger?")
        self.assertEqual(self.score("Tesla Model Y Juniper Fußmatten", tesla), 0)

    def test_an_accessory_the_question_asks_for_is_fine(self):
        case = watch_images.Question("Gibt es die Apple iPhone 17 Pro Hülle aus FineWoven wieder?")
        self.assertGreater(self.score("Apple iPhone 17 Pro FineWoven Hülle", case), 0)


class PageItemTests(unittest.TestCase):
    def test_json_ld_product_with_its_own_image(self):
        items = watch_images.page_items(
            product_page("adidas Adizero Adios Pro 4 Laufschuhe"), "https://shop.test/p/1",
        )
        self.assertIn(
            ("adidas Adizero Adios Pro 4 Laufschuhe", ["https://cdn.shop.test/p/adios-pro-4.jpg"]),
            items,
        )

    def test_product_without_image_falls_back_to_the_page_preview(self):
        html = """<html><head><meta property="og:image" content="/img/shoe.jpg">
        <script type="application/ld+json">{"@type": ["Product"], "name": "Adios Pro 4"}</script>
        </head></html>"""
        self.assertEqual(
            watch_images.page_items(html, "https://shop.test/a/b"),
            [("Adios Pro 4", ["https://shop.test/img/shoe.jpg"])],
        )

    def test_a_product_inside_a_review_or_list_never_inherits_the_page_image(self):
        review = """<html><head><meta property="og:type" content="article">
        <meta property="og:image" content="https://news.test/hero-runner-on-track.jpg">
        <script type="application/ld+json">{"@type": "Review",
          "itemReviewed": {"@type": "Product", "name": "Adidas Adizero Adios Pro 4"}}</script></head></html>"""
        self.assertEqual(watch_images.page_items(review, "https://news.test/r"),
                         [("Adidas Adizero Adios Pro 4", [])])
        listing = """<html><head><meta property="og:image" content="https://shop.test/category-banner.jpg">
        <script type="application/ld+json">{"@type": "ItemList", "itemListElement": [
          {"@type": "ListItem", "item": {"@type": "Product", "name": "Adios Pro 4"}}]}</script></head></html>"""
        self.assertEqual(watch_images.page_items(listing, "https://shop.test/c"), [("Adios Pro 4", [])])
        video = """<html><head><meta property="og:image" content="https://video.test/thumb.jpg">
        <script type="application/ld+json">{"@type": "VideoObject", "name": "Live",
          "publication": {"@type": "BroadcastEvent", "name": "Adios Pro 4 launch"}}</script></head></html>"""
        self.assertEqual(watch_images.page_items(video, "https://video.test/v"), [])
        main_entity = """<html><head><meta property="og:image" content="https://shop.test/p4.jpg">
        <script type="application/ld+json">{"@type": "WebPage",
          "mainEntity": {"@type": "Product", "name": "Adios Pro 4"}}</script></head></html>"""
        self.assertEqual(watch_images.page_items(main_entity, "https://shop.test/p"),
                         [("Adios Pro 4", ["https://shop.test/p4.jpg"])])

    def test_microdata_takes_its_own_name_not_the_brand(self):
        html = """<div itemscope itemtype="https://schema.org/Product">
          <div itemprop="brand" itemscope itemtype="https://schema.org/Brand"><span itemprop="name">adidas</span>
            <img itemprop="image" src="/brand-logo.jpg"></div>
          <h1 itemprop="name">Adizero Adios Pro 4</h1><img itemprop="image" src="/p4.jpg"></div>"""
        self.assertEqual(watch_images.page_items(html, "https://shop.test/x"),
                         [("Adizero Adios Pro 4", ["https://shop.test/p4.jpg"])])

    def test_og_item_and_microdata_count_articles_do_not(self):
        og = """<html><head><meta property="og:type" content="ebay-objects:item">
        <meta property="og:title" content="adidas Adizero Adios Pro 4">
        <meta property="og:image" content="https://i.ebayimg.test/s-l1600.jpg"></head></html>"""
        self.assertEqual(
            watch_images.page_items(og, "https://www.ebay.test/p/1"),
            [("adidas Adizero Adios Pro 4", ["https://i.ebayimg.test/s-l1600.jpg"])],
        )
        micro = """<div itemscope itemtype="http://schema.org/Product">
        <h1 itemprop="name">Adios Pro 4</h1><img itemprop="image" src="/p/4.jpg"></div>"""
        self.assertEqual(
            watch_images.page_items(micro, "https://shop.test/x"),
            [("Adios Pro 4", ["https://shop.test/p/4.jpg"])],
        )
        self.assertEqual(watch_images.page_items(ARTICLE_PAGE, "https://news.test/a"), [])

    def test_broken_json_ld_is_ignored(self):
        html = '<script type="application/ld+json">{"@type": "Product", </script>'
        self.assertEqual(watch_images.page_items(html, "https://shop.test/"), [])


class CandidateTests(unittest.TestCase):
    def test_google_store_is_not_skipped_with_google_search(self):
        self.assertEqual(
            watch_images.candidate_urls([{"url": "https://store.google.com/product/pixel_10"}]),
            ["https://store.google.com/product/pixel_10"],
        )

    def test_cited_twice_first_one_host_per_round_and_no_social_sites(self):
        sources = [
            {"url": "https://www.reddit.com/r/running/1"},
            {"url": "https://shop-a.test/p/1"},
            {"url": "https://shop-a.test/p/2"},
            {"url": "https://shop-b.test/p/9#reviews"},
            {"url": "https://shop-b.test/p/9"},
            {"url": "https://docs.test/manual.pdf"},
            {"url": "https://www.google.com/search?q=adios"},
            {"url": "javascript:alert(1)"},
            "not a dict",
        ]
        self.assertEqual(
            watch_images.candidate_urls(sources),
            ["https://shop-b.test/p/9", "https://shop-a.test/p/1", "https://shop-a.test/p/2"],
        )


class ThumbnailTests(unittest.TestCase):
    def test_photo_becomes_a_small_webp(self):
        data, size = watch_images.make_thumbnail(photo_bytes((800, 600)))
        self.assertEqual(size, (320, 240))
        self.assertLessEqual(len(data), watch_images.STORED_MAX_BYTES)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "WEBP")

    def test_unusual_modes_and_broken_files_never_raise(self):
        for mode, fmt in (("CMYK", "JPEG"), ("I;16", "PNG"), ("LA", "PNG"), ("P", "GIF")):
            image = Image.frombytes("RGB", (400, 300), random.Random(3).randbytes(400 * 300 * 3)).convert(
                "RGB" if mode == "I;16" else mode)
            if mode == "I;16":
                image = Image.new("I;16", (400, 300))
            buffer = io.BytesIO()
            image.save(buffer, fmt)
            watch_images.make_thumbnail(buffer.getvalue())  # must not raise
        data = photo_bytes()
        self.assertIsNone(watch_images.make_thumbnail(data[: len(data) // 3]))
        self.assertIsNone(watch_images.make_thumbnail(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64))

    def test_a_huge_jpeg_is_decoded_small(self):
        buffer = io.BytesIO()
        Image.frombytes("RGB", (64, 64), random.Random(5).randbytes(64 * 64 * 3)).resize(
            (6000, 4000)).save(buffer, "JPEG", quality=70)
        opened = []
        real_open = Image.open

        def spy(*args, **kwargs):
            image = real_open(*args, **kwargs)
            opened.append(image)
            return image

        with patch.object(watch_images.Image, "open", side_effect=spy):
            data, size = watch_images.make_thumbnail(buffer.getvalue())
        self.assertEqual(size, (320, 213))
        # draft() made the decoder work at a fraction of 6000 x 4000.
        self.assertLessEqual(max(opened[0].size), 1500)

    def test_a_huge_png_is_not_decoded_at_all(self):
        buffer = io.BytesIO()
        Image.new("RGB", (4000, 3000)).save(buffer, "PNG")
        self.assertIsNone(watch_images.make_thumbnail(buffer.getvalue()))

    def test_exif_orientation_is_applied(self):
        image = Image.frombytes("RGB", (600, 300), random.Random(9).randbytes(600 * 300 * 3))
        exif = Image.Exif()
        exif[0x0112] = 6
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        _data, size = watch_images.make_thumbnail(buffer.getvalue())
        self.assertEqual(size, (160, 320))

    def test_logos_icons_strips_and_non_images_are_rejected(self):
        self.assertIsNone(watch_images.make_thumbnail(flat_bytes()))
        self.assertIsNone(watch_images.make_thumbnail(photo_bytes((120, 120))))
        self.assertIsNone(watch_images.make_thumbnail(photo_bytes((1000, 200))))
        self.assertIsNone(watch_images.make_thumbnail(b"<svg></svg>"))
        self.assertTrue(watch_images._looks_like_logo("https://cdn.test/assets/logo-dark.png"))
        self.assertTrue(watch_images._looks_like_logo("https://cdn.test/no-image.jpg"))
        self.assertFalse(watch_images._looks_like_logo("https://cdn.test/iconic-runner.jpg"))


class FindImageTests(unittest.TestCase):
    sources = [
        {"url": "https://news.test/a"},
        {"url": "https://blocked-shop.test/p"},
        {"url": "https://shop.test/p/1"},
    ]

    def test_finds_the_product_photo_behind_blocked_and_article_sources(self):
        fetch = FakeFetch(
            pages={
                "https://news.test/a": ARTICLE_PAGE.encode(),
                "https://shop.test/p/1": product_page("adidas Adizero Adios Pro 4 Laufschuhe").encode(),
            },
            images={"https://cdn.shop.test/p/adios-pro-4.jpg": photo_bytes()},
        )
        found = watch_images.find_image(self.sources, QUESTION, GOAL, fetch=fetch)
        self.assertEqual(found["source_url"], "https://shop.test/p/1")
        self.assertEqual(found["source_host"], "shop.test")
        self.assertEqual(found["content_type"], "image/webp")
        self.assertNotIn(("image", "https://news.test/hero.jpg"), fetch.calls)

    def test_no_image_for_the_wrong_model_or_an_abstract_question(self):
        fetch = FakeFetch(
            pages={"https://shop.test/p/1": product_page("adidas Adizero Adios Pro 3").encode()},
            images={"https://cdn.shop.test/p/adios-pro-4.jpg": photo_bytes()},
        )
        self.assertIsNone(watch_images.find_image(self.sources, QUESTION, GOAL, fetch=fetch))
        self.assertFalse([call for call in fetch.calls if call[0] == "image"])
        self.assertIsNone(watch_images.find_image(
            [{"url": "https://news.test/a"}],
            "Is GPT-6 Sol actually better value than Claude Opus 5.5 for coding?",
            fetch=FakeFetch(pages={"https://news.test/a": ARTICLE_PAGE.encode()}),
        ))

    def test_a_topic_gets_the_preview_image_of_a_matching_article(self):
        question = "Has the EU AI Act guidance for general-purpose AI changed?"
        article = """<html><head><meta property="og:type" content="article">
        <meta property="og:image" content="https://news.test/img/2026/10/eu-ai-act-brussels.jpg">
        <script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
          {"@type": "WebPage", "name": "News"},
          {"@type": "NewsArticle", "headline": "EU AI Act: Commission issues new guidance for general-purpose AI",
           "image": "https://news.test/img/other.jpg"}]}</script></head></html>"""
        unrelated = """<html><head><meta property="og:type" content="article">
        <meta property="og:title" content="The best laptops for students">
        <meta property="og:image" content="https://blog.test/laptops.jpg"></head></html>"""
        fetch = FakeFetch(
            pages={"https://blog.test/a": unrelated.encode(), "https://news.test/eu": article.encode()},
            images={
                "https://blog.test/laptops.jpg": photo_bytes(seed=1),
                "https://news.test/img/2026/10/eu-ai-act-brussels.jpg": photo_bytes(seed=2),
            },
        )
        found = watch_images.find_image(
            [{"url": "https://blog.test/a"}, {"url": "https://news.test/eu"}], question, fetch=fetch,
        )
        self.assertEqual(found["kind"], "article")
        self.assertEqual(found["source_url"], "https://news.test/eu")
        self.assertNotIn(("image", "https://blog.test/laptops.jpg"), fetch.calls)
        self.assertEqual(
            watch_images.page_article(article, "https://news.test/eu")[1][0],
            "https://news.test/img/2026/10/eu-ai-act-brussels.jpg",
        )

    def test_a_site_default_share_image_is_not_the_topic(self):
        article = """<html><head><meta property="og:type" content="article">
        <meta property="og:title" content="EU AI Act guidance for general-purpose AI explained">
        <meta property="og:image" content="https://news.test/static/og-default.jpg"></head></html>"""
        fetch = FakeFetch(
            pages={"https://news.test/eu": article.encode()},
            images={"https://news.test/static/og-default.jpg": photo_bytes()},
        )
        self.assertIsNone(watch_images.find_image(
            [{"url": "https://news.test/eu"}], "Has the EU AI Act guidance changed?", fetch=fetch,
        ))
        self.assertEqual(fetch.calls, [("page", "https://news.test/eu")])

    def test_headline_matching_needs_a_name_from_the_question(self):
        question = "Is GPT-6 Sol actually better value than Claude Opus 5.5 for coding?"
        context, entities = watch_images._tokens(question), watch_images.entity_tokens(question)
        self.assertTrue({"gpt", "6", "sol", "claude", "opus"} <= entities)
        self.assertNotIn("coding", entities)
        self.assertGreater(watch_images.article_score("Introducing GPT-6 Sol", context, entities), 0)
        self.assertGreater(watch_images.article_score(
            "Claude Opus 5.5 vs GPT-6 Sol: 92% on SWE-bench", context, entities), 0)
        self.assertEqual(watch_images.article_score("The best AI coding tools in 2026", context, entities), 0)
        self.assertEqual(watch_images.article_score("Better value coding tips", context, entities), 0)
        german = "Wann kommt das neue iPhone 17 Pro nach Deutschland?"
        self.assertGreater(watch_images.article_score(
            "iPhone 17 Pro: Marktstart in Deutschland", watch_images._tokens(german),
            watch_images.entity_tokens(german)), 0)

    def test_a_logo_or_placeholder_is_not_the_product(self):
        fetch = FakeFetch(
            pages={"https://shop.test/p/1": product_page(
                "adidas Adizero Adios Pro 4", image="https://cdn.shop.test/logo.png").encode()},
            images={"https://cdn.shop.test/logo.png": photo_bytes()},
        )
        self.assertIsNone(watch_images.find_image(self.sources, QUESTION, GOAL, fetch=fetch))
        fetch = FakeFetch(
            pages={"https://shop.test/p/1": product_page("adidas Adizero Adios Pro 4").encode()},
            images={"https://cdn.shop.test/p/adios-pro-4.jpg": flat_bytes()},
        )
        self.assertIsNone(watch_images.find_image(self.sources, QUESTION, GOAL, fetch=fetch))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        self.db.stores["shares"]["S" * 16] = share()
        self.db.stores[watch_service.WATCHES_COLLECTION][WATCH_ID] = {
            "owner_uid": "u1", "share_id": "S" * 16, "status": "active",
            "visibility": "public", "condition": GOAL,
        }
        watch_images.forget(WATCH_ID)
        watch_images._MISSES.clear()
        self.found = {
            "content": watch_images.make_thumbnail(photo_bytes())[0],
            "content_type": "image/webp", "width": 320, "height": 240,
            "source_url": "https://shop.test/p/1", "source_host": "shop.test",
        }

    def watch(self):
        return self.db.stores[watch_service.WATCHES_COLLECTION][WATCH_ID]

    def test_ready_image_is_served_listed_and_kept(self):
        self.assertEqual(watch_images.store_result(WATCH_ID, self.found, db=self.db), "ready")
        view = watch_images.image_view(WATCH_ID, self.watch())
        token = self.watch()["image"]["token"]
        self.assertEqual(view["url"], f"/api/watch/{WATCH_ID}/image/{token}")
        self.assertEqual(view["source_host"], "shop.test")
        self.assertEqual(view["kind"], "item")
        self.assertEqual(watch_images.load_image(WATCH_ID, token, db=self.db)[1], "image/webp")
        self.assertIsNone(watch_images.load_image(WATCH_ID, "0" * 20, db=self.db))
        self.assertIsNone(watch_images.load_image("../etc", token, db=self.db))

        listed = watch_service.list_watches("u1", db=self.db)[0]
        self.assertEqual(listed["image"], view)
        self.assertEqual(watch_service.get_public_watch_meta("S" * 16, db=self.db)["image"], view)
        # A later check never replaces the picked image.
        self.assertEqual(watch_images.store_result(WATCH_ID, None, db=self.db), "kept")
        self.assertEqual(self.watch()["image"]["status"], "ready")

    def test_three_empty_attempts_end_the_search(self):
        for _ in range(watch_images.MAX_ATTEMPTS):
            self.assertTrue(watch_images.needs_image(self.watch()))
            self.assertEqual(watch_images.store_result(WATCH_ID, None, db=self.db), "none")
        self.assertFalse(watch_images.needs_image(self.watch()))
        self.assertEqual(
            watch_images.refresh_for_watch(
                WATCH_ID, self.watch(), [{"url": "https://shop.test/p/1"}], QUESTION,
                db=self.db, fetch=FakeFetch(),
            ),
            "skipped",
        )
        self.assertIsNone(watch_service.list_watches("u1", db=self.db)[0]["image"])

    def test_blocked_sources_do_not_use_up_attempts_but_are_capped(self):
        sources = [{"url": "https://blocked-shop.test/p"}]
        for _ in range(watch_images.MAX_TRIES - 1):
            self.assertEqual(watch_images.refresh_for_watch(
                WATCH_ID, self.watch(), sources, QUESTION, db=self.db, fetch=FakeFetch(),
            ), "none")
        self.assertEqual(self.watch()["image"]["attempts"], 0)
        self.assertTrue(watch_images.needs_image(self.watch()))
        watch_images.refresh_for_watch(WATCH_ID, self.watch(), sources, QUESTION, db=self.db, fetch=FakeFetch())
        self.assertEqual(self.watch()["image"]["tries"], watch_images.MAX_TRIES)
        self.assertFalse(watch_images.needs_image(self.watch()))

    def test_a_read_page_without_a_match_counts_as_an_attempt(self):
        fetch = FakeFetch(pages={"https://news.test/a": ARTICLE_PAGE.encode()})
        watch_images.refresh_for_watch(
            WATCH_ID, self.watch(), [{"url": "https://news.test/a"}],
            "Is GPT-6 Sol actually better value than Claude Opus 5.5 for coding?", db=self.db, fetch=fetch,
        )
        self.assertEqual(self.watch()["image"]["attempts"], 1)

    def test_a_dismissal_during_a_read_does_not_leave_the_image_cached(self):
        watch_images.store_result(WATCH_ID, self.found, db=self.db)
        token = self.watch()["image"]["token"]
        real_collection = self.db.collection

        def collection(name):
            if name == watch_images.WATCH_IMAGES_COLLECTION:
                watch_images.forget(WATCH_ID)  # a dismiss commits mid-read
            return real_collection(name)

        with patch.object(self.db, "collection", side_effect=collection):
            self.assertIsNotNone(watch_images.load_image(WATCH_ID, token, db=self.db))
        self.assertNotIn(WATCH_ID, watch_images._CACHE)

    def test_an_unknown_watch_costs_one_read_whatever_the_token(self):
        reads = []
        real_collection = self.db.collection

        def collection(name):
            reads.append(name)
            return real_collection(name)

        with patch.object(self.db, "collection", side_effect=collection):
            for token in ("1" * 20, "2" * 20, "3" * 20):
                self.assertIsNone(watch_images.load_image("NoSuchWatch01", token, db=self.db))
        self.assertEqual(reads, [watch_images.WATCH_IMAGES_COLLECTION])

    def test_an_unexpected_search_error_counts_as_a_try(self):
        with patch.object(watch_images, "search", side_effect=RuntimeError("parser bug")):
            outcome = watch_images.refresh_for_watch(
                WATCH_ID, self.watch(), [{"url": "https://shop.test/p/1"}], QUESTION, db=self.db,
            )
        self.assertEqual(outcome, "none")
        self.assertEqual(self.watch()["image"]["tries"], 1)
        self.assertEqual(self.watch()["image"]["attempts"], 0)

    def test_a_failed_thread_start_frees_the_slot(self):
        with patch.object(watch_images.threading, "Thread", side_effect=RuntimeError("no threads")):
            self.assertFalse(watch_images._submit(WATCH_ID, lambda: None))
        self.assertNotIn(WATCH_ID, watch_images._PENDING)

    def test_a_wrong_token_for_a_known_image_costs_no_read(self):
        watch_images.store_result(WATCH_ID, self.found, db=self.db)
        token = self.watch()["image"]["token"]
        self.assertIsNotNone(watch_images.load_image(WATCH_ID, token, db=self.db))
        with patch.object(self.db, "collection", side_effect=AssertionError("no read expected")):
            self.assertIsNotNone(watch_images.load_image(WATCH_ID, token, db=self.db))
            self.assertIsNone(watch_images.load_image(WATCH_ID, "f" * 20, db=self.db))

    def test_sources_without_candidates_do_not_count_as_an_attempt(self):
        outcome = watch_images.refresh_for_watch(
            WATCH_ID, self.watch(), [{"url": "https://www.youtube.com/watch?v=1"}], QUESTION,
            db=self.db, fetch=FakeFetch(),
        )
        self.assertEqual(outcome, "skipped")
        self.assertNotIn("image", self.watch())

    def test_dismissed_image_never_comes_back_and_its_bytes_are_gone(self):
        watch_images.store_result(WATCH_ID, self.found, db=self.db)
        token = self.watch()["image"]["token"]
        self.assertIsNotNone(watch_images.load_image(WATCH_ID, token, db=self.db))
        with self.assertRaises(watch_service.WatchError):
            watch_service.dismiss_watch_image("someone-else", WATCH_ID, db=self.db)
        watch_service.dismiss_watch_image("u1", WATCH_ID, db=self.db)
        self.assertEqual(self.watch()["image"]["status"], "dismissed")
        self.assertNotIn(WATCH_ID, self.db.stores[watch_images.WATCH_IMAGES_COLLECTION])
        self.assertIsNone(watch_images.load_image(WATCH_ID, token, db=self.db))
        self.assertEqual(watch_images.store_result(WATCH_ID, self.found, db=self.db), "kept")
        self.assertNotIn(WATCH_ID, self.db.stores[watch_images.WATCH_IMAGES_COLLECTION])

    def test_deleting_the_watch_deletes_its_image(self):
        watch_images.store_result(WATCH_ID, self.found, db=self.db)
        token = self.watch()["image"]["token"]
        self.assertTrue(watch_service._delete_watch_record(WATCH_ID, db=self.db))
        self.assertEqual(self.db.stores[watch_images.WATCH_IMAGES_COLLECTION], {})
        self.assertIsNone(watch_images.load_image(WATCH_ID, token, db=self.db))
        # A pick that finishes after the deletion writes nothing.
        self.assertEqual(watch_images.store_result(WATCH_ID, self.found, db=self.db), "gone")
        self.assertEqual(self.db.stores[watch_images.WATCH_IMAGES_COLLECTION], {})

    def test_pending_account_deletion_blocks_the_write(self):
        self.db.stores[persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION]["u1"] = {"status": "pending"}
        with self.assertRaises(persistence_guard.AccountDeletionInProgress):
            watch_images.store_result(WATCH_ID, self.found, db=self.db)
        self.assertEqual(self.db.stores[watch_images.WATCH_IMAGES_COLLECTION], {})

    def test_background_job_runs_once_per_watch_at_a_time(self):
        started, release, done = threading.Event(), threading.Event(), threading.Event()

        def job():
            started.set()
            release.wait(5)
            done.set()

        self.assertTrue(watch_images._submit(WATCH_ID, job))
        self.assertTrue(started.wait(5))
        self.assertFalse(watch_images._submit(WATCH_ID, job))
        release.set()
        self.assertTrue(done.wait(5))
        for _ in range(50):
            if WATCH_ID not in watch_images._PENDING:
                break
            time.sleep(0.02)
        self.assertNotIn(WATCH_ID, watch_images._PENDING)

    def test_background_scheduling_is_off_in_tests(self):
        self.assertFalse(watch_images.background_enabled())
        self.assertFalse(watch_images.schedule_after_run(
            WATCH_ID, self.watch(), [{"url": "https://shop.test/p/1"}], QUESTION,
        ))
        self.assertFalse(watch_images.schedule_for_new_watch(WATCH_ID))


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(watch_router.router)
        cls.client = TestClient(app)

    def test_image_route_serves_bytes_privately_cached(self):
        with patch.object(watch_router.watch_images, "load_image", return_value=(b"RIFFwebp", "image/webp")) as load:
            response = self.client.get(f"/api/watch/{WATCH_ID}/image/{'a' * 20}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertIn("private", response.headers["cache-control"])
        load.assert_called_once_with(WATCH_ID, "a" * 20)
        with patch.object(watch_router.watch_images, "load_image", return_value=None):
            self.assertEqual(self.client.get(f"/api/watch/{WATCH_ID}/image/{'b' * 20}").status_code, 404)

    def test_dismiss_requires_login_and_maps_ownership(self):
        self.assertEqual(self.client.request("DELETE", f"/api/watch/{WATCH_ID}/image").status_code, 401)
        with (
            patch.object(watch_router, "extract_id_token", return_value="tok"),
            patch.object(watch_router, "verify_user_token", return_value="u2"),
            patch.object(watch_router.watch_service, "dismiss_watch_image",
                         side_effect=watch_service.WatchError("forbidden", "no")),
        ):
            response = self.client.request("DELETE", f"/api/watch/{WATCH_ID}/image")
        self.assertEqual(response.status_code, 403)

    def test_create_from_an_answer_schedules_a_pick_query_first_does_not(self):
        for created, expected in (({"id": WATCH_ID}, True), ({"id": WATCH_ID, "query_first": True}, False)):
            with (
                patch.object(watch_router, "extract_id_token", return_value="tok"),
                patch.object(watch_router, "verify_user_token", return_value="u1"),
                patch.object(watch_router, "get_user_tier", return_value="free"),
                patch.object(watch_router.watch_service, "create_watch", return_value=created),
                patch.object(watch_router.watch_images, "schedule_for_new_watch") as schedule,
            ):
                response = self.client.post("/api/watch", json={
                    "result_id": "r1", "interval": "weekly", "visibility": "public",
                })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(schedule.called, expected)


class WatchPageTests(unittest.TestCase):
    def test_image_reaches_the_page_meta_but_never_the_og_card(self):
        image = {"url": f"/api/watch/{WATCH_ID}/image/{'c' * 20}", "width": 320, "height": 240,
                 "source_url": "https://shop.test/p/1", "source_host": "shop.test"}
        meta = share_router._build_watch_page_meta({"status": "active", "image": image}, [])
        self.assertEqual(meta["image"], image)
        self.assertIsNone(share_router._build_watch_page_meta({"status": "active"}, [])["image"])
        template = open("templates/watch_share.html", encoding="utf-8").read()
        og_block = template.split("<script type=\"application/ld+json\">")[0]
        self.assertNotIn("watch_image", og_block)
        self.assertIn('class="wp-image is-', template)


if __name__ == "__main__":
    unittest.main()
