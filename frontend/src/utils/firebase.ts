import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

/**
 * @deprecated - This file is no longer in use. Import from 'app' directly instead:
 * import { firebaseApp, firebaseAuth } from 'app';
 * 
 * The Firebase extension provides these instances for you.
 */

// Firebase configuration
const firebaseConfig = {
  // This config is no longer used - the Firebase extension manages it now
};

/**
 * @deprecated - Use firebaseApp from 'app' instead
 */
export const app = null;

/**
 * @deprecated - Use firebaseAuth from 'app' instead
 */
export const auth = null;

/**
 * @deprecated - Use getFirestore(firebaseApp) instead
 */
export const db = null;

/**
 * @deprecated - Use getStorage(firebaseApp) instead
 */
export const storage = null;
