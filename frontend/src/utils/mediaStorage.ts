import { ref, uploadBytesResumable, getDownloadURL, deleteObject, getStorage } from 'firebase/storage';
import { collection, addDoc, Timestamp, doc, updateDoc, arrayUnion, getFirestore } from 'firebase/firestore';
import { firebaseApp } from "app";
import { COLLECTIONS } from './firestore-schema';
import { TroubleshootingSession } from './sessionManager';

// Initialize Firebase services using the extension
const storage = getStorage(firebaseApp);
const firestore = getFirestore(firebaseApp);
// Ensure the collection name is defined (important for Firestore setup)
const COLLECTION_NAME = COLLECTIONS.SESSIONS;

export interface MediaFile {
  id: string;
  file: File;
  preview?: string;
  uploadProgress?: number;
  downloadURL?: string;
  error?: string;
}

/**
 * Upload media file to Firebase Storage with secure path handling
 * @param file - File to upload
 * @param sessionId - ID of the troubleshooting session
 * @returns Promise with download URL
 */

export const uploadMediaFile = async (file: File, sessionId: string): Promise<string> => {
  // Create a storage reference with a secure path
  const timestamp = new Date().getTime();
  const secureFileName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
  const secureSessionId = sessionId.replace(/[^a-zA-Z0-9._-]/g, '_');
  const fileName = `${secureSessionId}/${timestamp}-${secureFileName}`;
  const storageRef = ref(storage, `media/${fileName}`);
  
  // Upload the file
  const uploadTask = uploadBytesResumable(storageRef, file);
  
  // Return a promise that resolves with the download URL
  return new Promise((resolve, reject) => {
    uploadTask.on(
      'state_changed',
      (snapshot) => {
        // Track upload progress if needed
        const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
        console.log(`Upload progress: ${progress}%`);
      },
      (error) => {
        // Handle unsuccessful uploads
        console.error('Upload failed:', error);
        reject(error);
      },
      async () => {
        // Handle successful uploads
        try {
          const downloadURL = await getDownloadURL(uploadTask.snapshot.ref);
          resolve(downloadURL);
        } catch (error) {
          console.error('Failed to get download URL:', error);
          reject(error);
        }
      }
    );
  });
};

/**
 * Add media file to a troubleshooting session
 * @param sessionId - ID of the session
 * @param mediaFile - Media file object
 * @returns Promise with download URL
 */
export const addMediaToSession = async (
  sessionId: string,
  mediaFile: MediaFile
): Promise<string> => {
  try {
    // 1. Upload file to Storage
    const downloadURL = await uploadMediaFile(mediaFile.file, sessionId);
    
    // 2. Update the session with the media reference
    const sessionRef = doc(firestore, COLLECTION_NAME, sessionId);
    await updateDoc(sessionRef, {
      media: arrayUnion(downloadURL),
      lastUpdated: Timestamp.now(),
      status: 'in-progress'
    });
    
    return downloadURL;
  } catch (error) {
    console.error('Failed to add media to session:', error);
    throw error;
  }
};

/**
 * Delete a media file
 * @param url - URL of the file to delete
 */
export const deleteMediaFile = async (url: string): Promise<void> => {
  try {
    // Extract the path from the URL
    const filePath = extractPathFromUrl(url);
    const storageRef = ref(storage, filePath);
    
    // Delete the file
    await deleteObject(storageRef);
  } catch (error) {
    console.error('Failed to delete media file:', error);
    throw error;
  }
};

/**
 * Extract path from Firebase Storage URL
 * @param url - Firebase Storage URL
 * @returns Storage path
 */
const extractPathFromUrl = (url: string): string => {
  try {
    // Firebase Storage URLs contain a token after the path
    // Format: https://firebasestorage.googleapis.com/v0/b/[bucket]/o/[path]?token=[token]
    const pathMatch = url.match(/o\/([^?]+)/);
    if (pathMatch && pathMatch[1]) {
      return decodeURIComponent(pathMatch[1]);
    }
    throw new Error('Invalid Firebase Storage URL format');
  } catch (error) {
    console.error('Error extracting path from URL:', error);
    throw error;
  }
};
