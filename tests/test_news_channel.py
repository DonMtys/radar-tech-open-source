import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.news_channel import run_news_round


class TestNewsChannel(unittest.TestCase):
    def test_one_post_per_round_alternates_and_deduplicates(self):
        project = {
            "kind": "github", "url": "https://github.com/example/new-agent",
            "title": "example/new-agent", "description": "AI agent toolkit",
            "stars": 42, "language": "Python", "published": "2026-10-10",
        }
        article = {
            "kind": "news", "url": "https://example.org/tech-story",
            "title": "New database engine released", "source": "example.org",
            "discussion": "https://news.ycombinator.com/item?id=123",
            "published": "Sat, 10 Oct 2026 12:00:00 GMT",
        }
        sent = []

        def sender(**kwargs):
            sent.append(kwargs["text"])
            return {"ok": True, "message_id": len(sent)}

        with tempfile.TemporaryDirectory() as directory, patch(
            "src.news_channel.get_telegram_config", return_value=("test-token", "test-channel")
        ):
            db_path = Path(directory) / "radar.db"
            options = dict(db_path=db_path, github_fetch=lambda now: [project],
                           news_fetch=lambda now: [article], sender=sender,
                           max_daily_posts=2, min_interval_minutes=0)
            preview = run_news_round(preview=True, **options)
            first = run_news_round(**options)
            cooldown = run_news_round(**{**options, "min_interval_minutes": 55})
            second = run_news_round(**options)
            third = run_news_round(**options)

        self.assertEqual(preview["status"], "preview")
        self.assertEqual(cooldown["status"], "cooldown")
        self.assertEqual([first["kind"], second["kind"]], ["github", "news"])
        self.assertEqual(third["status"], "daily_limit")
        self.assertEqual(len(sent), 2)
        self.assertIn("42 estrelas", sent[0])
        self.assertIn(article["url"], sent[1])


if __name__ == "__main__":
    unittest.main()
