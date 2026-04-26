import React from "react";
import { AdminLayout } from "../components/AdminLayout";
import { lazy, Suspense } from "react";
//import { useCurrentUser } from ".";
import { useCurrentUser, firebaseAuth } from "../app";
import { useUserRoles } from "../utils/useUserRoles";
import App from "./App";
import { Spinner } from "../components/Spinner";

// Lazy load the role-specific dashboards
const SystemAdminDashboard = lazy(() => import("../pages/SystemAdminDashboard"));
const CompanyAdminDashboard = lazy(() => import("../pages/CompanyAdminDashboard"));
const TechnicianDashboard = lazy(() => import("../components/TechnicianDashboard"));

export default function AdminDashboard() {
  const { user, loading: userLoading } = useCurrentUser();
  const { role, isSystemAdmin, isCompanyAdmin, loading: roleLoading } = useUserRoles();

  // Loading indicator while role information is being retrieved
  const isLoading = userLoading || roleLoading;

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // Role-based rendering
  if (isSystemAdmin) {
    return (
      <AdminLayout activeTab="dashboard">
        <Suspense fallback={<Spinner />}>
          <SystemAdminDashboard />
        </Suspense>
      </AdminLayout>
    );
  }

  if (isCompanyAdmin) {
    return (
      <AdminLayout activeTab="dashboard">
        <Suspense fallback={<Spinner />}>
          <CompanyAdminDashboard />
        </Suspense>
      </AdminLayout>
    );
  }

  // Default to TechnicianDashboard for any authenticated user who is not an admin
  if (user) {
    return (
      <AdminLayout activeTab="dashboard">
        <Suspense fallback={<Spinner />}>
          <TechnicianDashboard />
        </Suspense>
      </AdminLayout>
    );
  }

  // Fallback for non-authenticated users to the main app page
  return <App />;
}
