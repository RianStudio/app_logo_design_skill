// Tide theme: Tailwind preset. Load theme.css first; values read its CSS variables.
module.exports = {
  theme: {
    extend: {
      colors: {
        'bg': 'var(--c-bg)',
        'surface': 'var(--c-surface)',
        'surface-2': 'var(--c-surface-2)',
        'border': 'var(--c-border)',
        'text': 'var(--c-text)',
        'text-2': 'var(--c-text-2)',
        'text-3': 'var(--c-text-3)',
        'primary': 'var(--c-primary)',
        'on-primary': 'var(--c-on-primary)',
        'primary-container': 'var(--c-primary-container)',
        'on-primary-container': 'var(--c-on-primary-container)',
        'success': 'var(--c-success)',
        'success-container': 'var(--c-success-container)',
        'warning': 'var(--c-warning)',
        'warning-container': 'var(--c-warning-container)',
        'danger': 'var(--c-danger)',
        'danger-container': 'var(--c-danger-container)',
        'info': 'var(--c-info)',
        'info-container': 'var(--c-info-container)',
        'glaze': 'var(--c-glaze)',
        'glaze-tint': 'var(--c-glaze-tint)',
        'glaze-lip': 'var(--c-glaze-lip)',
        'glaze-pool': 'var(--c-glaze-pool)'
      },
      borderRadius: {
        'xs': 'var(--r-xs)',
        'sm': 'var(--r-sm)',
        'md': 'var(--r-md)',
        'lg': 'var(--r-lg)',
        'xl': 'var(--r-xl)',
        'full': 'var(--r-full)'
      },
      boxShadow: { e1: 'var(--elev-1)', e2: 'var(--elev-2)', e3: 'var(--elev-3)' },
      fontFamily: { sans: ['var(--font)'], mono: ['var(--font-mono)'] },
    },
  },
};
