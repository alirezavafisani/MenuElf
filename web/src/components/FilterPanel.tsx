import { useState, useEffect } from 'react';
import { getFilterOptions } from '../api';
import type { FilterOptions } from '../types';

interface FilterPanelProps {
  priceMin: number | undefined;
  priceMax: number | undefined;
  categories: string[];
  dietary: string[];
  onPriceMinChange: (v: number | undefined) => void;
  onPriceMaxChange: (v: number | undefined) => void;
  onCategoriesChange: (v: string[]) => void;
  onDietaryChange: (v: string[]) => void;
  onClear: () => void;
}

export default function FilterPanel({
  priceMin,
  priceMax,
  categories,
  dietary,
  onPriceMinChange,
  onPriceMaxChange,
  onCategoriesChange,
  onDietaryChange,
  onClear,
}: FilterPanelProps) {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    getFilterOptions().then(setOptions).catch(() => {});
  }, []);

  if (!options) return null;

  const hasFilters =
    priceMin !== undefined ||
    priceMax !== undefined ||
    categories.length > 0 ||
    dietary.length > 0;

  const toggleCategory = (cat: string) => {
    onCategoriesChange(
      categories.includes(cat)
        ? categories.filter((c) => c !== cat)
        : [...categories, cat]
    );
  };

  const toggleDietary = (tag: string) => {
    onDietaryChange(
      dietary.includes(tag) ? dietary.filter((d) => d !== tag) : [...dietary, tag]
    );
  };

  return (
    <div className="mb-6">
      <div className="flex items-center gap-4 flex-wrap">
        <button
          onClick={() => setOpen(!open)}
          className={`flex items-center gap-2 px-4 py-2 text-sm uppercase tracking-widest font-semibold border transition-all duration-200 ${
            hasFilters
              ? 'border-terracotta text-terracotta bg-terracotta/5'
              : 'border-border-warm text-ink hover:border-sand'
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
          Filters
          {hasFilters && (
            <span className="bg-terracotta text-cream text-xs w-5 h-5 rounded-full flex items-center justify-center">
              {categories.length +
                dietary.length +
                (priceMin !== undefined ? 1 : 0) +
                (priceMax !== undefined ? 1 : 0)}
            </span>
          )}
        </button>

        {hasFilters && (
          <button
            onClick={onClear}
            className="font-serif italic text-sm text-sand hover:text-terracotta transition-colors"
          >
            clear all
          </button>
        )}
      </div>

      {open && (
        <div className="mt-4 p-6 bg-paper border border-border-warm">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h4 className="font-display text-base font-semibold text-ink mb-3">
                Price Range
              </h4>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  value={priceMin ?? ''}
                  onChange={(e) =>
                    onPriceMinChange(e.target.value ? Number(e.target.value) : undefined)
                  }
                  className="w-full px-3 py-2 text-sm bg-cream border border-border-warm focus:outline-none focus:border-terracotta"
                />
                <span className="text-sand">to</span>
                <input
                  type="number"
                  placeholder="Max"
                  value={priceMax ?? ''}
                  onChange={(e) =>
                    onPriceMaxChange(e.target.value ? Number(e.target.value) : undefined)
                  }
                  className="w-full px-3 py-2 text-sm bg-cream border border-border-warm focus:outline-none focus:border-terracotta"
                />
              </div>
            </div>

            <div>
              <h4 className="font-display text-base font-semibold text-ink mb-3">Category</h4>
              <div className="flex flex-wrap gap-1.5">
                {options.categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => toggleCategory(cat)}
                    className={`px-3 py-1 text-xs font-medium rounded-full border transition-all duration-200 ${
                      categories.includes(cat)
                        ? 'border-terracotta bg-terracotta text-cream'
                        : 'border-border-warm text-ink hover:border-sand'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-display text-base font-semibold text-ink mb-3">Dietary</h4>
              <div className="flex flex-wrap gap-1.5">
                {options.dietary_tags.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleDietary(tag)}
                    className={`px-3 py-1 text-xs font-medium rounded-full border transition-all duration-200 ${
                      dietary.includes(tag)
                        ? 'border-forest bg-forest text-cream'
                        : 'border-border-warm text-ink hover:border-sand'
                    }`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
