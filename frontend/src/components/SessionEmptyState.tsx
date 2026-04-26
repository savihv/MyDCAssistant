import React from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

interface SessionEmptyStateProps {
  variant: 'no-sessions' | 'no-selected-session' | 'loading-error';
  errorMessage?: string;
  onRetry?: () => void;
}

/**
 * Empty state component specifically for technician session views
 * Handles different empty state scenarios in the troubleshooting interface
 */
export function SessionEmptyState({ 
  variant, 
  errorMessage, 
  onRetry 
}: SessionEmptyStateProps) {
  const navigate = useNavigate();

  const content = {
    'no-sessions': {
      title: "No troubleshooting sessions yet",
      description: "Start a new session to capture images, videos, or voice commands and get AI assistance with your issue.",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
          <path d="M2 12a5 5 0 0 0 5 5 5 5 0 0 0 5-5 5 5 0 0 0-5-5 5 5 0 0 0-5 5Z"/>
          <path d="m12 7 5-5 5 5"/>
          <path d="M22 12a5 5 0 0 1-5 5 5 5 0 0 1-5-5 5 5 0 0 1 5-5 5 5 0 0 1 5 5Z"/>
          <path d="m12 17 5 5 5-5"/>
          <path d="M12 12a5 5 0 0 1-5 5 5 5 0 0 1-5-5 5 5 0 0 1 5-5 5 5 0 0 1 5 5Z"/>
          <path d="m12 7-5-5-5 5"/>
          <path d="M12 12a5 5 0 0 0 5 5 5 5 0 0 0 5-5 5 5 0 0 0-5-5 5 5 0 0 0-5 5Z"/>
          <path d="m12 17-5 5-5-5"/>
        </svg>
      ),
      actionLabel: "Start New Session",
      onAction: () => navigate("/SessionCreate")
    },
    'no-selected-session': {
      title: "Select a session",
      description: "Choose a troubleshooting session from the list or start a new one to get help with your technical issue.",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
          <path d="M12 20h9"/>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
        </svg>
      ),
      actionLabel: "Start New Session",
      onAction: () => navigate("/SessionCreate")
    },
    'loading-error': {
      title: "Couldn't load sessions",
      description: errorMessage || "There was an error loading your troubleshooting sessions. Please try again.",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-500">
          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
          <path d="M12 9v4"/>
          <path d="M12 17h.01"/>
        </svg>
      ),
      actionLabel: "Try Again",
      onAction: onRetry
    }
  };

  const selectedContent = content[variant];

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-lg border border-border bg-card/50 h-full min-h-[300px]">
      <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
        {selectedContent.icon}
      </div>
      <h3 className="text-lg font-medium mb-2">{selectedContent.title}</h3>
      <p className="text-muted-foreground mb-6 max-w-md">{selectedContent.description}</p>
      
      {selectedContent.actionLabel && (
        <Button onClick={selectedContent.onAction}>
          {selectedContent.actionLabel}
        </Button>
      )}
    </div>
  );
}
