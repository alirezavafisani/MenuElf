import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { searchDishes, categoryDishes } from '../api';
import type { Dish } from '../types';
import type { RestaurantGeo, UserLocation } from '../geo';
import { distanceKm } from '../geo';
import DishCard from './DishCard';
import FilterPanel from './FilterPanel';
import { DishGridSkeleton } from './LoadingSkeleton';
import { saveRecent } from './Hero';

interface DishSearchProps {
  onOpenChat: (slug: string, name: string) => void;
  restaurantPhotoMap: Record<string, string>;
  restaurantGeoMap: Record<string, RestaurantGeo>;
  userLoc: UserLocation | null;
  locDenied: boolean;
  onRequestLocation: () => void;
}

const MAX_RESULTS = 8;

const EMPTY_STATE_IDEAS = ['butter chicken', 'pho', 'birria tacos', 'cheesecake'];

/** Keep the query in the address bar so a search is a link you can share,
 *  bookmark, or send to the friend you are eating with. */
function writeUrl(q: string) {
  try {
    const url = new URL(window.location.href);
    if (q) url.searchParams.set('q', q);
    else url.searchParams.delete('q');
    window.history.replaceState(null, '', url);
  } catch {
    /* older browsers, no harm done */
  }
}

export default function DishSearch({
  onOpenChat,
  restaurantPhotoMap,
  restaurantGeoMap,
  userLoc,
  locDenied,
  onRequestLocation,
}: DishSearchProps) {
  const [query, setQuery] = useState('');
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');
  const [sortByDistance, setSortByDistance] = useState(false);

  const [priceMin, setPriceMin] = useState<number | undefined>();
  const [priceMax, setPriceMax] = useState<number | undefined>();
  const [categories, setCategories] = useState<string[]>([]);
  const [dietary, setDietary] = useState<string[]>([]);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const bootedRef = useRef(false);

  const doSearch = useCallback(
    async (q: string, useCategory = false) => {
      setLoading(true);
      setError('');
      setHasSearched(true);
      if (q.trim()) saveRecent(q.trim());
      writeUrl(q.trim());
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

  // First paint. A shared link with ?q= replays that exact search. A plain
  // visit quietly loads a handpicked set so the page is never an empty room,
  // and quietly stays a hero-only page if the backend has nothing to say.
  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;
    const q = new URLSearchParams(window.location.search).get('q')?.trim();
    if (q) {
      setQuery(q);
      doSearch(q);
      setTimeout(
        () => document.getElementById('search-results')?.scrollIntoView({ behavior: 'smooth' }),
        400
      );
      return;
    }
    searchDishes({ limit: MAX_RESULTS })
      .then((res) => {
        if (res.dishes.length > 0) {
          setDishes(res.dishes);
          setHasSearched(true);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    if (!query) return; // the handpicked set stays put until a real query comes in
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch, hasSearched]);

  useEffect(() => {
    if (hasSearched && bootedRef.current) doSearch(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceMin, priceMax, categories, dietary]);

  const clearFilters = () => {
    setPriceMin(undefined);
    setPriceMax(undefined);
    setCategories([]);
    setDietary([]);
  };

  // Relevance order comes from the backend. When the visitor shares their
  // location, closest-first becomes an option; dishes without coordinates sink.
  const shownDishes = useMemo(() => {
    if (!sortByDistance || !userLoc) return dishes;
    return [...dishes].sort((a, b) => {
      const ga = restaurantGeoMap[a.restaurant_slug];
      const gb = restaurantGeoMap[b.restaurant_slug];
      const da =
        ga?.lat != null && ga?.lng != null
          ? distanceKm(userLoc, { lat: ga.lat, lng: ga.lng })
          : Infinity;
      const db =
        gb?.lat != null && gb?.lng != null
          ? distanceKm(userLoc, { lat: gb.lat, lng: gb.lng })
          : Infinity;
      return da - db;
    });
  }, [dishes, sortByDistance, userLoc, restaurantGeoMap]);

  const toggleDistanceSort = () => {
    if (!sortByDistance && !userLoc) onRequestLocation();
    setSortByDistance((v) => !v);
  };

  const editSearch = () => {
    window.dispatchEvent(new Event('menuelf:focus-search'));
  };

  if (!hasSearched) return <div id="search-results" />;

  return (
    <section id="search-results" className="py-16 md:py-24 px-4 border-t border-border-warm">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-baseline justify-between flex-wrap gap-3">
              <div>
                <p className="font-serif italic text-base md:text-lg text-sand mb-2 md:mb-3">
                  real dishes, real Calgary menus. ask any kitchen, or jump to Google Maps.
                </p>
                <h2 className="font-display text-3xl md:text-5xl font-medium text-ink tracking-tight">
                {query ? (
                  <>
                    for{' '}
                    <span className="italic" style={{ fontVariationSettings: '"opsz" 144' }}>
                      "{query}"
                    </span>
                    <button
                      onClick={editSearch}
                      aria-label="Edit search"
                      className="ml-3 align-middle text-sm uppercase tracking-widest font-sans font-semibold text-sand hover:text-terracotta transition-colors"
                    >
                      edit
                    </button>
                  </>
                ) : (
                  'handpicked for you'
                )}
              </h2>
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={toggleDistanceSort}
                  data-testid="sort-distance"
                  className={`text-sm uppercase tracking-widest font-semibold transition-colors ${
                    sortByDistance && userLoc
                      ? 'text-terracotta'
                      : 'text-sand hover:text-terracotta'
                  }`}
                >
                  {sortByDistance && userLoc ? 'closest first ✓' : 'sort by distance'}
                </button>
                <p className="font-serif italic text-sand">up to {MAX_RESULTS} dishes</p>
              </div>
            </div>

            {sortByDistance && !userLoc && locDenied && (
              <p className="font-serif italic text-sm text-burgundy mb-4">
                location is off, so distance stays hidden. results are still ranked by match.
              </p>
            )}

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
              <div className="text-center py-8">
                <p className="text-burgundy font-serif italic mb-4">{error}</p>
                <button
                  onClick={() => doSearch(query)}
                  className="px-5 py-2.5 bg-ink hover:bg-terracotta text-cream text-xs uppercase tracking-widest font-semibold transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {loading ? (
              <DishGridSkeleton />
            ) : (
              <>
                {shownDishes.length > 0 && (
                  <p className="font-serif italic text-sm text-sand mb-4">
                    {shownDishes.length} {shownDishes.length === 1 ? 'dish' : 'dishes'} worth your attention
                  </p>
                )}

                {shownDishes.length === 0 && !error && (
                  <div className="text-center py-16">
                    <p className="font-serif italic text-xl text-sand mb-6">
                      nothing matched. try a different craving or loosen the filters.
                    </p>
                    <p className="font-serif italic text-base text-sand">
                      maybe{' '}
                      {EMPTY_STATE_IDEAS.map((s, i) => (
                        <span key={s}>
                          <button
                            onClick={() => {
                              setQuery(s);
                              doSearch(s);
                            }}
                            className="underline underline-offset-4 decoration-sand/40 hover:decoration-terracotta hover:text-terracotta transition-colors"
                          >
                            {s}
                          </button>
                          {i < EMPTY_STATE_IDEAS.length - 1 && (
                            <span className="text-sand/50"> · </span>
                          )}
                        </span>
                      ))}
                      ?
                    </p>
                  </div>
                )}

                <div
                  className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6"
                  data-testid="dish-grid"
                >
                  {shownDishes.map((dish, i) => (
                    <DishCard
                      key={`${dish.restaurant_slug}-${dish.name}-${i}`}
                      dish={dish}
                      index={i}
                      onOpenChat={onOpenChat}
                      photoUrl={restaurantPhotoMap[dish.restaurant_slug]}
                      geo={restaurantGeoMap[dish.restaurant_slug]}
                      userLoc={userLoc}
                    />
                  ))}
                </div>
              </>
            )}
      </div>
    </section>
  );
}
