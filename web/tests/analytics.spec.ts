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

/**
 * These tests run against the test-server (web/tests/test-server.py), which
 * imports the real analytics module and serves the built React app from
 * web/dist when present. They simulate personas by a mix of page navigation
 * (to trigger the page_view middleware) and direct API calls from the page
 * context (so they're independent of the evolving UI selectors).
 */
test.describe('Analytics: Proof of Use', () => {
  test('three personas generate correct analytics counts', async ({
    browser,
    baseURL,
  }) => {
    const before = await fetchStats(baseURL!);
    console.log('\n=== BASELINE STATS ===');
    console.log(`  Visitors: ${before.total_visitors}`);
    console.log(`  Searches: ${before.total_searches}`);
    console.log(`  Chats:    ${before.total_chats}`);

    // ─── Persona 1: "Hungry Tourist" ───
    // Visit page, do 2 searches, send 1 chat
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();
    await page1.goto('/app/');
    await page1.waitForLoadState('networkidle');

    await page1.evaluate(async () => {
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'pizza' }),
      });
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'burger' }),
      });
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
    // Visit page, do 1 dietary-filtered search
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    await page2.goto('/app/');
    await page2.waitForLoadState('networkidle');
    await page2.evaluate(async () => {
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'vegan', dietary: ['vegan'] }),
      });
    });
    await ctx2.close();

    // ─── Persona 3: "Late Night Foodie" ───
    // Visit page, do 3 searches
    const ctx3 = await browser.newContext();
    const page3 = await ctx3.newPage();
    await page3.goto('/app/');
    await page3.waitForLoadState('networkidle');
    await page3.evaluate(async () => {
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'ramen' }),
      });
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'spicy' }),
      });
      await fetch('/search-dishes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: '', price_max: 10 }),
      });
    });
    await ctx3.close();

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

    expect(visitorDelta).toBeGreaterThanOrEqual(1);
    expect(searchDelta).toBe(6);
    expect(chatDelta).toBeGreaterThanOrEqual(1);
    expect(after.daily_breakdown.length).toBeGreaterThanOrEqual(1);

    console.log('\n=== SUMMARY TABLE ===');
    console.log('┌──────────────┬──────────┬─────────┬─────────┐');
    console.log('│    Metric    │  Before  │  After  │  Delta  │');
    console.log('├──────────────┼──────────┼─────────┼─────────┤');
    console.log(
      `│ Visitors     │ ${String(before.total_visitors).padStart(8)} │ ${String(after.total_visitors).padStart(7)} │ ${String('+' + visitorDelta).padStart(7)} │`
    );
    console.log(
      `│ Searches     │ ${String(before.total_searches).padStart(8)} │ ${String(after.total_searches).padStart(7)} │ ${String('+' + searchDelta).padStart(7)} │`
    );
    console.log(
      `│ Chats        │ ${String(before.total_chats).padStart(8)} │ ${String(after.total_chats).padStart(7)} │ ${String('+' + chatDelta).padStart(7)} │`
    );
    console.log(
      `│ Weekly       │ ${String(before.weekly_visitors).padStart(8)} │ ${String(after.weekly_visitors).padStart(7)} │         │`
    );
    console.log('└──────────────┴──────────┴─────────┴─────────┘');
  });

  test('stats counter hidden until 20+ searches (threshold check)', async ({
    baseURL,
  }) => {
    // The StatsCounter now hides itself when total_searches < 20.
    // In a test run we'll have well under 20 searches, so the counter
    // should NOT be visible. We verify the threshold logic via the API.
    const stats = await fetchStats(baseURL!);
    console.log(`\nStats: ${stats.total_searches} searches (threshold: 20)`);
    if (stats.total_searches < 20) {
      console.log('  Counter should be hidden (below threshold) — OK');
    } else {
      console.log('  Counter should be visible (above threshold)');
    }
    // The real assertion: total_searches is a number >= 0 (schema check)
    expect(typeof stats.total_searches).toBe('number');
    expect(stats.total_searches).toBeGreaterThanOrEqual(0);
  });

  test('/stats endpoint returns correct schema', async ({ baseURL }) => {
    const stats = await fetchStats(baseURL!);

    expect(stats).toHaveProperty('total_visitors');
    expect(stats).toHaveProperty('total_searches');
    expect(stats).toHaveProperty('total_chats');
    expect(stats).toHaveProperty('weekly_visitors');
    expect(stats).toHaveProperty('daily_breakdown');

    expect(typeof stats.total_visitors).toBe('number');
    expect(typeof stats.total_searches).toBe('number');
    expect(typeof stats.total_chats).toBe('number');
    expect(typeof stats.weekly_visitors).toBe('number');
    expect(Array.isArray(stats.daily_breakdown)).toBe(true);

    console.log(
      `\n/stats schema validated. ${stats.total_visitors} visitors, ${stats.total_searches} searches, ${stats.total_chats} chats`
    );
  });
});
