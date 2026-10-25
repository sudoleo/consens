import unittest

import app.core.config as cfg


class ConsensusInputLimitTests(unittest.TestCase):
    def test_default_limits_exist_and_are_generous(self):
        self.assertGreaterEqual(cfg.get_consensus_answer_char_limit(), 30_000)
        self.assertGreaterEqual(cfg.get_consensus_question_char_limit(), 4_000)

    def test_limits_are_admin_overridable(self):
        original = cfg.get_limits_config()
        try:
            overrides = dict(original)
            overrides["consensus_max_answer_chars"] = 12_345
            overrides["consensus_max_question_chars"] = 1_234
            cfg.apply_limits(overrides)
            self.assertEqual(cfg.get_consensus_answer_char_limit(), 12_345)
            self.assertEqual(cfg.get_consensus_question_char_limit(), 1_234)
        finally:
            cfg.apply_limits(original)

    def test_answer_limit_never_clips_legit_reasoning_answers(self):
        # 8192 Output-Tokens entsprechen grob 32k Zeichen; der Cap muss
        # darüber liegen, sonst kappt er echte Antworten statt Abuse.
        approx_max_answer_chars = cfg.LIMITS["reasoning_max_tokens"] * 4
        self.assertGreaterEqual(
            cfg.get_consensus_answer_char_limit(), approx_max_answer_chars
        )


if __name__ == "__main__":
    unittest.main()
