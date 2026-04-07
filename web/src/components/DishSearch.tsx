import { useState, useEffect, useRef, useCallback } from 'react';
import { searchDishes } from '../api';
import type { Dish } from '../types';
import DishCard from './DishCard';
import FilterPanel from './FilterPanel';
import { DishGridSkeleton } from './LoadingSkeleton';

interface DishSearchProps {
  onOpenChat: (slug: string, name: string) => void;
  restaurantPhotoMap: Record<string, string>;
}

export default function DishSearch({ onOpenChat, restaurantPhotoMap }: DishSearchProps) {
  const [query, setQuery] = useState('');
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');

  // Filters
  const [priceMin, setPriceMin] = useState<number | undefined>();
  const [priceMax, setPriceMax] = useState<number | undefined>();
  const [categories, setCategories] = useState<string[]>([]);
  const [dietary, setDietary] = useState<string[]>([]);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const doSearch = useCallback(
    async (q: string) => {
      setLoading(true);
      setError('');
      setHasSearched(true);
      try {
        const res = await searchDishes({
          query: q || undefined,
          price_min: priceMin,
          price_max: priceMax,
          categories: categories.length > 0 ? categories : undefined,
          dietary: dietary.length > 0 ? dietary : undefined,
          limit: 30,
        });
        setDishes(res.dishes);
      } catch {
        setError('Failed to search. Please try again.');
      } finally {
        setLoading(false);
      }
    },
    [priceMin, priceMax, categories, dietary]
  );

  // Listen for hero search events
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { query: string; priceMax?: number };
      const q = detail.query ?? '';
      setQuery(q);
      if (detail.priceMax !== undefined) {
        setPriceMax(detail.priceMax);
      }
      doSearch(q);
    };
    window.addEventListener('menuelf:search', handler);
    return () => window.removeEventListener('menuelf:search', handler);
  }, [doSearch]);

  // Debounced search on query change
  useEffect(() => {
    if (!query && !hasSearched) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch, hasSearched]);

  // Re-search when filters change (if already searched)
  useEffect(() => {
    if (hasSearched) doSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceMin, priceMax, categories, dietary]);

  const clearFilters = () => {
    setPriceMin(undefined);
    setPriceMax(undefined);
    setCategories([]);
    setDietary([]);
  };

  return (
    <section id="search" className="py-16 px-4">
      <div className="max-w-7xl mx-auto">
        {hasSearched && (
          <>
            <FilterPanel
              priceMin={priceMin}
              priceMax={priceMax}
              categories={categories}
              dietary={dietary}
              onPriceMinChange={setPriceMin}
              onPriceMaxChange={setPriceMax}
              onCategoriesChange={setCategories}
              onDietaryChange={setDietary}
              onClear={clearFilters}
            />

            {error && (
              <div className="text-center py-8 text-red-500 text-sm">{error}</div>
            )}

            {loading ? (
              <DishGridSkeleton />
            ) : (
              <>
                {dishes.length > 0 && (
                  <p className="text-sm text-stone-500 mb-4">
                    Found <span className="font-semibold text-stone-700">{dishes.length}</span> dishes
                  </p>
                )}

                {dishes.length === 0 && !error && (
                  <div className="text-center py-12">
                    <p className="text-stone-500">No dishes found. Try a different search or adjust filters.</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dishes.map((dish, i) => (
                    <DishCard
                      key={`${dish.restaurant_slug}-${dish.name}-${i}`}
                      dish={dish}
                      index={i}
                      onOpenChat={onOpenChat}
                      photoUrl={restaurantPhotoMap[dish.restaurant_slug]}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
