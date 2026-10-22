# Solution: Add support for system dark mode via prefers-color-scheme or manual theme toggle
- **Issue:** [algora-io/algora #222](https://github.com/algora-io/algora/issues/222)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Implementation Patch

```javascript
// diff --git a/tailwind.config.js b/tailwind.config.js
module.exports = {
  darkMode: 'class', // Enable class-based dark mode
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'var(--color-bg)',
        foreground: 'var(--color-fg)',
        surface: 'var(--color-surface)',
        border: 'var(--color-border)',
      },
    },
  },
};
```

```typescript
// diff --git a/src/components/ThemeToggle.tsx b/src/components/ThemeToggle.tsx
// new file mode 100644
import React, { useEffect, useState } from 'react';

type Theme = 'light' | 'dark' | 'system';

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>('system');

  useEffect(() => {
    const saved = (localStorage.getItem('theme') as Theme) || 'system';
    setTheme(saved);
    applyTheme(saved);

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if ((localStorage.getItem('theme') || 'system') === 'system') {
        applyTheme('system');
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const applyTheme = (target: Theme) => {
    const isDark =
      target === 'dark' ||
      (target === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  const handleSelect = (newTheme: Theme) => {
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    applyTheme(newTheme);
  };

  return (
    <div className="flex items-center space-x-1 border border-border rounded-lg p-1 bg-surface">
      <button
        onClick={() => handleSelect('light')}
        className={`px-2 py-1 text-xs rounded ${theme === 'light' ? 'bg-primary text-white' : 'text-gray-500'}`}
        aria-label="Light mode"
      >
        Light
      </button>
      <button
        onClick={() => handleSelect('dark')}
        className={`px-2 py-1 text-xs rounded ${theme === 'dark' ? 'bg-primary text-white' : 'text-gray-500'}`}
        aria-label="Dark mode"
      >
        Dark
      </button>
      <button
        onClick={() => handleSelect('system')}
        className={`px-2 py-1 text-xs rounded ${theme === 'system' ? 'bg-primary text-white' : 'text-gray-500'}`}
        aria-label="System preference"
      >
        Auto
      </button>
    </div>
  );
}
```
