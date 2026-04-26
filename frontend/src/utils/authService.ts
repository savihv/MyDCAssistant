import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged, User } from 'firebase/auth';
import { doc, setDoc, getDoc, Timestamp, getFirestore } from 'firebase/firestore';
import { COLLECTIONS } from './firestore-schema';
import { firebaseApp, firebaseAuth } from "app";

// Use the Firebase auth from the extension
const auth = firebaseAuth;

// Initialize Firestore
const firestore = getFirestore(firebaseApp);

// User profile interface
export interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  role?: 'technician' | 'supervisor' | 'admin';
  company?: string;
  createdAt: number;
}

export const authService = {
  /**
   * Get the current user
   */
  getCurrentUser: () => {
    return auth.currentUser;
  },

  /**
   * Get the current user profile from Firestore
   */
  getUserProfile: async (uid: string): Promise<UserProfile | null> => {
    try {
      const userDoc = await getDoc(doc(firestore, COLLECTIONS.USERS, uid));
      if (userDoc.exists()) {
        return userDoc.data() as UserProfile;
      }
      return null;
    } catch (error) {
      console.error('Error getting user profile:', error);
      return null;
    }
  },
  
  /**
   * Update last active timestamp for a user
   */
  updateLastActive: async (uid: string): Promise<void> => {
    try {
      const userRef = doc(firestore, COLLECTIONS.USERS, uid);
      await setDoc(userRef, { lastActive: Timestamp.now() }, { merge: true });
    } catch (error) {
      console.error('Error updating last active timestamp:', error);
      // Don't throw - this is a non-critical operation
    }
  },

  /**
   * Register a new user
   */
  register: async (email: string, password: string, displayName?: string): Promise<User> => {
    try {
      // Create user in Firebase Auth
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      const user = userCredential.user;

      // Create user profile in Firestore
      await setDoc(doc(firestore, COLLECTIONS.USERS, user.uid), {
        uid: user.uid,
        email: user.email,
        displayName: displayName || '',
        role: 'technician', // Default role
        createdAt: Timestamp.now()
      });

      return user;
    } catch (error) {
      console.error('Error registering user:', error);
      throw error;
    }
  },

  /**
   * Sign in a user
   */
  signIn: async (email: string, password: string): Promise<User> => {
    try {
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      return userCredential.user;
    } catch (error) {
      console.error('Error signing in:', error);
      throw error;
    }
  },

  /**
   * Sign out the current user
   */
  signOut: async (): Promise<void> => {
    try {
      await signOut(auth);
    } catch (error) {
      console.error('Error signing out:', error);
      throw error;
    }
  },

  /**
   * Set up an auth state change listener
   */
  onAuthStateChanged: (callback: (user: User | null) => void) => {
    return onAuthStateChanged(auth, callback);
  }
};

export { auth };
