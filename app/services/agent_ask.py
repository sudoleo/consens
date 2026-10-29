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
- without it: the user allows or declines a step before the agent takes it,
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

from pydantic import BaseModel, ConfigDict, Field

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


def requested(call):
    """``(request, browser)`` of an ask_user call, or None when its arguments
    are not valid (the tool then says why)."""
    function = (call or {}).get("function") or {}
    if function.get("name") != TOOL:
        return None
    arguments = function.get("arguments")
    try:
        args = AskUserArgs.model_validate(json.loads(arguments) if isinstance(arguments, str) else arguments)
    except Exception:
        return None
    return " ".join(args.request.split()), args.browser


def hold(kind, request=""):
    """A hold of the user's (DelegationLoop.request_hold): ``kind`` is
    "browser", "confirm" or "takeover". The fields a reviewer's halt has stay
    empty, so the card and the activity tell the two apart by ``ask``."""
    return {"reviewer": "", "provider": "", "kind": "ask", "reason": "", "entry": None, "ask": kind,
            "request": request}


def answer(kind, decision):
    return dict(ANSWERS.get((kind, decision)) or ANSWERS[(kind, "continue")])


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
            "work goes on once they hand it back. Without it, they allow or decline a step before you take it, "
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
        fields = {"request": " ".join(str(args.request).split())[:REQUEST_CHARS], "ask": "browser" if args.browser
                  else "confirm"}
        if isinstance(result, dict) and result.get("status"):
            fields["ask_status"] = result["status"]
        return fields
