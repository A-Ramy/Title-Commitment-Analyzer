// The Firebase web config is public by design (every Firebase page ships it); access is enforced by the security
// rules (firebase/) and the engine's sign-in check.
export const firebaseConfig = {
  apiKey: 'AIzaSyBzhfk4YrsCmBANAb0mX-BtmQv_VJphQgs',
  authDomain: 'title-commitment-agent.firebaseapp.com',
  projectId: 'title-commitment-agent',
  storageBucket: 'title-commitment-agent.firebasestorage.app',
  messagingSenderId: '622792668017',
  appId: '1:622792668017:web:b593811d33156e1d1ebcd0',
};

// The engine on Cloud Run (engine/main.py). VITE_ENGINE_URL overrides it for local development.
export const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'https://title-agent-engine-622792668017.us-east1.run.app';

// Local development and tests: the Firebase emulators (VITE_EMULATORS=1), never the real project's data.
export const EMULATORS = import.meta.env.VITE_EMULATORS === '1';

export const TEAM_DOMAIN = 'totalchb.com';
