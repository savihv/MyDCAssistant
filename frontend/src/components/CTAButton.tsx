import React from "react";
import { Button } from "../components/Button";

interface Props {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  disabled?: boolean;
}

export function CTAButton({ children, onClick, className = "", disabled = false }: Props) {
  return (
    <Button
      onClick={onClick}
      variant="default"
      className={className}
      disabled={disabled}
    >
      {children}
    </Button>
  );
}
