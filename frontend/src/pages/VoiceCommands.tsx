import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/Button"; // Assuming shadcn button
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo"; // Assuming your Logo path
import { AudioRecorder } from "../components/AudioRecorder"; // Assuming your AudioRecorder path
import { firebaseApp, firebaseAuth } from "../app"; // Assuming your Firebase app path
import { getStorage, ref, uploadBytes, getDownloadURL } from "firebase/storage";

// Initialize storage
const storage = getStorage(firebaseApp);
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager"; // Ensuring TroubleshootingSession is imported
import { apiClient } from "../app"; // Your HTTP client
import { ProtectedRoute } from "../components/ProtectedRoute"; // Assuming your ProtectedRoute path
  import { TechnicianEmptyState } from "../components/TechnicianEmptyState"; // Assuming your EmptyState path
import { AlertCircle, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner"; // Added for consistency with other pages

// Define an interface for the expected API error structure
interface ApiError {
  detail?: string;
}

interface TranscriptionResponse {
  transcription: string;
  // Potentially other fields, but transcription is key
}


export default function VoiceCommands() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const sessionIdFromParams = queryParams.get("sessionId"); // Renamed for clarity vs. state sessionId

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionIdFromParams); // State for sessionId
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [voiceCommand, setVoiceCommand] = useState<{
    audioBlob: Blob;
    audioDuration: number;
  } | null>(null);

  // ANALYZED CHANGE: State to store mediaUrls and sessionData passed from MediaCapture
  const [passedMediaUrls, setPassedMediaUrls] = useState<string[] | undefined>(undefined);
  const [passedSessionData, setPassedSessionData] = useState<TroubleshootingSession | null>(null);

  useEffect(() => {
    setCurrentSessionId(sessionIdFromParams); // Update state if URL param changes

    if (!sessionIdFromParams) {
        setAuthError("Session ID is missing from URL. Please start from media capture.");
        toast.error("Session ID is missing from URL.");
    } else {
        // Optional: verify session, but primary session ID is from URL
        sessionManager.getSession(sessionIdFromParams)
            .then(session => {
                if (!session) {
                    setAuthError("Session not found. Please try again or create a new session.");
                    toast.error("Session not found.");
                } else {
                    setAuthError(null); // Clear error if session is found
                }
            })
            .catch(error => {
              console.error("Error verifying session on load:", error);
              setAuthError("Unable to verify your session. Please try again or create a new session.");
              toast.error("Session verification failed.");
            });
    }
    
    // ANALYZED CHANGE: Read from location.state
    if (location.state) {
      const state = location.state as { mediaUrls?: string[]; sessionData?: TroubleshootingSession };
      if (state.mediaUrls) {
        console.log("[VoiceCommands DEBUG] Received mediaUrls via navigation state:", state.mediaUrls);
        setPassedMediaUrls(state.mediaUrls);
      }
      if (state.sessionData) {
        console.log("[VoiceCommands DEBUG] Received sessionData via navigation state. ID:", state.sessionData.id);
        setPassedSessionData(state.sessionData);
        // If sessionData from state has a more reliable/current ID, consider using it.
        // Especially if sessionIdFromParams was initially null.
        if (state.sessionData.id && !currentSessionId) {
            setCurrentSessionId(state.sessionData.id);
        }
      }
    }
  }, [sessionIdFromParams, location.state]); // Added location.state dependency

  const handleRecordingComplete = (audioBlob: Blob, audioDuration: number) => {
    setVoiceCommand({
      audioBlob,
      audioDuration,
    });
    setProcessingError(null); // Clear previous errors when new recording is made
  };

  const handleProcessVoiceCommand = async () => {
    if (!voiceCommand || !voiceCommand.audioBlob) {
      setProcessingError("No voice recording available to process.");
      toast.error("No voice recording found.");
      return;
    }
    if (!currentSessionId) { // Use state variable currentSessionId
      setProcessingError("Session ID is missing. Cannot process command.");
      toast.error("Critical error: Session ID not found.");
      return;
    }

    setIsProcessing(true);
    setProcessingError(null);
    setAuthError(null);
    const processingToastId = toast.loading("Processing your voice command...");

    try {
      // Force a refresh of the user's ID token before the upload.
      // Force a refresh of the user's ID token before the upload.
      const currentUser = firebaseAuth.currentUser;
      if (currentUser) {
        console.log("[VoiceCommands DEBUG] Forcing token refresh before upload...");
        // Correctly assign the token to a variable
        const token = await currentUser.getIdToken(true); // The 'true' forces a server refresh.
        console.log("[VoiceCommands DEBUG] Token refreshed.");
        // Use the correct variable name in the log
        console.log("Refreshed ID Token:", token); 
        const decodedToken = await currentUser.getIdTokenResult(true);
        console.log("Decoded Token Claims:", decodedToken.claims);
      }

      // 1. Dynamically determine the file extension from the blob's MIME type.
      const mimeType = voiceCommand.audioBlob.type;
      const fileExtension = (mimeType.split('/')[1] || 'webm').split(';')[0];

      // 2. Use the dynamic extension to create the path and filename.
      const timestamp = new Date().getTime();
      const audioPath = `voice-commands/${currentSessionId}/${timestamp}.${fileExtension}`;
      const audioFileName = `voice_command.${fileExtension}`;
      
      const audioRef = ref(storage, audioPath);

      console.log("[VoiceCommands DEBUG] Uploading audio to Firebase Storage:", audioPath);
      await uploadBytes(audioRef, voiceCommand.audioBlob);
      const downloadURL = await getDownloadURL(audioRef);
      console.log("[VoiceCommands DEBUG] Audio uploaded. URL:", downloadURL);

      console.log('[VoiceCommands DEBUG] Transcribing audio with apiClient.transcribe_audio...');
      // Ensure audioBlob is correctly passed. It should be a Blob or File.
      // Wrapping in a File object with a name can sometimes help ensure compatibility.
      const audioFileForTranscription = new File([voiceCommand.audioBlob], audioFileName, { type: mimeType });
      const response = await apiClient.transcribe_audio({ audio: audioFileForTranscription });
      
      console.log('[VoiceCommands DEBUG] Raw response from apiClient.transcribe_audio:', response);

      if (!response.ok) {
        let errorData: ApiError | null = null; 
        try { errorData = await response.json() as ApiError; } catch (jsonError) { /* ignore */ }
        if (response.status === 401) {
          setAuthError("Authentication error during transcription. Please log out and log back in.");
          toast.error("Transcription authorization failed.", { id: processingToastId });
          return;
        }
        const detailMessage = errorData?.detail || `Transcription API error: ${response.status}`; 
        throw new Error(detailMessage);
      }
      
      const transcriptionData = await response.json() as TranscriptionResponse;
      console.log('[VoiceCommands DEBUG] Parsed transcriptionData:', transcriptionData);

      if (!transcriptionData || typeof transcriptionData.transcription === 'undefined') {
        throw new Error('Received invalid transcription data from server.');
      }
      const transcription = transcriptionData.transcription;
      console.log('[VoiceCommands DEBUG] Transcription:', transcription);

      // ANALYZED CHANGE: Prioritize passedMediaUrls, then fallback to fetch
      let mediaUrlsForResponse: string[] = [];
      if (passedMediaUrls && passedMediaUrls.length > 0) {
        mediaUrlsForResponse = passedMediaUrls;
        console.log("[VoiceCommands DEBUG] Using mediaUrls from navigation state for Response page:", mediaUrlsForResponse);
      } else {
        console.warn("[VoiceCommands DEBUG] mediaUrls not available from (or empty in) navigation state. Attempting refetch as fallback.");
        try {
          const sessionAfterCommand = await sessionManager.getSession(currentSessionId);
          mediaUrlsForResponse = sessionAfterCommand?.media || [];
          console.log("[VoiceCommands DEBUG] Fallback fetch for mediaUrls resulted in:", mediaUrlsForResponse);
        } catch (fetchErr: any) {
          console.error("[VoiceCommands DEBUG] Fallback fetch for mediaUrls failed:", fetchErr.message);
          toast.error("Could not retrieve latest media, proceeding without it.", { duration: 3000 });
        }
      }
      
      // Capture the commandId and ensure the correct function name is used
      const commandId = await sessionManager.saveCommandAndGetId(currentSessionId, transcription, downloadURL, mediaUrlsForResponse);

      if (!commandId) {
          toast.error("Failed to save command. Cannot generate response.");
          setIsProcessing(false);
          return;
      }

      // await sessionManager.updateStatus(currentSessionId, "in-progress"); // Often handled by saveCommand or next step
      toast.success("Voice command processed! Generating response...", { id: processingToastId });
      
      navigate(
        `/Response?sessionId=${currentSessionId}`,
        { state: { 
            transcript: transcription, 
            mediaUrls: mediaUrlsForResponse,
            commandId: commandId // Pass the commandId to the Response page
            // sessionData: passedSessionData // Optionally pass if Response.tsx can use it
          } 
        }
      );

    } catch (error: any) {
      console.error("[VoiceCommands DEBUG] Error caught:", error);
      if (error.code && (error.code.includes('auth') || error.code.includes('permission-denied'))) {
        setAuthError("Authentication error. Please log out and log back in.");
      } else {
        setProcessingError(error.message || "Failed to process voice command. Please try again.");
      }
      toast.error(error.message || "Processing failed.", { id: processingToastId });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <ProtectedRoute>
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
            <nav>
              <ul className="flex space-x-4">
                <li><button onClick={() => navigate("/")} className="text-gray-300 hover:text-white">Home</button></li>
                <li><button onClick={() => navigate("/SessionCreate")} className="text-gray-300 hover:text-white">New Session</button></li>
                <li><button onClick={() => navigate(currentSessionId ? `/MediaCapture?sessionId=${currentSessionId}` : "/MediaCapture")} className="text-gray-300 hover:text-white">Media Capture</button></li>
                {/* <li><button onClick={() => navigate(currentSessionId ? `/VoiceCommands?sessionId=${currentSessionId}` : "")} className="text-blue-400" disabled={!currentSessionId}>Voice Commands</button></li> */}
                <li><button onClick={() => navigate("/History")} className="text-gray-300 hover:text-white">History</button></li>
              </ul>
            </nav>
          </div>
        </header>

        <main className="flex-1 container mx-auto py-8 px-4 flex flex-col items-center justify-center">
          <div className="w-full max-w-2xl">
            {!currentSessionId && !authError ? ( // Show if no session ID and no other auth error yet
                <TechnicianEmptyState
                    title="No Session Active"
                    description="A session ID is required to record voice commands. Please start by capturing media or from your session history."
                    icon={<AlertCircle className="h-12 w-12 text-yellow-400" />}
                    actionLabel="Go to Media Capture"
                    onAction={() => navigate("/MediaCapture")}
                    secondaryActionLabel="View History"
                    onSecondaryAction={() => navigate("/History")}
                />
            ) : authError ? (
              <TechnicianEmptyState
                title="Session Error"
                description={authError}
                icon={<AlertCircle className="h-12 w-12 text-red-500" />}
                actionLabel="Go to Media Capture"
                onAction={() => navigate(currentSessionId ? `/MediaCapture?sessionId=${currentSessionId}` : "/MediaCapture" )}
                secondaryActionLabel="Try Reloading"
                onSecondaryAction={() => window.location.reload()}
              />
            ) : (
              <div className="space-y-8 bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-blue-400 mb-2">Record Voice Command</h2>
                    <p className="text-md text-gray-400">
                        For Session ID: <span className="font-mono text-blue-300 bg-gray-700 px-2 py-1 rounded">{currentSessionId?.substring(0,8)}...</span>
                    </p>
                    {passedMediaUrls && passedMediaUrls.length > 0 && (
                        <p className="text-sm text-gray-500 mt-1">
                        ({passedMediaUrls.length} media item(s) will be included with your command)
                        </p>
                    )}
                </div>

                <AudioRecorder onRecordingComplete={handleRecordingComplete} maxDuration={120} />

                {voiceCommand && (
                  <div className="mt-6 space-y-4">
                    <div className="bg-gray-700/50 p-4 rounded-lg">
                        <h3 className="text-lg font-semibold mb-2 text-gray-200">Recorded Audio</h3>
                        <p className="text-sm text-gray-300">
                        Duration: {Math.floor(voiceCommand.audioDuration / 60)}:{(voiceCommand.audioDuration % 60).toString().padStart(2, '0')} seconds
                        </p>
                        {/* Optional: Playback control for the recorded audio can be added here */}
                    </div>
                    
                    {processingError && (
                      <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded-md flex items-start">
                        <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="font-semibold">Processing Error</p>
                            <p className="text-sm">{processingError}</p>
                        </div>
                      </div>
                    )}

                    <Button 
                      variant="default" 
                      size="lg" 
                      className="w-full flex items-center justify-center text-lg py-3 shadow-lg"
                      onClick={handleProcessVoiceCommand}
                      disabled={isProcessing}
                    >
                      {isProcessing ? (
                        <>
                          <Loader2 className="animate-spin mr-3 h-6 w-6" />
                          Processing Voice Command...
                        </>
                      ) : (
                        'Process Command & Get Response'
                      )}
                    </Button>
                  </div>
                )}
                 <div className="mt-8 text-center">
                    <Button 
                        variant="outline"
                        onClick={() => {
                             const navState: any = {};
                             if (passedMediaUrls) navState.mediaUrls = passedMediaUrls;
                             if (passedSessionData) navState.sessionData = passedSessionData;
                             navigate(currentSessionId ? `/MediaCapture?sessionId=${currentSessionId}` : '/MediaCapture', { state: location.state }); // Pass original state back
                        }}
                        className="text-sm"
                        disabled={isProcessing}
                    >
                        Back to Media Capture
                    </Button>
                </div>
              </div>
            )}
          </div>
        </main>

        <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
          <div className="container mx-auto px-4 text-center text-gray-400">
            <p>&copy; {new Date().getFullYear()} TechTalk. All rights reserved.</p>
          </div>
        </footer>
      </div>
    </ProtectedRoute>
  );
}
