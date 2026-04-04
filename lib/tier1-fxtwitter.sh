#!/usr/bin/env bash
# Tier 1: Fetch tweet via FxTwitter API (no authentication required)
#
# Source this file and call tier1_fetch:
#   source lib/tier1-fxtwitter.sh
#   tier1_fetch <tweet-url> <output-file>
#
# Returns 0 on success (JSON written to output-file), 1 on failure.

tier1_fetch() {
  local url="$1" outfile="$2"
  local username tweet_id response code

  username=$(echo "$url" | sed -E 's|https?://[^/]+/([^/]+)/status/[0-9]+.*|\1|')
  tweet_id=$(echo "$url"  | sed -E 's|https?://[^/]+/[^/]+/status/([0-9]+).*|\1|')

  # Validate parsed values look like a username and numeric tweet ID
  if [ -z "$username" ] || [ -z "$tweet_id" ]; then
    echo "tier1: Could not parse URL: $url" >&2
    return 1
  fi
  if ! echo "$tweet_id" | grep -qE '^[0-9]+$'; then
    echo "tier1: Tweet ID is not numeric in URL: $url" >&2
    return 1
  fi

  response=$(curl -sf --max-time 15 \
    "https://api.fxtwitter.com/${username}/status/${tweet_id}" 2>/dev/null) || return 1

  [ -z "$response" ] && return 1

  # Verify response is valid JSON with a tweet object
  if ! echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'tweet' in d" \
      2>/dev/null; then
    # Could be an error response — extract code if present
    code=$(echo "$response" | python3 -c \
      "import json,sys; print(json.load(sys.stdin).get('code','unknown'))" 2>/dev/null || echo "unknown")
    echo "tier1: FxTwitter returned no tweet data (code=$code) for: $url" >&2
    return 1
  fi

  echo "$response" > "$outfile"
  return 0
}
