"""ask_user: the agent hands a step to the user and waits on a card above the field
(AgentLoop._ask_wait).

``browser``: the user takes over the browser for what is theirs to do (a sign-in, a payment, a human
check); handing it back continues the work, and the agent hears only that, never what they did.
``secret``: the user pastes a key that the server writes into the workspace (agent_secrets.py), never
into the chat or a model's context. ``choices``: two to four answers as buttons, since a confirm
card cannot say which of two ways to go. None of these: the user allows or declines a step taken in
their name (sending, posting, booking, deleting): the acting model knows what such a step does, and
the user decides rather than a reviewer on every click.

A user who takes over unasked makes the next workspace call wait the same way (card ``takeover``). A
message on the card is the answer, Stop stops; without an answer in HOLD_TIMEOUT_SECONDS the agent
hears so and finishes its answer."""
from __future__ import annotations

import json
import unicodedata
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services import agent_secrets
from app.services.agent_tools import ReadOnlyTool

TOOL = "ask_user"
REQUEST_CHARS = 600
MIN_CHOICES = 2
MAX_CHOICES = 4
CHOICE_CHARS = 80
# How often a waiting run looks whether the user handed the browser back.
HANDBACK_POLL_SECONDS = 3

# What the agent reads, by the card's kind and the user's answer.
ANSWERS = {
    ("browser", "handed_back"): {"status": "handed_back",
                                 "note": "The user handed the browser back. Read the page to see where it stands."},
    ("browser", "continue"): {"status": "continued", "note": "The user let you go on without taking over the browser."},
    ("confirm", "continue"): {"status": "allowed", "note": "The user allowed it."},
    ("confirm", "deny"): {"status": "declined", "note": "The user did not allow it. Do not take this step: go on "
                                                        "without it, or say in your answer what is left."},
    ("browser", "steer"): {"status": "message", "note": "The user answered with a message instead: it follows."},
    ("confirm", "steer"): {"status": "message", "note": "The user answered with a message instead: it follows."},
    ("browser", "timeout"): {"status": "no_answer", "note": "The user did not take this up within 30 minutes. "
                                                            "Finish with what you have and say what waits for them."},
    ("confirm", "timeout"): {"status": "no_answer", "note": "The user did not answer within 30 minutes. Do not "
                                                            "take the step: finish with what you have and say what "
                                                            "waits for them."},
    ("secret", "continue"): {"status": "saved", "note": "The user saved it in {path}, which only your user reads. "
                                                        "Read it in the same command line that needs it (each "
                                                        "command is a shell of its own), such as {name}=\"$(cat "
                                                        "{path})\" npm start; never print it, copy it into your "
                                                        "project or put it in your answer. Where an output shows "
                                                        "it, you read a mask that says it is hidden from you: the "
                                                        "file is fine, never write the mask into a file."},
    ("secret", "deny"): {"status": "declined", "note": "The user did not give it. Go on without it, or say in your "
                                                       "answer what it is needed for."},
    ("secret", "steer"): {"status": "message", "note": "The user answered with a message instead: it follows."},
    ("secret", "timeout"): {"status": "no_answer", "note": "The user did not answer within 30 minutes. Finish with "
                                                           "what you have and say what waits for them."},
    ("choice", "choose"): {"status": "chosen", "note": "The user chose: {choice}"},
    ("choice", "steer"): {"status": "message", "note": "The user answered with a message instead: it follows."},
    ("choice", "timeout"): {"status": "no_answer", "note": "The user did not answer within 30 minutes. Finish with "
                                                           "what you have and say what waits for them."},
}
# A workspace call that waited while the user had the browser and was never handed it back.
TAKEOVER_TIMEOUT = ("The user took over the workspace's browser and did not hand it back within 30 minutes, so "
                    "this call did not run. Finish with what you have and say what waits for them.")


class AskUserArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request: str = Field(min_length=3, max_length=REQUEST_CHARS, description="What you ask of the user, one or two "
                         "sentences in the language of their message; they read it on a card.")
    browser: bool = Field(default=False, description="True when the user is to act in the browser: they take it "
                          "over and hand it back. False when they allow or decline the step you describe.")
    secret: str = Field(default="", max_length=64, description="The name of a key or token you need from the user, "
                        "such as OPENAI_API_KEY (capitals, digits, _): they paste it into a field on the card and it "
                        "is saved in your workspace, never in the chat. Not with browser.")
    choices: list[Annotated[str, Field(min_length=1, max_length=CHOICE_CHARS)]] = Field(
        default_factory=list, max_length=MAX_CHOICES, description="Two to four short answers when you ask the user "
        "which way to go, such as a game against a person or against a bot: each is a button on the card, and their "
        "pick comes back as choice. Not with browser or secret.")

    @model_validator(mode="after")
    def _secret(self):
        if self.secret and not agent_secrets.NAME.fullmatch(self.secret):
            raise ValueError("secret is a name in capitals, digits and _, such as OPENAI_API_KEY.")
        if self.secret and self.browser:
            raise ValueError("Ask for a secret or for the browser, not both at once.")
        if self.choices:
            if self.browser or self.secret:
                raise ValueError("choices go without browser and secret.")
            # Without invisible characters: two answers that read the same would be two buttons.
            self.choices = [" ".join("".join(char for char in choice if unicodedata.category(char) != "Cf").split())
                            for choice in self.choices]
            if (len(self.choices) < MIN_CHOICES or not all(any(char.isalnum() for char in choice)
                                                           for choice in self.choices)
                    or len({choice.casefold() for choice in self.choices}) < len(self.choices)):
                raise ValueError(f"choices are {MIN_CHOICES} to {MAX_CHOICES} different answers, none empty.")
        return self


def requested(call):
    """``(request, browser, secret, choices)`` of an ask_user call, or None when its arguments are
    not valid."""
    function = (call or {}).get("function") or {}
    if function.get("name") != TOOL:
        return None
    arguments = function.get("arguments")
    try:
        args = AskUserArgs.model_validate(json.loads(arguments) if isinstance(arguments, str) else arguments)
    except Exception:
        return None
    return " ".join(args.request.split()), args.browser, args.secret, list(args.choices)


def hold(kind, request="", secret="", choices=()):
    """A hold of the user's: ``kind`` "browser", "confirm", "secret", "choice" or "takeover". The
    fields a reviewer's halt has stay empty, so card and activity tell the two apart by ``ask``."""
    return {"reviewer": "", "provider": "", "kind": "ask", "reason": "", "entry": None, "ask": kind,
            "request": request, **({"secret": secret} if secret else {}),
            **({"choices": list(choices)} if choices else {})}


def chosen(hold, choice):
    """The answer picked by its index, or None when ``choice`` names none."""
    choices = (hold or {}).get("choices") or []
    if (hold or {}).get("ask") != "choice" or type(choice) is not int or not 0 <= choice < len(choices):
        return None
    return str(choices[choice])


def answer(kind, decision, secret="", picked=None):
    """What the tool returns for the user's ``decision`` on a card of ``kind``."""
    said = dict(ANSWERS.get((kind, decision)) or ANSWERS.get((kind, "continue")) or ANSWERS[(kind, "timeout")])
    if kind == "secret" and said["status"] == "saved":
        said["path"] = agent_secrets.path(secret)
        said["note"] = said["note"].format(path=said["path"], name=secret)
    if kind == "choice" and said["status"] == "chosen":
        said["choice"] = str(picked or "")
        said["note"] = said["note"].format(choice=said["choice"])
    return said


class AskTools:
    """ask_user of one message. The loop runs it once the user answered (the answer in
    ``loop.ask_answer``)."""

    def __init__(self, vm_tools):
        self.vm = vm_tools

    def tools(self):
        return [ReadOnlyTool(
            TOOL, "Pause and hand a step to the user. With browser, they take over the workspace's browser for "
            "what is theirs to do there, such as a sign-in, a password, a payment or a check for a human, and your "
            "work goes on once they hand it back. With secret, they give you a key or token your work needs, saved "
            "in your workspace for your commands. With choices, they pick one of the answers you name. Without any "
            "of these, they allow or decline a step before you take it, such as sending, posting, booking or "
            "deleting something in their name.",
            AskUserArgs, self.ask, activity=self._activity)]

    def ask(self, args, *, cancellation):
        loop = self.vm.loop
        result, loop.ask_answer = getattr(loop, "ask_answer", None), None
        if not result:
            raise ValueError("The user could not be asked right now. Go on without it, or say in your answer what "
                             "you need from them.")
        browser = getattr(self.vm, "browser_tools", None)
        if result.get("status") == "handed_back" and browser is not None:
            # The browser as the user left it, in this result.
            try:
                seen = browser.look(cancellation)
            except ValueError:
                return result
            result["page"] = str(seen.get("page") or "")
            result["note"] = ("The user handed the browser back. The page as they left it is below"
                              + ("; its screenshot follows as an image after these results." if "screenshot follows"
                                 in str(seen.get("note") or "") else "."))
        return result

    def _activity(self, args, result):
        fields = {"request": " ".join(str(args.request).split())[:REQUEST_CHARS],
                  "ask": "browser" if args.browser else "secret" if args.secret else "choice" if args.choices
                  else "confirm"}
        if args.secret:
            fields["secret"] = args.secret
        if args.choices:
            fields["choices"] = list(args.choices)
        if isinstance(result, dict) and result.get("status"):
            fields["ask_status"] = result["status"]
        if isinstance(result, dict) and isinstance(result.get("choice"), str):
            fields["choice"] = result["choice"]
        return fields
