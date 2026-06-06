/** @type {import('tailwindcss').Config} */
// Carrera palette — see docs/BRANDING.md
// We remap Tailwind's `blue` scale to teal values so the entire UI
// picks up the brand colour without per-component edits. `carrera`
// and `accent` scales are also available as explicit tokens.
const teal = {
  50: '#F0FDFA',
  100: '#CCFBF1',
  200: '#99F6E4',
  300: '#5EEAD4',
  400: '#2DD4BF',
  500: '#14B8A6',
  600: '#0D9488',
  700: '#0F766E',
  800: '#115E59',
  900: '#134E4A',
  950: '#042F2E',
}

const amber = {
  50: '#FFFBEB',
  100: '#FEF3C7',
  400: '#FBBF24',
  500: '#F59E0B',
  600: '#D97706',
  700: '#B45309',
}

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Brand — teal
        carrera: teal,
        // Remap `blue-*` classes used throughout the UI to the Carrera teal.
        // Existing `text-blue-500`, `bg-blue-600`, etc. become the brand colour.
        blue: teal,
        // Accent — amber
        accent: amber,
      },
      fontFamily: {
        sans: ['Inter', '"Segoe UI"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', '"JetBrains Mono"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
