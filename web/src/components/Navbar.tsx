import { useState, useEffect } from 'react';

const navLinks = [
  { label: 'SEARCH', href: '#search' },
  { label: 'SURPRISE', href: '#surprise' },
  { label: 'MAP', href: '#map' },
  { label: 'BROWSE', href: '#browse' },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-cream/85 backdrop-blur-lg border-b border-border-warm'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2 group">
            {/* speech bubble + fork icon */}
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              {/* speech bubble */}
              <path d="M3 5 Q3 3, 5 3 L19 3 Q21 3, 21 5 L21 15 Q21 17, 19 17 L9 17 L5 20 L5 17 L5 17 Q3 17, 3 15 Z" fill="#C94B1F"/>
              {/* fork tines (3 small vertical lines inside the bubble) */}
              <rect x="10" y="7" width="1" height="5" fill="#FAF6F0"/>
              <rect x="12" y="7" width="1" height="5" fill="#FAF6F0"/>
              <rect x="14" y="7" width="1" height="5" fill="#FAF6F0"/>
              {/* fork handle */}
              <rect x="11" y="10" width="3" height="1" fill="#FAF6F0"/>
            </svg>
            <span className="font-display text-2xl font-semibold text-ink tracking-tight">
              MenuElf
            </span>
          </a>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-10">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm uppercase tracking-widest font-semibold text-ink hover:text-terracotta transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded-lg hover:bg-paper transition-colors"
            aria-label="Toggle menu"
          >
            <svg
              className="w-6 h-6 text-ink"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              {mobileOpen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden bg-cream/95 backdrop-blur-lg border-t border-border-warm">
          <div className="px-4 py-3 space-y-2">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="block px-3 py-2 text-sm uppercase tracking-widest font-semibold text-ink hover:text-terracotta transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
