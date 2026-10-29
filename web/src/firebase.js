import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, connectAuthEmulator, getAuth, signInWithCredential, signInWithPopup, signOut } from 'firebase/auth';
import { connectFirestoreEmulator, getFirestore } from 'firebase/firestore';
import { connectStorageEmulator, getStorage } from 'firebase/storage';
import { EMULATORS, TEAM_DOMAIN, firebaseConfig } from './config.js';

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);

if (EMULATORS) {
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
  connectFirestoreEmulator(db, '127.0.0.1', 8085);
  connectStorageEmulator(storage, '127.0.0.1', 9199);
  // Tests only: the Auth emulator accepts a made-up Google account without the popup. Never in the real build.
  window.__emulatorSignIn = (email, verified = true) => signInWithCredential(auth, GoogleAuthProvider.credential(
    JSON.stringify({ sub: 'emu-' + email, email, email_verified: verified, name: email.split('@')[0] })));
}

export function teamAccount(user) {
  const email = (user?.email || '').toLowerCase();
  return !!user && user.emailVerified && email.endsWith('@' + TEAM_DOMAIN);
}

export async function signIn() {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ hd: TEAM_DOMAIN, prompt: 'select_account' });  // offer company accounts first
  const { user } = await signInWithPopup(auth, provider);
  if (!teamAccount(user)) {
    await signOut(auth);
    throw new Error(`${user.email} isn't a ${TEAM_DOMAIN} account. Sign in with your company Google account.`);
  }
  return user;
}

export const signOutNow = () => signOut(auth);
