import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Skeleton } from "../../components/ui/Skeleton";

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div
        role="status"
        aria-label="Checking authentication"
        className="min-h-screen bg-bg flex flex-col p-6 max-w-7xl mx-auto space-y-6"
      >
        <div className="flex justify-between items-center h-16 border-b border-border/50">
          <Skeleton className="w-32 h-8" />
          <div className="flex gap-4">
            <Skeleton className="w-20 h-8" />
            <Skeleton className="w-20 h-8" />
            <Skeleton className="w-10 h-10 rounded-full" />
          </div>
        </div>
        <div className="space-y-4 pt-4">
          <Skeleton className="w-64 h-8" />
          <Skeleton className="w-96 h-4" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  if (status === "unauthenticated" || status === "expired") {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
