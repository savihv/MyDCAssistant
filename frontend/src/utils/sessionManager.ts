import { firebaseApp, firebaseAuth } from "../app/auth/firebase";
import { COLLECTIONS } from "./firestore-schema";
import { collection, doc, setDoc, getDoc, updateDoc, Timestamp, query, orderBy, limit, getDocs, addDoc, getFirestore, serverTimestamp, deleteDoc, where } from "firebase/firestore";

export interface TroubleshootingSession {
  id: string;
  userId: string; // ID of the user who created the session
  company: string; // Company the session belongs to
  organization: string; // Organization within the company
  assignmentName: string;
  assignmentLocation?: string;
  assignmentDescription: string;
  timestamp: Timestamp;
  lastUpdated: Timestamp;
  status: 'new' | 'in-progress' | 'completed' | 'archived';
  media?: string[];
  transcript?: string;
  response?: string;
  responseAudioUrl?: string;
  feedback?:any;
  is_in_knowledge_base?: boolean; 
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Timestamp;
  audioUrl?: string | null;
  mediaUrls?: string[] | null;
}

// Initialize Firebase services
const firestore = getFirestore(firebaseApp);
const COLLECTION_NAME = COLLECTIONS.SESSIONS;

export interface SessionManager {
  createSession(data: {
    assignmentName: string;
    assignmentLocation?: string;
    assignmentDescription: string;
    organization: string;
  }): Promise<string>;
 
  getSession(sessionId: string): Promise<any | null>; // Consider defining a Session type
  getSessions(userId: string): Promise<any[]>; // Consider defining a Session type
  listSessions(companyId?: string, organizationFilter?: string): Promise<TroubleshootingSession[]>;
  addMessageToSession(sessionId: string, message: ChatMessage): Promise<string>;
  getConversationHistory(sessionId: string): Promise<ChatMessage[]>;
  addResponse(sessionId: string, response: string, responseAudioUrl?: string): Promise<void>;
  saveCommandAndGetId(
    sessionId: string,
    transcription: string,
    audioUrl?: string | null,
    mediaUrls?: string[] | null
  ): Promise<string>;
  updateSession(sessionId: string, data: Partial<Omit<TroubleshootingSession, 'id' | 'timestamp' | 'userId'>>): Promise<void>;
  updateStatus(sessionId: string, status: TroubleshootingSession['status']): Promise<void>;
  reopenSessionIfNeeded(sessionId: string): Promise<void>;
  addMedia(sessionId: string, mediaUrl: string): Promise<string[]>;
  addTranscript_DEPRECATED?(sessionId: string, transcript: string): Promise<void>;
}

export const sessionManager: SessionManager = {
  async getSessions(userId: string): Promise<any[]> {
    return [];
  },
  /**
   * Create a new troubleshooting session
   */
  async createSession(data: {
    assignmentName: string;
    assignmentLocation?: string;
    assignmentDescription: string;
    organization: string; // Added organization
  }): Promise<string> {
    // Ensure user is authenticated
    const currentUser = firebaseAuth.currentUser; // <--- CHANGE HERE
    if (!currentUser) {
      throw new Error("User must be authenticated to create a session");
    }

    // Get custom claims to extract company
    let companyClaim: string | null = null;
    try {
      const idTokenResult = await currentUser.getIdTokenResult(true); // Force refresh claims
      companyClaim = idTokenResult.claims.company as string || null;
    } catch (error) {
      console.error("Error getting user claims for session creation:", error);
      throw new Error("Could not verify user company for session creation.");
    }

    if (!companyClaim) {
      console.error("User company claim is missing. Cannot create session without company.");
      throw new Error("User company information is missing. Cannot create session.");
    }
    
    const sessionsRef = collection(firestore, COLLECTION_NAME);
    const docRef = doc(sessionsRef);
    
    const now = Timestamp.now();
    
    // Explicitly define the type for newSession to include company
    const newSessionData: Omit<TroubleshootingSession, 'id'> = {
      userId: currentUser.uid,
      company: companyClaim, // Add company here
      organization: data.organization, // Added organization
      assignmentName: data.assignmentName,
      assignmentLocation: data.assignmentLocation,
      assignmentDescription: data.assignmentDescription,
      timestamp: now,
      lastUpdated: now,
      status: 'new',
      // media, transcript, response, responseAudioUrl will be undefined initially
    };
    
    await setDoc(docRef, newSessionData);
    
    return docRef.id;
  },
  
  /**
   * Get a session by ID
   */
  async getSession(sessionId: string): Promise<any | null> {
    console.log(`[sessionManager DEBUG] getSession called for ID: ${sessionId}`);
    const firestore = getFirestore(firebaseApp);
    const docRef = doc(firestore, "troubleshootingSessions", sessionId);
    try {
      const docSnap = await getDoc(docRef);
      if (docSnap.exists()) {
        console.log("[sessionManager DEBUG] getSession found document:", docSnap.data());
        return { id: docSnap.id, ...docSnap.data() };
      } else {
        console.log("[sessionManager DEBUG] getSession: No document found for this ID.");
        return null;
      }
    } catch (error) {
      console.error("[sessionManager] Error getting session:", error);
      throw error;
    }
  },
  
  /**
   * Update a session
   */
  async updateSession(sessionId: string, data: Partial<Omit<TroubleshootingSession, 'id' | 'timestamp' | 'userId'>>): Promise<void> {
    // Ensure user is authenticated
    const currentUser = firebaseAuth.currentUser; // <--- CHANGE HERE
    if (!currentUser) {
      throw new Error("User must be authenticated to update a session");
    }
    
    // Verify the current user is the owner of this session
    const session = await this.getSession(sessionId);
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    if (session.userId !== currentUser.uid) {
      throw new Error("You don't have permission to update this session");
    }
    
    const docRef = doc(firestore, COLLECTION_NAME, sessionId);
    
    await updateDoc(docRef, {
      ...data,
      lastUpdated: Timestamp.now(),
    });
  },

  /**
   * Save a text command as a transcript in the voiceCommands subcollection
   * and update the session status.
   */
  /**
   * Saves a command (text or transcribed voice) to the voiceCommands subcollection
   * and updates the session status. Now returns the ID of the new command document.
   */
  async saveCommandAndGetId(
    sessionId: string,
    transcription: string,
    audioUrl?: string | null,
    mediaUrls?: string[] | null
  ): Promise<string> { // <-- MODIFIED return type
    const currentUser = firebaseAuth.currentUser;
    if (!currentUser) {
      throw new Error("User must be authenticated to save a command");
    }

    // Verify the current user is the owner of this session
    const session = await this.getSession(sessionId);
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    if (session.userId !== currentUser.uid) {
      throw new Error("You don't have permission to update this session");
    }

    // Path to the voiceCommands subcollection for this session
    const voiceCommandsRef = collection(firestore, COLLECTION_NAME, sessionId, COLLECTIONS.VOICE_COMMANDS);
    const newCommandDocRef = doc(voiceCommandsRef); // Create a new document with an auto-generated ID

      
    await setDoc(newCommandDocRef, {
      transcription: transcription,
      audioUrl: audioUrl === undefined ? null : audioUrl, // Store null if undefined
      mediaUrls: mediaUrls || null,
      timestamp: serverTimestamp(),
      userId: currentUser.uid,
    });

    // Also update the main session's status and lastUpdated time
    await this.updateSession(sessionId, { // <-- AWAITED
      status: 'in-progress'
    });

    return newCommandDocRef.id; // <-- RETURN ID
  },
  
  /**
   * Update session status
   */
  async updateStatus(sessionId: string, status: TroubleshootingSession['status']): Promise<void> {
    return this.updateSession(sessionId, { status });
  },
  
  /**
   * Reopens a session if it was completed.
   */
  async reopenSessionIfNeeded(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId);
    if (session && session.status === 'completed') {
      await this.updateStatus(sessionId, 'in-progress');
    }
  },

  /**
   * Add media to a session
   */
  async addMedia(sessionId: string, mediaUrl: string): Promise<string[]> { // MODIFIED: Return type
    const session = await this.getSession(sessionId);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    const updatedMedia = [...(session.media || []), mediaUrl]; // Create new array

    await this.updateSession(sessionId, {
      media: updatedMedia, // Use the new array for the update
      status: 'in-progress'
    });

    return updatedMedia; // MODIFIED: Return the updated media array
  },
  
  /**
   * Add transcript to a session
   */
  /**
   * DEPRECATED: Use saveCommandToSubcollection instead for consistent data storage.
   * Original function to add transcript directly to the parent session.
   */
  async addTranscript_DEPRECATED(sessionId: string, transcript: string): Promise<void> {
    return this.updateSession(sessionId, { 
      transcript,
      status: 'in-progress' 
    });
  },
  
  /**
   * Add response to a session
   */
  async addResponse(sessionId: string, response: string, responseAudioUrl?: string): Promise<void> {
    console.log(`[sessionManager DEBUG] addResponse called for ID: ${sessionId}`);
    console.log(`[sessionManager DEBUG] Data to write: response='${response}', responseAudioUrl='${responseAudioUrl}'`);
    const firestore = getFirestore(firebaseApp);
    const sessionRef = doc(firestore, "troubleshootingSessions", sessionId);
    try {
      await updateDoc(sessionRef, {
        response: response,
        responseAudioUrl: responseAudioUrl || null,
        lastUpdated: serverTimestamp(),
        status: 'completed',
      });
      console.log("[sessionManager DEBUG] addResponse: Successfully updated document.");
    } catch (error) {
      console.error(`[sessionManager] Error adding response to session ${sessionId}:`, error);
      throw error;
    }
  },
  
  /**
   * List all sessions for the current user, ordered by lastUpdated (descending)
   */
  async listSessions(companyId?: string, organizationFilter?: string): Promise<TroubleshootingSession[]> {
    // Ensure user is authenticated
    const currentUser = firebaseAuth.currentUser; // <--- CHANGE HERE
    if (!currentUser) {
      throw new Error("User must be authenticated to list sessions");
    }
    
    try {
      const sessionsRef = collection(firestore, COLLECTION_NAME);
      let conditions = [];
      if (companyId) {
        console.log(`Filtering sessions by companyId: ${companyId}`);
        conditions.push(where("company", "==", companyId));
      } else if (currentUser) {
        // Only filter by userId if companyId is not provided
        console.log(`Filtering sessions by userId: ${currentUser.uid}`);
        conditions.push(where("userId", "==", currentUser.uid));
      } else {
        // Should not happen if companyId or currentUser is expected
        console.warn("listSessions called without companyId and no current user for userId filtering.");
        return [];
      }

      if (organizationFilter && organizationFilter.trim() !== "") {
        console.log(`Filtering sessions by organization: ${organizationFilter}`);
        conditions.push(where("organization", "==", organizationFilter.trim()));
      }
      
      // Add orderBy last. It's important for Firestore that orderBy is consistent with where clauses,
      // especially if an inequality filter is used on a different field.
      // Since we are primarily filtering by company or user, and then optionally organization,
      // orderBy lastUpdated should be fine.
      conditions.push(orderBy("lastUpdated", "desc"));
      
      const finalQuery = query(sessionsRef, ...conditions);
      console.log("Final query conditions:", conditions);
      const querySnapshot = await getDocs(finalQuery);
      
      const sessions: TroubleshootingSession[] = [];
      
      querySnapshot.forEach((doc) => {
        sessions.push({
          id: doc.id,
          ...doc.data(),
        } as TroubleshootingSession);
      });
      
      return sessions;
    } catch (error) {
      console.error("Error fetching sessions:", error);
      // Return empty array instead of throwing error when collection doesn't exist
      return [];
    }
  },

  /**
   * @param sessionId The ID of the session
   * @returns An array of chat messages
   */
  async getConversationHistory(sessionId: string): Promise<ChatMessage[]> {
    console.log(`[sessionManager DEBUG] getConversationHistory called for ID: ${sessionId}`);
    const firestore = getFirestore(firebaseApp);
    const messagesColRef = collection(firestore, `troubleshootingSessions/${sessionId}/voiceCommands`);
    const q = query(messagesColRef, orderBy("timestamp", "asc"));

    try {
        const querySnapshot = await getDocs(q);
        console.log(`[sessionManager DEBUG] getConversationHistory found ${querySnapshot.docs.length} documents.`);
        const history: ChatMessage[] = [];

        querySnapshot.forEach(doc => {
            const data = doc.data();
            // Add the user message
            history.push({
                id: doc.id,
                role: 'user',
                content: data.transcription,
                timestamp: data.timestamp
            });

            // If there's a corresponding assistant response, add it too
            if (data.response) {
                history.push({
                    id: `${doc.id}-response`,
                    role: 'assistant',
                    content: data.response,
                    timestamp: data.responseTimestamp || data.timestamp, // Fallback to user timestamp
                    audioUrl: data.responseAudioUrl || null
                });
            }
        });
        console.log("[sessionManager DEBUG] getConversationHistory returning mapped history:", history);
        return history;
    } catch (error) {
        console.error(`[sessionManager] Error getting conversation history for session ${sessionId}:`, error);
        throw error; // Re-throw the error to be handled by the caller
    }
  },

  /**
   * @param sessionId The ID of the session
   * @param message The chat message object to add
   */
  async addMessageToSession(sessionId: string, message: ChatMessage): Promise<string> {
    console.log(`[sessionManager DEBUG] addMessageToSession called for session ${sessionId} with message:`, message);
    const firestore = getFirestore(firebaseApp);
    // The previous implementation was violating Firestore security rules
    // by sending 'role' and 'content' instead of the allowed fields.
    // The 'saveCommandAndGetId' function already handles this correctly.
    // We will leverage it here to ensure consistency and security.
    try {
      // The 'saveCommandAndGetId' function handles adding the command to the
      // 'voiceCommands' subcollection and updating the parent session document.
      const commandId = await this.saveCommandAndGetId(
        sessionId,
        message.content, // Maps 'content' to 'transcription'
        message.audioUrl,
        message.mediaUrls
      );
      console.log(`[sessionManager DEBUG] addMessageToSession: Successfully added message via saveCommandAndGetId. New command ID: ${commandId}`);
      return commandId;
    } catch (error) {
        console.error(`[sessionManager] Error adding message to session ${sessionId}:`, error);
        throw error;
    }
  },
};
