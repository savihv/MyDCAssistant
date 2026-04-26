import { useState, useEffect, useCallback } from 'react';
import { useCurrentUser } from 'app';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Spinner } from './Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { userManagementClient } from 'utils/userManagementClient';
import { Progress } from '@/components/ui/progress';

interface UserManagementProps {
  systemAdmin?: boolean;
}

export function UserManagement({ systemAdmin = false }: UserManagementProps) {
  const { user } = useCurrentUser();
  const role = (user as any)?.customClaims?.role || 'technician';
  const company = (user as any)?.customClaims?.company || '';
  
  // State for users and pending requests
  const [pendingRequests, setPendingRequests] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pending');
  
  // State for available domains
  const [availableDomains, setAvailableDomains] = useState<Record<string, string>>({});
  const [domainDialogOpen, setDomainDialogOpen] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState('');
  
  // State for the rejection dialog
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [selectedUserId, setSelectedUserId] = useState('');
  
  // Filter states
  const [filterText, setFilterText] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [companyFilter, setCompanyFilter] = useState<string>('all');
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);
  
  // Fetch pending requests and users
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch pending requests from backend API
      const pendingUsers = await userManagementClient.getPendingUsers();
      setPendingRequests(pendingUsers);
      
      // Fetch all users from backend API
      const allUsers = await userManagementClient.getAllUsers();
      setUsers(allUsers);
      
      // Fetch available domains
      const domains = await userManagementClient.getAvailableDomains();
      setAvailableDomains(domains);
      
      // Reset pagination when data changes
      setCurrentPage(1);
    } catch (error) {
      console.error('Error fetching user data:', error);
      toast.error('Failed to load user data');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user, fetchData]);
  
  // Handle approving a user
  const handleApproveUser = async (uid: string) => {
    try {
      setLoading(true);
      
      await userManagementClient.approveRejectUser({
        userId: uid,
        approve: true
      });
      
      toast.success('User approved successfully');
      fetchData(); // Refresh data
    } catch (error) {
      console.error('Error approving user:', error);
      toast.error('Failed to approve user');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle opening rejection dialog
  const handleOpenRejectionDialog = (uid: string) => {
    setSelectedUserId(uid);
    setRejectionReason('');
    setRejectionDialogOpen(true);
  };
  
  // Handle rejecting a user
  const handleRejectUser = async () => {
    if (!selectedUserId) return;
    
    try {
      setLoading(true);
      
      await userManagementClient.approveRejectUser({
        userId: selectedUserId,
        approve: false,
        rejectionReason: rejectionReason
      });
      
      toast.success('User request rejected');
      setRejectionDialogOpen(false);
      fetchData(); // Refresh data
    } catch (error) {
      console.error('Error rejecting user:', error);
      toast.error('Failed to reject user');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle opening domain dialog
  const handleOpenDomainDialog = (userId: string, currentDomain?: string) => {
    setSelectedUserId(userId);
    setSelectedDomain(currentDomain || '');
    setDomainDialogOpen(true);
  };

  // Handle assigning domain
  const handleAssignDomain = async () => {
    if (!selectedUserId || !selectedDomain) return;

    try {
      setLoading(true);
      await userManagementClient.assignUserDomain(selectedUserId, selectedDomain);
      toast.success('Domain assigned successfully');
      setDomainDialogOpen(false);
      fetchData(); // Refresh data
    } catch (error) {
      console.error('Error assigning domain:', error);
      toast.error('Failed to assign domain');
    } finally {
      setLoading(false);
    }
  };
  
  // Get unique companies for filter dropdown
  const uniqueCompanies = ['all', ...new Set(users.map(user => user.company).filter(Boolean))];

  // Filter users based on all criteria
  const filteredPendingRequests = pendingRequests.filter(request => {
    // Text search filter
    const matchesText = !filterText || [
      request.displayName,
      request.userEmail,
      request.company
    ].some(field => field?.toLowerCase().includes(filterText.toLowerCase()));
    
    // Role filter
    const matchesRole = roleFilter === 'all' || request.requestedRole === roleFilter;
    
    // Status filter - pending requests are always pending
    const matchesStatus = statusFilter === 'all' || statusFilter === 'pending_approval';
    
    // Company filter
    const matchesCompany = companyFilter === 'all' || request.company === companyFilter;
    
    return matchesText && matchesRole && matchesStatus && matchesCompany;
  });
  
  const filteredUsers = users.filter(user => {
    // Text search filter
    const matchesText = !filterText || [
      user.displayName,
      user.email,
      user.company,
      user.role
    ].some(field => field?.toLowerCase().includes(filterText.toLowerCase()));
    
    // Role filter
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    
    // Status filter
    const matchesStatus = statusFilter === 'all' || user.approvalStatus === statusFilter;
    
    // Company filter
    const matchesCompany = companyFilter === 'all' || user.company === companyFilter;
    
    return matchesText && matchesRole && matchesStatus && matchesCompany;
  });
  
  // Calculate pagination for users
  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage);
  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );
  
  // UI helpers
  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'system_admin':
        return <Badge className="bg-purple-600">System Admin</Badge>;
      case 'company_admin':
        return <Badge className="bg-blue-600">Company Admin</Badge>;
      case 'technician':
        return <Badge className="bg-green-600">Technician</Badge>;
      default:
        return <Badge className="bg-gray-600">{role}</Badge>;
    }
  };
  
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <Badge className="bg-green-600">Approved</Badge>;
      case 'pending_approval':
      case 'pending':
        return <Badge className="bg-yellow-600">Pending</Badge>;
      case 'rejected':
        return <Badge className="bg-red-600">Rejected</Badge>;
      default:
        return <Badge className="bg-gray-600">{status}</Badge>;
    }
  };
  
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight">
          User Management
        </h2>
        <p className="text-muted-foreground">
          {systemAdmin ? 'Manage user access across the platform' : 'Manage technicians in your company'}
        </p>
      </div>
      
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <Input 
            placeholder="Search users..."
            className="w-full md:w-1/3"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
          
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 w-full md:w-2/3">
            {/* Role Filter */}
            <div className="space-y-1">
              <Label htmlFor="roleFilter">Role</Label>
              <select
                id="roleFilter"
                className="w-full border border-gray-600 rounded p-2 bg-gray-800 text-white"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <option value="all">All Roles</option>
                <option value="system_admin">System Admin</option>
                <option value="company_admin">Company Admin</option>
                <option value="technician">Technician</option>
              </select>
            </div>
            
            {/* Status Filter */}
            <div className="space-y-1">
              <Label htmlFor="statusFilter">Status</Label>
              <select
                id="statusFilter"
                className="w-full border border-gray-600 rounded p-2 bg-gray-800 text-white"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Statuses</option>
                <option value="approved">Approved</option>
                <option value="pending_approval">Pending</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
            
            {/* Company Filter - Only show for system admins */}
            {systemAdmin && uniqueCompanies.length > 1 && (
              <div className="space-y-1">
                <Label htmlFor="companyFilter">Company</Label>
                <select
                  id="companyFilter"
                  className="w-full border border-gray-600 rounded p-2 bg-gray-800 text-white"
                  value={companyFilter}
                  onChange={(e) => setCompanyFilter(e.target.value)}
                >
                  {uniqueCompanies.map((company, index) => (
                    <option key={index} value={company}>
                      {company === 'all' ? 'All Companies' : company}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>
        
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-gray-700">
              {activeTab === 'pending' ? filteredPendingRequests.length : filteredUsers.length} results
            </Badge>
            {(filterText || roleFilter !== 'all' || statusFilter !== 'all' || companyFilter !== 'all') && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => {
                  setFilterText('');
                  setRoleFilter('all');
                  setStatusFilter('all');
                  setCompanyFilter('all');
                  setCurrentPage(1);
                }}
              >
                Clear filters
              </Button>
            )}
          </div>
          <Button variant="outline" onClick={fetchData}>
            Refresh
          </Button>
        </div>
      </div>
      
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="pending">
            Pending Requests 
            {pendingRequests.length > 0 && (
              <Badge className="ml-2 bg-yellow-600">{pendingRequests.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="users">All Users</TabsTrigger>
        </TabsList>
        
        <TabsContent value="pending" className="mt-6">
          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner size="lg" />
            </div>
          ) : filteredPendingRequests.length === 0 ? (
            <div className="text-center py-8 border rounded-md bg-gray-800">
              <p className="text-muted-foreground">
                {(filterText || roleFilter !== 'all' || statusFilter !== 'all' || companyFilter !== 'all') 
                  ? 'No pending requests match your filters' 
                  : 'No pending approval requests'}
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredPendingRequests.map((request) => (
                <Card key={request.id}>
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle>{request.displayName}</CardTitle>
                        <CardDescription>{request.userEmail}</CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {getRoleBadge(request.requestedRole)}
                        {getStatusBadge(request.status)}
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium">Company</p>
                        <p className="text-sm text-muted-foreground">
                          {request.company || '-'}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm font-medium">Requested At</p>
                        <p className="text-sm text-muted-foreground">
                          {userManagementClient.formatDate(request.requestedAt)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex justify-end space-x-2 mt-4">
                      <Button 
                        variant="outline" 
                        onClick={() => handleOpenRejectionDialog(request.id)}
                      >
                        Reject
                      </Button>
                      <Button 
                        variant="default" 
                        onClick={() => handleApproveUser(request.id)}
                      >
                        Approve
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
        
        <TabsContent value="users" className="mt-6">
          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner size="lg" />
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center py-8 border rounded-md bg-gray-800">
              <p className="text-muted-foreground">
                {(filterText || roleFilter !== 'all' || statusFilter !== 'all' || companyFilter !== 'all') 
                  ? 'No users match your filters' 
                  : 'No users found'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="py-3 px-4 text-left">Name</th>
                    <th className="py-3 px-4 text-left">Email</th>
                    <th className="py-3 px-4 text-left">Company</th>
                    <th className="py-3 px-4 text-left">Role</th>
                    <th className="py-3 px-4 text-left">Domain</th>
                    <th className="py-3 px-4 text-left">Status</th>
                    <th className="py-3 px-4 text-left">Created</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedUsers.map((user) => (
                    <tr key={user.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                      <td className="py-3 px-4">{user.displayName || '-'}</td>
                      <td className="py-3 px-4">{user.email}</td>
                      <td className="py-3 px-4">{user.company || '-'}</td>
                      <td className="py-3 px-4">{getRoleBadge(user.role)}</td>
                      <td className="py-3 px-4">
                        {user.assignedDomain ? (
                          <Badge variant="outline">{availableDomains[user.assignedDomain] || user.assignedDomain}</Badge>
                        ) : (
                          <span className="text-gray-500 text-sm">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4">{getStatusBadge(user.approvalStatus)}</td>
                      <td className="py-3 px-4">
                        {userManagementClient.formatDate(user.createdAt)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenDomainDialog(user.uid, user.assignedDomain)}
                        >
                          Assign Domain
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {/* Pagination controls */}
              {totalPages > 1 && (
                <div className="flex justify-center mt-6 space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  
                  <div className="flex items-center space-x-1">
                    {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                      // Show 5 pages max with the current page centered
                      let pageNum;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }
                      return (
                        <Button
                          key={pageNum}
                          variant={currentPage === pageNum ? "default" : "outline"}
                          size="sm"
                          className="w-8 h-8 p-0"
                          onClick={() => setCurrentPage(pageNum)}
                        >
                          {pageNum}
                        </Button>
                      );
                    })}
                  </div>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </Button>
                </div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
      
      {/* Rejection Dialog */}
      <Dialog open={rejectionDialogOpen} onOpenChange={setRejectionDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject User Request</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this user request. This will be visible to the user.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="rejectionReason">Rejection Reason</Label>
              <Textarea
                id="rejectionReason"
                placeholder="Explain why this request is being rejected"
                rows={3}
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setRejectionDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button 
              variant="outline" 
              onClick={handleRejectUser}
              disabled={!rejectionReason.trim()}
            >
              Reject Request
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Domain Assignment Dialog */}
      <Dialog open={domainDialogOpen} onOpenChange={setDomainDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign Domain</DialogTitle>
            <DialogDescription>
              Assign a knowledge domain to this user. This determines which constraints and knowledge base they access.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="domainSelect">Select Domain</Label>
              <Select value={selectedDomain} onValueChange={setSelectedDomain}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a domain" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(availableDomains)
                    .filter(([key]) => key && key.length > 0)
                    .map(([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setDomainDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button 
              variant="default" 
              onClick={handleAssignDomain}
              disabled={!selectedDomain}
            >
              Save Assignment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
