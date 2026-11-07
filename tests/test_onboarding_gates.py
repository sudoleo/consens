"""Die Schranken, die neue Nutzer vor dem ersten echten Lauf verloren.

1. Der Verifizierungs-Rauswurf: unbestaetigte Sessions wurden sofort
   ausgeloggt. Wer den Link nicht im selben Moment fand, stand wieder vor der
   Login-Maske - mit verlorener Frage.
2. Das Follow-up-Schloss: die zweite Frage einer Sitzung war Pro. Damit endete
   jede Session nach genau einer Antwort.

Diese Datei haelt die Gegenrichtung fest, damit sie nicht versehentlich
zurueckgedreht wird.
"""

from pathlib import Path

import app.core.config as cfg


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Verifizierung: bleiben statt rauswerfen
# ---------------------------------------------------------------------------

def test_unverified_sessions_are_not_signed_out_anymore():
    firebase = read("static/firebase.js")

    start = firebase.index("if (!user.emailVerified) {")
    branch = firebase[start:firebase.index("hideEmailVerificationGate();", start)]
    # Kein Rauswurf; stattdessen erscheint der Streifen. Der einzige
    # signOut ist der, den der Nutzer selbst ausloest
    # ("Use a different address").
    assert branch.count("signOut(auth)") == 1
    assert "onSignOut:" in branch
    assert "showEmailVerificationGate(" in branch
    # Ohne Server-Session und ohne persistiertes Token bleibt die Schranke
    # serverseitig bestehen (verify_user_token lehnt unbestaetigt weiter ab).
    assert '"/auth/session"' in branch
    assert 'localStorage.removeItem("id_token")' in branch


def test_verification_banner_offers_resend_and_recheck():
    template = read("templates/index.html")

    assert 'id="verifyBanner"' in template
    for part in (
        'id="verifyBannerEmail"',
        'id="verifyBannerStatus"',
        'id="verifyBannerResend"',
        'id="verifyBannerRecheck"',
        'id="verifyBannerSignOut"',
    ):
        assert template.count(part) == 1, f"expected exactly one {part}"

    banner = template[template.index('id="verifyBanner"'):]
    banner = banner[:banner.index("</section>")]
    # Der haeufigste Grund fuer "keine Mail bekommen".
    assert "spam" in banner.lower()

    module = read("static/js/email-verify.js")
    assert "function showEmailVerificationGate" in module
    assert "function hideEmailVerificationGate" in module
    assert "window.App.emailVerification = Object.freeze" in module
    # Bestaetigt wird meist in einem anderen Tab; die Rueckkehr soll reichen.
    assert "visibilitychange" in module


def test_verification_link_returns_to_the_app_with_the_typed_question():
    firebase = read("static/firebase.js")
    app_init = read("static/js/app-init.js")
    query_send = read("static/js/query-send.js")

    # Der Link fuehrt zurueck in die App, nicht in eine Firebase-Sackgasse.
    assert "/app?verified=1" in firebase
    assert "sendVerificationMail(" in firebase

    # Tippen und Absenden sind zwei Rechte: warten heisst nicht schweigen.
    assert "window.userCanTypeQuestions" in app_init
    assert "consensio.questionDraft.v1" in app_init
    # Nur echte Tastenanschlaege sind ein Entwurf: der Auth-Callback leert den
    # Composer per clearResponseBoxes und feuert dabei ein programmatisches
    # input-Event - das wuerde den Entwurf sonst loeschen, bevor er gebraucht
    # wird.
    assert "if (!event.isTrusted) return;" in app_init
    # Und weil derselbe Callback das Feld leert, muss der Entwurf danach
    # wieder hinein - nicht nur einmal beim Start.
    assert "window.App.restoreQuestionDraft" in app_init
    assert "window.App?.restoreQuestionDraft?.()" in firebase
    # Der Entwurf verschwindet mit dem echten Lauf.
    assert "clearQuestionDraft" in app_init
    assert "window.App.clearQuestionDraft?.()" in query_send


def test_registration_never_probes_account_existence_with_caller_credentials():
    firebase = read("static/firebase.js")
    register = firebase[firebase.index('fetch("/register"'):]
    register = register[:register.index("function handleForgotPassword(", 1)]

    assert "password: password" not in register
    assert "signInWithEmailAndPassword" not in register
    assert "showRegistrationSuccess(email)" in register


# ---------------------------------------------------------------------------
# 2. Follow-ups: frei, aber gezaehlt
# ---------------------------------------------------------------------------

def test_followups_are_no_longer_pro_gated():
    agent_chat = read("static/js/agent-chat.js")
    chat_router = read("app/api/routers/chat.py")

    # Folgefragen laufen im Agent weiter: kein Tier, kein
    # Badge, keine Zwischenentscheidung vor der naechsten Frage.
    assert "require_pro_for_followup" not in agent_chat
    assert "followup-pro" not in agent_chat
    assert not (ROOT / "static" / "js" / "consensus-run.js").exists()

    # Serverseitig gibt es kein Follow-up-Gate - der Kontext kostet ueber
    # das normale Tagesbudget, nicht ueber ein Tier.
    assert "require_pro_for_followup" not in chat_router


def test_free_daily_runs_allow_more_than_a_single_try():
    # Drei Runs waren ein Test, keine Gewohnheit - und mit freien Follow-ups
    # waere ein Limit von drei sofort wieder die alte Sackgasse. Das
    # Free-Konto deckt mindestens zehn typische Laeufe.
    from app.services import agent_budget_config
    config = agent_budget_config.snapshot({})
    assert config["tier_limits"]["free"] >= 10 * config["run_estimates"]["free"]["consensus"]


