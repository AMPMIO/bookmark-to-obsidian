"""
bookmark-to-obsidian config loader.

Reads config.yaml and returns a flat dict of resolved values.
Used by note-generator.py and the embedded Python in process-bookmarks.sh.

Usage:
  import sys, os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
  from config import load_config
  cfg = load_config()  # reads T2O_CONFIG env var or finds config.yaml
"""

import json
import os
import sys
from pathlib import Path


def _expand(path: str) -> str:
    return str(Path(os.path.expanduser(path)).expanduser())


def _parse_wikilinks(raw) -> list:
    """Parse wikilinks from either dict or list format.

    Dict format (new):
      wikilinks:
        "React": "[[React Notes]]"
        "TypeScript": "[[TypeScript]]"

    List format (legacy):
      wikilinks:
        - entity: "React"
          target: "[[React Notes]]"  # optional
        - entity: "TypeScript"
    """
    if isinstance(raw, dict):
        return [
            {"entity": k, "target": v or f"[[{k}]]"}
            for k, v in raw.items()
            if k
        ]
    elif isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, dict):
                entity = item.get("entity", "")
                target = item.get("target", f"[[{entity}]]" if entity else "")
                if entity:
                    result.append({"entity": entity, "target": target})
            elif isinstance(item, str) and item:
                result.append({"entity": item, "target": f"[[{item}]]"})
        return result
    return []


def load_config(config_path: str = None) -> dict:
    """Load and return the resolved config as a flat dict."""
    if config_path is None:
        config_path = os.environ.get("T2O_CONFIG")
    if config_path is None:
        here = Path(__file__).resolve().parent
        for candidate in [here.parent / "config.yaml", Path("config.yaml")]:
            if candidate.exists():
                config_path = str(candidate)
                break
    if config_path is None or not Path(config_path).exists():
        print(
            "Error: config.yaml not found. Run setup.sh first, or set T2O_CONFIG.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print(
            "Error: PyYAML not installed. Run: pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    vault      = raw.get("vault", {})
    bookmarks  = raw.get("bookmarks", {})
    processing = raw.get("processing", {})
    template   = raw.get("template", {})
    enrichment = raw.get("enrichment", {})

    bookmarks_dir   = _expand(bookmarks.get("dir", "~/Documents/twitter-bookmarks"))
    bookmarks_file  = bookmarks.get("file", "bookmarks.txt")
    processed_file  = bookmarks.get("processed_file", "bookmarks-processed.txt")

    categories = raw.get("categories", [])
    wikilinks  = _parse_wikilinks(raw.get("wikilinks") or [])
    base_tags  = template.get("base_tags", ["type/tweet", "source/twitter"])

    return {
        # Vault
        "vault_path":        _expand(vault.get("path", "~/Documents/ObsidianVault")),
        "notes_folder":      vault.get("notes_folder", "Resources"),
        "default_category":  vault.get("default_category", "Inbox"),
        # Bookmarks
        "bookmarks_dir":     bookmarks_dir,
        "bookmarks_file":    os.path.join(bookmarks_dir, bookmarks_file),
        "processed_file":    os.path.join(bookmarks_dir, processed_file),
        # Processing
        "batch_size":        int(processing.get("batch_size", 10)),
        "batch_delay":       float(processing.get("batch_delay_seconds", 2)),
        # Enrichment
        "enrichment_enabled":   bool(enrichment.get("enabled", True)),
        "max_links_per_note":   int(enrichment.get("max_links_per_note", 3)),
        # Categories: list of {"name": str, "keywords": [str]}
        "categories":        categories,
        # Wikilinks: list of {"entity": str, "target": str}
        "wikilinks":         wikilinks,
        # Template
        "base_tags":              base_tags,
        "include_engagement":     bool(template.get("include_engagement", True)),
        "include_my_notes":       bool(template.get("include_my_notes", True)),
        "distillation_start":     int(template.get("distillation_start", 0)),
    }


def export_for_shell(config_path: str = None):
    """Print config as shell variable assignments (used by config.sh)."""
    cfg = load_config(config_path)

    vault_root = os.path.join(cfg["vault_path"], cfg["notes_folder"])

    print(f'VAULT_ROOT={json.dumps(vault_root)}')
    print(f'NOTES_FOLDER={json.dumps(cfg["notes_folder"])}')
    print(f'DEFAULT_CATEGORY={json.dumps(cfg["default_category"])}')
    print(f'BOOKMARKS_FILE={json.dumps(cfg["bookmarks_file"])}')
    print(f'PROCESSED_FILE={json.dumps(cfg["processed_file"])}')
    print(f'BATCH_SIZE={cfg["batch_size"]}')
    print(f'BATCH_DELAY={cfg["batch_delay"]}')
    print(f'CATEGORIES_JSON={json.dumps(json.dumps(cfg["categories"]))}')
    print(f'WIKILINKS_JSON={json.dumps(json.dumps(cfg["wikilinks"]))}')
    enrich = "true" if cfg["enrichment_enabled"] else "false"
    print(f'ENRICHMENT_ENABLED={enrich}')
    print(f'MAX_LINKS_PER_NOTE={cfg["max_links_per_note"]}')


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    export_for_shell(config_path)
