#!/usr/bin/env bash
set -euo pipefail

# bookmark-to-obsidian: Manual Bookmark Extractor Launcher (browser console version)
#
# Step 1 (default): Reads known URLs from vault, injects them into the JS
#   extractor, and copies the ready-to-paste script to clipboard.
#
# Step 2 (--save): Reads tweet URLs from clipboard and saves to bookmarks.txt.
#
# Usage:
#   ./scripts/extract-bookmarks-manual.sh [--config path/to/config.yaml]
#   ./scripts/extract-bookmarks-manual.sh --save [--config path/to/config.yaml]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
JS_TEMPLATE="$SCRIPT_DIR/extract-bookmarks-manual.js"

# ── Parse arguments ───────────────────────────────────────
CONFIG_PATH=""
SAVE_MODE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_PATH="$2"; shift 2 ;;
    --save)   SAVE_MODE=true; shift ;;
    *) shift ;;
  esac
done

# ── Load config ───────────────────────────────────────────
# shellcheck source=../lib/config.sh
source "$LIB_DIR/config.sh"
load_config "$CONFIG_PATH"

# ── Step 1: Generate and copy extractor ───────────────────
if [ "$SAVE_MODE" = false ]; then
  echo "Reading known URLs from vault: $VAULT_ROOT"

  known_urls=$(grep -rh "^source:" "$VAULT_ROOT" 2>/dev/null \
    | sed "s/source: [\"']//;s/[\"']//" \
    | grep -E "x\.com|twitter\.com" \
    | sed 's|twitter\.com|x.com|' \
    | sort -u || true)

  count=$(echo "$known_urls" | grep -c "." 2>/dev/null || echo 0)
  echo "Found $count known URLs in vault."

  # Build JS array
  js_array="["
  first=true
  while IFS= read -r url; do
    [ -z "$url" ] && continue
    url=$(echo "$url" | tr -d '[:space:]')
    if [ "$first" = true ]; then
      js_array+="\"$url\""
      first=false
    else
      js_array+=",\"$url\""
    fi
  done <<< "$known_urls"
  js_array+="]"

  # Inject into JS template
  js_code=$(sed "s|/\*__KNOWN_URLS__\*/\[\]|${js_array}|" "$JS_TEMPLATE")

  # Copy to clipboard
  if command -v pbcopy &>/dev/null; then
    echo "$js_code" | pbcopy
    clipboard_msg="Copied to clipboard (pbcopy)."
  elif command -v xclip &>/dev/null; then
    echo "$js_code" | xclip -selection clipboard
    clipboard_msg="Copied to clipboard (xclip)."
  elif command -v xsel &>/dev/null; then
    echo "$js_code" | xsel --clipboard --input
    clipboard_msg="Copied to clipboard (xsel)."
  else
    echo "$js_code" > /tmp/tweet-extractor.js
    clipboard_msg="Saved to /tmp/tweet-extractor.js (no clipboard tool found)."
  fi

  echo ""
  echo "============================================"
  echo "  Extractor ready! $clipboard_msg"
  echo "  $count known URLs embedded as stop boundary."
  echo "============================================"
  echo ""
  echo "Next steps:"
  echo "  1. Open https://x.com/i/bookmarks in Chrome (while logged in)"
  echo "  2. Open DevTools console: Cmd+Option+J (Mac) or F12 (Windows)"
  echo "  3. Paste the script and press Enter"
  echo "  4. Wait — it will scroll automatically and log progress"
  echo "  5. When done, URLs are auto-copied to your clipboard"
  echo "  6. Run: $(basename "$0") --save"
  echo ""
  exit 0
fi

# ── Step 2: Save clipboard to bookmarks.txt ───────────────
echo "Saving clipboard to: $BOOKMARKS_FILE"
mkdir -p "$(dirname "$BOOKMARKS_FILE")"

if command -v pbpaste &>/dev/null; then
  clipboard=$(pbpaste)
elif command -v xclip &>/dev/null; then
  clipboard=$(xclip -selection clipboard -o)
elif command -v xsel &>/dev/null; then
  clipboard=$(xsel --clipboard --output)
else
  echo "Error: No clipboard tool found (pbpaste/xclip/xsel)." >&2
  exit 1
fi

url_count=$(echo "$clipboard" | grep -cE "x\.com/.*/status/|twitter\.com/.*/status/" || true)
if [ "$url_count" -eq 0 ]; then
  echo "Error: Clipboard doesn't contain tweet URLs." >&2
  echo "Run the extractor in your browser first, then re-run with --save." >&2
  exit 1
fi

# Prepend new URLs to top of file (newest first)
if [ -f "$BOOKMARKS_FILE" ]; then
  existing=$(cat "$BOOKMARKS_FILE")
  { echo "$clipboard"; echo "$existing"; } > "$BOOKMARKS_FILE"
else
  echo "$clipboard" > "$BOOKMARKS_FILE"
fi

echo "Saved $url_count new URLs to $(basename "$BOOKMARKS_FILE")"
echo ""
echo "Next: process them into vault notes:"
echo "  ./bookmark-to-obsidian process"
echo "  # or: ./scripts/process-bookmarks.sh"
