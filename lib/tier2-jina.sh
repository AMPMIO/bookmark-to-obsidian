#!/usr/bin/env bash
# Tier 2: Fetch content via Jina Reader API (no authentication required)
#
# Source this file and call tier2_fetch:
#   source lib/tier2-jina.sh
#   tier2_fetch <url> <output-file>
#
# Returns 0 on success (markdown written to output-file), 1 on failure.
# Works for any URL: tweet pages, GitHub READMEs, blog posts, etc.
# Used for both Tier 2 tweet fallback and enrichment of linked content.

tier2_fetch() {
  local url="$1" outfile="$2"
  local response

  response=$(curl -sf --max-time 30 \
    -H "Accept: text/markdown" \
    -H "X-Return-Format: markdown" \
    "https://r.jina.ai/${url}" 2>/dev/null) || return 1

  [ -z "$response" ] && return 1

  # Jina returns "Error: ..." lines on failure
  if echo "$response" | head -1 | grep -q "^Error:" 2>/dev/null; then
    echo "tier2: Jina returned error for: $url" >&2
    return 1
  fi

  echo "$response" > "$outfile"
  return 0
}
