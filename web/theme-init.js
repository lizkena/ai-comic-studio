// Applied before first paint. Preferences belong to this application's WebView profile.
(() => {
  const key = 'comic-studio-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  let mode = 'dark';
  try { mode = localStorage.getItem(key) || 'dark'; } catch {}
  if (!['light','dark','system'].includes(mode)) mode = 'dark';
  const apply = () => {
    document.documentElement.dataset.themeMode = mode;
    document.documentElement.dataset.theme = mode === 'system' ? (media.matches ? 'dark' : 'light') : mode;
  };
  window.comicTheme = {
    get: () => mode,
    set: value => {
      if (!['light','dark','system'].includes(value)) return;
      mode = value;
      try {localStorage.setItem(key, mode);} catch {}
      apply();
    },
  };
  media.addEventListener('change', apply);
  window.addEventListener('storage', event => {
    if (event.key === key) {mode = ['light','dark','system'].includes(event.newValue) ? event.newValue : 'dark'; apply();}
  });
  apply();
})();
