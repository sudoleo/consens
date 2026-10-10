import unittest

from app.services.llm.citations import (
    SOURCE_SNIPPET_MAX_CHARS,
    is_search_result,
    parse_openrouter_response,
    presearch_end,
    result_sources,
    result_text,
    shift_citation,
)


class OpenRouterCitationParsingTests(unittest.TestCase):
    def test_url_annotations_become_deduplicated_tagged_sources(self):
        text = "The first claim is supported. The second claim is also supported."
        parsed = parse_openrouter_response(
            text,
            [
                {
                    "type": "url_citation",
                    "url_citation": {
                        "url": "https://example.com/article/",
                        "title": "Example article",
                        "content": "first claim",
                        "start_index": 0,
                        "end_index": 27,
                    },
                },
                {
                    "type": "url_citation",
                    "url_citation": {
                        "url": "https://example.com/article",
                        "title": "Duplicate title",
                        "content": "second claim",
                        "start_index": 28,
                        "end_index": len(text),
                    },
                },
                {"type": "text", "text": "ignored"},
            ],
            "openai",
        )

        self.assertEqual(len(result_sources(parsed)), 1)
        self.assertEqual(result_sources(parsed)[0]["id"], "S1")
        self.assertEqual(result_sources(parsed)[0]["title"], "Example article")
        self.assertEqual(result_sources(parsed)[0]["snippet"], "first claim")
        self.assertEqual(result_sources(parsed)[0]["provider"], "openai")
        self.assertEqual(result_text(parsed).count("[S1]"), 2)

    def test_invalid_annotations_are_ignored_and_text_is_preserved(self):
        text = "No usable citation here."
        parsed = parse_openrouter_response(
            text,
            [
                {"type": "citation", "url_citation": {"url": "https://ignored.example"}},
                {"type": "url_citation", "url_citation": {"title": "Missing URL"}},
                {"type": "url_citation", "url_citation": {"url": ""}},
            ],
        )
        self.assertEqual(result_text(parsed), text)
        self.assertEqual(result_sources(parsed), [])

    def test_page_sized_annotation_content_is_clipped_to_a_teaser(self):
        """OpenRouter schickt in `content` den Seitentext, nicht den Beleg.

        Gemessen bis ~4.000 Zeichen je Quelle. Ungekuerzt stand die halbe
        Seite in der Quellenliste unter der Antwort.
        """
        page = " ".join("wort%d" % i for i in range(1200))
        parsed = parse_openrouter_response(
            "Belegter Satz.",
            [{
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.com/lang",
                    "title": "Lange Seite",
                    "content": page,
                    "end_index": 14,
                },
            }],
        )

        snippet = result_sources(parsed)[0]["snippet"]
        self.assertLessEqual(len(snippet), SOURCE_SNIPPET_MAX_CHARS + 1)
        self.assertTrue(snippet.endswith("…"))
        self.assertTrue(snippet.startswith("wort0 wort1 "))
        # `extract` ist derselbe Teaser, nicht die ungekuerzte Fassung.
        self.assertEqual(result_sources(parsed)[0]["extract"], snippet)

    def test_short_snippets_stay_untouched(self):
        parsed = parse_openrouter_response(
            "Belegter Satz.",
            [{
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.com/kurz",
                    "content": "  Ein   kurzer Beleg.  ",
                    "end_index": 14,
                },
            }],
        )
        self.assertEqual(result_sources(parsed)[0]["snippet"], "Ein kurzer Beleg.")

    def test_zero_width_annotation_never_precedes_the_answer(self):
        parsed = parse_openrouter_response(
            "Die Antwort beginnt hier.",
            [{
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.com/zero",
                    "title": "Zero-width source",
                    "start_index": 0,
                    "end_index": 0,
                },
            }],
        )

        self.assertEqual(result_text(parsed), "Die Antwort beginnt hier. [S1]")

    def test_stream_fallback_advances_to_the_next_sentence_boundary(self):
        parsed = parse_openrouter_response(
            "Der erste belegte Satz endet hier. Danach folgt Kontext.",
            [{
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.com/claim",
                    "start_index": 0,
                    "end_index": 0,
                    "_stream_text_end_index": 18,
                },
            }],
        )

        self.assertEqual(
            result_text(parsed),
            "Der erste belegte Satz endet hier. [S1] Danach folgt Kontext.",
        )

    def test_invalid_offset_does_not_split_a_word(self):
        parsed = parse_openrouter_response(
            "Eine belegte Aussage.",
            [{
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.com/word",
                    "start_index": 0,
                    "end_index": 8,
                },
            }],
        )

        self.assertEqual(result_text(parsed), "Eine belegte [S1] Aussage.")


class PresearchTextTests(unittest.TestCase):
    def test_only_citations_without_a_span_mark_arriving_results(self):
        self.assertTrue(is_search_result({"start_index": 0, "end_index": 0}))
        self.assertTrue(is_search_result({}))
        self.assertFalse(is_search_result({"start_index": 3, "end_index": 9}))
        self.assertFalse(is_search_result({"end_index": 9}))

    def test_cut_needs_text_before_and_more_answer_after(self):
        text = "I will search. The rate is 2.5% since March."
        self.assertEqual(presearch_end(text, 14), 14)
        for results_at in (None, 0, len(text), len(text) + 5):
            self.assertEqual(presearch_end(text, results_at), 0)
        self.assertEqual(presearch_end("   " + text, 3), 0)
        # An answer from memory, merely confirmed afterwards, stays whole.
        self.assertEqual(presearch_end(text + " Confirmed.", len(text)), 0)

    def test_shifted_citation_follows_the_text(self):
        cut = 10
        moved = shift_citation({"start_index": 14, "end_index": 20, "fallback_end_index": 25}, cut)
        self.assertEqual(moved, {"start_index": 4, "end_index": 10, "fallback_end_index": 15})
        # Arriving results keep 0/0; a span inside the cut is gone.
        self.assertEqual(shift_citation({"start_index": 0, "end_index": 0, "fallback_end_index": 10}, cut),
                         {"start_index": 0, "end_index": 0, "fallback_end_index": 0})
        self.assertEqual(shift_citation({"start_index": 2, "end_index": 8, "_stream_text_end_index": 9}, cut,
                                        "_stream_text_end_index"),
                         {"start_index": 0, "end_index": 0, "_stream_text_end_index": 0})
        self.assertEqual(shift_citation({"start_index": None, "end_index": 12}, cut), {"start_index": None, "end_index": 2})


if __name__ == "__main__":
    unittest.main()
