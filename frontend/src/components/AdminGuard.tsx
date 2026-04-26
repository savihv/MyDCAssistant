import React from "react";import { useCurrentUser } from "../app";
import { Navigate, useLocation } from "react-router-dom"; // Added useLocation
import { Spinner } from "../components/Spinner";
import { useUserRoles } from "../utils/useUserRoles"; // Import useUserRoles

interface Props {
  children: React.ReactNode;
  /**
   * Allowed roles for this component. If not specified, any admin role is allowed.
   */
  allowedRoles?: ('company_admin' | 'system_admin')[];
}

/**
 * Guard component for admin-only pages
 * Redirects if user is not authorized based on roles from useUserRoles.
 */
export function AdminGuard({ children, allowedRoles }: Props) {
  const { user, loading: userLoading } = useCurrentUser();
  const { 
    role, // This is the role string like 'company_admin', 'system_admin', or 'technician'
    isSystemAdmin, 
    isCompanyAdmin, 
    loading: rolesLoading 
  } = useUserRoles();
  
  const location = useLocation(); // For redirect state

  const isLoading = userLoading || rolesLoading;

  // Show loading state while user or roles are loading
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  // If no user (should be caught by useCurrentUser, but good to double check after loading)
  if (!user) {
    console.log("AdminGuard: No user found after loading, redirecting to login.");
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Authorization Logic based on useUserRoles
  // role from useUserRoles is the primary determinant here.
  // isSystemAdmin and isCompanyAdmin are booleans derived from that role.

  // Check if the user has any admin role (either system_admin or company_admin)
  const hasAnAdminRole = isSystemAdmin || isCompanyAdmin;

  if (!hasAnAdminRole) {
    console.log(`AdminGuard: User ${user.email} with role '${role}' is not an admin. Redirecting.`);
    // Redirect non-admins to a general app page or home.
    return <Navigate to="/app" replace />; 
  }

  // If allowedRoles are specified, check if the user's role (from useUserRoles) matches.
  if (allowedRoles && allowedRoles.length > 0) {
    if (!role || !allowedRoles.includes(role as 'company_admin' | 'system_admin')) {
      console.log(`AdminGuard: User ${user.email} with role '${role}' does not have required roles: ${allowedRoles.join(', ')}. Redirecting.`);
      // Redirect to a general admin dashboard or a "not authorized" specific page.
      // Using /app/dashboard as a fallback for admins who don't meet specific criteria.
      return <Navigate to="/app/dashboard" replace />;
    }
  }

  // If all checks pass (user is an admin and, if specified, has an allowed role)
  console.log(`AdminGuard: User ${user.email} with role '${role}' is authorized.`);
  return <>{children}</>;
}
