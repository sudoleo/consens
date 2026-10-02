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

    def test_demo_result_has_an_agreement_score(self):
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")

        self.assertIn("agreement: {", demo_module)
        self.assertIn("score: 43,", demo_module)

    def test_every_checkable_demo_passage_has_a_coverage_claim(self):
        demo_module = (ROOT / "static" / "demo.js").read_text(encoding="utf-8")
        claims = demo_module.split("    claims: [", 1)[1].split(
            "    differences: [", 1
        )[0]
        anchors = (
            "Consensus: probably yes, with a few radiators changed",
            "All six models think a heat pump can heat this house",
            "The walls were insulated in 2015",
            "What none of them can tell you from here",
            "Get a room-by-room heat-loss calculation",
            "Test it this winter",
            "Rooms that stay warm keep their radiators",
            "Original 1970s radiators are often larger than the room needs today",
            "Have the heat pump sized from the calculation",
            "The models split on the target flow temperature",
            "They also disagree on what that costs you",
            "Keeping the gas boiler as a backup for the coldest days divides them as well",
            "Whether to start with the survey or with the winter test",
            "Heat-loss survey: 140 m² at roughly 8 kW.",
            "Test week at 50 °C",
            "Replace those two radiators, or more.",
            "Heat pump sized at 8 to 9 kW.",
            "Target flow temperature.",
            "Both bracketed parts are the ones the models could not settle for you",
        )
        for anchor in anchors:
            self.assertIn(f'anchor: "{anchor}"', claims)
        self.assertEqual(claims.count('coverage: "'), len(anchors))


if __name__ == "__main__":
    unittest.main()
