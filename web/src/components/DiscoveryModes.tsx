import { useState } from 'react';
import { getRandomDish } from '../api';
import type { Dish } from '../types';

interface DiscoveryModesProps {
  onOpenChat: (slug: string, name: string) => void;
}

const CATEGORY_TILES: Array<{
  label: string;
  query: string;
  photo: string;
}> = [
  {
    label: 'Burgers',
    query: 'burger',
    photo:
      'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Pizza',
    query: 'pizza',
    photo:
      'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Sushi',
    query: 'sushi',
    photo:
      'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Ramen',
    query: 'ramen',
    photo:
      'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Shawarma',
    query: 'shawarma',
    photo:
      'https://images.unsplash.com/photo-1633321702518-7feccafb94d5?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Thai',
    query: 'thai curry',
    photo:
      'https://images.unsplash.com/photo-1559314809-0d155014e29e?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Brunch',
    query: 'brunch',
    photo:
      'https://images.unsplash.com/photo-1533920379810-6bedac961555?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Dessert',
    query: 'dessert',
    photo:
      'https://images.unsplash.com/photo-1551024601-bec78aea704b?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Indian',
    query: 'indian curry',
    photo:
      'https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Pasta',
    query: 'pasta',
    photo:
      'https://images.unsplash.com/photo-1551892374-ecf8754cf8b0?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Tacos',
    query: 'tacos',
    photo:
      'https://images.unsplash.com/photo-1565299585323-38d6b0865b47?auto=format&fit=crop&w=400&q=80',
  },
  {
    label: 'Korean',
    query: 'korean',
    photo:
      'https://images.unsplash.com/photo-1553163147-622ab57be1c7?auto=format&fit=crop&w=400&q=80',
  },
];

function formatPrice(price: number | string | null | undefined): string {
  if (price === null || price === undefined || price === '') return '';
  if (typeof price === 'number') return price > 0 ? `$${price.toFixed(2)}` : '';
  const cleaned = String(price).replace(/[^0-9.-]/g, '').split('-')[0];
  const num = parseFloat(cleaned);
  return !isNaN(num) && num > 0 ? `$${num.toFixed(2)}` : '';
}

export default function DiscoveryModes({ onOpenChat }: DiscoveryModesProps) {
  const [dish, setDish] = useState<Dish | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [maxPrice, setMaxPrice] = useState<number | undefined>(undefined);
  const [rollId, setRollId] = useState(0);

  const roll = async () => {
    setLoading(true);
    setError('');
    try {
      const d = await getRandomDish(maxPrice);
      setDish(d);
      setRollId((n) => n + 1);
    } catch {
      setError('No dishes matched that budget. Try a higher max.');
      setDish(null);
    } finally {
      setLoading(false);
    }
  };

  const pickCategory = (q: string) => {
    const section = document.getElementById('search');
    if (section) section.scrollIntoView({ behavior: 'smooth' });
    window.dispatchEvent(
      new CustomEvent('menuelf:search', {
        detail: { query: q, useCategory: true },
      })
    );
  };

  const price = dish ? formatPrice(dish.price) : '';

  return (
    <section className="relative pt-16 pb-8 md:pt-24 md:pb-10 px-4 border-t border-border-warm">
      <div className="max-w-7xl mx-auto">
        {/* ─── Hungry mode ─── */}
        <div className="text-center mb-8">
          <p className="font-serif italic text-base text-sand mb-3">can't decide?</p>
          <h2 className="font-display text-4xl md:text-6xl font-medium text-ink tracking-tight">
            Let the elf pick.
          </h2>
        </div>

        <div className="max-w-3xl mx-auto">
          {/* Price selector */}
          <div className="flex items-center justify-center gap-3 mb-6 flex-wrap">
            <span className="font-serif italic text-sm text-sand">budget:</span>
            {[
              { label: '$10', v: 10 },
              { label: '$15', v: 15 },
              { label: '$20', v: 20 },
              { label: '$30', v: 30 },
              { label: 'any', v: undefined },
            ].map((opt) => (
              <button
                key={opt.label}
                onClick={() => setMaxPrice(opt.v)}
                className={`px-4 py-1.5 text-sm font-medium rounded-full border transition-all ${
                  maxPrice === opt.v
                    ? 'border-terracotta bg-terracotta text-cream'
                    : 'border-border-warm text-ink hover:border-sand'
                }`}
                data-testid={`budget-${opt.label}`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Result card or CTA */}
          {!dish && !loading && (
            <button
              onClick={roll}
              data-testid="hungry-button"
              className="w-full bg-terracotta hover:bg-terracotta-dark text-cream font-display text-2xl md:text-4xl font-medium py-10 md:py-14 rounded-sm transition-colors shadow-[0_8px_30px_-8px_rgba(201,75,31,0.5)] hover:shadow-[0_12px_40px_-8px_rgba(201,75,31,0.6)]"
            >
              Feed me something random
            </button>
          )}

          {loading && (
            <div className="bg-paper border border-border-warm rounded-sm p-12 text-center">
              <p className="font-serif italic text-xl text-sand">the elf is thinking...</p>
            </div>
          )}

          {error && !loading && (
            <div className="text-center py-6">
              <p className="font-serif italic text-burgundy">{error}</p>
              <button
                onClick={roll}
                className="mt-4 text-sm uppercase tracking-widest text-ink hover:text-terracotta underline underline-offset-4"
              >
                Try again
              </button>
            </div>
          )}

          {dish && !loading && (
            <div
              key={rollId}
              data-testid="random-dish-card"
              className="pop-in bg-paper border border-border-warm rounded-sm p-8 md:p-12"
            >
              <p className="font-serif italic text-sm text-sand mb-3">tonight, try</p>
              <h3
                className="font-display text-3xl md:text-5xl font-medium text-ink leading-tight mb-3"
                data-testid="random-dish-name"
              >
                {dish.name}
              </h3>
              {price && (
                <p className="font-display text-2xl md:text-3xl text-terracotta font-semibold mb-4">
                  {price}
                </p>
              )}
              {dish.description && (
                <p className="text-base md:text-lg text-ink/80 leading-relaxed mb-6 max-w-2xl">
                  {dish.description}
                </p>
              )}
              <p className="font-serif italic text-sand mb-6">
                at{' '}
                <button
                  onClick={() => onOpenChat(dish.restaurant_slug, dish.restaurant_name)}
                  className="not-italic font-sans font-semibold text-ink underline underline-offset-4 decoration-terracotta hover:text-terracotta transition-colors"
                >
                  {dish.restaurant_name}
                </button>
              </p>
              <div className="flex items-center gap-4 flex-wrap">
                <button
                  onClick={roll}
                  data-testid="try-another"
                  className="px-6 py-3 bg-ink hover:bg-terracotta text-cream text-sm uppercase tracking-widest font-semibold transition-colors"
                >
                  Try another
                </button>
                <button
                  onClick={() => onOpenChat(dish.restaurant_slug, dish.restaurant_name)}
                  className="px-6 py-3 border border-ink text-ink hover:bg-ink hover:text-cream text-sm uppercase tracking-widest font-semibold transition-colors"
                >
                  Ask the menu
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ─── Category tiles ─── */}
        <div className="mt-24 md:mt-32">
          <div className="flex items-baseline justify-between mb-8 flex-wrap gap-3">
            <h2 className="font-display text-3xl md:text-5xl font-medium text-ink tracking-tight">
              or browse by craving
            </h2>
            <p className="font-serif italic text-sand">twelve ways to start</p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 md:gap-4">
            {CATEGORY_TILES.map((tile) => (
              <button
                key={tile.label}
                onClick={() => pickCategory(tile.query)}
                data-testid={`tile-${tile.label.toLowerCase()}`}
                className="group relative aspect-square overflow-hidden rounded-sm bg-ink"
              >
                <img
                  src={tile.photo}
                  alt={tile.label}
                  loading="lazy"
                  className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 grayscale-[10%] group-hover:grayscale-0"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/20 to-transparent group-hover:from-terracotta/70 transition-colors" />
                <div className="absolute bottom-0 left-0 p-4 md:p-5">
                  <span className="font-display text-xl md:text-2xl font-medium text-cream drop-shadow-sm">
                    {tile.label}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
