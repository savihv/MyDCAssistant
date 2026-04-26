


import React, { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KnowledgeSearch } from "./KnowledgeSearch";
import { Troubleshoot } from "./Troubleshoot";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Toaster, toast } from "sonner";
import { useDropzone } from "react-dropzone";
import { apiClient } from "app";
import { TechnicianReportsList } from "components/TechnicianReportsList";


const ExpertSubmissionForm = () => {
  const [title, setTitle] = useState("");
  const [explanation, setExplanation] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prevFiles) => [...prevFiles, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".jpeg", ".jpg", ".png"],
      "audio/*": [".mp3", ".wav", "audio/mpeg"],
      "video/*": [".mp4", ".mov", ".avi", ".quicktime"],
      "application/*": [".pdf", ".doc", ".txt", ".xlsx"],
    },
  });

  const removeFile = (fileName: string) => {
    setFiles(files.filter((file) => file.name !== fileName));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!title.trim() || !explanation.trim() || files.length === 0) {
      toast.error("Title, explanation, and at least one file are required.");
      return;
    }

    setIsSubmitting(true);
    toast.loading("Submitting knowledge entry...");

    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("explanation", explanation);
      files.forEach((file) => {
        formData.append("files", file);
      });

      await apiClient.add_expert_entry_to_knowledge_base(formData as any);

      toast.success("Knowledge entry submitted successfully!");
      setTitle("");
      setExplanation("");
      setFiles([]);
    } catch (error) {
      console.error("Submission failed:", error);
      const errorMessage = (error as any)?.response?.data?.detail || "An unexpected error occurred.";
      toast.error(`Submission failed: ${errorMessage}`);
    } finally {
      setIsSubmitting(false);
      toast.dismiss();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit an Expert Tip</CardTitle>
        <CardDescription>
          Share your knowledge with the team. Your submission will be added
          to the knowledge base.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="title" className="text-lg font-semibold">
              Title
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., How to Recalibrate the XYZ Sensor"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="explanation" className="text-lg font-semibold">
              Explanation
            </Label>
            <Textarea
              id="explanation"
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="Provide a detailed step-by-step guide, common symptoms, and solutions..."
              className="min-h-[150px]"
              required
            />
          </div>

          <div className="space-y-2">
            <Label className="text-lg font-semibold">
              Supporting Files (Images/Audio)
            </Label>
            <div
              {...getRootProps()}
              className={`p-8 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors
                ${isDragActive ? "border-blue-500 bg-gray-700" : "border-gray-600 hover:border-gray-500"}
              `}
            >
              <input {...getInputProps()} />
              <p>Drag & drop files here, or click to select files</p>
              <em className="text-sm text-gray-500">(Images and audio files are accepted)</em>
            </div>
          </div>
          
          {files.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold">Selected files:</h3>
              <ul className="space-y-2">
                {files.map((file, index) => (
                  <li
                    key={index}
                    className="flex items-center justify-between bg-gray-700 p-2 rounded-md"
                  >
                    <span className="text-sm truncate pr-4">{file.name}</span>
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
            className="w-full font-bold text-lg py-3"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Submitting..." : "Submit to Knowledge Base"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};


export default function TechnicianDashboard() {
  const navigate = useNavigate();
  return (
    <Tabs defaultValue="session" className="h-full space-y-6">
      <div className="flex items-center justify-between">
        <TabsList>
          <TabsTrigger value="session" className="relative">
            Current Session
          </TabsTrigger>
          <TabsTrigger value="search">Knowledge Base</TabsTrigger>
          <TabsTrigger value="submit">Submit Expert Tip</TabsTrigger>
          {/* --- FIX START: Add the "My Reports" tab --- */}
          <TabsTrigger value="reports">My Reports</TabsTrigger>
          {/* --- FIX END --- */}
        </TabsList>
      </div>
      <TabsContent value="session" className="border-none p-0 outline-none">
        <Troubleshoot />
      </TabsContent>
      <TabsContent value="search" className="border-none p-0 outline-none">
        <Card>
          <CardHeader>
            <CardTitle>Search Knowledge Base</CardTitle>
            <CardDescription>
              Search across official documents, past troubleshooting sessions,
              and expert tips.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <KnowledgeSearch />
          </CardContent>
        </Card>
      </TabsContent>
      <TabsContent value="submit" className="border-none p-0 outline-none">
        <ExpertSubmissionForm />
      </TabsContent>
      {/* --- FIX START: Add the content panel for "My Reports" --- */}
      <TabsContent value="reports" className="border-none p-0 outline-none">
        <TechnicianReportsList />
      </TabsContent>
      {/* --- FIX END --- */}
    </Tabs>
  );
}
