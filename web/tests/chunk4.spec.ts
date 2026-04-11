import { test, expect } from '@playwright/test';

/**
 * Chunk 4 tests — launch prep polish:
 *   1. Chat responses contain no markdown asterisks (A1)
 *   2. /random-dish never returns drinks/wine/beer over 20 calls (A2)
 *   3. Chat with empty-menu restaurant returns the honest fallback (A4)
 */

test.describe('Chunk 4: Launch polish', () => {
  test('chat responses contain no markdown asterisks', async ({ baseURL }) => {
    // Hit /chat directly with a message; the response is produced by the
    // test server but its reply text deliberately matches the shape the
    // system-prompt rules in backend/main.py enforce.
    const res = await fetch(`${baseURL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        restaurant: 'pizza-place',
        message: 'What do you recommend?',
        history: [],
      }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    console.log(`\nChat reply: "${data.reply}"`);

    // The chunk 4 system prompt explicitly bans double-star and single-star
    // formatting around dish names.
    expect(data.reply).not.toContain('**');
    // Single asterisks would usually be markdown emphasis; also ban them.
    // (But we have to avoid false positives from other asterisk uses — we
    // check there's no `*word*` style pattern.)
    expect(data.reply).not.toMatch(/\*[A-Za-z]/);
  });

  test('random-dish never returns a drink over 20 calls', async ({ baseURL }) => {
    const NON_FOOD_CATEGORY_KEYWORDS = [
      'drink', 'beverage', 'wine', 'beer', 'cocktail',
      'liquor', 'alcohol', 'spirits', 'juice', 'soda',
      'coffee', 'tea',
    ];
    const NON_FOOD_NAME_KEYWORDS = [
      'cabernet', 'merlot', 'pinot', 'chardonnay', 'sauvignon',
      'riesling', 'malbec', 'lager', 'ipa', 'pilsner', 'stout', 'ale',
      'rosé', 'prosecco', 'champagne',
      'tequila', 'whiskey', 'vodka', 'gin', 'rum', 'bourbon',
    ];

    const seen: Array<{ name: string; category: string }> = [];
    for (let i = 0; i < 20; i++) {
      const res = await fetch(`${baseURL}/random-dish`);
      expect(res.ok).toBe(true);
      const dish = await res.json();
      const cat = (dish.category || '').toLowerCase();
      const name = (dish.name || '').toLowerCase();

      const isNonFoodCategory = NON_FOOD_CATEGORY_KEYWORDS.some((k) => cat.includes(k));
      const isNonFoodName = NON_FOOD_NAME_KEYWORDS.some((k) =>
        new RegExp(`\\b${k}\\b`).test(name)
      );

      if (isNonFoodCategory || isNonFoodName) {
        throw new Error(
          `Got non-food dish "${dish.name}" (category: ${dish.category}) on call ${i + 1}`
        );
      }
      seen.push({ name: dish.name, category: dish.category });
    }
    console.log(`\n/random-dish x20: all food. Sample: "${seen[0].name}", "${seen[seen.length - 1].name}"`);
  });

  test('chat with empty-menu restaurant returns honest fallback', async ({
    baseURL,
  }) => {
    // "ghost-restaurant" is a slug the test server treats as having no menu.
    // The backend mirrors the same pattern when MENU_INDEX has no dishes for
    // a given slug.
    const res = await fetch(`${baseURL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        restaurant: 'ghost-restaurant',
        message: 'What do you recommend?',
        history: [],
      }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    console.log(`\nEmpty-menu fallback reply: "${data.reply}"`);

    // Should be the honest fallback, not a hallucinated reply.
    expect(data.reply.toLowerCase()).toContain("don't have");
    expect(data.reply.toLowerCase()).toContain('menu loaded yet');
    // Should NOT contain fabricated prices or dish names.
    expect(data.reply).not.toMatch(/\$\d+(\.\d{2})?/);
  });
});
