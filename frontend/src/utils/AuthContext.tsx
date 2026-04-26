import React from "react";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, updateProfile, onAuthStateChanged, User } from 'firebase/auth';
import { doc, getDoc, setDoc, getFirestore, onSnapshot } from 'firebase/firestore';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { firebaseApp } from 'app';
import { COLLECTIONS } from './firestore-schema';

interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  photoURL?: string;
  role?: string;
  company?: string;
  createdAt: Date;
  lastLogin: Date;
}

interface AuthContextType {
  user: User | null;
  userProfile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => Promise<void>;
  updateUserProfile: (data: Partial<UserProfile>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Initialize Firebase services using the extension
const auth = getAuth(firebaseApp);
const db = getFirestore(firebaseApp);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Listen for auth state changes
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      
      if (currentUser) {
        // Listen to the user's profile document
        const userDocRef = doc(db, COLLECTIONS.USERS, currentUser.uid);
        const unsubscribeProfile = onSnapshot(userDocRef, (docSnapshot) => {
          if (docSnapshot.exists()) {
            setUserProfile(docSnapshot.data() as UserProfile);
          } else {
            // If profile doesn't exist yet, create it
            const newProfile: UserProfile = {
              uid: currentUser.uid,
              email: currentUser.email || '',
              displayName: currentUser.displayName || '',
              photoURL: currentUser.photoURL || '',
              createdAt: new Date(),
              lastLogin: new Date(),
            };
            setDoc(userDocRef, newProfile);
            setUserProfile(newProfile);
          }
        });
        
        return () => unsubscribeProfile();
      } else {
        setUserProfile(null);
      }
      
      setIsLoading(false);
    });

    return () => unsubscribe();
  }, []);

  // Sign in with email and password
  const signIn = async (email: string, password: string) => {
    try {
      setIsLoading(true);
      setError(null);
      await signInWithEmailAndPassword(auth, email, password);
      
      // Update last login
      if (auth.currentUser) {
        const userDocRef = doc(db, COLLECTIONS.USERS, auth.currentUser.uid);
        await setDoc(userDocRef, { lastLogin: new Date() }, { merge: true });
      }
    } catch (err: any) {
      setError(err.message || 'Failed to sign in');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  // Sign up with email and password
  const signUp = async (email: string, password: string, displayName: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Create auth user
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      
      // Update displayName
      if (auth.currentUser) {
        await updateProfile(auth.currentUser, { displayName });
      }
      
      // Create user profile document
      const newUser = userCredential.user;
      const userProfile: UserProfile = {
        uid: newUser.uid,
        email: newUser.email || '',
        displayName,
        createdAt: new Date(),
        lastLogin: new Date(),
      };
      
      const userDocRef = doc(db, COLLECTIONS.USERS, newUser.uid);
      await setDoc(userDocRef, userProfile);
      
    } catch (err: any) {
      setError(err.message || 'Failed to create account');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  // Sign out
  const signOutUser = async () => {
    try {
      await signOut(auth);
    } catch (err: any) {
      setError(err.message || 'Failed to sign out');
      throw err;
    }
  };

  // Update user profile
  const updateUserProfile = async (data: Partial<UserProfile>) => {
    try {
      if (!user) throw new Error('No authenticated user');
      
      const userDocRef = doc(db, COLLECTIONS.USERS, user.uid);
      await setDoc(userDocRef, data, { merge: true });
      
      // If displayName is updated, also update it in Auth
      if (data.displayName && auth.currentUser) {
        await updateProfile(auth.currentUser, { displayName: data.displayName });
      }
      
    } catch (err: any) {
      setError(err.message || 'Failed to update profile');
      throw err;
    }
  };

  const value = {
    user,
    userProfile,
    isLoading,
    error,
    signIn,
    signUp,
    signOut: signOutUser,
    updateUserProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
