"""Masking the keys the user gave the agent (agent_secrets.py): whole
values everywhere (scrub), and before a text is shortened also a key cut at
its edge (mask); a file that holds one is found by its bytes (holds)."""
import pytest

from app.services import agent_secrets

UID = "user-1"
KEY = "ghp_" + "A1b2C3d4E5f6G7h8" * 2
MASK = "[secret ~/.secrets/GITHUB_TOKEN, hidden from you]"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(agent_secrets, "_seen", {})
    agent_secrets.remember(UID, KEY, "GITHUB_TOKEN")


def test_whole_keys_are_masked_wherever_they_stand():
    assert agent_secrets.mask(UID, f"token={KEY}\nagain {KEY}") == f"token={MASK}\nagain {MASK}"
    assert agent_secrets.mask("someone-else", KEY) == KEY
    assert agent_secrets.mask(UID, "") == ""


def test_a_key_cut_at_an_edge_is_masked_from_four_characters_on():
    # The text starts inside a longer output: a key's end there.
    assert agent_secrets.mask(UID, KEY[9:] + " rest", cut_start=True) == MASK + " rest"
    assert agent_secrets.mask(UID, KEY[-4:] + " rest", cut_start=True) == MASK + " rest"
    # Three characters say nothing of a key (and match ordinary text too often).
    assert agent_secrets.mask(UID, KEY[-3:] + " rest", cut_start=True) == KEY[-3:] + " rest"
    # More is to come: a key's beginning at the end.
    assert agent_secrets.mask(UID, "token=" + KEY[:10], cut_end=True) == "token=" + MASK
    # An edge that was not cut stays as it is.
    assert agent_secrets.mask(UID, KEY[9:] + " rest") == KEY[9:] + " rest"
    assert agent_secrets.mask(UID, "token=" + KEY[:10]) == "token=" + KEY[:10]
    # The longest part that fits: a key with repeats in it.
    assert agent_secrets.mask(UID, KEY[20:] + "!", cut_start=True) == MASK + "!"


def test_a_file_that_holds_a_key_is_named_by_its_bytes():
    assert agent_secrets.holds(UID, f"GITHUB_TOKEN={KEY}\n".encode()) == "GITHUB_TOKEN"
    assert agent_secrets.holds(UID, KEY[:-1].encode()) is None
    assert agent_secrets.holds("someone-else", KEY.encode()) is None


def test_keys_the_server_reads_again_come_with_the_workbench_not_a_load_of_their_own():
    """open_chat reads them with the chat's folder and notes in one command
    (agent_workspace.CHAT_SCRIPT); the separate load had no caller left."""
    assert not hasattr(agent_secrets, "load") and not hasattr(agent_secrets, "LOAD_SCRIPT")
