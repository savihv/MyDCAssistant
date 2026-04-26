import React, { useState, useCallback, useEffect } from "react"; // Added useEffect
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { Textarea } from "../extensions/shadcn/components/textarea";
import { Label } from "../extensions/shadcn/components/label";
import { Toaster, toast } from "sonner";
import { useDropzone } from "react-dropzone";
import { apiClient } from "../app";
import { useUserGuardContext } from "../app";
import { Mic } from "lucide-react";
import { useStreamingVoiceInput } from "../utils/useStreamingVoiceInput";
import { API_URL, auth } from "../app";
import { CreateExpertTipEntryRequest } from "../apiclient/data-contracts";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
// --- Start of Added Imports ---
import {
  getFirestore,
  collection,
  query,
  where,
  onSnapshot,
  getDocs,
} from "firebase/firestore"; // Import necessary Firestore functions
import { firebaseApp } from "../app";
import { Badge } from "../extensions/shadcn/components/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Spinner } from "../components/Spinner";
import { KnowledgeBaseSelector } from "../components/KnowledgeBaseSelector";
// --- End of Added Imports ---

// --- Start of Added Interface ---
// Interface for type safety, matching the data structure in Firestore
interface ExpertTip {
  id: string;
  title: string;
  description: string;
  technicianId: string;
  status: "pending_review" | "approved" | "rejected" | "deleted";
  createdAt: { seconds: number; nanoseconds: number }; // Firestore Timestamp
  // --- Start of Added Line ---
  mediaUrls?: string[]; // Media files are optional
  // --- End of Added Line ---
}
// --- End of Added Interface ---

const ExpertSubmission = () => {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [problem, setProblem] = useState("");
  const [solution, setSolution] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { user } = useUserGuardContext();

  // --- Start of Added State ---
  const [submittedTips, setSubmittedTips] = useState<ExpertTip[]>([]);
  const [isLoadingTips, setIsLoadingTips] = useState(true);
  const [openingMedia, setOpeningMedia] = useState<string | null>(null);
  const [targetIndex, setTargetIndex] = useState<string>(''); // Will be set by KnowledgeBaseSelector
  // --- End of Added State ---

  // ADD this new function:
  const handleDefaultNamespaceLoad = useCallback((defaultNs: string) => {
    setTargetIndex(defaultNs);
  }, []);
  
  const {
    isRecording,
    isTranscribing,
    error: voiceError,
    toggleRecording,
  } = useStreamingVoiceInput();

  // --- Start of Added useEffect for fetching data ---
  useEffect(() => {
    if (!user) {
      setIsLoadingTips(false);
      return;
    }

    const db = getFirestore(firebaseApp);
    const tipsCollection = collection(db, "expert_tips");

    // Query for tips submitted by the current technician
    const tipsQuery = query(
      tipsCollection,
      where("technicianId", "==", user.uid) // <-- ADD THIS LINE
    );

    const unsubscribe = onSnapshot(
      tipsQuery,
      (querySnapshot) => {
        const tipsData = querySnapshot.docs.map(
          (doc) => ({ id: doc.id, ...doc.data() } as ExpertTip)
        );
        // Sort by date, newest first
        tipsData.sort((a, b) => b.createdAt.seconds - a.createdAt.seconds);
        setSubmittedTips(tipsData);
        setIsLoadingTips(false);
      },
      (error) => {
        console.error("Error fetching submitted tips:", error);
        toast.error("Could not load your submitted tips.");
        setIsLoadingTips(false);
      }
    );

    // Cleanup listener on unmount
    return () => unsubscribe();
  }, [user]);
  // --- End of Added useEffect ---

  const handleMicClick = async () => {
    const transcribedText = await toggleRecording();
    if (typeof transcribedText === "string") {
      setSolution((prev) => (prev ? `${prev} ${transcribedText}` : transcribedText));
    }
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prevFiles) => [...prevFiles, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".jpeg", ".jpg", ".png"],
      "audio/mp3": [".mp3"],
      "audio/wav": [".wav"],
      "video/mp4": [".mp4"],
      "video/mov": [".mov"],
      "application/pdf": [".pdf"],
      "application/doc": [".docx"],
      "application/text": [".txt"],

    },
  });

  const removeFile = (fileName: string) => {
    setFiles(files.filter((file) => file.name !== fileName));
  };

const handleViewMedia = useCallback(
    async (tip: ExpertTip, urlToOpen: string, clickedFileIndex: number) => {
      if (!tip || !urlToOpen) return;
  
      // Use a unique key for the loading state to only show the spinner on the clicked item
      setOpeningMedia(urlToOpen);
      const toastId = toast.loading("Generating secure link...");
    
      try {
        // Step 1: Get the auth token required for the API call.
        const token = await auth.getAuthToken();
        if (!token) {
          throw new Error("Authentication failed: No token available.");
        }
  
        // Step 2: Call the new backend endpoint using `fetch`.
        // We manually construct the URL to ensure it's correct.
        const response = await fetch(`${API_URL}/expert-tips-media/${tip.id}`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });
  
        // This is the error block you pointed out. It will now handle the fetch response.
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({
            detail: "An unexpected server error occurred.",
          }));
          throw new Error(errorData.detail || `Request failed: ${response.statusText}`);
        }
  
        const data = await response.json();
        const secureUrls = data.secure_urls;
  
        // Step 3: Find the correct secure URL from the response using its index.
        const secureUrlToOpen = secureUrls?.[clickedFileIndex];
  
        if (!secureUrlToOpen) {
          throw new Error("A secure link for this specific file could not be generated.");
        }
  
        // Step 4: Open the secure link in a new tab.
        window.open(secureUrlToOpen, "_blank", "noopener,noreferrer");
  
        toast.success("Secure link generated successfully!", { id: toastId });
      } catch (error) {
        console.error("Error opening media:", error);
        toast.error((error as Error).message || "Could not open file.", {
          id: toastId,
        });
      } finally {
        setOpeningMedia(null);
      }
    },
    [], // No dependencies needed
  );
  
  
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim() || !problem.trim() || !solution.trim()) {
      toast.error("Title, problem, and solution are required.");
      return;
    }

    setIsSubmitting(true);
    const submissionToast = toast.loading("Submitting expert tip...");

    try {
      // Step 1: Upload files first using the proven, working endpoint
      const uploadedMediaUrls: string[] = [];
      if (files.length > 0) {
        toast.loading("Uploading files...", { id: submissionToast });

        // Use Promise.all to upload files in parallel for better performance
        const uploadPromises = files.map(async (file) => {
          const formData = new FormData();
          formData.append("file", file);

          const token = await auth.getAuthToken();
          if (!token) {
            throw new Error("Authentication failed: No token available.");
          }

          // Use fetch directly to handle FormData correctly, bypassing brain client for this call
          const response = await fetch(`${API_URL}/uploads/upload_general_file`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              // NOTE: Do NOT set Content-Type, browser does it for multipart/form-data
            },
            body: formData,
          });

          if (!response.ok) {
            const errorData = await response
              .json()
              .catch(() => ({ detail: "Upload failed with an unknown error." }));
            throw new Error(
              `Failed to upload ${file.name}: ${errorData.detail || response.statusText}`
            );
          }

          const data = await response.json();
          if (!data.gcs_path) {
            throw new Error(
              `Upload for ${file.name} succeeded but did not return a file path.`
            );
          }
          return data.gcs_path;
        });

        const results = await Promise.all(uploadPromises);
        uploadedMediaUrls.push(...results);
      }

      // Step 2: Create the expert tip entry with the GCS URLs
      toast.loading("Saving submission...", { id: submissionToast });

      const tipData: CreateExpertTipEntryRequest = {
        title: title,
        // Combine 'problem' and 'solution' into the single 'description' field
        description: `Problem: ${problem}\n\nSolution: ${solution}`,
        mediaUrls: uploadedMediaUrls,
        target_index: targetIndex, 
      };
      const tipResponse = await apiClient.create_expert_tip_entry(tipData);

      if (!tipResponse.ok) {
        const errorData = await tipResponse.json();
        throw new Error(errorData.detail || "Failed to save submission.");
      }

      toast.success("Expert tip submitted successfully for review!", {
        id: submissionToast,
      });

      // Clear the form
      setTitle("");
      setProblem("");
      setSolution("");
      setFiles([]);
      setTargetIndex('expert');
    } catch (error) {
      console.error("Submission failed:", error);
      const errorMessage =
        (error as Error).message || "An unexpected error occurred.";
      toast.error(`Submission failed: ${errorMessage}`, {
        id: submissionToast,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Toaster position="top-center" richColors />
      <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto flex items-center justify-between">
          <div
            className="flex items-center cursor-pointer"
            onClick={() => navigate("/")}
          >
            <JuniorTechBotLogo className="w-8 h-8 mr-2" />
            <h1 className="text-xl font-bold">
              <span className="text-white">Junior</span>
              <span className="text-blue-400">TechBot</span>
            </h1>
          </div>
          <nav>
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
                  onClick={() => navigate("/SessionCreate")} 
                  className="text-gray-300 hover:text-white"
                >
                  New Session
                </button>
              </li>
              <li>
                <button
                  onClick={() => navigate("/History")}
                  className="text-gray-300 hover:text-white"
                >
                  History
                </button>
              </li>
              <li>
                <button
                  onClick={() => navigate("/KnowledgeBaseSearch")}
                  className="text-gray-300 hover:text-white"
                >
                  Knowledge Base Search
                </button>
              </li>
              <li>
                <button
                  onClick={() => navigate("/ExpertSubmission")}
                  className="text-blue-400"
                >
                  Expert Submission
                </button>
              </li>
            </ul>
          </nav>
        </div>
      </header>
      <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center p-4 sm:p-6 md:p-8">
        <div className="w-full max-w-3xl bg-gray-800 rounded-lg shadow-lg p-8 border border-gray-700">
          <h1 className="text-3xl font-bold mb-2 text-center text-gray-100">
            Submit Expert Knowledge
          </h1>
          <p className="text-center text-gray-400 mb-8">
            Share your insights and solutions. Your submission will be reviewed
            by an admin before being added to the knowledge base.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label
                htmlFor="title"
                className="text-lg font-semibold text-gray-300"
              >
                Title
              </Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., How to Recalibrate the XYZ Sensor"
                className="bg-gray-700 border-gray-600 text-white"
                required
              />
            </div>

            {/* First Block: For the Problem */}
            <div className="space-y-2">
              <Label
                htmlFor="problem"
                className="text-lg font-semibold text-gray-300"
              >
                Problem
              </Label>
              <Textarea
                id="problem"
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                placeholder="Describe the problem, including symptoms or error codes."
                className="bg-gray-700 border-gray-600 text-white min-h-[100px]"
                required
              />
            </div>

            {/* Second Block: For the Solution (includes the mic button) */}
            <div className="space-y-2">
              <Label
                htmlFor="solution"
                className="text-lg font-semibold text-gray-300"
              >
                Solution
              </Label>
              <div className="relative">
                <Textarea
                  id="solution"
                  value={solution}
                  onChange={(e) => setSolution(e.target.value)}
                  placeholder="Provide a detailed, step-by-step guide to fix the problem."
                  className="bg-gray-700 border-gray-600 text-white min-h-[150px] pr-12"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleMicClick}
                  className="absolute top-2 right-2 text-gray-400 hover:text-white"
                  disabled={isTranscribing}
                >
                  {isRecording ? (
                    <Mic className="h-5 w-5 text-red-500 animate-pulse" />
                  ) : (
                    <Mic className="h-5 w-5" />
                  )}
                </Button>
              </div>
              {isTranscribing && (
                <p className="text-xs text-blue-400 mt-1">Transcribing...</p>
              )}
              {voiceError && (
                <p className="text-xs text-red-500 mt-1">{voiceError}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label className="text-lg font-semibold text-gray-300">
                Target Knowledge Base
              </Label>
              <KnowledgeBaseSelector
                value={targetIndex}
                onChange={setTargetIndex}
                disabled={isSubmitting}
                onDefaultNamespaceLoad={handleDefaultNamespaceLoad}
              />
              <p className="text-sm text-gray-400">
                Select which knowledge base this tip should be added to when approved.
              </p>
            </div>
            
            <div className="space-y-2">
              <Label className="text-lg font-semibold text-gray-300">
                Supporting Files (Images/Audio/PDFs)
              </Label>
              <div
                {...getRootProps()}
                className={`p-8 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors
                  ${
                    isDragActive
                      ? "border-blue-500 bg-gray-700"
                      : "border-gray-600 hover:border-gray-500"
                  }
                `}
              >
                <input {...getInputProps()} />
                <p>Drag & drop files here, or click to select files</p>
                <em className="text-sm text-gray-500">
                  (Images and audio files are accepted)
                </em>
              </div>
            </div>

            {files.length > 0 && (
              <div className="space-y-2">
                <h3 className="font-semibold text-gray-300">
                  Selected files:
                </h3>
                <ul className="space-y-2">
                  {files.map((file, index) => (
                    <li
                      key={index}
                      className="flex items-center justify-between bg-gray-700 p-2 rounded-md"
                    >
                      <span className="text-sm text-gray-200 truncate pr-4">
                        {file.name}
                      </span>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeFile(file.name)}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-lg py-3"
              disabled={isSubmitting || !targetIndex}
            >
              {isSubmitting ? "Submitting..." : "Submit for Review"}
            </Button>
          </form>
        </div>

        {/* --- Start of Added Section: Your Submitted Tips --- */}
        <div className="w-full max-w-3xl mt-12">
          <h2 className="text-3xl font-bold mb-8 text-center text-gray-100 border-t border-gray-700 pt-8">
            Your Submitted Tips
          </h2>

          {isLoadingTips ? (
            <div className="flex items-center justify-center py-8">
              <Spinner size="lg" />
              <span className="ml-4">Loading your tips...</span>
            </div>
          ) : submittedTips.length === 0 ? (
            <div className="text-center text-gray-400 bg-gray-800 rounded-lg p-8 border border-gray-700">
              <p>You haven't submitted any tips yet.</p>
              <p className="text-sm text-gray-500 mt-2">Use the form above to share your knowledge.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {submittedTips.map((tip) => (
                <div key={tip.id} className="bg-gray-800 rounded-lg shadow-lg p-6 border border-gray-700">
                   <div className="flex justify-between items-start mb-4">
                    <h3 className="text-xl font-semibold text-gray-100">{tip.title}</h3>
                    <Badge
                      variant={
                        tip.status === 'approved'
                          ? 'default'
                          : tip.status === 'pending_review'
                          ? 'secondary'
                          : 'destructive'
                      }
                      className={
                        tip.status === 'approved'
                          ? 'bg-green-600/20 text-green-300 border-green-500/50'
                          : tip.status === 'pending_review'
                          ? 'bg-yellow-600/20 text-yellow-300 border-yellow-500/50'
                          : 'bg-red-600/20 text-red-300 border-red-500/50'
                      }
                    >
                      {tip.status.replace('_', ' ').toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-500 mb-4">
                    Submitted on:{" "}
                    {new Date(
                      tip.createdAt?.seconds * 1000
                    ).toLocaleDateString()}
                  </p>
                  <p className="text-gray-300 whitespace-pre-wrap text-sm">
                    {tip.description}
                  </p>
                  {/* --- Start of Modified Section --- */}
                  {tip.mediaUrls && tip.mediaUrls.length > 0 && (
                    <div className="mt-4">
                      <h4 className="font-semibold text-sm text-gray-400">Attached Media</h4>
                      <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                        {tip.mediaUrls.map((url, index) => {
                          const fileName = decodeURIComponent(url.split('/').pop()?.split('?')[0] || `Media File ${index + 1}`);
                          // The loading state is now tied to the specific URL, not the whole tip
                          const isLoading = openingMedia === url;
                          return (
                            <li key={index}>
                              <button
                                // *** THIS IS THE CRUCIAL CHANGE ***
                                onClick={() => handleViewMedia(tip, url, index)}
                                disabled={isLoading}
                                className="text-blue-400 hover:underline text-sm disabled:text-gray-500 ..."
                              >
                                {isLoading && <Spinner size="sm" className="mr-2" />}
                                {fileName}
                              </button>
                            </li>
                        );
                        })}
                      </ul>
                    </div>
                  )}
                  {/* --- End of Modified Section --- */}
                </div>
              ))}
            </div>
          )}
        </div>
        {/* --- End of Added Section --- */}

      </div>
    </>
  );
};

export default ExpertSubmission;
