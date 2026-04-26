import React from "react";
import { Button } from "../components/Button";

interface Props {
  title: string;
  description: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
}

/**
 * Reusable empty state component for displaying when no content is available
 */
export function EmptyState({ 
  title, 
  description, 
  icon, 
  actionLabel, 
  onAction 
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      {icon && (
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground mt-2 text-center max-w-md">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button 
          variant="outline" 
          className="mt-4"
          onClick={onAction}
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
}