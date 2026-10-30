// Settings (admins change them; everyone can see them): people, the daily email, due dates, the Google folder, and
// what is connected. Saved through the engine (PUT /v1/settings).
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api.js';
import { useReference, useSettings } from '../data.js';
import { Icon, Spinner, useToast } from '../ui.jsx';

const DUE = [['payoff', 'Payoff Letters'], ['curative', 'Court / Curative'], ['documents', 'Documents'],
  ['bring_down', 'Bring-Down'], ['closing', 'At Closing']];
const lines = v => (v || []).join('\n');
const parse = t => t.replace(/,/g, '\n').split('\n').map(x => x.trim()).filter(Boolean);
const ET = { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' };

// The daily email's last run (written by scripts/daily_email.py).
function emailStatus(last) {
  if (!last) return ['No Run Yet', 'sent from GitHub each weekday at 8:00 AM ET', 'muted'];
  const at = d => new Date(d).toLocaleString('en-US', ET) + ' ET';
  if (last.result === 'scheduled' && last.deliver_at) {
    return new Date() >= new Date(last.deliver_at) ? ['Sending', `last sent ${at(last.deliver_at)} · ${last.detail}`, 'green']
      : ['Scheduled', `goes out ${at(last.deliver_at)} · ${last.detail}`, 'green'];
  }
  if (last.result === 'sent' || last.result === 'test') {
    return ['Sending', `${last.result === 'test' ? 'test sent' : 'last sent'} ${at(last.at)} · ${last.detail}`, 'green'];
  }
  return last.result === 'failed' ? ['Failed', `${at(last.at)} · ${last.detail}`, 'red'] : ['Skipped', `${at(last.at)} · ${last.detail}`, 'muted'];
}

export function Settings({ me }) {
  const toast = useToast();
  const s = useSettings();
  const ref = useReference();
  const admin = !!me?.admin;
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState('');
  const [check, setCheck] = useState(null);
  const [showScript, setShowScript] = useState(false);
  useEffect(() => {
    if (s && !f) {
      setF({ admins: lines(s.admins), tcs: lines(s.tcs), email_recipients: lines(s.email_recipients),
        email_from: s.email_from || 'title-agent@totalchb.com', due_offsets: { ...(s.due_offsets || {}) },
        google_folder_id: s.google_folder_id || '' });
    }
  }, [s]);
  if (!s || !f) return <p class="lede"><Spinner /> Loading settings…</p>;
  const set = k => e => setF({ ...f, [k]: e.currentTarget.value });
  const save = async () => {
    setBusy('save');
    try {
      await api.putSettings({ admins: parse(f.admins), tcs: parse(f.tcs), email_recipients: parse(f.email_recipients),
        email_from: f.email_from.trim(), due_offsets: f.due_offsets, google_folder_id: f.google_folder_id.trim() });
      toast('Saved.');
    } catch (e) { toast(e.message, true); } finally { setBusy(''); }
  };
  const testFolder = async () => {
    setBusy('check'); setCheck(null);
    try { setCheck(await api.googleCheck()); } catch (e) { setCheck({ ok: false, message: e.message }); } finally { setBusy(''); }
  };
  const [eValue, eSub, eCls] = emailStatus(s.email_last_run);
  const google = ref?.connections?.google;
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">{admin ? 'Admins Only' : 'Read Only: Only Admins Change Settings'}</span></div>
          <h1 class="title">Settings</h1>
          <p class="lede">The Team, The Daily Email, Due Dates And The Google Folder.</p>
        </div>
      </section>

      <fieldset disabled={!admin} style="border:none;margin:0;padding:0;display:flex;flex-direction:column;gap:18px;min-width:0">
        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">People</h2>
          <div class="two">
            <label class="field"><span>Admins (Emails, One Per Line)</span>
              <textarea class="input" rows={4} value={f.admins} onInput={set('admins')} /></label>
            <label class="field"><span>TCs (Names, One Per Line)</span>
              <textarea class="input" rows={4} value={f.tcs} onInput={set('tcs')} /></label>
          </div>
          <span class="row-sub">Admins approve lessons and change settings. No admins listed means everyone is an admin (first-time setup).</span>
        </section>

        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">Daily Email</h2>
          <span class="row-sub">Weekdays at 8:00 AM Eastern: every open deal's blockers and items due in the next 3 days.</span>
          <div class="two">
            <label class="field"><span>Send To (Emails, One Per Line)</span>
              <textarea class="input" rows={4} value={f.email_recipients} onInput={set('email_recipients')} /></label>
            <label class="field"><span>Send From</span><input class="input" value={f.email_from} onInput={set('email_from')} /></label>
          </div>
        </section>

        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">Due Dates</h2>
          <span class="row-sub">Days before closing each kind of item is due. Weekends move back to Friday.</span>
          <div class="tiles">
            {DUE.map(([k, label]) => (
              <label key={k} class="field"><span>{label}</span>
                <input class="input" type="number" min={0} max={60} value={f.due_offsets[k] ?? 0}
                  onInput={e => setF({ ...f, due_offsets: { ...f.due_offsets, [k]: Number(e.currentTarget.value) } })} /></label>))}
          </div>
        </section>

        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">Google Exports</h2>
          <label class="field"><span>Google Drive Folder (Paste Its Link)</span>
            <input class="input" value={f.google_folder_id} onInput={set('google_folder_id')}
              placeholder="https://drive.google.com/drive/folders/…" /></label>
          <div class="toolbar">
            <button class="btn glass pill sm" type="button" onClick={testFolder} disabled={!!busy || !google}>
              {busy === 'check' ? <Spinner /> : <Icon name="folder" />} Test Google Folder</button>
            {!google && <span class="row-sub">Not set up yet: follow the steps below.</span>}
            {google === 'script' && <span class="row-sub">Exports are saved by the Google export script, as the person who deployed it.</span>}
          </div>
          {check && <div class={`note ${check.ok ? 'green' : 'red'}`}>{check.message}</div>}
          <button class="link-btn" type="button" style="align-self:flex-start" onClick={() => setShowScript(!showScript)}>
            {showScript ? 'Hide' : 'Show'} The Setup Steps (About 5 Minutes)</button>
          {showScript && (
            <div style="display:flex;flex-direction:column;gap:10px;font-size:14px">
              <ol style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px">
                <li>Signed in as someone who can add files to the folder, go to <b>script.google.com → New project</b> and replace everything with the script below. Save.</li>
                <li><b>Services (+) → Drive API → Add.</b></li>
                <li>Pick <b>setup</b> at the top → <b>Run</b> → allow access. The log shows <code>GOOGLE_EXPORT_KEY = "…"</code>.</li>
                <li><b>Deploy → New deployment → Web app</b>, execute as <b>Me</b>, access <b>Anyone</b> → copy the web app URL.</li>
                <li>Give the engine <code>GOOGLE_EXPORT_URL</code> and <code>GOOGLE_EXPORT_KEY</code> (GitHub → Settings → Secrets → Actions), then run Deploy engine.</li>
                <li>Paste the folder's link above, Save, then Test Google Folder.</li>
              </ol>
              <pre class="code">{ref?.google_script || 'Loading…'}</pre>
              <button class="btn glass pill sm" type="button" style="align-self:flex-start"
                onClick={() => navigator.clipboard.writeText(ref?.google_script || '').then(() => toast('Script copied.'))}>
                Copy The Script</button>
            </div>)}
        </section>
      </fieldset>

      {admin && (
        <div class="toolbar">
          <button class="btn primary pill" onClick={save} disabled={!!busy}>{busy === 'save' ? <Spinner /> : <Icon name="check" />} Save Settings</button>
        </div>)}

      <div class="section-head"><h2>Connections</h2><p>Set in the engine's secrets, never here.</p></div>
      <div class="tiles">
        <div class="card tile"><span>AI (Anthropic)</span><b class={ref?.connections?.ai ? 'green' : 'red'}>{ref ? (ref.connections.ai ? 'Connected' : 'Not Set') : '…'}</b><small>ANTHROPIC_API_KEY</small></div>
        <div class="card tile"><span>Database</span><b class="green">Firestore</b><small>title-commitment-agent</small></div>
        <div class="card tile"><span>Google</span><b class={google ? 'green' : 'muted'}>{google ? 'Set Up' : 'Not Set'}</b>
          <small>{google === 'script' ? 'export script' : google ? 'service account' : 'for Sheets / Docs exports'}</small></div>
        <div class="card tile"><span>Team Hub</span><b class={ref?.connections?.hub ? 'green' : 'muted'}>{ref ? (ref.connections.hub ? 'Connected' : 'Not Set') : '…'}</b>
          <small>Closing Blockers go to hub.totalchb.com</small></div>
        <div class="card tile"><span>Daily Email</span><b class={eCls}>{eValue}</b><small>{eSub}</small></div>
      </div>
    </>
  );
}
