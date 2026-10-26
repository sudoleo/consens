"""Compaction of a long VM run's own conversation (DelegationLoop._compact).

A turn that works in its VM may run for hours and hundreds of steps
(AgentPolicy.vm_turn_*). Every command's output stays in the conversation, so
each step would send all earlier output again: the account's ledger counts it
whole (cached or not) and the model's window fills. Once the run's own part of
the conversation (from this message's question on) passes COMPACT_ABOVE_CHARS,
the older results of COMPACTABLE tools become a short stub: what ran or was
read, how it ended, the last lines of its output. The newest results stay
whole until they add up to KEEP_RECENT_CHARS, the newest batch always.

Prompt cache: each step's request continues the previous one's prefix, and
changing an older message rewrites the cached prefix from there on. So a cut
happens only above the mark and only when it saves at least MIN_GAIN_CHARS;
afterwards the prefix stays stable until the run has grown back to the mark.
Only tool results change: assistant messages (their reasoning signatures and
tool arguments) go back to the provider exactly as it wrote them, and the
number and order of messages stay the same.

The reviewers keep the whole results: the work log recorded them when they
returned (agent_work_log.py); the cut itself is an ``app`` entry
``compacted`` there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json

COMPACT_ABOVE_CHARS = 150_000
KEEP_RECENT_CHARS = 40_000
MIN_GAIN_CHARS = 30_000
# A result this short stays as it is: its stub would save next to nothing.
MIN_RESULT_CHARS = 2_000
TAIL_CHARS = 600
COMPACTABLE = frozenset({"vm_exec", "vm_read_file"})
OUTPUT_CLEARED = ("Earlier output cleared to save context; only its end is kept. Run the command again if you "
                  "need all of it.")
CONTENT_CLEARED = "File content cleared to save context. Read the file again if you need it."


@dataclass
class Cut:
    """What a compaction changes: ``replacements`` as ``(index, message)``."""
    replacements: list = field(default_factory=list)
    before: int = 0
    after: int = 0

    def summary(self):
        return {"results": len(self.replacements), "chars_before": self.before, "chars_after": self.after,
                "tool_call_ids": [message["tool_call_id"] for _, message in self.replacements]}


def _size(message):
    return len(json.dumps(message, ensure_ascii=False))


def own_chars(messages, start):
    """Characters of the run's own messages, as they go to the provider."""
    return sum(_size(message) for message in messages[start:])


def _tail(text):
    """The end of ``text``, from a line start where one is near."""
    text = text or ""
    if len(text) <= TAIL_CHARS:
        return text
    end = text[-TAIL_CHARS:]
    newline = end.find("\n")
    return end[newline + 1:] if 0 <= newline < TAIL_CHARS // 2 else end


def stub(name, content):
    """The compacted form of a tool result (its JSON text)."""
    try:
        result = json.loads(content)
    except (TypeError, ValueError):
        result = None
    if not isinstance(result, dict):
        return json.dumps({"compacted": OUTPUT_CLEARED, "end": _tail(str(content))}, ensure_ascii=False)
    # The first VM result of a message names the attachments (VMSession.announce).
    inputs = {key: result[key] for key in ("input_dir", "inputs", "inputs_unavailable") if key in result}
    if name == "vm_read_file":
        kept = {key: result[key] for key in ("path", "first_line", "last_line", "total_lines", "binary", "bytes")
                if key in result}
        return json.dumps({**kept, **inputs, "compacted": CONTENT_CLEARED}, ensure_ascii=False)
    kept = {key: result[key] for key in ("exit_code", "timed_out", "duration_ms", "cwd", "error", "note")
            if key in result}
    kept.update(inputs)
    for stream in ("stdout", "stderr"):
        end = _tail(result.get(stream))
        if end:
            kept[f"{stream}_end"] = end
    return json.dumps({**kept, "compacted": OUTPUT_CLEARED}, ensure_ascii=False)


def compact(messages, start):
    """The cut that brings ``messages[start:]`` back down, or None.

    ``messages`` is not changed; the caller replaces the messages the cut
    names. None up to COMPACT_ABOVE_CHARS, and when the cut would save less
    than MIN_GAIN_CHARS (it would rewrite the cached prefix for little)."""
    before = own_chars(messages, start)
    if before <= COMPACT_ABOVE_CHARS:
        return None
    names, last_assistant = {}, None
    for index in range(start, len(messages)):
        message = messages[index]
        if message.get("role") == "assistant":
            last_assistant = index
            for call in message.get("tool_calls") or []:
                names[call.get("id")] = (call.get("function") or {}).get("name")
    candidates = []
    for index in range(start, last_assistant if last_assistant is not None else start):
        message = messages[index]
        name = names.get(message.get("tool_call_id"))
        content = message.get("content")
        if (message.get("role") != "tool" or name not in COMPACTABLE or not isinstance(content, str)
                or len(content) < MIN_RESULT_CHARS or '"compacted"' in content):
            continue
        candidates.append((index, name, content))
    # The newest results stay whole until they reach ``keep``; everything
    # older is cut.
    kept = 0
    while candidates and kept + len(candidates[-1][2]) <= KEEP_RECENT_CHARS:
        kept += len(candidates.pop()[2])
    cut = Cut(before=before, after=before)
    for index, name, content in candidates:
        message = {**messages[index], "content": stub(name, content)}
        cut.after -= _size(messages[index]) - _size(message)
        cut.replacements.append((index, message))
    if before - cut.after < MIN_GAIN_CHARS:
        return None
    return cut
