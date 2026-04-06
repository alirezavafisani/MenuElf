export default function Hero() {
  const quickSearches = ['Pizza', 'Sushi', 'Vegan', 'Under $10', 'Spicy'];

  const handleSearch = (query: string) => {
    const searchSection = document.getElementById('search');
    if (searchSection) {
      searchSection.scrollIntoView({ behavior: 'smooth' });
      // Parse "Under $X" style queries into price filter
      const underMatch = query.match(/^Under \$(\d+)$/i);
      if (underMatch) {
        window.dispatchEvent(
          new CustomEvent('menuelf:search', {
            detail: { query: '', priceMax: Number(underMatch[1]) },
          })
        );
      } else {
        window.dispatchEvent(
          new CustomEvent('menuelf:search', { detail: { query } })
        );
      }
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const input = e.currentTarget.querySelector('input') as HTMLInputElement;
    if (input.value.trim()) {
      handleSearch(input.value.trim());
      input.value = '';
    }
  };

  return (
    <section className="relative pt-32 pb-20 px-4 overflow-hidden">
      {/* Background photo with overlay */}
      <div
        className="absolute inset-0 -z-20"
        style={{
          backgroundImage: 'url(https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=2000&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      />
      <div className="absolute inset-0 -z-10 bg-bg/[0.92]" />
      {/* Subtle accent blobs */}
      <div className="absolute top-20 right-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-80 h-80 bg-amber-200/20 rounded-full blur-3xl pointer-events-none" />

      <div className="relative max-w-4xl mx-auto text-center">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-stone-900 tracking-tight leading-tight">
          Discover your next favorite
          <span className="text-accent"> dish</span> in Calgary
        </h1>
        <p className="mt-5 text-lg sm:text-xl text-stone-500 max-w-2xl mx-auto">
          AI-powered search across 487 restaurants and 18,000+ menu items
        </p>

        {/* Search bar */}
        <form
          onSubmit={handleSubmit}
          className="mt-10 max-w-2xl mx-auto flex items-center bg-white rounded-full shadow-lg shadow-stone-200/50 border border-stone-200 hover:shadow-xl hover:border-stone-300 transition-all duration-300 focus-within:shadow-xl focus-within:border-accent/40 focus-within:ring-2 focus-within:ring-accent/10"
        >
          <svg className="ml-5 w-5 h-5 text-stone-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="What are you craving? Try 'spicy ramen under $15'"
            className="flex-1 px-4 py-4 bg-transparent text-stone-900 placeholder-stone-400 outline-none text-base sm:text-lg"
          />
          <button
            type="submit"
            className="mr-2 px-6 py-2.5 bg-accent hover:bg-accent-hover text-white font-semibold rounded-full transition-colors duration-200 flex-shrink-0"
          >
            Search
          </button>
        </form>

        {/* Quick filters */}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {quickSearches.map((q) => (
            <button
              key={q}
              onClick={() => handleSearch(q)}
              className="px-4 py-1.5 text-sm font-medium text-stone-600 bg-white border border-stone-200 rounded-full hover:border-accent hover:text-accent hover:bg-orange-50 transition-all duration-200"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
