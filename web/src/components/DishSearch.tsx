import { useState, useEffect, useRef, useCallback } from 'react';
import { searchDishes } from '../api';
import type { Dish } from '../types';
import DishCard from './DishCard';
import FilterPanel from './FilterPanel';
import { DishGridSkeleton } from './LoadingSkeleton';

interface DishSearchProps {
  onOpenChat: (slug: string, name: string) => void;
}

export default function DishSearch({ onOpenChat }: DishSearchProps) {
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
  const inputRef = useRef<HTMLInputElement>(null);

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
      const detail = (e as CustomEvent).detail as string;
      setQuery(detail);
      if (inputRef.current) inputRef.current.value = detail;
      doSearch(detail);
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
        {/* Search input */}
        <div className="max-w-2xl mx-auto mb-8">
          <div className="relative">
            <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search dishes..."
              className="w-full pl-12 pr-4 py-3.5 bg-white border border-stone-200 rounded-full text-stone-900 placeholder-stone-400 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-all duration-200"
            />
          </div>
        </div>

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
