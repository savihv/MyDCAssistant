import React, { useState, useEffect } from "react";
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { FileUploader } from "../components/FileUploader";
import { useNavigate, useLocation } from "react-router-dom";
import { apiClient } from "../app";
import { toast } from "sonner";
// import { storage } from "utils/firebase"; // DEPRECATED: storage was null
import { firebaseApp } from "../app"; // Correct firebaseApp import
import { getStorage } from "firebase/storage"; // Import getStorage
// import { ref, uploadBytes, getDownloadURL } from "firebase/storage"; // Not directly used if brain client handles upload
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { TechnicianEmptyState } from "../components/TechnicianEmptyState";
import { AlertCircle, UploadCloud, MicIcon, MessageSquareText } from "lucide-react"; // Added MessageSquareText

// --- ADD THIS IMPORT ---
import { firebaseAuth, API_URL } from "../app"; // Assuming 'firebaseAuth' is the exported auth instance

// Initialize Firebase Storage correctly at the module level
// const storage = getStorage(firebaseApp); // Not directly used if brain client handles upload

interface FileWithPreview extends File {
  preview?: string;
  id: string;
}

export default function MediaCapture() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const sessionIdFromParams = queryParams.get("sessionId");
  
  const [deviceType, setDeviceType] = useState("");
  const [issueDescription, setIssueDescription] = useState("");
  const [imageFiles, setImageFiles] = useState<FileWithPreview[]>([]);
  const [videoFiles, setVideoFiles] = useState<FileWithPreview[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(sessionIdFromParams);
  const [sessionDetails, setSessionDetails] = useState<TroubleshootingSession | null>(null);
  const [isLoading, setIsLoading] = useState(sessionIdFromParams ? true : false);
  const [uploadComplete, setUploadComplete] = useState(false); // New state for post-upload choice
  // ANALYZED CHANGE: State to hold fresh session data after uploads
  const [sessionDataForNextStep, setSessionDataForNextStep] = useState<TroubleshootingSession | null>(null);
  const [clientSideMediaUrls, setClientSideMediaUrls] = useState<string[]>([]); // Collect GCS paths client-side
  
  const handleImageFilesChanged = (files: FileWithPreview[]) => {
    setImageFiles(files);
  };
  
  const handleVideoFilesChanged = (files: FileWithPreview[]) => {
    setVideoFiles(files);
  };
  
  // Fetch session details if we have a session ID
  useEffect(() => {
    const fetchSessionDetails = async () => {
      if (!sessionId) return;
      
      try {
        const session = await sessionManager.getSession(sessionId);
        
        if (session) {
          setSessionDetails(session);
          
          // Prefill the form fields if available
          if (session.assignmentName) setDeviceType(session.assignmentName);
          if (session.assignmentDescription) setIssueDescription(session.assignmentDescription);
        } else {
          setUploadError("Session not found. Please start a new session.");
        }
      } catch (error) {
        console.error("Error fetching session details:", error);
        setUploadError("Error loading session details.");
      } finally {
        setIsLoading(false);
      }
    };
    
    if (sessionId) {
      fetchSessionDetails();
    }
  }, [sessionId]);
  
  const handleSubmit = async () => {
    // --- INITIAL SESSION ID STATE LOGGING ---
    console.log(`[MediaCapture DEBUG] handleSubmit triggered at ${new Date().toISOString()}`);
    console.log(`[MediaCapture DEBUG] Initial sessionIdFromParams (URL): "${sessionIdFromParams || 'N/A'}"`);
    console.log(`[MediaCapture DEBUG] Initial component state sessionId: "${sessionId || 'N/A'}"`); // This 'sessionId' is from useState
    // --- END OF INITIAL SESSION ID STATE LOGGING ---

    if (!deviceType.trim()) {
      alert("Please enter a device type");
      return;
    }
    
    if (!issueDescription.trim()) {
      alert("Please enter an issue description");
      return;
    }

    // --- ADD TOKEN REFRESH LOGIC ---
    if (firebaseAuth.currentUser) { // Use the imported firebaseAuth instance
      try {
        console.log("Forcing ID token refresh before media upload...");
        await firebaseAuth.currentUser.getIdToken(true); // true forces refresh
        console.log("ID token refreshed.");
      } catch (refreshError) {
        console.error("Error forcing ID token refresh:", refreshError);
      }
    }
    // --- END OF TOKEN REFRESH LOGIC ---
    
    if (imageFiles.length === 0 && videoFiles.length === 0) {
      alert("Please upload at least one image or video"); // Or decide to allow session update without media
      // return; // If media is strictly required. Otherwise, comment out to proceed.
    }
    
    setIsUploading(true);
    setUploadError(null);
    setUploadComplete(false); // Reset upload complete state
    setSessionDataForNextStep(null); // Reset fresh session data
    setClientSideMediaUrls([]); // Reset client-side URLs

    try {
      let currentSessionId = sessionId;
      
      if (!currentSessionId) {
        console.log("[MediaCapture DEBUG] No existing sessionId found, creating new session...");
        // ANALYZED CHANGE: Ensure organization is passed if it's a required field for session creation
        // This example assumes organization might come from a state variable or a default value.
        // For simplicity, I'll omit explicit organization handling here, but it needs consideration
        // if your sessionManager.createSession requires it and it's not part of deviceType/issueDescription.
        currentSessionId = await sessionManager.createSession({
          assignmentName: deviceType,
          assignmentDescription: issueDescription,
          organization: ""
          // organization: "default-org" // Example if organization is needed
        });
        console.log(`[MediaCapture DEBUG] New session created with ID: "${currentSessionId}"`);
        setSessionId(currentSessionId); 
      } else {
        console.log(`[MediaCapture DEBUG] Using existing sessionId: "${currentSessionId}", updating session details.`);
        await sessionManager.updateSession(currentSessionId, {
          assignmentName: deviceType,
          assignmentDescription: issueDescription
        });
      }

      if (currentSessionId && firebaseAuth.currentUser) {
        try {
          const user = firebaseAuth.currentUser;
          const idTokenResult = await user.getIdTokenResult(false); 
          const claims = idTokenResult.claims;
          console.log(`[MediaCapture DEBUG] Upload Context at ${new Date().toISOString()}:
            Session ID: "${currentSessionId}"
            User ID: "${user.uid}"
            User Email: "${user.email}"
            Role: "${claims.role || 'N/A'}"
            Company: "${claims.company || 'N/A'}"`);
        } catch (claimsError) {
          console.error("[MediaCapture DEBUG] Error getting user claims for logging:", claimsError);
          console.log(`[MediaCapture DEBUG] Upload Context (claims error) at ${new Date().toISOString()}:
            Session ID: "${currentSessionId}"
            User ID: "${firebaseAuth.currentUser?.uid || 'N/A'}"
            User Email: "${firebaseAuth.currentUser?.email || 'N/A'}"`);
        }
      } else {
        let errorMsg = "[MediaCapture DEBUG] Critical info missing for comprehensive log (after session ID init):";
        if (!currentSessionId) errorMsg += " currentSessionId is STILL null/undefined.";
        if (!firebaseAuth.currentUser) errorMsg += " currentUser is null."; 
        console.error(errorMsg);
      }
      
      if (!currentSessionId) {
        console.error("[MediaCapture DEBUG] currentSessionId is null or undefined before API upload loop!");
        setUploadError("Critical error: Session ID is missing. Cannot proceed.");
        setIsUploading(false);
        return;
      }

      if (!firebaseAuth.currentUser) {
        console.error("[MediaCapture DEBUG] User not authenticated before API upload loop!");
        setUploadError("Critical error: User not authenticated. Please sign in again.");
        setIsUploading(false);
        return;
      }

      let allUploadsSuccessful = true;
      const collectedGcsPaths: string[] = []; // Initialize here

      if ((imageFiles.length > 0 || videoFiles.length > 0) && firebaseAuth.currentUser) {
        const filesToUpload = [...imageFiles, ...videoFiles];
        for (const file of filesToUpload) {
          console.log(`[MediaCapture DEBUG] Preparing to upload ${file.name} for session ${currentSessionId} via brain client.`);
          const uploadToastId = toast.loading(`Uploading ${file.name}...`);

          try {
            const response = await apiClient.upload_general_file({
              sessionId: currentSessionId,
              file: file as any, 
            } as any);
            const result = await response.json(); 

            console.log(`Successfully uploaded ${file.name} via brain client:`, result);
            toast.success(`File "${result.filename || file.name}" uploaded!`, {
              id: uploadToastId,
              description: result.gcs_path ? `Path: ${result.gcs_path}` : undefined,
            });
            if (result.gcs_path) {
              collectedGcsPaths.push(result.gcs_path); // Collect GCS path
            }
          } catch (error: any) {
            console.error(`Error uploading ${file.name} via brain client:`, error);
            let errorMessage = `Failed to upload ${file.name}. Please try again.`;
            if (error.response && typeof error.response.json === 'function') {
              try {
                const errJson = await error.response.json();
                errorMessage = errJson.detail || errJson.message || errorMessage;
              } catch (parseError) { /* Ignore */ }
            } else if (error.message) {
              errorMessage = error.message;
            }
            toast.error(errorMessage, { id: uploadToastId });
            setUploadError(errorMessage); 
            allUploadsSuccessful = false;
            break; 
          }
        }
      } else if (imageFiles.length === 0 && videoFiles.length === 0) {
        allUploadsSuccessful = true; // No files, so treat as success for session update part
      }

      if (allUploadsSuccessful) {
        setClientSideMediaUrls(collectedGcsPaths); // Set state with collected URLs
        // ANALYZED CHANGE: Fetch fresh session data here
        if (currentSessionId) { 
          try {
            console.log("[MediaCapture DEBUG] Media processing complete. Fetching latest session data before showing command options...");
            const freshSession = await sessionManager.getSession(currentSessionId);
            if (freshSession) {
              setSessionDataForNextStep(freshSession); 
              console.log("[MediaCapture DEBUG] Fresh session data fetched and stored for next step:", freshSession);
            } else {
              console.error("[MediaCapture DEBUG] Failed to fetch fresh session data after uploads. Session might not be found.");
              setSessionDataForNextStep(null); 
            }
          } catch (error) {
            console.error("[MediaCapture DEBUG] Error fetching fresh session data after uploads:", error);
            setSessionDataForNextStep(null); 
          }
        }
        setUploadComplete(true); 
        if (imageFiles.length > 0 || videoFiles.length > 0) {
          console.log("[MediaCapture DEBUG] All files processed successfully. Ready for command input choice.");
        } else {
          console.log("[MediaCapture DEBUG] No files to upload, but session updated/created. Ready for command input choice.");
        }
      } else if (!allUploadsSuccessful) {
        console.log("[MediaCapture DEBUG] Some uploads failed. Not navigating. Error state should be set.");
      }

    } catch (error) {
      console.error("Failed to process session/media:", error); 
      if ((error as any).code === 'storage/unauthorized') { // Example of more specific error handling
         setUploadError("Permission denied. Please ensure you have the correct permissions.");
      } else if (error instanceof Error) {
         setUploadError(error.message || "Failed to process session/media. Please try again.");
      } else {
         setUploadError("An unknown error occurred. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <ProtectedRoute>
      {!uploadComplete ? (
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
                <button onClick={() => navigate("/SessionCreate")} className="text-gray-300 hover:text-white">
                  New Session
                </button>
              </li>
              <li>
                <button onClick={() => navigate(sessionId ? `/MediaCapture?sessionId=${sessionId}` : "/MediaCapture")} className="text-blue-400">
                  Media Capture
                </button>
              </li>
              {/* Navigation items can be dynamically shown based on sessionId or other states */}
            </ul>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto py-8 px-4">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold mb-6">
            {sessionId ? "Add Media to Troubleshooting Session" : "Start New Troubleshooting Session"}
          </h2>
          
          {isLoading && ( // Simplified isLoading check
            <div className="bg-gray-800 rounded-lg p-6 mb-8 border border-gray-700 flex items-center justify-center">
              <svg className="animate-spin h-8 w-8 text-blue-500 mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Loading session details...</span>
            </div>
          )}
          
          <div className="bg-gray-800 rounded-lg p-6 mb-8 border border-gray-700">
            <h3 className="text-xl font-bold mb-4">
              {sessionId && sessionDetails ? `Session: ${sessionDetails.assignmentName}` : "Device & Issue Details"}
            </h3>
            
            {sessionId && sessionDetails && (
              <div className="mb-4 p-3 bg-gray-700/60 rounded-md text-sm">
                <p><span className="text-gray-400">ID:</span> {sessionId.substring(0,6)}...</p>
                <p><span className="text-gray-400">Description:</span> {sessionDetails.assignmentDescription}</p>
                <p><span className="text-gray-400">Status:</span> <span className="capitalize">{sessionDetails.status}</span></p>
              </div>
            )}
            
            <div className="mb-4">
              <label htmlFor="deviceType" className="block text-gray-300 mb-2">
                Device Type / Assignment Name
              </label>
              <input
                type="text"
                id="deviceType"
                placeholder="e.g., CNC Machine Model X, Air Handling Unit 3"
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value)}
                disabled={isLoading}
              />
            </div>
            
            <div className="mb-4">
              <label htmlFor="issueDescription" className="block text-gray-300 mb-2">
                Brief Issue Description
              </label>
              <textarea
                id="issueDescription"
                rows={3}
                placeholder="e.g., Loud grinding noise during operation, Fails to power on"
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={issueDescription}
                onChange={(e) => setIssueDescription(e.target.value)}
                disabled={isLoading}
              />
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-6 mb-8 border border-gray-700">
            <h3 className="text-xl font-bold mb-4">Upload Media (Optional)</h3>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-lg font-semibold mb-3">Images (Max 5)</h4>
                <FileUploader 
                  acceptedFileTypes="image/*" 
                  maxFiles={5}
                  maxFileSize={10} // MB
                  isMultiple={true}
                  fileType="image"
                  onFilesChanged={handleImageFilesChanged}
                />
              </div>
              
              <div>
                <h4 className="text-lg font-semibold mb-3">Video (Max 1)</h4>
                <FileUploader 
                  acceptedFileTypes="video/*" 
                  maxFiles={1}
                  maxFileSize={100} // MB
                  isMultiple={false}
                  fileType="video"
                  onFilesChanged={handleVideoFilesChanged}
                />
              </div>
            </div>
            
            {uploadError && (
              <div className="mt-4">
                <TechnicianEmptyState
                  title="Upload Error"
                  description={uploadError}
                  icon={<AlertCircle className="text-red-500 h-12 w-12"/>} // Adjusted icon
                  actionLabel="Dismiss"
                  onAction={() => setUploadError(null)}
                />
              </div>
            )}
            
            <div className="mt-6">
              <Button 
                variant="default" 
                size="lg" 
                className="w-full"
                onClick={handleSubmit}
                disabled={isUploading || isLoading}
              >
                {isUploading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {sessionId ? "Updating & Uploading..." : "Creating & Uploading..."}
                  </>
                ) : (
                  sessionId ? "Update Session & Add Media" : "Create Session & Add Media"
                )}
              </Button>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
        <div className="container mx-auto px-4 text-center text-gray-400">
          <p>&copy; {new Date().getFullYear()} TechTalk. All rights reserved.</p>
        </div>
      </footer>
      </div>
      ) : (
        // Upload Complete UI
        <div className="flex flex-col min-h-screen bg-gray-900 text-white">
          <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
            <div className="container mx-auto flex items-center justify-between">
              <div className="flex items-center">
                <JuniorTechBotLogo className="w-8 h-8 mr-2" />
                <h1 className="text-xl font-bold">
                  <span className="text-white">Junior</span>
                  <span className="text-blue-400">TechBot</span>
                </h1>
              </div>
               {/* Simplified Nav for this view */}
            </div>
          </header>

          <main className="flex-1 container mx-auto py-8 px-4 flex items-center justify-center">
            <div className="max-w-2xl mx-auto text-center bg-gray-800 p-8 md:p-12 rounded-xl shadow-2xl border border-gray-700">
              <UploadCloud className="h-16 w-16 text-blue-400 mx-auto mb-6" />
              <h2 className="text-3xl font-bold mb-4 text-blue-400">Session Ready!</h2>
              {sessionId && (
                <p className="text-lg text-gray-300 mb-2">
                  Session ID: <span className="font-mono text-blue-300 bg-gray-700 px-2 py-1 rounded">{sessionId.substring(0,8)}...</span>
                </p>
              )}
              {sessionDataForNextStep?.media && sessionDataForNextStep.media.length > 0 && (
                <p className="text-md text-gray-400 mb-1">
                  {sessionDataForNextStep.media.length} media file(s) associated.
                </p>
              )}
              <p className="text-lg text-gray-300 mb-8">
                How would you like to provide your command or question?
              </p>
              <div className="space-y-4 sm:space-y-0 sm:flex sm:flex-col sm:items-center md:flex-row md:space-x-4 md:justify-center">
                <Button 
                  variant="default"
                  size="lg"
                  onClick={() => {
                    // ANALYZED CHANGE: Pass fresh session data/mediaUrls in navigation state
                    const navState: { mediaUrls?: string[]; sessionData?: TroubleshootingSession | null } = {};
                    navState.mediaUrls = clientSideMediaUrls; // Use client-side collected URLs
                    if (sessionDataForNextStep) { // Use the state variable holding fresh session data for other details
                      navState.sessionData = sessionDataForNextStep; 
                    } else if (sessionDetails) { // Fallback to initially fetched details if fresh fetch failed
                      navState.sessionData = sessionDetails;
                    }
                    navigate(`/VoiceCommands?sessionId=${sessionId}`, { state: navState });
                  }}
                  className="w-full md:w-auto flex items-center justify-center text-base"
                  disabled={!sessionId}
                >
                  <MicIcon className="mr-2 h-5 w-5" />
                  Use Voice Command
                </Button>
                <Button 
                  variant="outline" 
                  size="lg"
                  onClick={() => {
                    // ANALYZED CHANGE: Pass fresh session data/mediaUrls in navigation state
                    const navState: { mediaUrls?: string[]; sessionData?: TroubleshootingSession | null } = {};
                    navState.mediaUrls = clientSideMediaUrls; // Use client-side collected URLs
                    if (sessionDataForNextStep) { // Use the state variable holding fresh session data for other details
                      navState.sessionData = sessionDataForNextStep;
                    } else if (sessionDetails) { // Fallback to initially fetched details if fresh fetch failed
                      navState.sessionData = sessionDetails;
                    }
                    navigate(`/text-commands-page?sessionId=${sessionId}`, { state: navState });
                  }} 
                  className="w-full md:w-auto flex items-center justify-center text-base"
                  disabled={!sessionId}
                >
                  <MessageSquareText className="mr-2 h-5 w-5" />
                  Use Text Command
                </Button>
              </div>
              <Button 
                variant="outline" 
                size="default"
                onClick={() => navigate("/History")} 
                className="w-full md:w-auto mt-8 text-sm"
              >
                View Session History
              </Button>
            </div>
          </main>

          <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
            <div className="container mx-auto px-4 text-center text-gray-400">
              <p>&copy; {new Date().getFullYear()} TechTalk. All rights reserved.</p>
            </div>
          </footer>
        </div>
      )}
    </ProtectedRoute>
  );
}
