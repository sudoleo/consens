"""The agent looks at pictures in its VM (vm_view_image): a chart it plotted
or a screenshot follows the batch's results as a user message with the image,
the format attached images use, only for a chat model that takes images.
The VM is FakeVM (test_agent_vm.py); no provider is called.
"""
import base64
import json

import pytest

from app.services import agent_compaction, agent_vm, agent_vm_tools
from app.services.agent_compaction import PICTURE_GONE, older_pictures, own_chars
from app.services.agent_vm_tools import PICTURE_INTRO, picture_message
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_long_runs import LongAgent
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import _admin_allowance, fake_vm, results, vm_loop  # noqa: F401  (fixtures)

PNG = b"\x89PNG\r\n\x1a\n" + b"chart" * 20


@pytest.fixture
def sees(monkeypatch):
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)


def put(fake_vm, loop, path, data):
    loop.vm_tools.session.ready(ProviderCancellation())
    fake_vm.vms[agent_vm.workspace_name(UID)]["files"][path] = data


def test_the_agent_sees_its_chart_after_the_results(store, fake_vm, sees):
    script = LongAgent([[("vm_view_image", {"path": "chart.png"}), ("vm_exec", {"command": "ls"})]])
    loop = vm_loop(store, script)
    put(fake_vm, loop, f"{agent_vm.chat_dir(loop.chat_id)}/chart.png", PNG)
    list(loop.run())
    assert "vm_view_image" in script.offered[0]
    viewed = results(loop)[0]
    chart = f"{agent_vm.chat_dir(loop.chat_id)}/chart.png"
    assert viewed == {"path": chart, "mime": "image/png", "bytes": len(PNG), "chat_folder": agent_vm.chat_dir(loop.chat_id),
                      "note": "The picture follows as an image after these results."}
    # The next step: both results first (every call answered), then the picture.
    after = script.seen[1]
    assert [m["role"] for m in after[-3:]] == ["tool", "tool", "user"]
    text, image = after[-1]["content"]
    assert text == {"type": "text", "text": PICTURE_INTRO.format(path=chart)}
    assert image == {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()}}
    # What the agent saw is outside content: memory locks; the reviewers see it is a VM picture.
    assert loop.memory_locked is True
    entry = next(e for e, t in loop.work_log.entries_after(0) if e["kind"] == "context" and t.startswith("[consens.io: the picture"))
    assert entry["data"] == "vm"


def test_only_pictures_and_only_for_a_model_that_takes_them(store, fake_vm, sees, monkeypatch):
    loop = vm_loop(store, LongAgent([[("vm_view_image", {"path": "notes.txt"})],
                                     [("vm_view_image", {"path": "big.png"})]]))
    put(fake_vm, loop, f"{agent_vm.chat_dir(loop.chat_id)}/notes.txt", b"just text")
    put(fake_vm, loop, f"{agent_vm.chat_dir(loop.chat_id)}/big.png", b"\x89PNG\r\n\x1a\n" + b"0" * agent_vm_tools.PICTURE_BYTES)
    list(loop.run())
    text, big = results(loop)
    assert "no PNG, JPEG, WebP or GIF" in text["error"] and "larger than 5 MB" in big["error"]
    assert loop.vm_tools.take_pictures() == []
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: False)
    script = LongAgent()
    list(vm_loop(store, script, request_id="two").run())
    assert "vm_view_image" not in script.offered[0]


def test_only_the_newest_pictures_stay_in_view_and_count_as_little():
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    for n in range(agent_compaction.PICTURES_KEPT + 2):
        messages.append(picture_message(f"/home/sprite/p{n}.png", "image/png", PNG * 1000))
    gone = older_pictures(messages, 2)
    assert [index for index, _ in gone] == [2, 3]
    assert gone[0][1]["content"] == [messages[2]["content"][0], {"type": "text", "text": PICTURE_GONE}]
    # A picture weighs PICTURE_CHARS towards compaction, not its base64 length.
    assert own_chars(messages[2:3], 0) < agent_compaction.PICTURE_CHARS + 500
    assert len(json.dumps(messages[2])) > 100_000
