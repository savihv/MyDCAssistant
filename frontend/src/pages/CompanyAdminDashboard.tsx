import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { API_URL, auth } from "../app";
import { useCurrentUser } from "../app";
import { useUserRoles } from "../utils/useUserRoles";
import { AdminLayout } from "../components/AdminLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "../extensions/shadcn/components/card";
import { Users, FileText, MessageSquare, Search, Percent, Upload } from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { UserManagement } from '../components/UserManagement';
import { Spinner } from "../components/Spinner";
import { AdminEmptyState } from "../components/AdminEmptyState";
import { apiClient } from "../app";
import { BodyUploadDocument } from "../apiclient/data-contracts";
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager";
import { toast } from "sonner";
import { Button } from "../components/Button";
import { Progress } from "../extensions/shadcn/components/progress";
import { getRoutePath, navigateSafely } from "../utils/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "../extensions/shadcn/components/dialog";
import { Input } from "../extensions/shadcn/components/input";
import { Label } from "../extensions/shadcn/components/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../extensions/shadcn/components/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../extensions/shadcn/components/tabs";
import {
  getFirestore,
  collection,
  query,
  where,
  onSnapshot,
  doc,      // <-- ADD THIS
  updateDoc 
} from "firebase/firestore";
import { firebaseApp } from "../app";

import { useUserGuardContext} from "../app/auth"; 
import ConstraintManagement from "./ConstraintManagement";

// --- New Interface for Expert Tips ---
interface ExpertTip {
  id: string;
  title: string;
  description: string;
  company: string;
  technicianId: string;
  technicianName: string;
  status: "pending_review" | "approved" | "rejected" | "deleted";
  mediaUrls: string[];
  audioUrl: string | null;
  createdAt: any; // Using 'any' for Firestore Timestamps is common
  isAddedToKnowledgeBase: boolean;
}


const ExpertTipsManagement = () => {
  // CORRECT: Destructure 'user' and 'company' separately
  const { user } = useUserGuardContext(); // This gets the user object.
  const { company } = useUserRoles();      // THIS IS THE FIX: Get company from the correct hook.

  const [pendingTips, setPendingTips] = useState<ExpertTip[]>([]);
  const [approvedTips, setApprovedTips] = useState<ExpertTip[]>([]);
  const [deletedTips, setDeletedTips] = useState<ExpertTip[]>([]); // <-- ADD THIS LINE
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // CORRECT: Check for 'user' and 'company' directly
    if (!user || !company) {
      setIsLoading(false);
      return;
    }

    const db = getFirestore(firebaseApp);
    const tipsCollection = collection(db, "expert_tips");

    // Listener for pending tips with the correct company filter
    const qPending = query(
      tipsCollection,
      where("status", "==", "pending_review"),
      where("company", "==", company) // Use the 'company' variable
    );
    const unsubPending = onSnapshot(
      qPending,
      (snap) => {
        setPendingTips(
          snap.docs.map((doc) => ({ id: doc.id, ...doc.data() } as ExpertTip))
        );
        setIsLoading(false);
      },
      (error) => {
        console.error("Error fetching pending tips:", error);
        toast.error("Failed to load pending tips.");
        setIsLoading(false);
      }
    );

    // Listener for approved tips with the correct company filter
    const qApproved = query(
      tipsCollection,
      where("status", "==", "approved"),
      where("company", "==", company) // Use the 'company' variable
    );
    const unsubApproved = onSnapshot(
      qApproved,
      (snap) => {
        setApprovedTips(
          snap.docs.map((doc) => ({ id: doc.id, ...doc.data() } as ExpertTip))
        );
      },
      (error) => {
        console.error("Error fetching approved tips:", error);
        toast.error("Failed to load approved tips.");
      }
    );
    // --- ADD THIS NEW LISTENER FOR DELETED TIPS ---
    const qDeleted = query(
      tipsCollection,
      where("status", "in", ["deleted", "rejected"]),
      where("company", "==", company) // Or "company", whichever is now correct
    );

    const unsubDeleted = onSnapshot(qDeleted, (snap) => {
      setDeletedTips(
        snap.docs.map((doc) => ({ id: doc.id, ...doc.data() } as ExpertTip))
      );
    }, (error) => {
      console.error("Error fetching deleted tips:", error);
      toast.error("Failed to load deleted tips.");
    });
    // --- END OF NEW LISTENER ---

    return () => {
      unsubPending();
      unsubApproved();
      unsubDeleted();
    };
  }, [user, company]); // Add 'user' and 'company' to the dependency array

  // ... (The rest of the handleApprove, handleReject, handleDelete, and JSX remains exactly the same)

  // Inside your component
  const [openingMedia, setOpeningMedia] = useState<string | null>(null);

  const handleAdminViewMedia = useCallback(
    async (tip: ExpertTip, mediaUrl: string, mediaIndex: number) => {
      // Use a unique key to show the spinner only on the clicked item
      const loadingKey = `${tip.id}-${mediaIndex}`;
      setOpeningMedia(loadingKey);
      const toastId = toast.loading("Generating secure link...");
      
      try {
        const token = await auth.getAuthToken();
        if (!token) {
          throw new Error("Authentication failed: No token available.");
        }
  
        // This calls the EXACT same endpoint as the technician's page.
        // The backend will handle the authorization check.
        const response = await fetch(`${API_URL}/expert-tips-media/${tip.id}`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });
  
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "An unexpected server error occurred." }));
          throw new Error(errorData.detail || `Request failed: ${response.statusText}`);
        }
  
        const data = await response.json();
        // The endpoint returns all secure URLs for the tip
        const secureUrlToOpen = data.secure_urls?.[mediaIndex];
  
        if (!secureUrlToOpen) {
          throw new Error("A secure link for this specific file could not be generated.");
        }
  
        window.open(secureUrlToOpen, "_blank", "noopener,noreferrer");
        toast.success("Secure link generated successfully!", { id: toastId });
      } catch (error) {
        console.error("Error opening media:", error);
        toast.error((error as Error).message || "Could not open file.", { id: toastId });
      } finally {
        setOpeningMedia(null);
      }
    },
    [], // No dependencies needed
  );
  const handleApprove = async (tipId: string, title: string) => {
    toast.info(`Approving tip: "${title}"...`);
    try {
      const response = await apiClient.approve_expert_tip({ document_id: tipId });
      toast.success(`"${title}" approved and added to Knowledge Base.`);
    } catch (error) {
      console.error("Approval failed:", error);
      toast.error(`Failed to approve "${title}".`);
    }
  };

  const handleReject = async (tipId: string, title: string) => {
    toast.info(`Rejecting tip: "${title}"...`);
    try {
      const response = await apiClient.reject_expert_tip({ document_id: tipId });
      toast.success(`"${title}" has been rejected.`);
    } catch (error) {
      console.error("Rejection failed:", error);
      toast.error(`Failed to reject "${title}".`);
    }
  };

  const handleDelete = async (tipId: string, title: string) => {
    if (
      !window.confirm(
        `Are you sure you want to permanently delete "${title}" from the knowledge base? This action cannot be undone.`
      )
    ) {
      return;
    }
    toast.info(`Deleting "${title}" from knowledge base...`);
    try {
      const response = await apiClient.delete_expert_tip_from_knowledge_base({
        document_id: tipId,
      });
      toast.success(`"${title}" successfully deleted.`);
    } catch (error) {
      console.error("Deletion failed:", error);
      toast.error(`Failed to delete "${title}".`);
    }
  };

  const handleRestore = async (tipId: string) => {
    // 1. Create the loading toast AND capture its ID.
    const toastId = toast.loading("Restoring tip...");
  
    try {
      const db = getFirestore(firebaseApp);
      const tipRef = doc(db, "expert_tips", tipId);
  
      // Set the status back to pending_review
      await updateDoc(tipRef, {
        status: "pending_review"
      });
      
      // 2. On SUCCESS, update the original toast using its ID.
      toast.success("Tip restored successfully and moved to Pending Review.", {
        id: toastId
      });
  
    } catch (error) {
      console.error("Error restoring tip:", error);
  
      // 3. On ERROR, update the original toast using its ID.
      toast.error("Failed to restore tip.", {
        id: toastId
      });
    }
  };
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
        <span className="ml-4 text-lg font-medium">Loading Expert Tips...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Section 1: Pending Review */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Pending Review</h3>
        {pendingTips.length === 0 ? (
          <p className="text-muted-foreground">
            No pending expert tips to review.
          </p>
        ) : (
          <div className="space-y-4">
            {pendingTips.map((tip) => (
              <Card key={tip.id}>
                <CardHeader>
                  <CardTitle>{tip.title}</CardTitle>
                  <CardDescription>Submitted for review.</CardDescription>
                </CardHeader>
                <CardContent className="whitespace-pre-wrap text-sm">
                  {tip.description}
                  {tip.mediaUrls && tip.mediaUrls.length > 0 && (
                    <div className="mt-4">
                      <h4 className="font-semibold text-sm text-gray-400">Attached Media</h4>
                      <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                        {tip.mediaUrls.map((url, index) => {
                          const fileName = decodeURIComponent(url.split('/').pop()?.split('?')[0] || `Media File ${index + 1}`);
                          const isLoading = openingMedia === `${tip.id}-${index}`;
        
                          return (
                            <li key={index}>
                              <button
                                onClick={() => handleAdminViewMedia(tip, url, index)}
                                disabled={isLoading}
                                className="text-blue-400 hover:underline text-sm disabled:text-gray-500"
                              >
                                {isLoading && <Spinner size="sm" className="inline-block mr-2" />}
                                {fileName}
                                </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </CardContent>
                <CardFooter className="flex justify-end space-x-2">
                  <Button
                    variant="outline"
                    onClick={() => handleReject(tip.id, tip.title)}
                  >
                    Reject
                  </Button>
                  <Button onClick={() => handleApprove(tip.id, tip.title)}>
                    Approve
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Section 2: Active in Knowledge Base */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Active in Knowledge Base</h3>
        {approvedTips.length === 0 ? (
          <p className="text-muted-foreground">
            No expert tips are currently active in the knowledge base.
          </p>
        ) : (
          <div className="space-y-4">
            {approvedTips.map((tip) => (
              <Card key={tip.id}>
                <CardHeader>
                  <CardTitle>{tip.title}</CardTitle>
                  <CardDescription>
                    This tip is active and searchable.
                  </CardDescription>
                </CardHeader>
                <CardContent className="whitespace-pre-wrap text-sm">
                  {tip.description}
                </CardContent>
                <CardFooter className="flex justify-end">
                  <Button
                    variant="outline"
                    onClick={() => handleDelete(tip.id, tip.title)}
                  >
                    Delete
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
      {/* Section 3: Deleted Tips */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Deleted Tips</h3>
        {isLoading ? (
          <p className="text-muted-foreground">Loading deleted tips...</p>
        ) : deletedTips.length === 0 ? (
          <p className="text-muted-foreground">
            No deleted expert tips found.
          </p>
        ) : (
          <div className="space-y-4">
            {deletedTips.map((tip) => (
              <Card key={tip.id}>
                <CardHeader>
                  <CardTitle>{tip.title}</CardTitle>
                  <CardDescription>
                    Submitted by: {tip.technicianName} on {new Date(tip.createdAt?.seconds * 1000).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
                <CardContent className="whitespace-pre-wrap text-sm">
                  {tip.description}
                </CardContent>
                <CardFooter className="flex justify-end">
                  <Button
                    variant="outline"
                    onClick={() => handleRestore(tip.id)}
                  >
                    Restore
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
  </div>
  );
};


export default function CompanyAdminDashboard() {
  const { user, loading: userLoading } = useCurrentUser();
  const navigate = useNavigate();
  const location = useLocation();
  const { company, loading: rolesLoading, role } = useUserRoles();
  const [activeTab, setActiveTab] = useState("overview");
  const [metrics, setMetrics] = useState({
    totalDocuments: 0,
    totalResponses: 0,
    ragUsageRate: 0,
    webSearchUsageRate: 0,
    totalTechnicians: 0,
    activeTechnicians: 0,
    responsesUsingRAG: 0,
    responsesUsingWeb: 0,
    totalWebSearches: 0,
    companyWebsiteHits: 0,
    usersByRole: {} as Record<string, number>,
    documentTrends: [] as Array<{ month: string; count: number }>,
    loading: true,
    error: null as string | null,
  });
  const [recentDocuments, setRecentDocuments] = useState<any[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [companySessions, setCompanySessions] = useState<TroubleshootingSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [organizationFilter, setOrganizationFilter] = useState("");
  const [addingToKB, setAddingToKB] = useState<string | null>(null);
  const [deletingFromKB, setDeletingFromKB] = useState<string | null>(null);

  // Sync activeTab with URL parameter
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get("tab");
    
    const validTabs = ["overview", "sessions", "users", "expert-tips", "constraints"];
    setActiveTab(validTabs.includes(tabParam || "") ? tabParam! : "overview");
  }, [location.search]);

  const handleAddSessionToKnowledgeBase = async (sessionId: string) => {
    setAddingToKB(sessionId);
    toast.info(`Adding session ${sessionId} to the knowledge base...`);
    try {
      const response = await apiClient.add_session_to_knowledge_base({
        sessionId: sessionId,
      });

      if (response.ok) {
        toast.success(
          `Session ${sessionId} successfully added and is being processed.`
        );
        setCompanySessions((prevSessions) =>
          prevSessions.map((session) =>
            session.id === sessionId
              ? { ...session, is_in_knowledge_base: true }
              : session
          )
        );
      } else {
        const errorData = (await response.json()) as unknown as {
          detail: string;
        };
        toast.error(
          `Failed to add session: ${errorData.detail || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("An unexpected error occurred:", error);
      toast.error("An unexpected error occurred while adding the session.");
    } finally {
      setAddingToKB(null);
    }
  };

  const handleDeleteSessionFromKnowledgeBase = async (sessionId: string) => {
    if (
      !window.confirm(
        "Are you sure you want to remove this session from the Knowledge Base? This cannot be undone."
      )
    ) {
      return;
    }

    setDeletingFromKB(sessionId);
    toast.info(`Removing session ${sessionId} from the knowledge base...`);

    try {
      const response = await apiClient.delete_session_from_knowledge_base({
        sessionId,
      });

      if (response.ok) {
        toast.success(
          `Session ${sessionId} has been removed from the knowledge base.`
        );
        setCompanySessions((prevSessions) =>
          prevSessions.map((session) =>
            session.id === sessionId
              ? { ...session, is_in_knowledge_base: false }
              : session
          )
        );
      } else {
        const errorData = (await response.json()) as { detail?: string };
        toast.error(
          `Failed to remove session: ${errorData.detail || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("An unexpected error occurred during deletion:", error);
      toast.error("An unexpected error occurred while removing the session.");
    } finally {
      setDeletingFromKB(null);
    }
  };

  const fetchRecentDocuments = async () => {
    try {
      if (!user || !company) {
        console.log("User or company not loaded yet, skipping document fetch");
        return;
      }

      const queryParams: Record<string, any> = {
        limit: 5,
        company,
        status: "queued,processing,processed,failed,split",
      };

      console.log("Fetching documents with params:", queryParams);
      const response = await apiClient.list_documents(queryParams);

      if (response.ok) {
        const data = await response.json();
        setRecentDocuments(data.documents || []);
      } else {
        throw new Error("Failed to fetch recent documents");
      }
    } catch (error) {
      console.error("Error fetching recent documents:", error);
      toast.error("Error loading documents. Please verify Firebase configuration.");
      setRecentDocuments([]);
    }
  };

  const handleReprocess = async (docId: string) => {
    setReprocessingId(docId);
    toast.info(`Requesting reprocessing for document ${docId}...`);
    try {
      const response = await apiClient.reprocess_stuck_document({
        document_id: docId,
      });
      if (response.ok) {
        const result = await response.json();
        toast.success(result.message || "Document submitted for reprocessing.");
        fetchRecentDocuments();
      } else {
        const errorData = (await response.json()) as { detail?: string };
        toast.error(
          `Failed to reprocess: ${errorData.detail || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("Reprocessing error:", error);
      toast.error("An unexpected error occurred while reprocessing.");
    } finally {
      setReprocessingId(null);
    }
  };

  useEffect(() => {
    if (userLoading) return;
    if (!userLoading && !company) return;
    console.log(
      "CompanyAdminDashboard - fetchRecentDocuments starting for company:",
      company
    );
    fetchRecentDocuments();
  }, [user, company, userLoading, rolesLoading]);

  useEffect(() => {
    if (!userLoading && !rolesLoading && user && company) {
      setSessionsLoading(true);
      sessionManager
        .listSessions(company, organizationFilter)
        .then((sessions) => {
          setCompanySessions(sessions);
          setSessionsLoading(false);
        })
        .catch((error) => {
          console.error("Error fetching company sessions:", error);
          toast.error("Failed to load company sessions.");
          setSessionsLoading(false);
        });
    }
  }, [user, company, userLoading, rolesLoading, organizationFilter]);

  // ✅ ADD THE METRICS FETCH CODE HERE
  useEffect(() => {
    if (userLoading || rolesLoading || !user || !company) {
      return;
    }

    const fetchMetrics = async () => {
      try {
        console.log("CompanyAdminDashboard - Fetching metrics for company:", company);
        const response = await apiClient.get_admin_metrics({ company });
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("CompanyAdminDashboard - Metrics data received:", data);
        
        setMetrics({
          ...data,
          loading: false,
          error: null
        });
      } catch (error) {
        console.error("CompanyAdminDashboard - Error fetching metrics:", error);
        setMetrics(prev => ({
          ...prev,
          loading: false,
          error: error instanceof Error ? error.message : "Failed to load company metrics"
        }));
      }
    };

    fetchMetrics();
  }, [user, company, userLoading, rolesLoading]);

  if (userLoading || rolesLoading || metrics.loading) {
    return (
      <AdminLayout activeTab="dashboard">
        <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
          <Spinner size="lg" />
          <span className="ml-4 text-lg font-medium">
            Loading company dashboard...
          </span>
        </div>
      </AdminLayout>
    );
  }

  if (!userLoading && !rolesLoading && role === "company_admin" && !company) {
    return (
      <AdminLayout activeTab="dashboard">
        <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] p-6 max-w-3xl mx-auto text-center">
          <div className="mb-6 w-16 h-16 rounded-full bg-amber-500/10 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              className="w-8 h-8 text-amber-500"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h1" />
              <path d="M15 3h1a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-1" />
              <path d="M2 15H10" />
              <path d="M12 15H10" />
              <path d="M5 15v5" />
              <path d="M19 15v5" />
            </svg>
          </div>
          <h2 className="text-xl font-bold mb-2">Company Not Assigned</h2>
          <p className="text-muted-foreground mb-6">
            Your account is set as a company admin but doesn't have a company
            assigned. Please contact a system administrator to set up your
            company affiliation or update your user claims.
          </p>
          <div className="space-x-4">
            <Button onClick={() => window.location.reload()}>Reload Page</Button>
            <Button variant="outline" onClick={() => navigateSafely("")}>
              Go to Home
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-8">
            Technical details: Missing 'company' field in your user claims.
            Current role: {role || "unknown"}
          </p>
        </div>
      </AdminLayout>
    );
  }

  if (metrics.error) {
    return (
      <AdminLayout activeTab="dashboard">
        <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] p-6 max-w-3xl mx-auto text-center">
          <div className="mb-6 w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              className="w-8 h-8 text-red-500"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-xl font-bold mb-2">
            Failed to load company dashboard
          </h2>
          <p className="text-muted-foreground mb-6">{metrics.error}</p>
          <div className="space-x-4">
            <Button onClick={() => window.location.reload()}>Reload Page</Button>
            <Button variant="outline" onClick={() => navigateSafely("")}>
              Go to Home
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-8">
            If this problem persists, please contact the system administrator.
          </p>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout activeTab="dashboard">
      <div className="p-4 sm:p-6 lg:p-8">
        <h1 className="text-2xl font-bold mb-6">Company Admin Dashboard</h1>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="sessions">Session Knowledge Base</TabsTrigger>
            <TabsTrigger value="users">User Management</TabsTrigger>
            <TabsTrigger value="expert-tips">Expert Tips</TabsTrigger>
            <TabsTrigger value="constraints">Constraints</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="border-none p-0 outline-none">
            <div className="space-y-6">
              <Card className="mb-6">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>
                      Welcome, {user?.email || "User"}!
                    </CardTitle>
                    <CardDescription>
                      Here's a summary of your company's activity
                    </CardDescription>
                  </div>
                  <Button
                    onClick={() => navigateSafely("")}
                    variant="outline"
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
                      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                      <polyline points="9 22 9 12 15 12 15 22" />
                    </svg>
                    Home
                  </Button>
                </CardHeader>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Documents</CardTitle>
                    <CardDescription>Knowledge base size</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">
                      {metrics.totalDocuments}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {metrics.documentTrends &&
                      metrics.documentTrends.length > 0
                        ? `${
                            metrics.documentTrends[
                              metrics.documentTrends.length - 1
                            ]?.count || 0
                          } added this month`
                        : "No recent uploads"}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Responses</CardTitle>
                    <CardDescription>Total AI interactions</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">
                      {metrics.totalResponses}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                      <div className="flex items-center gap-0.5">
                        <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                        <span>
                          RAG: {metrics.responsesUsingRAG} (
                          {metrics.ragUsageRate}%)
                        </span>
                      </div>
                      <div className="flex items-center gap-0.5">
                        <div className="h-2 w-2 rounded-full bg-purple-500"></div>
                        <span>
                          Web: {metrics.responsesUsingWeb} (
                          {metrics.webSearchUsageRate}%)
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Technicians</CardTitle>
                    <CardDescription>Active users</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">
                      {metrics.totalTechnicians ||
                        (metrics.usersByRole?.technician || 0)}
                    </div>
                    <div className="mt-2">
                      <div className="flex justify-between mb-1 text-xs">
                        <span>Active</span>
                        <span>
                          {metrics.activeTechnicians || 0} of{" "}
                          {metrics.totalTechnicians ||
                            (metrics.usersByRole?.technician || 0)}
                        </span>
                      </div>
                      <Progress
                        value={
                          (metrics.activeTechnicians /
                            (metrics.totalTechnicians || 1)) *
                          100
                        }
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Web Searches</CardTitle>
                    <CardDescription>External knowledge</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold">
                      {metrics.totalWebSearches || 0}
                    </div>
                    {metrics.companyWebsiteHits !== undefined && (
                      <div className="mt-2">
                        <div className="flex justify-between mb-1 text-xs">
                          <span>{company} Website Hits</span>
                          <span>
                            {metrics.companyWebsiteHits} of{" "}
                            {metrics.totalWebSearches || 1}
                          </span>
                        </div>
                        <Progress
                          value={
                            (metrics.companyWebsiteHits /
                              (metrics.totalWebSearches || 1)) *
                            100
                          }
                        />
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Recent Documents</CardTitle>
                    <CardDescription>
                      Latest additions to your knowledge base
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {recentDocuments.length > 0 ? (
                    <div className="space-y-4">
                      {recentDocuments.map((doc: any) => (
                        <div key={doc.id} className="flex items-start gap-4">
                          <div className="p-2 rounded-md bg-primary/10">
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
                            >
                              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                              <polyline points="14 2 14 8 20 8" />
                            </svg>
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">
                                  {doc.title ||
                                    doc.id ||
                                    "Untitled Document"}
                                </span>
                                <span
                                  className={`text-xs px-2 py-1 rounded-full ${
                                    doc.status === "processed"
                                      ? "bg-green-500/20 text-green-700"
                                      : doc.status === "processing"
                                      ? "bg-yellow-500/20 text-yellow-600 animate-pulse"
                                      : doc.status === "failed"
                                      ? "bg-red-500/20 text-red-600"
                                      : doc.status === "queued"
                                      ? "bg-blue-500/20 text-blue-600"
                                      : "bg-gray-500/20 text-gray-600"
                                  }`}
                                >
                                  {doc.status
                                    ? doc.status.charAt(0).toUpperCase() +
                                      doc.status.slice(1)
                                    : "Unknown"}
                                </span>
                              </div>
                              {["processing", "failed"].includes(
                                doc.status
                              ) && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleReprocess(doc.id)}
                                  disabled={reprocessingId === doc.id}
                                >
                                  {reprocessingId === doc.id ? (
                                    <>
                                      <Spinner size="sm" className="mr-2" />
                                      Reprocessing...
                                    </>
                                  ) : (
                                    "Reprocess"
                                  )}
                                </Button>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {doc.fileName}
                            </p>
                            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                              <span>
                                {new Date(doc.createdAt).toLocaleString()}
                              </span>
                              <span className="border-l border-border pl-2">
                                {doc.uploadedBy || "N/A"}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <AdminEmptyState
                      title="No documents have been uploaded yet"
                      description="Visit the Documents tab to upload and manage your knowledge base."
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
                          className="h-6 w-6"
                        >
                          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                      }
                    />
                  )}
                </CardContent>
                <CardFooter>
                  <button
                    className="text-sm text-primary hover:underline"
                    onClick={() => navigate("/admin-documents")}
                  >
                    View all documents →
                  </button>
                </CardFooter>
              </Card>
            </div>
          </TabsContent>
          <TabsContent value="sessions" className="border-none p-0 outline-none">
            <Card>
              <CardHeader>
                <CardTitle>Company Troubleshooting Sessions</CardTitle>
                <CardDescription>
                  Review and archive completed troubleshooting sessions to build
                  your knowledge base.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Input
                    placeholder="Filter by Organization..."
                    value={organizationFilter}
                    onChange={(e) => setOrganizationFilter(e.target.value)}
                    className="max-w-sm"
                  />
                </div>
                {sessionsLoading ? (
                  <div className="flex justify-center items-center py-10">
                    <Spinner size="lg" />
                    <span className="ml-2">Loading sessions...</span>
                  </div>
                ) : companySessions.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Session ID</TableHead>
                        <TableHead>Technician (User ID)</TableHead>
                        <TableHead>Organization</TableHead>
                        <TableHead>Assignment</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Last Updated</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {companySessions.map((session) => (
                        <TableRow key={session.id}>
                          <TableCell className="font-medium truncate max-w-[100px]">
                            <button
                              onClick={() =>
                                navigate(`/response?sessionId=${session.id}`)
                              }
                              className="text-blue-600 hover:underline"
                            >
                              {session.id}
                            </button>
                          </TableCell>
                          <TableCell className="truncate max-w-[150px]">
                            {session.userId}
                          </TableCell>
                          <TableCell>{session.organization || "N/A"}</TableCell>
                          <TableCell className="truncate max-w-[200px]">
                            {session.assignmentName}
                          </TableCell>
                          <TableCell>
                            <span
                              className={`px-2 py-1 text-xs rounded-full ${
                                session.status === "completed"
                                  ? "bg-green-100 text-green-700"
                                  : session.status === "in-progress"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-gray-100 text-gray-700"
                              }`}
                            >
                              {session.status}
                            </span>
                          </TableCell>
                          <TableCell>
                            {new Date(
                              session.lastUpdated.seconds * 1000
                            ).toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            {session.is_in_knowledge_base ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  handleDeleteSessionFromKnowledgeBase(
                                    session.id
                                  )
                                }
                                disabled={deletingFromKB === session.id}
                              >
                                {deletingFromKB === session.id ? (
                                  <>
                                    <Spinner size="sm" className="mr-2" />
                                    Deleting...
                                  </>
                                ) : (
                                  "Delete from KB"
                                )}
                              </Button>
                            ) : (
                              session.status === "completed" && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    handleAddSessionToKnowledgeBase(session.id)
                                  }
                                  disabled={addingToKB === session.id}
                                >
                                  {addingToKB === session.id ? (
                                    <>
                                      <Spinner size="sm" className="mr-2" />
                                      Adding...
                                    </>
                                  ) : (
                                    "Add to KB"
                                  )}
                                </Button>
                              )
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <AdminEmptyState
                    title="No Sessions Found"
                    description={
                      organizationFilter
                        ? `No sessions found for organization "${organizationFilter}".`
                        : "No troubleshooting sessions have been recorded for this company yet."
                    }
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="users" className="border-none p-0 outline-none">
            <UserManagement systemAdmin={false} />
          </TabsContent>
          <TabsContent value="expert-tips" className="border-none p-0 outline-none">
             <ExpertTipsManagement />
          </TabsContent>
          <TabsContent value="constraints" className="border-none p-0 outline-none">
            <ConstraintManagement />
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
