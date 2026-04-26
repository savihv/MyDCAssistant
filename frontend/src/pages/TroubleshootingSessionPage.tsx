import React, { useState, useEffect } from "react";
import { useSearchParams, Navigate } from "react-router-dom";
import { apiClient } from "../app";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { toast } from "sonner";
import { useUserGuardContext } from "../app";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../extensions/shadcn/components/card";

// Assuming apiClient.upload_technician_file_v2 is generated and available
// and its response includes { gcs_path: string, filename: string, session_id: string }

interface UploadedMedia {
  filename: string;
  gcsPath: string;
}

const TroubleshootingSessionPage = () => {
  const { user } = useUserGuardContext(); // Ensures user is authenticated
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("sessionId");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedMedia[]>([]); // To display uploaded files

  // TODO: In a real app, you would fetch existing media for the session here
  // useEffect(() => {
  //   if (sessionId) {
  //     // brain.get_session_media({ sessionId }).then(response => {
  //     //   setUploadedFiles(response.data); // Assuming an endpoint to get media
  //     // }).catch(error => {
  //     //   toast.error("Failed to load existing media for this session.");
  //     // });
  //   }
  // }, [sessionId]);

  if (!user) {
    // This should ideally not happen due to UserGuard, but as a fallback
    return <Navigate to="/login" replace />;
  }

  if (!sessionId) {
    return (
      <div className="container mx-auto p-4">
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-500">Session ID is missing. Please ensure you have accessed this page correctly.</p>
            <Button onClick={() => window.history.back()} className="mt-4">Go Back</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    } else {
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error("Please select a file to upload.");
      return;
    }
    if (!sessionId) {
      toast.error("Session ID is missing. Cannot upload.");
      return;
    }

    setIsUploading(true);
    const uploadToastId = toast.loading(`Uploading ${selectedFile.name}...`);

    try {
      const response = await apiClient.upload_technician_file_v2({
        sessionId: sessionId, 
        file: selectedFile 
      });
      const result = await response.json(); // Assuming response.json() gives the FileUploadResponse model
      toast.success(`File "${result.filename}" uploaded successfully!`, {
        id: uploadToastId,
        description: `Path: ${result.gcs_path}`,
      });
      setSelectedFile(null); // Reset file input
      setUploadedFiles(prevFiles => [...prevFiles, { filename: result.filename, gcsPath: result.gcs_path }]);
    } catch (error: any) {
      console.error("Upload failed:", error);
      let errorMessage = "File upload failed. Please try again.";
      if (error.response && typeof error.response.json === 'function') {
        try {
          const errJson = await error.response.json();
          errorMessage = errJson.detail || errJson.message || errorMessage;
        } catch (parseError) {
          // Ignore parsing errors
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      toast.error(errorMessage, { id: uploadToastId });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="container mx-auto p-4 flex flex-col items-center">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Troubleshooting Session: {sessionId}</CardTitle>
          <CardDescription>
            Upload media files (images, videos) for this session. Logged in as: {user.email}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Select File
            </label>
            <Input
              id="file-upload"
              type="file"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"
              disabled={isUploading}
            />
            {selectedFile && <p className="text-xs mt-1">Selected: {selectedFile.name}</p>}
          </div>
          <Button
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            className="w-full"
          >
            {isUploading ? "Uploading..." : "Upload File"}
          </Button>
        </CardContent>
        <CardFooter className="flex-col items-start">
          {uploadedFiles.length > 0 && (
            <div className="mt-6 w-full">
              <h3 className="text-lg font-semibold mb-2">Uploaded Media:</h3>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                {uploadedFiles.map((file, index) => (
                  <li key={index}>
                    {file.filename} (<a href={`https://storage.googleapis.com/${FIREBASE_BUCKET_NAME}/${file.gcsPath.replace("gs://" + FIREBASE_BUCKET_NAME + "/", "")}`} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">View/Download</a>)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardFooter>
      </Card>
    </div>
  );
};

// Need to get FIREBASE_BUCKET_NAME for constructing download links.
// This is a client-side constant, if it's fixed.
const FIREBASE_BUCKET_NAME = "juniortechbot.firebasestorage.app";

export default TroubleshootingSessionPage;
