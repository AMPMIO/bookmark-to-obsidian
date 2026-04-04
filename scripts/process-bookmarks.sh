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

# Normalize a tweet URL: twitter.com → x.com, strip whitespace
normalize_url() {
  echo "$1" | sed 's|twitter\.com|x.com|g' | tr -d '[:space:]'
}

# Build set of known vault URLs, normalized for comparison
build_known_urls() {
  grep -rh "^source:" "$VAULT_ROOT" 2>/dev/null \
    | sed "s/source: *[\"']*//;s/[\"']*$//" \
    | sed 's|twitter\.com|x.com|g' \
    | tr -d '[:space:]' \
    | sort -u || true
}

sanitize_filename() {
  echo "$1" | sed 's/[\/\\:*?"<>|]/-/g' | sed 's/  */ /g' | cut -c1-80
}

# Safe mktemp with explicit error
safe_mktemp() {
  local f
  f=$(mktemp) || { warn "mktemp failed — /tmp may be full"; return 1; }
  echo "$f"
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
  tmpdata=$(safe_mktemp) || return 1

  if ! fetch_tweet_data "$url" "$tmpdata"; then
    warn "[$index/$total] All tiers failed: $url"
    rm -f "$tmpdata"
    return 1
  fi

  # Build note-generator.py args
  local gen_args=("$tmpdata" "--config" "$CONFIG_PATH" "--format" "$FETCH_FMT")
  [ "$FETCH_FMT" = "markdown" ] && gen_args+=("--url" "$url")

  local note_json
  note_json=$(python3 "$LIB_DIR/note-generator.py" "${gen_args[@]}" 2>&1) || {
    warn "[$index/$total] Note generation failed: $url"
    warn "  Detail: $note_json"
    rm -f "$tmpdata"
    return 1
  }

  rm -f "$tmpdata"

  # Parse and validate note-generator output, then extract all fields in one Python call
  local parsed
  parsed=$(echo "$note_json" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    title = d.get("title", "").strip()
    folder = d.get("folder", "").strip()
    note = d.get("note", "").strip()
    linked = d.get("linked_urls", [])
    if not title or not folder or not note:
        print("ERROR: missing required field in note-generator output", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"title": title, "folder": folder, "note": note, "linked_urls": linked}))
except (json.JSONDecodeError, KeyError) as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
') || {
    warn "[$index/$total] Failed to parse note output: $url"
    return 1
  }

  # Extract all fields in a single Python call using base64 to safely handle multi-line note
  local _b64 title folder note linked_urls_json
  _b64=$(echo "$parsed" | python3 -c '
import json, sys, base64
d = json.load(sys.stdin)
for val in [d["title"], d["folder"], d["note"], json.dumps(d["linked_urls"])]:
    print(base64.b64encode(val.encode()).decode())
')
  title=$(echo "$_b64"          | sed -n '1p' | base64 -d)
  folder=$(echo "$_b64"         | sed -n '2p' | base64 -d)
  note=$(echo "$_b64"           | sed -n '3p' | base64 -d)
  linked_urls_json=$(echo "$_b64" | sed -n '4p' | base64 -d)

  # Validate extracted fields
  if [ -z "$title" ] || [ -z "$folder" ]; then
    warn "[$index/$total] Empty title or folder for: $url"
    return 1
  fi

  # Write note to vault
  local safe_title folder_path filepath
  safe_title=$(sanitize_filename "$title")
  folder_path="$VAULT_ROOT/$folder"

  # Ensure folder path is not empty before creating
  if [ -z "$folder_path" ] || [ "$folder_path" = "/" ]; then
    warn "[$index/$total] Invalid folder path for: $url"
    return 1
  fi

  mkdir -p "$folder_path" || {
    warn "[$index/$total] Failed to create folder: $folder_path"
    return 1
  }
  filepath="$folder_path/${safe_title}.md"

  if [ -f "$filepath" ]; then
    warn "[$index/$total] Already exists: $folder/${safe_title}.md"
    return 0
  fi

  printf "%s" "$note" > "$filepath" || {
    warn "[$index/$total] Failed to write note: $filepath"
    return 1
  }
  log "[$index/$total] -> $folder/${safe_title}.md"

  # ── Enrichment ─────────────────────────────────────────
  if [ "$NO_ENRICH" = false ] && [ "${ENRICHMENT_ENABLED:-true}" = "true" ]; then
    local max_links="${MAX_LINKS_PER_NOTE:-3}"
    local enrich_count=0
    local enrich_added=false

    local url_list
    url_list=$(echo "$linked_urls_json" | python3 -c \
      "import json,sys; [print(u) for u in json.load(sys.stdin)]" 2>/dev/null) || url_list=""

    if [ -n "$url_list" ]; then
      while IFS= read -r lurl && [ $enrich_count -lt "$max_links" ]; do
        [ -z "$lurl" ] && continue
        local etmp
        etmp=$(safe_mktemp) || continue
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
  fi
}

# ── Main ─────────────────────────────────────────────────
main() {
  if [ ! -f "$BOOKMARKS_FILE" ]; then
    echo "Error: Bookmarks file not found: $BOOKMARKS_FILE" >&2
    echo "Add tweet URLs (one per line) to that file, then re-run." >&2
    exit 1
  fi

  # Ensure processed file's parent directory exists
  mkdir -p "$(dirname "$PROCESSED_FILE")" || {
    echo "Error: Cannot create directory for processed file: $PROCESSED_FILE" >&2
    exit 1
  }

  log "Loading bookmarks from: $BOOKMARKS_FILE"
  log "Vault: $VAULT_ROOT"

  local known_urls
  known_urls=$(build_known_urls)

  local urls=() skipped=0
  while IFS= read -r url || [ -n "$url" ]; do
    [[ -z "$url" || "$url" == \#* ]] && continue
    url=$(normalize_url "$url")
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
    tmpf=$(safe_mktemp) || { warn "Cannot clean bookmarks.txt — mktemp failed"; return 0; }
    while IFS= read -r url || [ -n "$url" ]; do
      [[ -z "$url" || "$url" == \#* ]] && { echo "$url" >> "$tmpf"; continue; }
      local norm
      norm=$(normalize_url "$url")
      if ! grep -qF "$norm" "$PROCESSED_FILE" 2>/dev/null; then
        echo "$url" >> "$tmpf"
      fi
    done < "$BOOKMARKS_FILE"
    mv "$tmpf" "$BOOKMARKS_FILE"
    log "Cleaned processed URLs from $(basename "$BOOKMARKS_FILE")"
  fi
}

main "$@"
