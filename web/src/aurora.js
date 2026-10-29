// The Universal Team Hub's background: three soft brand-colour glows drifting behind the page; the green one follows
// the pointer. Same colours, sizes and speeds as the hub; still for people who turn motion off.
const COLOURS = { light: ['#109648', '#4d458a', '#bd2239'], dark: ['#4fd98a', '#8f87dd', '#ef5a6f'] };

export function startAurora(canvas) {
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const au = { t: 0, last: performance.now(), fx: 0.5, fy: 0.55, tx: null, ty: null, until: 0 };
  const onPtr = e => {
    au.tx = e.clientX / window.innerWidth; au.ty = e.clientY / window.innerHeight;
    au.until = e.pointerType === 'mouse' ? Infinity : performance.now() + 2500;
  };
  const onOut = e => { if (!e.relatedTarget) au.until = 0; };
  window.addEventListener('pointermove', onPtr, { passive: true });
  window.addEventListener('pointerdown', onPtr, { passive: true });
  document.addEventListener('pointerout', onOut);
  let raf = 0;
  const frame = now => {
    if (!document.hidden) {
      const dt = Math.min(0.05, (now - au.last) / 1000); au.t += still ? 0 : dt;
      const w = Math.ceil(window.innerWidth / 2), h = Math.ceil(window.innerHeight / 2);  // half size: blurry anyway
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      const c = canvas.getContext('2d'), dark = document.documentElement.dataset.theme === 'dark';
      const cols = COLOURS[dark ? 'dark' : 'light'];
      const follow = !still && au.tx !== null && now < au.until, t = au.t;
      au.fx += ((follow ? au.tx : 0.5 + 0.3 * Math.sin(t * 0.07)) - au.fx) * (follow ? 0.025 : 0.01);
      au.fy += ((follow ? au.ty : 0.55 + 0.25 * Math.cos(t * 0.09)) - au.fy) * (follow ? 0.025 : 0.01);
      c.clearRect(0, 0, w, h);
      c.globalCompositeOperation = dark ? 'lighter' : 'source-over';
      const R = Math.min(190, Math.max(100, Math.max(w, h) * 0.22));
      [2, 1, 0].forEach(i => {
        const ph = i * 2.1, sp = 0.05 + i * 0.018;
        const x = (i ? 0.5 + 0.38 * Math.sin(t * sp + ph) : au.fx) * w;
        const y = (i ? 0.5 + 0.34 * Math.cos(t * sp * 1.3 + ph) : au.fy) * h;
        const g = c.createRadialGradient(x, y, 0, x, y, R * (i ? 1 : 0.85)), n = parseInt(cols[i].slice(1), 16);
        const rgb = `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`, a = dark ? 0.3 : i ? 0.27 : 0.32;
        g.addColorStop(0, `rgba(${rgb},${a})`); g.addColorStop(1, `rgba(${rgb},0)`);
        c.fillStyle = g; c.fillRect(0, 0, w, h);
      });
      c.globalCompositeOperation = 'source-over';
    }
    au.last = now;
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener('pointermove', onPtr); window.removeEventListener('pointerdown', onPtr);
    document.removeEventListener('pointerout', onOut);
  };
}
