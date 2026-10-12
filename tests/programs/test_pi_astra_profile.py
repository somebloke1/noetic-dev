"""The routed Astra fragment does not replace native subscription authentication."""

import json
from pathlib import Path
import unittest


class PiAstraProfileTests(unittest.TestCase):
    def test_fragment_uses_proxy_responses_without_subscription_secrets(self):
        path = Path(__file__).resolve().parents[2] / "config/pi-astra-models.json"
        fragment = json.loads(path.read_text())
        self.assertEqual(set(fragment["providers"]), {"litellm"})
        provider = fragment["providers"]["litellm"]
        self.assertEqual(set(provider), {"models"})
        self.assertEqual(len(provider["models"]), 1)
        model = provider["models"][0]
        self.assertEqual(model["id"], "codex/gpt-6-astra")
        self.assertEqual(model["api"], "openai-responses")
        self.assertNotIn("apiKey", model)
        self.assertNotIn("baseUrl", model)
        self.assertTrue(model["reasoning"])
        self.assertEqual(model["input"], ["text", "image"])
        self.assertEqual(model["thinkingLevelMap"]["high"], "high")
        self.assertEqual(model["thinkingLevelMap"]["max"], "max")
        self.assertIsNone(model["thinkingLevelMap"]["off"])


if __name__ == "__main__":
    unittest.main()
