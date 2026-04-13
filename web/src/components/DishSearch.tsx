import { useState, useEffect, useRef, useCallback } from 'react';
import { searchDishes, categoryDishes } from '../api';
import type { Dish } from '../types';
import DishCard from './DishCard';
import FilterPanel from './FilterPanel';
import { DishGridSkeleton } from './LoadingSkeleton';

interface DishSearchProps {
  onOpenChat: (slug: string, name: string) => void;
  restaurantPhotoMap: Record<string, string>;
}

const MAX_RESULTS = 8;

export default function DishSearch({ onOpenChat, restaurantPhotoMap }: DishSearchProps) {
  const [query, setQuery] = useState('');
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');

  const [priceMin, setPriceMin] = useState<number | undefined>();
  const [priceMax, setPriceMax] = useState<number | undefined>();
  const [categories, setCategories] = useState<string[]>([]);
  const [dietary, setDietary] = useState<string[]>([]);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const doSearch = useCallback(
    async (q: string, useCategory = false) => {
      setLoading(true);
      setError('');
      setHasSearched(true);
      try {
        const params = {
          query: q || undefined,
          price_min: priceMin,
          price_max: priceMax,
          categories: categories.length > 0 ? categories : undefined,
          dietary: dietary.length > 0 ? dietary : undefined,
          limit: MAX_RESULTS,
        };
        const res = useCategory ? await categoryDishes(params) : await searchDishes(params);
        setDishes(res.dishes);
      } catch {
        setError('Failed to search. Please try again.');
      } finally {
        setLoading(false);
      }
    },
    [priceMin, priceMax, categories, dietary]
  );

  // Hero / category events
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as {
        query: string;
        priceMax?: number;
        useCategory?: boolean;
      };
      const q = detail.query ?? '';
      setQuery(q);
      if (detail.priceMax !== undefined) setPriceMax(detail.priceMax);
      doSearch(q, !!detail.useCategory);
    };
    window.addEventListener('menuelf:search', handler);
    return () => window.removeEventListener('menuelf:search', handler);
  }, [doSearch]);

  useEffect(() => {
    if (!query && !hasSearched) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch, hasSearched]);

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

  if (!hasSearched) return <div id="search-results" />;

  return (
    <section id="search-results" className="py-16 md:py-24 px-4 border-t border-border-warm">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-baseline justify-between flex-wrap gap-3">
              <h2 className="font-display text-3xl md:text-5xl font-medium text-ink tracking-tight">
                {query ? (
                  <>
                    for{' '}
                    <span className="italic" style={{ fontVariationSettings: '"opsz" 144' }}>
                      "{query}"
                    </span>
                  </>
                ) : (
                  'handpicked for you'
                )}
              </h2>
              <p className="font-serif italic text-sand">up to {MAX_RESULTS} dishes</p>
            </div>

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
              <div className="text-center py-8 text-burgundy font-serif italic">{error}</div>
            )}

            {loading ? (
              <DishGridSkeleton />
            ) : (
              <>
                {dishes.length > 0 && (
                  <p className="font-serif italic text-sm text-sand mb-4">
                    {dishes.length} {dishes.length === 1 ? 'dish' : 'dishes'} worth your attention
                  </p>
                )}

                {dishes.length === 0 && !error && (
                  <div className="text-center py-16">
                    <p className="font-serif italic text-xl text-sand">
                      nothing matched. try a different craving or loosen the filters.
                    </p>
                  </div>
                )}

                <div
                  className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6"
                  data-testid="dish-grid"
                >
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
      </div>
    </section>
  );
}
