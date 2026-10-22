import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "../../lib/supabase";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "expired";

export interface AuthContextType {
  status: AuthStatus;
  user: User | null;
  session: Session | null;
  accessToken: string | null;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  markSessionExpired: () => void;
  resetPasswordForEmail: (email: string) => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<Session | null>(null);

  // Restore session & attach listener
  useEffect(() => {
    if (!supabase) {
      setStatus("unauthenticated");
      return;
    }

    let isMounted = true;

    // 1. Initial session restoration
    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!isMounted) return;
        if (error || !data.session) {
          setSession(null);
          setStatus("unauthenticated");
        } else {
          setSession(data.session);
          setStatus("authenticated");
        }
      })
      .catch(() => {
        if (isMounted) {
          setSession(null);
          setStatus("unauthenticated");
        }
      });

    // 2. Auth state change listener (token refresh, sign out, sign in)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, newSession) => {
      if (!isMounted) return;

      if (event === "SIGNED_IN" && newSession) {
        setSession(newSession);
        setStatus("authenticated");
      } else if (event === "SIGNED_OUT") {
        setSession(null);
        setStatus("unauthenticated");
      } else if (event === "TOKEN_REFRESHED" && newSession) {
        setSession(newSession);
        setStatus("authenticated");
      } else if (event === "USER_UPDATED" && newSession) {
        setSession(newSession);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(
    async (email: string, password: string): Promise<{ error: string | null }> => {
      if (!supabase) {
        return { error: "Supabase client is not configured." };
      }
      try {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) {
          return { error: error.message };
        }
        if (data.session) {
          setSession(data.session);
          setStatus("authenticated");
        }
        return { error: null };
      } catch {
        return { error: "Unable to complete sign-in request. Please try again." };
      }
    },
    []
  );

  const signOut = useCallback(async () => {
    if (supabase) {
      try {
        await supabase.auth.signOut();
      } catch {
        // Fallback local cleanup even if remote call fails
      }
    }
    setSession(null);
    setStatus("unauthenticated");
  }, []);

  const markSessionExpired = useCallback(() => {
    setSession(null);
    setStatus("expired");
  }, []);

  const resetPasswordForEmail = useCallback(
    async (email: string): Promise<{ error: string | null }> => {
      if (!supabase) {
        return { error: "Supabase client is not configured." };
      }
      try {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/login?reset=true`,
        });
        if (error) {
          return { error: error.message };
        }
        return { error: null };
      } catch {
        return { error: "Unable to process password reset request." };
      }
    },
    []
  );

  return (
    <AuthContext.Provider
      value={{
        status,
        user: session?.user ?? null,
        session,
        accessToken: session?.access_token ?? null,
        signIn,
        signOut,
        markSessionExpired,
        resetPasswordForEmail,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
