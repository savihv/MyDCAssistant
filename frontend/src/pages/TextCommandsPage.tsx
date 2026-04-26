import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "../components/Button";
// Removed duplicate import: import { sessionManager } from "utils/sessionManager";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager"; // Ensured TroubleshootingSession is imported if used for passedSessionData
// Removed: import { firebase } from "utils/firebase"; // Not directly used for Firestore timestamp in this file's logic
import { toast } from "sonner";
import { MessageSquareText, Send, Loader2, AlertTriangle } from "lucide-react";

export default function TextCommandsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const sessionIdFromParams = queryParams.get("sessionId");

  const [sessionId, setSessionId] = useState<string | null>(sessionIdFromParams);
  const [typedCommand, setTypedCommand] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ANALYZED CHANGE: State to store mediaUrls and sessionData passed from MediaCapture
  const [passedMediaUrls, setPassedMediaUrls] = useState<string[] | undefined>(undefined);
  const [passedSessionData, setPassedSessionData] = useState<TroubleshootingSession | null>(null); // Optional: if you need other session data

  useEffect(() => {
    if (!sessionIdFromParams) {
      setError("Session ID is missing. Please start from media capture or a valid session link.");
      toast.error("Session ID is missing from URL.");
    }
    setSessionId(sessionIdFromParams);

    // ANALYZED CHANGE: Read from location.state
    if (location.state) {
      const state = location.state as { mediaUrls?: string[]; sessionData?: TroubleshootingSession };
      if (state.mediaUrls) {
        console.log("[TextCommandsPage DEBUG] Received mediaUrls via navigation state:", state.mediaUrls);
        setPassedMediaUrls(state.mediaUrls);
      }
      if (state.sessionData) {
        console.log("[TextCommandsPage DEBUG] Received sessionData via navigation state. ID:", state.sessionData.id);
        setPassedSessionData(state.sessionData);
        // If sessionData from state has a more reliable/current ID, consider using it.
        // For now, we primarily rely on sessionIdFromParams for the main sessionId.
        if (state.sessionData.id && !sessionIdFromParams) {
            setSessionId(state.sessionData.id); // Useful if URL param is missing but state has it
        }
      }
    }
  }, [sessionIdFromParams, location.state]);

  const handleProcessTextCommand = async () => {
    if (!sessionId) {
      setError("Session ID is missing. Cannot process command.");
      toast.error("Critical error: Session ID not found.");
      return;
    }
    if (!typedCommand.trim()) {
      setError("Please enter a command or question.");
      toast.warning("Command input is empty.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    const processingToastId = toast.loading("Processing your command...");

    try {
      // ANALYZED CHANGE: Prioritize passedMediaUrls, then fallback to fetch
      let mediaUrlsForResponse: string[] = [];

      if (passedMediaUrls && passedMediaUrls.length > 0) {
        mediaUrlsForResponse = passedMediaUrls;
        console.log("[TextCommandsPage DEBUG] Using mediaUrls from navigation state for Response page:", mediaUrlsForResponse);
      } else {
        console.warn("[TextCommandsPage DEBUG] mediaUrls not available from (or empty in) navigation state. Attempting refetch as fallback.");
        try {
          const currentSession = await sessionManager.getSession(sessionId);
          mediaUrlsForResponse = currentSession?.media || [];
          console.log("[TextCommandsPage DEBUG] Fallback fetch for mediaUrls resulted in:", mediaUrlsForResponse);
        } catch (fetchErr: any) {
          console.error("[TextCommandsPage DEBUG] Fallback fetch for mediaUrls failed:", fetchErr.message);
          toast.error("Could not retrieve latest media, proceeding without it.", { duration: 3000 });
          // mediaUrlsForResponse remains empty
        }
      }
      
      // Capture the commandId returned by the function
      const commandId = await sessionManager.saveCommandAndGetId(sessionId, typedCommand.trim(), null, mediaUrlsForResponse);

      if (!commandId) {
        toast.error("Failed to save command. Cannot generate response.");
        setIsProcessing(false);
        return;
      }
      
      toast.success("Text command processed! Generating response...", { id: processingToastId });
      
      // If passedSessionData exists and is more "current" (e.g., has organization),
      // you might pass that instead of relying on Response.tsx to fetch it again.
      // For now, just passing transcript and mediaUrls.
      navigate(
        `/Response?sessionId=${sessionId}`,
        { state: { 
            transcript: typedCommand.trim(), 
            mediaUrls: mediaUrlsForResponse,
            commandId: commandId // Pass the commandId to the Response page
          } 
        }
      );

    } catch (err: any) {
      console.error("Error processing text command:", err);
      const errorMessage = err.message || "Failed to process command. Please try again.";
      setError(errorMessage);
      toast.error(errorMessage, { id: processingToastId });
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
                <li><button onClick={() => navigate("/")} className="text-gray-300 hover:text-white">Home</button></li>
                <li><button onClick={() => navigate("/SessionCreate")} className="text-gray-300 hover:text-white">New Session</button></li>
                <li>
                  <button 
                    onClick={() => navigate(sessionId ? `/MediaCapture?sessionId=${sessionId}` : "/MediaCapture")} 
                    className="text-gray-300 hover:text-white"
                  >
                    Media Capture
                  </button>
                </li>
                <li><button onClick={() => navigate("/History")} className="text-gray-300 hover:text-white">History</button></li>
              </ul>
            </nav>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 container mx-auto py-8 px-4 flex flex-col items-center justify-center">
          <div className="w-full max-w-2xl bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700">
            <div className="text-center mb-8">
              <MessageSquareText className="w-16 h-16 text-blue-500 mx-auto mb-4" />
              <h2 className="text-3xl font-bold text-blue-400">Enter Your Command</h2>
              {sessionId ? (
                <p className="text-md text-gray-400 mt-2">
                  For Session ID: <span className="font-mono text-blue-300 bg-gray-700 px-2 py-1 rounded">{sessionId.substring(0,8)}...</span>
                </p>
              ) : (
                <p className="text-md text-red-500 mt-2 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 mr-2" /> Session ID not found. Please go back.
                </p>
              )}
               {passedMediaUrls && passedMediaUrls.length > 0 && (
                <p className="text-sm text-gray-500 mt-1">
                  ({passedMediaUrls.length} media item(s) will be included)
                </p>
              )}
            </div>

            <div className="space-y-6">
              <div>
                <label htmlFor="textCommand" className="block text-sm font-medium text-gray-300 mb-1">
                  Type your question or command for the AI assistant:
                </label>
                <textarea
                  id="textCommand"
                  rows={6}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-500 text-white text-base resize-none shadow-sm disabled:opacity-70"
                  placeholder="e.g., 'The device is making a clicking sound, what are the common causes?' or 'Guide me through a hard reset.'"
                  value={typedCommand}
                  onChange={(e) => setTypedCommand(e.target.value)}
                  disabled={isProcessing || !sessionId}
                />
              </div>

              {error && (
                <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded-md flex items-start">
                  <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Error</p>
                    <p className="text-sm">{error}</p>
                  </div>
                </div>
              )}

              <Button
                variant="default"
                size="lg"
                className="w-full flex items-center justify-center text-lg py-3 shadow-lg hover:shadow-blue-500/30 transition-shadow duration-300 disabled:opacity-60"
                onClick={handleProcessTextCommand}
                disabled={isProcessing || !typedCommand.trim() || !sessionId}
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="animate-spin mr-3 h-6 w-6" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Send className="mr-3 h-5 w-5" />
                    Process Command & Get Response
                  </>
                )}
              </Button>
            </div>
            
            <div className="mt-8 text-center">
                <Button 
                    variant="outline"
                    onClick={() => {
                        // When going back, pass the current state (including mediaUrls) back to MediaCapture if needed
                        const navState: any = {};
                        if (passedMediaUrls) navState.mediaUrls = passedMediaUrls;
                        if (passedSessionData) navState.sessionData = passedSessionData;
                        // MediaCapture typically re-fetches or uses its own state, but passing it back might be useful in some scenarios
                        // For simplicity, often just navigating with sessionId is enough if MediaCapture always re-evaluates its state.
                        navigate(sessionId ? `/MediaCapture?sessionId=${sessionId}` : '/MediaCapture', { state: location.state }); // Pass original state back
                    }}
                    className="text-sm"
                    disabled={isProcessing}
                >
                    Back to Media Capture
                </Button>
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
    </ProtectedRoute>
  );
}
