import { useState, useRef } from "react";
import { apiClient } from "app";

type UseStreamingVoiceInputReturn = {
  isRecording: boolean;
  isTranscribing: boolean;
  error: string | null;
  toggleRecording: () => Promise<string | void>;
};

export const useStreamingVoiceInput = (): UseStreamingVoiceInputReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  // A resolver function to bridge the event-based MediaRecorder API with the async hook consumer
  const transcriptionResolver = useRef<(text: string | void) => void>();

  const startRecording = async (): Promise<void> => {
    if (isRecording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      setError(null);

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        setIsTranscribing(true);
        setError(null);

        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const audioFile = new File([audioBlob], "voice-command.webm", { type: "audio/webm" });

        try {
          // Check if there's actual audio data to prevent empty API calls
          if (audioBlob.size > 0) {
            const response = await apiClient.transcribe_audio({ audio: audioFile });
            if (response.ok) {
              const data = await response.json();
              if (transcriptionResolver.current) {
                transcriptionResolver.current(data.transcription);
              }
            } else {
              const errorData = await response.json();
              throw new Error((errorData as any).detail || "Transcription failed");
            }
          } else {
            // If no data, resolve with nothing.
            if (transcriptionResolver.current) {
                transcriptionResolver.current();
            }
          }
        } catch (err) {
          console.error("Transcription error:", err);
          setError(err instanceof Error ? err.message : "An unknown error occurred.");
          if (transcriptionResolver.current) {
            transcriptionResolver.current(); // Resolve with void on error
          }
        } finally {
          setIsTranscribing(false);
          // Ensure all tracks are stopped to release the mic
          stream.getTracks().forEach((track) => track.stop());
        }
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      setError("Could not access microphone. Please check permissions.");
      setIsRecording(false);
    }
  };

  const stopRecording = async (): Promise<string | void> => {
    return new Promise((resolve) => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        transcriptionResolver.current = resolve;
        mediaRecorderRef.current.stop();
        setIsRecording(false);
      } else {
        resolve(); // Resolve immediately if not recording
      }
    });
  };

  const toggleRecording = async (): Promise<string | void> => {
    if (isRecording) {
      return await stopRecording();
    } else {
      await startRecording();
      // startRecording doesn't return the text, so we return void here.
      // The consumer will get the text from the stopRecording promise.
    }
  };

  return { isRecording, isTranscribing, error, toggleRecording };
};
