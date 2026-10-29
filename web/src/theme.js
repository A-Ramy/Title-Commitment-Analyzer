import { useEffect, useState } from 'preact/hooks';

export function useTheme() {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || 'light');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('ta-theme', theme); } catch { /* private window */ }
  }, [theme]);
  return [theme, setTheme];
}
