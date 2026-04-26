import { AdminLayout } from "../components/AdminLayout";
import React, { useState, useEffect } from 'react';
import { apiClient } from "../app";
import { useUserRoles } from "../utils/useUserRoles";

// Types for our dashboard
interface User {
  uid: string;
  email: string;
  displayName?: string;
  role?: string;
  requestedRole?: string;
  company?: string;
  status: 'active' | 'pending' | 'inactive';
  created?: string;
  requestedAt?: { seconds: number; nanoseconds: number };
}

interface MetricsState {
  totalDocuments: number;
  totalFeedback: number;
  totalUsers: number;
  totalCompanies: number; // Add this line
  totalResponses: number;
  ragUsageRate: number;
  documentsPerCompany: Record<string, number>;
  webSearchUsageRate: number;
  usersByRole?: {
    system_admin: number;
    company_admin: number;
    technician: number;
  };
}

const SystemAdminDashboard: React.FC = () => {
  // State management
  const [metrics, setMetrics] = useState<MetricsState>({
    totalDocuments: 0,
    totalFeedback: 0,
    totalUsers: 0,
    totalCompanies: 0, // Add this line
    totalResponses: 0,
    ragUsageRate: 0,
    documentsPerCompany: {},
    webSearchUsageRate: 0,
    usersByRole: {
      system_admin: 0,
      company_admin: 0,
      technician: 0
    }
  });
  const [pendingUsers, setPendingUsers] = useState<User[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState({
    metrics: true,
    pendingUsers: true,
    allUsers: true
  });
  const [error, setError] = useState<string | null>(null);
  const [processingUsers, setProcessingUsers] = useState<string[]>([]);
  const { isSystemAdmin } = useUserRoles();

  // Filter state for user directory
  const [userFilter, setUserFilter] = useState({
    role: 'all',
    searchTerm: ''
  });

  // Fetch metrics data
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        console.log("SystemAdminDashboard - Fetching metrics data");
        setLoading(prev => ({ ...prev, metrics: true }));
        
        const response = await apiClient.get_admin_metrics({});
        console.log("SystemAdminDashboard - Metrics response:", response);
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("SystemAdminDashboard - Metrics data:", data);
        
        setMetrics(data);
      } catch (err) {
        console.error("SystemAdminDashboard - Error fetching metrics:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(prev => ({ ...prev, metrics: false }));
      }
    };

    fetchMetrics();
  }, []);

  // Fetch pending users
  useEffect(() => {
    const fetchPendingUsers = async () => {
      try {
        console.log("SystemAdminDashboard - Fetching pending users");
        setLoading(prev => ({ ...prev, pendingUsers: true }));
        
        const response = await apiClient.get_pending_users();
        
        if (response.status !== 200) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("SystemAdminDashboard - Pending users:", data);
        
        // Transform API data into our User format with robust fallbacks
        const pendingUsersList = data.users.map((user: any) => ({
          uid: user.uid || user.id || '',  // Use id as fallback when uid is empty
          email: user.userEmail || user.email || '',
          displayName: user.displayName || (user.userEmail ? user.userEmail.split('@')[0] : (user.email ? user.email.split('@')[0] : '')),
          requestedRole: user.requestedRole || user.role || 'technician',
          status: 'pending' as const,
          requestedAt: user.requestedAt,
          created: user.requestedAt?.seconds ? new Date(user.requestedAt.seconds * 1000).toISOString() : 
                 (user.createdAt?.seconds ? new Date(user.createdAt.seconds * 1000).toISOString() : '')
        }));
        
        console.log("SystemAdminDashboard - Transformed pending users:", pendingUsersList);
        setPendingUsers(pendingUsersList);
      } catch (err) {
        console.error("SystemAdminDashboard - Error fetching pending users:", err);
        setError(err instanceof Error ? err.message : "Unknown error fetching pending users");
      } finally {
        setLoading(prev => ({ ...prev, pendingUsers: false }));
      }
    };

    fetchPendingUsers();
  }, []);

  // Fetch all users
  useEffect(() => {
    const fetchAllUsers = async () => {
      try {
        console.log("SystemAdminDashboard - Fetching all users");
        setLoading(prev => ({ ...prev, allUsers: true }));
        
        const response = await apiClient.get_all_users({});
        
        if (response.status !== 200) {
          throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("SystemAdminDashboard - All users:", data);
        
        // Transform API data into our User format with standardized status handling
        const allUsersList = data.users.map((user: any) => ({
          uid: user.uid || user.id || '',
          email: user.email || user.userEmail || '',
          displayName: user.displayName || (user.email ? user.email.split('@')[0] : ''),
          role: user.role || 'unknown',
          company: user.company || '',
          // Standardize status handling for consistent UI display
          status: user.approvalStatus === 'approved' ? 'active' : 
                 user.approvalStatus === 'pending_approval' ? 'pending' : 
                 user.approvalStatus || 'pending',
          created: user.createdAt?.seconds ? new Date(user.createdAt.seconds * 1000).toISOString() : ''
        }));
        
        setAllUsers(allUsersList);
      } catch (err) {
        console.error("SystemAdminDashboard - Error fetching all users:", err);
        setError(err instanceof Error ? err.message : "Unknown error fetching users");
      } finally {
        setLoading(prev => ({ ...prev, allUsers: false }));
      }
    };

    fetchAllUsers();
  }, []);


  const determineUserStatus = (user: any): 'active' | 'pending' | 'inactive' => {
    if (user.approvalStatus === 'approved') return 'active';
    if (user.approvalStatus === 'pending_approval') return 'pending';
    if (user.approvalStatus === 'rejected') return 'inactive';
    if (user.status === 'pending') return 'pending';
    return 'pending'; // Default fallback
  };
  
  // Improved function to refetch both pending and all users with consistent data mapping
  const refreshUserData = async () => {
    try {
      // Reset loading state
      setLoading(prev => ({ ...prev, pendingUsers: true, allUsers: true }));
      
      // Fetch pending users again
      const pendingResponse = await apiClient.get_pending_users();
      if (pendingResponse.status === 200) {
        const data = await pendingResponse.json();
        console.log("Refresh - Pending users data:", data);
        
        // Transform data with robust fallbacks and consistent field mapping
        const pendingUsersList = data.users.map((user: any) => ({
          uid: user.uid || user.id || '',
          email: user.userEmail || user.email || '',
          displayName: user.displayName || (user.userEmail ? user.userEmail.split('@')[0] : (user.email ? user.email.split('@')[0] : '')),
          requestedRole: user.requestedRole || user.role || 'technician',
          status: 'pending' as const,
          requestedAt: user.requestedAt,
          created: user.requestedAt?.seconds ? new Date(user.requestedAt.seconds * 1000).toISOString() : 
                 (user.createdAt?.seconds ? new Date(user.createdAt.seconds * 1000).toISOString() : '')
        }));
        
        console.log("Refresh - Transformed pending users:", pendingUsersList);
        setPendingUsers(pendingUsersList);
      }


      // Fetch all users again
      const allUsersResponse = await apiClient.get_all_users({});
      if (allUsersResponse.status === 200) {
        const data = await allUsersResponse.json();
        console.log("Refresh - All users data:", data);
        
        // Transform data with robust fallbacks and consistent status mapping
        const allUsersList = data.users.map((user: any) => ({
          uid: user.uid || user.id || '',
          email: user.email || user.userEmail || '',
          displayName: user.displayName || (user.email ? user.email.split('@')[0] : ''),
          role: user.role || 'unknown',
          company: user.company || '',
          // Standardize status handling for consistent UI display
          status: determineUserStatus(user),
          created: user.createdAt?.seconds ? new Date(user.createdAt.seconds * 1000).toISOString() : 
                 (user.metadata?.creationTime || '')
        }));
        
        console.log("Refresh - Transformed all users:", allUsersList);
        setAllUsers(allUsersList);
      }
    } catch (err) {
      console.error("Error refreshing user data:", err);
      setError(err instanceof Error ? err.message : "Failed to refresh user data");
    } finally {
      setLoading(prev => ({ ...prev, pendingUsers: false, allUsers: false }));
    }
  };

  // Enhanced user approval handler with better error handling, consistent parameter naming, and robust validation
  const handleUserApproval = async (uid: string, approve: boolean, role: string = 'technician') => {
    console.log("DEBUG - Processing user with ID:", uid, "| Approve:", approve, "| Role:", role);
    
    if (!uid) {
      setError("Cannot process user: Missing user ID");
      return;
    }
  
    try {
      // Add user to processing state to show UI feedback
      setProcessingUsers(prev => [...prev, uid]);
      setError(null);
      
      // Log detailed parameters for debugging
      console.log('Approval request parameters:', {
        userId: uid,
        approve: approve,
        rejectionReason: approve ? undefined : 'Rejected by system admin',
        role: approve ? role : undefined,
      });

      // Call the direct_approve_user endpoint
      const response = await apiClient.direct_approve_user({
        uid: uid,
        approved: approve,
        rejection_reason: approve ? undefined : "Rejected by system admin",
      });

      console.log("Direct approval API response:", response);

      if (response.status !== 200) {
        const errorData = await response.json();
        throw new Error(`API Error: ${errorData.message || 'Failed to process request'}`);
      }

      // On success, remove user from pending list and refresh all users
      setPendingUsers(prev => prev.filter(user => user.uid !== uid));
      await refreshUserData();

    } catch (err) {
      console.error("Error processing user approval:", err);
      setError(err instanceof Error ? err.message : "Unknown error processing user");
    } finally {
      // Always remove the user from the processing state
      setProcessingUsers(prev => prev.filter(id => id !== uid));
    }
  };


  // Handle filtering of users in the user directory
  const filteredUsers = allUsers.filter(user => {
    const roleMatch = userFilter.role === 'all' || user.role === userFilter.role;
    const searchTermMatch = userFilter.searchTerm === '' ||
      user.email.toLowerCase().includes(userFilter.searchTerm.toLowerCase()) ||
      (user.displayName && user.displayName.toLowerCase().includes(userFilter.searchTerm.toLowerCase())) ||
      (user.company && user.company.toLowerCase().includes(userFilter.searchTerm.toLowerCase()));
    return roleMatch && searchTermMatch;
  });

  return (
    <AdminLayout activeTab="dashboard">
      <div className="container mx-auto p-4 md:p-6">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100">System Admin Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400">Overview of system metrics and user management</p>
        </header>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
            <strong className="font-bold">Error: </strong>
            <span className="block sm:inline">{error}</span>
            <span className="absolute top-0 bottom-0 right-0 px-4 py-3" onClick={() => setError(null)}>
              <svg className="fill-current h-6 w-6 text-red-500" role="button" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><title>Close</title><path d="M14.348 14.849a1.2 1.2 0 0 1-1.697 0L10 11.819l-2.651 3.029a1.2 1.2 0 1 1-1.697-1.697l2.758-3.15-2.759-3.152a1.2 1.2 0 1 1 1.697-1.697L10 8.183l2.651-3.031a1.2 1.2 0 1 1 1.697 1.697l-2.758 3.152 2.758 3.15a1.2 1.2 0 0 1 0 1.698z"/></svg>
            </span>
          </div>
        )}

        {/* Metrics Section */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          <MetricCard title="Total Users" value={metrics.totalUsers} loading={loading.metrics} />
          <MetricCard title="Total Companies" value={metrics.totalCompanies} loading={loading.metrics} />
          <MetricCard title="Total Documents" value={metrics.totalDocuments} loading={loading.metrics} />
        </section>

        {/* User Approval Section */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">Pending User Approvals</h2>
          {loading.pendingUsers ? (
            <div className="flex justify-center p-8"><div className="w-8 h-8 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div></div>
          ) : pendingUsers.length > 0 ? (
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">User</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Requested Role</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Requested At</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {pendingUsers.map(user => (
                    <tr key={user.uid} className={`transition-opacity ${processingUsers.includes(user.uid) ? 'opacity-50' : ''}`}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{user.displayName}</div>
                          <div className="text-sm text-gray-500 dark:text-gray-400 ml-4">{user.email}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                          {user.requestedRole}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                         {user.requestedAt ? new Date(user.requestedAt.seconds * 1000).toLocaleString() : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => handleUserApproval(user.uid, true, user.requestedRole)}
                          disabled={processingUsers.includes(user.uid)}
                          className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleUserApproval(user.uid, false)}
                          disabled={processingUsers.includes(user.uid)}
                          className="ml-4 text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-600 dark:text-gray-400">No pending user approvals.</p>
          )}
        </section>

        {/* User Directory Section */}
        <section>
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">User Directory</h2>
          
          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4 mb-4">
            <input
              type="text"
              placeholder="Search by name, email, or company..."
              value={userFilter.searchTerm}
              onChange={e => setUserFilter(prev => ({ ...prev, searchTerm: e.target.value }))}
              className="flex-grow p-2 border rounded-md bg-white dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-indigo-500"
            />
            <select
              value={userFilter.role}
              onChange={e => setUserFilter(prev => ({ ...prev, role: e.target.value }))}
              className="p-2 border rounded-md bg-white dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Roles</option>
              <option value="system_admin">System Admin</option>
              <option value="company_admin">Company Admin</option>
              <option value="technician">Technician</option>
            </select>
          </div>

          {loading.allUsers ? (
            <div className="flex justify-center p-8"><div className="w-8 h-8 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div></div>
          ) : (
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Name</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Company</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Role & Status</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Joined</th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredUsers.map(user => (
                    <tr key={user.uid}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{user.displayName}</div>
                          <div className="text-sm text-gray-500 dark:text-gray-400 ml-4">{user.email}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{user.company || 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${user.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                          {user.role}
                        </span>
                        <span className={`ml-2 px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          user.status === 'active' ? 'bg-green-100 text-green-800' :
                          user.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {user.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {user.created ? new Date(user.created).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </AdminLayout>
  );
};

// Helper component for metric cards
const MetricCard: React.FC<{ title: string; value: number | string; loading: boolean }> = ({ title, value, loading }) => (
  <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6 flex flex-col justify-between">
    <h3 className="text-lg font-medium text-gray-600 dark:text-gray-400">{title}</h3>
    {loading ? (
      <div className="flex justify-center items-center h-16">
        <div className="w-6 h-6 border-2 border-blue-500 border-dashed rounded-full animate-spin"></div>
      </div>
    ) : (
      <p className="text-4xl font-bold text-gray-900 dark:text-gray-100 mt-2">{value}</p>
    )}
  </div>
);

export default SystemAdminDashboard;
