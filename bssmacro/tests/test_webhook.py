import unittest

from bssmacro.types import Stats
from bssmacro.webhook.discord import DiscordWebhook, WebhookConfig


class TestWebhook(unittest.TestCase):
    def test_disabled(self):
        wh = DiscordWebhook(WebhookConfig(url=""))
        self.assertFalse(wh.cfg.enabled())
        self.assertFalse(wh.maybe_heartbeat(Stats(), None, now=0.0))
        self.assertFalse(wh.notify_event("start", Stats(), None, now=0.0))

    def test_event_filter(self):
        cfg = WebhookConfig(url="https://example.com/x", on_events=["start"])
        wh = DiscordWebhook(cfg)
        # "windy" is not in on_events -> should not send
        self.assertFalse(wh.notify_event("windy", Stats(), None, now=0.0))

    def test_heartbeat_throttled(self):
        cfg = WebhookConfig(url="https://example.com/x", interval_sec=60)
        wh = DiscordWebhook(cfg)
        # now=0 and last=0 -> elapsed 0 < 60 -> skip (no network)
        self.assertFalse(wh.maybe_heartbeat(Stats(), None, now=0.0))
        # jump far ahead -> would attempt send; stub _post to avoid network
        wh._post = lambda payload, files: True  # type: ignore[assignment]
        wh._last_heartbeat = 0.0
        self.assertTrue(wh.maybe_heartbeat(Stats(), None, now=1000.0))

    def test_payload_structure(self):
        cfg = WebhookConfig(url="https://example.com/x", color=0x123456)
        wh = DiscordWebhook(cfg)
        payload = wh._build_payload(Stats(), "Heartbeat", 0x123456, "")
        self.assertIn("embeds", payload)
        embed = payload["embeds"][0]
        self.assertEqual(embed["color"], 0x123456)
        self.assertEqual(embed["title"], "Heartbeat")
        names = {f["name"] for f in embed["fields"]}
        self.assertIn("Uptime", names)
        self.assertIn("Tokens/min", names)

    def test_send_with_stub(self):
        cfg = WebhookConfig(url="https://example.com/x")
        wh = DiscordWebhook(cfg)
        sent = {}

        def _post(payload, files):
            sent["payload"] = payload
            sent["files"] = files
            return True

        wh._post = _post  # type: ignore[assignment]
        ok = wh.send(Stats(), None, title="Test", description="hi")
        self.assertTrue(ok)
        self.assertIn("embeds", sent["payload"])
        self.assertIsNone(sent["files"])


if __name__ == "__main__":
    unittest.main()
