"""
Unit tests for lib/note-generator.py core functions.

Tests the pure transformation logic (no file I/O, no config loading).
Run with:  python3 -m pytest tests/ -v
       or: python3 -m unittest tests/test_note_generator.py -v
"""

import importlib.util
import sys
import unittest
from pathlib import Path

# Load lib/note-generator.py by file path (hyphens prevent direct import)
_module_path = Path(__file__).resolve().parent.parent / "lib" / "note-generator.py"
_spec = importlib.util.spec_from_file_location("note_generator", _module_path)
_mod = importlib.util.module_from_spec(_spec)
# note-generator.py adds lib/ to sys.path internally for config import; pre-insert it
sys.path.insert(0, str(_module_path.parent))
_spec.loader.exec_module(_mod)

apply_wikilinks = _mod.apply_wikilinks
classify_tweet = _mod.classify_tweet
extract_linked_urls = _mod.extract_linked_urls
extract_title = _mod.extract_title
fmt_number = _mod.fmt_number


class TestFmtNumber(unittest.TestCase):
    def test_below_thousand(self):
        self.assertEqual(fmt_number(0), "0")
        self.assertEqual(fmt_number(999), "999")

    def test_thousands(self):
        self.assertEqual(fmt_number(1000), "1.0K")
        self.assertEqual(fmt_number(1500), "1.5K")
        self.assertEqual(fmt_number(999_999), "1.0M")

    def test_millions(self):
        self.assertEqual(fmt_number(1_000_000), "1.0M")
        self.assertEqual(fmt_number(2_500_000), "2.5M")


class TestExtractTitle(unittest.TestCase):
    def test_announcement_pattern(self):
        title = extract_title("Introducing MyLib — a fast JSON parser", "user")
        self.assertIn("MyLib", title)

    def test_github_url(self):
        title = extract_title("Check out github.com/owner/awesome-repo for details", "user")
        self.assertEqual(title, "owner/awesome-repo")

    def test_strips_leading_url(self):
        title = extract_title("https://example.com is a great site for learning", "user")
        self.assertNotIn("https://", title)

    def test_fallback_to_username(self):
        # Empty text falls back to "@username"
        title = extract_title("", "alice")
        self.assertIn("alice", title)

    def test_truncation(self):
        long_text = "A" * 200
        title = extract_title(long_text, "user")
        self.assertLessEqual(len(title), 80)


class TestClassifyTweet(unittest.TestCase):
    CATEGORIES = [
        {"name": "AI", "keywords": ["llm", "gpt", "neural network"], "tags": ["topic/ai"]},
        {"name": "Python", "keywords": ["python", "pip", "pypi"], "tags": ["topic/python"]},
    ]
    DEFAULT = "Inbox"

    def test_first_match_wins(self):
        folder, tags = classify_tweet("This llm is written in python", self.CATEGORIES, self.DEFAULT)
        self.assertEqual(folder, "AI")
        self.assertIn("topic/ai", tags)

    def test_case_insensitive(self):
        folder, tags = classify_tweet("GPT-4 is impressive", self.CATEGORIES, self.DEFAULT)
        self.assertEqual(folder, "AI")

    def test_default_when_no_match(self):
        folder, tags = classify_tweet("Nothing relevant here", self.CATEGORIES, self.DEFAULT)
        self.assertEqual(folder, self.DEFAULT)
        self.assertEqual(tags, [])

    def test_category_tags_returned(self):
        _, tags = classify_tweet("pip install mypackage", self.CATEGORIES, self.DEFAULT)
        self.assertEqual(tags, ["topic/python"])

    def test_empty_text_returns_default(self):
        folder, tags = classify_tweet("", self.CATEGORIES, self.DEFAULT)
        self.assertEqual(folder, self.DEFAULT)


class TestApplyWikilinks(unittest.TestCase):
    def test_basic_replacement(self):
        wikilinks = [{"entity": "Python", "target": "[[Python]]"}]
        result = apply_wikilinks("I love Python programming", wikilinks)
        self.assertIn("[[Python]]", result)

    def test_longest_first_prevents_partial_match(self):
        # "React Native" should match before "React"
        wikilinks = [
            {"entity": "React", "target": "[[React]]"},
            {"entity": "React Native", "target": "[[React Native]]"},
        ]
        result = apply_wikilinks("React Native is a framework", wikilinks)
        self.assertIn("[[React Native]]", result)
        self.assertNotIn("[[React]] Native", result)

    def test_only_first_occurrence_replaced(self):
        wikilinks = [{"entity": "Python", "target": "[[Python]]"}]
        result = apply_wikilinks("Python is a language. Python is great.", wikilinks)
        self.assertEqual(result.count("[[Python]]"), 1)

    def test_no_match_returns_unchanged(self):
        wikilinks = [{"entity": "Rust", "target": "[[Rust]]"}]
        original = "I love Python programming"
        result = apply_wikilinks(original, wikilinks)
        self.assertEqual(result, original)

    def test_entity_without_target_uses_double_brackets(self):
        wikilinks = [{"entity": "TypeScript"}]
        result = apply_wikilinks("I use TypeScript daily", wikilinks)
        self.assertIn("[[TypeScript]]", result)

    def test_empty_wikilinks_returns_unchanged(self):
        original = "Some tweet text"
        result = apply_wikilinks(original, [])
        self.assertEqual(result, original)


class TestExtractLinkedUrls(unittest.TestCase):
    def test_extracts_external_url(self):
        urls = extract_linked_urls("Check out https://example.com for more")
        self.assertEqual(urls, ["https://example.com"])

    def test_skips_twitter_urls(self):
        urls = extract_linked_urls("See https://x.com/user/status/123 and https://twitter.com/foo")
        self.assertEqual(urls, [])

    def test_skips_t_co_urls(self):
        urls = extract_linked_urls("Short link https://t.co/abc123 here")
        self.assertEqual(urls, [])

    def test_deduplicates(self):
        urls = extract_linked_urls("https://example.com first and https://example.com again")
        self.assertEqual(urls, ["https://example.com"])

    def test_strips_trailing_punctuation(self):
        urls = extract_linked_urls("Visit https://example.com.")
        self.assertIn("https://example.com", urls)
        self.assertNotIn("https://example.com.", urls)

    def test_multiple_urls_preserved(self):
        urls = extract_linked_urls("See https://a.com and https://b.com for details")
        self.assertEqual(len(urls), 2)


if __name__ == "__main__":
    unittest.main()
