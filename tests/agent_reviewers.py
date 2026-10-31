"""Test-only reviewers that never start (agent_audit.AnswerAudit).

Since 2026-10-31 every chat run of the agent has reviewers: the user's
chosen models follow its work log and review its fixed answer. There is no
production switch without them, and none for tests either. A test about
something else (the workspace, quotas, memory, a tool) whose completion
factory scripts only the agent's steps would otherwise have the reviewers'
rounds take that script's replies, at moments the test does not control.

``InertAnswerAudit`` is the real AnswerAudit whose reviewers never start, the
state "no reviewer could answer": no session follows the log, no gate opens
before an outward call, memory locks once outside content is in view
(DelegationLoop.memory_locked), no time is reserved for final rounds, and the
review of the fixed answer ends "failed" with ``audit_unavailable`` and no
marks, as AnswerAudit.run ends it when its reviewers never started. Tests
about the review itself script the reviewers instead (test_agent_audit.Audit).

``without_reviewers(loop)`` gives a loop the test built such an auditor; the
``inert_reviewers`` fixture does it for every loop built while it is active
(one the route builds, routers/agent.py).
"""
import pytest

from app.services import agent_audit


class InertAnswerAudit(agent_audit.AnswerAudit):
    def follow(self, work_log):
        """No reviewer starts: nothing follows the log."""


def without_reviewers(loop):
    """``loop`` with InertAnswerAudit as its auditor; returns ``loop``."""
    loop.comparison.auditor = InertAnswerAudit(loop.comparison)
    return loop


@pytest.fixture
def inert_reviewers(monkeypatch):
    monkeypatch.setattr(agent_audit, "AnswerAudit", InertAnswerAudit)
