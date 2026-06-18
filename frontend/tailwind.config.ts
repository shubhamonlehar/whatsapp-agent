import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211c',
        line: '#d6ddd8',
        panel: '#f7faf8',
        mint: '#2f8c67',
        amber: '#c27803',
        coral: '#d85b45'
      },
      boxShadow: {
        soft: '0 14px 40px rgba(23,33,28,0.08)'
      }
    }
  },
  plugins: []
} satisfies Config;
