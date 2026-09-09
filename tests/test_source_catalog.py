from copy import deepcopy

from app.services.llm.provider_transport import ProviderAnswer, fan_out_provider_answers
from app.services.source_catalog import canonical_source_url, normalize_source_catalog, rewrite_source_tags


def source(sid, url):
    return {"id": sid, "url": url, "title": url}


def answer(provider, text, sources):
    return ProviderAnswer(provider, "model", text, sources)


def resolve(result, provider):
    answers, _, catalog = result
    return answers[provider].response, {row["id"]: row["url"] for row in catalog}


def test_colliding_provider_local_ids_are_rewritten_before_synthesis():
    result = normalize_source_catalog({
        "openai": answer("OpenAI", "First [S1].", [source("S1", "https://a.test/a")]),
        "gemini": answer("Gemini", "Second [S1].", [source("S1", "https://b.test/b")]),
    })
    first, urls = resolve(result, "openai")
    second, _ = resolve(result, "gemini")
    assert first == "First [S1]."
    assert second == "Second [S2]."
    assert urls == {"S1": "https://a.test/a", "S2": "https://b.test/b"}


def test_deterministic_registry_order_and_input_immutability():
    answers = {
        "gemini": answer("Gemini", "B [S1]", [source("S1", "https://b.test")]),
        "openai": answer("OpenAI", "A [S1]", [source("S1", "https://a.test")]),
    }
    original = deepcopy(answers)
    assert normalize_source_catalog(answers) == normalize_source_catalog(dict(reversed(list(answers.items()))))
    assert answers == original


def test_duplicate_documents_deduplicate_and_retain_all_provider_provenance():
    normalized, model_sources, catalog = normalize_source_catalog({
        "openai": answer("OpenAI", "A [S1]", [source("S1", "https://EXAMPLE.test/Page#intro")]),
        "gemini": answer("Gemini", "B [S7]", [source("S7", "https://example.test/Page#details")]),
    })
    assert len(catalog) == 1
    assert catalog[0]["providers"] == ["OpenAI", "Gemini"]
    assert normalized["gemini"].response == "B [S1]"
    assert model_sources["Gemini"][0]["providers"] == ["OpenAI", "Gemini"]


def test_path_and_query_case_are_significant():
    urls = ["https://a.test/Page", "https://a.test/page", "https://a.test/page?x=A", "https://a.test/page?x=a"]
    _, _, catalog = normalize_source_catalog({
        "openai": answer("OpenAI", "", [source("S" + str(i + 1), url) for i, url in enumerate(urls)])
    })
    assert len(catalog) == 4
    assert canonical_source_url("HTTPS://A.test/Page#x") == "https://a.test/Page"
    assert canonical_source_url("https://a.test/Page/") != canonical_source_url("https://a.test/Page")


def test_browser_global_numbering_and_explicit_turn_sources_stay_stable():
    explicit = [source("S1", "https://a.test"), source("S2", "https://b.test"), source("S3", "https://c.test")]
    raw = {"openai": "A [S3].", "gemini": "B [S2]."}
    normalized, per_model, catalog = normalize_source_catalog(
        raw, model_sources={"OpenAI": [explicit[2]], "Gemini": [explicit[1]]}, turn_sources=explicit,
    )
    assert normalized == raw
    assert [(s["id"], s["url"]) for s in catalog] == [(s["id"], s["url"]) for s in explicit]
    assert per_model["OpenAI"][0]["id"] == "S3"


def test_explicit_turn_catalog_cannot_override_provider_local_mapping():
    normalized, _, catalog = normalize_source_catalog(
        {"openai": answer("OpenAI", "B [S1]", [source("S1", "https://b.test")])},
        turn_sources=[source("S1", "https://a.test")],
    )
    assert normalized["openai"].response == "B [S2]"
    assert {row["id"]: row["url"] for row in catalog} == {"S1": "https://a.test", "S2": "https://b.test"}


def test_ambiguous_local_ids_never_acquire_a_link_and_neither_document_is_lost():
    normalized, _, catalog = normalize_source_catalog({
        "openai": answer("OpenAI", "Ambiguous [S1]", [source("S1", "https://a.test"), source("S1", "https://b.test")]),
        "gemini": answer("Gemini", "Correct [S1]", [source("S1", "https://c.test")]),
    })
    assert normalized["openai"].response == "Ambiguous [S1]"
    assert "S1" not in {row["id"] for row in catalog}
    assert len(catalog) == 3
    assert normalized["gemini"].response == "Correct [S4]"


def test_missing_references_are_reserved_in_other_provider_namespaces():
    normalized, _, catalog = normalize_source_catalog({
        "openai": answer("OpenAI", "Unknown [S1]", []),
        "gemini": answer("Gemini", "Known [S1]", [source("S1", "https://a.test")]),
    })
    assert normalized["openai"].response == "Unknown [S1]"
    assert normalized["gemini"].response == "Known [S2]"
    assert catalog[0]["id"] == "S2"


def test_missing_ids_fall_back_to_position_but_do_not_override_explicit_ids():
    normalized, _, catalog = normalize_source_catalog({
        "openai": answer("OpenAI", "Ambiguous [S1]", [source("", "https://a.test"), source("S1", "https://b.test")]),
    })
    assert len(catalog) == 2
    assert normalized["openai"].response == "Ambiguous [S1]"
    assert "S1" not in {row["id"] for row in catalog}


def test_only_real_citation_tags_are_rewritten():
    text = "Text [S1, 2]. `code [S1]` and ``code ` [S1]``.\n```python\n[S1]\n```\n~~~\n[S1]\n~~~\n    [S1]\nAfter [S1]. Escaped \\[S1]."
    assert rewrite_source_tags(text, {"S1": "S9", "S2": "S8"}) == text.replace("Text [S1, 2]", "Text [S9, S8]").replace("After [S1]", "After [S9]")
    assert rewrite_source_tags("```inline [S1]``` then [S1]", {"S1": "S9"}) == "```inline [S1]``` then [S9]"
    assert rewrite_source_tags("[S0]", {}) == "[S0]"


def test_normalization_is_idempotent():
    first = normalize_source_catalog({
        "openai": answer("OpenAI", "A [S1] unknown [S2]", [source("S1", "https://a.test")]),
        "gemini": answer("Gemini", "B [S1]", [source("S1", "https://b.test")]),
    })
    assert normalize_source_catalog(first[0]) == first


def test_explicit_catalog_fills_sources_for_string_answers_and_accepts_aliases():
    normalized, per_model, catalog = normalize_source_catalog(
        {"anthropic": "C [S7]"}, turn_sources=[source("S7", "https://a.test")],
    )
    assert normalized == {"anthropic": "C [S7]"}
    assert per_model["Anthropic"][0]["id"] == "S7"
    normalized, _, _ = normalize_source_catalog({"anthropic": "C [S1]"}, model_sources={"Claude": [source("S1", "https://a.test")]})
    assert normalized["anthropic"] == "C [S1]"


def test_fan_out_normalizes_real_transport_results():
    answers = fan_out_provider_answers(
        question="Q", provider_models={"openai": "a", "gemini": "b"}, keys={}, tier="pro", deep_think=False,
        provider_call=lambda provider, *args: {"text": "Answer [S1]", "sources": [source("S1", f"https://{provider}.test")]},
    )
    assert answers["openai"].response == "Answer [S1]"
    assert answers["gemini"].response == "Answer [S2]"


def test_catalog_does_not_drop_sources_above_old_fifty_source_limit():
    sources = [source(f"S{i}", f"https://a.test/{i}") for i in range(1, 101)]
    normalized, _, catalog = normalize_source_catalog({"openai": answer("OpenAI", "Last [S100]", sources)})
    assert len(catalog) == 100
    assert normalized["openai"].response == "Last [S100]"


def test_malformed_explicit_id_does_not_alias_position_and_dicts_keep_text_field():
    normalized, _, catalog = normalize_source_catalog({
        "openai": {"text": "Unresolved [S1]", "sources": [source("bad-id", "https://a.test")]},
    })
    assert normalized["openai"]["text"] == "Unresolved [S1]"
    assert "response" not in normalized["openai"]
    assert catalog[0]["id"] == "S2"


def test_unclosed_and_longer_fences_preserve_all_literal_citations():
    text = "Before [S1]\n````python\n```\nLiteral [S1]\n````\nAfter [S1]\n~~~\nUnclosed [S1]"
    assert rewrite_source_tags(text, {"S1": "S2"}) == text.replace("Before [S1]", "Before [S2]").replace("After [S1]", "After [S2]")


def test_persistence_sanitizer_retains_case_sensitive_paths_aliases_and_all_citations():
    from app.services.share_snapshots import sanitize_sources
    from app.services.public_markdown import render_public_markdown

    sources = [source(f"S{i}", f"https://example.test/source/{i}") for i in range(1, 79)]
    sources += [source("S79", "https://example.test/Page"), source("S80", "https://example.test/page"),
                source("S81", "https://example.test/Page#alias"),
                source("S81", "https://EXAMPLE.test/Page#duplicate")]
    normalized = sanitize_sources(sources)
    assert len(normalized) == 81
    assert {row["id"]: row["url"] for row in normalized}["S80"] == "https://example.test/page"
    assert {row["id"]: row["url"] for row in normalized}["S79"] == "https://example.test/Page"
    assert sanitize_sources(normalized) == normalized
    html = render_public_markdown("Uppercase [S79]. Lowercase [S80]. Alias [S81].", normalized)
    assert all(f'href="#src-{index}"' in html for index in (79, 80, 81))


def test_chat_model_and_turn_normalization_roundtrip_entire_source_catalog():
    from app.services.chat_store import normalize_model_answers, normalize_turn_sources, model_answer_metadata

    sources = [source(f"S{i}", f"https://example.test/{i}") for i in range(1, 101)]
    normalized = normalize_model_answers({"OpenAI": {"answer": "Last reference [S100]", "sources": sources}})
    stored = normalized["OpenAI"]
    assert len(stored["sources"]) == 100
    restored = model_answer_metadata(stored)
    assert restored["sources"] == stored["sources"]
    assert normalize_turn_sources(sources) == stored["sources"]
    assert restored["sources"][-1]["id"] == "S100"


def test_source_check_plan_preserves_validated_shared_provider_provenance():
    from app.services.source_verification import source_records, plan_source_verification

    raw = {
        "OpenAI": [dict(source("S1", "https://example.test/Page"), providers=["OpenAI", "unknown", {"bad": "input"}])],
        "Gemini": [dict(source("S1", "https://EXAMPLE.test/Page#details"), providers=["claude", "Gemini"])],
        "Grok": [source("S1", "https://different.test")],
    }
    records = source_records(raw)
    assert len(records) == 2
    assert records[0]["providers"] == ["OpenAI", "Anthropic", "Gemini"]
    assert records[1]["providers"] == ["Grok"]
    plan = plan_source_verification(question="Q", consensus="The product has a price of 20 euros. [S1]", sources=raw)
    assert plan["snapshot"]["sources"][0]["providers"] == ["OpenAI", "Anthropic", "Gemini"]
    assert plan["packages"][0]["sources"] == plan["snapshot"]["sources"]
