import { useCallback, useEffect, useRef, useState } from 'react';

export interface ApiResourceState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Loads an API resource with explicit loading/error/success states and a manual retry.
 *
 * Dashboard views previously swallowed fetch failures (`.catch(() => {})`), which left
 * them stuck on a skeleton forever. This hook guarantees that any failure surfaces as a
 * user-visible error state instead.
 */
export function useApiResource<T>(fetcher: () => Promise<T>): ApiResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState<number>(0);

  // Keep the latest fetcher without making it an effect dependency (prevents refetch loops
  // when callers pass an inline arrow function).
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    fetcherRef
      .current()
      .then((res) => {
        if (!isMounted) return;
        setData(res);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setData(null);
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Failed to load data from the backend.'
        );
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { data, isLoading, error, reload };
}
