import React, { createContext, useContext, useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import { fetchMe, UserProfileResponse } from "../../lib/api";

interface UserProfileContextType {
  profile: UserProfileResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const UserProfileContext = createContext<UserProfileContextType | undefined>(undefined);

export const UserProfileProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status, accessToken, markSessionExpired } = useAuth();
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [refetchIndex, setRefetchIndex] = useState(0);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) {
      setProfile(null);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchMe(accessToken, controller.signal)
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setLoading(false);
        if ((err as { status?: number }).status === 401) {
          markSessionExpired();
        } else {
          setError(
            (err as { message?: string }).message || "Unable to load user organization profile."
          );
        }
      });

    return () => {
      controller.abort();
    };
  }, [status, accessToken, markSessionExpired, refetchIndex]);

  const refetch = () => setRefetchIndex((i) => i + 1);

  return (
    <UserProfileContext.Provider value={{ profile, loading, error, refetch }}>
      {children}
    </UserProfileContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export function useUserProfile(): UserProfileContextType {
  const ctx = useContext(UserProfileContext);
  if (!ctx) {
    throw new Error("useUserProfile must be used within a UserProfileProvider");
  }
  return ctx;
}
