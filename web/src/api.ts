import type { SearchParams, ChatMessage, Restaurant, Dish, FilterOptions } from './types';

const API_BASE = '';

export async function searchDishes(params: SearchParams): Promise<{ dishes: Dish[] }> {
  const res = await fetch(`${API_BASE}/search-dishes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function categoryDishes(params: SearchParams): Promise<{ dishes: Dish[] }> {
  const res = await fetch(`${API_BASE}/category-dishes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('Category search failed');
  return res.json();
}

export async function getRandomDish(maxPrice?: number): Promise<Dish> {
  const qs = maxPrice ? `?max_price=${maxPrice}` : '';
  const res = await fetch(`${API_BASE}/random-dish${qs}`);
  if (!res.ok) throw new Error('No dish found');
  return res.json();
}

export async function getRestaurants(): Promise<{ restaurants: Restaurant[] }> {
  const res = await fetch(`${API_BASE}/restaurants`, {
    headers: { 'x-user-id': 'web-visitor' },
  });
  if (!res.ok) throw new Error('Failed to load restaurants');
  return res.json();
}

export async function chatWithRestaurant(
  slug: string,
  message: string,
  history: ChatMessage[]
): Promise<{ reply: string }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ restaurant: slug, message, history }),
  });
  if (!res.ok) {
    if (res.status === 429) throw new Error('RATE_LIMITED');
    throw new Error('Chat failed');
  }
  return res.json();
}

export async function getFilterOptions(): Promise<FilterOptions> {
  const res = await fetch(`${API_BASE}/filter-options`);
  if (!res.ok) throw new Error('Failed to load filters');
  return res.json();
}
