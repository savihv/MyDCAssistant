import React, { useState, useRef, useEffect } from "react";
import { Button } from "../components/Button";
import { feedbackManager } from "../utils/feedbackManager";
import { useUserGuardContext } from "../app";

interface Props {
  sessionId: string;
  initialHasFeedback?: boolean; // New prop from parent
  onFeedbackSubmitted?: () => void;
}

export function FeedbackComponent({ sessionId, initialHasFeedback, onFeedbackSubmitted }: Props) {
  const { user } = useUserGuardContext();
  const [isHelpful, setIsHelpful] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [hasFeedback, setHasFeedback] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  
  // Use the initialHasFeedback prop and internal feedbackSubmitted state
  // to determine if feedback form or thank you message should be shown.
  // The `hasFeedback` state is now primarily controlled by the prop.
  useEffect(() => {
    if (initialHasFeedback !== undefined) {
      setHasFeedback(initialHasFeedback);
    } else if (sessionId && user) {
      // Only check existing feedback if initialHasFeedback is not provided
      const checkExistingFeedback = async () => {
        try {
          const hasExistingFeedback = await feedbackManager.hasFeedback(sessionId);
          setHasFeedback(hasExistingFeedback);
        } catch (error) {
          console.error("Error checking for existing feedback:", error);
        }
      };
      checkExistingFeedback();
    }
  }, [initialHasFeedback, sessionId, user]);
  
  // Handle recording timer
  useEffect(() => {
    if (isRecording) {
      timerRef.current = window.setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);
  
  // Format recording time as MM:SS
  const formattedRecordingTime = () => {
    const minutes = Math.floor(recordingTime / 60);
    const seconds = recordingTime % 60;
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };
  
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/mpeg" });
        const audioUrl = URL.createObjectURL(audioBlob);
        setAudioUrl(audioUrl);
        
        // Stop all tracks in the stream
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingTime(0);
    } catch (error) {
      console.error("Error starting audio recording:", error);
      alert("Unable to access microphone. Please check your device permissions.");
    }
  };
  
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };
  
  const deleteRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
  };
  
  const dataURLtoBlob = (dataURL: string): Blob => {
    const arr = dataURL.split(",");
    const mime = arr[0].match(/:(.*?);/)?.[1] || "";
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], { type: mime });
  };
  
  const handleSubmit = async () => {
    if (isHelpful === null) {
      alert("Please indicate if the response was helpful.");
      return;
    }
    
    setSubmitting(true);
    
    try {
      let audioFileUrl = null;
      let audioTranscript = null;
      
      // If there's an audio recording, upload it and transcribe
      if (audioUrl) {
        // In a real application, we would upload the audio to storage
        // and then transcribe it. For now, we'll just use the URL.
        audioFileUrl = audioUrl;
      }
      
      // Submit the feedback
      await feedbackManager.createFeedback({
        sessionId,
        isHelpful,
        comment: comment || undefined,
        audioUrl: audioFileUrl || undefined,
        audioTranscript,
      });
      
      setFeedbackSubmitted(true);
      if (onFeedbackSubmitted) {
        onFeedbackSubmitted();
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
      alert("Error submitting feedback. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };
  
  if ((initialHasFeedback && !feedbackSubmitted) || hasFeedback || feedbackSubmitted) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-center py-4">
          <div className="text-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-xl font-bold mb-2">Thank You!</h3>
            <p className="text-gray-300 mb-2">Your feedback has been submitted.</p>
            <p className="text-gray-400 text-sm">This helps us improve our troubleshooting responses for similar issues.</p>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-xl font-bold mb-4">Was this response helpful?</h3>
      
      {/* Thumbs Up/Down Selection */}
      <div className="flex justify-center space-x-8 mb-6">
        <button 
          className={`flex flex-col items-center p-4 rounded-lg transition-all ${
            isHelpful === true ? "bg-green-900/30 border border-green-700" : "hover:bg-gray-700"
          }`}
          onClick={() => setIsHelpful(true)}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className={`h-12 w-12 ${isHelpful === true ? "text-green-500" : "text-gray-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
          </svg>
          <span className={`mt-2 font-medium ${isHelpful === true ? "text-green-400" : "text-gray-400"}`}>Helpful</span>
        </button>
        
        <button 
          className={`flex flex-col items-center p-4 rounded-lg transition-all ${
            isHelpful === false ? "bg-red-900/30 border border-red-700" : "hover:bg-gray-700"
          }`}
          onClick={() => setIsHelpful(false)}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className={`h-12 w-12 ${isHelpful === false ? "text-red-500" : "text-gray-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
          </svg>
          <span className={`mt-2 font-medium ${isHelpful === false ? "text-red-400" : "text-gray-400"}`}>Not Helpful</span>
        </button>
      </div>
      
      {/* Text Comment */}
      <div className="mb-6">
        <label htmlFor="comment" className="block text-sm font-medium text-gray-300 mb-2">
          Additional Comments (Optional)
        </label>
        <textarea
          id="comment"
          rows={3}
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-white"
          placeholder="Share more details about your experience with this response..."
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </div>
      
      {/* Audio Recording */}
      <div className="mb-6">
        <div className="flex items-center mb-2">
          <h4 className="text-sm font-medium text-gray-300">Voice Feedback (Optional)</h4>
          <div className="bg-blue-900/30 rounded-full px-2 py-0.5 text-xs text-blue-300 ml-2">
            Field-Friendly
          </div>
        </div>
        
        {audioUrl ? (
          <div className="flex flex-col space-y-2">
            <audio src={audioUrl} controls className="w-full" />
            <div className="flex space-x-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="flex-1 text-red-400 border-red-800 hover:bg-red-900/50"
                onClick={deleteRecording}
              >
                Delete Recording
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between bg-gray-700 rounded-md p-2">
            {isRecording ? (
              <div className="flex items-center space-x-2 text-red-400 animate-pulse">
                <span className="block w-3 h-3 rounded-full bg-red-500"></span>
                <span>Recording... {formattedRecordingTime()}</span>
              </div>
            ) : (
              <div className="text-gray-400 text-sm">
                Record your feedback verbally
              </div>
            )}
            
            <Button 
              variant={isRecording ? "outline" : "default"}
              size="sm"
              className={isRecording ? "text-red-400 border-red-800" : ""}
              onClick={isRecording ? stopRecording : startRecording}
            >
              {isRecording ? "Stop Recording" : "Start Recording"}
            </Button>
          </div>
        )}
        
        <p className="text-xs text-gray-400 mt-1">
          Speak freely about your experience with this troubleshooting response.
        </p>
      </div>
      
      {/* Submit Button */}
      <div className="flex justify-center">
        <Button 
          variant="default"
          className="w-full"
          onClick={handleSubmit}
          disabled={submitting || isHelpful === null}
        >
          {submitting ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Submitting...
            </>
          ) : "Submit Feedback"}
        </Button>
      </div>
    </div>
  );
}
