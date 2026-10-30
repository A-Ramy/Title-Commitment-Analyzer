// A deal: the live list a TC works, in the hub's task-card design. Reads come from Firestore; every change goes
// through the engine and shows here (and on every other open screen) a moment later. Changes appear at once here.
import { collection, onSnapshot, query, where } from 'firebase/firestore';
import { getDownloadURL, ref } from 'firebase/storage';
import { useEffect, useMemo, useState } from 'preact/hooks';
import { api, jobId } from '../api.js';
import { DONE, PRIORITY, PRIORITY_ORDER, STATUSES, isOpen, useDeal, useItems, useJob, useLatestRun } from '../data.js';
import { db, storage } from '../firebase.js';
import { go } from '../router.js';
import { Icon, Menu, Modal, Seg, Spinner, daysUntil, fmtDate, money, useMenu, useToast, when } from '../ui.jsx';

const STATUS_CLS = { Open: 's-open', Ordered: 's-ordered', Received: 's-received', Cleared: 's-cleared', Waived: 's-waived' };
const PROOF = { true: '✓', false: '✗' };
const PRI_CHIP = { blocker: 'red', before: 'orange', fyi: '' };
const GROUP = { blocker: 'Closing Blockers', before: 'Before Closing', fyi: 'Review / FYI' };

// ---------------------------------------------------------------- one item
function ItemCard({ item, deal, open, onToggle, onChange }) {
  const status = useMenu();
  const [editDue, setEditDue] = useState(false);
  const [notes, setNotes] = useState(item.notes || '');
  useEffect(() => setNotes(item.notes || ''), [item.notes]);
  const owner = item.owner === 'TC' ? deal.tc || 'TC' : item.owner;
  const cleared = DONE.has(item.status);
  const removed = item.change === 'removed';
  const days = daysUntil(item.due_date);
  const late = days !== null && days < 0 && !cleared;
  return (
    <article class={`card row-card p-${item.priority} ${cleared ? 'done' : ''} ${removed ? 'removed' : ''}`}>
      <div class="row-top">
        <button class={`check ${cleared ? 'on' : ''}`} disabled={removed} aria-pressed={cleared}
          title={cleared ? 'Cleared: click to reopen' : 'Mark cleared'}
          onClick={() => onChange({ status: cleared ? 'Open' : 'Cleared' })}>
          {cleared && <Icon name="check" size={16} stroke={3} />}
        </button>
        <div class="row-text" onClick={onToggle} role="button" tabIndex={0} aria-expanded={open}
          onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onToggle())}>
          <span class="row-title">
            {item.change === 'new' && <span class="chip green" style="margin-right:6px">New</span>}
            {item.title}
          </span>
          <span class="row-sub">{item.action}</span>
        </div>
        <div class="row-meta">
          <button class={`status glass ${STATUS_CLS[item.status] || 's-open'}`} onClick={status.open}
            disabled={removed} title="Status" aria-haspopup="menu">
            {item.status}<Icon name="chevron" size={14} stroke={2.5} />
          </button>
          <Menu menu={status} label="Status">
            {STATUSES.map(s => (
              <button key={s} role="menuitemradio" aria-selected={s === item.status} onClick={() => onChange({ status: s })}>
                <span class={`status ${STATUS_CLS[s]}`} style="cursor:inherit">{s}</span>
              </button>))}
          </Menu>
          {editDue ? (
            <input type="date" class="input" style="width:auto;padding:6px 10px;font-size:14px" autoFocus
              value={item.due_date || ''} aria-label="Due date"
              onChange={e => { onChange({ due_date: e.currentTarget.value || '' }); setEditDue(false); }}
              onBlur={() => setEditDue(false)} />
          ) : (
            <button class={`mini ${late ? 'has' : item.due_date ? '' : 'muted'}`} onClick={() => setEditDue(true)}
              title={late ? 'Overdue' : 'Due date'} disabled={removed}>
              <Icon name="calendar" />{item.due_date ? fmtDate(item.due_date, false) : 'Due'}
            </button>
          )}
          <button class={`mini ${item.notes ? '' : 'muted'}`} title={item.notes || 'Notes'} onClick={onToggle}>
            <Icon name="note" />
          </button>
          <button class="mini" aria-label={open ? 'Hide details' : 'Show details'} onClick={onToggle}>
            <Icon name="chevron" size={18} />
          </button>
        </div>
      </div>
      {open && (
        <div class="row-detail">
          {item.why && <div>{item.why}</div>}
          <div class="kv">
            <span>Provided by <b>{item.provided_by}</b></span>
            <span>Owner <b>{owner}</b></span>
            {item.amount != null && <span>Amount <b>{money(item.amount)}</b></span>}
            <span>{item.category}</span>
          </div>
          {(item.sources || []).map((s, n) => (
            <div key={n} style="display:flex;flex-direction:column;gap:6px">
              <span class="src">{s.ref}{s.page ? ` · p.${s.page}` : ''} {PROOF[s.verified] || ''}
                <span class="row-sub" style="font-family:var(--font-body);font-weight:400">
                  {s.verified === true ? ' found word for word on the page' : s.verified === false
                    ? ' not found word for word: check the commitment' : ''}</span></span>
              {s.quote && <blockquote class="quote">{s.quote}</blockquote>}
            </div>))}
          <label class="field">
            <span>Notes</span>
            <textarea class="input" rows={2} value={notes} placeholder="e.g. Payoff requested from servicer 10/26"
              onInput={e => setNotes(e.currentTarget.value)} />
          </label>
          <div class="toolbar">
            <button class="btn sm secondary pill" disabled={notes === (item.notes || '')}
              onClick={() => onChange({ notes })}>Save Notes</button>
            <span class="spacer" />
            <ItemFeedback deal={deal} item={item} />
          </div>
        </div>
      )}
    </article>
  );
}

function ItemFeedback({ deal, item }) {
  const menu = useMenu();
  const toast = useToast();
  const send = async kind => {
    try {
      await api.itemFeedback(deal.id, { item_key: item.key, kind, note: '' });
      toast('Sent to the Feedback Inbox. Set the status to Waived with a note if it isn\'t needed.');
    } catch (e) { toast(e.message, true); }
  };
  return (
    <>
      <button class="link-btn" onClick={menu.open}><Icon name="flag" /> Feedback</button>
      <Menu menu={menu} label="Feedback on this item">
        <button onClick={() => send('not_needed')}>Not Needed On This Deal</button>
        <button onClick={() => send('wrong')}>Wrong Information</button>
      </Menu>
    </>
  );
}

// ---------------------------------------------------------------- dialogs
function JobProgress({ id }) {
  const job = useJob(id);
  return <p class="note" role="status" style="display:flex;gap:10px;align-items:center"><Spinner />{job?.step || 'Starting'}…</p>;
}

function ExportDialog({ deal, items, onClose }) {
  const toast = useToast();
  const live = items.filter(i => i.change !== 'removed');
  const counts = { all: live.length, action: live.filter(i => i.priority !== 'fyi').length,
    blockers: live.filter(i => i.priority === 'blocker').length };
  const [include, setInclude] = useState('all');
  const [busy, setBusy] = useState('');
  const run = async (key, fn) => {
    setBusy(key);
    try { await fn(); } catch (e) { toast(e.message, true); } finally { setBusy(''); }
  };
  const google = kind => run(kind, async () => {
    const { link } = await api.google(deal.id, kind, include);
    window.open(link, '_blank', 'noopener');
    toast('Created in the team\'s Google Drive folder.');
  });
  return (
    <Modal title="Export List" onClose={onClose}>
      <Seg label="Include" value={include} onChange={setInclude} options={[
        { value: 'all', label: 'Everything', n: counts.all },
        { value: 'action', label: 'No Review / FYI', n: counts.action },
        { value: 'blockers', label: 'Closing Blockers Only', n: counts.blockers }]} />
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px">
        {[['pdf', 'PDF'], ['docx', 'Word'], ['xlsx', 'Excel'], ['csv', 'CSV']].map(([f, label]) => (
          <button key={f} class="btn glass pill" disabled={!!busy}
            onClick={() => run(f, () => api.download(deal.id, f, include))}>
            {busy === f ? <Spinner /> : <Icon name="download" />} {label}
          </button>))}
        <button class="btn glass pill" disabled={!!busy} onClick={() => google('sheet')}>
          {busy === 'sheet' ? <Spinner /> : <Icon name="sheet" />} Google Sheets</button>
        <button class="btn glass pill" disabled={!!busy} onClick={() => google('doc')}>
          {busy === 'doc' ? <Spinner /> : <Icon name="file" />} Google Docs</button>
      </div>
      <p class="row-sub" style="margin:0">Exports contain names, addresses and loan numbers. Send them only to people on the deal.</p>
      <div class="actions"><button class="btn ghost pill" onClick={onClose}>Done</button></div>
    </Modal>
  );
}

function MissingDialog({ deal, onClose }) {
  const toast = useToast();
  const [f, setF] = useState({ what: '', where: '', why: '', priority: 'blocker', provided_by: 'Seller', add_to_list: true });
  const [busy, setBusy] = useState(false);
  const set = k => e => setF({ ...f, [k]: e.currentTarget.type === 'checkbox' ? e.currentTarget.checked : e.currentTarget.value });
  const send = async () => {
    setBusy(true);
    try {
      await api.missing(deal.id, f);
      toast(f.add_to_list ? 'Added to this deal and sent to the Feedback Inbox.' : 'Sent to the Feedback Inbox.');
      onClose();
    } catch (e) { toast(e.message, true); setBusy(false); }
  };
  return (
    <Modal title="Report A Missing Item" onClose={onClose}>
      <p class="row-sub" style="margin:0">Something the agent should have listed. Once an admin approves the lesson, the
        agent checks for it on every deal.</p>
      <label class="field"><span>What's Missing</span>
        <input class="input" value={f.what} onInput={set('what')} placeholder="e.g. Final water bill / utility lien search" /></label>
      <label class="field"><span>Where In The Document (Optional)</span>
        <input class="input" value={f.where} onInput={set('where')} placeholder="e.g. B-II #10, page 9" /></label>
      <label class="field"><span>Why It Would Stop Or Delay The Closing</span>
        <textarea class="input" rows={3} value={f.why} onInput={set('why')}
          placeholder="e.g. The city records unpaid water bills as a lien; title won't insure over it." /></label>
      <div class="field"><span>Priority</span>
        <Seg label="Priority" value={f.priority} onChange={v => setF({ ...f, priority: v })} options={
          PRIORITY_ORDER.map(p => ({ value: p, label: PRIORITY[p] }))} /></div>
      <label class="field"><span>Who Has To Provide It</span>
        <input class="input" value={f.provided_by} onInput={set('provided_by')} /></label>
      <label style="display:flex;gap:10px;align-items:center;font-weight:600">
        <input type="checkbox" checked={f.add_to_list} onChange={set('add_to_list')} /> Add it to this deal's list now</label>
      <div class="actions">
        <button class="btn ghost pill" onClick={onClose}>Cancel</button>
        <button class="btn primary pill" disabled={!f.what.trim() || busy} onClick={send}>
          {busy && <Spinner />} Send Feedback</button>
      </div>
    </Modal>
  );
}

function RerunDialog({ deal, onClose }) {
  const toast = useToast();
  const [job, setJob] = useState(null);
  const start = async () => {
    const id = jobId(); setJob(id);
    try { await api.rerun(deal.id, id); toast('Review complete. Statuses and notes were kept.'); onClose(); }
    catch (e) { toast(e.message, true); setJob(null); }
  };
  return (
    <Modal title="Re-run The Review" onClose={() => !job && onClose()}>
      <p class="lede">Reads the latest commitment again with the latest team lessons. Statuses and notes are kept.
        It takes 1–3 minutes.</p>
      {job && <JobProgress id={job} />}
      <div class="actions">
        <button class="btn ghost pill" disabled={!!job} onClick={onClose}>Cancel</button>
        <button class="btn primary pill" disabled={!!job} onClick={start}><Icon name="refresh" /> Re-run Review</button>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------- documents and history
function Records({ deal }) {
  const toast = useToast();
  const [docs, setDocs] = useState([]);
  useEffect(() => onSnapshot(query(collection(db, 'documents'), where('deal_id', '==', deal.id)),
    s => setDocs(s.docs.map(d => d.data()).sort((a, b) => a.id - b.id)), () => setDocs([])), [deal.id]);
  const open = async d => {
    try { window.open(await getDownloadURL(ref(storage, d.path)), '_blank', 'noopener'); }
    catch { toast("Couldn't open that file.", true); }
  };
  const flip = async () => {
    try { await api.setDeal(deal.id, deal.status === 'open' ? 'closed' : 'open'); }
    catch (e) { toast(e.message, true); }
  };
  return (
    <section class="card" style="padding:18px 20px;display:flex;flex-direction:column;gap:12px">
      <h2 style="font-size:18px">Documents And Review History</h2>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        {docs.map(d => (
          <button key={d.id} class="btn glass pill sm" onClick={() => open(d)}>
            <Icon name="file" /> {d.kind === 'contract' ? 'Contract' : 'Commitment'}: {d.filename}
          </button>))}
        {!docs.length && <span class="row-sub">No documents.</span>}
      </div>
      <div class="toolbar">
        {deal.hub_error ? <span class="row-sub"><span class="chip orange">Team Hub</span> Not reached yet: it's sent again with the next change, and every weekday morning.</span>
          : deal.hub_synced_at ? <span class="row-sub"><span class="chip green">Team Hub</span> Closing Blockers sent {when(deal.hub_synced_at)}.</span>
          : null}
        <span class="spacer" />
        <button class="btn outline sm" onClick={flip}>{deal.status === 'open' ? 'Mark Deal Closed' : 'Reopen Deal'}</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- the page
export function Deal({ id }) {
  const toast = useToast();
  const { data: deal } = useDeal(id);
  const { items: fsItems } = useItems(id);
  const { run, analysis } = useLatestRun(id);
  const [pending, setPending] = useState({});  // changes shown at once, until Firestore confirms them
  const [view, setView] = useState('all');
  const [openOnly, setOpenOnly] = useState('all');
  const [expanded, setExpanded] = useState(() => new Set());
  const [dialog, setDialog] = useState('');

  const items = useMemo(() => (fsItems || []).map(i => (pending[i.key] ? { ...i, ...pending[i.key] } : i)), [fsItems, pending]);
  useEffect(() => {  // drop pending changes Firestore now shows
    setPending(p => {
      const next = { ...p };
      for (const i of fsItems || []) {
        if (next[i.key] && Object.entries(next[i.key]).every(([k, v]) => (i[k] ?? '') === (v ?? ''))) delete next[i.key];
      }
      return next;
    });
  }, [fsItems]);

  if (deal === undefined || fsItems === undefined) return <p class="lede"><Spinner /> Loading the deal…</p>;
  if (!deal) return <section class="empty"><h3>Deal not found</h3><p><a href="#/">Back to Deals</a></p></section>;

  const change = async (item, changes) => {
    setPending(p => ({ ...p, [item.key]: { ...(p[item.key] || {}), ...changes } }));
    try { await api.setItem(deal.id, { key: item.key, ...changes }); }
    catch (e) {
      toast(e.message, true);
      setPending(p => { const n = { ...p }; delete n[item.key]; return n; });
    }
  };
  const live = items.filter(i => i.change !== 'removed');
  const removed = items.filter(i => i.change === 'removed');
  const openBlockers = live.filter(i => i.priority === 'blocker' && isOpen(i)).length;
  const cleared = live.filter(i => !isOpen(i)).length;
  const cov = analysis?.coverage;  // same rule as Coverage.complete / .percent in titleagent/models.py
  const covGaps = cov ? [...(cov.unaddressed || []), ...(cov.numbering_gaps || [])] : [];
  const covTotal = cov ? cov.requirements_total + cov.exceptions_total : 0;
  const covPct = cov ? (covTotal ? Math.floor((100 * (cov.requirements_addressed + cov.exceptions_addressed)) / covTotal)
    : 100) : null;
  const a = analysis?.structure?.schedule_a || {};
  const days = daysUntil(deal.closing_date);
  const expires = (() => {  // the commitment's deadline vs the closing date
    if (!a.commitment_date || !a.requirements_deadline_days || !deal.closing_date) return null;
    const end = new Date(a.commitment_date); if (isNaN(end)) return null;
    end.setDate(end.getDate() + a.requirements_deadline_days);
    return end.toISOString().slice(0, 10) < deal.closing_date ? end.toISOString().slice(0, 10) : null;
  })();
  const shown = p => live.filter(i => i.priority === p && (openOnly === 'all' || isOpen(i)));
  const toggle = key => setExpanded(s => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n; });
  const card = i => (
    <ItemCard key={i.key} item={i} deal={deal} open={expanded.has(i.key)} onToggle={() => toggle(i.key)}
      onChange={c => change(i, c)} />);

  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row">
            <a class="link-btn" style="padding:4px 8px 4px 0" href="#/"><Icon name="back" /> Deals</a>
            <span class="eyebrow">{deal.deal_type || 'Deal'}</span>
            {deal.status !== 'open' && <span class="chip">Closed</span>}
            {deal.closing_date && (
              <span class={`chip ${days < 0 ? 'red' : days <= 7 ? 'orange' : ''}`}>
                Closing {fmtDate(deal.closing_date)}{days !== null && days >= 0 ? ` · ${days}d` : ''}</span>)}
          </div>
          <h1 class="title">{deal.address || `Deal ${deal.id}`}</h1>
          <p class="lede">{[deal.tc && `TC ${deal.tc}`, deal.title_company, a.commitment_number && `Commitment ${a.commitment_number}`]
            .filter(Boolean).join(' · ')}</p>
        </div>
        <div class="stats">
          <div class="stat"><b class={openBlockers ? 'red' : 'green'}>{openBlockers}</b><span>Open Blockers</span></div>
          <div class="stat"><b>{cleared}<span class="slash">/</span>{live.length}</b><span>Items Cleared</span></div>
          {covPct !== null && <div class="stat"><b class={covGaps.length ? 'red' : 'green'}>{covPct}%</b><span>Coverage</span></div>}
        </div>
      </section>
      <div class="progress" aria-hidden="true"><i style={{ width: `${live.length ? (100 * cleared) / live.length : 0}%` }} /></div>

      {expires && <div class="note red" role="alert"><b>The commitment expires before closing</b> ({fmtDate(expires)}).
        Ask the title company for an updated commitment now.</div>}
      {covGaps.length > 0 && <div class="note red" role="alert"><b>Check by hand:</b> these numbered items in the
        commitment weren't accounted for: {covGaps.join(', ')}. Read them in the commitment yourself.</div>}
      {(analysis?.corrections || []).map((c, n) => <div key={n} class="note"><b>Second review:</b> {c}</div>)}

      <div class="card bar-card">
        <button class="btn glass pill" onClick={() => setDialog('export')}><Icon name="download" /> Export List</button>
        <button class="btn primary pill" onClick={() => setDialog('missing')}><Icon name="plus" /> Report Missing Item</button>
        <span style="flex:1" />
        <button class="btn ghost pill" disabled={!run} onClick={() => setDialog('rerun')}><Icon name="refresh" /> Re-run</button>
        <button class="btn ghost pill" onClick={() => go(`analyze/update/${deal.id}`)}><Icon name="upload" /> Updated Commitment</button>
      </div>

      <div class="toolbar">
        <Seg label="Priority" value={view} onChange={setView} options={[
          { value: 'all', label: 'All', n: live.length },
          ...PRIORITY_ORDER.map(p => ({ value: p, label: GROUP[p], n: live.filter(i => i.priority === p).length }))]} />
        <Seg label="Status" value={openOnly} onChange={setOpenOnly} options={[
          { value: 'all', label: 'Any Status' }, { value: 'open', label: 'Open Only' }]} />
        <span class="spacer" />
        {expanded.size ? <button class="link-btn" onClick={() => setExpanded(new Set())}>Collapse All</button>
          : <button class="link-btn" onClick={() => setExpanded(new Set(live.map(i => i.key)))}>Expand All</button>}
      </div>

      {!live.length && <section class="empty"><h3>No items yet</h3><p>Run the review from Analyze.</p></section>}
      {PRIORITY_ORDER.filter(p => view === 'all' || view === p).map(p => {
        const list = shown(p);
        if (!list.length) return null;
        return (
          <section key={p} class="list" aria-label={PRIORITY[p]}>
            <div class="group-head"><h2>{GROUP[p]}</h2><span class={`chip ${PRI_CHIP[p]}`}>{list.length}</span></div>
            {list.map(card)}
          </section>);
      })}
      {removed.length > 0 && view === 'all' && (
        <section class="list" aria-label="Removed by the title company">
          <div class="group-head"><h2>Removed By The Title Company</h2><span class="chip">{removed.length}</span></div>
          {removed.map(card)}
        </section>)}

      <Records deal={deal} />
      {run && <p class="row-sub" style="text-align:center;margin:0">Last review {when(run.created_at)} by {run.created_by}
        {analysis ? ` · ${analysis.lessons_applied ?? 0} team lessons applied` : ''}</p>}

      {dialog === 'export' && <ExportDialog deal={deal} items={items} onClose={() => setDialog('')} />}
      {dialog === 'missing' && <MissingDialog deal={deal} onClose={() => setDialog('')} />}
      {dialog === 'rerun' && <RerunDialog deal={deal} onClose={() => setDialog('')} />}
    </>
  );
}
