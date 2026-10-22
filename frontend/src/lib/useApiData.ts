import { useState, useEffect, useCallback, useRef } from "react";
import { ApiError } from "./api";

export interface UseApiDataOptions<T> {
  fetcher: (signal: AbortSignal) => Promise<T>;
  enabled?: boolean;
  deps?: unknown[];
  staleTimeMs?: number; // Milliseconds before data is marked stale. Default 60,000 (1 min)
  onSuccess?: (data: T) => void;
  onError?: (error: Error | ApiError) => void;
}

export interface UseApiDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | ApiError | null;
  isStale: boolean;
  lastUpdated: Date | null;
  refetch: () => Promise<void>;
  abort: () => void;
}

/**
 * Robust data hook providing loading, error, empty, stale states,
 * abortable requests, and last-successful-update timestamps.
 */
export function useApiData<T>({
  fetcher,
  enabled = true,
  deps = [],
  staleTimeMs = 60000,
  onSuccess,
  onError,
}: UseApiDataOptions<T>): UseApiDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const staleTimerRef = useRef<number | null>(null);

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const executeFetch = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    // Cancel any ongoing fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    // If we already had data, mark stale while refetching
    if (data !== null) {
      setIsStale(true);
    }

    try {
      const result = await fetcher(controller.signal);
      // If controller aborted, return early
      if (controller.signal.aborted) {
        return;
      }
      setData(result);
      const now = new Date();
      setLastUpdated(now);
      setIsStale(false);
      setError(null);
      if (onSuccess) {
        onSuccess(result);
      }

      // Schedule stale timer
      if (staleTimerRef.current) {
        window.clearTimeout(staleTimerRef.current);
      }
      if (staleTimeMs > 0) {
        staleTimerRef.current = window.setTimeout(() => {
          setIsStale(true);
        }, staleTimeMs);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) {
        // Ignored abort
        return;
      }
      const typedErr =
        err instanceof Error
          ? (err as Error | ApiError)
          : new Error("An unexpected error occurred.");
      setError(typedErr);
      if (onError) {
        onError(typedErr);
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [enabled, fetcher, staleTimeMs, onSuccess, onError]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    executeFetch();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (staleTimerRef.current) {
        window.clearTimeout(staleTimerRef.current);
      }
    };
  }, [executeFetch, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    data,
    loading,
    error,
    isStale,
    lastUpdated,
    refetch: executeFetch,
    abort,
  };
}
