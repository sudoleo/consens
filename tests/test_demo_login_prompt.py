import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoLoginPromptContractTests(unittest.TestCase):
    def test_prompt_is_hidden_until_demo_finishes(self):
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
        shell = (ROOT / "static" / "css" / "shell.css").read_text(encoding="utf-8")

        self.assertIn('id="postDemoLoginPrompt"', template)
        self.assertIn('aria-live="polite" hidden', template)
        self.assertIn("showPostDemoLoginPrompt();", demo_module)
        self.assertIn("if (!prompt || window.auth?.currentUser) return;", demo_module)
        self.assertIn(
            "body:has(#postDemoLoginPrompt:not([hidden])) .chat-input-container",
            shell,
        )

    def test_prompt_opens_login_and_is_removed_after_auth(self):
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
        app_init = (ROOT / "static" / "js" / "app-init.js").read_text(encoding="utf-8")

        self.assertIn('id="postDemoLoginButton"', template)
        self.assertIn('document.getElementById("loginModal")', demo_module)
        self.assertIn("postDemoLoginPrompt.hidden = true;", app_init)

    def test_question_is_cleared_before_model_loading_starts(self):
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
        flow = demo_module.split("async function runDemoFlow()", 1)[1]
        typed = flow.index("await typeIntoInput")
        cleared = flow.index('qi.value = "";')
        loading = flow.index('window.setAgentModeStatus?.("running");')

        self.assertLess(typed, cleared)
        self.assertLess(cleared, loading)
        self.assertNotIn(
            'window.setAgentModeStatus?.("running");',
            flow[:cleared],
        )

    def test_demo_plays_the_one_mode_without_a_score(self):
        # Since 2026-10-31 the Agent has one mode: the reviewers' notes on the
        # answer, no judges and no agreement score.
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")

        self.assertIn('version: 1, mode: "audit", status,', demo_module)
        self.assertIn('kind: "audit", title: `Review · ${model.label}`', demo_module)
        self.assertIn('name: "audit_answer"', demo_module)
        for gone in ("agreement: {", "score:", "differencesData", "judge", "Coverage judge"):
            self.assertNotIn(gone, demo_module)

    def test_every_reviewer_note_stands_on_a_sentence_of_the_answer(self):
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
        answer = demo_module.split("  answer:\n`", 1)[1].split("`,", 1)[0]
        notes = demo_module.split("  notes: [", 1)[1].split("\n  ]\n", 1)[0]
        kinds = re.findall(r'kind: "([a-z]+)"', notes)
        self.assertEqual(sorted(kinds), ["doubtful", "incomplete", "wrong"])
        anchors = re.findall(r'anchor: "([^"]+)"', notes)
        targets = re.findall(r'target: "([^"]+)"', notes)
        self.assertEqual(len(anchors), 3)
        for anchor, target in zip(anchors, targets, strict=True):
            self.assertIn(anchor, answer)
            self.assertIn(target, anchor)


if __name__ == "__main__":
    unittest.main()
