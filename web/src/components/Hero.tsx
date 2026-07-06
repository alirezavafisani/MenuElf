import { useState, useEffect, useRef } from 'react';

const SUGGESTIONS = [
  'spicy ramen under $15',
  'handmade pasta',
  'Korean fried chicken',
  'bright morning brunch',
  'a dessert worth the trip',
];

const RECENTS_KEY = 'menuelf:recent';

export function readRecents(): string[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((s) => typeof s === 'string').slice(0, 4) : [];
  } catch {
    return [];
  }
}

export function saveRecent(q: string) {
  try {
    const next = [q, ...readRecents().filter((r) => r.toLowerCase() !== q.toLowerCase())].slice(0, 4);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
  } catch {
    /* private mode, fine */
  }
}

function getTimeWord(): string {
  const hour = new Date().getHours();
  return hour >= 5 && hour < 15 ? 'today' : 'tonight';
}

export default function Hero() {
  const [value, setValue] = useState('');
  const [timeWord] = useState(getTimeWord);
  const [recents, setRecents] = useState<string[]>(readRecents);
  const inputRef = useRef<HTMLInputElement>(null);

  // "/" anywhere focuses the search, the way people expect from tools they
  // actually live in. Ignored while already typing somewhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return;
      e.preventDefault();
      inputRef.current?.focus();
      inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Lets any part of the app (results header, navbar) send the visitor back
  // here with the cursor already in the box.
  useEffect(() => {
    const handler = () => {
      inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      inputRef.current?.focus();
    };
    window.addEventListener('menuelf:focus-search', handler);
    return () => window.removeEventListener('menuelf:focus-search', handler);
  }, []);

  // Refresh the recents row after any search, wherever it started.
  useEffect(() => {
    const handler = () => setRecents(readRecents());
    window.addEventListener('menuelf:search', handler);
    return () => window.removeEventListener('menuelf:search', handler);
  }, []);

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
    if (q) fireSearch(q);
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
              Type what you're craving. We'll find it on a real menu near you.
            </p>

            {/* Minimal search — bottom-border only */}
            <form onSubmit={onSubmit} className="mt-10 max-w-xl" role="search">
              <div className="flex items-center gap-3 border-b-2 border-ink py-3 focus-within:border-terracotta transition-colors">
                <svg
                  className="w-5 h-5 text-ink flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <input
                  ref={inputRef}
                  type="text"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Try: spicy ramen under $15"
                  aria-label="Search dishes across Calgary menus"
                  enterKeyHint="search"
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

            {recents.length > 0 && (
              <p className="mt-2 font-serif italic text-base text-sand" data-testid="recent-searches">
                Recent:{' '}
                {recents.map((s, i) => (
                  <span key={s}>
                    <button
                      onClick={() => {
                        setValue(s);
                        fireSearch(s);
                      }}
                      className="underline underline-offset-4 decoration-sand/40 hover:decoration-terracotta hover:text-terracotta transition-colors"
                    >
                      {s}
                    </button>
                    {i < recents.length - 1 && <span className="text-sand/50"> · </span>}
                  </span>
                ))}
              </p>
            )}
          </div>

          {/* Right — 40% editorial photo */}
          <div className="hidden md:block md:col-span-2">
            <div className="overflow-hidden">
              <img
                src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=85"
                alt="A beautifully plated dish"
                fetchPriority="high"
                className="w-full h-[520px] object-cover grayscale-[15%] contrast-[1.05]"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
