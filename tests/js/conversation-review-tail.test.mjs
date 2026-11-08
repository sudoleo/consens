/**
 * A reopened Agent chat whose previous answer stands while its reviewers
 * still work (agent_runs.hand_over) and whose next message already runs:
 * the server sends the answered turn in its place (routers/bookmarks.py
 * _transcript_turn, status "pending" with agent_answer_fixed) and names the
 * next one as running. The browser keeps that turn, so the chat neither
 * loses the message nor continues from the answer before it.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

function conversationHarness() {
  const source = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
  const start = source.indexOf("function normalizeConversationTurn(turn) {");
  const end = source.indexOf("async function loadBookmarkConversationOnce", start);
  const create = Function(
    "bookmarkDisplayQuestion",
    "bookmarkModelPresentation",
    `${source.slice(start, end)}\nreturn { materializeConversationBookmark };`
  );
  return create(bookmark => String(bookmark?.query || "").trim(), () => []);
}

const agentTurn = overrides => ({ execution_mode: "agent", status: "completed", model_answers: {}, ...overrides });

describe("an Agent turn whose reviewers still work", () => {
  it("stands in the transcript as the chat's newest answer", () => {
    const { materializeConversationBookmark } = conversationHarness();
    const first = agentTurn({ id: "a".repeat(32), question: "Earlier", consensus: "Earlier answer", position: 0 });
    const reviewing = agentTurn({ id: "b".repeat(32), question: "First", consensus: "Answer", position: 1,
      status: "pending", agent_answer_fixed: true });
    const result = materializeConversationBookmark({ query: "First", chat_id: "c".repeat(32) }, [first, reviewing]);
    expect(result.currentTurn.turn_id).toBe("b".repeat(32));
    expect(result.bookmark.responses.consensus).toBe("Answer");
    expect(result.historyTurns.map(turn => turn.turn_id)).toEqual(["a".repeat(32)]);
  });

  it("stands above a later message that already finished", () => {
    const { materializeConversationBookmark } = conversationHarness();
    const reviewing = agentTurn({ id: "b".repeat(32), question: "First", consensus: "Answer", position: 1,
      status: "pending", agent_answer_fixed: true });
    const next = agentTurn({ id: "d".repeat(32), question: "Second", consensus: "Second answer", position: 2 });
    const result = materializeConversationBookmark({ query: "Second", chat_id: "c".repeat(32) }, [reviewing, next]);
    expect(result.historyTurns.map(turn => turn.turn_id)).toEqual(["b".repeat(32)]);
    expect(result.currentTurn.turn_id).toBe("d".repeat(32));
  });

  it("leaves out a pending turn without a fixed answer", () => {
    const { materializeConversationBookmark } = conversationHarness();
    const done = agentTurn({ id: "a".repeat(32), question: "Earlier", consensus: "Earlier answer", position: 0 });
    const running = agentTurn({ id: "b".repeat(32), question: "Now", consensus: "Half an", position: 1, status: "pending" });
    const result = materializeConversationBookmark({ query: "Now", chat_id: "c".repeat(32) }, [done, running]);
    expect(result.currentTurn.turn_id).toBe("a".repeat(32));
    expect(result.historyTurns).toEqual([]);
  });
});
