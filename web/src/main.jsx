import { render } from 'preact';
import { onAuthStateChanged } from 'firebase/auth';
import { useEffect, useRef, useState } from 'preact/hooks';
import './styles.css';
import { api } from './api.js';
import { startAurora } from './aurora.js';
import { auth, signIn, signOutNow, teamAccount } from './firebase.js';
import { go, useRoute } from './router.js';
import { useTheme } from './theme.js';
import { Icon, Menu, Seg, Spinner, ToastHost, initials, useMenu } from './ui.jsx';
import { Deal } from './pages/Deal.jsx';
import { Deals } from './pages/Deals.jsx';
import { Soon } from './pages/Soon.jsx';

const TABS = [
  { value: 'deals', label: 'Deals' }, { value: 'analyze', label: 'Analyze' },
  { value: 'training', label: 'Training' }, { value: 'knowledge', label: 'Knowledge' },
];

function Header({ user, me, page }) {
  const [theme, setTheme] = useTheme();
  const menu = useMenu();
  return (
    <header class="header">
      <div class="header-row">
        <a class="logo" href="#/" aria-label="Title Agent home">
          <img src={theme === 'dark' ? '/logo-full-white.png' : '/logo-full.png'} alt="Total Cash Home Buyers" />
        </a>
        <Seg cls="glass dark-on" label="Theme" value={theme} onChange={setTheme} options={[
          { value: 'light', icon: 'sun', title: 'Light theme' },
          { value: 'dark', icon: 'moon', title: 'Dark theme' }]} />
        {user && (
          <>
            <Seg cls="caps dark-on tabs" label="Pages" value={page === 'deal' ? 'deals' : page}
              onChange={v => go(v === 'deals' ? '' : v)} options={TABS} />
            <button class="avatar" title={user.email} aria-label={`Signed in as ${user.email}`} onClick={menu.open}>
              {initials(user.displayName || user.email)}
            </button>
            <Menu menu={menu} label="Account">
              <div class="label">{user.email}{me?.admin ? ' · admin' : ''}</div>
              <button onClick={() => go('settings')}><Icon name="settings" /> Settings</button>
              <hr />
              <button onClick={signOutNow}><Icon name="out" /> Sign Out</button>
            </Menu>
          </>
        )}
      </div>
    </header>
  );
}

function Gate({ error, busy, onSignIn }) {
  return (
    <section class="card gate">
      <h2>Sign In To The <span class="accent">Title Agent</span></h2>
      <p>Every item needed to close, read from the title commitment. Sign in with your company Google account
        (@totalchb.com).</p>
      <button class="btn primary pill" onClick={onSignIn} disabled={busy}>
        {busy ? <Spinner /> : null} Sign In With Google
      </button>
      {error && <p class="note red" role="alert">{error}</p>}
    </section>
  );
}

function App() {
  const [user, setUser] = useState(undefined);
  const [me, setMe] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const route = useRoute();
  const bg = useRef(null);
  useEffect(() => startAurora(bg.current), []);
  useEffect(() => onAuthStateChanged(auth, u => {
    if (u && !teamAccount(u)) { signOutNow(); setError(`${u.email} doesn't have access. Use your @totalchb.com account.`); setUser(null); return; }
    setUser(u || null);
    if (u) api.me().then(setMe).catch(e => setError(e.message));
    else setMe(null);
  }), []);
  const doSignIn = async () => {
    setBusy(true); setError('');
    try { await signIn(); } catch (e) {
      if (e?.code !== 'auth/popup-closed-by-user' && e?.code !== 'auth/cancelled-popup-request') setError(e.message);
    } finally { setBusy(false); }
  };
  const [page, arg] = route;
  return (
    <ToastHost>
      <canvas ref={bg} class="aurora" aria-hidden="true" />
      <Header user={user} me={me} page={page} />
      <main class="main">
        {user === undefined ? <p class="lede" style="text-align:center"><Spinner /></p>
          : !user ? <Gate error={error} busy={busy} onSignIn={doSignIn} />
            : page === 'deal' ? <Deal id={arg} me={me} />
              : page === 'deals' ? <Deals />
                : <Soon page={page} />}
      </main>
    </ToastHost>
  );
}

render(<App />, document.getElementById('app'));
