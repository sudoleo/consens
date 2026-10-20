"""Watch mails and Telegram read like the app (Apple audit K1, K2, K4-K9).

The answer is rendered, never escaped Markdown; mails use the app's tokens
with a dark mode; the success mail names goal and question; Telegram
confirms on the message itself. Builders are called directly, Telegram's Bot
API is a mock, Firestore is the in-memory FakeDb: nothing leaves the process.
"""
from copy import deepcopy
from html import unescape
from unittest.mock import Mock, patch
import re

import pytest

from test_watch_feature import FakeDb, share

from app.services import (
    mailer, notification_delivery, notification_markdown, notification_outbox,
    telegram_watch, watch_service,
)


# A typical model answer: heading, bold, list, table, a link, citations,
# chat framing around it and an image a model wrote.
ANSWER = (
    "Here's the current picture:\n\n"
    "## Short answer\n\n"
    "**GPT-6 was released on 14 October 2026** for Plus and the API [S1][S2].\n\n"
    "## Availability\n\n"
    "- EU: *yes*, at launch [S3]\n"
    "- Free tier: rolling out\n\n"
    "| Region | Status |\n|---|---|\n| US | live |\n| EU | **live** |\n\n"
    "![tracker](https://pixel.example/open.png)\n\n"
    "Sources: [OpenAI blog](https://openai.com/blog/gpt-6) [S9]\n\n"
    "If you want, I can also track the price."
)

ANSWER_SOURCES = [
    {"id": "S1", "title": "Introducing GPT-6", "url": "https://openai.com/index/gpt-6/"},
    {"id": "S2", "title": "Rollout", "url": "https://www.theverge.com/gpt-6"},
    {"id": "S3", "title": "EU", "url": "https://www.reuters.com/gpt-6-eu"},
]

MARKDOWN_SIGNS = re.compile(r"\*\*|##|\|-{3}|\]\(|!\[|\[S\d")

SITE = "https://consens.io"

def _parts(message):
    return (
        message.get_body(preferencelist=("html",)).get_content(),
        message.get_body(preferencelist=("plain",)).get_content(),
    )

def _visible(markup):
    """What a reader sees: no head, no tags, entities resolved."""
    body = markup.split("</head>", 1)[-1]
    return unescape(re.sub(r"<[^>]+>", " ", body))

def _run_mail(**overrides):
    kwargs = {
        "recipient": "owner@example.test", "question": "Will GPT-6 be out in the EU?",
        "delta": {"summary": "It was released."}, "moved": True, "consensus": ANSWER,
        "share_url": SITE + "/s/q", "unsubscribe_url": SITE + "/watch/unsubscribe?token=x",
        "answer_sources": ANSWER_SOURCES,
    }
    return mailer.build_run_message(**{**kwargs, **overrides})

def _condition_mail(**overrides):
    kwargs = {
        "recipient": "owner@example.test", "question": "Will the iPhone 18 go on sale in Germany?",
        "goal": "It is on sale in Germany", "reason": "Apple's German store lists it.",
        "sources": [{"title": "Apple Store", "url": "https://www.apple.com/de/shop"}],
        "consensus": ANSWER, "share_url": SITE + "/s/q",
        "unsubscribe_url": SITE + "/watch/unsubscribe?token=x", "answer_sources": ANSWER_SOURCES,
    }
    return mailer.build_condition_message(**{**kwargs, **overrides})

def _all_mails():
    unsub = SITE + "/watch/unsubscribe?token=x"
    delta = {"summary": "It moved.", "goal": "A date is set"}
    return {
        "change": mailer.build_change_message(
            recipient="o@example.test", question="Q?", delta=delta, share_url=SITE, unsubscribe_url=unsub),
        "run": _run_mail(),
        "condition": _condition_mail(),
        "paused": mailer.build_paused_message(
            recipient="o@example.test", question="Q?", share_url=SITE, unsubscribe_url=unsub,
            resume_url=SITE + "/watch/resume?token=r"),
        "brief": mailer.build_brief_message(
            recipient="o@example.test", date_label="Tuesday", items=[], changes_count=0,
            site_url=SITE, unsubscribe_url=unsub),
        "follower": mailer.build_follower_change_message(
            recipient="r@example.test", question="Q?", delta=delta, share_url=SITE, unsubscribe_url=unsub),
        "follow_confirm": mailer.build_follow_confirm_message(
            recipient="r@example.test", question="Q?", confirm_url=SITE + "/c", share_url=SITE),
        "topic_confirm": mailer.build_topic_follow_confirm_message(
            recipient="r@example.test", title="T", confirm_url=SITE + "/c", topic_url=SITE + "/topics/t"),
        "topic_change": mailer.build_topic_change_message(
            recipient="r@example.test", title="T", question="Q?", delta=delta,
            topic_url=SITE + "/topics/t", unsubscribe_url=unsub),
    }

@pytest.mark.parametrize("build", [_run_mail, _condition_mail], ids=["every_check", "goal_reached"])
def test_mail_shows_the_answer_rendered_not_as_markdown(build):
    markup, plain = _parts(build())
    answer = markup.split("The answer", 1)[1]
    assert re.search(r"<h2[^>]*>Availability</h2>", answer)
    assert re.search(r"<strong[^>]*>GPT-6 was released on 14 October 2026</strong>", answer)
    assert re.search(r"<li[^>]*>EU: <em[^>]*>yes</em>", answer)
    assert re.search(r"<th[^>]*>Region</th>", answer) and "<td" in answer
    assert re.search(r'<a href="https://openai.com/blog/gpt-6"[^>]*>OpenAI blog</a>', answer)
    # [S1] becomes a small link to its source; an unknown [S9] disappears.
    assert re.search(r'<a href="https://openai.com/index/gpt-6/"[^>]*>openai</a>', answer)
    assert not MARKDOWN_SIGNS.search(_visible(markup)), MARKDOWN_SIGNS.findall(_visible(markup))
    # Chat framing goes; a URL from the answer never loads in a mail client.
    assert "Here's the current picture" not in markup and "track the price" not in markup
    assert "pixel.example" not in markup
    # Inline styles only: mail clients drop page CSS for content.
    assert "<link" not in markup and "class=\"" in answer and "style=\"" in answer
    text_answer = plain.split("THE ANSWER", 1)[1]
    assert not MARKDOWN_SIGNS.search(text_answer)
    assert "- EU: yes, at launch" in text_answer and "Region | Status" in text_answer
    assert "OpenAI blog (https://openai.com/blog/gpt-6)" in text_answer

def test_answer_markup_escapes_what_a_model_writes():
    markup = notification_markdown.answer_mail_html(
        'Use <script>alert(1)</script> & [x](javascript:alert(1)) "quoted"',
        palette=mailer.MAIL_PALETTE,
    )
    assert "<script" not in markup and "&lt;script&gt;" in markup
    assert 'href="javascript' not in markup

def test_telegram_answer_uses_only_the_html_telegram_accepts():
    for limit in (120, 300, 600, 1_500):
        markup = notification_markdown.answer_telegram(ANSWER, sources=ANSWER_SOURCES, limit=limit)
        assert len(markup) <= limit + 1
        tags = re.findall(r"</?([a-z]+)", markup)
        assert set(tags) <= {"b", "i", "s", "code", "a"}, (limit, tags)
        # Every tag that opens also closes: the budget never cuts inside one.
        for tag in set(tags):
            assert markup.count(f"<{tag}") == markup.count(f"</{tag}>"), (limit, tag, markup)
        assert not MARKDOWN_SIGNS.search(unescape(re.sub(r"<[^>]+>", "", markup)))
    full = notification_markdown.answer_telegram(ANSWER, sources=ANSWER_SOURCES)
    assert "<b>GPT-6 was released on 14 October 2026</b>" in full
    assert "• EU: <i>yes</i>, at launch" in full
    assert '<a href="https://openai.com/blog/gpt-6">OpenAI blog</a>' in full
    assert "Region · Status" in full and "pixel.example" not in full

def test_telegram_every_check_and_goal_reached_carry_the_rendered_answer():
    view = {"question": "Q?", "condition": "A date is set"}
    result = {"delta": {"summary": "It moved."}, "moved": True,
              "consensus": ANSWER, "consensus_sources": ANSWER_SOURCES,
              "condition_reason": "The date is 15 September.",
              "condition_sources": [{"title": "Press", "url": "https://example.com/press"}]}
    for kind in ("every_run", "condition"):
        text = telegram_watch._notification_text(kind, view, result)
        quote_block = text.split("<b>The answer</b>\n", 1)[1]
        assert quote_block.startswith("<blockquote expandable><b>GPT-6 was released")
        assert "**" not in text and "##" not in text and "|---" not in text
        assert len(text) < 4_096
    # K4: the one success message names its sources like the mail does.
    condition = telegram_watch._notification_text("condition", view, result)
    assert condition.count("<b>Why</b>") == 1
    assert '<a href="https://example.com/press">Press</a>' in condition
    assert "You were waiting for" in condition

def test_every_mail_has_the_app_look_and_a_dark_mode():
    for name, message in _all_mails().items():
        markup, _plain = _parts(message)
        head = markup.split("</head>", 1)[0]
        assert '<html lang="en">' in markup, name
        for meta in ('name="viewport"', 'name="color-scheme" content="light dark"',
                     'name="supported-color-schemes" content="light dark"'):
            assert meta in head, (name, meta)
        assert re.search(r"<title>[^<]+</title>", head), name
        assert "@media (prefers-color-scheme: dark)" in head and ".cx-ink{color:#ededed!important}" in head
        lowered = markup.lower()
        assert "#335cff" not in lowered and "text-transform:uppercase" not in lowered, name
        # The one filled button is black with white text, as in the app.
        if 'class="cx-btn"' in markup:
            assert f"background:{mailer.INK}" in markup and f"color:{mailer.BUTTON_TEXT}" in markup
        # Footer links carry a colour instead of the client's default blue.
        for link in re.findall(r"<a [^>]*>", markup.split("</head>", 1)[1]):
            assert "color:" in link, (name, link)

def test_goal_reached_mail_names_goal_and_question_and_says_why_once():
    message = _condition_mail()
    assert message["Subject"] == (
        "Reached: It is on sale in Germany · Will the iPhone 18 go on sale in Germany?"
    )
    markup, plain = _parts(message)
    assert markup.count(">Why</p>") == 1 and plain.count("WHY") == 1
    assert ">You were waiting for</p>" in markup and ">Waiting for</p>" not in markup
    why = markup.split(">Why</p>", 1)[1].split(">Question</p>", 1)[0]
    assert "Apple&#x27;s German store lists it." in why and "https://www.apple.com/de/shop" in why
    assert "YOU WERE WAITING FOR\nIt is on sale in Germany" in plain

def test_subjects_end_at_a_word_and_the_preview_does_not_repeat_the_mail():
    question = "Will the European Commission publish its final guidance on general-purpose AI models before the end of 2026?"
    message = mailer.build_change_message(
        recipient="o@example.test", question=question, delta={"summary": "A draft appeared. Details follow."},
        share_url=SITE, unsubscribe_url=SITE + "/u",
    )
    subject = message["Subject"]
    assert subject.endswith("…")
    clipped = subject.removeprefix("Moved: ").removesuffix("…")
    assert question.startswith(clipped) and question[len(clipped)] == " "
    markup, _plain = _parts(message)
    preheader = re.search(r'<div style="display:none[^>]*>(.*?)</div>', markup).group(1)
    # The preheader says the change, then invisible filler keeps the client
    # from pulling the mail's first lines into the preview.
    assert preheader.startswith("A draft appeared.") and preheader.count("&zwnj;") >= 40

def test_brief_opens_the_watches_and_writes_reached_goals_and_zones_like_people():
    items = [
        {"question": "Reached one?", "status": "resolved", "goal": "It is on sale",
         "share_path": "/s/a", "interval": "daily", "run_time": "07:00", "timezone": "Europe/Berlin",
         "resolution": {"reason": "Apple lists it."}},
        {"question": "Local one?", "status": "active", "goal": "A date is set",
         "share_path": "/s/b", "interval": "daily", "run_time": "09:00", "timezone": "Europe/Berlin",
         "new_points": []},
        {"question": "Far one?", "status": "active", "goal": "",
         "share_path": "/s/c", "interval": "weekly", "run_weekday": "monday", "run_time": "08:30",
         "timezone": "America/Los_Angeles", "new_points": []},
    ]
    message = mailer.build_brief_message(
        recipient="o@example.test", date_label="Tuesday", items=items, changes_count=1,
        site_url=SITE, unsubscribe_url=SITE + "/u", brief_timezone="Europe/Berlin",
    )
    markup, plain = _parts(message)
    assert f'href="{SITE}/app/watches"' in markup and f"Open your watches: {SITE}/app/watches" in plain
    assert f'href="{SITE}/app"' not in markup
    reached_row = markup.split("Reached one?", 1)[1].split("Local one?", 1)[0]
    assert "<strong" in reached_row and "Reached.</strong> Apple lists it." in reached_row
    assert "Waiting for" not in reached_row and "Changed." not in reached_row
    assert "REACHED: Apple lists it." in plain
    assert "Daily at 09:00 ·" not in markup  # the brief's own zone needs no name
    assert "Daily at 09:00</p>" in markup or "Daily at 09:00<" in markup
    assert "Weekly on Monday at 08:30 Los Angeles time" in markup
    assert "Europe/Berlin" not in markup and "America/Los_Angeles" not in markup

def test_paused_mail_offers_resume_not_pause(monkeypatch):
    monkeypatch.setenv("WATCH_UNSUBSCRIBE_SECRET", "test-secret")
    item = {"kind": notification_outbox.KIND_WATCH_PAUSED, "resource_id": "w1", "uid": "u1"}
    payload = {"question": "Will it change?", "share_id": "A" * 16, "share_slug": "q", "visibility": "public"}
    message = notification_delivery._owner_message(item, payload, "o@example.test", ("", []))
    markup, plain = _parts(message)
    resume = re.search(r'href="([^"]*/watch/resume\?token=[^"]+)" class="cx-btn-label"', markup)
    assert resume, markup
    token = unescape(resume.group(1)).split("token=", 1)[1]
    assert watch_service.parse_resume_token(token) == "w1"
    body = markup.split("</head>", 1)[1]
    assert ">Resume watch</a>" in markup and "/watch/unsubscribe" not in body
    assert "Pause this watch" not in body and "unsubscribe" not in body.lower()
    assert "Unsubscribe" not in plain and "Resume this watch: " in plain
    # A mail client can still stop these mails (RFC 8058).
    assert message["List-Unsubscribe"].startswith("<https://")
    assert message["Subject"] == "Watch paused: Will it change?"

class TestTelegramActsInPlace:
    def setup_method(self):
        self.db = FakeDb()
        self.db.stores["shares"]["A" * 16] = share()
        self.db.stores["watches"]["w1"] = {"owner_uid": "u1", "share_id": "A" * 16, "status": "active"}
        self.db.stores[telegram_watch.CONNECTIONS_COLLECTION]["u1"] = {
            "uid": "u1", "chat_id": "123", "telegram_user_id": "123", "enabled": True,
        }
        self.db.stores[telegram_watch.CHATS_COLLECTION][telegram_watch._digest("123")] = {
            "uid": "u1", "chat_id": "123",
        }
        self.url_row = [{"text": "Open watch", "url": "https://www.consens.io/s/question-AAAA"}]
        self.message = {
            "message_id": 77, "chat": {"id": 123, "type": "private"},
            "text": "The answer moved\n\nWhat changed\nIt moved.",
            "entities": [{"type": "bold", "offset": 0, "length": 16}],
            "reply_markup": {"inline_keyboard": [
                self.url_row,
                [{"text": "Mute 24h", "callback_data": "wm:w1"}, {"text": "Pause", "callback_data": "wp:w1"}],
            ]},
        }

    def _tap(self, data, api):
        update = {"callback_query": {"id": "cb", "data": data, "from": {"id": 123},
                                     "message": deepcopy(self.message)}}
        with patch.object(telegram_watch.telegram_notifier, "call_bot_api", api), \
                patch.object(telegram_watch.telegram_notifier, "send_bot_message") as send:
            telegram_watch.handle_update(update, db=self.db)
        send.assert_not_called()  # never a new message
        return [(call.args[0], call.args[1]) for call in api.call_args_list]

    def test_pause_confirms_on_the_message_itself(self):
        calls = self._tap("wp:w1", Mock(return_value={"status": "sent"}))
        edit = dict(calls)["editMessageReplyMarkup"]
        assert edit["message_id"] == 77
        assert edit["reply_markup"]["inline_keyboard"] == [self.url_row, [
            {"text": "Confirm pause", "callback_data": "wpc:w1"},
            {"text": "Cancel", "callback_data": "wx:w1"},
        ]]
        assert self.db.stores["watches"]["w1"]["status"] == "active"

        calls = self._tap("wpc:w1", Mock(return_value={"status": "sent"}))
        assert self.db.stores["watches"]["w1"]["status"] == "paused"
        edit = dict(calls)["editMessageText"]
        assert edit["text"].endswith("\n\n" + telegram_watch.STATUS_PAUSED)
        assert {"type": "bold", "offset": 0, "length": 16} in edit["entities"]
        assert edit["reply_markup"]["inline_keyboard"] == [
            self.url_row, [{"text": "Resume watch", "callback_data": "wr:w1"}],
        ]
        assert dict(calls)["answerCallbackQuery"]["text"] == "Watch paused."

    def test_cancel_restores_the_buttons_and_resume_restarts(self):
        calls = self._tap("wx:w1", Mock(return_value={"status": "sent"}))
        assert dict(calls)["editMessageReplyMarkup"]["reply_markup"] == self.message["reply_markup"]
        self.db.stores["watches"]["w1"]["status"] = "paused"
        self.message["text"] += "\n\n" + telegram_watch.STATUS_PAUSED
        with patch.object(telegram_watch, "get_user_tier", return_value="pro"):
            calls = self._tap("wr:w1", Mock(return_value={"status": "sent"}))
        assert self.db.stores["watches"]["w1"]["status"] == "active"
        edit = dict(calls)["editMessageText"]
        assert edit["text"] == "The answer moved\n\nWhat changed\nIt moved.\n\n" + telegram_watch.STATUS_RESUMED

    def test_a_refused_text_edit_still_swaps_the_buttons(self):
        api = Mock(side_effect=lambda method, payload: (
            {"status": "failed_http", "http_status": 400} if method == "editMessageText" else {"status": "sent"}
        ))
        calls = self._tap("wpc:w1", api)
        assert [method for method, _ in calls] == [
            "answerCallbackQuery", "editMessageText", "editMessageReplyMarkup",
        ]

def test_telegram_speaks_like_the_app_and_links_to_the_watch():
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
    view = {"question": "Q?", "condition": "G", "share_id": "A" * 16, "share_slug": "q"}
    for kind in ("change", "every_run", "condition", "paused_error"):
        text = telegram_watch._notification_text(kind, view, {"delta": {"summary": "Moved."}})
        assert not emoji.search(text), kind
    private = telegram_watch._watch_keyboard("w1", {**view, "visibility": "private"}, "change")
    assert private["inline_keyboard"][0][0]["url"] == "https://www.consens.io/app?next=/s/" + "A" * 16
    paused = telegram_watch._watch_keyboard("w1", view, "paused_error")["inline_keyboard"]
    assert paused[0] == [{"text": "Resume watch", "callback_data": "wr:w1"}]
    reached = telegram_watch._watch_keyboard("w1", view, "condition")["inline_keyboard"]
    assert reached == [[{"text": "Open watch", "url": "https://www.consens.io/s/q-" + "A" * 16}]]
    with patch.object(telegram_watch.telegram_notifier, "send_bot_message") as send:
        telegram_watch.handle_update({"message": {"text": "/start", "chat": {"id": 1}}}, db=FakeDb())
    text = send.call_args.args[1]
    assert "Connect Telegram" in text and "Settings" not in text and not emoji.search(text)
    assert send.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["url"].endswith("/app/watches")
