import { useState, useEffect } from 'react';
import { useCurrentUser } from 'app';

/**
 * Hook to properly extract user roles from Firebase ID token claims
 * Fixed to prevent role toggling by waiting for auth to fully complete
 */
import { User } from 'firebase/auth'; // Ensure User type is imported

export interface UserRolesResult {
  role: string | null;
  isSystemAdmin: boolean;
  isCompanyAdmin: boolean;
  isTechnician: boolean;
  company: string | null;
  loading: boolean;
  debug?: {
    userEmail: string | null | undefined;
    claims: any;
    userLoading: boolean;
    claimsLoading: boolean;
  };
}

export function useUserRoles(): UserRolesResult {
  const { user, loading: userLoading } = useCurrentUser();
  const [role, setRole] = useState('');
  const [isSystemAdmin, setIsSystemAdmin] = useState(false);
  const [isCompanyAdmin, setIsCompanyAdmin] = useState(false);
  const [isTechnician, setIsTechnician] = useState(false); // Added isTechnician state
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [claims, setClaims] = useState(null);
  const [company, setCompany] = useState<string | null>(null);

  // Only run this effect when user or userLoading changes
  useEffect(() => {
    // If still loading auth, don't do anything yet
    if (userLoading) {
      return;
    }
    
    // Auth loading finished but no user is logged in
    if (!user) {
      console.log('No user logged in, defaulting to technician role');
      setRole(null);
      setIsTechnician(false);
      setIsSystemAdmin(false);
      setIsCompanyAdmin(false);
      // setIsTechnician(false); // Already set above
      setCompany(null); // Reset company on error or no user
      setClaimsLoading(false);
      return;
    }
    
    // User is logged in, get their token claims
    console.log('User logged in, getting token claims...', user.email);
    
    user.getIdTokenResult(true) // Force refresh to get latest claims
      .then(idTokenResult => {
        const userRole = (idTokenResult.claims.role as string) || 'technician';
        
        console.log('🔶 Token claims received:', idTokenResult.claims);
        console.log('🔶 Role from token:', userRole);
        console.log('🔶 Is system admin?', userRole === 'system_admin');
        
        setClaims(idTokenResult.claims);
        setRole(userRole);
        setIsSystemAdmin(userRole === 'system_admin');
        setIsCompanyAdmin(userRole === 'company_admin');
        setIsTechnician(userRole === 'technician');
        
        const companyClaim = (idTokenResult.claims.company as string) || null; 
        setCompany(companyClaim);
        // console.log('🔶 Company from token claims:', companyClaim); // Optional: remove debug logs
        setClaimsLoading(false);
      })
      .catch(error => {
        console.error('❌ Error getting token claims:', error);
        setRole('technician'); // Safe default
        setIsSystemAdmin(false);
        setIsCompanyAdmin(false);
        setIsTechnician(true);
        setCompany(null); // Reset company on error or no user
        setClaimsLoading(false);
      });
  }, [user, userLoading]);

  return {
    role,
    isSystemAdmin,
    isCompanyAdmin,
    isTechnician, // Added isTechnician to return object
    company,
    loading: userLoading || claimsLoading,
    debug: { 
      userEmail: user?.email || 'none',
      claims,
      userLoading,
      claimsLoading
    }
  };
}