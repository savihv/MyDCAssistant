import React, { useEffect, useState } from 'react';
import { useCurrentUser } from 'app';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, InfoIcon } from 'lucide-react';
import { doc, getDoc, getFirestore, DocumentSnapshot } from 'firebase/firestore';
import { firebaseApp } from 'app';
import { COLLECTIONS } from '../utils/firestore-schema';

interface PendingApprovalProps {
  onRedirect?: () => void;
}

export function PendingApproval({ onRedirect }: PendingApprovalProps) {
  const { user } = useCurrentUser();
  const [approvalStatus, setApprovalStatus] = useState<string | null>(null);
  const [requestedRole, setRequestedRole] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchApprovalStatus = async () => {
      if (!user) return;
      
      try {
        setLoading(true);
        // Get the user doc from Firestore to check approval status
        const firestore = getFirestore(firebaseApp);
        let userDoc: DocumentSnapshot | null = null;
        
        try {
          userDoc = await getDoc(doc(firestore, COLLECTIONS.USERS, user.uid));
        } catch (error) {
          console.error('Error fetching user document:', error);
          // If collection doesn't exist, assume user is approved
          setLoading(false);
          return;
        }
        
        if (userDoc && userDoc.exists()) {
          const userData = userDoc.data();
          setApprovalStatus(userData.approvalStatus || null);
          setRequestedRole(userData.role || null);
          setRejectionReason(userData.rejectionReason || null);
        }
      } catch (error) {
        console.error('Error fetching approval status:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchApprovalStatus();
  }, [user]);
  
  if (loading || !approvalStatus || approvalStatus === 'approved') {
    return null;
  }
  
  // Helper function to format role name for display
  const formatRole = (role: string | null) => {
    if (!role) return 'user';
    
    switch (role) {
      case 'technician':
        return 'Technician';
      case 'company_admin':
        return 'Company Admin';
      case 'system_admin':
        return 'System Admin';
      default:
        return role;
    }
  };
  
  if (approvalStatus === 'pending_approval') {
    return (
      <Alert variant="destructive" className="my-4 border-yellow-600 bg-yellow-700/10">
        <AlertCircle className="h-5 w-5 text-yellow-500" />
        <AlertTitle className="text-yellow-500">Account Pending Approval</AlertTitle>
        <AlertDescription>
          <p className="mb-2">
            Your account request for {formatRole(requestedRole)} role is pending approval. 
            You will have limited access until your account is approved.
          </p>
          {onRedirect && (
            <Button 
              variant="outline" 
              className="mt-2 border-yellow-600 text-yellow-500 hover:bg-yellow-500 hover:text-black" 
              onClick={onRedirect}
            >
              Go to Home Page
            </Button>
          )}
        </AlertDescription>
      </Alert>
    );
  }
  
  if (approvalStatus === 'rejected') {
    return (
      <Alert variant="destructive" className="my-4">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>Account Request Rejected</AlertTitle>
        <AlertDescription>
          <p className="mb-2">
            Your account request for {formatRole(requestedRole)} role was rejected.
          </p>
          {rejectionReason && (
            <p className="mb-2">
              <strong>Reason:</strong> {rejectionReason}
            </p>
          )}
          <p>
            Please contact a system administrator for more information.
          </p>
        </AlertDescription>
      </Alert>
    );
  }
  
  return null;
}
