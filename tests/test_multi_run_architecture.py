"""Source-level contracts for the browser-session multi-run boundary.

Behavioral isolation is covered by tests/js/run-registry.test.mjs and
tests/js/multi-run-view.test.mjs. These checks protect the script order and the
explicit context hand-offs that are easy to accidentally bypass later.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_registry_is_the_single_browser_session_owner_and_loads_before_consumers():
    bundles = read("static/js/bundles.json")
    registry = read("static/js/run-registry.js")

    assert bundles.index("static/js/run-registry.js") < bundles.index("static/firebase.js")
    assert bundles.index("static/js/run-view.js") < bundles.index("static/js/query-send.js")
    assert "const MAX_ACTIVE_RUNS = 2" in registry
    assert "const runs = new Map()" in registry
    assert "let visibleRunId = null" in registry
    assert "let selectedConversationBasis = null" in registry
    assert "conversationLocks = new Map()" in registry
    assert '"parallel_limit"' in registry
    assert '"conversation_busy"' in registry
    assert '"conversation_uncertain"' in registry
    assert "deepFreeze(cloneValue(spec.config" in registry
    assert "cancelAll(reason)" in registry
    assert "clearAll(reason" in registry


def test_query_callbacks_use_their_bound_context_not_visible_dom():
    query = read("static/js/query-send.js")
    sources = read("static/js/sources.js")

    assert "async function runProvider(context, providerConfig" in query
    assert "registry.isExecuting(context.runId)" in query
    assert "registry.isVisible(context.runId)" in query
    assert "context.config.providers.map(provider => runProvider(context" in query
    assert "persistenceOptions(context)" in query
    assert 'document.getElementById("openaiResponse")' not in query
    assert "window.currentEvidenceSources =" not in query
    assert "prepareResponseSourcesForEvidence" in sources

    # The Consensus pipeline left the browser on 2026-10-25: no script
    # starts it, and no bridge reaches it from the visible DOM.
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [*(ROOT / "static" / "js").glob("*.js"), ROOT / "static" / "firebase.js"]
    )
    for gone in ("executeConsensusRun", "window.getConsensus =", "saveBookmarkConsensus",
                 "consensusPipeline", "consensusLifecycle", "cancelCurrentConsensus"):
        assert gone not in scripts, gone


def test_bookmark_view_and_logout_keep_run_ownership_explicit():
    firebase = read("static/firebase.js")
    view = read("static/js/run-view.js")
    init = read("static/js/app-init.js")
    insights = read("static/js/consensus-insights.js")

    assert "runOptions?.runId" in firebase
    assert "conversation?.runId" in firebase
    assert "window.App?.runRegistry?.showSavedView?.(" in firebase
    assert 'window.App?.runRegistry?.clearAll?.("logout")' in firebase
    assert "restoreRegistryRunRows()" in firebase
    assert "clearPreparedBookmarkShareResult();" in firebase.split(
        'window.addEventListener("consensio:run-registry-change"', 1
    )[1].split("function publishAuthState", 1)[0]
    assert "expectedVersion" in firebase
    assert "versionParts" in firebase

    assert "registry.setProjector(project)" in view
    # A run switch clears what a saved answer left on screen: a comparison
    # opened next to it must not inherit its consensus or its footer.
    assert "clearConsensus();" in view
    assert "window.App.consensusFooter?.clear?.()" in view
    assert 'row.dataset.runId = context.runId' in view
    # One delegated listener opens every run row, also one that became a
    # saved row in place (Apple audit C7/A11).
    assert "registry.show(row.dataset.runId);\n    window.App.chatScroll?.opened?.();" in view
    assert '"#bookmarksContainer .bookmark.run-entry[data-run-id]"' in view
    assert "if (registry.isVisible(context.runId))" not in view  # projector is already selected-only

    new_comparison = init.split('getElementById("newRunButton")', 1)[1].split(
        "// Fenstergröße", 1
    )[0]
    assert "cancelCurrentQuery" not in new_comparison
    assert "cancelCurrentConsensus" not in new_comparison
    assert "clearResponseBoxes" in new_comparison

    # A saved contradiction shows its stored Resolve result; the browser
    # starts no new round against the visible run (2026-10-25).
    assert "function runResolveRound" not in insights
    assert "resolutionBindingIsWritable" not in insights
