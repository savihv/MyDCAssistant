import { useState, useEffect, useCallback } from "react";
import { firebaseApp } from "../app"; // Removed useCurrentUser
import { useUserRoles } from "../utils/useUserRoles"; // Added useUserRoles
import { getFirestore, collection, getDocs, query, where, orderBy, limit, startAfter, doc, updateDoc, Timestamp } from "firebase/firestore";
import { AdminGuard } from "../components/AdminGuard";
import { AdminLayout } from "../components/AdminLayout";
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { Spinner } from "../components/Spinner";
import { Card } from "../extensions/shadcn/components/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../extensions/shadcn/components/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../extensions/shadcn/components/select";
import { Label } from "../extensions/shadcn/components/label";
import { Badge } from "../extensions/shadcn/components/badge";
import { toast } from "sonner";
import { apiClient } from "../app";
import { AdminEmptyState } from "../components/AdminEmptyState";
import { User } from "lucide-react";

interface User {
  id: string;
  email: string;
  displayName?: string;
  company?: string;
  organization?: string;
  role: "technician" | "company_admin" | "system_admin";
  createdAt: string;
  lastLogin?: string;
  disabled: boolean;
}

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  // Renamed loading to pageLoading to avoid conflict with userRolesLoading
  const [pageLoading, setPageLoading] = useState(true); 
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userForm, setUserForm] = useState({
    role: "",
    company: "",
    organization: "",
    disabled: false
  });
  const [submitting, setSubmitting] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [lastDoc, setLastDoc] = useState<any>(null);
  const [hasMore, setHasMore] = useState(false);
  
  // Use useUserRoles hook for consistent role management
  const {
    role, // Actual role string
    isSystemAdmin,
    // company, // company from useUserRoles might be useful if fetching users per company for company_admin
    loading: userRolesLoading // Combined loading state for user and claims
  } = useUserRoles();
  const db = getFirestore(firebaseApp);

  // Function to fetch users
  const fetchUsers = useCallback(async (startAfterDoc: any = null) => {
    // Wait for roles to be loaded and ensure user is a system admin
    if (userRolesLoading) return; // Don't fetch if roles are still loading

    if (!isSystemAdmin) {
      // This toast might be redundant if AdminGuard handles it, but can be a quick feedback
      // toast.error("You don't have permission to access this page");
      // setPageLoading(false); // Ensure loading stops if we can't proceed
      return; // Critical: Exit if not system admin or roles not loaded
    }
    
    setPageLoading(true); // Start page loading for this fetch operation
    try {
      
      // Base query
      let usersRef = collection(db, 'users');
      let constraints: any[] = [orderBy('createdAt', 'desc')];
      
      // Apply role filter if not 'all'
      if (roleFilter !== 'all') {
        constraints.push(where('role', '==', roleFilter));
      }
      
      // Apply pagination
      if (startAfterDoc) {
        constraints.push(startAfter(startAfterDoc));
      }
      
      // Apply limit
      constraints.push(limit(10));
      
      // Execute query
      const q = query(usersRef, ...constraints);
      const snapshot = await getDocs(q);
      
      // Check if there are more documents
      const lastVisible = snapshot.docs[snapshot.docs.length - 1];
      setLastDoc(lastVisible);
      setHasMore(snapshot.docs.length === 10);
      
      // Process documents
      const fetchedUsers = snapshot.docs.map(doc => {
        const data = doc.data();
        return {
          id: doc.id,
          ...data,
          createdAt: data.createdAt instanceof Timestamp ? 
            data.createdAt.toDate().toISOString() : data.createdAt,
          lastLogin: data.lastLogin instanceof Timestamp ? 
            data.lastLogin.toDate().toISOString() : data.lastLogin,
        } as User;
      });
      
      // Update state
      if (startAfterDoc) {
        setUsers(prev => [...prev, ...fetchedUsers]);
      } else {
        setUsers(fetchedUsers);
      }
      
    } catch (error) {
      console.error("Error fetching users:", error);
      toast.error("Failed to load users");
    } finally {
      setPageLoading(false); // Stop page loading regardless of outcome
    }
  }, [db, roleFilter, isSystemAdmin, userRolesLoading]); // Added userRolesLoading to dependencies

  // Initial load and re-fetch on filter change
  useEffect(() => {
    // Only fetch if roles are loaded and user is system admin
    if (!userRolesLoading && isSystemAdmin) {
      setUsers([]); // Clear previous users when filter changes or on initial load for system admin
      setLastDoc(null); // Reset pagination
      fetchUsers();
    }
    // If not system admin after roles are loaded, ensure loading is false and users are empty
    else if (!userRolesLoading && !isSystemAdmin) {
      setPageLoading(false);
      setUsers([]);
    }
  }, [fetchUsers, roleFilter, isSystemAdmin, userRolesLoading]); // Added userRolesLoading and isSystemAdmin

  // Function to handle user edit
  const handleEditUser = (user: User) => {
    setSelectedUser(user);
    setUserForm({
      role: user.role,
      company: user.company || "",
      organization: user.organization || "",
      disabled: user.disabled
    });
    setShowEditDialog(true);
  };

  // Function to save user changes
  const handleSaveUser = async () => {
    if (!selectedUser) return;
    
    try {
      setSubmitting(true);
      
      // Call API to update user
      const response = await (apiClient as any).update_user_roles(
        { uid: selectedUser.id },
        { 
          role: userForm.role as "technician" | "company_admin" | "system_admin",
          company: userForm.company || null,
          organization: userForm.organization || null,
          disabled: userForm.disabled
        }
      );
      
      if (!response.ok) {
        throw new Error(`Failed to update user: ${response.statusText}`);
      }
      
      // Update local state
      setUsers(prev => 
        prev.map(u => 
          u.id === selectedUser.id 
            ? { ...u, ...userForm, role: userForm.role as "technician" | "company_admin" | "system_admin" } 
            : u
        )
      );
      
      // Reset state and close dialog
      setSelectedUser(null);
      setShowEditDialog(false);
      
      toast.success("User updated successfully");
    } catch (error) {
      console.error("Error updating user:", error);
      toast.error("Failed to update user");
    } finally {
      setSubmitting(false);
    }
  };

  // Function to handle load more
  const handleLoadMore = () => {
    if (lastDoc) {
      fetchUsers(lastDoc);
    }
  };

  // Filter users by search term
  const filteredUsers = users.filter(user => {
    if (!searchTerm) return true;
    
    const search = searchTerm.toLowerCase();
    return (
      user.email?.toLowerCase().includes(search) ||
      user.displayName?.toLowerCase().includes(search) ||
      user.company?.toLowerCase().includes(search) ||
      user.organization?.toLowerCase().includes(search) ||
      user.role?.toLowerCase().includes(search)
    );
  });

  // Guard for non-system admins or while roles are loading.
  // AdminGuard will handle the redirection/message if not system_admin after roles are loaded.
  // This primarily handles the page-specific loading state until roles are confirmed.
  if (userRolesLoading) {
    return (
      <AdminGuard allowedRoles={['system_admin']}> {/* Still good to keep AdminGuard for overall structure */}
        <AdminLayout activeTab="users">
          <div className="flex justify-center items-center h-64">
            <Spinner size="lg" />
          </div>
        </AdminLayout>
      </AdminGuard>
    );
  }

  // If, after roles are loaded, the user is NOT a system admin, 
  // AdminGuard would have redirected. If for some reason it didn't, 
  // or if we want a specific message here before AdminGuard acts:
  if (!isSystemAdmin) {
     // AdminGuard should handle the visual block/redirect. 
     // This state is mostly for preventing API calls or rendering sensitive data prematurely.
     // The toast in fetchUsers or a message from AdminGuard would be the user-facing error.
    return (
        <AdminGuard allowedRoles={['system_admin']}>
            <AdminLayout activeTab="users">
                 <div className="flex justify-center items-center h-64">
                     <p className="text-muted-foreground">Loading access permissions...</p>
                 </div>
            </AdminLayout>
        </AdminGuard>
    ); 
  }

  return (
    <AdminGuard allowedRoles={['system_admin']}>
      <AdminLayout activeTab="users">
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
            <p className="text-muted-foreground">
              Manage user roles and permissions across the platform
            </p>
          </div>
          
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <div className="flex-1">
              <Input 
                placeholder="Search users..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <Select 
              value={roleFilter} 
              onValueChange={setRoleFilter}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="technician">Technicians</SelectItem>
                <SelectItem value="company_admin">Company Admins</SelectItem>
                <SelectItem value="system_admin">System Admins</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {/* User List */}
          <div className="space-y-4">
            {pageLoading && users.length === 0 ? (
              <div className="flex justify-center items-center h-64">
                <Spinner size="lg" />
              </div>
            ) : filteredUsers.length === 0 ? (
              <AdminEmptyState 
                title="No users found"
                description={searchTerm ? 
                  `No users match your search criteria "${searchTerm}".` : 
                  `No users found in the selected role filter.`}
                icon={<User className="h-6 w-6" />}
                actionLabel={searchTerm ? "Clear search" : roleFilter !== "all" ? "Show all roles" : undefined}
                onAction={searchTerm ? 
                  () => setSearchTerm("") : 
                  roleFilter !== "all" ? () => setRoleFilter("all") : undefined}
              />
            ) : (
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
                            {user.displayName || user.email}
                            {user.disabled && (
                              <Badge variant="outline" className="ml-2 text-muted-foreground">Disabled</Badge>
                            )}
                          </h3>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                          
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Badge className={
                              user.role === 'system_admin' ? 'bg-purple-500/20 text-purple-600 hover:bg-purple-500/30' :
                              user.role === 'company_admin' ? 'bg-blue-500/20 text-blue-600 hover:bg-blue-500/30' :
                              'bg-gray-500/20 text-gray-600 hover:bg-gray-500/30'
                            }>
                              {user.role === 'system_admin' ? 'System Admin' :
                               user.role === 'company_admin' ? 'Company Admin' : 'Technician'}
                            </Badge>
                            
                            {user.company && (
                              <Badge variant="outline">{user.company}</Badge>
                            )}
                            
                            {user.organization && (
                              <Badge variant="outline" className="text-muted-foreground">{user.organization}</Badge>
                            )}
                          </div>
                          
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span>
                              Created: {new Date(user.createdAt).toLocaleDateString()}
                            </span>
                            {user.lastLogin && (
                              <span className="border-l border-border pl-2">
                                Last login: {new Date(user.lastLogin).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      <div>
                        <Button 
                          onClick={() => handleEditUser(user)}
                          variant="outline"
                        >
                          Edit User
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
            
            {pageLoading && users.length > 0 && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}
            
            {!pageLoading && hasMore && (
              <div className="flex justify-center pt-4">
                <Button variant="outline" onClick={handleLoadMore}>
                  Load More
                </Button>
              </div>
            )}
          </div>
        </div>
      </AdminLayout>
      
      {/* Edit User Dialog */}
      {selectedUser && (
        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Edit User</DialogTitle>
              <DialogDescription>
                Update user role and permissions
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-1">
                <p className="font-medium">{selectedUser.email}</p>
                {selectedUser.displayName && (
                  <p className="text-sm text-muted-foreground">{selectedUser.displayName}</p>
                )}
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="role">User Role</Label>
                <Select 
                  value={userForm.role} 
                  onValueChange={(value) => setUserForm({...userForm, role: value})}
                >
                  <SelectTrigger id="role">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="technician">Technician</SelectItem>
                    <SelectItem value="company_admin">Company Admin</SelectItem>
                    <SelectItem value="system_admin">System Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="company">Company</Label>
                <Input 
                  id="company"
                  value={userForm.company}
                  onChange={(e) => setUserForm({...userForm, company: e.target.value})}
                  placeholder="Company name"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="organization">Organization</Label>
                <Input 
                  id="organization"
                  value={userForm.organization}
                  onChange={(e) => setUserForm({...userForm, organization: e.target.value})}
                  placeholder="Organization/department name"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="disabled"
                  checked={userForm.disabled}
                  onChange={(e) => setUserForm({...userForm, disabled: e.target.checked})}
                  className="h-4 w-4 rounded border-gray-300 focus:ring-primary"
                />
                <Label htmlFor="disabled" className="text-sm font-normal">
                  Disable user account
                </Label>
              </div>
            </div>
            
            <DialogFooter>
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => setShowEditDialog(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button 
                type="button" 
                onClick={handleSaveUser}
                disabled={submitting}
              >
                {submitting ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </AdminGuard>
  );
}
