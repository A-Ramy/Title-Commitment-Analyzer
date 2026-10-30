// Shared pieces in the Universal Team Hub's design: icons, header, pill groups, menus, dialogs, notices.
import { createContext } from 'preact';
import { useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';

// ---------------------------------------------------------------- icons (the hub's line icons)
const P = {
  sun: 'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41',
  moon: 'M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z',
  chevron: 'm6 9 6 6 6-6', back: 'm15 18-6-6 6-6', right: 'm9 18 6-6-6-6', check: 'M20 6 9 17l-5-5',
  calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  note: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3', plus: 'M5 12h14M12 5v14',
  refresh: 'M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12',
  search: 'm21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z', settings:
    'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  file: 'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2zM14 2v6h6',
  flag: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7',
  camera: 'M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3zM12 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  x: 'M18 6 6 18M6 6l12 12', out: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  sheet: 'M3 3h18v18H3zM3 9h18M3 15h18M9 3v18', book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15zM20 17v5H6.5a2.5 2.5 0 0 1 0-5',
  cap: 'M22 10 12 5 2 10l10 5 10-5zM6 12v5c3 3 9 3 12 0v-5', folder: 'M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
  alert: 'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01',
};
export function Icon({ name, size = 16, stroke = 2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width={stroke}
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none">
      {name === 'sun' && <circle cx="12" cy="12" r="4" />}
      <path d={P[name]} />
    </svg>
  );
}

export const Spinner = () => <span class="spin" aria-hidden="true" />;

// ---------------------------------------------------------------- pill groups
export function Seg({ options, value, onChange, label, cls = '' }) {
  return (
    <div class={`seg ${cls}`} role="group" aria-label={label}>
      {options.map(o => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}
          title={o.title} aria-label={o.label ? undefined : o.title}>
          {o.icon && <Icon name={o.icon} />}
          {o.label && <span class={o.hideOnPhone ? 'lbl' : ''}>{o.label}</span>}
          {o.n !== undefined && <span class="n">{o.n}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- menus anchored to a button
export function useMenu() {
  const [at, setAt] = useState(null);
  const open = useCallback(e => {
    const r = e.currentTarget.getBoundingClientRect();
    const below = r.bottom + 6, right = window.innerWidth - r.right;
    setAt(r.left > window.innerWidth / 2 ? { top: below, right } : { top: below, left: r.left });
  }, []);
  return { at, open, close: () => setAt(null) };
}

export function Menu({ menu, children, label, cls = '', keepOpen = false }) {
  const box = useRef(null);
  useLayoutEffect(() => {  // keep it on screen
    const el = box.current;
    if (!el || !menu.at) return;
    const r = el.getBoundingClientRect();
    if (r.bottom > window.innerHeight - 8) el.style.top = Math.max(8, menu.at.top - r.height - 48) + 'px';
  }, [menu.at]);
  useEffect(() => {
    if (!menu.at) return;
    const key = e => e.key === 'Escape' && menu.close();
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, [menu.at]);
  if (!menu.at) return null;
  return (
    <>
      <div class="scrim" onClick={menu.close} />
      <div class={`menu ${cls}`} ref={box} role={keepOpen ? 'dialog' : 'menu'} aria-label={label} style={menu.at}
        onClick={keepOpen ? undefined : menu.close}>{children}</div>
    </>
  );
}

// ---------------------------------------------------------------- the hub's due date picker
// A month calendar in a menu, as in the Universal Team Hub: today ringed, the chosen day filled, Remove and Set.
// Days only (the title items have a due day, not a time). value and onSet use YYYY-MM-DD; '' removes it.
const WEEK = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const pad = n => String(n).padStart(2, '0');
const isoOf = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export function DatePicker({ menu, value, onSet, label = 'Due Date', title = '', setText = 'Set Due Date' }) {
  const start = value ? new Date(`${value}T12:00`) : new Date();
  const [view, setView] = useState({ y: start.getFullYear(), m: start.getMonth() });
  const [pick, setPick] = useState(value || '');
  useEffect(() => {  // each time it opens: the saved day, and its month
    if (!menu.at) return;
    const d = value ? new Date(`${value}T12:00`) : new Date();
    setView({ y: d.getFullYear(), m: d.getMonth() }); setPick(value || '');
  }, [menu.at]);
  const today = isoOf(new Date());
  const first = new Date(view.y, view.m, 1).getDay(), days = new Date(view.y, view.m + 1, 0).getDate();
  const cells = [...Array(first).fill(0), ...Array.from({ length: days }, (_, i) => i + 1)];
  const shift = n => setView(v => { const m = v.m + n; return { y: v.y + Math.floor(m / 12), m: ((m % 12) + 12) % 12 }; });
  const done = v => { menu.close(); onSet(v); };
  const month = new Date(view.y, view.m, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
  const summary = pick ? new Date(`${pick}T12:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : '';
  return (
    <Menu menu={menu} label={label} cls="dp-menu" keepOpen>
      <div class="dp-title"><b>{label}</b>{title && <span>{title}</span>}</div>
      <div class="dp-nav">
        <button type="button" class="dp-round" aria-label="Previous month" onClick={() => shift(-1)}><Icon name="back" stroke={2.5} /></button>
        <span>{month}</span>
        <button type="button" class="dp-round" aria-label="Next month" onClick={() => shift(1)}><Icon name="right" stroke={2.5} /></button>
      </div>
      <div class="dp-grid">
        {WEEK.map(w => <span key={w} class="dp-week">{w}</span>)}
        {cells.map((d, i) => {
          if (!d) return <span key={`b${i}`} />;
          const v = `${view.y}-${pad(view.m + 1)}-${pad(d)}`;
          return (
            <button key={v} type="button" class={`dp-day ${v === pick ? 'on' : ''} ${v === today ? 'today' : ''} ${v < today ? 'past' : ''}`}
              aria-label={v} aria-pressed={v === pick} onClick={() => setPick(v)}>{d}</button>);
        })}
      </div>
      <div class="dp-summary">{pick ? `${label.replace(' Date', '')} ${summary}` : 'Pick a day on the calendar.'}</div>
      <div class="dp-actions">
        {value && <button type="button" class="dp-remove" onClick={() => done('')}>Remove</button>}
        <button type="button" class="dp-set" disabled={!pick} onClick={() => done(pick)}>{setText}</button>
      </div>
    </Menu>
  );
}

// ---------------------------------------------------------------- dialogs
export function Modal({ title, children, onClose, wide }) {
  useEffect(() => {
    const key = e => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, [onClose]);
  return (
    <div class="modal-scrim" onClick={e => e.target === e.currentTarget && onClose()}>
      <div class="modal" role="dialog" aria-modal="true" aria-label={title} style={wide ? 'max-width:760px' : ''}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- toasts
const ToastCtx = createContext(() => {});
export function ToastHost({ children }) {
  const [toast, setToast] = useState(null);
  const show = useCallback((text, err = false) => {
    setToast({ text, err, id: Date.now() });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.err ? 6000 : 3000);
    return () => clearTimeout(t);
  }, [toast]);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && <div class={`toast ${toast.err ? 'err' : ''}`} role="status">{toast.text}</div>}
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

// ---------------------------------------------------------------- formatting
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function fmtDate(iso, year = true) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}${year ? ', ' + y : ''}`;
}
export function daysUntil(iso) {
  if (!iso) return null;
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(y, m - 1, d) - today) / 86400000);
}
export const money = v => (v == null ? '' : '$' + Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 }));
export const when = ts => {
  const d = ts?.toDate ? ts.toDate() : ts ? new Date(ts) : null;
  return d ? d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
};
export const initials = s => (s || '').split(/[\s@.]/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('');
