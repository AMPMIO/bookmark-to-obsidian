#!/usr/bin/env python3
"""
bookmark-to-obsidian note generator.

Converts tweet data (FxTwitter JSON or Jina markdown) into Obsidian vault note content.

Usage:
  python3 lib/note-generator.py <data-file> [--config <path>] [--format json|markdown] [--url <tweet-url>]

Input formats:
  json (default)  FxTwitter API response JSON
  markdown        Jina Reader markdown content

Output (JSON to stdout):
  {
    "note": "<full note markdown content>",
    "title": "<note title>",
    "folder": "<category folder name>",
    "linked_urls": ["<url1>", ...]
  }
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def _load_cfg(config_path=None):
    lib_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(lib_dir))
    from config import load_config
    return load_config(config_path)


def fmt_number(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def extract_title(text, screen_name):
    """Smart title extraction from tweet text."""
    # GitHub repo pattern: github.com/owner/repo
    github_match = re.search(r'github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', text)
    if github_match:
        repo = re.sub(r'[.,!?)\]]+$', '', github_match.group(1))
        if len(repo) > 3:
            return repo

    lines = text.strip().split('\n')
    first = lines[0].strip()
    # Remove URLs
    first = re.sub(r'https?://\S+', '', first).strip()
    # Remove leading @mentions
    first = re.sub(r'^(@\w+\s*)+', '', first).strip()

    # Announcement patterns: "Introducing Foo", "Launching Foo v1", etc.
    intro = re.match(
        r'^(?:Introducing|Announcing|Launching|Releasing|Just\s+released?:?)\s+(.+?)[\.\!\n,]',
        first, re.IGNORECASE
    )
    if intro:
        candidate = intro.group(1).strip()[:80]
        if len(candidate) > 3:
            return candidate

    title = first[:80].strip()
    if title:
        return title

    return f"Tweet by @{screen_name}"


def classify(text, categories, default):
    lower = text.lower()
    for cat in categories:
        for kw in cat.get("keywords", []):
            if kw.lower() in lower:
                return cat["name"]
    return default


def apply_wikilinks(text, wikilinks):
    """Apply configured wikilinks (first occurrence of each entity)."""
    for item in wikilinks:
        if isinstance(item, dict):
            entity = item.get("entity", "")
            target = item.get("target", f"[[{entity}]]" if entity else "")
        else:
            entity = str(item)
            target = f"[[{entity}]]"
        if not entity:
            continue
        pattern = re.compile(r'\b' + re.escape(entity) + r'\b')
        text = pattern.sub(target, text, count=1)
    return text


def extract_linked_urls(text):
    """Extract non-Twitter/t.co URLs from tweet text for enrichment."""
    urls = re.findall(r'https?://\S+', text)
    result = []
    seen = set()
    for url in urls:
        url = url.rstrip('.,!?)\]"\'')
        if re.search(r'(x\.com|twitter\.com|t\.co)', url):
            continue
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def generate_from_json(data_file, cfg):
    """Generate note from FxTwitter JSON data."""
    with open(data_file) as f:
        data = json.load(f)

    tweet = data.get("tweet", {})
    text = tweet.get("text", "").strip()
    author = tweet.get("author", {})
    screen_name = author.get("screen_name", "unknown")
    display_name = author.get("name", screen_name)
    created_at = tweet.get("created_at", "")
    url = tweet.get("url", "")
    likes = tweet.get("likes", 0)
    retweets = tweet.get("retweets", 0)
    replies = tweet.get("replies", 0)
    views = tweet.get("views", 0)
    bookmarks_n = tweet.get("bookmarks", 0)

    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        tweet_date = dt.strftime("%Y-%m-%d")
        display_date = dt.strftime("%b %d, %Y")
    except Exception:
        tweet_date = display_date = datetime.now().strftime("%Y-%m-%d")

    engagement = (
        f"\U0001f4ac {fmt_number(replies)} \u00b7 "
        f"\U0001f501 {fmt_number(retweets)} \u00b7 "
        f"\u2764\ufe0f {fmt_number(likes)} \u00b7 "
        f"\U0001f441 {fmt_number(views)} \u00b7 "
        f"\U0001f516 {fmt_number(bookmarks_n)}"
    )

    media = tweet.get("media", {}) or {}
    media_types = []
    for item in media.get("all", []):
        mt = item.get("type", "")
        if mt and mt not in media_types:
            media_types.append(mt)

    title = extract_title(text, screen_name)
    folder = classify(text, cfg["categories"], cfg["default_category"])
    linked_text = apply_wikilinks(text, cfg["wikilinks"])
    linked_urls = extract_linked_urls(text)

    tags_str = ", ".join(cfg["base_tags"])
    today = datetime.now().strftime("%Y-%m-%d")

    # Quote tweet
    quote = tweet.get("quote")
    quote_section = ""
    if quote:
        q_author = quote.get("author", {})
        q_name = q_author.get("screen_name", "unknown")
        q_display = q_author.get("name", q_name)
        q_text = quote.get("text", "").strip()
        q_url = quote.get("url", "")
        q_body = q_text.replace("\n", "\n> ")
        quote_section = f"\n## Quoted Tweet\n\n> **@{q_name}** ({q_display}):\n> {q_body}\n>\n> Source: {q_url}\n"

    # X Article
    article = tweet.get("article")
    article_section = ""
    if article:
        blocks = (article.get("content") or {}).get("blocks", [])
        if blocks:
            article_text = "\n\n".join(b.get("text", "") for b in blocks if b.get("text"))
            article_section = f"\n## Article Content\n\n{article_text}\n"

    media_line = f"\n**Media:** {', '.join(media_types)}" if media_types else ""
    engagement_line = f"\n{engagement}{media_line}\n" if cfg["include_engagement"] else ""
    my_notes = "\n## My Notes\n\n-\n" if cfg["include_my_notes"] else ""

    note = (
        f"---\n"
        f"tags: [{tags_str}]\n"
        f"created: {today}\n"
        f'source: "{url}"\n'
        f'author: "@{screen_name} ({display_name})"\n'
        f"tweet_date: {tweet_date}\n"
        f"distillation: {cfg['distillation_start']}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"**Source:** {url}\n"
        f"**Author:** @{screen_name} ({display_name}) · {display_date}\n"
        f"{engagement_line}\n"
        f"## Summary\n\n"
        f"{linked_text}\n"
        f"{quote_section}"
        f"{article_section}"
        f"{my_notes}"
    )

    return {
        "note": note.rstrip() + "\n",
        "title": title,
        "folder": folder,
        "linked_urls": linked_urls,
    }


def generate_from_markdown(data_file, cfg, tweet_url):
    """Generate note from Jina Reader markdown (Tier 2 fallback)."""
    with open(data_file) as f:
        content = f.read()

    text = content.strip()

    # Jina wraps content; try to extract just the main body
    content_match = re.search(r'Markdown Content:\s*\n=+\s*\n(.*)', text, re.DOTALL)
    if content_match:
        text = content_match.group(1).strip()

    screen_name = "unknown"
    if tweet_url:
        user_match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)/status/', tweet_url)
        if user_match:
            screen_name = user_match.group(1)

    title = extract_title(text, screen_name)
    folder = classify(text, cfg["categories"], cfg["default_category"])
    linked_text = apply_wikilinks(text, cfg["wikilinks"])
    linked_urls = extract_linked_urls(text)

    tags_str = ", ".join(cfg["base_tags"])
    today = datetime.now().strftime("%Y-%m-%d")
    url = tweet_url or ""

    my_notes = "\n## My Notes\n\n-\n" if cfg["include_my_notes"] else ""

    note = (
        f"---\n"
        f"tags: [{tags_str}]\n"
        f"created: {today}\n"
        f'source: "{url}"\n'
        f'author: "@{screen_name}"\n'
        f"tweet_date: {today}\n"
        f"distillation: {cfg['distillation_start']}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"**Source:** {url}\n"
        f"**Author:** @{screen_name}\n\n"
        f"## Summary\n\n"
        f"{linked_text}\n"
        f"{my_notes}"
    )

    return {
        "note": note.rstrip() + "\n",
        "title": title,
        "folder": folder,
        "linked_urls": linked_urls,
    }


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    data_file = args[0]
    config_path = None
    fmt = "json"
    tweet_url = None

    i = 1
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1]
            i += 2
        elif args[i] == "--url" and i + 1 < len(args):
            tweet_url = args[i + 1]
            i += 2
        else:
            i += 1

    cfg = _load_cfg(config_path)

    try:
        if fmt == "markdown":
            result = generate_from_markdown(data_file, cfg, tweet_url)
        else:
            result = generate_from_json(data_file, cfg)
    except Exception as e:
        print(f"Error generating note: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
