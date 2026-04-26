import React from "react";
import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser, firebaseApp } from "../app";
import { useUserRoles } from "../utils/useUserRoles"; 
import { getFirestore, collection, getDocs, query, where, orderBy, limit, startAfter, doc, updateDoc, deleteDoc, Timestamp, onSnapshot, getDoc } from "firebase/firestore";
import { getStorage, ref, uploadBytes, getDownloadURL } from "firebase/storage";
import { AdminGuard } from "../components/AdminGuard";
import { AdminLayout } from "../components/AdminLayout";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { Textarea } from "../extensions/shadcn/components/textarea.tsx";
import { Label } from "../extensions/shadcn/components/label.tsx";
import { Card } from "../extensions/shadcn/components/card.tsx";
import { Spinner } from "../components/Spinner";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../extensions/shadcn/components/dialog.tsx";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../extensions/shadcn/components/dropdown-menu.tsx";
import { Badge } from "../extensions/shadcn/components/badge.tsx";
import { Checkbox } from "../extensions/shadcn/components/checkbox.tsx";
import { toast } from "sonner";
import { apiClient } from "../app";
import { DocumentUpdateRequest } from "../apiclient/data-contracts.ts";
import { AdminEmptyState } from "../components/AdminEmptyState";
import { FileText, Upload, Trash2 } from "lucide-react";
import { KnowledgeBaseSelector } from '../components/KnowledgeBaseSelector';

interface Document {
  id: string;
  title?: string;
  description?: string;
  fileUrl: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  uploadedBy: string;
  company: string;
  organization?: string;
  createdAt: string;
  lastModified?: string;
  status: string;
  moderationStatus: string;
  isProcessed: boolean;
  tags?: string[];
}

// Helper function to check if a document is in a state that requires polling
const isDocumentProcessing = (status: string): boolean => {
  const s = status.toLowerCase();
  return s === "queued" || s === "processing" || s === "split" || s === "pending";
};

// Status filter options (Kept for reference, but the list below is the one being used in the component)
const statusOptions = [
  { value: "", label: "All Statuses" },
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "processed", label: "Processed" },
  { value: "failed", label: "Failed" },
  { value: "split", label: "Split" },
];

export default function AdminDocuments() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    title: "",
    description: "",
    tags: "",
    file: null as File | null
  });
  const [targetIndex, setTargetIndex] = useState('general');
  const [defaultNamespaceLoaded, setDefaultNamespaceLoaded] = useState(false);

  const [dialogKey, setDialogKey] = useState(0);

  // Handler for when default namespace is loaded
  const handleDefaultNamespaceLoad = (defaultNamespace: string) => {
    if (!defaultNamespaceLoaded) {
      console.log('[AdminDocuments] Setting default namespace to:', defaultNamespace);
      setTargetIndex(defaultNamespace);
      setDefaultNamespaceLoaded(true);
    }
  };


  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [lastDoc, setLastDoc] = useState<any>(null);
  const [hasMore, setHasMore] = useState(false);
  
  // Bulk delete state
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Document details modal state
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [editForm, setEditForm] = useState({
    title: "",
    description: "",
    tags: ""
  });
  const [updating, setUpdating] = useState(false);
  
  // Helper function to safely format status strings
  const formatStatus = (status?: string | null): string => {
    if (typeof status === 'string' && status.length > 0) {
      // Add 'queued' and 'split' to the formatting
      if (status.toLowerCase() === 'queued') return 'Queued';
      if (status.toLowerCase() === 'split') return 'Split';
      if (status.toLowerCase() === 'failed') return 'Failed';
      if (status.toLowerCase() === 'processed') return 'Processed';
      return status.charAt(0).toUpperCase() + status.slice(1);
    }
    return 'Unknown';
  };
  
  const { user, loading: userLoading } = useCurrentUser(); 
  const { 
    role, 
    company, 
    isSystemAdmin, 
    loading: rolesLoading 
  } = useUserRoles();
  
  const db = getFirestore(firebaseApp); // ← Add this line here

  
  
  // --- START: New Firestore Listener Logic ---
  useEffect(() => {
    // Identify documents that need real-time status updates.
    const documentsToWatch = documents.filter(doc => isDocumentProcessing(doc.status));

    // If there are no documents currently processing, we don't need to do anything.
    if (documentsToWatch.length === 0) {
      return;
    }

    // const db = getFirestore(firebaseApp);
    const unsubscribers: (() => void)[] = [];

    // Create a listener for each document that is processing.
    documentsToWatch.forEach(docToWatch => {
      const docRef = doc(db, "documents", docToWatch.id);
      
      const unsubscribe = onSnapshot(docRef, (updatedDocSnap) => {
        if (updatedDocSnap.exists()) {
          const updatedData = updatedDocSnap.data() as Document;

          // Update the specific document in our state array.
          setDocuments(currentDocs => {
            const index = currentDocs.findIndex(d => d.id === updatedDocSnap.id);
            if (index === -1) {
              // Should not happen if doc was in the list, but handle defensively.
              return currentDocs;
            }
            
            // Create a new array with the updated document.
            const newDocs = [...currentDocs];
            newDocs[index] = { ...newDocs[index], ...updatedData };
            return newDocs;
          });
        }
      }, (error) => {
        console.error(`Error listening to document ${docToWatch.id}:`, error);
        // We don't toast here to avoid spamming on transient network errors.
      });
      
      unsubscribers.push(unsubscribe);
    });

    // Return a cleanup function that will be called when the component
    // unmounts or when the `documents` dependency array changes.
    // This is crucial to prevent memory leaks.
    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [documents, db]); // Rerun this effect whenever the list of documents changes.
  // --- END: New Firestore Listener Logic ---
  
  // Function to fetch documents
  const fetchDocuments = useCallback(async (startAfterOffset: number = 0) => {
  if (rolesLoading) {
  console.log("AdminDocuments: fetchDocuments skipped, roles are still loading.");
  setLoading(false);
  return;
  }
  if (!isSystemAdmin && !company) {
  console.log("AdminDocuments: fetchDocuments skipped, Company Admin has no company context.");
  setDocuments([]);
  setHasMore(false);
  setLoading(false);
  return;
  }
  setLoading(true); 
  
    try {
      const queryParams: any = {
        limit: 10, 
        offset: startAfterOffset, 
      };
        
      if (statusFilter !== 'all') {
        queryParams.status = statusFilter;
      }
        
      if (company && !isSystemAdmin) {
        queryParams.company = company;       
        
      }
        
      if (searchTerm.trim()) { // Only add search if searchTerm is not empty
        queryParams.search = searchTerm.trim();
      }
        
      console.log("AdminDocuments: Attempting to fetch documents with params:", queryParams);
      const response = await apiClient.list_documents(queryParams);
        
      console.log("AdminDocuments: apiClient.list_documents response status:", response.status, "ok:", response.ok);

      if (response.ok) {
        const data = await response.json();
        console.log("AdminDocuments: apiClient.list_documents SUCCESS response data:", data);

        const fetchedDocs = Array.isArray(data?.documents) ? data.documents : [];
        // Add this mapping code right after it:
        const mappedDocs: Document[] = fetchedDocs.map((doc: any) => ({
          ...doc,
          // Provide default values for fields that might not exist in the API list response
          // but are required by the component's local `Document` interface.
          fileUrl: doc.fileUrl || '', 
          uploadedBy: doc.uploadedBy || 'N/A',
          moderationStatus: doc.moderationStatus || 'pending',
        }));

        if (startAfterOffset > 0) { 
          setDocuments(prev => [...prev, ...mappedDocs]); // Use mappedDocs here
        } else { 
          setDocuments(mappedDocs); // And use mappedDocs here for the initial set
        }

        // +++ START FIX: Override hasMore logic on the client-side +++
        // The backend's hasMore can be unreliable when search is used.
        // A more reliable client-side check is to see if the number of documents
        // returned is equal to the limit we requested. If it is, we assume there
        // might be more.
        const newHasMore = fetchedDocs.length === queryParams.limit;
        setHasMore(newHasMore);
        
        // --- Start Polling for new documents ---
        // THIS BLOCK IS NO LONGER NEEDED AND IS REMOVED
        // const processingDocs = mappedDocs.filter(doc => isDocumentProcessing(doc.status));
        // if (processingDocs.length > 0) {
        //     setIsPolling(true);
        // } else {
        //     setIsPolling(false);
        // }
        // -------------------------------------

        //newHasMore = data.pagination?.hasMore !== undefined 
        //                    ? data.pagination.hasMore 
        //                    : (fetchedDocs.length === queryParams.limit);
        //setHasMore(newHasMore);
        setLastDoc(startAfterOffset + fetchedDocs.length); 
        } else {
        let errorDetail = `API Error: Status ${response.status}`; // Default error detail
        try {
          // Attempt to parse error response only if there's a body
          if (response.body) {
            const errorData = await response.json() as { detail?: string };
            console.error("AdminDocuments: API Error response data:", errorData);
            errorDetail = errorData.detail || errorDetail;       
          } else {
            console.error("AdminDocuments: API Error response has no body.");
          }
        } catch (e) {
          console.error("AdminDocuments: Failed to parse error response JSON from API:", e);
        }
        console.error("AdminDocuments: API error fetching documents. Detail:", errorDetail);
        toast.error(`Error: ${errorDetail}`);
        if (startAfterOffset === 0) setDocuments([]);
        setHasMore(false);
        }
      } catch (error) {
      console.error("AdminDocuments: Unexpected error in fetchDocuments:", error);
      toast.error("An unexpected client-side error occurred while loading documents.");
      if (startAfterOffset === 0) setDocuments([]);
      setHasMore(false);
      } finally {
      setLoading(false);
      }
    }, [company, statusFilter, searchTerm, rolesLoading, isSystemAdmin, db]);
  
  // Initial load
    useEffect(() => {
      // This effect is primarily for the initial load based on user context
      // or when the fundamental context (like company affiliation) changes.
      if (!userLoading && !rolesLoading) {
      if (isSystemAdmin) { 
        fetchDocuments(0); // Initial fetch for system admin
      } else if (company) { 
        fetchDocuments(0); // Initial fetch for company admin with a company
      } else { 
        // Non-system admin, roles loaded, but no company affiliation found
        console.warn("AdminDocuments: User is not System Admin and no company is assigned.");
        setDocuments([]);
        setLoading(false);
        setHasMore(false);
        toast.error("No company affiliation found. Cannot list documents.");
      }
      } else {
      // Still waiting for user or role information to load, show spinner
      setLoading(true); 
      }
    }, [userLoading, rolesLoading, isSystemAdmin, company]);
    //}, [userLoading, rolesLoading, isSystemAdmin, company, fetchDocuments]);
  // Effect 2: Resets and refetches documents when filters or search term change.
    useEffect(() => {
      // We create a reference to avoid re-running this on every render.
      // The check for !loading prevents a refetch while one is already in progress.
      if (!loading) {
        fetchDocuments(0);
      }
    // This effect runs ONLY when the search or filter criteria change.
    }, [statusFilter, searchTerm]);

const loadDocumentDetails = async (documentId: string) => {
  // 1. Find the document in the existing state array.
  const existingDoc = documents.find(d => d.id === documentId);
  if (!existingDoc) {
    toast.error("Could not find the document in the list.");
    return;
  }

  try {
    // 2. Fetch the latest editable details from the API.
    const response = await apiClient.get_document({ docId: documentId });
    
    if (response.ok) {
      const freshDetails = await response.json(); // This is type DocumentResponse

      // 3. Merge the existing full data with the fresh details.
      const completeDocument: Document = {
        ...existingDoc, // Use the full object from the list as the base
        ...freshDetails, // Overwrite with the latest data from the API
      };
      
      setSelectedDocument(completeDocument);
      setEditForm({
        title: completeDocument.title || '',
        description: completeDocument.description || '',
        tags: completeDocument.tags ? completeDocument.tags.join(', ') : ''
      });
      setShowDetailsModal(true);

    } else {
      throw new Error('Failed to load document details');
    }
  } catch (error) {
    console.error('Error loading document details:', error);
    toast.error('Failed to load document details');
  }
};
  
  // Function to handle update document details
  const handleUpdateDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedDocument) return;
    
    try {
      setUpdating(true);
      
      // Prepare the update request
      const updateData: DocumentUpdateRequest = {
        title: editForm.title || undefined,
        description: editForm.description || undefined
      };
      
      // Handle tags (convert comma-separated string to array)
      if (editForm.tags) {
        updateData.tags = editForm.tags
          .split(',')
          .map(tag => tag.trim())
          .filter(tag => tag.length > 0);
      } else {
        updateData.tags = [];
      }
      
      // Call the API to update the document
      const response = await apiClient.update_document(
        { documentId: selectedDocument.id },
        updateData
      );
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Update failed');
      }
      
      // Update the document in the list
      setDocuments(prev => prev.map(doc => {
        if (doc.id === selectedDocument.id) {
          return {
            ...doc,
            title: editForm.title,
            description: editForm.description,
            tags: updateData.tags
          };
        }
        return doc;
      }));
      
      // Close the modal
      setShowDetailsModal(false);
      setSelectedDocument(null);
      
      toast.success('Document updated successfully');
    } catch (error) {
      console.error('Error updating document:', error);
      toast.error(`Failed to update document: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setUpdating(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!uploadForm.file || !uploadForm.title) {
      toast.error("Title and file are required");
      return;
    }
    
    try {
      setUploading(true);
      
      // Prepare form data for upload
      const formData = new FormData();
      formData.append('file', uploadForm.file);
      formData.append('title', uploadForm.title);
      formData.append('target_index', targetIndex); 
      
      if (uploadForm.description) {
        formData.append('description', uploadForm.description);
      }
      
      if (uploadForm.tags) {
        formData.append('tags', uploadForm.tags);
      } else {
        formData.append('tags', ""); // Explicitly set to empty string
      }
      
      // Use the API to upload the document
      const response = await apiClient.upload_document({
        file: uploadForm.file,
        title: uploadForm.title,
        description: uploadForm.description || null,
        tags: uploadForm.tags || null,
        target_index: targetIndex
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }
      
      // Reset form and close dialog
      setUploadForm({
        title: "",
        description: "",
        tags: "",
        file: null
      });
      setShowUploadDialog(false);
      
      // Refresh documents
      fetchDocuments();
      
      toast.success("Document uploaded successfully. Status updates will follow.");
    } catch (error) {
      console.error("Error uploading document:", error);
      toast.error(`Failed to upload document: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setUploading(false);
    }
  };

  // Function to handle document deletion
  const handleDeleteDocument = async (documentId: string) => {
    if (!confirm("Are you sure you want to delete this document? This action cannot be undone.")) {
      return;
    }
    
    try {
      // Call API to delete the document
      const response = await apiClient.delete_document({ documentId } as any);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Delete failed');
      }
      
      // Update state
      setDocuments(prev => prev.filter(doc => doc.id !== documentId));
      
      toast.success("Document deleted successfully");
    } catch (error) {
      console.error("Error deleting document:", error);
      toast.error(`Failed to delete document: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // NEW: Handle bulk delete
  const handleBulkDelete = async () => {
    if (selectedDocIds.size === 0) {
      toast.error("No documents selected");
      return;
    }

    if (!confirm(`Are you sure you want to delete ${selectedDocIds.size} document(s)? This action cannot be undone.`)) {
      return;
    }

    setIsDeleting(true);
    const BATCH_SIZE = 5; // Process 5 documents at a time
    const docIdsArray = Array.from(selectedDocIds);
    const totalDocs = docIdsArray.length;
    let processedCount = 0;
    let successCount = 0;
    let failCount = 0;
    const successfulIds = new Set<string>();

    try {
      // Process documents in batches
      for (let i = 0; i < docIdsArray.length; i += BATCH_SIZE) {
        const batch = docIdsArray.slice(i, i + BATCH_SIZE);
        const batchNumber = Math.floor(i / BATCH_SIZE) + 1;
        const totalBatches = Math.ceil(totalDocs / BATCH_SIZE);
        
        // Show progress toast
        toast.info(`Deleting batch ${batchNumber}/${totalBatches}...`, {
          id: 'bulk-delete-progress',
        });

        // Delete batch in parallel
        const batchPromises = batch.map(docId => 
          apiClient.delete_document({ docId } as any)
            .then(response => ({ docId, success: response.ok, response }))
            .catch(error => ({ docId, success: false, error }))
        );

        const batchResults = await Promise.allSettled(batchPromises);

        // Process batch results
        batchResults.forEach((result) => {
          processedCount++;
          if (result.status === 'fulfilled' && result.value.success) {
            successCount++;
            successfulIds.add(result.value.docId);
          } else {
            failCount++;
            const docId = result.status === 'fulfilled' ? result.value.docId : 'unknown';
            console.error(`Failed to delete document ${docId}`);
          }
        });
      }

      // Update state to remove successfully deleted documents
      if (successCount > 0) {
        setDocuments(prev => prev.filter(doc => !successfulIds.has(doc.id)));
        // Refetch documents to ensure the page is filled
        setTimeout(() => {
          fetchDocuments(0);
        }, 500);
      }
      
      setSelectedDocIds(new Set());

      // Dismiss progress toast
      toast.dismiss('bulk-delete-progress');

      // Show final result toast
      if (successCount > 0 && failCount === 0) {
        toast.success(`Successfully deleted ${successCount} document(s)`);
      } else if (successCount > 0 && failCount > 0) {
        toast.warning(`Deleted ${successCount} document(s), but ${failCount} failed`);
      } else {
        toast.error(`Failed to delete all ${failCount} document(s)`);
      }
    } catch (error) {
      console.error("Error during bulk delete:", error);
      toast.dismiss('bulk-delete-progress');
      toast.error("An error occurred during bulk delete");
    } finally {
      setIsDeleting(false);
    }
  };

  // NEW: Toggle document selection
  const toggleDocumentSelection = (docId: string) => {
    setSelectedDocIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return newSet;
    });
  };

  // NEW: Toggle select all
  const toggleSelectAll = () => {
    if (selectedDocIds.size === documents.length && documents.length > 0) {
      // Deselect all
      setSelectedDocIds(new Set());
    } else {
      // Select all
      setSelectedDocIds(new Set(documents.map(doc => doc.id)));
    }
  };

  // Function to handle search
  const handleSearch = () => {
    fetchDocuments();
  };

  // NEW: Function to handle viewing a document
  const handleViewDocument = async (documentId: string) => {
    try {
      toast.info("Generating secure URL...");
      // Call the API to get the signed URL
      const response = await apiClient.get_secure_document_url({ documentId: documentId });

      if (response.ok) {
        const { signed_url } = await response.json();
        // Open the secure URL in a new tab
        window.open(signed_url, "_blank");
        toast.success("Secure URL generated successfully.");
      } else {
        const errorData = await response.json() as { detail?: string };
        throw new Error(errorData.detail || "Failed to generate secure URL");
      }
    } catch (error) {
      console.error("Error generating secure document URL:", error);
      toast.error(`Failed to view document: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Function to handle load more
  const handleLoadMore = () => {              
    if (hasMore && !loading) {              
      fetchDocuments(lastDoc); // lastDoc holds the offset for the next page              
    }             
  };


  return (
    <AdminGuard>
      <AdminLayout activeTab="documents">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Document Management</h1>
              <p className="text-muted-foreground">
                Upload and manage documents for the knowledge base
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button onClick={() => navigate("/bulk-import")} variant="outline">
                <Upload className="mr-2 h-4 w-4" />
                Manage Historic records (CSV)
              </Button>
              <Button onClick={() => navigate("/zip-import")} variant="outline">
                <Upload className="mr-2 h-4 w-4" />
                Zip Import
              </Button>
              <Button onClick={() => {
                setShowUploadDialog(true);
                setDefaultNamespaceLoaded(false); // Reset flag to allow fresh namespace load
                setDialogKey(prev => prev + 1); // Increment to force fresh mount
              }}>
                Upload Document
              </Button>
            </div>
          </div>
          
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <div className="flex-1">
              <Input 
                placeholder="Search documents..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">
                  {statusFilter === 'all' ? 'All Statuses' : 
                   statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1)}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setStatusFilter('all')}>All Statuses</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('active')}>Active</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('processing')}>Processing</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('archived')}>Archived</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('flagged')}>Flagged</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setStatusFilter('rejected')}>Rejected</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Bulk actions bar */}
          {documents.length > 0 && (
            <div className="flex items-center justify-between gap-4 p-4 bg-muted/50 rounded-lg border border-border">
              <div className="flex items-center gap-3">
                <Checkbox
                  id="select-all"
                  checked={selectedDocIds.size === documents.length && documents.length > 0}
                  onCheckedChange={toggleSelectAll}
                />
                <Label htmlFor="select-all" className="cursor-pointer">
                  Select All ({selectedDocIds.size} / {documents.length})
                </Label>
              </div>

              {selectedDocIds.size > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkDelete}
                  disabled={isDeleting}
                >
                  {isDeleting ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete Selected ({selectedDocIds.size})
                    </>
                  )}
                </Button>
              )}
            </div>
          )}
          
          {/* Document List */}
          <div className="space-y-4">
            {/* 1. Initial Loading Spinner */}
            {loading && documents.length === 0 && (
              <div className="flex justify-center items-center h-64">
                <Spinner size="lg" />
              </div>
            )}

            {/* 2. Empty State Display */}
            {!loading && documents.length === 0 && (
              <AdminEmptyState
                title={searchTerm ? "No documents match your search" : statusFilter !== "all" ? `No ${statusFilter} documents found` : "No documents found"}
                description={searchTerm ? `No results found for "${searchTerm}".` : statusFilter !== "all" ? "Try changing the status filter." : isSystemAdmin ? "Upload your first document to start building your knowledge base." : "Contact your system administrator if you believe this is an error."}
                icon={<FileText className="h-6 w-6" />}
                actionLabel={searchTerm ? "Clear search" : statusFilter !== "all" ? "Show all documents" : isSystemAdmin ? "Upload Document" : undefined}
                onAction={searchTerm ? () => setSearchTerm("") : statusFilter !== "all" ? () => setStatusFilter("all") : isSystemAdmin ? () => {
                  setShowUploadDialog(true);
                  setDefaultNamespaceLoaded(false);
                } : undefined}
              />
            )}

            {/* 3. Document List Display */}
            {documents.length > 0 && (
              <div className="grid gap-4">
                {documents.map(doc => {
                  return (
                    <Card key={doc.id} className="p-4">
                      <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
                        <div className="flex flex-1 gap-4 items-start">
                          {/* Checkbox for selection */}
                          <div className="flex items-center pt-1">
                            <Checkbox
                              id={`select-${doc.id}`}
                              checked={selectedDocIds.has(doc.id)}
                              onCheckedChange={() => toggleDocumentSelection(doc.id)}
                            />
                          </div>

                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5 text-primary">
                              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                              <polyline points="14 2 14 8 20 8"/>
                            </svg>
                          </div>
                          <div className="flex-1">
                            <h3 className="font-semibold">{doc.title || doc.fileName}</h3>
                            {doc.description && (
                              <p className="text-sm text-muted-foreground line-clamp-2">{doc.description}</p>
                            )}
                            <div className="mt-2 flex flex-wrap gap-2">
                              {doc.tags && doc.tags.map((tag: string, index: number) => (
                                <Badge key={index} variant="outline">{tag}</Badge>
                              ))}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>
                                {new Date(doc.createdAt).toLocaleDateString()} {new Date(doc.createdAt).toLocaleTimeString()}
                              </span>
                              <span className="border-l border-border pl-2">{doc.fileName}</span>
                              <span className="border-l border-border pl-2">
                                {(doc.fileSize / 1024 / 1024).toFixed(2)} MB
                              </span>
                              {isSystemAdmin && doc.company && (
                                <span className="border-l border-border pl-2">{doc.company}</span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-row md:flex-col items-center md:items-end gap-2 w-full md:w-auto">
                          <div className="flex gap-1">
                            <Badge className={`${doc.status === 'active' ? 'bg-green-500/20 text-green-600 hover:bg-green-500/30' : 
                                               doc.status === 'processing' || doc.status === 'queued' || doc.status === 'split' ? 'bg-blue-500/20 text-blue-600 hover:bg-blue-500/30' : 
                                               doc.status === 'flagged' ? 'bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30' : 
                                               doc.status === 'rejected' || doc.status === 'failed' ? 'bg-red-500/20 text-red-600 hover:bg-red-500/30' : 
                                               'bg-gray-500/20 text-gray-600 hover:bg-gray-500/30'}`}>
                              {formatStatus(doc.status)}
                            </Badge>
                            <Badge className={`${doc.moderationStatus === 'approved' ? 'bg-green-500/20 text-green-600 hover:bg-green-500/30' : 
                                               doc.moderationStatus === 'rejected' ? 'bg-red-500/20 text-red-600 hover:bg-red-500/30' : 
                                               'bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30'}`}>
                              {formatStatus(doc.moderationStatus)}
                            </Badge>
                            {doc.isProcessed ? (
                              <Badge className="bg-green-500/20 text-green-600 hover:bg-green-500/30">
                                Processed
                              </Badge>
                            ) : (
                              <Badge className="bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30">
                                Unprocessed
                              </Badge>
                            )}
                          </div>
                          <div className="flex gap-2">
                            <Button 
                              size="sm" 
                              variant="outline" 
                              onClick={() => handleViewDocument(doc.id)}>
                              View
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => handleDeleteDocument(doc.id)}>
                              Delete
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => loadDocumentDetails(doc.id)}>
                              Edit
                            </Button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* 4. "Loading More" Spinner */}
            {loading && documents.length > 0 && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}

            {/* 5. "Load More" Button */}
            {!loading && hasMore && (
              <div className="flex justify-center pt-4">
                <Button variant="outline" onClick={handleLoadMore}>
                  Load More
                </Button>
              </div>
            )}
          </div>
        </div>
      </AdminLayout>
      
      {/* Upload Dialog */}
      <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
            <DialogDescription>
              Add a new document to the knowledge base
            </DialogDescription>
          </DialogHeader>
          
          <form onSubmit={handleFileUpload} className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="target_index">Knowledge Base Type *</Label>
              <KnowledgeBaseSelector
                key={dialogKey} // Use the counter instead
                value={targetIndex}
                onChange={setTargetIndex}
                onDefaultNamespaceLoad={handleDefaultNamespaceLoad}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input 
                id="title" 
                required 
                value={uploadForm.title}
                onChange={(e) => setUploadForm({...uploadForm, title: e.target.value})}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea 
                id="description"
                value={uploadForm.description}
                onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                rows={3}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="tags">Tags (comma separated)</Label>
              <Input 
                id="tags"
                value={uploadForm.tags}
                onChange={(e) => setUploadForm({...uploadForm, tags: e.target.value})}
                placeholder="tag1, tag2, tag3"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="file">Document File *</Label>
              <Input 
                id="file"
                type="file"
                required
                onChange={(e) => setUploadForm({
                  ...uploadForm, 
                  file: e.target.files ? e.target.files[0] : null
                })}
              />
              <p className="text-xs text-muted-foreground">
                Supported formats: PDF, DOCX, PPTX, CSV, XLS, XLSX, JPG, PNG
              </p>
            </div>
            
            <DialogFooter className="pt-4">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => setShowUploadDialog(false)}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={uploading}>
                {uploading ? <><Spinner className="mr-2" size="sm" /> Uploading...</> : 'Upload'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      
      {/* Document Details Modal */}
      <Dialog open={showDetailsModal} onOpenChange={setShowDetailsModal}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Document Details</DialogTitle>
            <DialogDescription>
              View and edit document metadata
            </DialogDescription>
          </DialogHeader>
          
          {selectedDocument && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge 
                  className={`${selectedDocument.status === 'active' ? 'bg-green-500/20 text-green-600' : 
                  selectedDocument.status === 'processing' || selectedDocument.status === 'queued' || selectedDocument.status === 'split' ? 'bg-blue-500/20 text-blue-600' : 
                  selectedDocument.status === 'flagged' ? 'bg-yellow-500/20 text-yellow-600' : 
                  selectedDocument.status === 'rejected' || selectedDocument.status === 'failed' ? 'bg-red-500/20 text-red-600' : 
                  'bg-gray-500/20 text-gray-600'}`}
                >
                  {formatStatus(selectedDocument.status)}
                </Badge>
                
                <Badge 
                  className={`${selectedDocument.moderationStatus === 'approved' ? 'bg-green-500/20 text-green-600' : 
                  selectedDocument.moderationStatus === 'rejected' ? 'bg-red-500/20 text-red-600' : 
                  'bg-yellow-500/20 text-yellow-600'}`}
                >
                  {formatStatus(selectedDocument.moderationStatus)}
                </Badge>
                
                {selectedDocument.isProcessed ? (
                  <Badge className="bg-green-500/20 text-green-600">
                    Processed
                  </Badge>
                ) : (
                  <Badge className="bg-yellow-500/20 text-yellow-600">
                    Unprocessed
                  </Badge>
                )}
              </div>
              
              <div className="text-sm">
                <p>
                  <span className="font-semibold">File:</span> {selectedDocument.fileName}
                </p>
                <p>
                  <span className="font-semibold">Size:</span> {(selectedDocument.fileSize / 1024 / 1024).toFixed(2)} MB
                </p>
                <p>
                  <span className="font-semibold">Uploaded:</span> {new Date(selectedDocument.createdAt).toLocaleString()}
                </p>
                {selectedDocument.lastModified && (
                  <p>
                    <span className="font-semibold">Last Modified:</span> {new Date(selectedDocument.lastModified).toLocaleString()}
                  </p>
                )}
              </div>
              
              <form onSubmit={handleUpdateDocument}>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="edit-title">Title</Label>
                    <Input 
                      id="edit-title" 
                      value={editForm.title}
                      onChange={(e) => setEditForm({...editForm, title: e.target.value})}
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="edit-description">Description</Label>
                    <Textarea 
                      id="edit-description"
                      value={editForm.description}
                      onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                      rows={3}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="edit-tags">Tags (comma separated)</Label>
                    <Input 
                      id="edit-tags"
                      value={editForm.tags}
                      onChange={(e) => setEditForm({...editForm, tags: e.target.value})}
                      placeholder="tag1, tag2, tag3"
                    />
                  </div>
                  
                  <DialogFooter>
                    <Button 
                      type="button" 
                      variant="outline" 
                      onClick={() => setShowDetailsModal(false)}
                      disabled={updating}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={updating}>
                      {updating ? <><Spinner className="mr-2" size="sm" /> Updating...</> : 'Save Changes'}
                    </Button>
                  </DialogFooter>
                </div>
              </form>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AdminGuard>
  );
}
