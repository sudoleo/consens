"""ask_user: the agent hands a step to the user and waits (since 2026-10-29).

Working together in the workspace's browser had no "your turn". A sign-in
was the user's to do, yet the agent could only call the browser again (each
call waited up to 120 s while the user had it, VMSession.wait_for_user) or
end its answer, and the user did not see that they still held the browser
(Max, 2026-10-29: he waited for the agent while it waited for him). Now the
agent asks, and the run pauses on a card above the field
(DelegationLoop._ask_wait, a hold with ``ask``):

- ``browser``: the user takes over the browser for what is theirs to do
  there (a sign-in, a password, a payment, a check for a human, a last click
  the agent leaves to them). Handing it back is the trigger: once they had it
  and gave it back (agent_workspace.user_has_browser), the work goes on. The
  agent hears only that, never what the user did there, and reads the page
  again itself.
- ``secret`` (a name such as OPENAI_API_KEY): the user pastes a key or a
  token into a field on the card, and the server writes it to the workbench
  (agent_secrets.py, POST .../secret), never into the chat, the record or a
  model's context; the agent hears where it lies.
- neither: the user allows or declines a step before the agent takes it,
  such as sending, posting, booking or deleting in their name. This took the
  place of the reviewers' gate on every browser click (agent_gate.py): the
  acting model knows what a step does in the user's name, and the user
  decides, not a cheaper model on every click (Max, 2026-10-29).

The user can also take over without being asked: the agent's next call into
the workspace then waits the same way (DelegationLoop._takeover_wait, card
``takeover``) instead of failing after 120 s. A message written on the card
is the user's answer, Stop stops. Without an answer in HOLD_TIMEOUT_SECONDS
the agent hears so and finishes its answer; the response does not stop as
it does after a reviewer's halt.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services import agent_secrets
from app.services.agent_tools import ReadOnlyTool

TOOL = "ask_user"
REQUEST_CHARS = 600
# How often a waiting run looks whether the user handed the browser back
# (the account's record, agent_workspace.control_state): the agent goes on
# within about a second (2 s until the first games were played, 2026-10-29).
HANDBACK_POLL_SECONDS = 1

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
}
# A call into the workspace that waited while the user had the browser and
# was never handed it back.
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

    @model_validator(mode="after")
    def _secret(self):
        if self.secret and not agent_secrets.NAME.fullmatch(self.secret):
            raise ValueError("secret is a name in capitals, digits and _, such as OPENAI_API_KEY.")
        if self.secret and self.browser:
            raise ValueError("Ask for a secret or for the browser, not both at once.")
        return self


def requested(call):
    """``(request, browser, secret)`` of an ask_user call, or None when its
    arguments are not valid (the tool then says why)."""
    function = (call or {}).get("function") or {}
    if function.get("name") != TOOL:
        return None
    arguments = function.get("arguments")
    try:
        args = AskUserArgs.model_validate(json.loads(arguments) if isinstance(arguments, str) else arguments)
    except Exception:
        return None
    return " ".join(args.request.split()), args.browser, args.secret


def hold(kind, request="", secret=""):
    """A hold of the user's (DelegationLoop.request_hold): ``kind`` is
    "browser", "confirm", "secret" (with the key's name) or "takeover". The
    fields a reviewer's halt has stay empty, so the card and the activity
    tell the two apart by ``ask``."""
    return {"reviewer": "", "provider": "", "kind": "ask", "reason": "", "entry": None, "ask": kind,
            "request": request, **({"secret": secret} if secret else {})}


def answer(kind, decision, secret=""):
    said = dict(ANSWERS.get((kind, decision)) or ANSWERS[(kind, "continue")])
    if kind == "secret" and said["status"] == "saved":
        said["path"] = agent_secrets.path(secret)
        said["note"] = said["note"].format(path=said["path"], name=secret)
    return said


class AskTools:
    """ask_user of one message, next to the browser (VMTools). The loop runs
    it once the user answered on the card (DelegationLoop._ask_wait puts the
    answer in ``loop.ask_answer``)."""

    def __init__(self, vm_tools):
        self.vm = vm_tools

    def tools(self):
        return [ReadOnlyTool(
            TOOL, "Pause and hand a step to the user. With browser, they take over the workspace's browser for "
            "what is theirs to do there, such as a sign-in, a password, a payment or a check for a human, and your "
            "work goes on once they hand it back. With secret, they give you a key or token your work needs, saved "
            "in your workspace for your commands. Without either, they allow or decline a step before you take it, "
            "such as sending, posting, booking or deleting something in their name.",
            AskUserArgs, self.ask, activity=self._activity)]

    def ask(self, args, *, cancellation):
        loop = self.vm.loop
        result, loop.ask_answer = getattr(loop, "ask_answer", None), None
        if not result:
            raise ValueError("The user could not be asked right now. Go on without it, or say in your answer what "
                             "you need from them.")
        browser = getattr(self.vm, "browser_tools", None)
        if result.get("status") == "handed_back" and browser is not None:
            # The browser as the user left it, in this result (agent_browser.look).
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
                  "ask": "browser" if args.browser else "secret" if args.secret else "confirm"}
        if args.secret:
            fields["secret"] = args.secret
        if isinstance(result, dict) and result.get("status"):
            fields["ask_status"] = result["status"]
        return fields
