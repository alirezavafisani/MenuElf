import { test, expect } from '@playwright/test';

/**
 * Chunk 3 tests — exercise the new features:
 *   1. "Hungry" button → /random-dish → card displays, "Try another" re-rolls
 *   2. Category tiles   → /category-dishes, results capped at ≤ 8
 *   3. Search limit     → every search returns at most 8 dishes
 *   4. Analytics still increment after the redesign
 *   5. New endpoints    → /random-dish and /category-dishes respond correctly
 */

interface Stats {
  total_visitors: number;
  total_searches: number;
  total_chats: number;
  weekly_visitors: number;
}

async function fetchStats(baseURL: string): Promise<Stats> {
  const res = await fetch(`${baseURL}/stats`);
  return res.json();
}

test.describe('Chunk 3: Editorial redesign + discovery modes', () => {
  test('Hungry button rolls a random dish and re-rolls on "Try another"', async ({
    page,
  }) => {
    await page.goto('/app/');
    await page.waitForLoadState('networkidle');

    // The button exists
    const hungryBtn = page.locator('[data-testid="hungry-button"]');
    await expect(hungryBtn).toBeVisible();

    // Click it — card should appear
    await hungryBtn.click();
    const card = page.locator('[data-testid="random-dish-card"]');
    await expect(card).toBeVisible({ timeout: 5000 });

    const firstName =
      (await page.locator('[data-testid="random-dish-name"]').textContent()) || '';
    expect(firstName.length).toBeGreaterThan(0);
    console.log(`\nFirst dish: "${firstName.trim()}"`);

    // Click "Try another" and expect the card to re-render (same selector, maybe
    // the same dish occasionally with random — so we just verify it still shows)
    const tryAnother = page.locator('[data-testid="try-another"]');
    await tryAnother.click();
    await expect(card).toBeVisible();

    // Re-roll a few times and confirm at least one yields a different dish
    // (14 mock dishes — probability of 5 identical in a row is ~1 in 37k)
    const seen = new Set<string>([firstName.trim()]);
    for (let i = 0; i < 5; i++) {
      await tryAnother.click();
      await page.waitForTimeout(200);
      const n =
        (await page.locator('[data-testid="random-dish-name"]').textContent()) || '';
      seen.add(n.trim());
      if (seen.size > 1) break;
    }
    expect(seen.size).toBeGreaterThanOrEqual(2);
    console.log(`  Saw ${seen.size} unique dishes across rolls`);
  });

  test('Category tile click runs a search and caps at 8 results', async ({ page }) => {
    await page.goto('/app/');
    await page.waitForLoadState('networkidle');

    const pizzaTile = page.locator('[data-testid="tile-pizza"]');
    await expect(pizzaTile).toBeVisible();
    await pizzaTile.click();

    // Wait for results grid to render
    const grid = page.locator('[data-testid="dish-grid"]');
    await expect(grid).toBeVisible({ timeout: 5000 });

    const cards = grid.locator('[data-testid="dish-card"]');
    const count = await cards.count();
    console.log(`\nCategory tile → ${count} dishes rendered (cap: 8)`);
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(8);
  });

  test('API: /search-dishes caps results at 8', async ({ baseURL }) => {
    // Even if we explicitly ask for 30, backend must cap at 8
    const res = await fetch(`${baseURL}/search-dishes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: '', limit: 30 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    console.log(`\n/search-dishes returned ${data.dishes.length} dishes (cap: 8)`);
    expect(Array.isArray(data.dishes)).toBe(true);
    expect(data.dishes.length).toBeLessThanOrEqual(8);
  });

  test('API: /random-dish returns a dish with all required fields', async ({
    baseURL,
  }) => {
    const res = await fetch(`${baseURL}/random-dish`);
    expect(res.ok).toBe(true);
    const dish = await res.json();
    console.log(`\n/random-dish: "${dish.name}" at ${dish.restaurant_name}`);
    expect(dish).toHaveProperty('name');
    expect(dish).toHaveProperty('price');
    expect(dish).toHaveProperty('restaurant_slug');
    expect(dish).toHaveProperty('restaurant_name');
  });

  test('API: /random-dish respects max_price filter', async ({ baseURL }) => {
    const res = await fetch(`${baseURL}/random-dish?max_price=12`);
    expect(res.ok).toBe(true);
    const dish = await res.json();
    console.log(`\n/random-dish?max_price=12 → "${dish.name}" at $${dish.price}`);
    expect(Number(dish.price)).toBeLessThanOrEqual(12);
  });

  test('API: /category-dishes returns up to 8 dishes', async ({ baseURL }) => {
    const res = await fetch(`${baseURL}/category-dishes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'pasta' }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    console.log(`\n/category-dishes 'pasta' → ${data.dishes.length} dishes`);
    expect(data.dishes.length).toBeLessThanOrEqual(8);
    expect(data.dishes.length).toBeGreaterThan(0);
  });

  test('Analytics still works end-to-end after redesign', async ({
    baseURL,
    page,
  }) => {
    const before = await fetchStats(baseURL!);

    // Load the redesigned page (page_view event)
    await page.goto('/app/');
    await page.waitForLoadState('networkidle');

    // Click Hungry button (random_dish event — separate from searches)
    await page.locator('[data-testid="hungry-button"]').click();
    await page.waitForSelector('[data-testid="random-dish-card"]');

    // Click a category tile (search event)
    await page.locator('[data-testid="tile-ramen"]').click();
    await page.waitForSelector('[data-testid="dish-grid"]');

    await page.waitForTimeout(500);

    const after = await fetchStats(baseURL!);
    const searchDelta = after.total_searches - before.total_searches;
    console.log(
      `\nRedesign analytics: +${searchDelta} searches, visitors now ${after.total_visitors}`
    );

    // At least one search (from the category tile) should have registered
    expect(searchDelta).toBeGreaterThanOrEqual(1);
    expect(after.total_visitors).toBeGreaterThanOrEqual(before.total_visitors);
  });

  test('UI renders with new editorial typography (Fraunces loaded)', async ({
    page,
  }) => {
    await page.goto('/app/');
    await page.waitForLoadState('networkidle');

    // The Hero h1 should use the display (Fraunces) font
    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
    const fontFamily = await h1.evaluate((el) => window.getComputedStyle(el).fontFamily);
    console.log(`\nHero h1 font-family: ${fontFamily}`);
    expect(fontFamily.toLowerCase()).toContain('fraunces');
  });
});
