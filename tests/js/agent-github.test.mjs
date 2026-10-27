import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// GitHub for the agent's VM (agent-github.js): the pull request card under an
// answer, which alone sends a prepared change to GitHub, and the connection
// in Settings.
function setup() {
  const app = loadScripts(["static/js/agent-github.js"], {
    body: '<div id="agentGithubSettings"></div><div><div id="answer"></div></div>' });
  const { window } = app;
  window.auth = { currentUser: { uid: "u1", getIdToken: async () => "token" } };
  window.App.showPopup = vi.fn();
  return { app, window, document: app.document, github: window.App.agentGithub };
}

function reply(data, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}

function proposal(fields = {}) {
  return { id: "p1", status: "pending", repo: "maxl/app", base: "main", branch: "consens/fix-1a2b",
    title: "Fix the greeting", body: "Says hello.", hash: "a".repeat(64), diff: "-hi\n+hello\n", diff_truncated: false,
    approval_until: "2999-01-01T00:00:00+00:00",
    files: [{ path: "src/main.py", change: "modified", additions: 3, deletions: 1 },
      { path: "old.txt", change: "deleted", additions: 0, deletions: 5 }], ...fields };
}

describe("the pull request card", () => {
  it("shows where the change goes and what it changes, nothing sent yet", () => {
    const { document, github } = setup();
    const answer = document.getElementById("answer");
    github.render(answer, { key: "c:t", proposal: proposal(), chatId: "c", turnId: "t" });
    const card = answer.nextElementSibling;
    expect(card.className).toBe("agent-pr-card");
    expect(card.querySelector(".agent-pr-title").textContent).toBe("Pull request ready for review");
    expect(card.querySelector(".agent-pr-target").textContent).toBe("maxl/app · consens/fix-1a2b → main");
    expect([...card.querySelectorAll(".agent-pr-files li")].map(li => li.textContent))
      .toEqual(["~ src/main.py +3 −1", "− old.txt +0 −5"]);
    // Repository, branch, title, files and diff are data.
    for (const selector of [".agent-pr-target", ".agent-pr-name", ".agent-pr-files", ".agent-pr-diff-text"]) {
      expect(card.querySelector(selector).hasAttribute("data-i18n-skip")).toBe(true);
    }
    expect(card.querySelector(".agent-pr-status").textContent).toContain("Nothing goes to GitHub");
    expect(card.querySelector(".agent-pr-create").hidden).toBe(false);
    expect(card.querySelector(".agent-pr-open").hidden).toBe(true);
  });

  it("lists every file when the diff is cut, otherwise the first 20", () => {
    // Security audit 2026-10-27: nothing goes up unseen.
    const { document, github } = setup();
    const answer = document.getElementById("answer");
    const files = Array.from({ length: 25 }, (_, n) => ({ path: `docs/${n}.md`, change: "added" }));
    github.render(answer, { key: "c:t", proposal: proposal({ files }), chatId: "c", turnId: "t" });
    const card = answer.nextElementSibling;
    expect(card.querySelectorAll(".agent-pr-files li").length).toBe(20);
    expect(card.querySelector(".agent-pr-more").textContent).toBe("and 5 more files");
    github.render(answer, { key: "c:t", proposal: proposal({ files, diff_truncated: true }), chatId: "c", turnId: "t" });
    expect(card.querySelectorAll(".agent-pr-files li").length).toBe(25);
    expect(card.querySelector(".agent-pr-more").hidden).toBe(true);
  });

  it("creates the pull request with the exact preview and then links to it", async () => {
    const { window, document, github } = setup();
    window.fetch = vi.fn(async () => reply({ pull_request: { status: "succeeded",
      result: { number: 12, url: "https://github.com/maxl/app/pull/12" } } }));
    const answer = document.getElementById("answer");
    github.render(answer, { key: "c:t", proposal: proposal(), chatId: "c", turnId: "t" });
    answer.nextElementSibling.querySelector(".agent-pr-create").click();
    await vi.waitFor(() => expect(answer.nextElementSibling.dataset.state).toBe("succeeded"));
    const [url, options] = window.fetch.mock.calls[0];
    expect(url).toBe("/agent/chats/c/turns/t/pull-request");
    expect(JSON.parse(options.body)).toEqual({ expected_hash: "a".repeat(64) });
    const card = answer.nextElementSibling;
    expect(card.querySelector(".agent-pr-title").textContent).toBe("Pull request created");
    const link = card.querySelector(".agent-pr-open");
    expect(link.hidden).toBe(false);
    expect(link.href).toBe("https://github.com/maxl/app/pull/12");
    expect(link.textContent).toBe("Open pull request #12 on GitHub");
    expect(card.querySelector(".agent-pr-create").hidden).toBe(true);
    // The saved turn still says pending until it reloads: the decision stands.
    github.render(answer, { key: "c:t", proposal: proposal(), chatId: "c", turnId: "t" });
    expect(card.dataset.state).toBe("succeeded");
  });

  it("says an expired preview cannot be sent and never links elsewhere than GitHub", () => {
    const { document, github } = setup();
    const answer = document.getElementById("answer");
    github.render(answer, { key: "c:t", proposal: proposal({ approval_until: "2000-01-01T00:00:00+00:00" }),
      chatId: "c", turnId: "t" });
    const card = answer.nextElementSibling;
    expect(card.querySelector(".agent-pr-create").hidden).toBe(true);
    expect(card.querySelector(".agent-pr-status").textContent).toContain("expired");
    github.render(answer, { key: "c:t", proposal: proposal({ status: "succeeded",
      result: { number: 3, url: "https://evil.example/pr" } }), chatId: "c", turnId: "t" });
    expect(card.querySelector(".agent-pr-open").hidden).toBe(true);
    github.render(answer, { key: "c:t", proposal: null });
    expect(answer.nextElementSibling).toBeNull();
  });
});

describe("GitHub in Settings", () => {
  it("shows the connection and its repositories, with disconnect and manage", async () => {
    const { window, document, github } = setup();
    window.fetch = vi.fn(async () => reply({ configured: true, connected: true,
      login: "maxl", repositories: ["maxl/app", "org/readonly"], manage_url: "https://github.com/settings/installations" }));
    await github.loadConnection();
    const host = document.getElementById("agentGithubSettings");
    expect(host.querySelector(".agent-github-status").textContent).toBe("Connected as maxl.");
    expect(host.querySelector(".agent-github-repos").textContent).toBe("maxl/app, org/readonly");
    const [connect, disconnect, manage] = host.querySelectorAll(".agent-github-link");
    expect(connect.textContent).toBe("Connect again");
    expect(disconnect.hidden).toBe(false);
    expect(manage.href).toBe("https://github.com/settings/installations");
  });

  it("says when the installation has no GitHub app yet", async () => {
    const { window, document, github } = setup();
    window.fetch = vi.fn(async () => reply({ configured: false, connected: false, repositories: [] }));
    await github.loadConnection();
    const host = document.getElementById("agentGithubSettings");
    expect(host.querySelector(".agent-github-status").textContent).toBe("GitHub is not set up on this installation yet.");
    expect(host.querySelector(".agent-github-link").hidden).toBe(true);
  });
});
