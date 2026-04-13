import StatsCounter from './StatsCounter';

export default function Footer() {
  return (
    <footer id="about" className="bg-paper border-t border-border-warm pt-6 pb-10 md:pt-8 md:pb-12 px-4">
      <div className="max-w-4xl mx-auto text-center">
        <StatsCounter />
        <p className="text-sm text-sand">
          Built by Alireza Vafisani · © 2025–2026 ·{' '}
          <a
            href="https://linkedin.com/in/alireza-vafisani"
            target="_blank"
            rel="noopener noreferrer"
            className="text-terracotta hover:underline underline-offset-4"
          >
            LinkedIn
          </a>
        </p>
      </div>
    </footer>
  );
}
