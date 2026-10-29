// Training: a commitment the team already worked + the closer's list → compare with the agent. Every miss becomes a
// suggested lesson in the Feedback Inbox (Knowledge); an admin approves it before the agent uses it.
import { useEffect, useMemo, useState } from 'preact/hooks';
import { api, jobId } from '../api.js';
import { PRIORITY, useReference } from '../data.js';
import { Icon, useToast } from '../ui.jsx';
import { JobStep, PdfPicker } from './Analyze.jsx';

// Same split as titleagent/training.py parse_expert_list: one item per numbered paragraph or blank-line block.
export function parseExpertList(text) {
  return text.trim().split(/\n\s*(?=\(?\d{1,3}[.)]\s)|\n\s*\n/)
    .map(c => c.replace(/\s+/g, ' ').trim()).filter(c => c.length > 3);
}

function Results({ out }) {
  const total = out.matched.length + out.missed.length;
  return (
    <>
      <div class="section-head">
        <h2>How The Agent Did</h2>
        <p>{total ? `Found ${out.matched.length} of ${total} of the closer's items (${Math.round(out.recall * 100)}%).`
          : `Clean title check: the agent marked ${out.blockers} Closing Blocker${out.blockers === 1 ? '' : 's'} (expected 0).`}
          {' '}AI cost ${out.cost_usd.toFixed(2)}.</p>
      </div>
      <div class="cols3">
        <div class="list">
          <div class="group-head"><h2>Both Found</h2><span class="chip green">{out.matched.length}</span></div>
          {out.matched.map((m, n) => (
            <div key={n} class="card row-card p-fyi col"><span class="row-title" style="font-size:15px">{m.expert}</span>
              <span class="row-sub">Agent: {m.title} · {PRIORITY[m.priority]}</span></div>))}
        </div>
        <div class="list">
          <div class="group-head"><h2>Agent Missed</h2><span class="chip red">{out.missed.length}</span></div>
          {out.missed.map((m, n) => (
            <div key={n} class="card row-card p-blocker col"><span class="row-title" style="font-size:15px">{m.expert}</span>
              {m.lesson && <span class="row-sub"><b>Suggested lesson:</b> {m.lesson}</span>}</div>))}
          {out.missed.length > 0 && <p class="row-sub" style="margin:0">Each one is waiting in Knowledge → Feedback Inbox
            for an admin to approve.</p>}
        </div>
        <div class="list">
          <div class="group-head"><h2>Agent Extra</h2><span class="chip">{out.extra.length}</span></div>
          {out.extra.map((x, n) => (
            <div key={n} class="card row-card p-before col"><span class="row-title" style="font-size:15px">{x.title}</span>
              <span class="row-sub">{PRIORITY[x.priority]} · {x.refs.join(', ')}</span></div>))}
          {out.extra.length > 0 && <p class="row-sub" style="margin:0">Extras are often good catches closers handle without
            writing down. If one is wrong, add a lesson in Knowledge.</p>}
        </div>
      </div>
    </>
  );
}

export function Training() {
  const toast = useToast();
  const ref = useReference();
  const [file, setFile] = useState(null);
  const [dealType, setDealType] = useState('');
  const [name, setName] = useState('');
  const [list, setList] = useState('');
  const [job, setJob] = useState(null);
  const [out, setOut] = useState(null);
  useEffect(() => { if (!dealType && ref?.deal_types?.length) setDealType(ref.deal_types[0]); }, [ref]);
  const expert = useMemo(() => (list.trim() ? parseExpertList(list) : []), [list]);
  const compare = async () => {
    const id = jobId(); setJob(id); setOut(null);
    try {
      const path = await api.upload(file);
      setOut(await api.training({ job_id: id, path, filename: file.name, deal_type: dealType || ref?.deal_types?.[0] || '',
        name: name.trim() || file.name, expert }));
    } catch (e) { toast(e.message, true); } finally { setJob(null); }
  };
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">Optional</span></div>
          <h1 class="title">Train The <span class="accent">Agent</span></h1>
          <p class="lede">Upload A Commitment Your Team Already Worked, Paste The Closer's List, And Compare.</p>
        </div>
      </section>
      <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:16px">
        <div class="two">
          <PdfPicker id="train-pdf" label="Worked Commitment (PDF)" hint="Drop it here or click to choose."
            file={file} onFile={(f, m) => { if (m) toast(m, true); setFile(f); }} />
          <div style="display:flex;flex-direction:column;gap:14px">
            <label class="field"><span>Deal Type</span>
              <select class="input" value={dealType} onChange={e => setDealType(e.currentTarget.value)}>
                {(ref?.deal_types || []).map(t => <option key={t}>{t}</option>)}
              </select></label>
            <label class="field"><span>Name For This Example</span>
              <input class="input" value={name} onInput={e => setName(e.currentTarget.value)} placeholder="e.g. Ohio, prior-owner judgments" /></label>
          </div>
        </div>
        <label class="field"><span>The Closer's List</span>
          <textarea class="input" rows={6} value={list} onInput={e => setList(e.currentTarget.value)}
            placeholder={'Paste it from the email as is, one item per numbered paragraph:\n7. Payment and Release of Prior Owner Judgment …\n8. Payment and Release of …'} /></label>
        <span class="row-sub">{expert.length ? `${expert.length} item${expert.length === 1 ? '' : 's'} found in the list.`
          : 'A clean title? Leave the list empty: the agent should then find no Closing Blockers.'}</span>
        {job ? <JobStep id={job} fallback="Uploading" /> : (
          <div class="toolbar">
            <button class="btn primary pill" disabled={!file} onClick={compare}><Icon name="cap" /> Compare With Agent</button>
            <span class="row-sub">A full review: 1–3 minutes and roughly $1–2 in AI usage.</span>
          </div>)}
      </section>
      {out && <Results out={out} />}
    </>
  );
}
