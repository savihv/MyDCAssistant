/**
 * This file contains Firebase security rules that should be used to secure your app.
 * Copy these rules into the Firebase Console for both Firestore and Storage.
 */

export const firestoreRules = `rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow users to read and write only their own data
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    
    // Allow users to read and write only their own troubleshooting sessions
    match /troubleshootingSessions/{sessionId} {
      allow create: if request.auth != null;
      allow read, update, delete: if request.auth != null && request.auth.uid == resource.data.uid;
      // Allow Company Admins to read sessions belonging to their company
      allow read: if request.auth != null && request.auth.token.company != null && request.auth.token.company == resource.data.company;
    }
    
    // Deny access to all other documents
    match /{document=**} {
      allow read, write: if false;
    }
  }
}`;

export const storageRules = `rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Allow authenticated users to read and write their own media files
    match /media/{sessionId}/{filename} {
      // Extract the session ID from the path
      function getSessionId() {
        return sessionId;
      }
      
      // Verify the user owns the session by checking Firestore
      function userOwnsSession() {
        let sessionData = firestore.get(/databases/(default)/documents/troubleshootingSessions/$(getSessionId())).data;
        return sessionData != null && request.auth.uid == sessionData.uid;
      }
      
      // Allow upload if user is authenticated
      allow create: if request.auth != null;
      
      // Allow read, update, delete if user owns the session
      allow read, update, delete: if request.auth != null && userOwnsSession();
    }
    
    // Deny access to all other files
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}`;

export const setupInstructions = `
# Firebase Setup Instructions

## Enable Firestore
1. Go to Firebase Console > Firestore Database
2. Click "Create Database"
3. Choose your location and start in production mode
4. Once created, go to the "Rules" tab
5. Replace the rules with the Firestore rules above
6. Click "Publish"

## Enable Storage
1. Go to Firebase Console > Storage
2. Click "Get Started"
3. Follow the setup wizard
4. Once created, go to the "Rules" tab
5. Replace the rules with the Storage rules above
6. Click "Publish"

## Authentication Methods
1. Go to Firebase Console > Authentication
2. Click "Get Started"
3. Enable Email/Password provider
4. (Optional) Enable Google provider

## Domain Configuration
1. Go to Firebase Console > Authentication > Settings
2. Add riff.new, riff.works, and your app domain to Authorized Domains
`;
