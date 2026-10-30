import { useCallback, useEffect, useRef, useState } from "react";
import type { DependencyList } from "react";
import { ApiError, errorMessage } from "@/api/client";

interface AsyncOptions {
  enabled?: boolean;
  pollMs?: number;
  keepDataOnError?: boolean;
}

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  status: number | null;
  loading: boolean;
  refresh: () => void;
  setData: (value: T | null) => void;
}

/**
 * Small data-loading primitive: abortable fetches, manual refresh, optional
 * polling. Polls do not flash the loading state and pause in background tabs.
 */
export function useAsync<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
  options: AsyncOptions = {},
): AsyncState<T> {
  const { enabled = true, pollMs, keepDataOnError = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const dataRef = useRef(data);
  dataRef.current = data;

  const refresh = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    const hasData = dataRef.current !== null;

    if (!hasData) setLoading(true);
    setError(null);

    loaderRef
      .current(controller.signal)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setStatus(200);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled || (cause instanceof DOMException && cause.name === "AbortError")) return;
        setStatus(cause instanceof ApiError ? cause.status : null);
        setError(errorMessage(cause));
        if (!keepDataOnError) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, ...deps]);

  useEffect(() => {
    if (!enabled || !pollMs) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [enabled, pollMs, refresh]);

  return { data, error, status, loading, refresh, setData };
}
