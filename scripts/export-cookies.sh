#!/usr/bin/env bash
set -euo pipefail

# bookmark-to-obsidian: Chrome Cookie Export
#
# Opens a browser window for you to log in to X.com, then saves the session
# cookies to cookies.json for use with Playwright automated extraction.
#
# Usage:
#   ./scripts/export-cookies.sh [--output <path>]
#
# Requires: Node.js + Playwright (npm install)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
OUTPUT_FILE="${1:-}"

# ── Parse args ────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

OUTPUT_FILE="${OUTPUT_FILE:-$PROJECT_DIR/cookies.json}"

# ── Check Playwright ──────────────────────────────────────
if ! command -v node &>/dev/null; then
  echo "Error: Node.js not found." >&2
  echo "Install: https://nodejs.org" >&2
  exit 1
fi

if ! node -e "require('playwright')" 2>/dev/null; then
  echo "Error: Playwright not installed." >&2
  echo "Run: npm install (in the bookmark-to-obsidian directory)" >&2
  exit 1
fi

echo ""
echo "══════════════════════════════════════════"
echo "  bookmark-to-obsidian — Cookie Export"
echo "══════════════════════════════════════════"
echo ""
echo "A browser window will open. Log in to X.com."
echo "Cookies are saved automatically after you reach the bookmarks page."
echo ""

node - "$OUTPUT_FILE" << 'JSEOF'
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [,, outfile] = process.argv;

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('[Cookie Export] Opening X.com...');
  await page.goto('https://x.com/login', { waitUntil: 'domcontentloaded' });

  console.log('[Cookie Export] Log in, then navigate to Bookmarks.');
  console.log('[Cookie Export] Waiting for bookmarks page (up to 2 minutes)...');

  try {
    // Wait until the user lands on the bookmarks page
    await page.waitForURL('**/i/bookmarks**', { timeout: 120000 });

    const cookies = await context.cookies();
    fs.writeFileSync(outfile, JSON.stringify(cookies, null, 2));
    console.log(`\n[Cookie Export] Saved ${cookies.length} cookies to ${outfile}`);
    console.log('[Cookie Export] Done. You can now run: ./bookmark-to-obsidian extract');

  } catch (e) {
    console.error('\n[Cookie Export] Timed out waiting for bookmarks page.');
    console.error('[Cookie Export] Try again and navigate to x.com/i/bookmarks after logging in.');
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
JSEOF

echo ""
echo "Cookie export complete. Run: ./bookmark-to-obsidian extract"
echo "Cookies are stored at: $OUTPUT_FILE"
echo ""
echo "Note: Refresh cookies if extraction fails after ~2 weeks."
