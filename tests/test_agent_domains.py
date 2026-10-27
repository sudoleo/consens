"""The workbench's network per chat (agent_domains.py, since 2026-10-27): the
package registries by default, another domain only after the user allowed
it for the chat, in the policy while the chat's message has the workspace.
The loop's card is in test_agent_gate.py; the VM here is FakeVM.
"""
import json

import pytest

from app.services import agent_domains, agent_vm
from app.services.agent_domains import DomainTools, RequestDomainArgs, normalize
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import NAME, Agent, _admin_allowance, fake_vm, vm_loop  # noqa: F401  (fixtures)


@pytest.mark.parametrize("domain,error", [
    ("*.example.com", "wildcard"), ("https://api.example.com", "scheme"), ("api.example.com:8443", "port"),
    ("api.example.com/v1", "path"), ("1.2.3.4", "Addresses"), ("localhost", "no valid"), ("github.com", "github_import"),
    ("raw.githubusercontent.com", "github_import"), ("api.github.com", "github_import"),
    ("my-app.internal", "cannot be allowed"), ("x.flycast", "cannot be allowed"), ("api.sprites.dev", "cannot be"),
    ("consens-w-a.sprites.app", "cannot be allowed"), ("-bad.example.com", "no valid")])
def test_only_one_plain_host_name_can_be_asked_for(domain, error):
    with pytest.raises(ValueError, match=error):
        normalize(domain)


def test_a_host_name_is_taken_as_the_policy_reads_it():
    assert normalize(" API.Example.COM. ") == "api.example.com"
    assert agent_domains.open_already("pypi.org") and agent_domains.open_already("de.archive.ubuntu.com")
    assert not agent_domains.open_already("example.com")
    assert agent_domains.rules() == agent_vm.WORKBENCH_RULES
    assert agent_domains.rules(["api.example.com", "pypi.org"]) == [
        *agent_vm.WORKBENCH_RULES, {"domain": "api.example.com", "action": "allow"}]


def test_what_the_user_allowed_stays_with_the_chat(store, fake_vm):
    loop = vm_loop(store, Agent())
    assert agent_domains.grant(store, UID, loop.chat_id, "api.example.com", "t1") == ["api.example.com"]
    assert agent_domains.grant(store, UID, loop.chat_id, "api.example.com", "t2") == ["api.example.com"]
    chat = store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert agent_domains.granted(chat) == ["api.example.com"] and chat["agent_domains"][0]["turn_id"] == "t1"
    for number in range(agent_domains.MAX_DOMAINS - 1):
        agent_domains.grant(store, UID, loop.chat_id, f"api{number}.example.com", "t3")
    with pytest.raises(ValueError, match="most it takes"):
        agent_domains.grant(store, UID, loop.chat_id, "one-more.example.com", "t4")
    # Nothing but host names from the record reaches the policy.
    assert agent_domains.granted({"agent_domains": [{"domain": "*"}, "x", {"domain": "ok.example.com"}]}) == [
        "ok.example.com"]


def test_the_tool_runs_only_for_a_domain_the_user_allowed_and_opens_it_at_once(store, fake_vm):
    loop = vm_loop(store, Agent())
    tools = DomainTools(loop.vm_tools)
    args = RequestDomainArgs(domain="api.example.com", reason="The script calls the API.")
    with pytest.raises(ValueError, match="did not allow"):
        tools.request(args, cancellation=ProviderCancellation())
    session = loop.vm_tools.session
    session.ready(ProviderCancellation())
    assert fake_vm.vms[NAME]["policy"] == agent_vm.WORKBENCH_RULES
    loop.allowed_domains.add("api.example.com")
    result = tools.request(args, cancellation=ProviderCancellation())
    assert result["status"] == "allowed" and result["domain"] == "api.example.com"
    # Live: the policy holds it now, and the chat keeps it.
    assert fake_vm.vms[NAME]["policy"] == agent_domains.rules(["api.example.com"])
    assert agent_domains.granted(store._chat_ref(UID, loop.chat_id).get().to_dict()) == ["api.example.com"]
    # A registry needs nothing.
    assert tools.request(RequestDomainArgs(domain="pypi.org", reason="pip"),
                         cancellation=ProviderCancellation())["status"] == "open"
    # The message ends: the policy goes back to the registries.
    session.close()
    assert fake_vm.vms[NAME]["policy"] == agent_vm.WORKBENCH_RULES


def test_the_chats_domains_come_with_its_next_message_and_leave_with_it(store, fake_vm):
    first = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    agent_domains.grant(store, UID, first.chat_id, "api.example.com", "t0")
    policies = []
    original = type(fake_vm.backend()).set_policy

    def recording(self, name, rules):
        policies.append(list(rules))
        original(self, name, rules)
    type(fake_vm.backend()).set_policy = recording
    try:
        list(first.run())
    finally:
        type(fake_vm.backend()).set_policy = original
    # In the policy from the start of the message (ensure), back to the registries at its end.
    ensured = next(index for index, call in enumerate(fake_vm.calls) if call == ("ensure", NAME))
    assert fake_vm.calls[ensured] == ("ensure", NAME)
    assert policies == [agent_vm.WORKBENCH_RULES]
    assert fake_vm.vms[NAME]["policy"] == agent_vm.WORKBENCH_RULES
    # Another chat of the account never gets them.
    other = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]), request_id="other")
    claimed = []
    from app.services import agent_workspace
    real_claim = agent_workspace.claim

    def claim(*args, **kwargs):
        claimed.append(real_claim(*args, **kwargs))
        return claimed[-1]
    agent_workspace.claim = claim
    try:
        list(other.run())
    finally:
        agent_workspace.claim = real_claim
    assert claimed[0].domains == ()


def test_a_request_names_its_domain_and_reason():
    call = {"function": {"name": "request_domain",
                         "arguments": json.dumps({"domain": "API.example.com", "reason": "  The   API. "})}}
    assert agent_domains.requested(call) == ("api.example.com", "The API.")
    assert agent_domains.requested({"function": {"name": "request_domain", "arguments": "{}"}}) is None
    assert agent_domains.requested({"function": {"name": "request_domain",
                                                 "arguments": json.dumps({"domain": "github.com",
                                                                          "reason": "clone"})}}) is None
    assert agent_domains.requested({"function": {"name": "browser", "arguments": "{}"}}) is None
