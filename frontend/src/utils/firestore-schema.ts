/**
 * This file defines the Firestore database schema and collections
 * It provides type safety and documentation for the database structure
 * 
 * IMPORTANT: Make sure to configure security rules in the Firebase console 
 * to match the rules defined in this file.
 */

import { Timestamp } from 'firebase/firestore';

// User collection
export interface User {
  uid: string;           // Firebase Auth UID
  email: string;         // User email
  displayName?: string;  // Optional display name
  role: 'technician' | 'company_admin' | 'system_admin';
  approvalStatus: 'pending_approval' | 'approved' | 'rejected';
  company?: string;      // Optional company name
  organization?: string;  // Optional organization within company
  createdAt: Timestamp; // When the user was created
  lastActive?: Timestamp; // Last user activity
  permissions?: string[]; // Optional array of special permissions
  rejectionReason?: string; // Reason for rejection if applicable
}

// TroubleshootingSession collection
export interface TroubleshootingSession {
  id: string;            // Document ID
  uid: string;        // ID of the user who created the session
  assignmentName: string; // Name of the troubleshooting assignment
  assignmentLocation?: string; // Optional location information
  assignmentDescription: string; // Description of the problem/assignment
  timestamp: Timestamp;  // When the session was created
  lastUpdated: Timestamp; // When the session was last updated
  status: 'new' | 'in-progress' | 'completed' | 'archived';
  media?: string[];      // Array of media URLs (images/videos)
  transcript?: string;   // Voice command transcript
  response?: string;     // AI response in text format
  responseAudioUrl?: string; // URL to audio version of response
  tags?: string[];       // Optional tags for categorization
}

// Feedback collection
export interface Feedback {
  id: string;            // Document ID
  sessionId: string;     // ID of the session this feedback relates to
  uid: string;        // ID of the user who gave the feedback
  company?: string;      // Company of the user who gave feedback
  organization?: string; // Organization within company
  sessionOrganization?: string; // Organization selected during session creation
  timestamp: Timestamp;  // When the feedback was given
  isHelpful: boolean;    // Whether the response was helpful (thumbs up/down)
  comment?: string;      // Optional text comment
  audioUrl?: string;     // Optional URL to audio feedback recording
  audioTranscript?: string; // Optional transcription of the audio feedback
  context: {
    transcript: string;   // Original voice command
    response: string;     // AI response that received feedback
  };
}

// Document collection for company knowledge base
export interface Document {
  id: string;                        // Document ID
  title: string;                     // Document title
  description?: string;              // Optional document description
  fileUrl: string;                   // URL to the stored file
  fileName: string;                  // Original filename
  fileType: string;                  // MIME type
  fileSize: number;                  // Size in bytes
  uploadedBy: string;                // User ID who uploaded the document
  company: string;                   // Company the document belongs to
  organization?: string;             // Optional organization within company
  uploadedAt: Timestamp;             // When the document was uploaded
  lastModified?: Timestamp;          // When the document was last modified
  status: 'processing' | 'active' | 'archived' | 'flagged' | 'rejected'; // Document status
  moderationStatus: 'pending' | 'approved' | 'rejected' | 'flagged';    // Moderation status
  moderationDetails?: {              // Optional moderation details
    moderatedBy?: string;            // User ID or 'automated'
    moderatedAt?: Timestamp;         // When moderation occurred
    reason?: string;                 // Reason for rejection or flagging
    confidence?: number;             // Confidence score for automated moderation
  };
  tags?: string[];                   // Optional tags for categorization
  metadata?: Record<string, any>;    // Additional metadata
  isProcessed: boolean;              // Whether document has been processed for RAG
  processingError?: string;          // Error message if processing failed
}

// DocumentChunk collection for document chunks used in RAG
export interface DocumentChunk {
  id: string;                        // Chunk ID
  documentId: string;                // Parent document ID
  company: string;                   // Company the chunk belongs to
  organization?: string;             // Optional organization within company
  content: string;                   // Text content of the chunk
  pageNumber?: number;               // Page number for PDFs
  chunkIndex: number;                // Index of the chunk within the document
  embedding?: number[];              // Vector embedding (may be stored elsewhere)
  embeddingModelVersion?: string;    // Version of embedding model used
  metadata?: Record<string, any>;    // Additional metadata
  createdAt: Timestamp;              // When the chunk was created
  lastUpdated?: Timestamp;           // When the chunk was last updated
}

// PendingRequest collection for user role approval requests
export interface PendingRequest {
  id: string;                       // Request ID (same as user ID)
  uid: string;                   // User ID who requested approval
  userEmail: string;                // Email of the user
  displayName: string;              // Display name of the user
  requestedRole: 'technician' | 'company_admin'; // Role requested
  company: string | null;           // Company name (required for company_admin)
  organization?: string | null;
  requestedAt: Timestamp;           // When the request was made
  status: 'pending' | 'approved' | 'rejected'; // Request status
  reviewedBy?: string;              // User ID who reviewed the request
  reviewedAt?: Timestamp;           // When the request was reviewed
  rejectionReason?: string;         // Reason for rejection if applicable
  notificationSent?: boolean;       // Whether notification was sent to user
  notificationSentAt?: Timestamp;   // When notification was sent
}


export interface AuditLog {
  id: string;                        // Log ID
  timestamp: Timestamp;              // When the action occurred
  uid: string;                    // User who performed the action
  userEmail: string;                 // Email of the user
  userRole: string;                  // Role of the user
  company?: string;                  // Company of the user, if applicable
  action: string;                    // Action performed (e.g., 'upload_document', 'delete_document')
  resourceType: string;              // Type of resource affected (e.g., 'document', 'user')
  resourceId: string;                // ID of the resource affected
  details: Record<string, any>;      // Additional details about the action
  ipAddress?: string;                // IP address of the user
  userAgent?: string;                // User agent of the browser/client
}

// ModerationQueue collection for content moderation
export interface ModerationQueueItem {
  id: string;                        // Queue item ID
  resourceType: string;              // Type of resource to moderate (e.g., 'document', 'image')
  resourceId: string;                // ID of the resource to moderate
  company: string;                   // Company the resource belongs to
  submittedBy: string;               // User ID who submitted the resource
  submittedAt: Timestamp;            // When the resource was submitted
  status: 'pending' | 'in_review' | 'approved' | 'rejected'; // Moderation status
  automatedResults?: {               // Results from automated moderation
    score: number;                   // Overall confidence score
    categories: Record<string, number>; // Category-specific scores
    flagged: boolean;                // Whether the content was flagged
    reason?: string;                 // Reason for flagging
  };
  reviewedBy?: string;               // User ID who reviewed the item (if manual review)
  reviewedAt?: Timestamp;            // When the item was reviewed
  reviewNotes?: string;              // Notes from the reviewer
  priority: 'low' | 'medium' | 'high'; // Priority for review
}


// Firebase collections paths
export const COLLECTIONS = {
  USERS: 'users',
  SESSIONS: 'troubleshootingSessions',
  FEEDBACK: 'feedback',
  VOICE_COMMANDS: 'voiceCommands', // Added for clarity and consistency
  DOCUMENTS: 'documents',           // Company knowledge base documents
  DOCUMENT_CHUNKS: 'documentChunks', // Chunked text from documents for RAG
  AUDIT_LOGS: 'auditLogs',           // Audit trail for admin actions
  MODERATION: 'moderationQueue',     // Content moderation queue
  PENDING_REQUESTS: 'pendingRequests', // Pending user role approval requests
  // Add more collections as needed
};

/**
 * Example Firestore Security Rules
 *
 * ```
 * rules_version = '2';
 * service cloud.firestore {
 *   match /databases/{database}/documents {
 *     // Allow authenticated users to read/write their own data
 *     match /users/{uid} {
 *       allow read, write: if request.auth != null && request.auth.uid == uid;
 *       
 *       // Allow admins to read all user documents
 *       allow read: if request.auth != null && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
 *     }
 *     
 *     // Sessions can only be read/written by their owners
 *     match /troubleshootingSessions/{sessionId} {
 *       allow read, write: if request.auth != null && request.auth.uid == resource.data.uid;
 *       
 *       // Allow creation of new sessions (uid must match auth)
 *       allow create: if request.auth != null && request.resource.data.uid == request.auth.uid;
 *       
 *       // Allow admins and supervisors to read all sessions
 *       allow read: if request.auth != null && 
 *                    (get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin' ||
 *                     get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'supervisor');
 *
 *      // Rules for voiceCommands subcollection within a session
 *      match /voiceCommands/{commandId} {
 *        // Helper function to check if the requester is the owner of the parent session
 *        function isSessionOwner() {
 *          return request.auth != null && request.auth.uid == get(/databases/$(database)/documents/troubleshootingSessions/$(sessionId)).data.uid;
 *        }
 *
 *        // Allow owner of the session to read, update, delete their own voice commands
 *        allow read, update, delete: if isSessionOwner();
 *
 *        // Specific create rule for voice commands
 *        allow create: if isSessionOwner() &&
 *                       request.resource.data.keys().hasAll(['transcription', 'timestamp', 'userId', 'audioUrl']) &&
 *                       request.resource.data.keys().hasOnly(['transcription', 'timestamp', 'userId', 'audioUrl']) &&
 *                       request.resource.data.transcription is string && request.resource.data.transcription.size() > 0 &&
 *                       request.resource.data.timestamp == request.time &&
 *                       request.resource.data.userId == request.auth.uid &&
 *                       (request.resource.data.audioUrl == null || 
 *                        (request.resource.data.audioUrl is string && 
 *                         request.resource.data.audioUrl.size() > 0 && 
 *                         request.resource.data.audioUrl.matches('^https?://.+')) ); // audioUrl can be null or a valid HTTP/S URL
 *      }
 *     }
 *   }
 * }
 * ```
 */
