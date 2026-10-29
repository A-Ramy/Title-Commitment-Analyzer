// Live reads from Firestore (layout: titleagent/firestore_store.py). The page never writes: changes go through
// the engine, and these listeners show them a moment later on every open screen.
import { collection, doc, limit, onSnapshot, orderBy, query } from 'firebase/firestore';
import { getBytes, ref } from 'firebase/storage';
import { useEffect, useState } from 'preact/hooks';
import { api } from './api.js';
import { db, storage } from './firebase.js';

export const PRIORITY = { blocker: 'Closing Blocker', before: 'Before Closing', fyi: 'Review / FYI' };
export const PRIORITY_ORDER = ['blocker', 'before', 'fyi'];
export const STATUSES = ['Open', 'Ordered', 'Received', 'Cleared', 'Waived'];
export const DONE = new Set(['Cleared', 'Waived']);
export const isOpen = i => !DONE.has(i.status) && i.change !== 'removed';

function useLive(make, deps) {
  const [state, setState] = useState({ data: undefined, error: null });
  useEffect(() => {
    const target = make();
    if (!target) { setState({ data: null, error: null }); return undefined; }
    return onSnapshot(target,
      snap => setState({ data: snap.docs ? snap.docs.map(d => ({ _id: d.id, ...d.data() })) : snap.exists() ? snap.data() : null,
        error: null }),
      error => setState({ data: null, error }));
  }, deps);
  return state;
}

export function useDeals() {
  const { data, error } = useLive(() => collection(db, 'deals'), []);
  const deals = data ? [...data].sort((a, b) => (b.updated_at?.seconds || 0) - (a.updated_at?.seconds || 0)) : data;
  return { deals, error };
}

export const useDeal = id => useLive(() => (id ? doc(db, 'deals', String(id)) : null), [id]);

export function useItems(dealId) {
  const { data, error } = useLive(() => (dealId ? collection(db, 'deals', String(dealId), 'items') : null), [dealId]);
  return { items: data ? [...data].sort((a, b) => a.position - b.position).map(d => ({ ...d.data, _doc: d._id })) : data, error };
}

// Every open deal's items, for the Deals page counts. Small team: one listener per open deal.
export function useAllItems(dealIds) {
  const [byDeal, setByDeal] = useState({});
  const key = dealIds.join(',');
  useEffect(() => {
    const offs = dealIds.map(id => onSnapshot(collection(db, 'deals', String(id), 'items'),
      snap => setByDeal(prev => ({ ...prev, [id]: snap.docs.map(d => d.data().data) })), () => {}));
    return () => offs.forEach(off => off());
  }, [key]);
  return byDeal;
}

// The latest review run and its full analysis (Storage runs/<id>.json: coverage, Schedule A, corrections).
export function useLatestRun(dealId) {
  const { data: runs } = useLive(
    () => (dealId ? query(collection(db, 'deals', String(dealId), 'runs'), orderBy('id', 'desc'), limit(1)) : null),
    [dealId]);
  const run = runs?.[0] || null;
  const [analysis, setAnalysis] = useState(null);
  useEffect(() => {
    if (!run?.analysis_path) { setAnalysis(null); return undefined; }
    let live = true;
    getBytes(ref(storage, run.analysis_path))
      .then(b => live && setAnalysis(JSON.parse(new TextDecoder().decode(b))))
      .catch(() => live && setAnalysis(null));
    return () => { live = false; };
  }, [run?.analysis_path]);
  return { run, analysis, loading: runs === undefined };
}

// Saved settings over the engine's defaults (Python DEFAULT_SETTINGS), exactly as the engine sees them.
export function useSettings() {
  const { data } = useLive(() => collection(db, 'settings'), []);
  const ref = useReference();
  if (!data || !ref) return null;
  const saved = Object.fromEntries(data.map(d => [d._id, d.value]));
  return { ...ref.settings_defaults, ...saved,
    due_offsets: { ...ref.settings_defaults.due_offsets, ...(saved.due_offsets || {}) } };
}

export const useJob = id => useLive(() => (id ? doc(db, 'jobs', id) : null), [id]).data;

// Deal types, the professional checklist and connections, from the engine (once per page load).
let referenceCache = null;
export function useReference() {
  const [ref, setRef] = useState(referenceCache);
  useEffect(() => {
    if (referenceCache) return;
    api.call('GET', '/v1/reference')
      .then(r => { referenceCache = r; setRef(r); }).catch(() => {});
  }, []);
  return ref;
}
