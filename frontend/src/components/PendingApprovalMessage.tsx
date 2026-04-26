import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { JuniorTechBotLogo } from './JuniorTechBotLogo';

interface PendingApprovalMessageProps {
  role: string;
  company?: string;
}

export function PendingApprovalMessage({ role, company = '' }: PendingApprovalMessageProps) {
  // Determine message based on role
  const isCompanyAdmin = role === 'company_admin';
  const approverType = isCompanyAdmin ? 'system administrators' : 'company administrators';
  const roleDisplay = isCompanyAdmin ? 'Company Admin' : 'Technician';
  
  return (
    <Card className="mx-auto max-w-md border-yellow-600/50 bg-yellow-950/20">
      <CardHeader className="pb-3">
        <div className="flex flex-col items-center mb-2">
          <JuniorTechBotLogo className="w-12 h-12 mb-2" />
          <CardTitle className="text-center text-xl">
            Account Pending Approval
          </CardTitle>
        </div>
        <CardDescription className="text-center text-yellow-400">
          Your request is being reviewed
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <p className="text-sm text-center">
            Your request for a <span className="font-semibold text-yellow-400">{roleDisplay}</span> account
            {company && <span> at <span className="font-semibold text-yellow-400">{company}</span></span>} is 
            currently under review by {approverType}.
          </p>
          <p className="text-sm text-center">
            You'll receive an email notification once your request has been reviewed.
            Thank you for your patience.
          </p>
          <div className="flex items-center justify-center space-x-1 text-yellow-400/70 mt-4">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="">
              <circle cx="12" cy="12" r="10"/>
              <path d="m12 8 4 4-4 4"/>
              <path d="m8 12h8"/>
            </svg>
            <p className="text-xs">You'll gain full access once approved</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
