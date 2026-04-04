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
#
# Retries once on transient network failure (timeout or empty response).

JINA_MAX_RETRIES=2

tier2_fetch() {
  local url="$1" outfile="$2"
  local response attempt=1

  while [ $attempt -le $JINA_MAX_RETRIES ]; do
    response=$(curl -sf --max-time 30 \
      -H "Accept: text/markdown" \
      -H "X-Return-Format: markdown" \
      "https://r.jina.ai/${url}" 2>/dev/null)
    local exit_code=$?

    # Success: got a non-empty response that doesn't start with "Error:"
    if [ $exit_code -eq 0 ] && [ -n "$response" ]; then
      if ! echo "$response" | head -1 | grep -q "^Error:" 2>/dev/null; then
        echo "$response" > "$outfile"
        return 0
      fi
      # Jina returned an application-level error — no point retrying
      echo "tier2: Jina returned error for: $url" >&2
      return 1
    fi

    # Transient failure (timeout = exit 28, connection error = exit 6/7)
    if [ $attempt -lt $JINA_MAX_RETRIES ]; then
      echo "tier2: Attempt $attempt failed (curl exit=$exit_code), retrying..." >&2
      sleep 2
    fi
    attempt=$((attempt + 1))
  done

  echo "tier2: All attempts failed for: $url" >&2
  return 1
}
