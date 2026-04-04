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
from typing import Any, Dict, List, Optional, Tuple


def _load_cfg(config_path: Optional[str] = None) -> Dict[str, Any]:
    lib_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(lib_dir))
    from config import load_config
    return load_config(config_path)


def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def extract_title(text: str, screen_name: str) -> str:
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


def classify_tweet(text: str, categories: List[Dict[str, Any]], default: str) -> Tuple[str, List[str]]:
    """Return (folder_name, category_tags) for the first matching category.

    Checks category keywords case-insensitively in config order — first match wins.
    Returns (default_category, []) if no category matches.
    """
    lower = text.lower()
    for cat in categories:
        for kw in cat.get("keywords", []):
            if kw.lower() in lower:
                return cat["name"], cat.get("tags") or []
    return default, []


def apply_wikilinks(text: str, wikilinks: List[Any]) -> str:
    """Apply configured wikilinks (first occurrence of each entity).

    Entities are sorted longest-first before matching so that longer names
    (e.g. "React Native") are linked before shorter overlapping names ("React").
    Placeholders prevent already-linked text from being re-matched (e.g.
    "React" inside "[[React Native]]" is not separately linked).
    """
    pairs = []
    for item in wikilinks:
        if isinstance(item, dict):
            entity = item.get("entity", "")
            target = item.get("target", f"[[{entity}]]" if entity else "")
        else:
            entity = str(item)
            target = f"[[{entity}]]"
        if entity:
            pairs.append((entity, target))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)

    # Replace matched entities with null-byte placeholders so shorter overlapping
    # names are not re-matched inside an already-linked span.
    placeholders = {}
    for i, (entity, target) in enumerate(pairs):
        placeholder = f"\x00{i}\x00"
        placeholders[placeholder] = target
        pattern = re.compile(r'\b' + re.escape(entity) + r'\b')
        text = pattern.sub(placeholder, text, count=1)
    for placeholder, target in placeholders.items():
        text = text.replace(placeholder, target)
    return text


def extract_linked_urls(text: str) -> List[str]:
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


def _classify_and_tag(text: str, cfg: Dict[str, Any]) -> Tuple[str, str, str, List[str]]:
    """Classify tweet text and build the final merged tag list.

    Returns (folder, tags_str, linked_text, linked_urls):
      folder      — matched category name (or default)
      tags_str    — comma-separated merged tag string for frontmatter
      linked_text — tweet text with wikilinks applied
      linked_urls — list of external URLs extracted from text
    """
    folder, category_tags = classify_tweet(text, cfg["categories"], cfg["default_category"])
    linked_text = apply_wikilinks(text, cfg["wikilinks"])
    linked_urls = extract_linked_urls(text)
    all_tags = cfg["base_tags"] + [t for t in category_tags if t not in cfg["base_tags"]]
    tags_str = ", ".join(all_tags)
    return folder, tags_str, linked_text, linked_urls


def _build_frontmatter(tags_str: str, today: str, url: str, author_str: str, tweet_date: str, cfg: Dict[str, Any]) -> str:
    """Render the YAML frontmatter block (including closing ---)."""
    return (
        f"---\n"
        f"tags: [{tags_str}]\n"
        f"created: {today}\n"
        f'source: "{url}"\n'
        f'author: "{author_str}"\n'
        f"tweet_date: {tweet_date}\n"
        f"distillation: {cfg['distillation_start']}\n"
        f"---\n\n"
    )


def _format_engagement(tweet: Dict[str, Any]) -> str:
    """Build the engagement stats string from tweet metrics."""
    replies   = tweet.get("replies", 0)
    retweets  = tweet.get("retweets", 0)
    likes     = tweet.get("likes", 0)
    views     = tweet.get("views", 0)
    bookmarks = tweet.get("bookmarks", 0)
    media_types: List[str] = []
    for item in (tweet.get("media") or {}).get("all", []):
        mt = item.get("type", "")
        if mt and mt not in media_types:
            media_types.append(mt)
    media_line = f"\n**Media:** {', '.join(media_types)}" if media_types else ""
    stats = (
        f"\U0001f4ac {fmt_number(replies)} \u00b7 "
        f"\U0001f501 {fmt_number(retweets)} \u00b7 "
        f"\u2764\ufe0f {fmt_number(likes)} \u00b7 "
        f"\U0001f441 {fmt_number(views)} \u00b7 "
        f"\U0001f516 {fmt_number(bookmarks)}"
    )
    return f"\n{stats}{media_line}\n"


def _build_quote_section(quote: Optional[Dict[str, Any]]) -> str:
    """Render a quoted tweet as a Markdown blockquote section."""
    if not quote:
        return ""
    q_author  = quote.get("author", {})
    q_name    = q_author.get("screen_name", "unknown")
    q_display = q_author.get("name", q_name)
    q_body    = quote.get("text", "").strip().replace("\n", "\n> ")
    q_url     = quote.get("url", "")
    return f"\n## Quoted Tweet\n\n> **@{q_name}** ({q_display}):\n> {q_body}\n>\n> Source: {q_url}\n"


def _build_article_section(article: Optional[Dict[str, Any]]) -> str:
    """Render an X Article's text blocks as a Markdown section."""
    if not article:
        return ""
    blocks = (article.get("content") or {}).get("blocks", [])
    if not blocks:
        return ""
    article_text = "\n\n".join(b.get("text", "") for b in blocks if b.get("text"))
    return f"\n## Article Content\n\n{article_text}\n"


def generate_from_json(data_file: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Generate note from FxTwitter JSON data."""
    path = Path(data_file)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {data_file}: {e}") from e

    tweet = data.get("tweet", {})
    if not isinstance(tweet, dict):
        raise ValueError(
            f"Invalid response: 'tweet' field must be a dict, got {type(tweet).__name__}"
        )
    text = tweet.get("text", "").strip()
    author = tweet.get("author", {})
    screen_name = author.get("screen_name", "unknown")
    display_name = author.get("name", screen_name)
    created_at = tweet.get("created_at", "")
    url = tweet.get("url", "")
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        tweet_date = dt.strftime("%Y-%m-%d")
        display_date = dt.strftime("%b %d, %Y")
    except Exception:
        print(
            f"Warning: cannot parse tweet date {created_at!r}, using today's date",
            file=sys.stderr,
        )
        tweet_date = display_date = datetime.now().strftime("%Y-%m-%d")

    title = extract_title(text, screen_name)
    folder, tags_str, linked_text, linked_urls = _classify_and_tag(text, cfg)
    today = datetime.now().strftime("%Y-%m-%d")

    engagement_line = _format_engagement(tweet) if cfg["include_engagement"] else ""
    quote_section   = _build_quote_section(tweet.get("quote"))
    article_section = _build_article_section(tweet.get("article"))
    my_notes        = "\n## My Notes\n\n-\n" if cfg["include_my_notes"] else ""

    note = (
        _build_frontmatter(tags_str, today, url, f"@{screen_name} ({display_name})", tweet_date, cfg)
        + f"# {title}\n\n"
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


def generate_from_markdown(data_file: str, cfg: Dict[str, Any], tweet_url: Optional[str]) -> Dict[str, Any]:
    """Generate note from Jina Reader markdown (Tier 2 fallback)."""
    path = Path(data_file)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")
    with open(path) as f:
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
    folder, tags_str, linked_text, linked_urls = _classify_and_tag(text, cfg)
    today = datetime.now().strftime("%Y-%m-%d")
    url = tweet_url or ""

    my_notes = "\n## My Notes\n\n-\n" if cfg["include_my_notes"] else ""

    note = (
        _build_frontmatter(tags_str, today, url, f"@{screen_name}", today, cfg)
        + f"# {title}\n\n"
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
    except (FileNotFoundError, ValueError) as e:
        print(f"Error generating note ({type(e).__name__}): {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
