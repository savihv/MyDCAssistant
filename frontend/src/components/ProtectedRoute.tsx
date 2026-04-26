import React from 'react';
import { UserGuard } from 'app';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * ProtectedRoute component using the Firebase UserGuard
 * 
 * This is a wrapper around the UserGuard component from the Firebase extension
 * that provides a consistent interface for protecting routes in the app.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  // The UserGuard from the Firebase extension handles auth state, loading, and redirects
  return <UserGuard>{children}</UserGuard>;
}
