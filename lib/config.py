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
    return str(Path(path).expanduser())


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


def _validate(cfg: dict, config_path: str) -> None:
    """Validate config values and raise ValueError with clear messages."""
    errors = []

    # vault.path is required and must not be empty after expansion
    if not cfg.get("vault_path"):
        errors.append("vault.path is required and cannot be empty")

    # batch_size must be a positive integer
    bs = cfg.get("batch_size", 0)
    if not isinstance(bs, int) or bs < 1:
        errors.append(f"processing.batch_size must be a positive integer (got {bs!r})")

    # batch_delay must be non-negative
    bd = cfg.get("batch_delay", 0)
    if not isinstance(bd, (int, float)) or bd < 0:
        errors.append(f"processing.batch_delay_seconds must be >= 0 (got {bd!r})")

    # max_links_per_note must be 0–20
    ml = cfg.get("max_links_per_note", 0)
    if not isinstance(ml, int) or ml < 0 or ml > 20:
        errors.append(f"enrichment.max_links_per_note must be 0–20 (got {ml!r})")

    # categories must be a list of dicts with 'name' and 'keywords' keys
    for i, cat in enumerate(cfg.get("categories", [])):
        if not isinstance(cat, dict):
            errors.append(f"categories[{i}] must be a mapping with 'name' and 'keywords'")
            continue
        if not cat.get("name"):
            errors.append(f"categories[{i}].name is required and cannot be empty")
        kws = cat.get("keywords", [])
        if not isinstance(kws, list):
            errors.append(f"categories[{i}].keywords must be a list")
        cat_tags = cat.get("tags")
        if cat_tags is not None and not isinstance(cat_tags, list):
            errors.append(f"categories[{i}].tags must be a list if provided (got {type(cat_tags).__name__})")

    if errors:
        msg = "\n".join(f"  - {e}" for e in errors)
        print(
            f"Error: Invalid config ({config_path}):\n{msg}",
            file=sys.stderr,
        )
        sys.exit(1)


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

    # Safe int/float conversion with fallback and error capture
    try:
        batch_size = int(processing.get("batch_size", 10))
    except (ValueError, TypeError):
        batch_size = -1  # will fail validation

    try:
        batch_delay = float(processing.get("batch_delay_seconds", 2))
    except (ValueError, TypeError):
        batch_delay = -1.0  # will fail validation

    try:
        max_links = int(enrichment.get("max_links_per_note", 3))
    except (ValueError, TypeError):
        max_links = -1  # will fail validation

    try:
        distillation_start = int(template.get("distillation_start", 0))
    except (ValueError, TypeError):
        distillation_start = 0

    cfg = {
        # Vault
        "vault_path":        _expand(vault.get("path", "~/Documents/ObsidianVault")),
        "notes_folder":      vault.get("notes_folder", "Resources"),
        "default_category":  vault.get("default_category", "Inbox"),
        # Bookmarks
        "bookmarks_dir":     bookmarks_dir,
        "bookmarks_file":    os.path.join(bookmarks_dir, bookmarks_file),
        "processed_file":    os.path.join(bookmarks_dir, processed_file),
        # Processing
        "batch_size":        batch_size,
        "batch_delay":       batch_delay,
        # Enrichment
        "enrichment_enabled":   bool(enrichment.get("enabled", True)),
        "max_links_per_note":   max_links,
        # Categories: list of {"name": str, "keywords": [str]}
        "categories":        categories,
        # Wikilinks: list of {"entity": str, "target": str}
        "wikilinks":         wikilinks,
        # Template
        "base_tags":              base_tags,
        "include_engagement":     bool(template.get("include_engagement", True)),
        "include_my_notes":       bool(template.get("include_my_notes", True)),
        "distillation_start":     distillation_start,
    }

    _validate(cfg, config_path)
    return cfg


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
