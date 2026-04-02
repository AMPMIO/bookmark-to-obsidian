#!/usr/bin/env bash
# Tier 3: Fetch tweet via Playwright (headless Chromium, optional cookies)
#
# Source this file and call tier3_fetch:
#   source lib/tier3-playwright.sh
#   tier3_fetch <tweet-url> <output-file> [<cookies-file>]
#
# Returns 0 on success (FxTwitter-compatible JSON written to output-file), 1 on failure.
# Requires: Node.js + Playwright (npm install in project root)

tier3_fetch() {
  local url="$1" outfile="$2" cookies_file="${3:-}"

  if ! command -v node &>/dev/null; then
    echo "tier3: Node.js not found" >&2
    return 1
  fi

  if ! node -e "require('playwright')" 2>/dev/null; then
    echo "tier3: Playwright not installed. Run: npm install" >&2
    return 1
  fi

  node - "$url" "$outfile" "$cookies_file" << 'JSEOF'
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [,, url, outfile, cookiesFile] = process.argv;

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });

  if (cookiesFile && fs.existsSync(cookiesFile)) {
    try {
      const cookies = JSON.parse(fs.readFileSync(cookiesFile, 'utf-8'));
      await context.addCookies(cookies);
    } catch (e) {
      console.error('tier3: Could not load cookies:', e.message);
    }
  }

  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Extract tweet text from DOM
    const tweetText = await page.$eval(
      '[data-testid="tweetText"]',
      el => el.innerText
    ).catch(() => null);

    if (!tweetText) {
      console.error('tier3: Could not extract tweet text from DOM');
      process.exit(1);
    }

    // Extract author display name
    const displayName = await page.$eval(
      '[data-testid="User-Name"] span span',
      el => el.innerText
    ).catch(() => '');

    const username = (url.match(/(?:x\.com|twitter\.com)\/([^/]+)\/status\//) || [])[1] || 'unknown';

    const result = {
      tweet: {
        url: url,
        text: tweetText,
        author: {
          screen_name: username,
          name: displayName || username,
        },
        created_at: '',
        likes: 0,
        retweets: 0,
        replies: 0,
        views: 0,
        bookmarks: 0,
      }
    };

    fs.writeFileSync(outfile, JSON.stringify(result));
    process.exit(0);

  } catch (e) {
    console.error('tier3: Error:', e.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
JSEOF
}
