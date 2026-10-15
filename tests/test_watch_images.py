"""Watch-Bilder: ein echtes Bild aus den Quellen -- oder keins.

Produktentscheidung 2026-10-10/11: kein KI-Bild, kein Stockfoto; der
Gegenstand selbst, sonst das Vorschaubild eines passenden Artikels. Seit
2026-10-12 sonst die Logos der Seiten, um die es geht (nie die einer Seite,
die nur berichtet), und ohne Bild ein Symbol aus fester Liste.
"""

import asyncio
import functools
import io
import json
import random
import re
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.routers import share as share_router
from app.api.routers import watch as watch_router
from app.core.rate_limit import limiter
from app.services import persistence_guard, watch_images, watch_service, watch_symbols
from app.services.llm import consensus_engine
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


def icon_bytes(size=180, fill=(0, 110, 80, 255), glyph=(255, 255, 255, 255), fmt="PNG"):
    """An app icon: a filled square with a round mark; fill=None leaves only
    the mark on transparency, like a favicon."""
    image = Image.new("RGBA", (size, size), fill or (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((size * .3, size * .3, size * .7, size * .7), fill=glyph)
    buffer = io.BytesIO()
    image.save(buffer, fmt, **({"sizes": [(size, size)]} if fmt == "ICO" else {}))
    return buffer.getvalue()


def home_page(*links):
    return ("<html><head><title>Home</title>" + "".join(links) + "</head><body></body></html>").encode()


CURSOR_QUESTION = "Is Cursor or Claude Code better value for daily coding?"
UNRELATED_ARTICLE = """<html><head><meta property="og:type" content="article">
<meta property="og:title" content="The best laptops for students">
<meta property="og:image" content="https://news.test/laptops.jpg"></head></html>""".encode()


class SiteTests(unittest.TestCase):
    def test_the_registrable_domain(self):
        self.assertEqual(watch_images.site_domain("docs.github.com"), "github.com")
        self.assertEqual(watch_images.site_domain("www.bbc.co.uk"), "bbc.co.uk")
        self.assertEqual(watch_images.site_domain("gemini.google"), "gemini.google")
        self.assertEqual(watch_images.site_domain("karriere.hs-hannover.de"), "hs-hannover.de")
        self.assertEqual(watch_images.site_domain("localhost"), "")
        # An address is no domain ("192.168.1.1" would become "1.1").
        self.assertEqual(watch_images.site_domain("192.168.1.1"), "")
        self.assertEqual(watch_images.site_domain("::1"), "")
        self.assertEqual(watch_images.source_sites([{"url": "http://8.8.8.8/x"}]), [])

    def test_sites_by_citations_without_search_redirects(self):
        sites = watch_images.source_sites([
            {"url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"},
            {"url": "https://heise.de/a"},
            {"url": "https://support.claude.com/x"},
            {"url": "https://platform.claude.com/y"},
            {"url": "ftp://files.test/z"},
        ])
        self.assertEqual(sites, [
            ("claude.com", ["https://support.claude.com/x", "https://platform.claude.com/y"]),
            ("heise.de", ["https://heise.de/a"]),
        ])

    def test_named_sites_follow_the_question_and_skip_reporters(self):
        question = watch_images.Question("Is Kimchi Coding cheaper than Claude Code and Cursor for AI coding?")
        sites = watch_images.source_sites([
            {"url": "https://www.heise.de/news/kimchi"},
            {"url": "https://cursor.com/pricing"},
            {"url": "https://support.claude.com/x"},
            {"url": "https://kimchi.dev/"},
        ])
        self.assertEqual(watch_images.named_sites(sites, question), ["kimchi.dev", "claude.com"])
        job = watch_images.Question(
            "Ausgeschriebene Stelle als Wis. Mitarbeiter an der Hochschule Hannover oder Leibniz Universität")
        sites = watch_images.source_sites([
            {"url": "https://www.uni-hannover.de/jobs/id/8689"},
            {"url": "https://www.stellenwerk.de/hannover"},
            {"url": "https://karriere.hs-hannover.de/portal"},
        ])
        self.assertEqual(watch_images.named_sites(sites, job), ["uni-hannover.de", "hs-hannover.de"])
        self.assertEqual(watch_images.named_sites(sites, watch_images.Question("how to make money")), [])


class LogoTests(unittest.TestCase):
    def test_page_icons_prefer_the_largest_app_icon(self):
        html = """<html><head>
        <link rel="apple-touch-icon" sizes="57x57" href="/icons/apple-57.png">
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/apple-180.png">
        <link rel="icon" type="image/svg+xml" href="/favicon.svg">
        <link rel="mask-icon" href="/pinned.png">
        <link rel="icon" sizes="32x32" href="/icons/32.png">
        <link rel="icon" sizes="192x192" href="/icons/192.png">
        <link rel="shortcut icon" href="/favicon.ico">
        <link rel="stylesheet" href="/site.css"></head></html>"""
        self.assertEqual(watch_images.page_icons(html, "https://site.test/home"), [
            "https://site.test/icons/apple-180.png",
            "https://site.test/icons/192.png",
            "https://site.test/apple-touch-icon.png",
            "https://site.test/favicon.ico",
        ])

    def test_an_app_icon_fills_its_tile_and_a_mark_sits_on_its_own_ground(self):
        filled = watch_images.make_logo(icon_bytes())
        self.assertEqual(filled.size, (watch_images.LOGO_SIDE, watch_images.LOGO_SIDE))
        self.assertEqual(filled.getpixel((3, 70)), (0, 110, 80))
        dark_mark = watch_images.make_logo(icon_bytes(fill=None, glyph=(30, 30, 30, 255)))
        self.assertEqual(dark_mark.getpixel((3, 3)), (255, 255, 255))
        light_mark = watch_images.make_logo(icon_bytes(fill=None, glyph=(250, 250, 250, 255)))
        self.assertEqual(light_mark.getpixel((3, 3)), (32, 33, 36))
        self.assertIsNotNone(watch_images.make_logo(icon_bytes(size=96, fmt="ICO")))

    def test_an_ico_that_lies_about_its_size_is_never_decoded(self):
        # The directory says 32 px, the embedded PNG says 12000 px: Pillow
        # would decode it inside Image.open, before any size check.
        def ico(payload):
            entry = bytes([32, 32, 0, 0]) + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") \
                + len(payload).to_bytes(4, "little") + (22).to_bytes(4, "little")
            return b"\x00\x00\x01\x00" + (1).to_bytes(2, "little") + entry + payload

        png_bomb = b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" \
            + (12000).to_bytes(4, "big") + (12000).to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"
        bmp_bomb = (40).to_bytes(4, "little") + (9000).to_bytes(4, "little") + (18000).to_bytes(4, "little")
        with patch.object(watch_images.Image, "open") as opened:
            self.assertIsNone(watch_images.make_logo(ico(png_bomb)))
            self.assertIsNone(watch_images.make_logo(ico(bmp_bomb)))
            self.assertIsNone(watch_images.make_logo(b"\x00\x00\x01\x00\x00\x00"))
        opened.assert_not_called()
        self.assertTrue(watch_images._ico_fits(icon_bytes(size=96, fmt="ICO")))

    def test_tiny_blank_or_broken_icons_are_no_logo(self):
        self.assertIsNone(watch_images.make_logo(icon_bytes(size=48)))
        self.assertIsNone(watch_images.make_logo(icon_bytes(glyph=(0, 110, 80, 255))))
        self.assertIsNone(watch_images.make_logo(icon_bytes(fill=None, glyph=(0, 0, 0, 0))))
        self.assertIsNone(watch_images.make_logo(b"<svg></svg>"))
        self.assertIsNone(watch_images.make_logo(b"\x00\x00\x01\x00garbage"))

    def test_two_logos_become_one_image_with_rounded_tiles(self):
        tile = watch_images.make_logo(icon_bytes())
        data, size = watch_images.compose_logos([tile, tile, tile])
        self.assertEqual(size, (304, 144))
        self.assertLessEqual(size[0], watch_images.THUMB_SIDE)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "WEBP")
            image = image.convert("RGBA")
            self.assertEqual(image.getpixel((0, 0))[3], 0)  # rounded corner
            self.assertEqual(image.getpixel((150, 72))[3], 0)  # the gap
            self.assertEqual(image.getpixel((72, 72))[3], 255)


class LogoSearchTests(unittest.TestCase):
    sources = [
        {"url": "https://news.test/a"},
        {"url": "https://cursor.com/pricing"},
        {"url": "https://support.claude.com/x"},
    ]

    def fetch(self, **extra_pages):
        pages = {
            "https://news.test/a": UNRELATED_ARTICLE,
            "https://cursor.com/": home_page('<link rel="apple-touch-icon" href="/apple-touch-icon-light.png">'),
            "https://claude.com/": home_page('<link rel="icon" href="https://assets.test/32.png?w=32">'),
        }
        pages.update(extra_pages)
        return FakeFetch(pages=pages, images={
            "https://news.test/laptops.jpg": photo_bytes(seed=4),
            "https://cursor.com/apple-touch-icon-light.png": icon_bytes(fill=(20, 20, 20, 255)),
            "https://claude.com/apple-touch-icon.png": icon_bytes(fill=(217, 119, 87, 255)),
        })

    def test_without_product_or_article_the_named_sites_show_their_logos(self):
        fetch = self.fetch()
        found = watch_images.find_image(self.sources, CURSOR_QUESTION, fetch=fetch)
        self.assertEqual(found["kind"], "logo")
        self.assertEqual(found["source_host"], "cursor.com, claude.com")
        self.assertEqual(found["source_url"], "https://cursor.com/")
        self.assertEqual((found["width"], found["height"]), (304, 144))
        # The news page's own picture or icon is never taken.
        self.assertNotIn(("image", "https://news.test/laptops.jpg"), fetch.calls)
        self.assertFalse([call for call in fetch.calls if "news.test" in call[1] and call[0] != "page"])

    def test_the_judges_choice_replaces_the_name_rule(self):
        fetch = self.fetch()
        self.assertIsNone(watch_images.find_image(self.sources, CURSOR_QUESTION, fetch=fetch, sites=[]))
        self.assertNotIn(("page", "https://cursor.com/"), fetch.calls)
        found = watch_images.find_image(
            self.sources, "Is GPT-6 Sol better value for coding?", fetch=self.fetch(), sites=["claude.com"],
        )
        self.assertEqual(found["source_host"], "claude.com")
        self.assertEqual(found["width"], watch_images.LOGO_SIDE)

    def test_the_logo_beats_a_publishers_article_picture(self):
        article = """<html><head><meta property="og:type" content="article">
        <meta property="og:title" content="Cursor changes its pricing for Pro users">
        <meta property="og:image" content="https://news.test/cursor-pricing.jpg"></head></html>""".encode()
        fetch = self.fetch(**{"https://news.test/cursor": article})
        fetch.images["https://news.test/cursor-pricing.jpg"] = photo_bytes(seed=5)
        found = watch_images.find_image(
            [{"url": "https://news.test/cursor"}, {"url": "https://cursor.com/pricing"}],
            "Has Cursor changed its pricing for Pro users?", fetch=fetch,
        )
        self.assertEqual((found["kind"], found["source_host"]), ("logo", "cursor.com"))
        self.assertNotIn(("image", "https://news.test/cursor-pricing.jpg"), fetch.calls)
        # Without a site of its own, the article picture still comes through.
        found = watch_images.find_image(
            [{"url": "https://news.test/cursor"}], "Has Cursor changed its pricing for Pro users?",
            fetch=fetch, sites=[],
        )
        self.assertEqual((found["kind"], found["source_url"]), ("article", "https://news.test/cursor"))

    def test_a_redirect_counts_as_the_page_it_ends_on(self):
        redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
        video = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/def"
        product = product_page("adidas Adizero Adios Pro 4").encode()

        async def fetch(url, purpose):
            if url == redirect:
                return "https://shop.test/p/1", product, "text/html", False
            if url == video:
                return "https://www.youtube.com/watch?v=1", product, "text/html", False
            if url == "https://cdn.shop.test/p/adios-pro-4.jpg":
                return url, photo_bytes(), "image/jpeg", False
            raise ValueError("status_403")

        found = watch_images.find_image([{"url": redirect}], QUESTION, GOAL, fetch=fetch)
        self.assertEqual((found["source_url"], found["source_host"]), ("https://shop.test/p/1", "shop.test"))
        self.assertIsNone(watch_images.find_image([{"url": video}], QUESTION, GOAL, fetch=fetch))

    def test_our_own_pages_are_never_a_source(self):
        own = [{"url": "https://www.consens.io/s/abc123"}, {"url": "https://consens.io/topics/x"}]
        self.assertEqual(watch_images.candidate_urls(own), [])
        self.assertEqual(watch_images.source_sites(own), [])

    def test_a_blocked_home_page_falls_back_to_the_cited_page(self):
        fetch = self.fetch(**{
            "https://cursor.com/pricing": home_page('<link rel="apple-touch-icon" href="/apple-touch-icon-light.png">'),
        })
        del fetch.pages["https://cursor.com/"]
        found = watch_images.find_image(self.sources[:2], "Is Cursor worth it?", fetch=fetch)
        self.assertEqual(found["source_host"], "cursor.com")
        self.assertIn(("page", "https://cursor.com/pricing"), fetch.calls)


class VisualPickTests(unittest.TestCase):
    sources = [{"url": "https://news.test/a"}, {"url": "https://cursor.com/pricing"}]

    def setUp(self):
        self.db = FakeDb()
        self.db.stores["shares"]["S" * 16] = share()
        self.db.stores[watch_service.WATCHES_COLLECTION][WATCH_ID] = {
            "owner_uid": "u1", "share_id": "S" * 16, "status": "active", "visibility": "public",
        }
        watch_images.forget(WATCH_ID)
        self.fetch = FakeFetch(
            pages={
                "https://news.test/a": UNRELATED_ARTICLE,
                "https://cursor.com/": home_page('<link rel="apple-touch-icon" href="/touch.png">'),
            },
            images={"https://cursor.com/touch.png": icon_bytes()},
        )

    def watch(self):
        return self.db.stores[watch_service.WATCHES_COLLECTION][WATCH_ID]

    def refresh(self, pick, sources=None, question=CURSOR_QUESTION):
        return watch_images.refresh_for_watch(
            WATCH_ID, self.watch(), self.sources if sources is None else sources, question,
            db=self.db, fetch=self.fetch, pick=pick,
        )

    def test_the_judge_picks_once_from_the_source_domains(self):
        calls = []

        def pick(question, condition, domains):
            calls.append(domains)
            return {"symbol": "code", "sites": ["cursor.com", "invented.example", "cursor.com"]}

        self.assertEqual(self.refresh(pick), "ready")
        self.assertEqual(calls, [["news.test", "cursor.com"]])
        self.assertEqual(self.watch()["symbol"], "code")
        self.assertEqual(self.watch()["image"]["sites"], ["cursor.com"])
        self.assertEqual(self.watch()["image"]["kind"], "logo")
        listed = watch_service.list_watches("u1", db=self.db)[0]
        self.assertEqual(listed["symbol"], "code")
        self.assertEqual(listed["image"]["kind"], "logo")
        self.assertEqual(self.refresh(pick), "skipped")
        self.assertEqual(len(calls), 1)

    def test_a_choice_with_nothing_to_fetch_is_remembered(self):
        calls = []

        def pick(question, condition, domains):
            calls.append(domains)
            return {"symbol": "film", "sites": []}

        self.assertEqual(self.refresh(pick, sources=[{"url": "https://www.youtube.com/watch?v=1"}]), "kept")
        self.assertEqual(self.watch()["symbol"], "film")
        self.assertEqual(self.watch()["image"], {"sites": []})
        self.assertEqual(self.refresh(pick, sources=[{"url": "https://www.youtube.com/watch?v=2"}]), "skipped")
        self.assertEqual(self.refresh(pick), "none")  # an unrelated article, no logo chosen
        self.assertEqual(len(calls), 1)
        self.assertNotIn(("page", "https://cursor.com/"), self.fetch.calls)

    def test_a_failing_judge_leaves_the_default_symbol_and_the_name_rule(self):
        def pick(question, condition, domains):
            raise RuntimeError("judge down")

        self.assertEqual(self.refresh(pick), "ready")
        self.assertNotIn("symbol", self.watch())
        self.assertNotIn("sites", self.watch()["image"])
        self.assertEqual(watch_service.list_watches("u1", db=self.db)[0]["symbol"], watch_symbols.DEFAULT_SYMBOL)
        for verdict in (None, {"symbol": "<svg>", "sites": []}, "code"):
            self.assertIsNone(watch_images._pick_visual(lambda *_: verdict, CURSOR_QUESTION, "", self.sources))

    def test_a_judge_without_domains_only_sets_the_symbol(self):
        calls = []

        def pick(question, condition, domains):
            calls.append(domains)
            return {"symbol": "code", "sites": [domain for domain in domains if domain == "cursor.com"]}

        # Created from an answer without sources: the judge saw no domain.
        self.assertEqual(self.refresh(pick, sources=[]), "kept")
        self.assertEqual(self.watch()["symbol"], "code")
        self.assertNotIn("image", self.watch())
        # So a later check with sources asks again and finds the logo.
        self.assertEqual(self.refresh(pick), "ready")
        self.assertEqual(calls, [[], ["news.test", "cursor.com"]])
        self.assertEqual(self.watch()["image"]["kind"], "logo")

    def test_a_judge_that_keeps_failing_is_asked_three_times(self):
        calls = []

        def pick(question, condition, domains):
            calls.append(domains)
            raise RuntimeError("judge down")

        sources = [{"url": "https://www.youtube.com/watch?v=1"}]
        for expected in (1, 2):
            self.assertEqual(self.refresh(pick, sources=sources), "kept")
            self.assertEqual(self.watch()["visual_tries"], expected)
            self.assertNotIn("symbol", self.watch())
        self.refresh(pick, sources=sources)
        self.assertEqual(self.watch()["symbol"], watch_symbols.DEFAULT_SYMBOL)
        # Neither the symbol nor the site choice asks again; logos fall back
        # to the name rule.
        self.assertEqual(self.refresh(pick, sources=sources), "skipped")
        self.assertEqual(self.refresh(pick), "ready")
        self.assertEqual(len(calls), 3)

    def test_slow_pages_do_not_crowd_out_the_logos(self):
        async def fetch(url, purpose):
            if url == "https://slow.test/a":
                await asyncio.sleep(5)
            return await self.fetch(url, purpose)

        with patch.object(watch_images, "ATTEMPT_SECONDS", 0.2):
            started = time.monotonic()
            found = watch_images.find_image(
                [{"url": "https://slow.test/a"}, {"url": "https://cursor.com/pricing"}],
                CURSOR_QUESTION, fetch=fetch,
            )
        self.assertEqual(found["kind"], "logo")
        self.assertLess(time.monotonic() - started, 3)

    def test_a_symbol_is_set_once(self):
        watch_images.store_result(WATCH_ID, None, db=self.db, symbol="code", attempted=False)
        watch_images.store_result(WATCH_ID, None, db=self.db, symbol="film", attempted=False)
        watch_images.store_result(WATCH_ID, None, db=self.db, symbol="<b>", attempted=False)
        self.assertEqual(self.watch()["symbol"], "code")
        self.assertNotIn("image", self.watch())

    def test_failures_of_an_older_search_do_not_count(self):
        self.watch()["image"] = {"status": "none", "attempts": 3, "tries": 3}
        self.assertTrue(watch_images.needs_image(self.watch()))
        self.assertEqual(watch_images.store_result(WATCH_ID, None, db=self.db), "none")
        image = self.watch()["image"]
        self.assertEqual((image["attempts"], image["tries"], image["version"]),
                         (1, 1, watch_images.SEARCH_VERSION))

    def test_no_judge_in_tests(self):
        self.assertIsNone(watch_images._default_pick())


class JudgeTests(unittest.TestCase):
    KEYS = {"OpenRouter": "dummy"}

    def test_the_judge_only_picks_from_its_lists(self):
        raw = json.dumps({"symbol": "briefcase", "sites": ["HS-Hannover.de", "evil.example", "uni-hannover.de",
                                                           "hs-hannover.de", "stellenwerk.de"]})
        with patch.object(consensus_engine, "_call_engine_text", return_value=raw) as call:
            result = consensus_engine.pick_watch_visual(
                "Stelle an der Hochschule Hannover?", "Eine Stelle wird ausgeschrieben",
                ["hs-hannover.de", "uni-hannover.de", "stellenwerk.de"], watch_symbols.SYMBOLS,
                self.KEYS, "OpenAI",
            )
        self.assertEqual(result, {"symbol": "briefcase", "sites": ["hs-hannover.de", "uni-hannover.de"]})
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["json_schema"]["properties"]["symbol"]["enum"], list(watch_symbols.SYMBOLS))
        self.assertIn('"stellenwerk.de"', kwargs["prompt"])
        self.assertIn("untrusted data", kwargs["prompt"])

    def test_an_unknown_symbol_is_a_failed_attempt(self):
        with patch.object(consensus_engine, "_call_engine_text",
                          return_value=json.dumps({"symbol": "unicorn", "sites": []})) as call:
            with self.assertRaises(RuntimeError):
                consensus_engine.pick_watch_visual("q", "", [], watch_symbols.SYMBOLS, self.KEYS, "OpenAI")
        self.assertGreaterEqual(call.call_count, 2)

    def test_a_stalled_judge_hands_over_without_its_retry(self):
        """Prod 2026-10-15: Luna hung twice for 120 s each before the next
        family answered; the picture of a Topic waited four minutes."""
        calls = []

        def fake(provider, *args, **kwargs):
            calls.append(provider)
            if provider == "openai":
                stop = consensus_engine.current_provider_cancellation()
                for _ in range(500):
                    if stop is not None and stop.cancelled:
                        raise consensus_engine.ProviderCancelled("stopped")
                    time.sleep(0.01)
                raise AssertionError("the stalled attempt was never stopped")
            return json.dumps({"symbol": "sparkle", "sites": ["epoch.ai"]})

        started = time.monotonic()
        with patch.object(consensus_engine, "JUDGE_ATTEMPT_SECONDS", 0.05), \
                patch.object(consensus_engine, "_call_engine_text", side_effect=fake):
            result = consensus_engine.pick_watch_visual(
                "When will AGI arrive?", "", ["epoch.ai", "metaculus.com"], watch_symbols.SYMBOLS,
                self.KEYS, "OpenAI",
            )
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(result, {"symbol": "sparkle", "sites": ["epoch.ai"]})
        self.assertEqual(calls.count("openai"), 1)
        self.assertEqual(len(calls), 2)


class SymbolTests(unittest.TestCase):
    def test_every_symbol_has_a_drawing_and_every_drawing_a_symbol(self):
        source = open("static/js/watch-dashboard.js", encoding="utf-8").read()
        block = source.split("const SYMBOL_ICONS = {", 1)[1].split("\n  };", 1)[0]
        drawn = re.findall(r"^\s{4}(\w+): '", block, flags=re.MULTILINE)
        self.assertEqual(drawn, list(watch_symbols.SYMBOLS))
        self.assertIn(watch_symbols.DEFAULT_SYMBOL, watch_symbols.SYMBOLS)
        self.assertEqual(watch_symbols.clean_symbol("nope"), watch_symbols.DEFAULT_SYMBOL)
        self.assertEqual(watch_symbols.clean_symbol("trophy"), "trophy")
        # Public pages draw the same symbols without script (Topic pages).
        drawings = dict(re.findall(r"^\s{4}(\w+): '(.*)',?$", block, flags=re.MULTILINE))
        self.assertEqual(drawings, watch_symbols.SYMBOL_PATHS)


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
        # The picture is drawn by the part Watch and Topic pages share.
        self.assertIn("check.head(watch_page.status, question, watch_page.image)", template)
        parts = open("templates/partials/check_page.html", encoding="utf-8").read()
        self.assertIn('class="wp-image is-', parts)


if __name__ == "__main__":
    unittest.main()
