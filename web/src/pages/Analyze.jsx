// Analyze: upload the commitment (and the contract), the agent reads it, the uploader confirms the deal details,
// then the full review runs and opens the deal. Same steps as the Streamlit app (titleagent/flows.py).
// #/analyze/update/<deal id> starts an updated commitment for that deal.
import { doc, getDoc } from 'firebase/firestore';
import { useEffect, useState } from 'preact/hooks';
import { api, jobId } from '../api.js';
import { useDeals, useJob, useReference, useSettings } from '../data.js';
import { db } from '../firebase.js';
import { go } from '../router.js';
import { Icon, Spinner, fmtDate, useToast } from '../ui.jsx';

const DRAFT_KEY = 'ta-draft';  // the draft survives a refresh (this tab only)
const MAX_MB = 50;

export function JobStep({ id, fallback = 'Starting' }) {
  const job = useJob(id);
  return (
    <div class="note" role="status" style="display:flex;gap:12px;align-items:center">
      <Spinner /><span><b>{job?.step || fallback}…</b><br />
        <span class="row-sub">This takes 1–3 minutes. You can keep this tab open and work in another one.</span></span>
    </div>
  );
}

export function PdfPicker({ label, hint, file, onFile, id }) {
  const [over, setOver] = useState(false);
  const pick = f => {
    if (!f) return;
    if (f.type !== 'application/pdf' && !/\.pdf$/i.test(f.name)) return onFile(null, 'Choose a PDF file.');
    if (f.size > MAX_MB * 1024 * 1024) return onFile(null, `That file is over ${MAX_MB} MB.`);
    onFile(f);
  };
  return (
    <label for={id} class={`drop ${over ? 'over' : ''} ${file ? 'has' : ''}`}
      onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}>
      <input id={id} type="file" accept="application/pdf,.pdf" class="sr" onChange={e => pick(e.currentTarget.files[0])} />
      <Icon name={file ? 'file' : 'upload'} size={22} />
      <b>{file ? file.name : label}</b>
      <span class="row-sub">{file ? `${file.size < 1048576 ? Math.max(1, Math.round(file.size / 1024)) + ' KB' : (file.size / 1048576).toFixed(1) + ' MB'} · click to change` : hint}</span>
    </label>
  );
}

function Upload({ updateFor, onRead }) {
  const toast = useToast();
  const { deals } = useDeals();
  const open = (deals || []).filter(d => d.status === 'open');
  const [commitment, setCommitment] = useState(null);
  const [contract, setContract] = useState(null);
  const [target, setTarget] = useState(updateFor || '');
  const [job, setJob] = useState(null);
  useEffect(() => setTarget(updateFor || ''), [updateFor]);
  const fileErr = (set, f, msg) => { if (msg) toast(msg, true); set(f); };
  const read = async () => {
    const id = jobId(); setJob(id);
    try {
      const [cPath, kPath] = await Promise.all([api.upload(commitment), contract ? api.upload(contract) : null]);
      const out = await api.read({ job_id: id, commitment_path: cPath, commitment_name: commitment.name,
        contract_path: kPath, contract_name: contract?.name || 'Contract.pdf', update_for: target ? Number(target) : null });
      onRead(out);
    } catch (e) { toast(e.message, true); setJob(null); }
  };
  return (
    <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:16px">
      <div class="two">
        <PdfPicker id="commitment" label="Title Commitment (PDF)" hint="Drop it here or click to choose. Scans are fine."
          file={commitment} onFile={(f, m) => fileErr(setCommitment, f, m)} />
        <PdfPicker id="contract" label="Purchase Contract (Optional)" hint="Lets the agent check seller, buyer, price and dates."
          file={contract} onFile={(f, m) => fileErr(setContract, f, m)} />
      </div>
      <label class="field"><span>Is This An Updated Commitment For A Deal Already In The App?</span>
        <select class="input" value={target} onChange={e => setTarget(e.currentTarget.value)}>
          <option value="">No, a new deal</option>
          {open.map(d => <option key={d.id} value={d.id}>Yes: {d.address || `Deal ${d.id}`} · {d.deal_type}</option>)}
        </select>
      </label>
      {job ? <JobStep id={job} fallback="Uploading" /> : (
        <div class="toolbar">
          <button class="btn primary pill" disabled={!commitment} onClick={read}><Icon name="right" /> Read Documents</button>
          <span class="row-sub">Reading takes about a minute. Nothing is saved as a deal until you confirm.</span>
        </div>)}
    </section>
  );
}

function Confirm({ draft, onDone, onStartOver }) {
  const toast = useToast();
  const ref = useReference();
  const settings = useSettings();
  const tcs = settings?.tcs || [];
  const p = draft.prefill || {};
  const s = draft.summary || {};
  const [f, setF] = useState({ address: p.address || '', state: p.state || '', deal_type: p.deal_type || '',
    closing_date: p.closing_date || '', tc: p.tc || '', title_company: p.title_company || '', notes: p.notes || '' });
  const [job, setJob] = useState(null);
  useEffect(() => { if (!f.tc && tcs.length) setF(x => ({ ...x, tc: tcs[0] })); }, [tcs.length]);
  const set = k => e => setF({ ...f, [k]: e.currentTarget.value });
  const missing = Object.entries(s.missing || {}).filter(([, v]) => v?.length);
  const run = async () => {
    const id = jobId(); setJob(id);
    try { const { deal_id } = await api.review({ job_id: id, draft_id: draft.draft_id, fields: f }); onDone(deal_id); }
    catch (e) { toast(e.message, true); setJob(null); }
  };
  return (
    <section class="card" style="padding:24px;display:flex;flex-direction:column;gap:16px">
      <h2 style="font-size:22px;font-weight:800">Confirm The Deal</h2>
      {missing.length ? (
        <div class="note red" role="alert"><b>Numbering check:</b> these printed items were not picked up even after a
          second read: {missing.map(([k, v]) => `Schedule ${k} #${v.join(', #')}`).join('; ')}. The review continues and
          shows them; check them by hand.</div>
      ) : (
        <div class="note green">Numbering check passed: {s.requirements} requirements and {s.exceptions} exceptions, every
          printed number accounted for.{s.scanned_pages?.length ? ` Scanned pages read as images: ${s.scanned_pages.join(', ')}.` : ''}</div>
      )}
      <div class="two">
        <label class="field"><span>Property Address</span><input class="input" value={f.address} onInput={set('address')} /></label>
        <label class="field"><span>State</span><input class="input" maxLength={2} value={f.state} onInput={set('state')} /></label>
        <label class="field"><span>Deal Type</span>
          <select class="input" value={f.deal_type} onChange={set('deal_type')}>
            {!f.deal_type && <option value="">Choose…</option>}
            {(ref?.deal_types || [f.deal_type]).filter(Boolean).map(t => <option key={t}>{t}</option>)}
          </select></label>
        <label class="field"><span>Closing Date</span>
          <input class="input" type="date" value={f.closing_date} onInput={set('closing_date')} /></label>
        <label class="field"><span>TC (Owns Every Item)</span>
          {tcs.length ? (
            <select class="input" value={f.tc} onChange={set('tc')}>{tcs.map(t => <option key={t}>{t}</option>)}</select>
          ) : <input class="input" value={f.tc} onInput={set('tc')} placeholder="Name of the TC" />}</label>
        <label class="field"><span>Title Company</span><input class="input" value={f.title_company} onInput={set('title_company')} /></label>
      </div>
      <label class="field"><span>Notes For The Agent (Optional)</span>
        <textarea class="input" rows={2} value={f.notes} onInput={set('notes')}
          placeholder="e.g. Seller is behind on payments; end buyer is a hard-money borrower." /></label>
      <div class="kv">
        {s.commitment_number && <span>Commitment <b>{s.commitment_number}</b>{s.commitment_date ? ` dated ${s.commitment_date}` : ''}</span>}
        {s.deadline_days ? <span>Requirements due within <b>{s.deadline_days} days</b></span> : null}
        {s.vested_owner && <span>Vested in <b>{s.vested_owner}</b></span>}
        {s.proposed_insured && <span>Proposed insured <b>{s.proposed_insured}</b></span>}
      </div>
      {job ? <JobStep id={job} /> : (
        <div class="toolbar">
          <button class="btn primary pill" disabled={!f.deal_type} onClick={run}><Icon name="check" /> Run Full Review</button>
          <button class="btn ghost pill" onClick={onStartOver}>Start Over</button>
          <span class="row-sub">{draft.update_for ? 'Statuses and notes carry over; new and removed items are marked.'
            : f.closing_date ? `Due dates count back from ${fmtDate(f.closing_date)}.` : 'Add the closing date for due dates.'}</span>
        </div>)}
    </section>
  );
}

export function Analyze({ arg, sub }) {
  const updateFor = arg === 'update' ? sub : '';
  const [draft, setDraft] = useState(null);
  useEffect(() => {  // after a refresh: the draft this tab was confirming
    let id = null;
    try { id = sessionStorage.getItem(DRAFT_KEY); } catch { /* private window */ }
    if (!id) return;
    getDoc(doc(db, 'drafts', id)).then(s => s.exists() && setDraft({ draft_id: id, ...s.data() })).catch(() => {});
  }, []);
  const keep = d => { setDraft(d); try { d ? sessionStorage.setItem(DRAFT_KEY, d.draft_id) : sessionStorage.removeItem(DRAFT_KEY); } catch { /* */ } };
  return (
    <>
      <section class="hero">
        <div class="hero-text">
          <div class="eyebrow-row"><span class="eyebrow">{updateFor ? 'Updated Commitment' : 'New Commitment'}</span></div>
          <h1 class="title">Analyze A <span class="accent">Commitment</span></h1>
          <p class="lede">Upload The Commitment. The Agent Lists Everything That Has To Happen Before This Deal Can Close.</p>
        </div>
      </section>
      {draft ? <Confirm draft={draft} onStartOver={() => keep(null)} onDone={id => { keep(null); go(`deal/${id}`); }} />
        : <Upload updateFor={updateFor} onRead={keep} />}
    </>
  );
}
