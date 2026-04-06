export interface Restaurant {
  name: string;
  slug: string;
  lat: number | null;
  lng: number | null;
  rating: number | null;
  reviews: number | null;
  address: string | null;
  photos: string[];
}

export interface Dish {
  id?: string;
  name: string;
  price: number | string | null;
  description: string;
  category: string;
  restaurant_slug: string;
  restaurant_name: string;
  dietary_info: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface SearchParams {
  query?: string;
  price_min?: number;
  price_max?: number;
  categories?: string[];
  dietary?: string[];
  limit?: number;
}

export interface FilterOptions {
  categories: string[];
  dietary_tags: string[];
  price_min: number;
  price_max: number;
}
