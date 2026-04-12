import StatsCounter from './StatsCounter';

export default function Footer() {
  return (
    <footer id="about" className="bg-paper border-t border-border-warm pt-6 pb-16 md:pt-8 md:pb-20 px-4">
      <div className="max-w-4xl mx-auto text-center">
        <StatsCounter />
        <div className="flex items-center justify-center gap-2 mb-6">
          <span className="font-display text-3xl font-semibold text-terracotta">
            MenuElf
          </span>
        </div>
        <p className="font-serif italic text-lg text-sand max-w-xl mx-auto mb-10 leading-relaxed">
          built with care in Calgary. powered by FastAPI, React, and too much OpenAI.
        </p>

        {/* Links */}
        <div className="flex justify-center gap-8 mb-10">
          <a
            href="https://github.com/alirezavafisani/MenuElf"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm uppercase tracking-widest font-semibold text-ink hover:text-terracotta transition-colors"
          >
            GitHub
          </a>
          <a
            href="https://linkedin.com/in/alireza-vafisani"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm uppercase tracking-widest font-semibold text-ink hover:text-terracotta transition-colors"
          >
            LinkedIn
          </a>
        </div>

        <div className="font-serif italic text-xs text-sand">
          Built by Alireza Vafisani · © 2025–2026
        </div>
      </div>
    </footer>
  );
}
