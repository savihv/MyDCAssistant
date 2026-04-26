import React from "react";
import { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { Paperclip, Mic } from "lucide-react";
import { sessionManager, ChatMessage } from "../utils/sessionManager";
import { Timestamp } from "firebase/firestore";
import { apiClient } from "../app";
import { API_URL, useUserGuardContext } from "../app";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { AudioPlayer } from "../components/AudioPlayer";

const SessionChatPage = () => {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("sessionId");
  const navigate = useNavigate();
  const { user } = useUserGuardContext();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!sessionId) {
      setIsLoading(false);
      return;
    }

    const fetchHistory = async () => {
      try {
        setIsLoading(true);
        const history = await sessionManager.getConversationHistory(sessionId);
        console.log("[SessionChatPage.tsx DEBUG] Fetched conversation history:", history);
        setMessages(history);
      } catch (err: any) {
        console.error("Failed to load conversation history:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !sessionId) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("sessionId", sessionId);
      formData.append("file", file);

      // FIX: Pass a single object to the brain client
      const response = await apiClient.upload_technician_file_v2({
        sessionId: sessionId,
        file: file,
      });

      if (response.ok) {
        const result = await response.json();
        // Add a system message to the chat
        const systemMessage: ChatMessage = {
          id: `upload-${Date.now()}`,
          content: `File "${result.filename}" uploaded successfully. You can now ask questions about it.`,
          role: "system",
          timestamp: Timestamp.now(),
        };
        setMessages((prev) => [...prev, systemMessage]);
      } else {
        const errorData = await response.json();
        throw new Error((errorData as any).detail || "File upload failed");
      }
    } catch (error) {
      console.error("Upload error:", error);
      setUploadError(error instanceof Error ? error.message : "An unknown error occurred during upload.");
    } finally {
      setIsUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleMicClick = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorderRef.current = new MediaRecorder(stream);
        audioChunksRef.current = [];

        mediaRecorderRef.current.ondataavailable = (event) => {
          audioChunksRef.current.push(event.data);
        };

        mediaRecorderRef.current.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const audioFile = new File([audioBlob], "voice-command.webm", { type: "audio/webm" });

          setTranscriptionError(null);
          try {
            const response = await apiClient.transcribe_audio({ audio: audioFile });
            if (response.ok) {
              const data = await response.json();
              setNewMessage((prev) => prev + data.transcription);
            } else {
              const errorData = await response.json();
              throw new Error((errorData as any).detail || "Transcription failed");
            }
          } catch (error) {
            console.error("Transcription error:", error);
            setTranscriptionError(error instanceof Error ? error.message : "An unknown error occurred during transcription.");
          } finally {
             // Stop all media tracks to turn off the mic indicator
            stream.getTracks().forEach(track => track.stop());
          }
        };

        mediaRecorderRef.current.start();
        setIsRecording(true);
      } catch (error) {
        console.error("Error accessing microphone:", error);
        setTranscriptionError("Could not access microphone. Please check permissions.");
      }
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !sessionId || !user.email) return;

    setIsSending(true);
    setUploadError(null);

    const optimisticUserMessage: ChatMessage = {
      id: `optimistic-${Date.now()}`,
      role: 'user',
      content: newMessage,
      timestamp: Timestamp.now(),
    };

    console.log("[SessionChatPage.tsx DEBUG] Created optimistic user message:", optimisticUserMessage);
    setMessages(prev => [...prev, optimisticUserMessage]);
    setNewMessage("");

    try {
      // 1. Save user command and get its ID
      const commandId = await sessionManager.addMessageToSession(sessionId, optimisticUserMessage);

      // Create a clean history for the backend (text-only)
      const historyForApi = messages.slice(-10);

      // 2. Call the backend API
      console.log("[SessionChatPage.tsx DEBUG] Calling brain.generate_response with request:", {
        session_id: sessionId,
        transcript: newMessage,
        uid: user.uid,
        command_id: commandId,
        history: historyForApi.map(m => ({ role: m.role, content: m.content })),
        media_urls: [], // TODO: Populate with uploaded media
      });
      const response = await apiClient.generate_response({
        session_id: sessionId,
        transcript: newMessage,
        uid: user.uid,
        command_id: commandId,
        history: historyForApi.map(m => ({ role: m.role, content: m.content })),
        media_urls: [], // TODO: Populate with uploaded media
      });

      if (!response.ok) {
        throw new Error("Failed to get response from the assistant.");
      }

      const responseData = await response.json();
      console.log("[SessionChatPage.tsx DEBUG] Received response data:", responseData);

      console.log("[SessionChatPage.tsx DEBUG] Creating assistant message. Text:", responseData.text_response, "Audio URL:", responseData.audio_url);
      const assistantMessage: ChatMessage = {
        id: `${commandId}-response`,
        role: 'assistant',
        content: responseData.text_response,
        timestamp: Timestamp.now(), // This will be slightly off, but acceptable
        audioUrl: responseData.audio_url,
      };
      
      // Replace optimistic message with final one and add assistant response
      setMessages(prev => {
        const finalMessages = prev.filter(m => m.id !== optimisticUserMessage.id);
        const finalUserMessage = { ...optimisticUserMessage, id: commandId };
        return [...finalMessages, finalUserMessage, assistantMessage];
      });

    } catch (err: any) {
      setUploadError(err.message || "An error occurred while sending the message.");
      // Revert optimistic update on error
      setMessages(prev => prev.filter(m => m.id !== optimisticUserMessage.id));
    } finally {
      setIsSending(false);
    }
  };

  const formatDate = (timestamp: Timestamp) => {
    if (!timestamp) return "Sending...";
    return new Date(timestamp.seconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center cursor-pointer" onClick={() => navigate("/")}>
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

      <CardHeader className="p-4 border-b border-gray-700 bg-gray-800">
        <CardTitle>Troubleshooting Session</CardTitle>
      </CardHeader>
      
      <CardContent className="flex-grow p-4 overflow-y-auto">
        <div className="space-y-4">
          {isLoading && (
            <div className="flex justify-center items-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white" />
            </div>
          )}
          {uploadError && (
            <div className="flex justify-center items-center h-full">
              <p className="text-red-500">{uploadError}</p>
            </div>
          )}
          {!isLoading && !uploadError && messages.map((message) => (
            <div
              key={message.id}
              className={`flex flex-col ${
                message.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-md p-3 rounded-lg ${
                  message.role === "user"
                    ? "bg-blue-600"
                    : "bg-gray-700"
                }`}
              >
                <p>{message.content}</p>
                  {(() => {
                    // This logic prevents the app from crashing when an assistant message
                    // has no audio. It now passes the full URL directly.
                    if (message.role === 'assistant' && message.audioUrl) {
                      return <AudioPlayer src={message.audioUrl} />;
                    }
                    return null;
                  })()}
                </div>
              <span className="text-xs text-gray-500 mt-1 px-1">
                {formatDate(message.timestamp)}
              </span>
            </div>
          ))}
          {isSending && (
            <div className="flex flex-col items-start">
              <div className="max-w-md p-3 rounded-lg bg-gray-700">
                <p className="italic">Assistant is typing...</p>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </CardContent>
      
      <CardFooter className="p-4 border-t border-gray-700 bg-gray-800">
        {uploadError && <p className="text-red-500 text-xs mb-2">{uploadError}</p>}
        {transcriptionError && <p className="text-red-500 text-xs mb-2">{transcriptionError}</p>}
        <div className="flex items-center w-full space-x-2">
          <Input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            disabled={isUploading}
          />
          <Button variant="ghost" size="sm" onClick={handleFileSelect} disabled={isUploading}>
            {isUploading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
            ) : (
              <Paperclip className="h-5 w-5" />
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleMicClick}>
            {isRecording ? (
              <Mic className="h-5 w-5 text-red-500 animate-pulse" />
            ) : (
              <Mic className="h-5 w-5" />
            )}
          </Button>
          <Input 
            type="text" 
            placeholder="Type your command or question..." 
            className="flex-grow bg-gray-700 border-gray-600 focus:ring-blue-500"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            disabled={isSending}
          />
          <Button onClick={handleSendMessage} disabled={isSending}>
            {isSending ? "Sending..." : "Send"}
          </Button>
        </div>
      </CardFooter>
    </div>
  );
};

export default SessionChatPage;
