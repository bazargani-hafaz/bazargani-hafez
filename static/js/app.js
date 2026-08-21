(() => {
  document.querySelectorAll('img').forEach(img => {
    img.loading = 'lazy';
    img.decoding = 'async';
  });

  const root = document.documentElement;
  const toggle = document.getElementById('themeToggle');
  const saved = localStorage.getItem('hafez-theme');
  if (saved) root.dataset.theme = saved;
  const syncIcon = () => { if (toggle) toggle.textContent = root.dataset.theme === 'light' ? '☾' : '☀'; };
  syncIcon();
  toggle?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    localStorage.setItem('hafez-theme', next);
    syncIcon();
  });

  document.querySelectorAll('.card,.cat').forEach(el => {
    el.addEventListener('pointermove', e => {
      if (window.innerWidth < 900) return;
      const r = el.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width - .5) * 2;
      const y = ((e.clientY - r.top) / r.height - .5) * 2;
      el.style.transform = `translateY(-6px) rotateX(${y * -1.2}deg) rotateY(${x * 1.2}deg)`;
    });
    el.addEventListener('pointerleave', () => { el.style.transform = ''; });
  });
})();
