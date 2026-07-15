import json
import re
import unicodedata
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalize_name(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().replace("&", " and ").replace("'", "").replace("’", "")
    value = re.sub(
        r"\b(first nations?|cree nation|dene nation|dakota nation|nakoda nation|saulteaux nation|indian band)\b",
        " ",
        value,
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


class NewsIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bands = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))["bands"]
        cls.news = json.loads((ROOT / "news-data.json").read_text(encoding="utf-8"))["articles"]

    def test_band_ids_and_community_names_agree(self):
        bands_by_id = {str(band["id"]): band for band in self.bands}
        for article in self.news:
            if article.get("bandId") is None:
                continue
            band = bands_by_id.get(str(article["bandId"]))
            self.assertIsNotNone(band, article.get("title"))
            identities = [article.get("communityName"), article.get("community")]
            identities.extend(article.get("communityAliases") or [])
            self.assertIn(normalize_name(band["name"]), {normalize_name(value) for value in identities})

    def test_every_article_has_source_identity(self):
        for article in self.news:
            self.assertTrue(article.get("title"))
            self.assertRegex(str(article.get("url") or ""), r"^https://")
            self.assertTrue(article.get("publishedAt"))


if __name__ == "__main__":
    unittest.main()
