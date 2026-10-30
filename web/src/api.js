// The engine (engine/main.py): every call carries the signed-in person's Firebase ID token.
import { ref, uploadBytes } from 'firebase/storage';
import { ENGINE_URL } from './config.js';
import { auth, storage } from './firebase.js';

export class ApiError extends Error {}

async function call(method, path, body, { raw = false } = {}) {
  const user = auth.currentUser;
  if (!user) throw new ApiError('Sign in first.');
  const token = await user.getIdToken();
  let res;
  try {
    res = await fetch(ENGINE_URL + path, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Couldn't reach the Title Commitment Agent. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail; } catch { /* not JSON */ }
    throw new ApiError(typeof detail === 'string' && detail ? detail : `Something went wrong (${res.status}).`);
  }
  return raw ? res : res.json();
}

export const jobId = () => 'job-' + crypto.randomUUID().replace(/-/g, '').slice(0, 24);

export const api = {
  call,
  me: () => call('GET', '/v1/me'),
  read: body => call('POST', '/v1/read', body),
  review: body => call('POST', '/v1/review', body),
  rerun: (dealId, job_id) => call('POST', `/v1/deals/${dealId}/rerun`, { job_id }),
  training: body => call('POST', '/v1/training', body),
  setItem: (dealId, body) => call('PATCH', `/v1/deals/${dealId}/items`, body),
  setDeal: (dealId, status) => call('PATCH', `/v1/deals/${dealId}`, { status }),
  missing: (dealId, body) => call('POST', `/v1/deals/${dealId}/missing`, body),
  itemFeedback: (dealId, body) => call('POST', `/v1/deals/${dealId}/feedback`, body),
  google: (dealId, kind, include) => call('POST', `/v1/deals/${dealId}/google`, { kind, include }),
  resolve: (id, approve, lesson) => call('POST', `/v1/feedback/${id}/resolve`, { approve, lesson }),
  addLesson: text => call('POST', '/v1/lessons', { text }),
  setLesson: (id, body) => call('PATCH', `/v1/lessons/${id}`, body),
  putSettings: body => call('PUT', '/v1/settings', body),
  googleCheck: () => call('POST', '/v1/google/check'),

  async download(dealId, format, include) {
    const res = await call('GET', `/v1/deals/${dealId}/export?format=${format}&include=${include}`, null, { raw: true });
    const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || `export.${format}`;
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  },

  // A PDF for the engine to read: into the person's own Storage folder (storage rules), then the engine takes it.
  async upload(file) {
    const user = auth.currentUser;
    const path = `uploads/${user.uid}/${crypto.randomUUID()}.pdf`;
    await uploadBytes(ref(storage, path), file, { contentType: 'application/pdf' });
    return path;
  },
};
