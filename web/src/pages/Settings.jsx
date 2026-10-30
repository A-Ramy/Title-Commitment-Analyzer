// Settings (managers change them; everyone can see them): Permissions (what Team Leaders and Members may do), the
// daily email (picked from the team), due dates, the Google folder, and what is connected. People are on Team
// (Managers, from the account menu). Saved through the engine (PUT /v1/settings).
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api.js';
import { useReference, useSettings } from '../data.js';
import { Icon, Spinner, useToast } from '../ui.jsx';
import { Avatar } from './Team.jsx';

const DUE = [['payoff', 'Payoff Letters'], ['curative', 'Court / Curative'], ['documents', 'Documents'],
  ['bring_down', 'Bring-Down'], ['closing', 'At Closing']];
const PERMS = [['approve_lessons', 'Approve Lessons', 'The Feedback Inbox and the lessons on Knowledge'],
  ['report_missing', 'Add Missing Items', 'Report Missing Item on a deal']];
const WHO = [['lead', 'Team Leaders'], ['member', 'Members']];
const ET = { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' };

// The daily email's last run (written by scripts/daily_email.py).
function emailStatus(last) {
  if (!last) return ['No Run Yet', 'sent each weekday at 8:00 AM ET', 'muted'];
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
      setF({ email_recipients: [...(s.email_recipients || [])], permissions: JSON.parse(JSON.stringify(s.permissions || {})),
        extra: '',
        email_from: s.email_from || 'title-agent@totalchb.com', due_offsets: { ...(s.due_offsets || {}) },
        google_folder_id: s.google_folder_id || '' });
    }
  }, [s]);
  if (!s || !f) return <p class="lede"><Spinner /> Loading settings…</p>;
  const set = k => e => setF({ ...f, [k]: e.currentTarget.value });
  const save = async () => {
    setBusy('save');
    try {
      await api.putSettings({ email_recipients: f.email_recipients, permissions: f.permissions,
        email_from: f.email_from.trim(), due_offsets: f.due_offsets, google_folder_id: f.google_folder_id.trim() });
      toast('Saved.');
    } catch (e) { toast(e.message, true); } finally { setBusy(''); }
  };
  const testFolder = async () => {
    setBusy('check'); setCheck(null);
    try { setCheck(await api.googleCheck()); } catch (e) { setCheck({ ok: false, message: e.message }); } finally { setBusy(''); }
  };
  const team = s.team || [];
  const sends = email => f.email_recipients.includes(email);
  const toggle = email => setF({ ...f, email_recipients: sends(email) ? f.email_recipients.filter(x => x !== email)
    : [...f.email_recipients, email] });
  const addExtra = () => {
    const email = f.extra.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return toast('Type a whole email address.', true);
    setF({ ...f, extra: '', email_recipients: sends(email) ? f.email_recipients : [...f.email_recipients, email] });
  };
  const others = f.email_recipients.filter(x => !team.some(p => p.email === x));
  const perm = (who, k) => !!f.permissions?.[who]?.[k];
  const setPerm = (who, k) => setF({ ...f, permissions: { ...f.permissions, [who]: { ...(f.permissions[who] || {}), [k]: !perm(who, k) } } });
  const [eValue, eSub, eCls] = emailStatus(s.email_last_run);
  const google = ref?.connections?.google;
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">{admin ? 'Managers Change Settings' : 'Read Only: Managers Change Settings'}</span></div>
          <h1 class="title">Settings</h1>
          <p class="lede">Who May Do What, The Daily Email, Due Dates And The Google Folder.</p>
        </div>
      </section>

      <fieldset disabled={!admin} style="border:none;margin:0;padding:0;display:flex;flex-direction:column;gap:18px;min-width:0">
        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">Permissions</h2>
          <span class="row-sub">Managers can always do everything. Choose what Team Leaders and Members may do.
            {admin ? <> Roles are set on <a href="#/team">Team</a> (your photo → Team).</> : ''}</span>
          <div class="perm-grid" role="table" aria-label="Permissions">
            <span role="columnheader" />
            {WHO.map(([w, label]) => <b key={w} role="columnheader">{label}</b>)}
            {PERMS.map(([k, label, hint]) => [
              <span key={k} class="perm-what" role="rowheader"><b>{label}</b><small>{hint}</small></span>,
              ...WHO.map(([w, wl]) => (
                <span key={k + w} class="perm-cell" role="cell">
                  <button type="button" class="switch" role="switch" aria-checked={perm(w, k)} aria-label={`${wl}: ${label}`}
                    onClick={() => setPerm(w, k)} />
                </span>))])}
          </div>
        </section>

        <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:14px">
          <h2 style="font-size:20px;font-weight:800">Daily Email</h2>
          <span class="row-sub">Weekdays at 8:00 AM Eastern: every open deal's open Closing Blockers.</span>
          <div class="field"><span>Send To</span>
            <div class="people-pick" role="group" aria-label="Send to">
              {team.map(p => (
                <button key={p.email} type="button" class="person-chip" aria-pressed={sends(p.email)} title={p.email}
                  onClick={() => toggle(p.email)}>
                  <Avatar person={p} size={28} />{p.name}{sends(p.email) && <Icon name="check" size={14} stroke={3} />}
                </button>))}
              {others.map(x => (
                <button key={x} type="button" class="person-chip" aria-pressed="true" title="Not on the team: click to remove"
                  onClick={() => toggle(x)}><Avatar person={{ email: x }} size={28} />{x}<Icon name="x" size={14} /></button>))}
              {!team.length && !others.length && <span class="row-sub">Save the team first (your photo → Team), then pick people here.</span>}
            </div>
            <div class="toolbar" style="margin-top:4px">
              <input class="input" style="flex:1 1 240px" placeholder="Someone not on the team? Their email" value={f.extra}
                onInput={set('extra')} onKeyDown={e => e.key === 'Enter' && addExtra()} />
              <button type="button" class="btn ghost pill sm" onClick={addExtra}><Icon name="plus" /> Add</button>
            </div>
          </div>
          <label class="field"><span>Send From</span><input class="input" value={f.email_from} onInput={set('email_from')} /></label>
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
          <p class="row-sub" style="margin:0">Every export is saved here, in a folder for its type (PDF, Word, Excel, CSV, Google Sheets, Google Docs, made the first time), with the date and time in its name. Downloads still save to the person's computer too.</p>
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
              <p class="note" style="margin:0"><b>Already set up?</b> When Test Google Folder says the script is the old version: open it at script.google.com, paste the script below over everything, Save, then <b>Deploy → Manage deployments → edit (pencil) → Version: New version → Deploy</b>. The web app URL and the key stay the same.</p>
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
