import React, { useState, useRef, useEffect } from 'react';
import { Button } from "../components/Button";
import { Play, Pause, RotateCcw, Loader2, AlertTriangle } from "lucide-react";
import { useUserGuardContext, auth, API_URL } from "../app";

interface AudioPlayerProps {
  src: string | null | undefined;
}

console.log("[AudioPlayer DEBUG] Component file loaded");

export function AudioPlayer({ src }: AudioPlayerProps) {
  console.log(`[AudioPlayer DEBUG] Instantiated with src: ${src}`);
  const { user } = useUserGuardContext();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  
  // No longer need retryCount in state
  // const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    console.log(`[AudioPlayer DEBUG] useEffect[src, user] triggered. src: ${src}`);
    
    // Define a function to sleep for a given time
    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    const fetchAndSetAudio = async () => {
      if (!src) {
        setIsLoading(false);
        setError("No audio source provided.");
        console.log("[AudioPlayer DEBUG] No src provided, aborting fetch.");
        return;
      }
      
      setIsLoading(true);
      setError(null);
      
      const MAX_RETRIES = 4;
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          console.log(`[AudioPlayer DEBUG] Attempt ${attempt}/${MAX_RETRIES}. Fetching audio from: ${src}`);
          
          console.log("[AudioPlayer DEBUG] Getting auth token...");
          const token = await auth.getAuthToken();
          if (!token) {
            // This is a permanent failure, no point in retrying.
            throw new Error("Authentication token not available.");
          }
          console.log("[AudioPlayer DEBUG] Auth token retrieved.");
          
          const response = await fetch(src, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          console.log(`[AudioPlayer DEBUG] Fetch response status: ${response.status}`);

          if (response.ok) {
            const blob = await response.blob();
            console.log(`[AudioPlayer DEBUG] Blob received. Size: ${blob.size}, Type: ${blob.type}`);
            
            const objectUrl = URL.createObjectURL(blob);
            console.log(`[AudioPlayer DEBUG] Created Object URL: ${objectUrl}`);
            
            if (audioRef.current) {
              console.log("[AudioPlayer DEBUG] Setting audioRef.current.src to the new object URL.");
              audioRef.current.src = objectUrl;
            }
            setIsLoading(false);
            
            // Cleanup the object URL when the component unmounts
            return () => {
              URL.revokeObjectURL(objectUrl);
              console.log(`[AudioPlayer DEBUG] Revoked Object URL: ${objectUrl}`);
            };
          }

          // If not ok, and it's a 404, we retry after a delay.
          if (response.status === 404) {
            if (attempt < MAX_RETRIES) {
              const delay = 1000 * attempt;
              console.warn(`[AudioPlayer WARN] 404 Not Found. Retrying in ${delay}ms...`);
              await sleep(delay);
              continue; // Go to the next iteration of the loop
            } else {
              // This was the last attempt
              throw new Error(`Failed to fetch audio after ${MAX_RETRIES} attempts.`);
            }
          }
          
          // For other non-ok statuses, fail immediately.
          throw new Error(`Failed to fetch audio: ${response.status} ${response.statusText}`);

        } catch (err: any) {
          console.error(`[AudioPlayer ERROR] An error occurred on attempt ${attempt}:`, err);
          // If this is the last attempt, set the final error state.
          if (attempt === MAX_RETRIES) {
            setError(err.message || "An unknown error occurred.");
            setIsLoading(false);
          }
        }
      }
    };

    fetchAndSetAudio();
  }, [src, user]); // Removed retryCount from dependencies

  useEffect(() => {
    const audioElement = audioRef.current;
    if (!audioElement) {
        console.warn("[AudioPlayer DEBUG] useEffect[audioRef] triggered but audio element is null.");
        return;
    };
    
    console.log("[AudioPlayer DEBUG] Adding event listeners to audio element.");

    const handleEnded = () => {
        console.log("[AudioPlayer DEBUG] 'ended' event triggered.");
        setIsPlaying(false)
    };
    const handlePlay = () => {
        console.log("[AudioPlayer DEBUG] 'play' event triggered.");
        setIsPlaying(true)
    };
    const handlePause = () => {
        console.log("[AudioPlayer DEBUG] 'pause' event triggered.");
        setIsPlaying(false)
    };
    const handleCanPlay = () => {
        console.log("[AudioPlayer DEBUG] 'canplay' event triggered. Audio is ready to play.");
    }
    const handleError = (e: Event) => {
        console.error("[AudioPlayer ERROR] 'error' event triggered on audio element.", e);
        setError("Audio playback error.");
    }

    audioElement.addEventListener("ended", handleEnded);
    audioElement.addEventListener("play", handlePlay);
    audioElement.addEventListener("pause", handlePause);
    audioElement.addEventListener("canplay", handleCanPlay);
    audioElement.addEventListener("error", handleError);

    return () => {
      console.log("[AudioPlayer DEBUG] Cleaning up event listeners from audio element.");
      audioElement.removeEventListener("ended", handleEnded);
      audioElement.removeEventListener("play", handlePlay);
      audioElement.removeEventListener("pause", handlePause);
      audioElement.removeEventListener("canplay", handleCanPlay);
      audioElement.removeEventListener("error", handleError);
    };
  }, [audioRef.current]); 

  const handlePlayPause = () => {
    console.log(`[AudioPlayer DEBUG] handlePlayPause clicked. State: isPlaying=${isPlaying}, isLoading=${isLoading}, error=${error}`);
    if (!audioRef.current || isLoading || error) {
      console.warn("[AudioPlayer DEBUG] Play/Pause blocked by component state.");
      return;
    }
    if (isPlaying) {
      console.log("[AudioPlayer DEBUG] Pausing audio.");
      audioRef.current.pause();
    } else {
      console.log("[AudioPlayer DEBUG] Attempting to play audio.");
      audioRef.current.play().catch(e => {
        console.error("[AudioPlayer ERROR] Playback failed:", e)
        setError(`Playback failed: ${e.message}`);
      });
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
        // This log is very noisy, so it's commented out. Uncomment for detailed tracking.
        // console.log(`[AudioPlayer DEBUG] Time update: ${audioRef.current.currentTime}`);
        setCurrentTime(audioRef.current.currentTime);
    }
  };
  
  const handleLoadedMetadata = () => {
    if (audioRef.current) {
        console.log(`[AudioPlayer DEBUG] 'loadedmetadata' event. Duration set to: ${audioRef.current.duration}`);
        setDuration(audioRef.current.duration);
    };
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (audioRef.current) {
        const newTime = Number(e.target.value);
        console.log(`[AudioPlayer DEBUG] handleSeek to: ${newTime}`);
        audioRef.current.currentTime = newTime;
        setCurrentTime(newTime); // Optimistically update the state
    };
  };

  const handleRestart = () => {
    if (audioRef.current) {
        console.log("[AudioPlayer DEBUG] handleRestart: Setting current time to 0.");
        audioRef.current.currentTime = 0;
    }
  };

  const formatTime = (timeInSeconds: number) => {
    if (isNaN(timeInSeconds) || timeInSeconds === Infinity) return "0:00";
    const minutes = Math.floor(timeInSeconds / 60);
    const seconds = Math.floor(timeInSeconds % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  console.log(`[AudioPlayer DEBUG] Rendering with state: isLoading=${isLoading}, isPlaying=${isPlaying}, error=${error}, duration=${duration}, currentTime=${currentTime}`);

  return (
    <div className="bg-gray-800/50 p-3 rounded-lg mt-2 border border-gray-700">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        className="hidden"
        controls={false}
      />
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm mb-2">
            <AlertTriangle className="w-4 h-4" />
            <p>Audio failed to load: {error}</p>
        </div>
      )}
      <div className="flex items-center gap-3">
        <Button onClick={handlePlayPause} size="sm" className="bg-blue-600 hover:bg-blue-700 w-9 h-9" disabled={isLoading || !!error}>
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : (isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />)}
        </Button>
        <div className="flex-grow">
          <input
            type="range"
            min="0"
            max={duration || 0}
            value={currentTime}
            onChange={handleSeek}
            disabled={isLoading || !!error}
            className="w-full h-1.5 bg-gray-600 rounded-lg appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundImage: `linear-gradient(to right, #3b82f6 ${duration > 0 ? (currentTime / duration) * 100 : 0}%, #4b5563 ${duration > 0 ? (currentTime / duration) * 100 : 0}%)` }}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
        <Button onClick={handleRestart} size="sm" variant="ghost" className="w-9 h-9" disabled={isLoading || !!error}>
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};
