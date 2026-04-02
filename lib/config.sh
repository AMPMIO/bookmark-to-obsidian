#!/usr/bin/env bash
# bookmark-to-obsidian config loader
# Sources this file from other scripts to export config as shell variables.
#
# Usage:
#   source "$(dirname "$0")/../lib/config.sh"          # auto-finds config.yaml
#   source "$(dirname "$0")/../lib/config.sh" "/path/to/config.yaml"
#
# Variables exported:
#   VAULT_ROOT, NOTES_FOLDER, DEFAULT_CATEGORY
#   BOOKMARKS_FILE, PROCESSED_FILE
#   BATCH_SIZE, BATCH_DELAY
#   CATEGORIES_JSON, WIKILINKS_JSON

load_config() {
  local config_path="${1:-}"
  local lib_dir
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  # Resolve config file path
  if [ -z "$config_path" ]; then
    config_path="${T2O_CONFIG:-}"
  fi
  if [ -z "$config_path" ]; then
    # Look for config.yaml next to lib/ (project root)
    local project_root
    project_root="$(dirname "$lib_dir")"
    if [ -f "$project_root/config.yaml" ]; then
      config_path="$project_root/config.yaml"
    fi
  fi
  if [ -z "$config_path" ] || [ ! -f "$config_path" ]; then
    echo "Error: config.yaml not found. Run setup.sh first, or set T2O_CONFIG." >&2
    echo "Hint: copy config.example.yaml to config.yaml and fill in your vault path." >&2
    return 1
  fi

  # Use Python to parse YAML and export shell variables
  local exports
  exports=$(python3 "$lib_dir/config.py" "$config_path" 2>&1) || {
    echo "$exports" >&2
    return 1
  }

  # eval the exported variable assignments
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    # Each line is VAR="value" — safe to eval since we control config.py output
    eval "export $line"
  done <<< "$exports"
}
