import { createContext, useContext, useState } from 'react';
import { firebaseAuth } from "../app";

// This file is currently NOT being used. The app uses Firebase Authentication directly from the extension.
// See App.tsx for implementation.
// This file is kept for reference only.

/**
 * @deprecated - Use authentication from Firebase extension instead
 */
export const FirebaseWrapper = () => {
  // The App is now using Firebase Authentication from the extension
  // This component is not needed anymore
  return null;
};
