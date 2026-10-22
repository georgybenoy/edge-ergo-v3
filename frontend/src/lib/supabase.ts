import { createClient, SupabaseClient } from "@supabase/supabase-js";

/**
 * Validates that required Vite public environment variables are supplied.
 */
export function getMissingEnvConfig(): string[] {
  const missing: string[] = [];
  const url = import.meta.env.VITE_SUPABASE_URL;
  const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

  if (!url || typeof url !== "string" || url.trim() === "") {
    missing.push("VITE_SUPABASE_URL");
  }
  if (!key || typeof key !== "string" || key.trim() === "") {
    missing.push("VITE_SUPABASE_PUBLISHABLE_KEY");
  }
  return missing;
}

const missing = getMissingEnvConfig();

/**
 * Singleton Supabase client instance.
 * Initialized only when configuration is present.
 */
export const supabase: SupabaseClient | null =
  missing.length === 0
    ? createClient(
        import.meta.env.VITE_SUPABASE_URL as string,
        import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string,
        {
          auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true,
            storageKey: "edgeergo_dashboard_auth",
          },
        }
      )
    : null;
