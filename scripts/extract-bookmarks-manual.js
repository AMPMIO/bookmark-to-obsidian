// Twitter Bookmarks Extractor — Browser Console Version
// Paste into browser console while on https://x.com/i/bookmarks
// Known URLs are injected by the launcher script (extract-bookmarks-manual.sh)

(async () => {
  "use strict";

  // ── CONFIG ──────────────────────────────────────────────
  const SCROLL_DELAY_MS = 1500;
  const MAX_STALE_SCROLLS = 5;     // stop after N scrolls with no new URLs
  const SCROLL_AMOUNT = 800;       // pixels per scroll

  // Injected by launcher — will be replaced with actual known URLs
  const KNOWN_URLS = new Set(/*__KNOWN_URLS__*/[]);

  // ── STATE ───────────────────────────────────────────────
  const extracted = [];
  const seen = new Set();
  let staleCount = 0;
  let hitBoundary = false;

  // ── HELPERS ─────────────────────────────────────────────
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function extractTweetURLs() {
    const links = document.querySelectorAll('a[href*="/status/"]');
    const urls = [];
    for (const link of links) {
      const href = link.getAttribute("href");
      // Match /{username}/status/{id} but not /status/{id}/analytics, /photo, etc.
      const match = href.match(/^\/([^/]+)\/status\/(\d+)$/);
      if (!match) continue;
      const url = `https://x.com${href}`;
      urls.push(url);
    }
    return urls;
  }

  // ── VERIFY PAGE ─────────────────────────────────────────
  if (!window.location.href.includes("x.com/i/bookmarks")) {
    console.error("[Extractor] Navigate to https://x.com/i/bookmarks first.");
    return;
  }

  console.log(`[Extractor] Starting. ${KNOWN_URLS.size} known URLs loaded.`);

  // ── SCROLL LOOP ─────────────────────────────────────────
  while (!hitBoundary && staleCount < MAX_STALE_SCROLLS) {
    const urls = extractTweetURLs();
    let newCount = 0;

    for (const url of urls) {
      if (seen.has(url)) continue;
      seen.add(url);

      // Check stop condition
      if (KNOWN_URLS.has(url)) {
        console.log(`[Extractor] Hit known URL boundary: ${url}`);
        hitBoundary = true;
        break;
      }

      extracted.push(url);
      newCount++;
    }

    if (newCount > 0) {
      staleCount = 0;
      console.log(
        `[Extractor] +${newCount} new (${extracted.length} total). Scrolling...`
      );
    } else {
      staleCount++;
      console.log(
        `[Extractor] No new URLs (stale ${staleCount}/${MAX_STALE_SCROLLS}). Scrolling...`
      );
    }

    window.scrollBy(0, SCROLL_AMOUNT);
    await sleep(SCROLL_DELAY_MS);
  }

  // ── RESULTS ─────────────────────────────────────────────
  const output = extracted.join("\n");

  if (extracted.length === 0) {
    console.log("[Extractor] No new bookmarks found.");
    return;
  }

  // Copy to clipboard
  try {
    await navigator.clipboard.writeText(output);
    console.log(`[Extractor] ${extracted.length} URLs copied to clipboard.`);
  } catch {
    console.warn("[Extractor] Clipboard write failed. Output below:");
  }

  // Also log to console for manual copy
  console.log(
    `\n[Extractor] Done. ${extracted.length} new bookmark URLs extracted.\n` +
      (hitBoundary
        ? "Stopped at known vault boundary."
        : `Stopped after ${MAX_STALE_SCROLLS} scrolls with no new tweets.`) +
      "\n\n" +
      output
  );

  // Return for programmatic access
  return extracted;
})();
