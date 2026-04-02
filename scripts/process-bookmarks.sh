#!/usr/bin/env bash
set -euo pipefail

# bookmark-to-obsidian: Batch Processor
# Reads bookmark URLs, fetches via 3-tier extraction, writes Obsidian vault notes.
#
# Usage:
#   ./scripts/process-bookmarks.sh [bookmarks-file] [--config path] [--no-enrich]
#
# Tiers:
#   1. FxTwitter API  — full structured data, no auth
#   2. Jina Reader    — markdown fallback, no auth
#   3. Playwright     — DOM scrape, requires cookies.json + npm install

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# ── Parse arguments ───────────────────────────────────────
CONFIG_PATH=""
BOOKMARKS_ARG=""
NO_ENRICH=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)    CONFIG_PATH="$2"; shift 2 ;;
    --no-enrich) NO_ENRICH=true; shift ;;
    *)           BOOKMARKS_ARG="$1"; shift ;;
  esac
done

# ── Load config ───────────────────────────────────────────
# shellcheck source=../lib/config.sh
source "$LIB_DIR/config.sh"
load_config "$CONFIG_PATH"

# Source tier fetch libraries
# shellcheck source=../lib/tier1-fxtwitter.sh
source "$LIB_DIR/tier1-fxtwitter.sh"
# shellcheck source=../lib/tier2-jina.sh
source "$LIB_DIR/tier2-jina.sh"
# shellcheck source=../lib/tier3-playwright.sh
source "$LIB_DIR/tier3-playwright.sh"

# Allow bookmarks file override from CLI argument
if [ -n "$BOOKMARKS_ARG" ]; then
  BOOKMARKS_FILE="$BOOKMARKS_ARG"
fi

# Resolve config path for note-generator.py calls
if [ -z "$CONFIG_PATH" ]; then
  CONFIG_PATH="$(dirname "$LIB_DIR")/config.yaml"
fi

# Find cookies.json for Tier 3
COOKIES_FILE=""
if [ -f "$(dirname "$LIB_DIR")/cookies.json" ]; then
  COOKIES_FILE="$(dirname "$LIB_DIR")/cookies.json"
fi

# ── Helpers ───────────────────────────────────────────────
log()  { echo "[$(date +%H:%M:%S)] $*"; }
warn() { echo "[$(date +%H:%M:%S)] WARNING: $*" >&2; }

build_known_urls() {
  grep -rh "^source:" "$VAULT_ROOT" 2>/dev/null \
    | sed "s/source: [\"']//;s/[\"']//" \
    | sort -u || true
}

sanitize_filename() {
  echo "$1" | sed 's/[\/\\:*?"<>|]/-/g' | sed 's/  */ /g' | cut -c1-80
}

# ── Tiered fetch ──────────────────────────────────────────
# Sets FETCH_FMT to "json" or "markdown" on success
FETCH_FMT="json"

fetch_tweet_data() {
  local url="$1" outfile="$2"
  FETCH_FMT="json"

  if tier1_fetch "$url" "$outfile" 2>/dev/null; then
    return 0
  fi

  warn "Tier 1 failed, trying Jina Reader..."
  FETCH_FMT="markdown"
  if tier2_fetch "$url" "$outfile" 2>/dev/null; then
    return 0
  fi

  warn "Tier 2 failed, trying Playwright..."
  FETCH_FMT="json"
  if tier3_fetch "$url" "$outfile" "$COOKIES_FILE" 2>/dev/null; then
    return 0
  fi

  return 1
}

# ── Main tweet processor ──────────────────────────────────
process_tweet() {
  local url="$1" index="$2" total="$3"

  local tmpdata
  tmpdata=$(mktemp)

  if ! fetch_tweet_data "$url" "$tmpdata"; then
    warn "[$index/$total] All tiers failed: $url"
    rm -f "$tmpdata"
    return 1
  fi

  # Build note-generator.py args
  local gen_args=("$tmpdata" "--config" "$CONFIG_PATH" "--format" "$FETCH_FMT")
  [ "$FETCH_FMT" = "markdown" ] && gen_args+=("--url" "$url")

  local note_json
  note_json=$(python3 "$LIB_DIR/note-generator.py" "${gen_args[@]}" 2>/dev/null) || {
    warn "[$index/$total] Note generation failed: $url"
    rm -f "$tmpdata"
    return 1
  }

  rm -f "$tmpdata"

  # Parse note-generator output
  local title folder note linked_urls_json
  title=$(echo "$note_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])")
  folder=$(echo "$note_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['folder'])")
  note=$(echo "$note_json"  | python3 -c "import json,sys; print(json.load(sys.stdin)['note'])")
  linked_urls_json=$(echo "$note_json" | python3 -c \
    "import json,sys; print(json.dumps(json.load(sys.stdin).get('linked_urls',[])))")

  # Write note to vault
  local safe_title folder_path filepath
  safe_title=$(sanitize_filename "$title")
  folder_path="$VAULT_ROOT/$folder"
  mkdir -p "$folder_path"
  filepath="$folder_path/${safe_title}.md"

  if [ -f "$filepath" ]; then
    warn "[$index/$total] Already exists: $folder/${safe_title}.md"
    return 0
  fi

  printf "%s" "$note" > "$filepath"
  log "[$index/$total] -> $folder/${safe_title}.md"

  # ── Enrichment ─────────────────────────────────────────
  if [ "$NO_ENRICH" = false ] && [ "${ENRICHMENT_ENABLED:-true}" = "true" ]; then
    local max_links="${MAX_LINKS_PER_NOTE:-3}"
    local enrich_count=0
    local enrich_added=false

    local url_list
    url_list=$(echo "$linked_urls_json" | python3 -c \
      "import json,sys; [print(u) for u in json.load(sys.stdin)]" 2>/dev/null || true)

    while IFS= read -r lurl && [ $enrich_count -lt "$max_links" ]; do
      [ -z "$lurl" ] && continue
      local etmp
      etmp=$(mktemp)
      if tier2_fetch "$lurl" "$etmp" 2>/dev/null; then
        if [ "$enrich_added" = false ]; then
          printf "\n## Linked Content\n" >> "$filepath"
          enrich_added=true
        fi
        printf "\n### [%s](%s)\n\n" "$lurl" "$lurl" >> "$filepath"
        head -60 "$etmp" >> "$filepath"
        printf "\n" >> "$filepath"
        enrich_count=$((enrich_count + 1))
        log "  enriched: $lurl"
      fi
      rm -f "$etmp"
    done <<< "$url_list"
  fi
}

# ── Main ─────────────────────────────────────────────────
main() {
  if [ ! -f "$BOOKMARKS_FILE" ]; then
    echo "Error: Bookmarks file not found: $BOOKMARKS_FILE" >&2
    echo "Add tweet URLs (one per line) to that file, then re-run." >&2
    exit 1
  fi

  log "Loading bookmarks from: $BOOKMARKS_FILE"
  log "Vault: $VAULT_ROOT"

  local known_urls
  known_urls=$(build_known_urls)

  local urls=() skipped=0
  while IFS= read -r url || [ -n "$url" ]; do
    [[ -z "$url" || "$url" == \#* ]] && continue
    url=$(echo "$url" | sed 's|twitter\.com|x.com|' | tr -d '[:space:]')
    if echo "$known_urls" | grep -qF "$url"; then
      skipped=$((skipped + 1))
      continue
    fi
    urls+=("$url")
  done < "$BOOKMARKS_FILE"

  local total=${#urls[@]}
  log "Found $total new URLs ($skipped already in vault)"

  if [ "$total" -eq 0 ]; then
    log "Nothing to process."
    exit 0
  fi

  local processed=0 failed=0 batch_count=0

  for i in "${!urls[@]}"; do
    local idx=$((i + 1))
    if process_tweet "${urls[$i]}" "$idx" "$total"; then
      echo "${urls[$i]}" >> "$PROCESSED_FILE"
      processed=$((processed + 1))
    else
      failed=$((failed + 1))
    fi

    batch_count=$((batch_count + 1))
    if [ "$batch_count" -ge "$BATCH_SIZE" ] && [ "$idx" -lt "$total" ]; then
      log "Batch of $BATCH_SIZE complete. Pausing ${BATCH_DELAY}s..."
      sleep "$BATCH_DELAY"
      batch_count=0
    fi
  done

  log "Done. Processed: $processed, Failed: $failed, Skipped: $skipped"

  # Cleanup: remove processed URLs from bookmarks.txt
  if [ "$processed" -gt 0 ]; then
    local tmpf
    tmpf=$(mktemp)
    while IFS= read -r url || [ -n "$url" ]; do
      [[ -z "$url" || "$url" == \#* ]] && { echo "$url" >> "$tmpf"; continue; }
      local norm
      norm=$(echo "$url" | sed 's|twitter\.com|x.com|' | tr -d '[:space:]')
      if ! grep -qF "$norm" "$PROCESSED_FILE" 2>/dev/null; then
        echo "$url" >> "$tmpf"
      fi
    done < "$BOOKMARKS_FILE"
    mv "$tmpf" "$BOOKMARKS_FILE"
    log "Cleaned processed URLs from $(basename "$BOOKMARKS_FILE")"
  fi
}

main "$@"
