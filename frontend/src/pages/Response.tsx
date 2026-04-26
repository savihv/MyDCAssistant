import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { FeedbackComponent } from "../components/FeedbackComponent";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  collection,
  query,
  orderBy,
  getDocs,
  getFirestore,
  doc,
  onSnapshot,
} from "firebase/firestore";
import { firebaseApp, useUserGuardContext } from "../app";
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { apiClient } from "../app";
import { ResponseRequest } from "../apiclient/data-contracts";
import { TechnicianEmptyState } from "../components/TechnicianEmptyState";
import { AudioPlayer } from "../components/AudioPlayer";
import { ThumbsUp, ThumbsDown, BrainCircuit } from "lucide-react";
import { toast } from "sonner";
import { useUserRoles } from "../utils/useUserRoles";
// NEW: Import Dialog components for the modal
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../extensions/shadcn/components/dialog";

console.log("[Response DEBUG] Component loaded");

export default function Response() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const sessionId = queryParams.get("sessionId");

  console.log(
    `[Response DEBUG] Initializing component with sessionId: ${sessionId}`
  );

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<TroubleshootingSession | null>(null);
  const [response, setResponse] = useState<{
    text: string;
    audioUrl: string | null;
  }>({
    text: "",
    audioUrl: null,
  });
  const [retryCount, setRetryCount] = useState(0);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackType, setFeedbackType] = useState<"positive" | "negative">(
    "positive"
  );
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [isAudioProcessing, setIsAudioProcessing] = useState(false);

  // NEW: State for Step 2 - Report Review and Saving
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [generatedReportMarkdown, setGeneratedReportMarkdown] = useState("");
  const [isSavingReport, setIsSavingReport] = useState(false);

  const { user } = useUserGuardContext();
  const { isCompanyAdmin, isSystemAdmin } = useUserRoles();
  const isAdmin = isCompanyAdmin || isSystemAdmin;
  const firestore = getFirestore(firebaseApp);

  useEffect(() => {
    console.log("[Response DEBUG] useEffect triggered. Dependencies:", {
      sessionId,
      user,
      firestore,
      retryCount,
    });
    console.log("[Response DEBUG] Location state:", location.state);

    const passedTranscript = location.state?.transcript as string | undefined;
    const passedMediaUrls = location.state?.mediaUrls as string[] | undefined;
    const passedCommandId = location.state?.commandId as string | undefined;

    console.log("[Response DEBUG] Passed state from location:", {
      passedTranscript,
      passedMediaUrls,
      passedCommandId,
    });

    const fetchSessionData = async () => {
      console.log("[Response DEBUG] fetchSessionData started.");
      if (!sessionId) {
        console.log("[Response DEBUG] No sessionId found, stopping fetch.");
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);
      console.log(
        "[Response DEBUG] State reset for new fetch (isLoading: true, error: null)"
      );

      try {
        console.log(
          `[Response DEBUG] Fetching session data for sessionId: ${sessionId}`
        );
        const sessionData = await sessionManager.getSession(sessionId);

        if (!sessionData) {
          console.error(
            `[Response DEBUG] Session not found for sessionId: ${sessionId}`
          );
          setError("Session not found.");
          setIsLoading(false);
          return;
        }

        console.log(
          "[Response DEBUG] Session data fetched successfully:",
          sessionData
        );
        setSession(sessionData);
        let transcriptToUse: string;
        let mediaUrlsToUse: string[] = [];
        let commandIdToUse: string;

        // If response is already in the session, display it
        if (sessionData.response && sessionData.responseAudioUrl !== undefined) {
          console.log(
            "[Response DEBUG] Found existing response in session data. Displaying it.",
            { text: sessionData.response, audioUrl: sessionData.responseAudioUrl }
          );
          setResponse({
            text: sessionData.response,
            audioUrl: sessionData.responseAudioUrl,
          });
          setIsLoading(false);
          return;
        }

        console.log(
          "[Response DEBUG] No existing response found in session. Proceeding to generate new one."
        );

        // Determine which command to use for generating the response
        if (
          passedCommandId &&
          passedTranscript &&
          passedMediaUrls !== undefined
        ) {
          console.log(
            "[Response DEBUG] Using data passed from previous page:",
            { passedCommandId, passedTranscript, passedMediaUrls }
          );
          transcriptToUse = passedTranscript;
          mediaUrlsToUse = passedMediaUrls;
          commandIdToUse = passedCommandId;
        } else {
          console.log(
            "[Response DEBUG] No data passed from previous page. Fetching latest voice command from Firestore."
          );
          const voiceCommandsQuery = query(
            collection(
              firestore,
              `troubleshootingSessions/${sessionId}/voiceCommands`
            ),
            orderBy("timestamp", "desc")
          );
          const voiceCommandsSnapshot = await getDocs(voiceCommandsQuery);

          if (voiceCommandsSnapshot.empty) {
            console.error(
              "[Response DEBUG] No voice commands found in Firestore for this session."
            );
            throw new Error("No voice commands found for this session.");
          }
          const latestCommand = voiceCommandsSnapshot.docs[0];
          const latestCommandData = latestCommand.data();
          commandIdToUse = latestCommand.id;
          transcriptToUse = latestCommandData.transcription || "";
          mediaUrlsToUse = sessionData.media || [];
          console.log("[Response DEBUG] Using latest voice command data:", {
            commandIdToUse,
            transcriptToUse,
            mediaUrlsToUse,
          });
        }

        if (!user) {
          console.error(
            "[Response DEBUG] User is not authenticated. Aborting response generation."
          );
          setError("User not authenticated.");
          setIsLoading(false);
          return;
        }

        const responseRequest: ResponseRequest = {
          session_id: sessionId,
          command_id: commandIdToUse,
          transcript: transcriptToUse,
          uid: user.uid,
          media_urls:
            mediaUrlsToUse && mediaUrlsToUse.length > 0
              ? mediaUrlsToUse
              : null,
          session_organization: sessionData.organization || null,
          use_knowledge_base: true,
        };

        console.log(
          "[Response DEBUG] Calling brain.generate_response with request:",
          responseRequest
        );
        const aiResponse = await apiClient.generate_response(responseRequest);
        const responseData = await aiResponse.json();
        console.log(
          "[Response DEBUG] Received AI response data:",
          responseData
        );

        setResponse({
          text: responseData.text_response,
          audioUrl: responseData.audio_url,
        });
        console.log("[Response DEBUG] Set response state with new data.");

        console.log(
          `[Response DEBUG] Updating session document with new response and audio URL: ${responseData.audio_url}`
        );
        await sessionManager.addResponse(
          sessionId,
          responseData.text_response,
          responseData.audio_url
        );
        console.log("[Response DEBUG] Session document updated successfully.");
      } catch (error: any) {
        console.error(
          "[Response DEBUG] An error occurred in fetchSessionData:",
          error
        );
        setError(`Failed to load data: ${error.message || "Unknown error"}`);
      } finally {
        console.log(
          "[Response DEBUG] fetchSessionData finished. Setting isLoading to false."
        );
        setIsLoading(false);
      }
    };

    if (user && firestore) {
      console.log(
        "[Response DEBUG] User and Firestore are available, calling fetchSessionData."
      );
      fetchSessionData();
    } else {
      console.log(
        "[Response DEBUG] User or Firestore not available, not calling fetchSessionData.",
        { user, firestore }
      );
      setIsLoading(false);
    }
  }, [sessionId, location.state, user, firestore, retryCount]);

  // NEW: Listen for audio URL updates from background TTS processing
  useEffect(() => {
    if (!sessionId || !response.text || response.audioUrl || !firestore) {
      return; // Only listen if we have text but no audio yet
    }

    console.log("[Response DEBUG] Setting up audio URL listener for session:", sessionId);
    setIsAudioProcessing(true);

    const unsubscribe = onSnapshot(
      doc(firestore, `troubleshootingSessions/${sessionId}`),
      (docSnapshot) => {
        const data = docSnapshot.data();
        
        // Check for audio processing errors
        if (data?.audioProcessingError) {
          console.log("[Response DEBUG] Audio processing failed:", data.audioProcessingError);
          toast.error("Audio generation failed. Text response is still available.");
          setIsAudioProcessing(false);
          return;
        }
        
        // Check for successful audio URL
        if (data?.responseAudioUrl && !response.audioUrl) {
          console.log("[Response DEBUG] Audio URL received from background processing:", data.responseAudioUrl);
          setResponse(prev => ({
            ...prev,
            audioUrl: data.responseAudioUrl
          }));
          setIsAudioProcessing(false);
        }
      },
      (error) => {
        console.error("[Response DEBUG] Audio listener error:", error);
        setIsAudioProcessing(false);
      }
    );

    // Cleanup listener on unmount
    return () => {
      console.log("[Response DEBUG] Cleaning up audio URL listener");
      unsubscribe();
    };
  }, [sessionId, response.text, response.audioUrl, firestore]);

  // UPDATED: Handler function now opens a modal
  const handleGenerateReport = async () => {
    // The sessionId is already available in the component's scope
    if (!sessionId) {
      toast.error("No active session found to generate a report.");
      return;
    }

    setIsGeneratingReport(true);
    try {
      // Call the new backend endpoint
      const response = await apiClient.generate_llm_draft_report({
        session_id: sessionId,
        // Passing null for notes as per the current requirement
        technician_final_notes: null,
      });

      if (response.ok) {
        const reportData = await response.json();
        // NEW: Instead of logging, save to state and open modal
        setGeneratedReportMarkdown(reportData.generated_report_markdown);
        setIsReportModalOpen(true);
      } else {
        // Handle API errors (e.g., 404, 500)
        const errorData = (await response.json()) as any; // <-- Add 'as any' here
        throw new Error(errorData.detail || "Failed to generate report.");
}
    } catch (error: any) {
      console.error("Error generating report:", error);
      toast.error(error.message || "An unexpected error occurred.");
    } finally {
      setIsGeneratingReport(false);
    }
  };

  // REVISED: Handler to save the final report (much simpler now)
  const handleSaveReport = async () => {
    if (!sessionId || !generatedReportMarkdown) {
      toast.error("Report data is missing.");
      return;
    }

    setIsSavingReport(true);
    try {
      // REMOVED: All navigator.geolocation logic is gone!

      // UPDATED: Call the save endpoint with the simpler request body.
      // The backend now handles finding the location.
      await apiClient.save_finalized_report({
        session_id: sessionId,
        report_markdown: generatedReportMarkdown,
        // REMOVED: latitude and longitude are no longer sent
      });

      toast.success("Report saved successfully!");
      setIsReportModalOpen(false);

    } catch (error: any) {
      console.error("Error saving report:", error);
      toast.error(error.message || "An unexpected error occurred while saving.");
    } finally {
      setIsSavingReport(false);
    }
  };

  const startNewSession = () => {
    console.log("[Response DEBUG] Navigating to /SessionCreate");
    navigate("/SessionCreate");
  };
  const goBackToHistory = () => {
    console.log("[Response DEBUG] Navigating to /History");
    navigate("/History");
  };

  const handleBackNavigation = () => {
    const target = sessionId
      ? `/VoiceCommands?sessionId=${sessionId}`
      : "/History";
    console.log(`[Response DEBUG] Handling back navigation to: ${target}`);
    if (sessionId) {
      navigate(`/VoiceCommands?sessionId=${sessionId}`);
    } else {
      navigate("/History");
    }
  };

  console.log("[Response DEBUG] Rendering component with state:", {
    isLoading,
    error,
    session,
    response,
  });
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
              {isAdmin ? (
                <button
                  onClick={() => navigate(isSystemAdmin ? "/system-admin-dashboard" : "/company-admin-dashboard?tab=sessions")}
                  className="text-gray-300 hover:text-white flex items-center gap-2"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="m12 19-7-7 7-7" />
                    <path d="M19 12H5" />
                  </svg>
                  Back to Dashboard
                </button>
              ) : (
                <ul className="flex space-x-4">
                  <li>
                    <button
                      onClick={() => navigate("/")}
                      className="text-gray-300 hover:text-white"
                    >
                      Home
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={startNewSession}
                      className="text-gray-300 hover:text-white"
                    >
                      New Session
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={goBackToHistory}
                      className="text-gray-300 hover:text-white"
                    >
                      History
                    </button>
                  </li>
                </ul>
              )}
            </nav>
          </div>
        </header>

        <main className="flex-1 container mx-auto py-8 px-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <h2 className="text-2xl font-bold">
                  Troubleshooting Response
                </h2>
              </div>
            </div>

            {!sessionId && !isLoading ? (
              <TechnicianEmptyState
                title="No Session Selected"
                description="Please select a troubleshooting session from History or start a new one."
                icon={
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-orange-500"
                  >
                    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
                    <circle cx="12" cy="13" r="3" />
                  </svg>
                }
                actionLabel="Start New Session"
                onAction={startNewSession}
                secondaryActionLabel="View History"
                onSecondaryAction={goBackToHistory}
              />
            ) : isLoading ? (
              <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 flex flex-col items-center justify-center min-h-[400px]">
                <svg
                  className="animate-spin h-12 w-12 text-blue-500 mb-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <p className="text-lg text-gray-300">
                  Generating AI-powered troubleshooting response...
                </p>
                <p className="text-sm text-gray-400 mt-2">
                  This may take a few moments
                </p>
              </div>
            ) : error ? (
              <TechnicianEmptyState
                title="Error Loading Response"
                description={
                  error || "Failed to load the troubleshooting response. Please try again."
                }
                icon={
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-red-500"
                  >
                    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                    <path d="M12 9v4" />
                    <path d="M12 17h.01" />
                  </svg>
                }
                actionLabel="Try Again"
                onAction={() => {
                  console.log("[Response DEBUG] 'Try Again' button clicked.");
                  setRetryCount((c) => c + 1);
                }}
                secondaryActionLabel="Back to History"
                onSecondaryAction={goBackToHistory}
              />
            ) : (
              <div className="space-y-6">
                {session && (
                  <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
                    <h3 className="text-lg font-semibold text-blue-400 mb-2">
                      {session.assignmentName}
                    </h3>
                    <div className="text-sm text-gray-400 space-y-1">
                      {session.organization && (
                        <p className="flex items-center">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-4 w-4 mr-2 text-gray-500"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                            />
                          </svg>
                          Organization: {session.organization}
                        </p>
                      )}
                      {session.assignmentLocation && (
                        <p className="flex items-center">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-4 w-4 mr-2 text-gray-500"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                            />
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                            />
                          </svg>
                          Location: {session.assignmentLocation}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-xl font-bold mb-4">Audio Response</h3>
                  {response.audioUrl ? (
                    <AudioPlayer src={response.audioUrl} />
                  ) : isAudioProcessing ? (
                    <div className="flex items-center gap-3 p-4 bg-gray-700/50 rounded-lg border border-blue-500/30">
                      <div className="animate-spin h-5 w-5 border-2 border-blue-400 border-t-transparent rounded-full" />
                      <div className="flex-1">
                        <p className="text-blue-400 font-medium">Generating audio response...</p>
                        <p className="text-sm text-gray-400 mt-1">Your text response is ready below. Audio will appear shortly.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 p-4 bg-gray-700/50 rounded-lg">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-gray-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                        />
                      </svg>
                      <p className="text-gray-400">Audio not available</p>
                    </div>
                  )}
                </div>

                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-xl font-bold mb-4">
                    Detailed Instructions
                  </h3>
                  <div className="prose prose-invert max-w-none prose-headings:text-blue-400 prose-p:text-gray-300 prose-strong:text-blue-300 prose-a:text-blue-400 hover:prose-a:underline prose-ul:text-gray-300 prose-ol:text-gray-300 prose-li:marker:text-blue-400">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {response.text}
                    </ReactMarkdown>
                  </div>
                  {sessionId && (
                    <div className="mt-6">
                      <FeedbackComponent
                        sessionId={sessionId}
                        initialHasFeedback={!!session?.feedback}
                      />
                    </div>
                  )}
                </div>
                {/* BUTTON CONTAINER */}
                <div className="mt-8 flex justify-center gap-4">
                  <Button
                    variant="outline"
                    onClick={handleGenerateReport}
                    disabled={isGeneratingReport}
                  >
                    {isGeneratingReport ? (
                      <>
                        <svg
                          className="animate-spin h-5 w-5 mr-2 text-white"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          ></circle>
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          ></path>
                        </svg>
                        Generating...
                      </>
                    ) : (
                      <>
                        <BrainCircuit className="h-5 w-5 mr-2" />
                        Generate Report
                      </>
                    )}
                  </Button>
                  <Button onClick={startNewSession}>Start New Session</Button>
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

        {/* NEW: Dialog for displaying and saving the generated report */}
        <Dialog open={isReportModalOpen} onOpenChange={setIsReportModalOpen}>
          <DialogContent className="max-w-3xl h-[90vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Generated Service Report</DialogTitle>
              <DialogDescription>
                Review the AI-generated report below. Once approved, it will be saved with a timestamp and your current location.
              </DialogDescription>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto p-4 border rounded-md bg-gray-900">
                <div className="prose prose-invert max-w-none prose-headings:text-blue-400 prose-p:text-gray-300 prose-strong:text-blue-300 prose-a:text-blue-400">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{generatedReportMarkdown}</ReactMarkdown>
                </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setIsReportModalOpen(false)}>Cancel</Button>
              <Button onClick={handleSaveReport} disabled={isSavingReport}>
                {isSavingReport ? (
                    <>
                        <svg className="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        Saving...
                    </>
                ) : "Approve & Save Report"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ProtectedRoute>
  );
}
