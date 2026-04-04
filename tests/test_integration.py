"""
Integration tests for lib/note-generator.py — generate_from_json and generate_from_markdown.

Tests the full note generation pipeline using temp files with realistic mock data.
Run with:  python3 -m unittest tests/ -v
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Load lib/note-generator.py and lib/config.py by file path
_LIB = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_LIB))

_spec = importlib.util.spec_from_file_location("note_generator", _LIB / "note-generator.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_from_json = _mod.generate_from_json
generate_from_markdown = _mod.generate_from_markdown


# Minimal config dict for testing (no file I/O needed)
_TEST_CFG = {
    "vault_path": "/tmp/vault",
    "notes_folder": "Resources",
    "default_category": "Inbox",
    "categories": [
        {"name": "AI", "keywords": ["llm", "gpt"], "tags": ["topic/ai"]},
        {"name": "Python", "keywords": ["python", "pip"], "tags": ["topic/python"]},
    ],
    "wikilinks": [
        {"entity": "Python", "target": "[[Python]]"},
        {"entity": "LLM", "target": "[[LLM]]"},
    ],
    "base_tags": ["type/tweet", "source/twitter"],
    "include_engagement": True,
    "include_my_notes": True,
    "distillation_start": 0,
}

# Sample FxTwitter API response
_SAMPLE_TWEET_JSON = {
    "tweet": {
        "url": "https://x.com/testuser/status/12345",
        "text": "Excited to share my new pip package for Python developers!",
        "author": {
            "screen_name": "testuser",
            "name": "Test User",
        },
        "created_at": "Mon Jan 01 12:00:00 +0000 2024",
        "likes": 1500,
        "retweets": 250,
        "replies": 80,
        "views": 50000,
        "bookmarks": 300,
    }
}


class TestGenerateFromJson(unittest.TestCase):
    def setUp(self):
        self._temp_files: list = []

    def _write_json(self, data):
        """Write JSON data to a temp file; return path."""
        tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(data, tf)
        tf.close()
        self._temp_files.append(tf.name)
        return tf.name

    def tearDown(self):
        for path in self._temp_files:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass
        self._temp_files.clear()

    def test_basic_note_generation(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        self.assertIn("note", result)
        self.assertIn("title", result)
        self.assertIn("folder", result)
        self.assertIn("linked_urls", result)

    def test_category_classification(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        # "python" keyword matches "Python" category
        self.assertEqual(result["folder"], "Python")

    def test_wikilinks_applied_in_note(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        # "Python" should be linked in the note body
        self.assertIn("[[Python]]", result["note"])

    def test_frontmatter_tags_include_category_tags(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        note = result["note"]
        self.assertIn("type/tweet", note)
        self.assertIn("source/twitter", note)
        self.assertIn("topic/python", note)

    def test_frontmatter_source_url(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        self.assertIn('source: "https://x.com/testuser/status/12345"', result["note"])

    def test_engagement_included_when_enabled(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        # Engagement emoji should appear in note
        self.assertIn("1.5K", result["note"])  # likes formatted

    def test_engagement_excluded_when_disabled(self):
        cfg = {**_TEST_CFG, "include_engagement": False}
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, cfg)
        # No engagement stats
        self.assertNotIn("❤️", result["note"])

    def test_missing_data_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            generate_from_json("/nonexistent/file.json", _TEST_CFG)

    def test_invalid_json_raises(self):
        tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        tf.write("not valid json {{{")
        tf.close()
        self._temp_files.append(tf.name)
        with self.assertRaises(ValueError):
            generate_from_json(tf.name, _TEST_CFG)

    def test_non_dict_tweet_field_raises(self):
        data = {"tweet": "should be a dict, not a string"}
        path = self._write_json(data)
        with self.assertRaises(ValueError):
            generate_from_json(path, _TEST_CFG)

    def test_default_category_when_no_match(self):
        data = {
            "tweet": {**_SAMPLE_TWEET_JSON["tweet"], "text": "nothing relevant here"}
        }
        path = self._write_json(data)
        result = generate_from_json(path, _TEST_CFG)
        self.assertEqual(result["folder"], "Inbox")

    def test_my_notes_section_included(self):
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, _TEST_CFG)
        self.assertIn("## My Notes", result["note"])

    def test_my_notes_section_excluded(self):
        cfg = {**_TEST_CFG, "include_my_notes": False}
        path = self._write_json(_SAMPLE_TWEET_JSON)
        result = generate_from_json(path, cfg)
        self.assertNotIn("## My Notes", result["note"])

    def test_linked_urls_extracted(self):
        data = {
            "tweet": {
                **_SAMPLE_TWEET_JSON["tweet"],
                "text": "Check out https://example.com for more info",
            }
        }
        path = self._write_json(data)
        result = generate_from_json(path, _TEST_CFG)
        self.assertIn("https://example.com", result["linked_urls"])


class TestGenerateFromMarkdown(unittest.TestCase):
    def setUp(self):
        self._temp_files: list = []

    def _write_md(self, content):
        tf = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w")
        tf.write(content)
        tf.close()
        self._temp_files.append(tf.name)
        return tf.name

    def tearDown(self):
        for path in self._temp_files:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass
        self._temp_files.clear()

    def test_basic_markdown_note(self):
        content = "Just released a new pip install package for Python developers."
        path = self._write_md(content)
        result = generate_from_markdown(path, _TEST_CFG, "https://x.com/user/status/99")
        self.assertIn("note", result)
        self.assertIn("title", result)
        self.assertEqual(result["folder"], "Python")

    def test_author_extracted_from_url(self):
        content = "Some tweet text"
        path = self._write_md(content)
        result = generate_from_markdown(path, _TEST_CFG, "https://x.com/alice/status/123")
        self.assertIn("@alice", result["note"])

    def test_missing_data_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            generate_from_markdown("/nonexistent/file.md", _TEST_CFG, None)

    def test_jina_content_extraction(self):
        # Jina wraps content with "Markdown Content:\n===\n" prefix
        content = "Markdown Content:\n===\nActual tweet text about Python."
        path = self._write_md(content)
        result = generate_from_markdown(path, _TEST_CFG, "https://x.com/user/status/1")
        self.assertEqual(result["folder"], "Python")

    def test_no_tweet_url_uses_empty_source(self):
        content = "Some tweet text"
        path = self._write_md(content)
        result = generate_from_markdown(path, _TEST_CFG, None)
        self.assertIn('source: ""', result["note"])


if __name__ == "__main__":
    unittest.main()
