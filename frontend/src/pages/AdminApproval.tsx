//import { useState, useEffect } from "react";
import React from "react";
import { useState, useEffect, useCallback } from "react"; // Added useCallback
import { useCurrentUser } from "../app/auth/useCurrentUser"; // Relative path
import { useUserRoles } from "../utils/useUserRoles"; // Relative path
import { AdminGuard } from "../components/AdminGuard";
import { AdminLayout } from "../components/AdminLayout";
import { AdminEmptyState } from "../components/AdminEmptyState";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input.tsx";
import { Spinner } from "../components/Spinner";
import { Card } from "../extensions/shadcn/components/card.tsx";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../extensions/shadcn/components/dialog.tsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../extensions/shadcn/components/select.tsx";
import { Textarea } from "../extensions/shadcn/components/textarea.tsx";
import { Label } from "../extensions/shadcn/components/label.tsx";
import { Badge } from "../extensions/shadcn/components/badge.tsx";
import { toast } from "sonner";
import { apiClient } from "../app";

// Combined interface for displaying users from various sources
interface DisplayUser {
  id: string; // common
  uid: string; // common
  userEmail: string; // common
  displayName?: string; // common
  company?: string; // common
  status: 'pending' | 'approved' | 'rejected' | string; // Specific status for UI consistency
  
  // Fields from PendingUser (mostly for 'pending' status)
  requestedRole?: string;
  requestedAt?: { seconds: number; nanoseconds: number };
  
  // Fields from UserData (for 'approved'/'rejected' and general info)
  // These will come from the get_all_users endpoint typically as ISO strings or null
  role?: string; // Actual role after approval
  approvalStatus?: string; // Backend might send this as well from UserData
  createdAt?: { seconds: number; nanoseconds: number } | string | null; 
  lastActive?: { seconds: number; nanoseconds: number } | string | null;
  approvedAt?: { seconds: number; nanoseconds: number } | string | null;
  rejectedAt?: { seconds: number; nanoseconds: number } | string | null;
  approvedBy?: string;
  rejectedBy?: string;
  rejectionReason?: string;
  photoURL?: string;

  // review fields from original PendingUser, might be set by UI or backend for pending
  reviewedBy?: string; 
  reviewedAt?: { seconds: number; nanoseconds: number }; 
}


interface PendingUser {
  id: string;
  uid: string;
  userEmail: string;
  displayName: string;
  requestedRole: string;
  company?: string;
  requestedAt?: { seconds: number; nanoseconds: number };
  status: string;
  reviewedBy?: string;
  reviewedAt?: { seconds: number; nanoseconds: number };
  rejectionReason?: string;
}

export default function AdminApproval() {
  const [displayedUsers, setDisplayedUsers] = useState<DisplayUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<DisplayUser | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("pending");
  
const { user, loading: userLoading } = useCurrentUser();
  const {
    role,
    company,
    isSystemAdmin,
    isCompanyAdmin,
    loading: rolesLoading,
  } = useUserRoles();

  const initialAuthLoading = userLoading || rolesLoading;

  // Universal date formatter for DisplayUser timestamps
  const formatDate = (timestamp?: { seconds: number; nanoseconds: number } | string | null): string => {
    if (!timestamp) return "N/A";
    if (typeof timestamp === 'string') {
      const date = new Date(timestamp);
      return isNaN(date.getTime()) ? "Invalid Date" : date.toLocaleString();
    }
    // Assuming { seconds, nanoseconds } object
    if (timestamp.seconds !== undefined && timestamp.nanoseconds !== undefined) {
      return new Date(timestamp.seconds * 1000).toLocaleString();
    }
    return "Invalid Date Format";
  };

  // Function to fetch users based on the status filter
  const fetchUsersByStatus = useCallback(async (currentFilter: string) => {
    setLoading(true);
    let combinedUsers: DisplayUser[] = [];

    try {
      if (currentFilter === "pending" || currentFilter === "all") {
        const response = await apiClient.get_pending_users();
        if (!response.ok) throw new Error(`Failed to fetch pending users: ${response.statusText}`);
        const data = await response.json();
        const pending = (data.users || []).map((apiUser: any): DisplayUser => ({
          id: apiUser.id || '',
          uid: apiUser.uid || '',
          userEmail: apiUser.userEmail || '',
          displayName: apiUser.displayName || '',
          requestedRole: apiUser.requestedRole || 'technician',
          company: apiUser.company,
          requestedAt: apiUser.requestedAt, // Keep as object for formatDate
          status: 'pending', // Explicitly set status for mapping
          reviewedBy: apiUser.reviewedBy,
          reviewedAt: apiUser.reviewedAt, // Keep as object
          rejectionReason: apiUser.rejectionReason,
          // Other DisplayUser fields will be undefined, which is fine
        }));
        combinedUsers = combinedUsers.concat(pending);
      }

      if (currentFilter === "approved" || currentFilter === "all") {
        const response = await apiClient.get_all_users({ approval_status_list_str: "approved" });
        if (!response.ok) throw new Error(`Failed to fetch approved users: ${response.statusText}`);
        const data = await response.json();
        const approved = (data.users || []).map((apiUser: any): DisplayUser => ({
          id: apiUser.id || '',
          uid: apiUser.uid || '',
          userEmail: apiUser.email || '', // Note: backend UserData has 'email'
          displayName: apiUser.displayName || '',
          role: apiUser.role,
          company: apiUser.company,
          status: 'approved', // Explicitly set status
          approvalStatus: apiUser.approvalStatus, // from backend UserData
          createdAt: apiUser.createdAt, // Expect ISO string
          lastActive: apiUser.lastActive, // Expect ISO string
          approvedAt: apiUser.approvedAt, // Expect ISO string
          approvedBy: apiUser.approvedBy,
          photoURL: apiUser.photoURL,
          // requestedRole might not be directly available for already approved users from this endpoint
        }));
        combinedUsers = combinedUsers.concat(approved);
      }

      if (currentFilter === "rejected" || currentFilter === "all") {
        const response = await apiClient.get_all_users({ approval_status_list_str: "rejected" });
        if (!response.ok) throw new Error(`Failed to fetch rejected users: ${response.statusText}`);
        const data = await response.json();
        const rejected = (data.users || []).map((apiUser: any): DisplayUser => ({
          id: apiUser.id || '',
          uid: apiUser.uid || '',
          userEmail: apiUser.email || '',
          displayName: apiUser.displayName || '',
          role: apiUser.role, // actual role might be blank or a default if rejected early
          company: apiUser.company,
          status: 'rejected', // Explicitly set status
          approvalStatus: apiUser.approvalStatus, // from backend UserData
          createdAt: apiUser.createdAt, // Expect ISO string
          rejectionReason: apiUser.rejectionReason,
          rejectedAt: apiUser.rejectedAt, // Expect ISO string
          rejectedBy: apiUser.rejectedBy,
          photoURL: apiUser.photoURL,
          // requestedRole might have been stored, or might be generic here.
        }));
        combinedUsers = combinedUsers.concat(rejected);
      }
      
      // For "all", remove duplicates if any (e.g. if a user was pending then approved quickly)
      // A more robust deduplication would use a Set or reduce by ID.
      if (currentFilter === "all") {
        const uniqueUsers = Array.from(new Map(combinedUsers.map(user => [user.id, user])).values());
        setDisplayedUsers(uniqueUsers);
      } else {
        setDisplayedUsers(combinedUsers);
      }

    } catch (error) {
      console.error(`Error fetching users for filter '${currentFilter}':`, error);
      toast.error(`Failed to load user requests for ${currentFilter}`);
      setDisplayedUsers([]); // Clear users on error to avoid showing stale data
    } finally {
      setLoading(false);
    }
  }, [setLoading, setDisplayedUsers]); // Removed brain from deps as it's stable

  // Initial load and filter change handler
  useEffect(() => {
    if (!initialAuthLoading) {
      if (user && (isSystemAdmin || isCompanyAdmin)) {
        fetchUsersByStatus(statusFilter);
      } else if (user) {
        setLoading(false);
      } else {
        setLoading(false);
      }
    }
  }, [user, initialAuthLoading, isSystemAdmin, isCompanyAdmin, statusFilter, fetchUsersByStatus]);

  // Function to handle user review
  const handleReviewUser = (user: PendingUser) => {
    setSelectedUser(user);
    setRejectionReason("");
    setShowReviewDialog(true);
  };

  // Function to approve user
  const handleApproveUser = async () => {
    if (!selectedUser) return;
    
    try {
      setSubmitting(true);
      
      const response = await apiClient.approve_reject_user({
        userId: selectedUser.id,
        approve: true
      });
      
      if (!response.ok) {
        throw new Error(`Failed to approve user: ${response.statusText}`);
      }
      
      // Update local state by re-fetching
      fetchUsersByStatus(statusFilter);
      
      // Reset state and close dialog
      setSelectedUser(null);
      setShowReviewDialog(false);
      
      toast.success("User approved successfully");
    } catch (error) {
      console.error("Error approving user:", error);
      toast.error("Failed to approve user");
    } finally {
      setSubmitting(false);
    }
  };

  // Function to reject user
  const handleRejectUser = async () => {
    if (!selectedUser) return;
    if (!rejectionReason) {
      toast.error("Please provide a reason for rejection");
      return;
    }
    
    try {
      setSubmitting(true);
      
      const response = await apiClient.approve_reject_user({
        userId: selectedUser.id,
        approve: false,
        rejectionReason: rejectionReason
      });
      
      if (!response.ok) {
        throw new Error(`Failed to reject user: ${response.statusText}`);
      }
      
      // Update local state by re-fetching
      fetchUsersByStatus(statusFilter);

      // Reset state and close dialog
      setSelectedUser(null);
      setRejectionReason("");
      setShowReviewDialog(false);
      
      toast.success("User request rejected");
    } catch (error) {
      console.error("Error rejecting user:", error);
      toast.error("Failed to reject user");
    } finally {
      setSubmitting(false);
    }
  };


  // Filter users by search term and status
  const filteredUsers = displayedUsers.filter(userToFilter => { // Renamed to avoid conflict with currentUser from useCurrentUser
    // Company Admin: Filter by their company
    if (isCompanyAdmin && company && userToFilter.company !== company) {
      return false;
    }

    // Apply status filter
    if (statusFilter !== "all" && userToFilter.status !== statusFilter) return false;
    
    // Apply search term filter
    if (!searchTerm) return true;
    
    const search = searchTerm.toLowerCase();
    return (
      userToFilter.userEmail?.toLowerCase().includes(search) ||
      userToFilter.displayName?.toLowerCase().includes(search) ||
      userToFilter.company?.toLowerCase().includes(search) ||
      userToFilter.requestedRole?.toLowerCase().includes(search) || // Search requested role
      userToFilter.role?.toLowerCase().includes(search) // Also search actual role for approved/rejected
    );
  });

  

  // Handle initial authentication loading state
  if (initialAuthLoading) {
    return (
      <AdminLayout activeTab="approval">
        <div className="flex justify-center items-center h-64">
          <Spinner size="lg" />
        </div>
      </AdminLayout>
    );
  }

  // Handle permission AFTER auth loading is complete.
  // This uses the reliable role checks from useUserRoles.
  if (!user || (!isSystemAdmin && !isCompanyAdmin)) {
    return (
      <AdminLayout activeTab="approval">
        <div className="flex justify-center items-center h-64">
          <p className="text-muted-foreground">You don't have permission to access this page.</p>
        </div>
      </AdminLayout>
    );
  }

  // If we reach here, auth is loaded AND user IS an admin.
  return (
    <AdminGuard allowedRoles={['system_admin', 'company_admin']}>
      <AdminLayout activeTab="approval">
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">User Approval Requests</h1>
            <p className="text-muted-foreground">
              {isSystemAdmin 
                ? 'Review and manage user registration requests' 
                : 'Review and manage technician registration requests for your company'}
            </p>
          </div>
          
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <div className="flex-1">
              <Input 
                placeholder="Search requests..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <Select 
              value={statusFilter} 
              onValueChange={setStatusFilter}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Requests</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {/* User Request List */}
          <div className="space-y-4">
            {loading ? (
              <div className="flex justify-center items-center h-64">
                <Spinner size="lg" />
              </div>
            ) : filteredUsers.length > 0 ? (
              <div className="grid gap-4">
                {filteredUsers.map(user => (
                  <Card key={user.id} className="p-4">
                    <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
                      <div className="flex flex-1 gap-4 items-start">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
                          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5 text-primary">
                            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                        </div>
                        
                        <div className="flex-1">
                          <h3 className="font-semibold">
                            {user.displayName || user.userEmail}
                          </h3>
                          <p className="text-sm text-muted-foreground">{user.userEmail}</p>
                          
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Badge className={user.status === 'pending' 
                              ? 'bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30'
                              : user.status === 'approved'
                                ? 'bg-green-500/20 text-green-600 hover:bg-green-500/30'
                                : user.status === 'rejected'
                                  ? 'bg-red-500/20 text-red-600 hover:bg-red-500/30'
                                  : 'bg-gray-500/20 text-gray-600 hover:bg-gray-500/30' // Default/fallback
                            }>
                              {user.status ? user.status.charAt(0).toUpperCase() + user.status.slice(1) : "Unknown"}
                            </Badge>
                            
                            <Badge className={
                              (user.role || user.requestedRole) === 'system_admin' 
                                ? 'bg-purple-500/20 text-purple-600 hover:bg-purple-500/30'
                                : (user.role || user.requestedRole) === 'company_admin'
                                  ? 'bg-blue-500/20 text-blue-600 hover:bg-blue-500/30'
                                  : 'bg-gray-500/20 text-gray-600 hover:bg-gray-500/30'
                            }>
                              {(user.role || user.requestedRole) === 'system_admin' ? 'System Admin' :
                               (user.role || user.requestedRole) === 'company_admin' ? 'Company Admin' : 'Technician'}
                            </Badge>
                            
                            {user.company && (
                              <Badge variant="outline">{user.company}</Badge>
                            )}
                          </div>
                          
                          <div className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                            {user.status === 'pending' && user.requestedAt && (
                              <span>Requested: {formatDate(user.requestedAt)}</span>
                            )}
                            {user.status === 'approved' && user.approvedAt && (
                              <span>Approved: {formatDate(user.approvedAt)}
                                {user.approvedBy && <span className="text-xs"> by UID: {user.approvedBy}</span>}                              
                              </span>
                            )}
                            {user.status === 'rejected' && user.rejectedAt && (
                              <span>Rejected: {formatDate(user.rejectedAt)}
                                {user.rejectedBy && <span className="text-xs"> by UID: {user.rejectedBy}</span>}
                              </span>
                            )}
                             {/* Display reviewedAt if status is not pending and reviewedAt exists, but not if it is already covered by approvedAt/rejectedAt logic*/}
                            {user.status !== 'pending' && user.reviewedAt && !(user.status === 'approved' && user.approvedAt) && !(user.status === 'rejected' && user.rejectedAt) && (
                              <span>Reviewed: {formatDate(user.reviewedAt)}</span>
                            )}
                             {/* Display createdAt if available */}
                            {user.createdAt && (
                              <span>Account Created: {formatDate(user.createdAt)}</span>
                            )}
                          </div>
                          
                          {user.status === 'rejected' && user.rejectionReason && (
                            <div className="mt-2 text-sm text-red-700">
                              <span className="font-medium">Reason for rejection:</span> {user.rejectionReason}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {user.status === 'pending' && (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            className="bg-green-500/10 text-green-600 hover:bg-green-500/20 hover:text-green-700 border-green-200"
                            onClick={() => {
                              setSelectedUser(user);
                              handleApproveUser();
                            }}
                          >
                            Approve
                          </Button>
                          <Button 
                            variant="outline"
                            className="bg-red-500/10 text-red-600 hover:bg-red-500/20 hover:text-red-700 border-red-200"
                            onClick={() => handleReviewUser(user as any)}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <AdminEmptyState
                title={searchTerm ? "No user requests match your search" : statusFilter !== "all" ? `No ${statusFilter} requests found` : "No user requests found"}
                description={searchTerm 
                  ? `Try different search terms or clear your search.` 
                  : statusFilter !== "all" 
                    ? `Try selecting a different status filter to view other requests.` 
                    : `New user registration requests will appear here when users sign up.`}
                icon={<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>}
                actionLabel={searchTerm ? "Clear Search" : statusFilter !== "all" ? "Show All Requests" : undefined}
                onAction={searchTerm ? () => setSearchTerm("") : statusFilter !== "all" ? () => setStatusFilter("all") : undefined}
              />
            )}
          </div>
        </div>
      </AdminLayout>
      
      {/* Rejection Dialog */}
      {selectedUser && (
        <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Reject User Request</DialogTitle>
              <DialogDescription>
                Please provide a reason for rejecting this request
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-1">
                <p className="font-medium">{selectedUser.userEmail}</p>
                {selectedUser.displayName && (
                  <p className="text-sm text-muted-foreground">{selectedUser.displayName}</p>
                )}
                <p className="text-sm">
                  Requested role: <span className="font-medium">{selectedUser.requestedRole}</span>
                  {selectedUser.company && (
                    <span> for company: <span className="font-medium">{selectedUser.company}</span></span>
                  )}
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="reason">Reason for rejection</Label>
                <Textarea
                  id="reason"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="Please provide a reason for rejecting this request"
                  rows={4}
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => setShowReviewDialog(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button 
                type="button"
                variant="outline"
                onClick={handleRejectUser}
                disabled={submitting || !rejectionReason.trim()}
              >
                {submitting ? <><Spinner className="mr-2" size="sm" /> Rejecting...</> : 'Reject Request'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </AdminGuard>
  );
}
