#!/usr/bin/env bash
set -euo pipefail

# bookmark-to-obsidian — Turn Twitter/X bookmarks into Obsidian vault notes
#
# Usage:
#   ./bookmark-to-obsidian [setup|extract|process|cookies|run]
#
#   setup    — Interactive first-run configuration
#   extract  — Pull bookmark URLs from Twitter (auto if cookies.json exists)
#   process  — Process URLs into Obsidian notes
#   cookies  — Export Chrome session cookies for automated extraction
#   run      — Full pipeline: extract + process [default]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"
COOKIES_FILE="$SCRIPT_DIR/cookies.json"

# ── Load config (skip for setup and cookies subcommands) ──
load_if_needed() {
  local cmd="${1:-}"
  if [[ "$cmd" != "setup" && "$cmd" != "cookies" ]]; then
    if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
      echo "Error: config.yaml not found." >&2
      echo "Run: ./bookmark-to-obsidian setup" >&2
      exit 1
    fi
    # shellcheck source=lib/config.sh
    source "$LIB_DIR/config.sh"
    load_config "$SCRIPT_DIR/config.yaml"
  fi
}

CMD="${1:-run}"
shift || true

case "$CMD" in

  # ── Setup ───────────────────────────────────────────────
  setup)
    exec "$SCRIPT_DIR/setup.sh" "$@"
    ;;

  # ── Cookie export ────────────────────────────────────────
  cookies)
    exec "$SCRIPT_DIR/scripts/export-cookies.sh" --output "$COOKIES_FILE" "$@"
    ;;

  # ── Extract bookmark URLs ────────────────────────────────
  extract)
    load_if_needed "extract"

    if [ -f "$COOKIES_FILE" ]; then
      echo "[bookmark-to-obsidian] Automated extraction via Playwright..."

      # Check Playwright available
      if ! command -v node &>/dev/null || ! node -e "require('playwright')" 2>/dev/null; then
        echo "Warning: Playwright not available. Falling back to manual mode." >&2
        echo "Run: npm install  to enable automated extraction." >&2
        exec "$SCRIPT_DIR/scripts/extract-bookmarks-manual.sh" "$@"
      fi

      node "$SCRIPT_DIR/scripts/extract-bookmarks.js" \
        --cookies "$COOKIES_FILE" \
        --vault   "$VAULT_ROOT" \
        --output  "$BOOKMARKS_FILE" \
        "$@"
    else
      echo "[bookmark-to-obsidian] No cookies.json found — using manual browser console mode."
      echo "[bookmark-to-obsidian] Tip: run './bookmark-to-obsidian cookies' for fully automated extraction."
      echo ""
      exec "$SCRIPT_DIR/scripts/extract-bookmarks-manual.sh" "$@"
    fi
    ;;

  # ── Process URLs into notes ──────────────────────────────
  process)
    load_if_needed "process"
    exec "$SCRIPT_DIR/scripts/process-bookmarks.sh" \
      --config "$SCRIPT_DIR/config.yaml" "$@"
    ;;

  # ── Full pipeline ────────────────────────────────────────
  run|"")
    load_if_needed "run"
    "$0" extract
    "$0" process
    ;;

  # ── Help ─────────────────────────────────────────────────
  help|--help|-h)
    cat << 'HELP'
bookmark-to-obsidian — Turn Twitter/X bookmarks into Obsidian vault notes

Usage: ./bookmark-to-obsidian [command]

Commands:
  run      Full pipeline: extract + process [default]
  setup    Interactive first-run configuration
  extract  Pull bookmark URLs from Twitter
           • Automated if cookies.json exists (via Playwright)
           • Falls back to manual browser console mode
  process  Process URLs from bookmarks.txt into Obsidian notes
  cookies  Export Chrome session cookies for automated extraction

Options for extract/process:
  --config <path>   Use an alternate config file

Examples:
  ./bookmark-to-obsidian              # Full pipeline (most common)
  ./bookmark-to-obsidian setup        # First-time setup
  ./bookmark-to-obsidian cookies      # Set up automated extraction
  ./bookmark-to-obsidian extract      # Just extract URLs
  ./bookmark-to-obsidian process      # Just process URLs
HELP
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Run: ./bookmark-to-obsidian --help" >&2
    exit 1
    ;;

esac
