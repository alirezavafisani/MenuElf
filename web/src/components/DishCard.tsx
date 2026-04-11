import type { Dish } from '../types';

function formatPrice(price: number | string | null): string {
  if (price === null || price === undefined || price === '') return '';
  if (typeof price === 'number') return price > 0 ? `$${price.toFixed(2)}` : '';
  const cleaned = String(price).replace(/[^0-9.-]/g, '').split('-')[0];
  const num = parseFloat(cleaned);
  return !isNaN(num) && num > 0 ? `$${num.toFixed(2)}` : '';
}

interface DishCardProps {
  dish: Dish;
  index: number;
  onOpenChat: (slug: string, name: string) => void;
  photoUrl?: string;
}

export default function DishCard({ dish, index, onOpenChat, photoUrl }: DishCardProps) {
  const price = formatPrice(dish.price);

  return (
    <div
      className="card-enter bg-paper border border-border-warm p-6 md:p-7 hover:-translate-y-0.5 hover:border-terracotta transition-all duration-200 flex flex-col"
      style={{ animationDelay: `${index * 60}ms` }}
      data-testid="dish-card"
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="font-display text-xl md:text-2xl font-medium text-ink leading-snug">
          {dish.name}
        </h3>
        {price && (
          <span className="font-display text-lg md:text-xl font-semibold text-terracotta whitespace-nowrap">
            {price}
          </span>
        )}
      </div>

      <button
        onClick={() => onOpenChat(dish.restaurant_slug, dish.restaurant_name)}
        className="flex items-center gap-2 font-serif italic text-sm text-sand hover:text-terracotta transition-colors mb-3 text-left"
      >
        {photoUrl && (
          <img
            src={photoUrl}
            alt=""
            className="w-6 h-6 rounded-full object-cover flex-shrink-0"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        )}
        at {dish.restaurant_name} →
      </button>

      {dish.description && (
        <p className="text-sm md:text-base text-ink/75 leading-relaxed line-clamp-3 mb-4 flex-1">
          {dish.description}
        </p>
      )}

      <div className="flex flex-wrap gap-2 mt-auto">
        {dish.category && (
          <span className="px-2.5 py-0.5 text-xs font-medium bg-border-warm/60 text-ink rounded-full">
            {dish.category}
          </span>
        )}
        {dish.dietary_info?.map((tag) => (
          <span
            key={tag}
            className="px-2.5 py-0.5 text-xs font-medium bg-forest/10 text-forest rounded-full"
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}
