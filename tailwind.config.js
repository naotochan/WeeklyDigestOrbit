/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./docs/index.html",
    "./docs/archives/*.html",
    "./templates/*.j2",
  ],
  safelist: [
    { pattern: /(bg|text|border|from|to|shadow)-(japan|orbit|tech|gtech|paper)-(50|100|200|300|400|500|600|700)/ },
    { pattern: /(bg|text|border)-(japan|orbit|tech|gtech|paper)-(50|100|200|300|400|500|600|700)/ },
  ],
  theme: {
    extend: {
      maxWidth: {
        'mid-xl': '1700px',
      },
      colors: {
        japan: {
          50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5',
          400: '#f87171', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c',
        },
        orbit: {
          50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc',
          400: '#818cf8', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca',
        },
        tech: {
          50: '#ecfdf5', 100: '#d1fae5', 200: '#a7f3d0', 300: '#6ee7b7',
          400: '#34d399', 500: '#10b981', 600: '#059669', 700: '#047857',
        },
        gtech: {
          50: '#ecfeff', 100: '#cffafe', 200: '#a5f3fc', 300: '#67e8f9',
          400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2', 700: '#0e7490',
        },
        paper: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
        },
      },
    },
  },
  plugins: [],
}
