// Knowledge: the Feedback Inbox (admins turn feedback into lessons), the lessons the agent follows on every deal,
// training examples with their latest score, and the professional checklist.
import { collection, onSnapshot } from 'firebase/firestore';
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api.js';
import { useReference } from '../data.js';
import { db } from '../firebase.js';
import { Icon, Spinner, useToast, when } from '../ui.jsx';

const KIND = { missing: 'Missing Item', not_needed: 'Not Needed', wrong: 'Wrong Info', training: 'Training Gap' };

function useCol(name) {
  const [rows, setRows] = useState(undefined);
  useEffect(() => onSnapshot(collection(db, name), s => setRows(s.docs.map(d => d.data())), () => setRows([])), [name]);
  return rows;
}

// A suggested starting point; the admin edits it into a general rule.
function suggested(f) {
  const d = f.detail || {};
  if (d.suggested_lesson) return d.suggested_lesson;
  if (f.kind === 'missing') return `On every commitment, check for: ${f.text}. ${d.why || ''}`.trim();
  if (f.kind === 'not_needed') return `Do not list this as an action item when it appears: ${f.text}`;
  return f.text;
}

function InboxCard({ f, admin }) {
  const toast = useToast();
  const [text, setText] = useState(suggested(f));
  const [busy, setBusy] = useState('');
  const d = f.detail || {};
  const act = async approve => {
    setBusy(approve ? 'yes' : 'no');
    try { await api.resolve(f.id, approve, text); toast(approve ? 'Lesson approved: it applies from the next review.' : 'Rejected.'); }
    catch (e) { toast(e.message, true); setBusy(''); }
  };
  return (
    <article class="card row-card p-before" style="display:flex;flex-direction:column;gap:10px">
      <div class="eyebrow-row">
        <span class="chip orange">{KIND[f.kind] || f.kind}</span>
        <span class="row-sub">{f.created_by} · {when(f.created_at)}{f.deal_id ? ' · ' : ''}
          {f.deal_id && <a href={`#/deal/${f.deal_id}`}>deal</a>}{d.where ? ` · ${d.where}` : ''}</span>
      </div>
      <span class="row-title">{f.text}</span>
      {d.why && <span class="row-sub">{d.why}</span>}
      <label class="field"><span>Lesson The Agent Will Follow</span>
        <textarea class="input" rows={3} value={text} disabled={!admin} onInput={e => setText(e.currentTarget.value)} /></label>
      <p class="row-sub" style="margin:0">Write it as a general rule: no names, addresses, amounts or case numbers from one deal.</p>
      {admin && (
        <div class="toolbar">
          <button class="btn primary pill sm" disabled={!!busy || !text.trim()} onClick={() => act(true)}>
            {busy === 'yes' ? <Spinner /> : <Icon name="check" />} Approve Lesson</button>
          <button class="btn ghost pill sm" disabled={!!busy} onClick={() => act(false)}>Reject</button>
        </div>)}
    </article>
  );
}

function LessonRow({ x, admin }) {
  const toast = useToast();
  const flip = async () => {
    try { await api.setLesson(x.id, { active: !x.active }); } catch (e) { toast(e.message, true); }
  };
  return (
    <div class={`card row-card ${x.active ? 'p-fyi' : 'done'}`} style="display:flex;gap:14px;align-items:flex-start">
      <div class="row-text" style="cursor:default">
        <span style="font-size:15px;color:var(--text-body)">{x.text}</span>
        <span class="row-sub" style="font-size:13px">{(x.source || '').replace(/^./, c => c.toUpperCase())} · {x.created_by}
          · {when(x.created_at)}{x.approved_by ? ` · approved by ${x.approved_by}` : ''}</span>
      </div>
      <button class="switch" role="switch" aria-checked={!!x.active} aria-label={x.active ? 'Turn this lesson off' : 'Turn this lesson on'}
        disabled={!admin} onClick={flip} title={admin ? '' : 'Only admins change lessons'} />
    </div>
  );
}

export function Knowledge({ me }) {
  const toast = useToast();
  const ref = useReference();
  const admin = !!me?.admin;
  const feedback = useCol('feedback');
  const lessons = useCol('lessons');
  const examples = useCol('examples');
  const scores = useCol('scores');
  const [newLesson, setNewLesson] = useState('');
  const [showChecklist, setShowChecklist] = useState(false);
  const inbox = (feedback || []).filter(f => f.status === 'pending').sort((a, b) => b.id - a.id);
  const all = (lessons || []).sort((a, b) => a.id - b.id);
  const active = all.filter(x => x.active);
  const latest = {};
  for (const s of [...(scores || [])].sort((a, b) => (a.run_at?.seconds || 0) - (b.run_at?.seconds || 0))) latest[s.example_id] = s;
  const matched = Object.values(latest).reduce((n, s) => n + s.matched, 0);
  const total = Object.values(latest).reduce((n, s) => n + s.total, 0);
  const checks = (ref?.checklist || []).reduce((n, g) => n + g.checks.length, 0);
  const add = async () => {
    try { await api.addLesson(newLesson.trim()); setNewLesson(''); toast('Lesson added: it applies from the next review.'); }
    catch (e) { toast(e.message, true); }
  };
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">What The Agent Knows</span></div>
          <h1 class="title">Team <span class="accent">Knowledge</span></h1>
          <p class="lede">Every Lesson Came From Your Team. The Agent Follows Every Active Lesson On Every Deal.</p>
        </div>
      </section>
      <div class="tiles">
        <div class="card tile"><span>Finds Expert Items</span><b class={total ? 'green' : 'muted'}>{total ? `${Math.round((100 * matched) / total)}%` : '—'}</b>
          <small>{total ? `across ${Object.keys(latest).length} training example(s)` : 'run Training to measure'}</small></div>
        <div class="card tile"><span>Active Lessons</span><b>{active.length}</b><small>{all.length - active.length} turned off</small></div>
        <div class="card tile"><span>Pro Checklist</span><b>{checks || '—'}</b><small>checks across {(ref?.checklist || []).length} groups</small></div>
        <div class="card tile"><span>Feedback Waiting</span><b class={inbox.length ? 'red' : 'green'}>{inbox.length}</b>
          <small>{inbox.length ? 'needs an admin' : 'inbox is empty'}</small></div>
      </div>

      <div class="section-head"><h2>Feedback Inbox</h2><p>From Report Missing Item, item feedback and training gaps.</p></div>
      {feedback === undefined ? <Spinner /> : inbox.length ? (
        <div class="list">{inbox.map(f => <InboxCard key={f.id} f={f} admin={admin} />)}</div>
      ) : <div class="note green">Inbox is empty. Every piece of feedback has been reviewed.</div>}
      {inbox.length > 0 && !admin && <p class="row-sub" style="margin:0">Only admins approve lessons (Settings → Admins).</p>}

      <div class="section-head"><h2>Lessons</h2><p>Turn one off to stop the agent using it; it takes effect on the next review.</p></div>
      <div class="list">{all.map(x => <LessonRow key={x.id} x={x} admin={admin} />)}</div>
      {admin && (
        <div class="card bar-card">
          <input class="input" style="flex:1 1 300px" value={newLesson} onInput={e => setNewLesson(e.currentTarget.value)}
            placeholder="Add a lesson, e.g. In Florida, always order a municipal lien search." />
          <button class="btn primary" disabled={!newLesson.trim()} onClick={add}><Icon name="plus" /> Add Lesson</button>
        </div>)}

      <div class="section-head"><h2>Training Examples</h2><p>Re-run any of them from Training after lessons change.</p></div>
      {(examples || []).length ? (
        <div class="list">{[...examples].sort((a, b) => a.id - b.id).map(e => {
          const s = latest[e.id];
          return (
            <div key={e.id} class="card row-card p-fyi col">
              <span class="row-title" style="font-size:15px">{e.name}</span>
              <span class="row-sub">{e.deal_type} · {(e.expert_items || []).length} closer item(s)
                {s ? ` · agent found ${s.matched}/${s.total} on ${when(s.run_at)}` : ''}</span>
            </div>);
        })}</div>
      ) : <div class="note">No training examples yet. Add them on the Training tab.</div>}

      <div class="section-head"><h2>The Professional Checklist</h2><p>What the agent checks on every deal.</p>
        <button class="link-btn" onClick={() => setShowChecklist(!showChecklist)}>{showChecklist ? 'Hide' : 'Show'} All {checks}</button></div>
      {showChecklist && (ref?.checklist || []).map(g => (
        <section key={g.group} class="card" style="padding:16px 20px;display:flex;flex-direction:column;gap:8px">
          <h3 style="font-size:17px">{g.group}</h3>
          {g.checks.map(c => (
            <div key={c.id} style="font-size:14px"><b style="color:var(--tchb-indigo-700)">{c.name}</b>
              {c.deal_types.length ? <span class="row-sub"> (only {c.deal_types.join(', ')})</span> : ''}: {c.look_for}</div>))}
        </section>))}
    </>
  );
}
