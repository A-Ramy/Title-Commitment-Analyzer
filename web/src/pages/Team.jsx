// Team (Managers only, from the account menu): who's on it, with roles, departments and photos, as in the Universal
// Team Hub's Team Members. Copy From The Team Hub fills it with the hub's Managers and TC department.
// Managers are the admins (they approve lessons and change settings); everyone in TC is in the TC list. Saved
// through the engine (PUT /v1/team); before the first save it starts with the person signed in, as a Manager.
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api.js';
import { useSettings } from '../data.js';
import { Icon, Menu, Spinner, initials, useMenu, useToast } from '../ui.jsx';

const ROLE = { manager: 'Manager', lead: 'Team Leader', member: 'Member' };
// The same team? (Firestore hands fields back in its own order, so compare the values.)
const key = t => JSON.stringify((t || []).map(p => [p.name, p.email, p.role, p.dept || '', p.photo || '']));
const DEPT = { TC: 'TC', '': 'No Department' };

// A photo, centre-cropped to a small square JPEG (as the hub does), kept as a data: URL with the team.
export function squarePhoto(file, size = 160) {
  return new Promise((res, rej) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const c = document.createElement('canvas'), m = Math.min(img.width, img.height);
      c.width = c.height = size;
      c.getContext('2d').drawImage(img, (img.width - m) / 2, (img.height - m) / 2, m, m, 0, 0, size, size);
      URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', 0.82));
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('That file is not a photo this browser can open.')); };
    img.src = url;
  });
}

export function Avatar({ person, size = 40 }) {
  return (
    <span class="team-avatar" style={{ width: size, height: size, fontSize: size > 30 ? 13 : 11 }}>
      {initials(person?.name || person?.email || '?')}
      {person?.photo && <img src={person.photo} alt="" />}
    </span>
  );
}

function Pick({ value, options, onChange, label, disabled }) {
  const menu = useMenu();
  return (
    <>
      <button type="button" class="pill-pick glass" aria-label={label} aria-haspopup="listbox" disabled={disabled}
        onClick={menu.open}>{options[value]}<Icon name="chevron" size={14} stroke={2.5} /></button>
      <Menu menu={menu} label={label}>
        {Object.entries(options).map(([k, text]) => (
          <button key={k} role="menuitemradio" aria-selected={k === value} onClick={() => onChange(k)}>{text}</button>))}
      </Menu>
    </>
  );
}

function Row({ p, admin, onEdit, onRemove }) {
  const toast = useToast();
  const photo = async e => {
    const file = e.currentTarget.files[0]; e.currentTarget.value = '';
    if (!file) return;
    try { onEdit({ photo: await squarePhoto(file) }); toast('Photo added. Save Changes to keep it.'); }
    catch (err) { toast(err.message, true); }
  };
  return (
    <div class="team-row">
      <div class="team-who">
        {admin ? (
          <label class="team-photo" title={p.photo ? 'Change the photo' : 'Add a photo'}>
            <Avatar person={p} />
            <span class="cam" aria-hidden="true"><Icon name="camera" size={9} stroke={2.5} /></span>
            <input type="file" accept="image/*" class="sr" onChange={photo} aria-label={`Photo for ${p.name}`} />
          </label>) : <Avatar person={p} />}
        <div class="team-name">
          {admin ? <input class="name-edit" value={p.name} aria-label="Name"
            onChange={e => onEdit({ name: e.currentTarget.value })} /> : <b>{p.name}</b>}
          <span>{p.email}</span>
        </div>
      </div>
      <Pick label="Role" value={p.role} options={ROLE} disabled={!admin}
        onChange={role => onEdit({ role, dept: role === 'manager' ? '' : p.dept || 'TC' })} />
      {p.role !== 'manager' && <Pick label="Department" value={p.dept || ''} options={DEPT} disabled={!admin}
        onChange={dept => onEdit({ dept })} />}
      {admin && <button type="button" class="team-remove" title="Remove from the team" aria-label={`Remove ${p.name}`}
        onClick={onRemove}><Icon name="x" /></button>}
    </div>
  );
}

export function Team({ me }) {
  const toast = useToast();
  const s = useSettings();
  const admin = !!me?.admin;
  const saved = s?.team;
  const [draft, setDraft] = useState(null);
  const [np, setNp] = useState({ name: '', email: '', role: 'member', dept: 'TC' });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (draft || !s || !me) return;
    const first = me.email.split('@')[0].split(/[._-]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    setDraft(JSON.parse(JSON.stringify(saved || [{ name: first, email: me.email, role: 'manager', dept: '', photo: '' }])));
  }, [s, me]);
  if (me && !admin) return <section class="empty"><h3>Managers only</h3><p>Ask a manager to change the team.</p></section>;
  if (!draft) return <p class="lede"><Spinner /> Loading the team…</p>;
  const dirty = !saved || key(draft) !== key(saved);
  const edit = (email, x) => setDraft(d => d.map(p => (p.email === email ? { ...p, ...x } : p)));
  const add = () => {
    const email = np.email.trim().toLowerCase(), name = np.name.trim();
    if (!name || !email.includes('@')) return toast('Add a name and their sign-in email.', true);
    if (draft.some(p => p.email === email)) return toast(`${email} is already on the team.`, true);
    setDraft(d => [...d, { name, email, role: np.role, dept: np.role === 'manager' ? '' : np.dept, photo: '' }]);
    setNp({ name: '', email: '', role: 'member', dept: 'TC' });
  };
  const fromHub = async () => {
    setBusy(true);
    try {
      const { people } = await api.teamFromHub();
      if (!people.length) return toast('The Team Hub sent nobody.', true);
      setDraft(people); toast(`Copied ${people.length} people from the Team Hub. Check them, then Save Changes.`);
    } catch (e) { toast(e.message, true); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    try { await api.putTeam({ people: draft }); toast('Team saved.'); }
    catch (e) { toast(e.message, true); } finally { setBusy(false); }
  };
  const by = (a, b) => (a.role === 'lead' ? 0 : 1) - (b.role === 'lead' ? 0 : 1);
  const groups = [['Managers', draft.filter(p => p.role === 'manager')],
    ['TC', draft.filter(p => p.role !== 'manager' && p.dept === 'TC').sort(by)],
    ['No Department', draft.filter(p => p.role !== 'manager' && p.dept !== 'TC').sort(by)]].filter(([, rows]) => rows.length);
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">Managers Only</span></div>
          <h1 class="title">The <span class="accent">Team</span></h1>
          <p class="lede">Managers Approve Lessons And Change Settings. Everyone In TC Can Own A Deal.</p>
        </div>
        <div class="stats">
          <div class="stat"><b>{draft.filter(p => p.role === 'manager').length}</b><span>Managers</span></div>
          <div class="stat"><b>{draft.filter(p => p.dept === 'TC').length}</b><span>In TC</span></div>
        </div>
      </section>

      {!saved && <div class="note">No team saved yet. Copy From The Team Hub (its Managers and TC department, with
        their photos) or add people below, then Save Changes.</div>}
      <div class="toolbar">
        <button class="btn glass pill" onClick={fromHub} disabled={busy}>{busy ? <Spinner /> : <Icon name="users" />} Copy From The Team Hub</button>
        <span class="row-sub">Replaces the list below with the hub's Managers and TC department. Nothing changes until you Save.</span>
      </div>

      {admin && (
        <div class="card team-add">
          <b>Add A Person</b>
          <input class="input" placeholder="Full name" value={np.name} onInput={e => setNp({ ...np, name: e.currentTarget.value })} />
          <input class="input" type="email" placeholder="Sign-in email (@totalchb.com)" value={np.email}
            onInput={e => setNp({ ...np, email: e.currentTarget.value })} onKeyDown={e => e.key === 'Enter' && add()} />
          <Pick label="Role" value={np.role} options={ROLE} onChange={role => setNp({ ...np, role })} />
          {np.role !== 'manager' && <Pick label="Department" value={np.dept} options={DEPT} onChange={dept => setNp({ ...np, dept })} />}
          <button type="button" class="btn primary pill" onClick={add}><Icon name="plus" /> Add</button>
        </div>)}

      {groups.map(([label, rows]) => (
        <section key={label} class="card team-group">
          <div class="eyebrow">{label}</div>
          {rows.map(p => <Row key={p.email} p={p} admin={admin} onEdit={x => edit(p.email, x)}
            onRemove={() => setDraft(d => d.filter(x => x.email !== p.email))} />)}
        </section>))}

      {admin && (
        <div class="toolbar">
          <button class="btn primary pill" onClick={save} disabled={busy || !dirty}>{busy ? <Spinner /> : <Icon name="check" />} Save Changes</button>
          <button class="btn ghost pill" disabled={busy || !dirty || !saved}
            onClick={() => setDraft(JSON.parse(JSON.stringify(saved)))}>Cancel</button>
          <span class="row-sub">Saving sets who the admins are (the managers) and the TC list on Analyze.</span>
        </div>)}
    </>
  );
}
