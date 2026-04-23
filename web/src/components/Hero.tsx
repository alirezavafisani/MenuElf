import { useState } from 'react';

const SUGGESTIONS = [
  'spicy ramen under $15',
  'handmade pasta',
  'Korean fried chicken',
  'bright morning brunch',
  'a dessert worth the trip',
];

function getTimeWord(): string {
  const hour = new Date().getHours();
  return hour >= 5 && hour < 15 ? 'today' : 'tonight';
}

export default function Hero() {
  const [value, setValue] = useState('');
  const [timeWord] = useState(getTimeWord);

  const fireSearch = (q: string) => {
    const section = document.getElementById('search-results');
    if (section) section.scrollIntoView({ behavior: 'smooth' });
    const underMatch = q.match(/^under \$(\d+)/i);
    if (underMatch) {
      window.dispatchEvent(
        new CustomEvent('menuelf:search', {
          detail: { query: '', priceMax: Number(underMatch[1]) },
        })
      );
    } else {
      window.dispatchEvent(new CustomEvent('menuelf:search', { detail: { query: q } }));
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (q) {
      fireSearch(q);
      setValue('');
    }
  };

  return (
    <section id="search" className="relative pt-32 pb-16 md:pt-40 md:pb-24 px-4">
      <div className="relative max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-10 md:gap-16 items-center">
          {/* Left — 60% */}
          <div className="md:col-span-3">
            <h1 className="font-display text-6xl sm:text-7xl md:text-8xl font-medium leading-[0.95] tracking-tight text-ink">
              Eat better
              <br />
              <span
                className="italic font-normal"
                style={{ fontVariationSettings: '"opsz" 144' }}
              >
                {timeWord}.
              </span>
            </h1>

            <p className="mt-6 md:mt-8 font-serif italic text-xl md:text-2xl text-sand leading-snug max-w-xl">
              Type what you're craving — we'll find it on a real menu near you.
            </p>

            {/* Minimal search — bottom-border only */}
            <form onSubmit={onSubmit} className="mt-10 max-w-xl">
              <div className="flex items-center gap-3 border-b-2 border-ink py-3 focus-within:border-terracotta transition-colors">
                <svg
                  className="w-5 h-5 text-ink flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Try: spicy ramen under $15"
                  className="flex-1 bg-transparent text-lg md:text-xl text-ink placeholder-sand/70 outline-none font-sans"
                />
                <button
                  type="submit"
                  className="text-sm uppercase tracking-widest text-ink hover:text-terracotta transition-colors font-semibold"
                >
                  Search
                </button>
              </div>
            </form>

            <p className="mt-6 font-serif italic text-base text-sand">
              Try asking:{' '}
              {SUGGESTIONS.map((s, i) => (
                <span key={s}>
                  <button
                    onClick={() => fireSearch(s)}
                    className="underline underline-offset-4 decoration-sand/40 hover:decoration-terracotta hover:text-terracotta transition-colors"
                  >
                    {s}
                  </button>
                  {i < SUGGESTIONS.length - 1 && (
                    <span className="text-sand/50"> · </span>
                  )}
                </span>
              ))}
            </p>
          </div>

          {/* Right — 40% editorial photo */}
          <div className="hidden md:block md:col-span-2">
            <div className="overflow-hidden">
              <img
                src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=85"
                alt="A beautifully plated dish"
                className="w-full h-[520px] object-cover grayscale-[15%] contrast-[1.05]"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
