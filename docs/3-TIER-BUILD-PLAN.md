# 3-Tier Twitter Scraping Architecture — Build Plan

## Overview

Apply Cairn's 3-tier web scraping pattern to the tweet-to-obsidian pipeline.
Each tier is a fallback for the one above it. The pipeline tries Tier 1 first,
falls back to Tier 2 on failure, then Tier 3 as last resort.

## The Three Tiers

### Tier 1: FxTwitter API (curl) — Current System
**Speed:** ~200ms per tweet | **Auth:** None | **Reliability:** High

What we have now. `curl https://api.fxtwitter.com/{user}/status/{id}`
Returns structured JSON with full tweet content, engagement, quotes, articles.

**When it works:** Any public tweet URL (95% of cases).
**When it fails:** FxTwitter is down, tweet is protected/deleted, rate limited.

### Tier 2: Jina Reader API — New, For Enrichment + Fallback
**Speed:** ~1-2s per URL | **Auth:** Optional (free tier works) | **Reliability:** High

`curl https://r.jina.ai/https://x.com/user/status/123` returns clean markdown.
Also works for ANY URL — GitHub READMEs, blog posts, articles linked in tweets.

**Use cases:**
- Fallback when FxTwitter returns 404/error
- Enrich tweet notes by fetching linked GitHub repos, blog posts, documentation
- Resolve t.co shortened URLs and fetch the actual content

**When it fails:** Jina is down, URL is behind auth, very heavy JS-rendered pages.

### Tier 3: Playwright Headless Browser — New, For Auth + Ultimate Fallback
**Speed:** ~3-5s per page | **Auth:** Uses saved session cookies | **Reliability:** Highest

Full headless Chrome via Playwright. Can do everything a human browser can.

**Use cases:**
- **Bookmark extraction** (replaces the manual console-paste workflow entirely)
- Fallback when both FxTwitter and Jina fail
- Future: scrape Twitter lists, search results, specific user timelines
- Future: could run on Cairn's VPS for remote/scheduled scraping

**When it fails:** Session cookies expired (re-export needed).

---

## What to Build

### 1. `lib/tier1-fxtwitter.sh` — Extract from existing process-bookmarks.sh

Pull the FxTwitter fetch + JSON parse logic into a standalone function.

```bash
# Input: tweet URL
# Output: JSON with normalized fields (text, author, date, engagement, etc.)
# Exit code: 0 = success, 1 = failure (triggers Tier 2)

tier1_fetch() {
  local url="$1"
  local username tweet_id api_url response
  # ... parse URL, curl FxTwitter, validate response
  # Return normalized JSON on success, exit 1 on failure
}
```

### 2. `lib/tier2-jina.sh` — Jina Reader Fallback + URL Enrichment

```bash
# Input: any URL (tweet, GitHub, blog post, etc.)
# Output: clean markdown content
# Exit code: 0 = success, 1 = failure (triggers Tier 3)

tier2_fetch() {
  local url="$1"
  curl -s "https://r.jina.ai/${url}" \
    -H "Accept: application/json" \
    -H "X-Return-Format: markdown"
  # Parse response, extract content, return
}

# Bonus: enrich a tweet note with linked content
tier2_enrich() {
  local tweet_json="$1"
  # Extract URLs from tweet text
  # For each URL: fetch via Jina, append to note
  # Especially useful for GitHub repos linked in tweets
}
```

### 3. `scripts/extract-bookmarks-playwright.js` — Replaces Manual Console Workflow

Node.js script using Playwright. This is the big win.

```javascript
// Usage: node scripts/extract-bookmarks-playwright.js [--cookies cookies.json]

const { chromium } = require('playwright');

async function extractBookmarks(cookiesPath, knownUrls) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  // Load session cookies
  const cookies = JSON.parse(fs.readFileSync(cookiesPath));
  await context.addCookies(cookies);

  const page = await context.newPage();
  await page.goto('https://x.com/i/bookmarks');
  await page.waitForSelector('[data-testid="tweet"]');

  const extracted = [];
  let staleCount = 0;
  const MAX_STALE = 5;

  while (staleCount < MAX_STALE) {
    // Extract tweet URLs from current viewport
    const urls = await page.evaluate(() => {
      return [...document.querySelectorAll('a[href*="/status/"]')]
        .map(a => a.getAttribute('href'))
        .filter(h => /^\/[^/]+\/status\/\d+$/.test(h))
        .map(h => `https://x.com${h}`);
    });

    let newCount = 0;
    for (const url of urls) {
      if (extracted.includes(url)) continue;
      if (knownUrls.has(url)) {
        console.log(`Hit vault boundary: ${url}`);
        await browser.close();
        return extracted;
      }
      extracted.push(url);
      newCount++;
    }

    if (newCount === 0) staleCount++;
    else staleCount = 0;

    await page.evaluate(() => window.scrollBy(0, 800));
    await page.waitForTimeout(1500);
  }

  await browser.close();
  return extracted;
}
```

### 4. `scripts/export-cookies.sh` — One-Time Cookie Export Helper

```bash
#!/usr/bin/env bash
# Exports X/Twitter session cookies from Chrome for Playwright use.
# Uses chrome-cookies-secure npm package or manual SQLite extraction.

# Option A: npm package (easier)
npx chrome-cookies-secure --url "https://x.com" --format "puppeteer" > cookies.json

# Option B: Direct SQLite (no npm dependency)
# Extract from ~/Library/Application Support/Google/Chrome/Default/Cookies
# Decrypt with macOS keychain
```

Cookies need re-exporting when they expire (every few weeks).
The script should detect stale cookies and warn the user.

### 5. Refactor `process-bookmarks.sh` — Tiered Fetch

Replace the single `curl` call with a tiered approach:

```bash
fetch_tweet() {
  local url="$1"

  # Tier 1: FxTwitter API
  local result
  result=$(tier1_fetch "$url" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "$result"
    return 0
  fi
  warn "Tier 1 (FxTwitter) failed for $url, trying Tier 2..."

  # Tier 2: Jina Reader
  result=$(tier2_fetch "$url" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "$result"
    return 0
  fi
  warn "Tier 2 (Jina) failed for $url, trying Tier 3..."

  # Tier 3: Playwright (slowest, most reliable)
  result=$(tier3_fetch "$url" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "$result"
    return 0
  fi

  warn "All tiers failed for $url"
  return 1
}
```

### 6. Optional: `lib/tier3-playwright.sh` — Single Tweet via Playwright

For cases where FxTwitter and Jina both fail on a specific tweet:

```bash
tier3_fetch() {
  local url="$1"
  node "$SCRIPT_DIR/lib/playwright-fetch-tweet.js" "$url" --cookies "$COOKIES_FILE"
}
```

Small Playwright script that navigates to a single tweet URL with cookies,
extracts the rendered content, and returns it as JSON.

---

## Updated Pipeline Flow

```
User runs: ./scripts/process-bookmarks.sh

Step 1: Extract bookmark URLs
  IF cookies.json exists → Playwright headless (fully automated)
  ELSE → prompt user to run extract-bookmarks.sh (manual console method)

Step 2: Dedup against vault

Step 3: For each new URL:
  Tier 1 → FxTwitter API (curl, ~200ms)
    ↓ on failure
  Tier 2 → Jina Reader (~1-2s)
    ↓ on failure
  Tier 3 → Playwright (~3-5s)
    ↓ on failure
  Log error, skip

Step 4: Classify, template, write to vault

Step 5: Enrich (optional)
  For each note with GitHub/blog links in tweet text:
    Tier 2 → Jina Reader fetches the linked content
    Append to note as "## Linked Content" section
```

---

## Dependencies to Add

```json
{
  "dependencies": {
    "playwright": "^1.42.0"
  },
  "optionalDependencies": {
    "chrome-cookies-secure": "^2.0.0"
  }
}
```

Run `npx playwright install chromium` after npm install.

---

## Build Order for CC

1. `lib/tier1-fxtwitter.sh` — extract from existing process-bookmarks.sh
2. `lib/tier2-jina.sh` — Jina Reader wrapper + enrichment function
3. `scripts/extract-bookmarks-playwright.js` — Playwright bookmark extractor
4. `scripts/export-cookies.sh` — cookie export helper
5. Refactor `process-bookmarks.sh` to use tiered fetch
6. `lib/tier3-playwright.sh` + `lib/playwright-fetch-tweet.js` — single-tweet Playwright fallback
7. Add `package.json` with Playwright dependency
8. Update README with 3-tier docs
9. Test: run full pipeline with Playwright bookmark extraction

---

## What This Unlocks

1. **Fully automated bookmark processing** — no more pasting JS in console
2. **GitHub README auto-enrichment** — tweets linking repos get the README content appended
3. **Resilient extraction** — if FxTwitter has issues, Jina and Playwright catch it
4. **Foundation for VPS deployment** — Playwright script can run on Cairn's Hetzner VPS
   on a cron schedule, scraping bookmarks daily and writing to vault via SSH/sync
5. **Foundation for more sources** — Tier 2 (Jina) already works for any URL,
   so YouTube, HN, RSS → vault becomes trivial to add
