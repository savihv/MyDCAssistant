import { useState, useEffect, lazy, Suspense } from "react";
import React from "react";
import { useUserRoles } from "../utils/useUserRoles";
import { AdminGuard } from "../components/AdminGuard";
import { AdminLayout } from "../components/AdminLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Spinner } from "../components/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../extensions/shadcn/components/tabs";
import { Button } from "../components/Button";
import { Badge } from "../extensions/shadcn/components/badge";
import { UserManagement } from "../components/UserManagement";
import AuditLogViewer from "../components/AuditLogViewer";import { apiClient } from "../app"; // apiClient for API calls
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../extensions/shadcn/components/accordion";
import { Avatar, AvatarFallback, AvatarImage } from "../extensions/shadcn/components/avatar";

// ADDED: Local type definition for admin metrics to resolve import error.
interface AdminMetricsResponse {
  totalDocuments: number;
  totalFeedback: number;
  totalUsers: number;
  totalCompanies: number;
  totalResponses: number;
  ragUsageRate: number;
  documentsPerCompany: Record<string, number>;
  responseTimeAvg?: number | null;
  recentDocuments: Array<{
    id: string;
    title: string;
    company: string;
    status: string;
    createdAt: string;
  }>;
  usersByRole: {
    system_admin: number;
    company_admin: number;
    technician: number;
  };
}

// NEW: Define a type for a single user, to be used in our merged data.
interface CompanyUser {
  uid: string;
  name: string | null;
  email: string;
  role: string;
}

// NEW: Define the structure for our merged company data.
interface CompanyDetails {
  name: string;
  userCount: number;
  documentCount: number;
  users: CompanyUser[];
}

export default function AdminSystem() {
  // REFACTORED: Simplified state to hold API response and a separate loading flag
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  // NEW: State for all users and the final merged company details.
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [companyDetails, setCompanyDetails] = useState<CompanyDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  const {
    isSystemAdmin,
    loading: userRolesLoading
  } = useUserRoles();

  // REFACTORED: Replaced direct Firestore calls with a single, secure API call
  useEffect(() => {
    if (userRolesLoading || !isSystemAdmin) {
      if (!userRolesLoading) {
        setLoading(false);
      }
      return;
    }

    const fetchMetrics = async () => {
      setLoading(true);
      try {
        const response = await apiClient.get_admin_metrics({});
        if (!response.ok) {
          throw new Error("Failed to fetch admin metrics");
        }
        const data = await response.json();
        setMetrics(data);
      } catch (error) {
        console.error(error);
        toast.error("Could not load system metrics.");
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, [isSystemAdmin, userRolesLoading]);

  // NEW: Add a useEffect to fetch all users.
  useEffect(() => {
    const fetchAllUsers = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get_all_users({});
        if (!response.ok) {
          throw new Error("Failed to fetch users");
        }
        const data = await response.json();
        setAllUsers(data.users || []);
      } catch (error) {
        console.error(error);
        toast.error("Could not load user list.");
      } finally {
        setLoading(false);
      }
    };
    fetchAllUsers();
  }, []);

  // NEW: Add a useEffect to merge metrics and user data when they change.
  useEffect(() => {
    if (!metrics || allUsers.length === 0) {
      if (metrics && metrics.totalCompanies > 0 && allUsers.length === 0 && !loading) {
        // Handle case where there are companies but no users fetched yet
        const companyData = Object.keys(metrics.documentsPerCompany).map(
          (name) => ({
            name,
            userCount: 0,
            documentCount: metrics.documentsPerCompany[name],
            users: [],
          }),
        );
        setCompanyDetails(companyData);
      }
      return;
    }

    // Group users by company
    const usersByCompany: Record<string, CompanyUser[]> = allUsers.reduce(
      (acc, user) => {
        const companyName = user.company || "Unassigned";
        if (!acc[companyName]) {
          acc[companyName] = [];
        }
        acc[companyName].push({
          uid: user.uid,
          name: user.displayName,
          email: user.email,
          role: user.role || "N/A",
        });
        return acc;
      },
      {},
    );

    // Get document counts from metrics
    const docsPerCompany = metrics.documentsPerCompany || {};

    // Combine all company names from both datasets
    const allCompanyNames = new Set([
      ...Object.keys(usersByCompany),
      ...Object.keys(docsPerCompany),
    ]);

    // Create the final merged data structure
    const mergedDetails: CompanyDetails[] = Array.from(allCompanyNames).map(
      (name) => {
        const users = usersByCompany[name] || [];
        const documentCount = docsPerCompany[name] || 0;
        return {
          name,
          userCount: users.length,
          documentCount: documentCount,
          users: users,
        };
      },
    );

    setCompanyDetails(mergedDetails);
  }, [metrics, allUsers, loading]);

  if (userRolesLoading) {
    return (
      <AdminGuard allowedRoles={['system_admin']}>
        <AdminLayout activeTab="system">
          <div className="flex items-center justify-center h-[60vh]">
            <Spinner size="lg" />
          </div>
        </AdminLayout>
      </AdminGuard>
    );
  }

  if (!isSystemAdmin) {
    return (
      <AdminGuard allowedRoles={['system_admin']}>
        <AdminLayout activeTab="system">
          <div className="flex flex-col items-center justify-center h-[60vh]">
            <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
            <p className="text-muted-foreground mb-6">You do not have the necessary permissions to view this page.</p>
            <Button onClick={() => window.location.href = "/app"}>Go to App Home</Button>
          </div>
        </AdminLayout>
      </AdminGuard>
    );
  }
  
  const StatCard = ({
    title,
    value,
    isLoading,
  }: {
    title: string;
    value: number;
    isLoading: boolean;
  }) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">
          {title}
        </CardTitle>
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 text-muted-foreground">
          <path d="M18 21v-7a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v7" />
          <rect width="20" height="5" x="2" y="3" rx="1" />
          <path d="M4 8v13" />
          <path d="M20 8v13" />
        </svg>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-2xl font-bold">Loading...</div>
        ) : (
          <div className="text-2xl font-bold">{value}</div>
        )}
        <p className="text-xs text-muted-foreground">
          {title === "Total Companies" ? "Registered organizations" : title === "Total Users" ? "Across all companies" : "Total documents uploaded"}
        </p>
      </CardContent>
    </Card>
  );

  return (
    <AdminGuard allowedRoles={['system_admin']}>
      <AdminLayout activeTab="system">
        <div className="flex flex-col gap-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">System Administration</h1>
            <p className="text-muted-foreground">
              Manage global settings and view system-wide metrics
            </p>
          </div>
          
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="audit">Audit Logs</TabsTrigger>
              <TabsTrigger value="companies">Companies</TabsTrigger>
              <TabsTrigger value="users">User Management</TabsTrigger>
              <TabsTrigger value="settings">Global Settings</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                  title="Total Companies"
                  value={metrics?.totalCompanies ?? 0}
                  isLoading={loading}
                />
                <StatCard
                  title="Total Users"
                  value={metrics?.totalUsers ?? 0}
                  isLoading={loading}
                />
                <StatCard
                  title="Knowledge Base Documents"
                  value={metrics?.totalDocuments ?? 0}
                  isLoading={loading}
                />
              </div>
              {/* We can add more detailed charts and recent activity feeds here */}
            </TabsContent>
            <TabsContent value="companies" className="mt-4">
              {loading && companyDetails.length === 0 ? (
                <p className="text-center text-gray-500">Loading company data...</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {companyDetails.map((company) => (
                    <Card key={company.name} className="flex flex-col">
                      <CardHeader>
                        <CardTitle>{company.name}</CardTitle>
                        <CardDescription>
                          {company.userCount} Users | {company.documentCount}{" "}
                          Documents
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="flex-grow">
                        <Accordion type="single" collapsible className="w-full">
                          <AccordionItem value="users">
                            <AccordionTrigger>View Users</AccordionTrigger>
                            <AccordionContent>
                              {company.users.length > 0 ? (
                                <ul className="space-y-2 pt-2">
                                  {company.users.map((user) => (
                                    <li
                                      key={user.uid}
                                      className="flex items-center space-x-3"
                                    >
                                      <Avatar className="h-8 w-8">
                                        <AvatarFallback>
                                          {user.name
                                            ? user.name.charAt(0).toUpperCase()
                                            : "?"}
                                        </AvatarFallback>
                                      </Avatar>
                                      <div className="text-sm">
                                        <p className="font-medium">
                                          {user.name || user.email}
                                        </p>
                                        <p className="text-muted-foreground">
                                          {user.role}
                                        </p>
                                      </div>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-sm text-muted-foreground pt-2">
                                  No users assigned to this company.
                                </p>
                              )}
                            </AccordionContent>
                          </AccordionItem>
                        </Accordion>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
            <TabsContent value="users" className="mt-4">
              <UserManagement />
            </TabsContent>
            <TabsContent value="audit" className="mt-4">
              <AuditLogViewer customerId="test_project_123" />
            </TabsContent>
            <TabsContent value="companies" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Company Management</CardTitle>
                  <CardDescription>
                    View and manage companies in the system
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="py-8 text-center">
                    <p className="text-muted-foreground mb-4">Company management interface under development</p>
                    <Button variant="outline">Add New Company</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="settings" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Global Settings</CardTitle>
                  <CardDescription>
                    Configure system-wide settings
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="py-8 text-center">
                    <p className="text-muted-foreground mb-4">Global settings interface under development</p>
                    <Button variant="outline">Configure Settings</Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </AdminLayout>
    </AdminGuard>
  );
}
