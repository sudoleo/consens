"""The finding: the one sentence a Topic page states before anything else."""

from app.services import topic_finding


def claim(label, *, streak=5, models=4, run_models=4, contested=False,
          holding=True, is_new=False):
    return {
        "label": label,
        "streak": streak,
        "appearances": streak,
        "model_count": models,
        "run_model_count": run_models,
        "contested": contested,
        "holding": holding,
        "is_new": is_new,
    }


def ledger(*, holding=(), new=(), contested=()):
    return {
        "holding": list(holding),
        "new": list(new),
        "contested": list(contested),
        "retired": [],
    }


def record(*, checks=5, changed_now=False, steady=3):
    return {
        "checks": checks,
        "changed_now": changed_now,
        "steady_checks": steady,
        "steady_days": steady,
        "first_display": "Jul 23, 2026",
        "latest_display": "Aug 19, 2026",
    }


def test_the_finding_is_the_claim_the_record_puts_first():
    """Held longest wins; on a tie the shorter sentence does, because the
    finding is read at a glance and not parsed."""
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("The GPT-5.6 family is the current frontier line, and it "
                  "covers the Sol, Terra and Luna variants", streak=5),
            claim("OpenAI has not announced a release date for GPT-6", streak=5),
            claim("Pricing has not been published", streak=2),
        ]),
        record(),
        {"consensus_md": "Something else entirely."},
    )

    assert found["line"] == "OpenAI has not announced a release date for GPT-6."
    assert found["source"] == "claim"
    assert found["state"] == "settled"
    assert found["voice"] == "All 4 models say the same"


def test_a_contested_claim_never_becomes_the_finding():
    """The page cannot state as settled fact something the models state
    differently -- but it has to say that the disagreement is there."""
    found = topic_finding.build_finding(
        ledger(
            holding=[claim("OpenAI has not announced a release date", streak=4)],
            contested=[claim("Ships in 2026", contested=True, streak=9)],
        ),
        record(),
        {},
    )

    assert found["line"] == "OpenAI has not announced a release date."
    assert found["state"] == "split"
    assert found["state_label"] == "The models disagree"
    assert found["split_count"] == 1


def test_a_check_that_moved_the_answer_outranks_every_other_state():
    found = topic_finding.build_finding(
        ledger(holding=[claim("A launch window is now on record", streak=2)]),
        record(changed_now=True),
        {},
    )

    assert found["state"] == "moved"


def test_a_claim_only_some_models_state_says_so_in_the_finding():
    found = topic_finding.build_finding(
        ledger(holding=[claim("No date is on record", models=3, run_models=4)]),
        record(),
        {},
    )

    assert found["voice"] == "3 of 4 models state this"


def test_supporting_lines_never_repeat_the_finding_or_run_long():
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("OpenAI has not announced a release date for GPT-6", streak=6),
            # Same statement, different wording: nothing gained by printing it.
            claim("OpenAI has announced no release date for GPT-6 so far", streak=4),
            claim("GPT-5.6 is the current flagship", streak=4),
            # A paragraph, not a supporting sentence.
            claim("A" * (topic_finding.MAX_SUPPORT_LINE + 5), streak=4),
            claim("Pricing has not been published", streak=3),
        ]),
        record(),
        {},
    )

    assert found["support"] == [
        "GPT-5.6 is the current flagship.",
        "Pricing has not been published.",
    ]


def test_an_editorial_headline_wins_over_the_derived_one():
    found = topic_finding.build_finding(
        ledger(holding=[claim("OpenAI has not announced a release date")]),
        record(),
        {"headline": "still no gpt-6 date"},
    )

    assert found["line"] == "Still no gpt-6 date."
    assert found["source"] == "editorial"


def test_a_topic_without_a_position_map_still_states_an_answer():
    """Manually seeded Topics carry no claims. The first sentence of the
    consensus is a weaker finding than a tracked claim, and still beats a
    score as the first thing on the page."""
    found = topic_finding.build_finding(
        None,
        record(checks=1, steady=0),
        {"consensus_md": "**No confirmed release date exists.** Everything "
                         "circulating is speculation."},
    )

    assert found["line"] == "No confirmed release date exists."
    assert found["source"] == "consensus"
    assert found["state"] == "first"
    assert found["support"] == []


def test_a_run_with_nothing_to_state_produces_no_finding():
    assert topic_finding.build_finding(None, record(), {}) is None
    assert topic_finding.build_finding(None, None, None) is None


def test_a_long_claim_stays_one_sentence_and_is_marked_as_long():
    long_claim = (
        "As of the latest official information available, there is no confirmed "
        "OpenAI blog post, product page, API model entry or release note that "
        "says when GPT-6 will launch"
    )
    found = topic_finding.build_finding(
        ledger(holding=[claim(long_claim)]), record(), {}
    )

    assert found["line"] == long_claim + "."
    assert found["is_long"] is True


def test_a_clipped_claim_is_restated_from_the_consensus_it_came_from():
    """Position Map labels are stored clipped. The finding is the statement,
    not the truncation, so the wording comes back from the answer itself."""
    clipped = (
        "The current evidence supports a qualified yes: AI has solved some "
        "previously open mathematical problems and has materially advanced "
        "others, but the strongest claims sti…"
    )
    full = (
        "The current evidence supports a qualified yes: AI has solved some "
        "previously open mathematical problems and has materially advanced "
        "others, but the strongest claims still come from a small number of "
        "highly publicised cases."
    )
    found = topic_finding.build_finding(
        ledger(holding=[claim(clipped, streak=4)]),
        record(),
        {"consensus_md": full + " What is most convincing right now."},
    )

    assert found["line"] == full
    assert "…" not in found["line"]


def test_a_clipped_claim_with_no_match_falls_back_to_a_whole_sentence():
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("Some entirely unrelated wording that was cut off here…", streak=4),
            claim("OpenAI has not announced a release date for GPT-6", streak=2),
        ]),
        record(),
        {"consensus_md": "A consensus about something else completely."},
    )

    assert found["line"] == "OpenAI has not announced a release date for GPT-6."


def test_a_mid_sentence_fragment_is_never_the_finding_or_a_supporting_line():
    """A label that starts lower-case is the tail of a quoted sentence."""
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("it was a real research problem, not a benchmark;", streak=9),
            claim("AI has advanced several open problems", streak=3),
        ]),
        record(),
        {"consensus_md": "Nothing comparable here."},
    )

    assert found["line"] == "AI has advanced several open problems."
    assert found["support"] == []


def test_a_claim_that_held_through_a_fraction_of_the_record_is_not_settled():
    """Two restatements out of twenty checks is churn, not a settled answer."""
    churning = topic_finding.build_finding(
        {**ledger(holding=[claim("AI has advanced several open problems", streak=2)]),
         "enumerated": 18},
        record(checks=20),
        {},
    )
    steady = topic_finding.build_finding(
        {**ledger(holding=[claim("AI has advanced several open problems", streak=15)]),
         "enumerated": 18},
        record(checks=20),
        {},
    )

    assert churning["state"] == "forming"
    assert churning["state_label"] == "Still forming"
    assert steady["state"] == "settled"


def test_a_statement_that_ends_inside_a_quotation_keeps_one_full_stop():
    found = topic_finding.build_finding(
        ledger(holding=[claim(
            "Google referred to progress on \u201cour new models including "
            "Gemini 4.\u201d"
        )]),
        record(),
        {},
    )

    assert found["line"].endswith("Gemini 4.\u201d")


def test_a_new_dispute_never_leads_even_though_new_claims_are_listed_together():
    """/topics/gpt-6-release-date, 2026-10-05: the ledger lists claims that
    only just entered in one group, disputed or not, and the finding took
    "OpenAI has officially announced and released a model named GPT-6
    Astra" from it -- a disputed point (one model said there is no such
    release) with every model that took any side counted as "stating" it."""
    disputed = claim(
        "OpenAI has officially announced and released a model named GPT-6 Astra",
        streak=1, models=3, contested=True, is_new=True,
    )
    found = topic_finding.build_finding(
        ledger(
            new=[disputed],
            holding=[claim("OpenAI has not published a release date for GPT-6", streak=1)],
        ),
        record(),
        {"consensus_md": "I do not have confirmed OpenAI documentation of GPT-6."},
    )

    assert found["line"] == "OpenAI has not published a release date for GPT-6."
    assert found["voice"] == "All 4 models say the same"

    alone = topic_finding.build_finding(
        ledger(new=[disputed]), record(),
        {"consensus_md": "There is no confirmed GPT-6 release. More detail follows."},
    )
    assert alone["source"] == "consensus"
    assert alone["line"] == "There is no confirmed GPT-6 release."
    assert alone["voice"] == ""


def test_a_disputed_claim_is_never_a_supporting_line():
    found = topic_finding.build_finding(
        ledger(
            holding=[claim("OpenAI has not published a release date for GPT-6", streak=6)],
            new=[claim("Official benchmark numbers and pricing are published",
                       streak=1, contested=True, is_new=True)],
        ),
        record(),
        {},
    )

    assert found["support"] == []


def test_fewer_than_three_models_carry_no_derived_finding():
    """/topics/gemini-4-release-date: "All 2 models" is a pair, not a panel."""
    pair = claim("Google has confirmed that Gemini 4 is in training", models=2, run_models=2)
    found = topic_finding.build_finding(
        ledger(holding=[pair]), record(),
        {"consensus_md": "Google has confirmed Gemini 4 is in training.",
         "models": ["Gemini", "OpenAI"]},
    )
    assert found is None

    # A wider claim further down the record still leads.
    found = topic_finding.build_finding(
        ledger(holding=[pair, claim("No release date for Gemini 4 is on record", streak=2, models=3)]),
        record(), {},
    )
    assert found["line"] == "No release date for Gemini 4 is on record."


def test_a_question_label_is_not_a_finding():
    """/topics/unsolved-math-problems-solved-by-ai led with "Whether AI has
    fully formalized Fermat's Last Theorem in Lean." -- the judge's name for
    a disputed point, not a statement."""
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("Whether AI has fully formalized Fermat's Last Theorem in Lean", streak=9),
            claim("Has AI solved the Navier-Stokes problem?", streak=8),
            claim("AI has produced new results on some previously open problems", streak=3),
        ]),
        record(), {},
    )

    assert found["line"] == "AI has produced new results on some previously open problems."
    assert topic_finding._is_question("When will GPT-6 ship")
    assert not topic_finding._is_question("OpenAI has not announced GPT-6")


def test_a_label_written_in_another_language_is_not_a_finding():
    found = topic_finding.build_finding(
        ledger(holding=[
            claim("Status de Pr\u00e9-Treinamento: A Google confirmou que o Gemini 4 "
                  "est\u00e1 em fase de pr\u00e9-treinamento", streak=6),
            claim("Google has confirmed that Gemini 4 is in post-training", streak=3),
        ]),
        record(), {},
    )

    assert found["line"] == "Google has confirmed that Gemini 4 is in post-training."
    assert topic_finding._reads_as_english("GPT-6 launched December 2026")
    assert not topic_finding._reads_as_english("Die Ver\u00f6ffentlichung ist nicht best\u00e4tigt und das Datum fehlt")
