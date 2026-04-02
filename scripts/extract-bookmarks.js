#!/usr/bin/env node
/**
 * bookmark-to-obsidian: Playwright Bookmark Extractor
 *
 * Automates scrolling through x.com/i/bookmarks using a saved session cookie.
 * Stops at known vault URLs to avoid reprocessing.
 *
 * Usage:
 *   node scripts/extract-bookmarks.js --cookies <path> --vault <path> --output <path>
 *
 * Options:
 *   --cookies <path>   Path to cookies.json (exported by export-cookies.sh)
 *   --vault <path>     Path to Obsidian vault notes folder (grepped for known URLs)
 *   --output <path>    File to write extracted URLs to (one per line)
 *   --headless false   Show browser window (default: true)
 */

"use strict";

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

// ── Parse CLI args ──────────────────────────────────────
const args = process.argv.slice(2);
const get = (flag) => {
  const i = args.indexOf(flag);
  return i !== -1 ? args[i + 1] : null;
};

const cookiesFile = get("--cookies");
const vaultPath   = get("--vault");
const outputFile  = get("--output");
const headless    = get("--headless") !== "false";

if (!cookiesFile || !outputFile) {
  console.error("Usage: node extract-bookmarks.js --cookies <path> --vault <path> --output <path>");
  process.exit(1);
}

// ── Load known vault URLs ────────────────────────────────
function getKnownUrls(vaultDir) {
  const known = new Set();
  if (!vaultDir || !fs.existsSync(vaultDir)) return known;

  function walk(dir) {
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); }
    catch (e) { return; }

    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith(".md")) {
        try {
          const content = fs.readFileSync(full, "utf-8");
          const match = content.match(/^source:\s*["']?(https?:\/\/[^\s"']+)["']?\s*$/m);
          if (match) known.add(match[1].trim());
        } catch (e) { /* skip unreadable files */ }
      }
    }
  }

  walk(vaultDir);
  console.log(`[Extractor] Loaded ${known.size} known URLs from vault.`);
  return known;
}

// ── Main ─────────────────────────────────────────────────
(async () => {
  const knownUrls = getKnownUrls(vaultPath);

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  // Load session cookies
  if (cookiesFile && fs.existsSync(cookiesFile)) {
    try {
      const cookies = JSON.parse(fs.readFileSync(cookiesFile, "utf-8"));
      await context.addCookies(cookies);
      console.log(`[Extractor] Loaded ${cookies.length} cookies from ${cookiesFile}`);
    } catch (e) {
      console.error("[Extractor] Failed to load cookies:", e.message);
      await browser.close();
      process.exit(1);
    }
  }

  const page = await context.newPage();

  console.log("[Extractor] Navigating to x.com/i/bookmarks...");
  try {
    await page.goto("https://x.com/i/bookmarks", { waitUntil: "domcontentloaded", timeout: 30000 });
  } catch (e) {
    console.error("[Extractor] Navigation failed:", e.message);
    await browser.close();
    process.exit(1);
  }

  // Check we're actually on bookmarks (not redirected to login)
  const currentUrl = page.url();
  if (!currentUrl.includes("bookmarks")) {
    console.error("[Extractor] Not on bookmarks page — cookies may be expired.");
    console.error("[Extractor] Run: ./bookmark-to-obsidian cookies  to refresh session.");
    await browser.close();
    process.exit(1);
  }

  await page.waitForTimeout(2000);

  // ── Scroll loop ────────────────────────────────────────
  const SCROLL_AMOUNT    = 800;
  const SCROLL_DELAY_MS  = 1500;
  const MAX_STALE_SCROLLS = 5;

  const extracted = [];
  const seen      = new Set();
  let staleCount  = 0;
  let hitBoundary = false;

  while (!hitBoundary && staleCount < MAX_STALE_SCROLLS) {
    const hrefs = await page.$$eval('a[href*="/status/"]', (links) =>
      links
        .map((l) => l.getAttribute("href"))
        .filter((h) => h && /^\/[^/]+\/status\/\d+$/.test(h))
    );

    let newCount = 0;
    for (const href of hrefs) {
      const url = `https://x.com${href}`;
      if (seen.has(url)) continue;
      seen.add(url);

      if (knownUrls.has(url)) {
        console.log(`[Extractor] Hit known URL boundary: ${url}`);
        hitBoundary = true;
        break;
      }

      extracted.push(url);
      newCount++;
    }

    if (newCount > 0) {
      staleCount = 0;
      console.log(`[Extractor] +${newCount} new (${extracted.length} total). Scrolling...`);
    } else {
      staleCount++;
      console.log(`[Extractor] No new URLs (stale ${staleCount}/${MAX_STALE_SCROLLS}). Scrolling...`);
    }

    await page.evaluate(() => window.scrollBy(0, 800));
    await page.waitForTimeout(SCROLL_DELAY_MS);
  }

  await browser.close();

  // ── Write output ───────────────────────────────────────
  if (extracted.length === 0) {
    console.log("[Extractor] No new bookmarks found.");
    process.exit(0);
  }

  fs.mkdirSync(path.dirname(outputFile), { recursive: true });

  // Prepend to existing file (newest first)
  let existing = "";
  if (fs.existsSync(outputFile)) {
    existing = fs.readFileSync(outputFile, "utf-8");
  }
  fs.writeFileSync(outputFile, extracted.join("\n") + "\n" + existing);

  console.log(
    `[Extractor] Done. ${extracted.length} URLs written to ${outputFile}.` +
    (hitBoundary ? " Stopped at vault boundary." : "")
  );
})();
