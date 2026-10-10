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
        self.context = watch_images._tokens(QUESTION) | watch_images._tokens(GOAL)

    def test_the_shop_name_of_the_watched_shoe_matches(self):
        for name in (
            "adidas Adizero Adios Pro 4 Laufschuhe für Herren - SS26",
            "ADIZERO ADIOS PRO 4 SCHUH",
            "adidas Adizero Adios Pro 4 Carbon Run White JR1094 | eBay",
        ):
            self.assertGreater(watch_images.match_score(name, self.context), 0, name)

    def test_another_model_number_or_another_thing_does_not(self):
        for name in (
            "adidas Adizero Adios Pro 3 Laufschuhe",
            "Nike Vaporfly 3",
            "adidas Laufschuhe Herren",
            "adidas Adizero Adios Pro 4 Gr. 42",
        ):
            self.assertEqual(watch_images.match_score(name, self.context), 0, name)

    def test_years_only_count_when_the_question_names_one(self):
        self.assertGreater(watch_images.match_score("Adidas Adizero Adios Pro 4 (2026)", self.context), 0)
        context = watch_images._tokens("Is the MacBook Air M4 2025 under 900 euros?")
        self.assertEqual(watch_images.match_score("MacBook Air M4 2024", context), 0)
        self.assertGreater(watch_images.match_score("MacBook Air M4 2025", context), 0)


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
    def test_cited_twice_first_one_host_per_round_and_no_social_sites(self):
        sources = [
            {"url": "https://www.reddit.com/r/running/1"},
            {"url": "https://shop-a.test/p/1"},
            {"url": "https://shop-a.test/p/2"},
            {"url": "https://shop-b.test/p/9#reviews"},
            {"url": "https://shop-b.test/p/9"},
            {"url": "https://docs.test/manual.pdf"},
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
        self.assertIn('class="wp-image"', template)


if __name__ == "__main__":
    unittest.main()
