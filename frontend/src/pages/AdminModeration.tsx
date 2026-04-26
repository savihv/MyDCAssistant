import { apiClient } from "../app";
import { DocumentData } from "firebase/firestore";
import React, { useEffect, useState, useCallback } from "react";
import { useUserRoles } from "../utils/useUserRoles";
import { firebaseApp, useCurrentUser } from "../app";
import { getFirestore, collection, query, where, getDocs, orderBy, limit, startAfter, doc, getDoc } from "firebase/firestore";
import { AdminLayout } from "../components/AdminLayout"; // Added import
import { Button } from "../components/Button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { toast } from "sonner";
import { API_URL } from "../app";
// import removed

interface ModerationItem {
  id: string;
  company?: string;
  content: string;
  contentType: "text" | "image" | "video" | "audio";
  decision?: "approved" | "rejected";
  decisionTimestamp?: any;
  docId?: string;
  flaggedBy?: string;
  reason?: string;
  status: "pending" | "reviewed";
  timestamp: any;
  userId?: string;
  originalUploaderName?: string;
  originalUploaderEmail?: string;
}

const AdminModeration = () => {
  const [moderationItems, setModerationItems] = useState<ModerationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user: currentUser, loading: authLoading } = useCurrentUser();
  const { role, company, loading: rolesAndClaimsLoading } = useUserRoles();

  const [lastVisible, setLastVisible] = useState<DocumentData | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const ITEMS_PER_PAGE = 10;

  const fetchUserDetails = useCallback(async (userId: string) => {
    if (!userId) return { name: "Unknown User", email: "N/A" };
    try {
      const userDocRef = doc(getFirestore(firebaseApp), `users/${userId}`);
      const userDocSnap = await getDoc(userDocRef);
      if (userDocSnap.exists()) {
        const userData = userDocSnap.data();
        return { name: userData.name || "Unknown User", email: userData.email || "N/A" };
      }
      return { name: "Unknown User", email: "N/A" };
    } catch (err) {
      console.error("Error fetching user details:", err);
      return { name: "Error Fetching Name", email: "Error Fetching Email" };
    }
  }, []);

  const fetchModerationItems = useCallback(async (loadMore = false) => {
    if (authLoading || rolesAndClaimsLoading || !currentUser) {
      return; 
    }
    setIsLoading(true);
    setError(null);

    let newItems: ModerationItem[] = [];

    try {
      const response = await (apiClient as any).list_moderation_queue({
        status: "pending",
        limit: ITEMS_PER_PAGE,
        offset: loadMore && moderationItems.length > 0 ? moderationItems.length : 0,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error ${response.status}: ${errorText || response.statusText}`);
      }
      
      const data = await response.json();
      if (!data || !Array.isArray(data.items)) {
        throw new Error("Invalid data structure from API");
      }
      newItems = data.items;
      setHasMore(data.items.length === ITEMS_PER_PAGE && data.total_items > (loadMore ? moderationItems.length : 0) + data.items.length);

    } catch (apiError: any) {
      console.error("Error fetching from API, falling back to Firestore:", apiError);
      setError(`API Error: ${apiError.message}. Falling back to direct Firestore access.`);
      toast.error(`API Error: ${apiError.message}. Falling back to direct Firestore access.`);
      
      if (!currentUser) {
        setError("User not available for Firestore query.");
        setIsLoading(false);
        return;
      }
      const db = getFirestore(firebaseApp);
      let q = query(
        collection(db, "moderationQueue"), 
        where("status", "==", "pending"),
        orderBy("timestamp", "desc"),
        limit(ITEMS_PER_PAGE)
      );

      if (role === "company_admin" && company) {
        q = query(
            collection(db, "moderationQueue"), 
            where("status", "==", "pending"),
            where("company", "==", company),
            orderBy("timestamp", "desc"),
            limit(ITEMS_PER_PAGE)
        );
      } else if (role === "system_admin") {
        // No additional company filter for system_admin
      } else {
        setError("Unauthorized: User role cannot access moderation queue directly.");
        setIsLoading(false);
        setHasMore(false);
        return;
      }

      if (loadMore && lastVisible) {
        q = query(q, startAfter(lastVisible));
      }

      try {
        const querySnapshot = await getDocs(q);
        const fallbackItems = querySnapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data(),
        })) as ModerationItem[];
        
        newItems = fallbackItems;
        setHasMore(fallbackItems.length === ITEMS_PER_PAGE);
        if (querySnapshot.docs.length > 0) {
          setLastVisible(querySnapshot.docs[querySnapshot.docs.length - 1]);
        }
      } catch (firestoreError: any) {
        console.error("Error fetching from Firestore fallback:", firestoreError);
        setError(`Firestore Fallback Error: ${firestoreError.message}`);
        toast.error(`Firestore Fallback Error: ${firestoreError.message}`);
        newItems = [];
        setHasMore(false);
      }
    }

    const itemsWithUserDetails = await Promise.all(
      newItems.map(async (item) => {
        const userDetails = await fetchUserDetails(item.userId || "");
        return { 
          ...item, 
          originalUploaderName: userDetails.name, 
          originalUploaderEmail: userDetails.email 
        };
      })
    );

    setModerationItems(prevItems => loadMore ? [...prevItems, ...itemsWithUserDetails] : itemsWithUserDetails);
    setIsLoading(false);
  }, [currentUser, role, company, authLoading, rolesAndClaimsLoading, lastVisible, fetchUserDetails, moderationItems.length]);

  useEffect(() => {
    if (!authLoading && !rolesAndClaimsLoading && currentUser) {
      fetchModerationItems(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, rolesAndClaimsLoading, currentUser, fetchModerationItems]);

  const handleReview = async (itemId: string, decision: "approved" | "rejected", comments?: string) => {
    try {
      const requestBody: any = {
        action: decision,
        reviewerComments: comments,
      };
      await (apiClient as any).review_moderation_item({ itemId }, requestBody);
      toast.success(`Item ${decision} successfully.`);
      setModerationItems(prevItems => prevItems.filter(item => item.id !== itemId));
    } catch (err: any) {
      console.error("Error reviewing item:", err);
      const errorMsg = err.response ? await err.response.text() : err.message;
      toast.error(`Failed to review item: ${errorMsg}`);
    }
  };

  if (authLoading || rolesAndClaimsLoading) {
    return <div className="p-4">Loading user information...</div>;
  }

  if (!currentUser) {
    return <div className="p-4">User not authenticated. Please log in.</div>;
  }

  if (role !== "system_admin" && role !== "company_admin") {
    return <div className="p-4">Unauthorized: You do not have permission to view this page.</div>;
  }

  return (
    <AdminLayout activeTab="moderation">
      <div className="p-4 md:p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold">Moderation Queue</h1>
        </div>

        {error && (
          <Card className="bg-destructive/10 border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Error</CardTitle>
            </CardHeader>
            <CardContent>
              <p>{error}</p>
              <Button variant="outline" size="sm" onClick={() => fetchModerationItems(false)} className="mt-2">
                Retry Fetch
              </Button>
            </CardContent>
          </Card>
        )}

        {isLoading && moderationItems.length === 0 && <p>Loading moderation items...</p>}
        
        {!isLoading && moderationItems.length === 0 && !error && (
          <p>No items currently in the moderation queue.</p>
        )}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {moderationItems.map(item => (
            <Card key={item.id} className="flex flex-col">
              <CardHeader>
                <CardTitle className="text-lg">{item.docId ? `Document: ${item.docId}` : "Unknown document"}</CardTitle>
                <CardDescription>
                  Flagged{item.flaggedBy === "system" ? " by automated system" : (item.flaggedBy ? ` by user ${item.flaggedBy}`: "")}.<br />
                  {item.reason && <span>Reason: {item.reason}<br /></span>}
                  Content Type: {item.contentType}<br/>
                  Uploaded: {item.timestamp?.toDate ? item.timestamp.toDate().toLocaleDateString() : (item.timestamp ? new Date(item.timestamp).toLocaleDateString() : "N/A")}<br/>
                  {item.originalUploaderName && item.originalUploaderName !== "Unknown User" && (
                    <span>By: {item.originalUploaderName} ({item.originalUploaderEmail || "N/A"})</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-grow">
                {item.contentType === "text" && <p className="prose dark:prose-invert max-w-none break-words">{item.content}</p>}
                {item.contentType === "image" && <img src={item.content} alt="Moderation content" className="max-w-full h-auto rounded" />}
                {(item.contentType === "video" || item.contentType === "audio") && 
                  <a href={item.content} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                    View {item.contentType} content
                  </a>
                }
              </CardContent>
              <CardFooter className="flex justify-end space-x-2">
                <Button variant="outline" size="sm" onClick={() => handleReview(item.id, "rejected")}>Reject</Button>
                <Button variant="default" size="sm" onClick={() => handleReview(item.id, "approved")}>Approve</Button>
              </CardFooter>
            </Card>
          ))}
        </div>

        {hasMore && !isLoading && (
          <div className="flex justify-center">
            <Button onClick={() => fetchModerationItems(true)} variant="outline">
              Load More
            </Button>
          </div>
        )}
        {isLoading && moderationItems.length > 0 && <p className="text-center">Loading more items...</p>}
      </div>
    </AdminLayout>
  );
};

export default AdminModeration;
