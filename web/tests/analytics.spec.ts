import { test, expect } from '@playwright/test';

interface Stats {
  total_visitors: number;
  total_searches: number;
  total_chats: number;
  weekly_visitors: number;
  daily_breakdown: Array<{
    day: string;
    visitors: number;
    searches: number;
    chats: number;
  }>;
}

async function fetchStats(baseURL: string): Promise<Stats> {
  const res = await fetch(`${baseURL}/stats`);
  return res.json();
}

test.describe('Analytics: Proof of Use', () => {
  test('three personas generate correct analytics counts', async ({ browser, baseURL }) => {
    // ─── Baseline ───
    const before = await fetchStats(baseURL!);
    console.log('\n=== BASELINE STATS ===');
    console.log(`  Visitors: ${before.total_visitors}`);
    console.log(`  Searches: ${before.total_searches}`);
    console.log(`  Chats:    ${before.total_chats}`);

    // ─── Persona 1: "Hungry Tourist" ───
    // Visits homepage, searches "pizza" and "burger", opens chat with one restaurant
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();

    await page1.goto('/app/');
    await page1.waitForLoadState('networkidle');

    // Search 1: pizza
    await page1.fill('#search-input', 'pizza');
    await page1.click('#search-btn');
    await page1.waitForSelector('.dish-card');

    // Search 2: burger
    await page1.fill('#search-input', 'burger');
    await page1.click('#search-btn');
    await page1.waitForSelector('.dish-card');

    // Open chat with a restaurant (triggers a chat event)
    // Use page.evaluate to call the chat API directly
    await page1.evaluate(async () => {
      await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          restaurant: 'pizza-place',
          message: 'What do you recommend?',
          history: [],
        }),
      });
    });

    await ctx1.close();

    // ─── Persona 2: "Vegan Student" ───
    // Visits homepage, searches with dietary filter "vegan"
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();

    await page2.goto('/app/');
    await page2.waitForLoadState('networkidle');

    // Search with vegan dietary filter via API (since UI is simplified for testing)
    await page2.evaluate(async () => {
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'vegan', dietary: ['vegan'], limit: 20 }),
      });
    });

    await ctx2.close();

    // ─── Persona 3: "Late Night Foodie" ───
    // Visits homepage, searches "ramen", "spicy", "under $10"
    const ctx3 = await browser.newContext();
    const page3 = await ctx3.newPage();

    await page3.goto('/app/');
    await page3.waitForLoadState('networkidle');

    // Search 1: ramen
    await page3.fill('#search-input', 'ramen');
    await page3.click('#search-btn');
    await page3.waitForSelector('.dish-card');

    // Search 2: spicy
    await page3.fill('#search-input', 'spicy');
    await page3.click('#search-btn');
    await page3.waitForSelector('.dish-card');

    // Search 3: under $10 (price filter)
    await page3.evaluate(async () => {
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: '', price_max: 10, limit: 20 }),
      });
    });

    await ctx3.close();

    // ─── Verify Stats ───
    // Small delay to let SQLite writes flush
    await new Promise((r) => setTimeout(r, 500));

    const after = await fetchStats(baseURL!);
    console.log('\n=== AFTER STATS ===');
    console.log(`  Visitors: ${after.total_visitors} (was ${before.total_visitors})`);
    console.log(`  Searches: ${after.total_searches} (was ${before.total_searches})`);
    console.log(`  Chats:    ${after.total_chats} (was ${before.total_chats})`);
    console.log(`  Weekly:   ${after.weekly_visitors}`);

    const visitorDelta = after.total_visitors - before.total_visitors;
    const searchDelta = after.total_searches - before.total_searches;
    const chatDelta = after.total_chats - before.total_chats;

    console.log('\n=== DELTAS ===');
    console.log(`  +${visitorDelta} visitors`);
    console.log(`  +${searchDelta} searches`);
    console.log(`  +${chatDelta} chats`);

    // Assertions
    // At least 1 visitor (all 3 contexts come from 127.0.0.1 on same day = same hash)
    expect(visitorDelta).toBeGreaterThanOrEqual(1);

    // Exactly 6 searches: 2 (tourist) + 1 (vegan) + 3 (foodie)
    expect(searchDelta).toBe(6);

    // At least 1 chat (tourist sent 1 message)
    expect(chatDelta).toBeGreaterThanOrEqual(1);

    // Daily breakdown should have today's entry
    expect(after.daily_breakdown.length).toBeGreaterThanOrEqual(1);

    console.log('\n=== SUMMARY TABLE ===');
    console.log('┌──────────────┬──────────┬─────────┬─────────┐');
    console.log('│    Metric    │  Before  │  After  │  Delta  │');
    console.log('├──────────────┼──────────┼─────────┼─────────┤');
    console.log(`│ Visitors     │ ${String(before.total_visitors).padStart(8)} │ ${String(after.total_visitors).padStart(7)} │ ${String('+' + visitorDelta).padStart(7)} │`);
    console.log(`│ Searches     │ ${String(before.total_searches).padStart(8)} │ ${String(after.total_searches).padStart(7)} │ ${String('+' + searchDelta).padStart(7)} │`);
    console.log(`│ Chats        │ ${String(before.total_chats).padStart(8)} │ ${String(after.total_chats).padStart(7)} │ ${String('+' + chatDelta).padStart(7)} │`);
    console.log(`│ Weekly       │ ${String(before.weekly_visitors).padStart(8)} │ ${String(after.weekly_visitors).padStart(7)} │         │`);
    console.log('└──────────────┴──────────┴─────────┴─────────┘');
  });

  test('stats counter displays in footer', async ({ page, baseURL }) => {
    // First, generate some data so counter has something to show
    await page.goto('/app/');
    await page.waitForLoadState('networkidle');

    // Do a search to create at least one event
    await page.fill('#search-input', 'pizza');
    await page.click('#search-btn');
    await page.waitForSelector('.dish-card');

    // Reload to pick up fresh stats (counter fetches on load)
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Wait for stats to load and render
    await page.waitForTimeout(1000);

    // Check that the footer has the stats counter with real numbers
    const stats = await fetchStats(baseURL!);
    if (stats.total_visitors > 0) {
      const counter = page.locator('[data-testid="stats-text"]');
      await expect(counter).toBeVisible();
      const text = await counter.textContent();
      console.log(`\nFooter counter text: "${text}"`);

      // Should contain the word "Calgarians" and real numbers
      expect(text).toContain('Calgarians');
      // Should NOT contain "0 dishes served to 0" — we have real data
      expect(text).not.toContain('0 dishes served to 0');
    }
  });

  test('/stats endpoint returns correct schema', async ({ baseURL }) => {
    const stats = await fetchStats(baseURL!);

    // Validate schema
    expect(stats).toHaveProperty('total_visitors');
    expect(stats).toHaveProperty('total_searches');
    expect(stats).toHaveProperty('total_chats');
    expect(stats).toHaveProperty('weekly_visitors');
    expect(stats).toHaveProperty('daily_breakdown');

    // Types
    expect(typeof stats.total_visitors).toBe('number');
    expect(typeof stats.total_searches).toBe('number');
    expect(typeof stats.total_chats).toBe('number');
    expect(typeof stats.weekly_visitors).toBe('number');
    expect(Array.isArray(stats.daily_breakdown)).toBe(true);

    console.log(`\n/stats schema validated. ${stats.total_visitors} visitors, ${stats.total_searches} searches, ${stats.total_chats} chats`);
  });
});
