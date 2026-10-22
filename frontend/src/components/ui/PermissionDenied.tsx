import React from "react";
import { ShieldAlert } from "lucide-react";
import { Button } from "./Button";
import { cn } from "../../lib/utils";

export interface PermissionDeniedProps {
  title?: string;
  message?: string;
  onReturn?: () => void;
  className?: string;
}

export const PermissionDenied: React.FC<PermissionDeniedProps> = ({
  title = "Access Denied",
  message = "Your current account or role does not have authorization to view this resource. Contact an organization administrator if you believe this is an error.",
  onReturn,
  className,
}) => {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center text-center p-8 sm:p-12 border border-border rounded-card bg-surface-raised max-w-lg mx-auto my-12",
        className
      )}
    >
      <div className="p-3 mb-4 rounded-full bg-warning/10 text-warning" aria-hidden="true">
        <ShieldAlert className="w-10 h-10" />
      </div>
      <h2 className="text-xl font-semibold text-text-primary mb-2">{title}</h2>
      <p className="text-sm text-text-secondary mb-6 leading-relaxed">{message}</p>
      {onReturn && (
        <Button variant="secondary" onClick={onReturn}>
          Return to Dashboard
        </Button>
      )}
    </div>
  );
};
