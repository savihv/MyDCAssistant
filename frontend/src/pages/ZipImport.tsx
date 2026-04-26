import React, { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { apiClient } from "../app";
import { Button } from "../components/Button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "../extensions/shadcn/components/card";
import { useUserGuardContext } from "../app";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../extensions/shadcn/components/table";
import { DocumentResponse } from "../apiclient/data-contracts";
import { Badge } from "../extensions/shadcn/components/badge";
import { Label } from "../extensions/shadcn/components/label";
import { Input } from "../extensions/shadcn/components/input";
import { Loader2, ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  collection,
  query,
  where,
  onSnapshot,
  getFirestore,
} from "firebase/firestore";
import { firebaseApp } from "../app";
// Import the KnowledgeBaseSelector component
import { KnowledgeBaseSelector } from "../components/KnowledgeBaseSelector";

const db = getFirestore(firebaseApp);

type DocumentStatus =
  | "pending"
  | "processing"
  | "processed"
  | "failed"
  | "queued"
  | "completed"; // Added 'completed' for completeness

export default function ZipImportPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastJobId, setLastJobId] = useState<string | null>(null);

  // New state for the selected knowledge base ID (target_index)
  const [targetIndex, setTargetIndex] = useState<string>('general');
  const [selectorKey, setSelectorKey] = useState(0);

  // Initialize state from session storage for persistence on refresh
  const [companyId, setCompanyId] = useState<string | null>(() =>
    sessionStorage.getItem("zipImportCompanyId"),
  );
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const { user } = useUserGuardContext();

  // --- Effect 1: Fetch and Persist Company ID ---
  useEffect(() => {
    const fetchCompanyId = async () => {
      if (user) {
        try {
          const tokenResult = await user.getIdTokenResult();
          const tokenCompany = tokenResult.claims.company as string;
          const cachedCompany = sessionStorage.getItem("zipImportCompanyId");
          
          if (!tokenCompany) {
            console.error("[ZipImport] No company claim in token");
            toast.error("No company assigned to your account. Please contact admin.");
            return;
          }
          
          // Validate: Does cached company match current user's token?
          if (cachedCompany !== tokenCompany) {
            console.log(
              `[ZipImport] Company mismatch detected. Cached: ${cachedCompany}, Token: ${tokenCompany}. Updating...`
            );
            sessionStorage.setItem("zipImportCompanyId", tokenCompany);
          } else {
            console.log(`[ZipImport] Using validated company: ${tokenCompany}`);
          }
          
          setCompanyId(tokenCompany); // Always use token as source of truth
        } catch (err) {
          console.error("Failed to retrieve user authentication details:", err);
          toast.error("Failed to retrieve user authentication details.");
        }
      }
    };
    fetchCompanyId();
  }, [user, companyId]);

  // Effect: Refresh KnowledgeBaseSelector when window regains focus
  useEffect(() => {
    const handleFocus = () => {
      console.log('[ZipImport] Window focused, refreshing namespace selector');
      setSelectorKey(prev => prev + 1);
    };
    
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  // --- Effect 2: Real-time Firestore Listener for Job Status ---
  useEffect(() => {
    // If there's no job ID or company ID, don't set up the listener.
    if (!lastJobId || !companyId) {
      return;
    }

    console.log(
      `Setting up real-time listener for jobId: ${lastJobId} in company: ${companyId}`,
    );

    // Create a query against the 'documents' collection.
    const q = query(
      collection(db, "documents"),
      where("jobId", "==", lastJobId),
      where("company", "==", companyId),
    );

    // onSnapshot returns an unsubscribe function.
    const unsubscribe = onSnapshot(
      q,
      (querySnapshot) => {
        const updatedDocs: DocumentResponse[] = [];
        let allProcessed = true;

        querySnapshot.forEach((doc) => {
          const data = doc.data() as DocumentResponse;
          // Ensure we have a valid status and id
          const docWithId = { ...data, id: doc.id };
          updatedDocs.push(docWithId);

          // Check if document is still being processed (positive check for active statuses)
          if (
            docWithId.status === "queued" ||
            docWithId.status === "processing" ||
            docWithId.status === "pending"
          ) {
            allProcessed = false;
          }
        });

        // Sort documents by file name for a consistent display order
        updatedDocs.sort((a, b) => a.fileName.localeCompare(b.fileName));
        setDocuments(updatedDocs);
        setIsProcessing(true); // Keep the UI in processing mode

        console.log("Firestore listener updated documents:", updatedDocs);

        // If all documents are processed, we can stop showing the main progress bar.
        if (allProcessed && updatedDocs.length > 0) {
          console.log("All documents have been processed.");
          setIsProcessing(false); // Update to finished state
        }
      },
      (err) => {
        // Handle listener errors
        console.error("Firestore listener error:", err);
        setError(
          "Error listening for real-time updates. Please refresh the page.",
        );
      },
    );

    // Cleanup: This function is called when the component unmounts
    // or when lastJobId or companyId changes.
    return () => {
      console.log(`Cleaning up listener for jobId: ${lastJobId}`);
      unsubscribe();
    };
  }, [lastJobId, companyId]); // Re-run this effect if job ID or company ID changes.


  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const selectedFile = event.target.files[0];
      if (
        selectedFile.type !== "application/zip" &&
        selectedFile.type !== "application/x-zip-compressed"
      ) {
        toast.error("Invalid file type. Please upload a .zip file.");
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setError(null);
      // Clear previous job data when a new file is selected
      setDocuments([]);
      setLastJobId(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.warning("Please select a file to upload.");
      return;
    }
    if (!companyId) {
      toast.error(
        "Cannot upload: Company ID is missing. Please try refreshing the page.",
      );
      return;
    }
    // New check: Ensure a knowledge base is selected
    if (!targetIndex || targetIndex.trim() === '') {
      toast.warning("Please select a Knowledge Base for the imported documents.");
      return;
    }

    setIsLoading(true);
    const toastId = toast.loading("Uploading zip file...");

    try {
      // Pass the selected targetIndex to the backend
      const response = await apiClient.upload_zip_archive({
        companyId: companyId,
        file: file,
        target_index: targetIndex, // <-- TARGET_INDEX ADDED HERE
      });
      const result = await response.json();

      if (response.ok) {
        const docCount = result.documents?.length || 0;
        toast.success(
          `Upload accepted! Processing ${docCount} files into index "${targetIndex}"...`,
          {
            id: toastId,
            duration: 5000,
          },
        );

        const currentJobId = result.job_id;
        setLastJobId(currentJobId);
        sessionStorage.setItem("zipUploadJobId", currentJobId);

        // Initialize documents with the response (should contain initial statuses like 'queued')
        if (result.documents) {
          setDocuments(result.documents);
        }

        setFile(null); // Clears the file from React state
        if (fileInputRef.current) {
          fileInputRef.current.value = ""; // Resets the actual file input element
        }
        setTargetIndex('general');
      } else {
        const errorData = result;
        const errorMessage =
          (errorData as any).detail || "An unknown server error occurred.";
        throw new Error(errorMessage);
      }
    } catch (uploadError: any) {
      toast.error(`Upload failed: ${uploadError.message}`, { id: toastId });
    } finally {
      setIsLoading(false);
    }
  };

  const getBadgeVariant = (status: DocumentStatus) => {
    const normalizedStatus = status ? status.toLowerCase() : "outline"; // Handle null/undefined status

    switch (normalizedStatus) {
      case "processed":
      case "completed":
        return "default";
      case "failed":
        return "destructive";
      case "processing":
        return "secondary";
      case "queued":
        return "outline";
      case "pending":
      default:
        return "outline";
    }
  };

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      <header className="flex-shrink-0 border-b border-gray-200 dark:border-gray-700">
        <div className="px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">Knowledge Base Management</h1>
          <Button
            variant="outline"
            onClick={() => navigate("/admin-documents")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Go back to Documents
          </Button>
        </div>
      </header>
      <main className="flex-1 overflow-auto p-6">
        <Card className="max-w-4xl mx-auto">
          <CardHeader>
            <CardTitle>Bulk Import via .zip</CardTitle>
            <CardDescription>
              Upload a .zip archive containing multiple unstructured files (PDFs,
              DOCX, images) to populate the knowledge base.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              {/* Knowledge Base Selector UI */}
              <div className="grid gap-2">
                <Label htmlFor="knowledge-base"> Knowledge Base Type</Label>
                <KnowledgeBaseSelector
                  key={selectorKey}
                  value={targetIndex}
                  onChange={setTargetIndex}
                  disabled={isLoading}
                />
              </div>

              {/* Zip File Input */}
              <div className="grid gap-2">
                <Label htmlFor="zip-file">Zip Archive</Label>
                <Input
                  ref={fileInputRef}
                  id="zip-file"
                  type="file"
                  accept=".zip"
                  onChange={handleFileChange}
                  className="file:text-foreground"
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
            </div>
          </CardContent>
          <CardFooter>
            <Button
              onClick={handleUpload}
              // Disable if no file, loading, no companyId, or no targetIndex
              disabled={!file || isLoading || !companyId || !targetIndex}
              className="w-full sm:w-auto"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading...
                </>
              ) : (
                "Upload and Process"
              )}
            </Button>
          </CardFooter>
        </Card>

        {isProcessing && documents.length > 0 && (
          <Card className="max-w-4xl mx-auto mt-6">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg font-medium">
                File Processing Status
              </CardTitle>
              {isProcessing && (
                <div className="flex items-center text-sm text-blue-500">
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Updating...
                </div>
              )}
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Filename</TableHead>
                    <TableHead className="text-right w-[150px]">
                      Status
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="max-w-xs truncate">
                        {doc.fileName}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant={getBadgeVariant(
                            doc.status as DocumentStatus,
                          )}
                        >
                          {doc.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                  {/* Show a message if documents array is empty but we are polling (waiting for first fetch) */}
                  {isProcessing && documents.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center text-gray-500 py-4"
                      >
                        Waiting for document list...
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
