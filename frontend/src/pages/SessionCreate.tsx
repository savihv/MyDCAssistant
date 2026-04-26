//Session create
import React, { useState, useEffect } from "react";
import { TechnicianEmptyState } from "../components/TechnicianEmptyState";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { AudioRecorder } from "../components/AudioRecorder";
import { getStorage } from "firebase/storage";
import { ref, uploadBytes, getDownloadURL } from "firebase/storage";
import { Input } from "../extensions/shadcn/components/input";
import { useForm, Controller } from "react-hook-form";
import { apiClient } from "../app";
import { sessionManager } from "../utils/sessionManager";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { PendingApproval } from "../components/PendingApproval";
import { doc, getDoc, getFirestore, DocumentSnapshot } from "firebase/firestore";
import { firebaseApp, useCurrentUser } from "../app";
import { COLLECTIONS } from "../utils/firestore-schema";
import { Link } from "react-router-dom";

// Initialize Firebase Storage at the module level
const storage = getStorage(firebaseApp);

interface VoiceDescription {
  audioBlob: Blob;
  audioDuration: number;
  downloadURL?: string;
  transcription?: string;
}

export default function SessionCreate() {
  const navigate = useNavigate();
  const { user } = useCurrentUser();
  
  const [isPendingApproval, setIsPendingApproval] = useState(false);
  const [assignmentName, setAssignmentName] = useState("");
  const [assignmentLocation, setAssignmentLocation] = useState("");
  const [assignmentDescription, setAssignmentDescription] = useState("");
  const [organization, setOrganization] = useState(""); // Added organization state
  
  const [isUsingVoice, setIsUsingVoice] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [voiceDescription, setVoiceDescription] = useState<VoiceDescription | null>(null);
  
  useEffect(() => {
    const checkApprovalStatus = async () => {
      if (!user) return;
      
      try {
        const firestore = getFirestore(firebaseApp);
        let userDoc: DocumentSnapshot | null = null;
        
        try {
          userDoc = await getDoc(doc(firestore, COLLECTIONS.USERS, user.uid));
        } catch (error) {
          console.error('Error fetching user document:', error);
          // If the collection doesn't exist, don't show approval status
          return;
        }
        
        if (userDoc && userDoc.exists()) {
          const userData = userDoc.data();
          setIsPendingApproval(userData.approvalStatus === 'pending_approval' || userData.approvalStatus === 'rejected');
        }
      } catch (error) {
        console.error('Error checking approval status:', error);
      }
    };
    
    checkApprovalStatus();
  }, [user]);
  
  const handleRecordingComplete = (audioBlob: Blob, audioDuration: number) => {
    setVoiceDescription({
      audioBlob,
      audioDuration,
    });
  };
  
  const handleProcessVoiceDescription = async () => {
    if (!voiceDescription) return;
    
    setIsProcessing(true);
    setProcessingError(null);

    if (!user || !user.uid) {
      console.error("User not authenticated or UID missing for voice description upload.");
      setProcessingError("Authentication error. Cannot upload voice description.");
      setIsProcessing(false);
      return;
    }
    
    try {
      // 1. Upload the audio file to Firebase Storage
      // Make sure 'user' object is available and has 'uid'
      const audioPath = `assignment-descriptions/${user.uid}/${new Date().getTime()}.wav`;
      const audioRef = ref(storage, audioPath); // Use module-level storage instance
      
      await uploadBytes(audioRef, voiceDescription.audioBlob);
      const downloadURL = await getDownloadURL(audioRef);
      
      // 2. Transcribe the audio using our backend API
      // Convert Blob to File for the API call
      const audioFile = new File([voiceDescription.audioBlob], "audio.wav", { type: voiceDescription.audioBlob.type });
      
      console.log('Sending audio for transcription...');
      // Pass an object to the brain client, it will handle FormData creation
      const response = await apiClient.transcribe_audio({ audio: audioFile });
      const transcriptionData = await response.json();
      const transcription = transcriptionData.transcription;
      console.log('Transcription received:', transcription);
      
      // 3. Update state with the transcription
      setVoiceDescription(prev => ({
        ...prev!,
        downloadURL,
        transcription
      }));
      
      // 4. Update the assignment description field
      setAssignmentDescription(transcription);
      
      // 5. Switch back to text input mode
      setIsUsingVoice(false);
    } catch (error) {
      console.error("Error processing voice description:", error);
      // It's good to check the error type for more specific messages
      if (error instanceof Error) {
        setProcessingError(`Failed to process voice description: ${error.message}. Please try again.`);
      } else {
        setProcessingError("Failed to process voice description due to an unknown error. Please try again.");
      }
    } finally {
      setIsProcessing(false);
    }
  };
  
  const handleCreateSession = async () => {
    // Validate inputs
    if (!assignmentName.trim()) {
      alert("Please enter an assignment name");
      return;
    }
    
    if (!assignmentDescription.trim()) {
      alert("Please enter an assignment description");
      return;
    }
    if (!organization.trim()) { // Added organization validation
      alert("Please enter your organization (e.g., Maintenance, Field Engineering)");
      return;
    }
    
    setIsProcessing(true);
    setProcessingError(null);
    
    try {
      // Create the session using sessionManager
      const sessionId = await sessionManager.createSession({
        assignmentName: assignmentName.trim(),
        assignmentLocation: assignmentLocation.trim(), // Ensure this is trimmed or handled if empty
        assignmentDescription: assignmentDescription.trim(),
        organization: organization.trim(), // Added organization
      });
      
      // Navigate to media capture page
      navigate(`/MediaCapture?sessionId=${sessionId}`);
    } catch (error) {
      console.error("Error creating session:", error);
      const errorMessage = error instanceof Error ? error.message : "Failed to create session. Please try again.";
      setProcessingError(errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };
  
  return (
    <ProtectedRoute>
      <div className="flex flex-col min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center">
            <JuniorTechBotLogo className="w-8 h-8 mr-2" />
            <h1 className="text-xl font-bold">
              <span className="text-white">Junior</span>
              <span className="text-blue-400">TechBot</span>
            </h1>
          </div>
          <nav>
            <ul className="flex space-x-4">
              <li>
                <button onClick={() => navigate("/")} className="text-gray-300 hover:text-white">
                  Home
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/SessionCreate")} className="text-blue-400">
                  New Session
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/History")} className="text-gray-300 hover:text-white">
                  History
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/KnowledgeBaseSearch")} className="text-gray-300 hover:text-white">
                  Knowledge Base Search
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/ExpertSubmission")} className="text-gray-300 hover:text-white">
                  Expert Submission
                </button>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto py-8 px-4">
        <div className="flex-grow p-6 flex flex-col items-center justify-start">
          <div className="w-full max-w-4xl space-y-8">
            <h2 className="text-2xl font-bold mb-6">Start New Troubleshooting Session</h2>
            
            <PendingApproval onRedirect={() => navigate('/')} />
            
            {!isPendingApproval && (
              <>
                <div className="bg-gray-800 rounded-lg p-6 mb-8 border border-gray-700">
                  <h3 className="text-xl font-bold mb-4">Assignment Details</h3>
                  
                  <div className="mb-4">
                    <label htmlFor="assignmentName" className="block text-gray-300 mb-2">
                      Assignment Name
                    </label>
                    <input
                      type="text"
                      id="assignmentName"
                      placeholder="Enter assignment name or ID"
                      className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={assignmentName}
                      onChange={(e) => setAssignmentName(e.target.value)}
                    />
                  </div>
                  
                  <div className="mb-4">
                    <label htmlFor="assignmentLocation" className="block text-gray-300 mb-2">
                      Location (Optional)
                    </label>
                    <input
                      type="text"
                      id="assignmentLocation"
                      placeholder="Enter service location"
                      className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={assignmentLocation}
                      onChange={(e) => setAssignmentLocation(e.target.value)}
                    />
                  </div>

                  {/* Organization Input */}
                  <div className="mb-4">
                    <label htmlFor="organization" className="block text-gray-300 mb-2">
                      Organization <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="organization"
                      placeholder="Enter your organization (e.g., Maintenance)"
                      className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={organization}
                      onChange={(e) => setOrganization(e.target.value)}
                    />
                  </div>
                  
                  {!isUsingVoice ? (
                    <div className="mb-4">
                      <div className="flex justify-between items-center mb-2">
                        <label htmlFor="assignmentDescription" className="block text-gray-300">
                          Assignment Description
                        </label>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => setIsUsingVoice(true)}
                          className="flex items-center text-blue-400 hover:text-blue-300"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                          </svg>
                          Use Voice Input
                        </Button>
                      </div>
                      <textarea
                        id="assignmentDescription"
                        rows={5}
                        placeholder="Describe what you're working on and the issues you're encountering"
                        className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={assignmentDescription}
                        onChange={(e) => setAssignmentDescription(e.target.value)}
                      />
                    </div>
                  ) : (
                    <div className="mb-4">
                      <div className="flex justify-between items-center mb-2">
                        <label className="block text-gray-300">
                          Assignment Description (Voice Input)
                        </label>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => setIsUsingVoice(false)}
                          className="flex items-center text-blue-400 hover:text-blue-300"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                          Use Text Input
                        </Button>
                      </div>
                      
                      <AudioRecorder onRecordingComplete={handleRecordingComplete} maxDuration={120} />
                      
                      {voiceDescription && (
                        <div className="mt-4">
                          <Button 
                            variant="default" 
                            onClick={handleProcessVoiceDescription}
                            disabled={isProcessing}
                            className="w-full"
                          >
                            {isProcessing ? (
                              <>
                                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Processing Voice Input...
                              </>
                            ) : (
                              'Process Voice Description'
                            )}
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                {processingError && (
                  <TechnicianEmptyState
                    title="Error Processing Request"
                    description={processingError}
                    icon={<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-500"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>}
                    actionLabel="Try Again"
                    onAction={() => setProcessingError(null)}
                  />
                )}
                
                <Button 
                  variant="default" 
                  size="lg" 
                  className="w-full"
                  onClick={handleCreateSession}
                  disabled={isProcessing}
                >
                  {isProcessing ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Creating Session...
                    </>
                  ) : (
                    'Create Session & Continue'
                  )}
                </Button>
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
        <div className="container mx-auto px-4 text-center text-gray-400">
          <p>&copy; 2025 TechTalk. All rights reserved.</p>
        </div>
      </footer>
      </div>
    </ProtectedRoute>
  );
}
