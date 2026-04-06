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
      className="card-enter bg-white rounded-xl border border-stone-200 p-5 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 flex flex-col"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="font-semibold text-stone-900 leading-snug line-clamp-2">
          {dish.name}
        </h3>
        {price && (
          <span className="text-accent font-bold text-sm whitespace-nowrap">
            {price}
          </span>
        )}
      </div>

      <button
        onClick={() => onOpenChat(dish.restaurant_slug, dish.restaurant_name)}
        className="flex items-center gap-2 text-xs text-stone-500 hover:text-accent transition-colors mb-2 text-left"
      >
        {photoUrl && (
          <img
            src={photoUrl}
            alt=""
            className="w-6 h-6 rounded-full object-cover flex-shrink-0"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        )}
        {dish.restaurant_name} →
      </button>

      {dish.description && (
        <p className="text-sm text-stone-500 line-clamp-2 mb-3 flex-1">
          {dish.description}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5 mt-auto">
        {dish.category && (
          <span className="px-2 py-0.5 text-xs font-medium bg-stone-100 text-stone-600 rounded-full">
            {dish.category}
          </span>
        )}
        {dish.dietary_info?.map((tag) => (
          <span
            key={tag}
            className="px-2 py-0.5 text-xs font-medium bg-green-50 text-green-700 rounded-full"
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}
