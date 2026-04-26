import { firebaseApp, firebaseAuth } from "../app";
import { COLLECTIONS } from "./firestore-schema";
import { collection, doc, setDoc, getDoc, getDocs, query, where, orderBy, Timestamp, getFirestore, addDoc, updateDoc } from "firebase/firestore";
import { Feedback, TroubleshootingSession } from "./firestore-schema"; // Added TroubleshootingSession

// Initialize Firebase services
const firestore = getFirestore(firebaseApp);
const auth = firebaseAuth;
const COLLECTION_NAME = COLLECTIONS.FEEDBACK;

export interface FeedbackData {
  sessionId: string;
  isHelpful: boolean;
  comment?: string;
  audioUrl?: string;
  audioTranscript?: string;
}

export const feedbackManager = {
  /**
   * Create a new feedback entry
   */
  async createFeedback(data: FeedbackData): Promise<string> {
    // Ensure user is authenticated
    const currentUser = auth.currentUser;
    if (!currentUser) {
      throw new Error("User must be authenticated to create feedback");
    }
    
    // Get the session data to include context
    const sessionRef = doc(firestore, COLLECTIONS.SESSIONS, data.sessionId);
    const sessionSnap = await getDoc(sessionRef);
    
    if (!sessionSnap.exists()) {
      throw new Error(`Session with ID ${data.sessionId} not found`);
    }
    
    const sessionData = sessionSnap.data() as TroubleshootingSession;
    
    // Get the user's company and organization data
    const userRef = doc(firestore, COLLECTIONS.USERS, currentUser.uid);
    const userSnap = await getDoc(userRef);
    
    let userCompany = undefined;
    let userOrganization = undefined;
    
    if (userSnap.exists()) {
      const userData = userSnap.data();
      userCompany = userData.company;
      userOrganization = userData.organization;
    }
    
    // Create a new feedback document
    const feedbacksRef = collection(firestore, COLLECTION_NAME);
    
    const now = Timestamp.now();
    
    const newFeedback: Omit<Feedback, 'id'> = {
      sessionId: data.sessionId,
      uid: currentUser.uid,
      company: userCompany, // Company from user profile
      organization: userOrganization === undefined ? null : userOrganization, // Organization from user profile
      sessionOrganization: (sessionData as any).organization === undefined ? null : (sessionData as any).organization, // Organization from the session
      timestamp: now,
      isHelpful: data.isHelpful,
      comment: data.comment === undefined ? null : data.comment,
      audioUrl: data.audioUrl === undefined ? null : data.audioUrl,
      audioTranscript: data.audioTranscript === undefined ? null : data.audioTranscript,
      context: {
        transcript: sessionData.transcript || "",
        response: sessionData.response || "",
      }
    };
    
    // Add the document to the collection
    const docRef = await addDoc(feedbacksRef, newFeedback);
    
    return docRef.id;
  },
  
  /**
   * Update an existing feedback
   */
  async updateFeedback(feedbackId: string, data: Partial<Omit<FeedbackData, 'sessionId'>>): Promise<void> {
    // Ensure user is authenticated
    const currentUser = auth.currentUser;
    if (!currentUser) {
      throw new Error("User must be authenticated to update feedback");
    }
    
    const docRef = doc(firestore, COLLECTION_NAME, feedbackId);
    const docSnap = await getDoc(docRef);
    
    if (!docSnap.exists()) {
      throw new Error(`Feedback with ID ${feedbackId} not found`);
    }
    
    const feedbackData = docSnap.data();
    
    // Verify the current user is the owner of this feedback
    if (feedbackData.uid !== currentUser.uid) {
      throw new Error("You don't have permission to update this feedback");
    }
    
    await updateDoc(docRef, data);
  },
  
  /**
   * Get feedback for a session
   */
  async getFeedbackForSession(sessionId: string): Promise<Feedback | null> {
    // Ensure user is authenticated
    const currentUser = auth.currentUser;
    if (!currentUser) {
      throw new Error("User must be authenticated to get feedback");
    }
    
    const feedbacksRef = collection(firestore, COLLECTION_NAME);
    const q = query(
      feedbacksRef,
      where("sessionId", "==", sessionId),
      where("uid", "==", currentUser.uid),
      orderBy("timestamp", "desc")
    );
    
    const querySnapshot = await getDocs(q);
    
    if (querySnapshot.empty) {
      return null;
    }
    
    // Get the most recent feedback
    const doc = querySnapshot.docs[0];
    
    return {
      id: doc.id,
      ...doc.data()
    } as Feedback;
  },
  
  /**
   * Check if a user has provided feedback for a session
   */
  async hasFeedback(sessionId: string): Promise<boolean> {
    const feedback = await this.getFeedbackForSession(sessionId);
    return feedback !== null;
  },
};
