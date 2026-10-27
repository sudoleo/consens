"""Which of the agent's calls act outside its workspace (since 2026-10-27).

In audit mode such a call runs only once the reviewers let it
(agent_audit.AnswerAudit.gate, docs/agent-work-log.md "Vor dem Aufruf"): a
reviewer's halt came only after the call before, because the app logs a step
and runs it at once while a round takes seconds. The app decides by a fixed
list, never a model: a shell command (vm_exec, vm_start_process) that talks
to the network, and the browser actions that send what a page holds (a
click, Enter, an upload). Typing alone sends nothing; the click or Enter that
follows is checked with it in view.

The list catches the usual ways out, not every one: a script the agent wrote
before and only runs now does not show what it does. The reviewers' live
rounds after every step stay the second net.
"""
from __future__ import annotations

import json
import re

# Tools whose ``command`` runs in the agent's VM.
COMMAND_TOOLS = frozenset({"vm_exec", "vm_start_process"})

# (reason, pattern) for a command, first match wins. A program counts where
# a command starts (the line's start, after ; & | ( ` $( or a quote that
# opens "bash -c"), behind sudo/env/nohup/time/timeout/xargs and variable
# assignments, also by its path ("/usr/bin/curl"); "grep -r curl src/" only
# names it.
_START = (r"(?:^|[;&|(`\n'\"]|\$\()\s*(?:\w+=\S*\s+)*"
          r"(?:(?:sudo|env|nohup|time|exec|nice|xargs|timeout\s+\S+)\s+(?:-\S+\s+)*)*(?:[\w.~-]*/)*")
_END = r"(?=$|[\s;&|)`'\"])"
OUTWARD = (
    ("browser", re.compile(_START + r"browser\s+(?:click|upload|key\s+(?:enter|return)\b|type\b[^\n]*--enter)",
                           re.IGNORECASE)),
    ("network", re.compile(_START + r"(?:curl|wget|ssh|scp|sftp|ftp|telnet|nc|ncat|netcat|socat|sendmail|mutt|"
                                    r"swaks|aria2c|lftp|smbclient)" + _END, re.IGNORECASE)),
    ("network", re.compile(_START + r"rsync\b[^\n]*(?:\S+@\S+:|\S+::|rsync://)", re.IGNORECASE)),
    ("publish", re.compile(r"\bgit\s+push\b|\b(?:npm|yarn|pnpm)\s+publish\b|\btwine\s+upload\b|"
                           r"\bdocker\s+push\b|\bgh\s+\S+|\bcargo\s+publish\b|\bgem\s+push\b", re.IGNORECASE)),
    ("network", re.compile(r"/dev/(?:tcp|udp)/", re.IGNORECASE)),
)
# Code run inline (python -c, node -e, a here-document) that opens a
# connection. Only there: "pip install requests" installs, it sends nothing.
INLINE = re.compile(r"\b(?:python3?|node|perl|ruby|php)\s+-[ce]\b|<<-?\s*['\"]?\w+", re.IGNORECASE)
INLINE_NETWORK = re.compile(r"\b(?:requests|httpx|aiohttp|urllib3?|http\.client|smtplib|ftplib|socket|paramiko)\b|"
                            r"\bfetch\s*\(|\baxios\b|\bXMLHttpRequest\b|\bnet\.connect\b|\bnew\s+WebSocket\b|"
                            r"\bNet::HTTP\b|\bLWP\b", re.IGNORECASE)


def command_of(call):
    """The shell command of a vm_exec / vm_start_process call, or None."""
    function = (call or {}).get("function") or {}
    if function.get("name") not in COMMAND_TOOLS:
        return None
    arguments = function.get("arguments")
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except ValueError:
        return None
    command = args.get("command") if isinstance(args, dict) else None
    return command if isinstance(command, str) and command.strip() else None


def outward(call):
    """Why ``call`` acts outside the workspace ("browser", "network",
    "publish"), or None for a call that stays inside it."""
    command = command_of(call)
    if command is None:
        return None
    for reason, pattern in OUTWARD:
        if pattern.search(command):
            return reason
    if INLINE.search(command) and INLINE_NETWORK.search(command):
        return "network"
    return None
