export default function Footer() {
  return (
    <footer id="about" className="bg-white border-t border-stone-200 py-16 px-4">
      <div className="max-w-4xl mx-auto text-center">
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="text-2xl font-bold text-accent">MenuElf</span>
        </div>
        <p className="text-stone-500 max-w-xl mx-auto mb-8">
          MenuElf is an AI-powered restaurant discovery engine for Calgary, built with
          FastAPI, React, OpenAI embeddings, and GPT-4o-mini.
        </p>

        {/* Links */}
        <div className="flex justify-center gap-6 mb-8">
          <a
            href="https://github.com/alirezavafisani/MenuElf"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-stone-500 hover:text-accent transition-colors"
          >
            GitHub
          </a>
          <a
            href="https://linkedin.com/in/alireza-vafisani"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-stone-500 hover:text-accent transition-colors"
          >
            LinkedIn
          </a>
        </div>

        <div className="text-xs text-stone-400">
          Built by Alireza Vafisani · © 2025–2026
        </div>
      </div>
    </footer>
  );
}
