/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // New editorial palette (chunk 3)
        ink: '#1A1511',
        cream: '#FAF6F0',
        paper: '#F5EFE6',
        terracotta: '#C94B1F',
        'terracotta-dark': '#9E3A17',
        burgundy: '#7A2E1F',
        forest: '#4A5D3F',
        mustard: '#D4A574',
        // Named "sand" instead of "stone" to avoid clobbering Tailwind's
        // built-in stone-50..950 palette still referenced in legacy code.
        sand: '#8B7E6E',
        'border-warm': '#E5DDD0',

        // Legacy tokens (kept so nothing mid-migration breaks). These
        // alias to the new palette so components that still reference
        // `accent` or `bg` render in the new colors.
        accent: '#C94B1F',
        'accent-hover': '#9E3A17',
        bg: '#FAF6F0',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
};
